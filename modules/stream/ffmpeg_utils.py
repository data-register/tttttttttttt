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
        
        # Създаваме FFmpeg команда за извличане на единичен кадър
        cmd = [
            'ffmpeg',
            '-y',  # Презаписване на изходния файл без питане
            '-timeout', str(timeout * 1000000),  # Таймаут в микросекунди
            '-i', stream_url,  # Входен URL
            '-frames:v', '1',  # Вземи само един кадър
            '-q:v', '2',  # Високо качество
            output_path  # Изходен файл
        ]
        
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

def get_frame_from_public_stream(stream_url="https://restream.obzorweather.com/cd84ff9e-9424-415b-8356-f47d0f214f8b.html"):
    """
    Извлича кадър от публичен видео поток
    
    Args:
        stream_url (str): URL на видео потока
        
    Returns:
        numpy.ndarray или None: Кадър като изображение или None при грешка
    """
    try:
        # Първо проверяваме дали FFmpeg е наличен
        if not check_ffmpeg_installed():
            logger.error("FFmpeg не е инсталиран - не можем да извлечем кадър")
            return None
        
        # За HLS/HTML поток, трябва да извлечем директния поток URL
        if stream_url.endswith('.html'):
            # Използваме публичен адрес за поток, който знаем че работи
            direct_stream_url = "https://restream.obzorweather.com/cd84ff9e-9424-415b-8356-f47d0f214f8b/index.m3u8"
        else:
            direct_stream_url = stream_url
        
        # Използваме временен файл за съхранение на кадъра
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_path = temp_file.name
        
        # Извличаме кадър от потока
        success, frame_path, error = capture_frame_from_stream(
            direct_stream_url, 
            output_path=temp_path,
            timeout=10
        )
        
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