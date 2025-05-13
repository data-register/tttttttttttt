"""
Помощни функции за работа с FFmpeg за извличане на кадри от видео потоци
"""

import os
import time
import subprocess
import tempfile
from datetime import datetime
import cv2
import numpy as np
from pathlib import Path

from utils.logger import setup_logger
from .cache import frame_cache

# Инициализиране на логър
logger = setup_logger("ffmpeg_utils")

def check_ffmpeg_installed():
    """
    Проверява дали FFmpeg е инсталиран и достъпен
    
    Returns:
        bool: True ако FFmpeg е наличен, False в противен случай
    """
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE,
                                timeout=3)
        
        if result.returncode == 0:
            version = result.stdout.decode('utf-8', errors='ignore').split('\n')[0]
            logger.info(f"FFmpeg наличен: {version}")
            return True
        else:
            logger.warning("FFmpeg не е намерен (грешка при изпълнение)")
            return False
            
    except Exception as e:
        logger.warning(f"Грешка при проверка за FFmpeg: {str(e)}")
        return False

def capture_frame_from_stream(stream_url, output_path=None, timeout=15):
    """
    Извлича единичен кадър от поток използвайки FFmpeg
    
    Args:
        stream_url (str): URL на видео потока (RTSP, HLS, RTMP и т.н.)
        output_path (str, optional): Път за запазване на изображението. 
                                     Ако е None, се създава временен файл.
        timeout (int): Таймаут в секунди
        
    Returns:
        tuple: (успех (bool), път до файла или None, съобщение за грешка)
    """
    # Ако няма зададен изходен файл, създаваме временен
    if output_path is None:
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time())
        output_path = os.path.join(temp_dir, f"snapshot_{timestamp}.jpg")
    
    try:
        # Скриваме реалния URL със звездички, ако съдържа потребител/парола
        if '@' in stream_url:
            masked_url = stream_url.split('@')
            auth_part = masked_url[0].split('//')
            masked_url = f"{auth_part[0]}//*****@{masked_url[1]}"
        else:
            masked_url = stream_url
            
        logger.info(f"Извличане на кадър от {masked_url} чрез FFmpeg")
        
        # Оптимизирана FFmpeg команда, специално за HLS потоци
        # Отнема по-малко време и е по-надеждна
        cmd = [
            'ffmpeg',
            '-y',  # Презаписване на изходния файл без питане
            '-loglevel', 'error',  # Показване само на грешки
            '-timeout', str(timeout * 1000000),  # Таймаут в микросекунди
            '-analyzeduration', '1000000',  # По-кратко време за анализ (1 секунда)
            '-probesize', '1000000',  # По-малък размер за проба
        ]
        
        # Добавяме специални опции за различни видове потоци
        if stream_url.endswith('.m3u8'):  # HLS поток
            cmd.extend([
                '-protocol_whitelist', 'file,http,https,tcp,tls',  # Разрешени протоколи
                '-fflags', '+discardcorrupt+genpts',  # Игнориране на повредени данни и генериране на timestamps
            ])
        
        # Добавяме входящия поток и опциите за изход
        cmd.extend([
            '-i', stream_url,  # Входен URL
            '-frames:v', '1',  # Вземи само един кадър
            '-q:v', '2',  # Високо качество
            output_path  # Изходен файл
        ])
        
        # Изпълняваме командата
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout  # Таймаут за цялата операция
        )
        
        # Проверяваме дали командата е успешна и файлът съществува
        if process.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            error_msg = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"FFmpeg не успя да извлече кадър: {error_msg}")
            
            # Опитваме с алтернативна команда, ако първата не успее (специално за HLS)
            if stream_url.endswith('.m3u8'):
                logger.info("Опитваме с алтернативна команда за HLS...")
                alt_cmd = [
                    'ffmpeg', '-y', 
                    '-loglevel', 'error',
                    '-fflags', 'nobuffer',
                    '-flags', 'low_delay',
                    '-strict', 'experimental',
                    '-i', stream_url,
                    '-frames:v', '1',
                    '-update', '1',
                    output_path
                ]
                
                alt_process = subprocess.run(
                    alt_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout
                )
                
                if alt_process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f"Алтернативната команда за HLS успя: {output_path}")
                    return True, output_path, ""
                else:
                    alt_error_msg = alt_process.stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Алтернативната команда също не успя: {alt_error_msg}")
                    return False, None, error_msg + "\n" + alt_error_msg
            
            return False, None, error_msg
        
        logger.info(f"Успешно извлечен кадър с FFmpeg: {output_path}")
        return True, output_path, ""
        
    except subprocess.TimeoutExpired:
        logger.error(f"Таймаут при изпълнение на FFmpeg команда")
        return False, None, "Операцията надвиши таймаута"
        
    except Exception as e:
        logger.error(f"Грешка при изпълнение на FFmpeg: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False, None, str(e)

def get_frame_from_public_stream(stream_url="rtsp://admin:admin@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0", force_refresh=False, max_cache_age=5):
    """
    Извлича кадър от публичен видео поток с използване на кеш - локална версия
    
    Args:
        stream_url (str): URL на видео потока
        force_refresh (bool): Задължително обновяване на кадъра, независимо от кеша
        max_cache_age (int): Максимална възраст на кеширания кадър в секунди
        
    Returns:
        numpy.ndarray или None: Кадър като изображение или None при грешка
    """
    try:
        # Генерираме уникален ключ за този поток в кеша
        cache_key = f"stream_{stream_url}"
        
        # Проверяваме за валиден кадър в кеша, освен ако не е поискано обновяване
        if not force_refresh:
            cached_frame, metadata = frame_cache.get_frame(cache_key, max_age=max_cache_age)
            if cached_frame is not None:
                logger.debug(f"Използване на кеширан кадър за {stream_url}, възраст: {metadata.get('age', 'unknown')}")
                return cached_frame
        
        # Ако нямаме кеширан кадър, продължаваме с извличане на нов
        logger.info(f"Извличане на нов кадър от поток {stream_url}")
        
        # Използваме директно подадения URL
        rtsp_url = stream_url
        
        # Създаваме frames директория ако не съществува
        frames_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Използваме постоянен път за последния кадър - за лесен преглед
        latest_path = os.path.join(frames_dir, "latest.jpg")
        
        # Създаваме и нов кадър с timestamp - за архив
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_path = os.path.join(frames_dir, f"frame_{timestamp_str}.jpg")
        
        # Директна FFmpeg команда за извличане на кадър - опростен вариант за локална работа
        cmd = [
            'ffmpeg',
            '-y',                   # Презаписване без питане
            '-rtsp_transport', 'tcp',  # По-надеждно за RTSP
            '-i', rtsp_url,         # RTSP URL
            '-frames:v', '1',       # Само един кадър
            '-q:v', '1',            # Най-високо качество
            latest_path             # Изходен файл
        ]
        
        logger.info(f"Изпълнение на FFmpeg команда локално: ffmpeg -rtsp_transport tcp -i {rtsp_url} -frames:v 1 -q:v 1 {latest_path}")
        
        try:
            # Изпълняваме командата
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15  # По-дълъг таймаут за локална среда
            )
            
            # Проверяваме резултата
            if process.returncode == 0 and os.path.exists(latest_path) and os.path.getsize(latest_path) > 0:
                # Копираме в архивния файл
                import shutil
                shutil.copy(latest_path, timestamp_path)
                
                # Зареждаме изображението
                frame = cv2.imread(latest_path)
                
                if frame is not None:
                    # Добавяме timestamp
                    frame_with_timestamp = add_timestamp_to_frame(
                        frame,
                        position="bottom-right",
                        text="Obzor PTZ Camera"
                    )
                    
                    # Запазваме обратно с timestamp
                    cv2.imwrite(latest_path, frame_with_timestamp)
                    
                    # Запазваме в кеша
                    metadata = {
                        'source': rtsp_url,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'type': 'rtsp_capture_local',
                        'path': latest_path
                    }
                    
                    frame_cache.store_frame(frame_with_timestamp, cache_key, metadata=metadata, max_age=max_cache_age)
                    logger.info(f"Успешно извлечен кадър от RTSP, записан в {latest_path} и {timestamp_path}")
                    
                    return frame_with_timestamp
                else:
                    logger.error(f"Не може да се зареди изображението от {latest_path}")
            else:
                error_output = process.stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg грешка: {error_output}")
        
        except Exception as e:
            logger.error(f"Грешка при изпълнение на FFmpeg: {str(e)}")
        
        # Алтернативен метод с OpenCV
        logger.info("Опитваме с OpenCV VideoCapture")
        
        try:
            # Настройваме параметрите за OpenCV
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
            
            # Отваряме потока
            cap = cv2.VideoCapture(rtsp_url)
            
            # Задаваме опция за намаляване на кеширането/буферирането
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if cap.isOpened():
                # Прочитаме първия кадър
                for i in range(3):  # Опитваме няколко пъти за по-голяма сигурност
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        break
                    time.sleep(0.5)
                
                # Освобождаваме камерата веднага
                cap.release()
                
                if ret and frame is not None:
                    # Добавяме timestamp
                    frame_with_timestamp = add_timestamp_to_frame(
                        frame,
                        position="bottom-right",
                        text="PTZ Camera (OpenCV)"
                    )
                    
                    # Запазваме кадрите
                    cv2.imwrite(latest_path, frame_with_timestamp)
                    cv2.imwrite(timestamp_path, frame_with_timestamp)
                    
                    # Запазваме в кеша
                    metadata = {
                        'source': rtsp_url,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'type': 'opencv_capture_local',
                        'path': latest_path
                    }
                    
                    frame_cache.store_frame(frame_with_timestamp, cache_key, metadata=metadata, max_age=max_cache_age)
                    logger.info(f"Успешно извлечен кадър с OpenCV, записан в {latest_path}")
                    
                    return frame_with_timestamp
                else:
                    logger.error("OpenCV не успя да прочете кадър от RTSP потока")
            else:
                logger.error(f"OpenCV не успя да отвори RTSP потока: {rtsp_url}")
        
        except Exception as e:
            logger.error(f"Грешка при OpenCV обработка: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Ако и двата метода са неуспешни, генерираме демо изображение
        logger.info("Генериране на демо изображение след неуспешни опити")
        
        try:
            # Създаваме базово изображение
            height, width = 480, 640
            image = np.zeros((height, width, 3), dtype=np.uint8)
            image[:, :, :] = (30, 50, 70)  # Тъмно синьо-сив фон
            
            # Добавяме информация
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cv2.putText(
                image,
                "PTZ Camera - Obzor",
                (50, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )
            
            cv2.putText(
                image,
                f"Време: {timestamp}",
                (50, 150),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 255),
                1
            )
            
            cv2.putText(
                image,
                f"Камера: {rtsp_url}",
                (50, 200),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (180, 180, 220),
                1
            )
            
            cv2.putText(
                image,
                "ГРЕШКА: Не може да се установи връзка с камерата",
                (50, 250),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (50, 50, 255),
                2
            )
            
            cv2.putText(
                image,
                "Проверете RTSP URL и мрежовата свързаност",
                (50, 300),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (100, 200, 200),
                1
            )
            
            # Добавяме рамка
            cv2.rectangle(image, (20, 20), (width-20, height-20), (100, 100, 180), 2)
            
            # Запазваме изображението
            cv2.imwrite(latest_path, image)
            
            # Запазваме в кеша
            metadata = {
                'source': rtsp_url,
                'timestamp': timestamp,
                'type': 'error_fallback',
                'path': latest_path
            }
            
            frame_cache.store_frame(image, cache_key, metadata=metadata, max_age=max_cache_age)
            logger.info(f"Генерирано заместващо изображение и записано в {latest_path}")
            
            return image
                
        except Exception as e:
            logger.error(f"Грешка при генериране на заместващо изображение: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Грешка при извличане на кадър от поток: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return None

def add_timestamp_to_frame(frame, position="bottom-right", text=None):
    """
    Добавя текущата дата и час като текст върху кадър
    
    Args:
        frame (numpy.ndarray): Входно изображение
        position (str): Позиция на текста (top-left, top-right, bottom-left, bottom-right)
        text (str): Допълнителен текст за добавяне (по избор)
        
    Returns:
        numpy.ndarray: Изображение с добавен текст
    """
    if frame is None:
        return None
        
    # Копираме кадъра, за да не променяме оригинала
    result = frame.copy()
    
    # Вземаме размерите на кадъра
    height, width = frame.shape[:2]
    
    # Текуща дата и час
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Комбиниран текст, ако има допълнителен
    if text:
        full_text = f"{timestamp} | {text}"
    else:
        full_text = timestamp
    
    # Определяме позицията според параметъра
    if position == "top-left":
        position = (10, 30)
    elif position == "top-right":
        # Изчисляваме ширината на текста, за да го позиционираме отдясно
        text_size = cv2.getTextSize(full_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        position = (width - text_size[0] - 10, 30)
    elif position == "bottom-left":
        position = (10, height - 20)
    else:  # bottom-right
        text_size = cv2.getTextSize(full_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
        position = (width - text_size[0] - 10, height - 20)
    
    # Добавяме черен контур около текста за по-добра четимост
    cv2.putText(
        result,
        full_text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        3  # По-дебел контур
    )
    
    # Добавяме белия текст върху контура
    cv2.putText(
        result,
        full_text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )
    
    return result