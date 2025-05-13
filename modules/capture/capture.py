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


def try_capture_with_url(url: str, timeout: int = 15) -> tuple:
    """
    Опитва се да захване кадър от посочения RTSP URL
    
    Args:
        url: RTSP URL адрес
        timeout: Таймаут в секунди
        
    Returns:
        tuple: (успех, кадър) - дали е успешно и кадъра ако има такъв
    """
    try:
        logger.info(f"Опит за свързване с RTSP поток: {url}")
        
        # Създаваме VideoCapture обект директно с FFMPEG backend
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        
        # Проверяваме дали потокът е отворен
        if not cap.isOpened():
            logger.warning(f"Не може да се отвори RTSP потока: {url}")
            cap.release()
            return False, None
        
        logger.info(f"RTSP потокът е отворен успешно: {url}")
        
        # Конфигурация за по-добра работа
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # По-голям буфер
        
        # Четем кадъра с таймаут
        has_frame = False
        start_time = time.time()
        frame = None
        
        # Правим няколко опита да прочетем кадър
        retry_count = 0
        max_retries = 3
        
        while not has_frame and time.time() - start_time < timeout and retry_count < max_retries:
            ret, frame = cap.read()
            if ret and frame is not None:
                has_frame = True
                break
            
            # Малко изчакване между опитите
            time.sleep(0.5)
            retry_count += 1
        
        # Освобождаваме ресурсите
        cap.release()
        
        if has_frame and frame is not None:
            logger.info(f"Успешно получен кадър от {url}")
            return True, frame
        else:
            logger.warning(f"Не може да се прочете кадър от RTSP потока: {url}")
            return False, None
            
    except Exception as e:
        logger.warning(f"Грешка при опит за четене от {url}: {str(e)}")
        return False, None

