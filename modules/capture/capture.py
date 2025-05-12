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
        
        # Създаваме директориите, ако не съществуват
        os.makedirs(config.save_dir, exist_ok=True)
        os.makedirs("static", exist_ok=True)
        
        # Генерираме имена на файлове
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(config.save_dir, f"frame_{timestamp}.jpg")
        latest_path = "static/latest.jpg"
        
        # Максимално опростен метод за отваряне на RTSP потока
        try:
            # В прост режим използваме стандартния начин
            cap = cv2.VideoCapture(config.rtsp_url)
            
            # Проверучваме дали сме отворили потока
            if not cap.isOpened():
                # Един опит с FFMPEG бекенда
                cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    # Ако и това не работи, създаваме празно изображение
                    height = config.height if config.height > 0 else 480
                    width = config.width if config.width > 0 else 640
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    cv2.putText(
                        frame,
                        "No camera connection",
                        (50, height // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        1, 
                        (255, 255, 255), 
                        2
                    )
                    
                    # Записваме празното изображение
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
                    cv2.imwrite(latest_path, frame, encode_params)
                    update_capture_config(status="error")
                    return False
            
            # Прочитаме един кадър
            ret, frame = cap.read()
            
            # Освобождаваме камерата
            cap.release()
            
            # Проверка дали имаме успешен кадър
            if not ret or frame is None:
                # При грешка създаваме празно изображение
                height = config.height if config.height > 0 else 480
                width = config.width if config.width > 0 else 640
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                cv2.putText(
                    frame,
                    "No frame available",
                    (50, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    1, 
                    (255, 255, 255), 
                    2
                )
                
                # Записваме празното изображение
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
                cv2.imwrite(latest_path, frame, encode_params)
                update_capture_config(status="error")
                return False
                
            # Преоразмеряваме кадъра ако е нужно
            if config.width > 0 and config.height > 0:
                frame = cv2.resize(frame, (config.width, config.height))
                
            # Записваме кадъра
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
            
            # Първо в static директорията (най-важно)
            cv2.imwrite(latest_path, frame, encode_params)
            
            # После във фрейм директорията
            try:
                cv2.imwrite(filepath, frame, encode_params)
            except Exception as e:
                logger.warning(f"Не може да се запише в {filepath}, но latest.jpg е записан: {str(e)}")
                # Продължаваме, тъй като най-важното е latest.jpg
            
            # Обновяваме конфигурацията
            update_capture_config(
                status="ok",
                last_frame_time=datetime.now(),
                last_frame_path=filepath
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Грешка при заснемане на кадър: {str(e)}")
            
            # Създаваме празно изображение при грешка
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
                
                # Записваме празното изображение
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), config.quality]
                cv2.imwrite(latest_path, frame, encode_params)
            except Exception as inner_err:
                logger.error(f"Не може да се създаде дори празно изображение: {str(inner_err)}")
                
            update_capture_config(status="error")
            return False
            
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

    # Създаваме всички необходими директории с правилните права
    try:
        # Основна директория за запазване на кадри
        os.makedirs(config.save_dir, exist_ok=True)
        os.chmod(config.save_dir, 0o777)
        logger.info(f"Създадена директория {config.save_dir} с права 777")

        # Статична директория за web достъп
        os.makedirs("static", exist_ok=True)
        os.chmod("static", 0o777)
        logger.info("Създадена директория static с права 777")

        # Временна директория за случаи на проблеми с права
        os.makedirs("/tmp/frames", exist_ok=True)
        os.chmod("/tmp/frames", 0o777)
        logger.info("Създадена директория /tmp/frames с права 777")
    except Exception as e:
        logger.error(f"Грешка при създаване на директории: {str(e)}")

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
            logger.info("Създаден placeholder за latest.jpg")
        except Exception as e:
            logger.error(f"Грешка при запис на placeholder: {str(e)}")
            try:
                # Опитваме във временната директория и после го копираме
                temp_path = "/tmp/placeholder.jpg"
                cv2.imwrite(temp_path, placeholder)
                import shutil
                shutil.copy(temp_path, "static/latest.jpg")
                logger.info("Създаден placeholder във временна директория и копиран в static")
            except Exception as e2:
                logger.error(f"Не може да се създаде placeholder и във временна директория: {str(e2)}")

    # Отлагаме тестовото първоначално извличане на кадър с няколко секунди
    # за да дадем време на системата да се стабилизира
    import threading

    def delayed_first_capture():
        logger.info("Изчакване 5 секунди преди първото извличане на кадър...")
        time.sleep(5)
        try:
            initial_result = capture_frame()
            status = "успешно" if initial_result else "неуспешно"
            logger.info(f"Резултат от първото извличане: {status}")
        except Exception as e:
            logger.error(f"Грешка при първо извличане: {str(e)}")

    # Стартираме фоновия процес за първоначално извличане
    first_capture_thread = threading.Thread(target=delayed_first_capture)
    first_capture_thread.daemon = True
    first_capture_thread.start()

    # Стартираме фоновия процес за периодично заснемане
    start_capture_thread()

    return True