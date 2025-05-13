"""
Основна логика за захващане на кадри от RTSP поток
"""

import os
import cv2
import time
import threading
from datetime import datetime
import numpy as np
from PIL import Image
from io import BytesIO

from .config import get_capture_config, update_capture_config
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("capture")

def capture_frame() -> bool:
    """Извлича един кадър от RTSP потока и го записва като JPEG файл"""
    config = get_capture_config()
    
    try:
        logger.info(f"Опит за свързване с RTSP поток: {config.rtsp_url}")
        
        # Създаваме VideoCapture обект директно с FFMPEG backend
        cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
        
        # Проверяваме дали потокът е отворен
        if not cap.isOpened():
            logger.error(f"Не може да се отвори RTSP потока: {config.rtsp_url}")
            update_capture_config(status="error")
            return False
        
        logger.info("RTSP потокът е отворен успешно")
        
        # Конфигурация за по-добра работа
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Четем кадъра със 5-секунден таймаут
        has_frame = False
        start_time = time.time()
        frame = None
        
        while not has_frame and time.time() - start_time < 5:
            ret, frame = cap.read()
            if ret and frame is not None:
                has_frame = True
                break
            time.sleep(0.1)
        
        # Освобождаваме ресурсите
        cap.release()
        
        if not has_frame or frame is None:
            logger.error("Не може да се прочете кадър от RTSP потока")
            update_capture_config(status="error")
            return False
        
        # Преоразмеряваме кадъра, ако е нужно
        if config.width > 0 and config.height > 0:
            frame = cv2.resize(frame, (config.width, config.height))
        
        # Генерираме име на файла с текущата дата и час
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.jpg"
        filepath = os.path.join(config.save_dir, filename)
        
        # Записваме кадъра като JPEG файл
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.quality]

        # Записваме в три различни локации за по-голяма сигурност
        success_paths = []
        
        # 1. Основна директория
        try:
            cv2.imwrite(filepath, frame, encode_params)
            success_paths.append(filepath)
        except Exception as e:
            logger.warning(f"Не може да се запише в {filepath}: {str(e)}")

        # 2. latest.jpg в основната директория
        latest_path = os.path.join(config.save_dir, "latest.jpg")
        try:
            cv2.imwrite(latest_path, frame, encode_params)
            success_paths.append(latest_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {latest_path}: {str(e)}")
        
        # 3. static директория за уеб достъп
        static_path = "static/latest.jpg"
        try:
            os.makedirs("static", exist_ok=True)
            cv2.imwrite(static_path, frame, encode_params)
            success_paths.append(static_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {static_path}: {str(e)}")
            
        # Проверка дали поне един запис е успешен
        if not success_paths:
            logger.error("Не може да се запише кадърът в нито една локация")
            update_capture_config(status="error")
            return False
        
        # Обновяваме конфигурацията
        update_capture_config(
            last_frame_path=filepath,
            last_frame_time=datetime.now(),
            status="ok"
        )
        
        logger.info(f"Успешно запазен кадър в: {', '.join(success_paths)}")
        return True
        
    except Exception as e:
        logger.error(f"Грешка при извличане на кадър: {str(e)}")
        update_capture_config(status="error")
        return False

def get_placeholder_image() -> bytes:
    """Създава placeholder изображение, когато няма наличен кадър"""
    config = get_capture_config()
    
    # Създаване на празно изображение с текст
    height = config.height if config.height > 0 else 720
    width = config.width if config.width > 0 else 1280
    placeholder = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Добавяне на текст в зависимост от статуса
    if config.status == "initializing":
        message = "Waiting for first frame..."
    elif config.status == "error":
        message = "Error: Could not capture frame"
    else:
        message = "No image available"
    
    # Добавяне на текст към изображението
    cv2.putText(
        placeholder, 
        message, 
        (50, height // 2 - 40),
        cv2.FONT_HERSHEY_SIMPLEX, 
        1, 
        (255, 255, 255), 
        2
    )
    
    # Добавяме текуща дата и час
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(
        placeholder, 
        timestamp, 
        (50, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.7, 
        (200, 200, 255), 
        2
    )
    
    # Добавяме инфо за камерата
    cv2.putText(
        placeholder, 
        f"Camera URL: {config.rtsp_url}", 
        (50, height // 2 + 40),
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.7, 
        (200, 255, 200), 
        2
    )
    
    # Конвертиране към bytes
    is_success, buffer = cv2.imencode(".jpg", placeholder)
    if is_success:
        return BytesIO(buffer).getvalue()
    else:
        # Връщаме празен BytesIO, ако не успеем да кодираме
        return BytesIO().getvalue()

def capture_loop():
    """Основен цикъл за периодично извличане на кадри"""
    config = get_capture_config()
    
    while config.running:
        try:
            capture_frame()
        except Exception as e:
            logger.error(f"Неочаквана грешка в capture_loop: {str(e)}")
        
        # Обновяваме конфигурацията (за случай, че е променена)
        config = get_capture_config()
        
        # Спим до следващото извличане
        time.sleep(config.interval)

# Инициализиране на capture_thread
capture_thread = None

def start_capture_thread():
    """Стартира фонов процес за извличане на кадри"""
    global capture_thread
    
    if capture_thread is None or not capture_thread.is_alive():
        capture_thread = threading.Thread(target=capture_loop)
        capture_thread.daemon = True
        capture_thread.start()
        logger.info("Capture thread started")
        return True
    
    logger.info("Capture thread вече е стартиран")
    return False

def stop_capture_thread():
    """Спира фоновия процес за извличане на кадри"""
    update_capture_config(running=False)
    logger.info("Capture thread stopping")
    return True

def initialize():
    """Инициализира модула"""
    config = get_capture_config()
    
    # Създаваме необходимите директории
    directories = [config.save_dir, "static"]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Създадена директория: {directory}")
        except Exception as e:
            logger.warning(f"Проблем при създаване на директория {directory}: {str(e)}")
    
    # Тестваме записа в директориите
    for directory in directories:
        try:
            test_file = os.path.join(directory, "test_write.txt")
            with open(test_file, "w") as f:
                f.write(f"Test write at {datetime.now()}")
            os.remove(test_file)
            logger.info(f"Тест за запис в {directory}: OK")
        except Exception as e:
            logger.warning(f"Тест за запис в {directory}: Неуспешен - {str(e)}")
    
    # Създаваме placeholder за latest.jpg
    latest_path = os.path.join(config.save_dir, "latest.jpg")
    static_path = "static/latest.jpg"
    
    if not os.path.exists(latest_path) or not os.path.exists(static_path):
        height = config.height if config.height > 0 else 720
        width = config.width if config.width > 0 else 1280
        placeholder = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Текст за инициализация
        cv2.putText(
            placeholder, 
            "Waiting for first frame...", 
            (50, height // 2 - 40),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (255, 255, 255), 
            2
        )
        
        # Дата и час
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            placeholder, 
            timestamp, 
            (50, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (200, 200, 255), 
            2
        )
        
        # Информация за URL
        cv2.putText(
            placeholder, 
            config.rtsp_url, 
            (50, height // 2 + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, 
            (200, 255, 200), 
            1
        )
        
        # Записваме placeholder в различни локации
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.quality]
        locations = [latest_path, static_path]
        
        for path in locations:
            try:
                cv2.imwrite(path, placeholder, encode_params)
                logger.info(f"Записан placeholder в {path}")
            except Exception as e:
                logger.warning(f"Не може да се запише placeholder в {path}: {str(e)}")
    
    # Опитваме се да извлечем първия кадър
    logger.info("Опит за извличане на първи кадър...")
    initial_result = capture_frame()
    logger.info(f"Резултат от първото извличане: {'успешно' if initial_result else 'неуспешно'}")
    
    # Стартиране на capture thread
    start_capture_thread()
    
    return True