def capture_frame() -> bool:
    """Извлича един кадър от RTSP потока и го записва като JPEG файл"""
    config = get_capture_config()
    
    try:
        # Първо опитваме с основния URL
        success, frame = try_capture_with_url(config.rtsp_url, timeout=15)
        
        # Ако не успее, опитваме с алтернативни URLs
        if not success:
            logger.info("Опитване на алтернативни RTSP URL адреси...")
            
            # Вземаме данните за връзка, за да построим алтернативни URLs
            from .config import rtsp_urls
            
            # Опитваме всеки URL
            for url in rtsp_urls:
                if url != config.rtsp_url:  # Пропускаме основния URL, който вече пробвахме
                    success, frame = try_capture_with_url(url, timeout=10)
                    if success:
                        # Ако успеем, обновяваме конфигурацията с работещия URL
                        logger.info(f"Намерен работещ RTSP URL: {url}")
                        update_capture_config(rtsp_url=url)
                        break
        
        # Ако не сме успели да получим кадър от нито един URL
        if not success or frame is None:
            logger.error("Не може да се прочете кадър от нито един RTSP поток")
            update_capture_config(status="error")
            return False
        
        # Преоразмеряваме кадъра, ако е нужно
        if config.width > 0 and config.height > 0:
            frame = cv2.resize(frame, (config.width, config.height))
        
        # Генерираме име на файла с текущата дата и час
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}.jpg"
        filepath = os.path.join(config.save_dir, filename)
        
        # Създаваме всички нужни директории
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Записваме кадъра като JPEG файл
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
        
        # Записваме файловете в различни локации за по-голяма надеждност
        success_paths = []
        error_paths = []
        
        # Най-важна локация: static директорията
        static_path = "static/latest.jpg"
        try:
            cv2.imwrite(static_path, frame, encode_params)
            success_paths.append(static_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {static_path}: {str(e)}")
            error_paths.append((static_path, str(e)))
            
        # Записваме архивно копие с timestamp
        try:
            cv2.imwrite(filepath, frame, encode_params)
            success_paths.append(filepath)
        except Exception as e:
            logger.warning(f"Не може да се запише в {filepath}: {str(e)}")
            error_paths.append((filepath, str(e)))
        
        # Записваме latest.jpg в frames директорията
        frames_latest_path = os.path.join(config.save_dir, "latest.jpg")
        try:
            cv2.imwrite(frames_latest_path, frame, encode_params)
            success_paths.append(frames_latest_path)
        except Exception as e:
            logger.warning(f"Не може да се запише в {frames_latest_path}: {str(e)}")
            error_paths.append((frames_latest_path, str(e)))
        
        # Опитваме да запишем и в /tmp директорията за допълнителна сигурност
        tmp_path = "/tmp/latest.jpg"
        try:
            cv2.imwrite(tmp_path, frame, encode_params)
            success_paths.append(tmp_path)
        except Exception as e:
            logger.debug(f"Не може да се запише в {tmp_path}: {str(e)}")
            error_paths.append((tmp_path, str(e)))
        
        # Проверяваме дали имаме поне един успешен запис
        if not success_paths:
            logger.error("Не може да се запише кадърът на нито една локация!")
            for path, error in error_paths:
                logger.error(f"Грешка за {path}: {error}")
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
        import traceback
        logger.error(f"Стек на грешката: {traceback.format_exc()}")

        # Създаваме placeholder изображение
        try:
            height = config.height if config.height > 0 else 480
            width = config.width if config.width > 0 else 640

            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.putText(
                frame,
                f"Error: {str(e)[:30]}",
                (50, height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            # Опитваме да запишем placeholder изображение във всички възможни локации
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
            locations = ["static/latest.jpg", os.path.join(config.save_dir, "latest.jpg"), "/tmp/latest.jpg"]
            for path in locations:
                try:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    cv2.imwrite(path, frame, encode_params)
                    logger.info(f"Записан placeholder в {path}")
                except Exception as inner_err:
                    logger.debug(f"Не може да се запише placeholder в {path}: {str(inner_err)}")
        except Exception as inner_err:
            logger.error(f"Не може да се създаде дори празно изображение: {str(inner_err)}")

        update_capture_config(status="error")
        return False


def verify_opencv_installation():
    """
    Проверява инсталацията на OpenCV и наличието на нужните бекенди
    """
    try:
        logger.info(f"OpenCV версия: {cv2.__version__}")

        # В новите версии на OpenCV, videoio_registry може да не съществува в cv2
        # затова го обвиваме в try-except блок
        try:
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
        except AttributeError as ae:
            logger.warning(f"videoio_registry не е наличен в тази версия на OpenCV: {str(ae)}")
        except Exception as e:
            logger.warning(f"Грешка при проверка на бекендите: {str(e)}")

        # Проверяваме дали можем да създадем VideoCapture обект
        logger.info("Проверка на VideoCapture функционалност...")
        try:
            # Опитваме да създадем устройство 0, но не го отваряме
            # и веднага го освобождаваме
            temp_cap = cv2.VideoCapture()
            temp_cap.release()
            logger.info("VideoCapture е наличен и работи правилно")
        except Exception as e:
            logger.warning(f"Грешка при създаване на VideoCapture: {str(e)}")

        return True
    except Exception as e:
        logger.error(f"Грешка при проверка на OpenCV: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


def get_latest_frame_bytes() -> Optional[bytes]:
    """
    Връща последното заснето изображение като байтове

    Returns:
        bytes или None при грешка
    """
    try:
        # Проверяваме дали съществува файл
        if os.path.exists("static/latest.jpg"):
            # Конвертиране към bytes
            with open("static/latest.jpg", "rb") as image_file:
                return image_file.read()

        # Ако не съществува в static, проверяваме във frames директорията
        config = get_capture_config()
        if config.last_frame_path and os.path.exists(config.last_frame_path):
            with open(config.last_frame_path, "rb") as image_file:
                data = image_file.read()
                # Опитваме да го запишем в static директорията
                try:
                    with open("static/latest.jpg", "wb") as out_file:
                        out_file.write(data)
                except Exception as e:
                    logger.warning(f"Не може да се копира от {config.last_frame_path} в static/latest.jpg: {str(e)}")
                return data

        return None

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
    
    # Добавяме текущия час
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(
        placeholder, 
        timestamp, 
        (50, height // 2 + 40),
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.7, 
        (200, 200, 255), 
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
    # verify_opencv_installation()
    try:
        logger.info(f"OpenCV версия: {cv2.__version__}")
        
        # Проверка на наличните бекенди
        try:
            backends = []
            # В различни версии на OpenCV това е организирано различно
            if hasattr(cv2, 'videoio_registry'):
                for backend_id in cv2.videoio_registry.getBackends():
                    backend_name = cv2.videoio_registry.getBackendName(backend_id)
                    backends.append(f"{backend_name}")
                logger.info(f"Налични бекенди: {backends}")
            else:
                logger.info("OpenCV videoio_registry не е наличен в тази версия")
        except Exception as e:
            logger.warning(f"Грешка при проверка на бекендите: {str(e)}")
    except Exception as e:
        logger.error(f"Грешка при проверка на OpenCV: {str(e)}")

    # Получаваме конфигурацията
    config = get_capture_config()
    logger.info(f"RTSP URL: {config.rtsp_url}")

    # Определяме дали сме в Hugging Face Space
    is_hf_space = os.environ.get('SPACE_ID') is not None
    logger.info(f"Hugging Face Space: {is_hf_space}")

    # Тестваме директориите за запис
    test_directories = [config.save_dir, "static", "/tmp"]
    for directory in test_directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Създадена директория: {directory}")
            # Опитваме се да зададем права, но не е критично
            try:
                os.chmod(directory, 0o777)
                logger.debug(f"Зададени права 777 за {directory}")
            except Exception as e:
                logger.debug(f"Не могат да се променят правата на {directory}: {e}")
                
            # Тестваме записа
            test_file = os.path.join(directory, "test_write.txt")
            with open(test_file, "w") as f:
                f.write(f"Test write at {datetime.now()}")
            os.remove(test_file)
            logger.info(f"Успешен запис в директория {directory}")
        except Exception as e:
            logger.warning(f"Проблем с директория {directory}: {str(e)}")
    
    # Създаваме placeholder за latest.jpg
    latest_path = os.path.join(config.save_dir, "latest.jpg")
    if not os.path.exists(latest_path) or not os.path.exists("static/latest.jpg"):
        height = config.height if config.height > 0 else 480
        width = config.width if config.width > 0 else 640
        placeholder = np.zeros((height, width, 3), dtype=np.uint8)

        # Добавяме текст за инициализация
        cv2.putText(
            placeholder, 
            "Waiting for first frame...", 
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
        camera_info = config.rtsp_url.split('@')[-1].split('/')[0]
        cv2.putText(
            placeholder, 
            f"Camera: {camera_info}", 
            (50, height // 2 + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (200, 255, 200), 
            2
        )

        # Записваме placeholder изображение в различни локации
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
        locations = ["static/latest.jpg", latest_path, "/tmp/latest.jpg"]
        
        for path in locations:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                cv2.imwrite(path, placeholder, encode_params)
                logger.info(f"Успешно записан placeholder в {path}")
            except Exception as e:
                logger.warning(f"Не може да се запише placeholder в {path}: {str(e)}")
    
    # Вземаме списъка с алтернативни URLs
    try:
        from .config import rtsp_urls
        logger.info(f"Налични RTSP URLs за опитване: {len(rtsp_urls)}")
    except Exception as e:
        logger.warning(f"Грешка при достъп до алтернативни URLs: {str(e)}")
    
    # Опитваме се да извлечем първия кадър
    logger.info("Опит за извличане на първи кадър...")
    initial_result = capture_frame()
    logger.info(f"Резултат от първото извличане: {'успешно' if initial_result else 'неуспешно'}")
    
    # Стартиране на capture thread
    start_capture_thread()
    
    return True