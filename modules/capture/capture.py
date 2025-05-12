"""
Модул за заснемане на изображения от RTSP поток
"""

import os
import cv2
import time
import threading
import numpy as np
from datetime import datetime
from io import BytesIO
from typing import Optional

from .config import get_capture_config, update_capture_config
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("capture")


def capture_frame() -> bool:
    """
    Заснема кадър от RTSP потока и го записва на диск
    
    Returns:
        bool: True ако операцията е успешна, False в противен случай
    """
    try:
        config = get_capture_config()
        
        # ВАЖНО: Маскираме паролата в логовете, но запазваме оригиналния URL
        log_url = config.rtsp_url
        if "@" in log_url:
            # Заместваме паролата със звездички
            parts = log_url.split("@")
            auth_part = parts[0].split("//")
            if len(auth_part) > 1 and ":" in auth_part[1]:
                user_pass = auth_part[1].split(":")
                masked_url = f"{auth_part[0]}//{user_pass[0]}:****@{parts[1]}"
                logger.info(f"Опит за свързване с RTSP поток: {masked_url}")
            else:
                logger.info(f"Опит за свързване с RTSP поток: {log_url}")
        else:
            logger.info(f"Опит за свързване с RTSP поток: {log_url}")
        
        # Използваме точно същия подход като в rtsptrend проекта
        cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
        
        # Проверяваме дали потокът е отворен
        if not cap.isOpened():
            logger.error("Не може да се отвори RTSP потока")
            update_capture_config(status="error")
            return False
        
        logger.info("RTSP потокът е отворен успешно!")
        
        # Минимални настройки за по-добра работа
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Диагностика на потока
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        logger.info(f"Поточни параметри: {width}x{height} @ {fps}fps")
        
        # Четем кадъра с 5-секунден таймаут
        has_frame = False
        start_time = time.time()
        frame = None
        
        # Опитваме да прочетем кадър точно както в rtsptrend
        while not has_frame and time.time() - start_time < 5:
            ret, frame = cap.read()
            if ret and frame is not None:
                has_frame = True
                break
            time.sleep(0.1)
        
        # Освобождаваме ресурсите незабавно
        cap.release()
        
        # Проверяваме дали сме получили кадър
        if not has_frame or frame is None:
            logger.error("Не може да се прочете кадър от потока (таймаут)")
            update_capture_config(status="error")
            return False
        
        logger.info(f"Получен валиден кадър с размери: {frame.shape}")
        
        # Преоразмеряваме кадъра, ако е нужно
        if config.width > 0 and config.height > 0:
            frame = cv2.resize(frame, (config.width, config.height))
        
        # Създаваме директориите ако не съществуват
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Генерираме име на файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(config.save_dir, f"frame_{timestamp}.jpg")
        latest_path = "static/latest.jpg"
        
        # Запазваме изображението
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
        
        try:
            # Записваме основния файл
            cv2.imwrite(filepath, frame, encode_params)
            # Записваме latest.jpg за лесен достъп
            cv2.imwrite(latest_path, frame, encode_params)
            logger.info(f"Успешно запазен кадър в: {filepath}")
        except PermissionError as pe:
            logger.error(f"Грешка с права за достъп: {str(pe)}")
            # Опитваме да запишем във временна директория
            try:
                alt_path = os.path.join("/tmp", f"frame_{timestamp}.jpg")
                cv2.imwrite(alt_path, frame, encode_params)
                logger.info(
                    f"Запазен кадър в алтернативна локация: {alt_path}"
                )
            except Exception as e2:
                logger.error(
                    f"Не може да се запише във временна директория: {str(e2)}"
                )
            return False
        except Exception as e:
            logger.error(f"Грешка при запис на файлове: {str(e)}")
            return False
        
        logger.info(f"Успешно запазен кадър в: {filepath}")
        
        # Обновяваме конфигурацията
        update_capture_config(
            status="ok",
            last_frame_time=datetime.now(),
            last_frame_path=filepath
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Грешка при заснемане на кадър: {str(e)}")
        import traceback
        logger.error(f"Стек на грешката: {traceback.format_exc()}")
        update_capture_config(status="error")
        return False


def verify_opencv_installation():
    """
    Проверява инсталацията на OpenCV и наличието на нужните бекенди
    """
    try:
        logger.info(f"OpenCV версия: {cv2.__version__}")
        
        # Проверка за налични бекенди
        backends = []
        for backend_id in cv2.videoio_registry.getBackends():
            backend_name = cv2.videoio_registry.getBackendName(backend_id)
            is_built = cv2.videoio_registry.isBackendBuiltIn(backend_id)
            backends.append(f"{backend_name} (built-in: {is_built})")
        
        logger.info(f"Налични бекенди: {backends}")
        
        # Проверка дали FFMPEG бекенда е наличен
        if cv2.CAP_FFMPEG not in cv2.videoio_registry.getBackends():
            logger.warning(
                "FFMPEG бекендът не е наличен! Това може да причини проблеми "
                "при заснемането на RTSP поток."
            )
        
        return True
    except Exception as e:
        logger.error(f"Грешка при проверка на OpenCV: {str(e)}")
        return False


def get_latest_frame_bytes() -> Optional[bytes]:
    """
    Връща последното заснето изображение като байтове
    
    Returns:
        bytes или None при грешка
    """
    try:
        # Проверяваме дали съществува файл
        if not os.path.exists("static/latest.jpg"):
            return None
        
        # Конвертиране към bytes
        with open("static/latest.jpg", "rb") as image_file:
            return image_file.read()
            
    except Exception as e:
        logger.error(f"Грешка при четене на latest.jpg: {str(e)}")
        return None


def get_placeholder_image() -> bytes:
    """
    Създава placeholder изображение, когато няма наличен кадър
    """
    config = get_capture_config()
    
    # Създаване на празно изображение с текст
    height = config.height if config.height > 0 else 480
    width = config.width if config.width > 0 else 640
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
        (50, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX, 
        1, 
        (255, 255, 255), 
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
    """
    Фонов цикъл за периодично заснемане на кадри
    """
    while True:
        try:
            config = get_capture_config()
            
            if not config.running:
                logger.info("Capture loop спрян")
                break
            
            # Заснемаме кадър, ако интервалът е положителен
            if config.interval > 0:  # Проверка за валиден интервал
                result = capture_frame()
                status = "успешно" if result else "неуспешно"
                logger.info(f"Периодично заснемане: {status}")
            
            # Изчакваме до следващото заснемане
            time.sleep(config.interval)
            
        except Exception as e:
            logger.error(f"Грешка в capture_loop: {str(e)}")
            time.sleep(10)  # Изчакваме при грешка


# Глобална променлива за capture thread
capture_thread = None


def start_capture_thread():
    """
    Стартира фонов процес за периодично заснемане на кадри
    """
    global capture_thread
    
    if capture_thread is None or not capture_thread.is_alive():
        capture_thread = threading.Thread(target=capture_loop)
        capture_thread.daemon = True
        capture_thread.start()
        logger.info("Capture thread started")
        return True
    
    logger.info("Capture thread вече е активен")
    return False


def stop_capture_thread():
    """
    Спира фоновия процес за заснемане на кадри
    """
    update_capture_config(running=False)
    logger.info("Capture thread stop requested")
    return True


def initialize():
    """
    Инициализира модула за заснемане
    """
    # Проверка на OpenCV инсталацията
    verify_opencv_installation()
    
    # Създаваме директориите ако не съществуват
    config = get_capture_config()
    os.makedirs(config.save_dir, exist_ok=True)
    os.makedirs("static", exist_ok=True)
    
    # Създаваме placeholder за latest.jpg ако не съществува
    if not os.path.exists("static/latest.jpg"):
        height = config.height if config.height > 0 else 480
        width = config.width if config.width > 0 else 640
        placeholder = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            placeholder, 
            "Waiting for first frame...", 
            (50, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1, 
            (255, 255, 255), 
            2
        )
        try:
            cv2.imwrite("static/latest.jpg", placeholder)
        except Exception as e:
            logger.error(f"Грешка при запис на placeholder: {str(e)}")
    
    # Тестово първоначално извличане на кадър
    initial_result = capture_frame()
    status = "успешно" if initial_result else "неуспешно"
    logger.info(f"Резултат от първото извличане: {status}")
    
    # Стартираме фоновия процес
    start_capture_thread()
    
    return True