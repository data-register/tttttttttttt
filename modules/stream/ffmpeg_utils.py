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

def get_frame_from_public_stream(stream_url="https://restream.obzorweather.com/cd84ff9e-9424-415b-8356-f47d0f214f8b.html", force_refresh=False, max_cache_age=5):
    """
    Извлича кадър от публичен видео поток с използване на кеш
    
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
        
        # Първо проверяваме дали FFmpeg е наличен
        if not check_ffmpeg_installed():
            logger.error("FFmpeg не е инсталиран - не можем да извлечем кадър")
            return None
        
        # ВАЖНО: Винаги използваме директния HLS URL, който работи гарантирано
        # Вместо да опитваме да използваме RTSP, директно използваме HLS
        direct_stream_url = "https://restream.obzorweather.com/cd84ff9e-9424-415b-8356-f47d0f214f8b/index.m3u8"
        
        # Използваме временен файл за съхранение на кадъра
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Извличаме кадър от потока
        start_time = time.time()
        success, frame_path, error = capture_frame_from_stream(
            direct_stream_url, 
            output_path=temp_path,
            timeout=10
        )
        capture_time = time.time() - start_time
        
        if not success:
            logger.error(f"Не успяхме да извлечем кадър: {error}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
        
        # Зареждаме изображението с OpenCV
        frame = cv2.imread(temp_path)
        
        # Премахваме временния файл
        os.unlink(temp_path)
        
        if frame is None:
            logger.error("Файлът е създаден, но не може да се прочете като изображение")
            return None
        
        # Съхраняваме кадъра в кеша с метаданни
        metadata = {
            'capture_time': f"{capture_time:.2f}s",
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': stream_url,
            'resolution': f"{frame.shape[1]}x{frame.shape[0]}"
        }
        frame_cache.store_frame(frame, cache_key, metadata=metadata, max_age=max_cache_age)
        logger.info(f"Кадърът е съхранен в кеша с ключ {cache_key}")
            
        return frame
    
    except Exception as e:
        logger.error(f"Грешка при извличане на кадър от публичен поток: {str(e)}")
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