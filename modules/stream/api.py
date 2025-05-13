"""
API маршрути за RTSP стриминг
"""

import os
import cv2
import time
import numpy as np
from datetime import datetime
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from .config import get_stream_config
from .ffmpeg_utils import get_frame_from_public_stream, add_timestamp_to_frame, check_ffmpeg_installed
from .cache import frame_cache
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
async def get_snapshot(force_refresh: bool = Query(False, description="Задължително обновяване на кадъра"),
                     rtsp_url: str = Query(None, description="Алтернативен RTSP URL (опционален)")):
    """Връща текущ кадър от видео потока като JPEG изображение с поддръжка на кеш - локална версия"""
    logger.info(f"Заявка за snapshot изображение (force_refresh={force_refresh}, rtsp_url={rtsp_url})")
    
    # Проверяваме дали FFmpeg е наличен в системата
    ffmpeg_available = check_ffmpeg_installed()
    
    if not ffmpeg_available:
        logger.warning("FFmpeg не е инсталиран локално. Инсталирайте с: apt-get install ffmpeg")
    
    # Определяме URL на потока (използваме подадения или стандартния)
    stream_url = rtsp_url if rtsp_url else "rtsp://admin:admin@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0"
    
    try:
        # Проверяваме за наличен latest.jpg файл, който се използва за локален достъп
        frames_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frames")
        latest_path = os.path.join(frames_dir, "latest.jpg")
        
        # Ако force_refresh е True или файлът не съществува, извличаме нов кадър
        if force_refresh or not os.path.exists(latest_path):
            logger.info(f"Извличане на нов кадър от {stream_url}")
            
            # Използваме локалната версия на функцията
            frame = get_frame_from_public_stream(stream_url=stream_url, force_refresh=True, max_cache_age=5)
            
            if frame is not None:
                # Преобразуваме в JPEG
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                logger.info("Успешно извличане на кадър от RTSP потока")
                return Response(content=jpeg.tobytes(), media_type="image/jpeg")
            else:
                logger.warning("Не може да се извлече нов кадър от RTSP потока")
        else:
            # Проверяваме дали latest.jpg съществува и е валиден
            if os.path.exists(latest_path) and os.path.getsize(latest_path) > 0:
                # Прочитаме готовия файл (по-бързо от да го генерираме отново)
                with open(latest_path, 'rb') as f:
                    content = f.read()
                    
                logger.info(f"Използване на съществуващ кадър от {latest_path}")
                return Response(content=content, media_type="image/jpeg")
    
    except Exception as e:
        logger.error(f"Грешка при обработка на кадър: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
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

@router.get("/cache")
async def get_cache_status():
    """
    Връща информация за състоянието на кеша за кадри
    """
    # Вземаме информация от кеш механизма
    cache_status = frame_cache.get_cache_status()
    
    # Добавяме информация за FFmpeg
    cache_status["ffmpeg_available"] = check_ffmpeg_installed()
    
    return JSONResponse({
        "status": "ok",
        "cache": cache_status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@router.post("/cache/clear")
async def clear_cache(source_id: str = None):
    """
    Изчиства кеша за кадри
    
    Args:
        source_id: Идентификатор на източника (опционален, ако не е зададен, изчиства целия кеш)
    """
    frame_cache.clear_cache(source_id)
    
    return JSONResponse({
        "status": "ok",
        "message": f"Кешът {'за ' + source_id if source_id else 'изцяло'} е изчистен успешно",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })