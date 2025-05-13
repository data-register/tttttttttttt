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
        "title": "RTSP Стрийминг",
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
    """Връща текущ кадър от RTSP потока като JPEG изображение"""
    config = get_stream_config()
    
    try:
        # Създаваме VideoCapture обект
        cap = cv2.VideoCapture(config.rtsp_url, cv2.CAP_FFMPEG)
        
        # Задаваме малък буфер за по-бърза работа
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Проверка дали потокът е отворен
        if not cap.isOpened():
            logger.error("Не може да се отвори RTSP потока")
            return create_error_image()
        
        # Опит за прочитане на кадър с таймаут
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
            return create_error_image()
        
        # Преобразуваме кадъра в JPEG
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")
        
    except Exception as e:
        logger.error(f"Грешка при получаване на snapshot: {str(e)}")
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