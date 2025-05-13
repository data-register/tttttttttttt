"""
API маршрути за RTSP стриминг
"""

import os
import cv2
import time
import numpy as np
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from .config import get_stream_config
from .ffmpeg_utils import get_frame_from_public_stream, add_timestamp_to_frame, check_ffmpeg_installed
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("stream_api")

# Създаваме router
router = APIRouter()

# Настройване на шаблони
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/view", response_class=HTMLResponse)
async def stream_view(request: Request):
    """Страница за визуализиране на RTSP поток"""
    config = get_stream_config()
    
    # Безопасен URL за показване, без паролата
    safe_url = config.rtsp_url
    if config.auth_password:
        safe_url = safe_url.replace(config.auth_password, "********")
    
    # Връщаме стрийминг страницата
    return templates.TemplateResponse("stream_view.html", {
        "request": request,
        "title": "Видео от камерата",
        "rtsp_url": safe_url,
        "auth_username": config.auth_username,
        "auth_password": "********"  # Никога не показваме истинската парола в HTML
    })

@router.get("/info")
async def stream_info():
    """Връща информация за стрийминга"""
    config = get_stream_config()
    
    # Безопасен URL без паролата за публично показване
    safe_url = config.rtsp_url
    if config.auth_password:
        safe_url = safe_url.replace(config.auth_password, "********")
    
    return JSONResponse({
        "status": config.status,
        "rtsp_url": safe_url,
        "streaming_page": "/stream/view"
    })

@router.get("/snapshot")
async def get_snapshot():
    """Връща текущ кадър от видео потока като JPEG изображение"""
    logger.info("Заявка за snapshot изображение")
    
    # Първо проверяваме дали FFmpeg е достъпен
    ffmpeg_available = check_ffmpeg_installed()
    
    if ffmpeg_available:
        try:
            # Опитваме да вземем кадър от публичния поток
            logger.info("Извличане на кадър от публичния поток")
            frame = get_frame_from_public_stream()
            
            if frame is not None:
                # Добавяме текущата дата и час към кадъра
                frame_with_timestamp = add_timestamp_to_frame(
                    frame,
                    position="bottom-right",
                    text="PTZ Camera"
                )
                
                # Преобразуваме в JPEG
                _, jpeg = cv2.imencode(".jpg", frame_with_timestamp, [cv2.IMWRITE_JPEG_QUALITY, 90])
                
                logger.info("Успешно извличане на кадър от потока")
                return Response(content=jpeg.tobytes(), media_type="image/jpeg")
            else:
                logger.warning("Не може да се извлече кадър от потока")
        except Exception as e:
            logger.error(f"Грешка при извличане на кадър от потока: {str(e)}")
    else:
        logger.warning("FFmpeg не е наличен, използваме резервен метод")
    
    # Запасен вариант - генерираме тестово изображение
    try:
        # Създаваме информативно изображение
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        height, width = 480, 640
        
        image = np.zeros((height, width, 3), dtype=np.uint8)
        image[:] = (50, 50, 50)  # Тъмносив фон
        
        # Добавяме текст за датата и часа
        cv2.putText(
            image,
            f"Текущо време: {timestamp}",
            (50, height // 2 - 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )
        
        # Добавяме информация за камерата
        cv2.putText(
            image,
            "Камера: 109.160.23.42",
            (50, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 200, 255),
            2
        )
        
        # Добавяме съобщение за FFmpeg
        cv2.putText(
            image,
            f"FFmpeg статус: {'Наличен' if ffmpeg_available else 'Недостъпен'}",
            (50, height // 2 + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 255, 200) if ffmpeg_available else (200, 100, 100),
            2
        )
        
        # Преобразуваме в JPEG
        _, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        logger.info("Успешно генериране на резервно изображение")
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")
        
    except Exception as e:
        logger.error(f"Грешка при генериране на резервно изображение: {str(e)}")
        return create_error_image()

def create_error_image(width=640, height=480):
    """Създава изображение с грешка при невъзможност за прихващане на кадър"""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Добавяме текст към изображението
    cv2.putText(
        image,
        "Не може да се свърже с камерата",
        (50, height // 2 - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )
    
    # Добавяме текуща дата и час
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(
        image,
        timestamp,
        (50, height // 2 + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (200, 200, 255),
        1
    )
    
    # Преобразуваме в JPEG
    _, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")