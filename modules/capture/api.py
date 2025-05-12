"""
API маршрути за захващане на изображения
"""

import os
import time
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import get_capture_config, update_capture_config
from .capture import capture_frame, get_placeholder_image, start_capture_thread, stop_capture_thread
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("capture_api")

# Регистриране на API router
router = APIRouter()

# Настройване на шаблони
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/latest.jpg")
async def latest_jpg():
    """Връща последния запазен JPEG файл"""
    try:
        # Първо проверяваме в static директорията
        static_path = "static/latest.jpg"
        if os.path.exists(static_path):
            return FileResponse(static_path, media_type="image/jpeg")

        # Ако не е в static, проверяваме в директорията за кадри
        config = get_capture_config()
        frames_path = os.path.join(config.save_dir, "latest.jpg")
        if os.path.exists(frames_path):
            return FileResponse(frames_path, media_type="image/jpeg")

        # Ако имаме последен известен кадър, опитваме с него
        if config.last_frame_path and os.path.exists(config.last_frame_path):
            # Копираме кадъра в static директорията за бъдещи запитвания
            try:
                import shutil
                shutil.copy(config.last_frame_path, static_path)
                logger.info(f"Копиран последен кадър от {config.last_frame_path} към {static_path}")
                return FileResponse(static_path, media_type="image/jpeg")
            except Exception as e:
                logger.warning(f"Грешка при копиране на кадър: {str(e)}")
                return FileResponse(config.last_frame_path, media_type="image/jpeg")

        # Връщаме placeholder изображение
        return Response(content=get_placeholder_image(), media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Грешка при достъпване на последния кадър: {str(e)}")
        # Опитваме да върнем placeholder вместо грешка
        try:
            return Response(content=get_placeholder_image(), media_type="image/jpeg")
        except:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/info")
async def capture_info():
    """Връща информация за последния запазен кадър"""
    config = get_capture_config()
    
    if config.last_frame_time is None:
        return JSONResponse({
            "status": "no_frame",
            "message": "Все още няма запазен кадър"
        }, status_code=404)
    
    return JSONResponse({
        "status": config.status,
        "last_frame_time": config.last_frame_time.isoformat() if config.last_frame_time else None,
        "last_frame_path": config.last_frame_path,
        "rtsp_url": config.rtsp_url,
        "width": config.width,
        "height": config.height,
        "quality": config.quality,
        "latest_url": "/capture/latest.jpg"
    })

@router.get("/capture_now")
async def api_capture():
    """Принудително извличане на нов кадър"""
    success = capture_frame()
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": "Кадърът е успешно извлечен",
            "last_frame_time": get_capture_config().last_frame_time.isoformat() 
                if get_capture_config().last_frame_time else None,
            "latest_url": "/capture/latest.jpg"
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": "Не може да се извлече кадър от камерата"
        }, status_code=500)

@router.post("/config")
async def update_config(
    rtsp_url: str = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    quality: int = Form(None),
    interval: int = Form(None)
):
    """Обновява конфигурацията на Capture модула"""
    update_params = {}
    
    if rtsp_url is not None:
        update_params["rtsp_url"] = rtsp_url
    
    if width is not None:
        update_params["width"] = width
    
    if height is not None:
        update_params["height"] = height
    
    if quality is not None:
        update_params["quality"] = quality
    
    if interval is not None:
        update_params["interval"] = interval
    
    # Обновяваме конфигурацията
    updated_config = update_capture_config(**update_params)
    
    return JSONResponse({
        "status": "ok",
        "message": "Конфигурацията е обновена успешно",
        "config": {
            "rtsp_url": updated_config.rtsp_url,
            "width": updated_config.width,
            "height": updated_config.height,
            "quality": updated_config.quality,
            "interval": updated_config.interval
        }
    })

@router.get("/start")
async def start_capture():
    """Стартира процеса за извличане на кадри"""
    success = start_capture_thread()
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": "Capture thread started successfully"
        })
    else:
        return JSONResponse({
            "status": "warning",
            "message": "Capture thread is already running"
        })

@router.get("/stop")
async def stop_capture():
    """Спира процеса за извличане на кадри"""
    success = stop_capture_thread()
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": "Capture thread stopping"
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": "Failed to stop capture thread"
        }, status_code=500)