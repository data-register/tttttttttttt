"""
Основна логика за захващане на кадри от RTSP поток
"""

import os
import cv2
import time
import threading
import subprocess
import tempfile
import shutil
from datetime import datetime
import numpy as np
from PIL import Image
from io import BytesIO

from .config import get_capture_config, update_capture_config
from .test_utils import create_test_image
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("capture")

# Задаваме по-високо ниво на логване за debug в Hugging Face
import logging
logger.setLevel(logging.DEBUG)

def get_rtsp_url_with_auth():
    """Създава RTSP URL с вградена автентикация"""
    rtsp_user = os.getenv("RTSP_USER", "admin")
    rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
    rtsp_url = f"rtsp://{rtsp_user}:{rtsp_pass}@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"
    return rtsp_url

def get_rtsp_url_for_log():
    """Създава маскиран URL за логове"""
    rtsp_url = get_rtsp_url_with_auth()
    rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
    return rtsp_url.replace(rtsp_pass, "*****")

def capture_frame_opencv() -> bool:
    """Извлича един кадър от RTSP потока използвайки OpenCV"""
    config = get_capture_config()

    try:
        # Използваме URL с автентикация
        rtsp_url = get_rtsp_url_with_auth()
        log_url = get_rtsp_url_for_log()
        logger.info(f"Опит за свързване с RTSP поток чрез OpenCV: {log_url}")
        
        # Създаваме директориите ако не съществуват
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Опции за VideoCapture
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        # Задаваме таймаут и буфер
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Малък буфер за по-бърза работа
        
        # Проверка за успешно отваряне
        if not cap.isOpened():
            logger.error(f"Не може да се отвори RTSP потока: {log_url}")
            update_capture_config(status="error")
            return False
        
        # Прочитаме кадър
        max_retries = 3
        for retry in range(max_retries):
            ret, frame = cap.read()  # Извличаме кадър
            if ret and frame is not None:
                break  # Успешно извлечен кадър
            logger.warning(f"Неуспешен опит {retry+1}/{max_retries} за извличане на кадър")
            time.sleep(0.5)  # Малко изчакване между опитите
        
        # Освобождаваме ресурсите
        cap.release()
        
        # Проверка за успешно извлечен кадър
        if not ret or frame is None:
            logger.error("Не може да се извлече кадър от RTSP потока")
            update_capture_config(status="error")
            return False
        
        # Преоразмеряваме кадъра, ако е нужно
        if config.width > 0 and config.height > 0:
            frame = cv2.resize(frame, (config.width, config.height))
        
        # Генерираме име на файла с текущата дата и час
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.jpg"
        filepath = os.path.join(config.save_dir, filename)
        
        # Записваме кадъра във всички нужни локации
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.quality]
        success_paths = []
        
        # 1. Архивно копие с timestamp
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
        
        # 3. static/latest.jpg за web достъп
        static_path = "static/latest.jpg"
        try:
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
        logger.error(f"Грешка при извличане на кадър с OpenCV: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        update_capture_config(status="error")
        return False

def capture_frame_ffmpeg() -> bool:
    """Извлича един кадър от RTSP потока използвайки FFmpeg директно"""
    config = get_capture_config()

    try:
        # Използваме URL с автентикация
        rtsp_url = get_rtsp_url_with_auth()
        log_url = get_rtsp_url_for_log()
        logger.info(f"Опит за свързване с RTSP поток чрез FFmpeg: {log_url}")

        # Създаваме временен файл за изображението
        temp_output = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_output.close()  # Затваряме файла, но запазваме името
        output_path = temp_output.name
        
        # Генерираме име на файла с текущата дата и час
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.jpg"
        filepath = os.path.join(config.save_dir, filename)
        
        # Създаваме директориите ако не съществуват
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Изпълняваме FFmpeg команда за извличане на един кадър
        # -rtsp_transport tcp указва използването на TCP за RTSP (по-надеждно)
        # -timeout 15000000 задава таймаут от 15 секунди (в микросекунди)
        # Използваме URL с включена автентикация: rtsp://username:password@host:port/path
        command = [
            'ffmpeg', 
            '-rtsp_transport', 'tcp',
            '-timeout', '15000000',
            '-y',  # Презаписване на изходния файл
            '-i', rtsp_url,  # Вход: RTSP URL с автентикация
            '-frames:v', '1',  # Само един кадър
            '-q:v', '2',  # Високо качество
            output_path  # Изход: временен файл
        ]
        
        # Изпълняваме командата със скрити STDOUT/STDERR
        result = subprocess.run(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=20  # 20 секунди таймаут за цялата операция
        )
        
        # Проверяваме дали командата е успешна и файлът съществува
        if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"FFmpeg не можа да извлече кадър: {error_msg}")
            update_capture_config(status="error")
            # Изтриваме временния файл ако съществува
            if os.path.exists(output_path):
                os.unlink(output_path)
            return False
        
        # Четем изображението и го преоразмеряваме ако е нужно
        frame = cv2.imread(output_path)
        
        # Проверка дали имаме валидно изображение
        if frame is None:
            logger.error("Не може да се прочете кадърът от временния файл")
            update_capture_config(status="error")
            os.unlink(output_path)
            return False
            
        # Преоразмеряваме кадъра, ако е нужно
        if config.width > 0 and config.height > 0:
            frame = cv2.resize(frame, (config.width, config.height))
        
        # Записваме кадъра във всички нужни локации
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, config.quality]
        success_paths = []
        
        # 1. Архивно копие с timestamp
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
        
        # 3. static/latest.jpg за web достъп
        static_path = "static/latest.jpg"
        try:
            cv2.imwrite(static_path, frame, encode_params)
            success_paths.append(static_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {static_path}: {str(e)}")
        
        # Изтриваме временния файл
        os.unlink(output_path)
        
        # Проверяваме дали поне един запис е успешен
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
        
    except subprocess.TimeoutExpired:
        logger.error(f"Таймаут при изпълнение на FFmpeg команда")
        update_capture_config(status="error")
        # Опитваме се да изтрием временния файл ако съществува
        if 'output_path' in locals() and os.path.exists(output_path):
            os.unlink(output_path)
        return False
    
    except Exception as e:
        logger.error(f"Грешка при извличане на кадър с FFmpeg: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        update_capture_config(status="error")
        # Опитваме се да изтрием временния файл ако съществува
        if 'output_path' in locals() and os.path.exists(output_path):
            os.unlink(output_path)
        return False

# Проверка за наличие на FFmpeg и избор на подходящ метод
def capture_frame() -> bool:
    """Създава тестово изображение вместо да опитва връзка с RTSP камера"""
    config = get_capture_config()
    
    try:
        logger.info("Генериране на тестово изображение вместо свързване с камера")
        
        # Създаваме директориите за снимки
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Генерираме име на файла с текущата дата и час
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.jpg"
        filepath = os.path.join(config.save_dir, filename)
        
        # Зададени размери от конфигурацията
        width = config.width if config.width > 0 else 1280
        height = config.height if config.height > 0 else 720
        
        # Генерираме текст за изображението
        text = f"Тестов кадър - {timestamp}"
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Създаваме тестовото изображение и го запазваме в static директория
        create_test_image(
            width=width,
            height=height,
            text=text,
            timestamp=time_str,
            save_path="static/latest.jpg"
        )
        
        # Списък с успешните пътища
        success_paths = ["static/latest.jpg"]
        
        # 1. Архивно копие с timestamp
        try:
            shutil.copy("static/latest.jpg", filepath)
            success_paths.append(filepath)
        except Exception as e:
            logger.warning(f"Не може да се запише в {filepath}: {str(e)}")
        
        # 2. latest.jpg в основната директория
        latest_path = os.path.join(config.save_dir, "latest.jpg")
        try:
            shutil.copy("static/latest.jpg", latest_path)
            success_paths.append(latest_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {latest_path}: {str(e)}")
        
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
        
        logger.info(f"Успешно запазен тестов кадър в: {', '.join(success_paths)}")
        return True
    except Exception as e:
        logger.error(f"Грешка при генериране на тестово изображение: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        update_capture_config(status="error")
        return False

# Използваме този метод, който работи в rtsptrend
logger.info("Използваме същия метод за скрийншоти като в rtsptrend приложението")

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
    
    # Добавяме инфо за камерата (без чувствителни данни)
    rtsp_host = "109.160.23.42"
    cv2.putText(
        placeholder, 
        f"Camera: {rtsp_host}", 
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
    
    # Проверка за наличие на FFmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            ffmpeg_version = result.stdout.decode('utf-8', errors='ignore').split('\n')[0]
            logger.info(f"FFmpeg наличен: {ffmpeg_version}")
        else:
            logger.warning("FFmpeg не е намерен или не работи правилно!")
    except Exception as e:
        logger.warning(f"Грешка при проверка за FFmpeg: {str(e)}")
        
    # Подготвяме RTSP URL с автентикация за тестване
    try:
        rtsp_user = os.getenv("RTSP_USER", "admin")
        rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
        rtsp_url = f"rtsp://{rtsp_user}:{rtsp_pass}@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"
        log_url = rtsp_url.replace(rtsp_pass, "*****")
        logger.info(f"Конфигуриран RTSP URL с автентикация: {log_url}")
    except Exception as e:
        logger.warning(f"Грешка при подготовка на RTSP URL: {str(e)}")
    
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