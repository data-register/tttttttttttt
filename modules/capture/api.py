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
        config = get_capture_config()
        
        # Списък с възможни локации на кадъра, подредени по приоритет
        possible_paths = [
            "static/latest.jpg",  # Първи приоритет - static директория
            os.path.join(config.save_dir, "latest.jpg"),  # Втори приоритет - frames директория
        ]
        
        # Добавяме последния запазен кадър, ако имаме такъв
        if config.last_frame_path and os.path.exists(config.last_frame_path):
            possible_paths.append(config.last_frame_path)
            
        # Проверяваме всяка локация за наличие на кадър
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    file_size = os.path.getsize(path)
                    if file_size > 0:  # Проверяваме дали файлът не е празен
                        logger.info(f"Намерен кадър в {path}, размер: {file_size} bytes")
                        
                        # Ако кадърът не е в static директорията, копираме го там
                        if path != "static/latest.jpg":
                            try:
                                import shutil
                                shutil.copy(path, "static/latest.jpg")
                                logger.debug(f"Копиран кадър от {path} в static/latest.jpg")
                            except Exception as copy_err:
                                logger.debug(f"Не може да се копира в static: {str(copy_err)}")
                        
                        return FileResponse(path, media_type="image/jpeg")
                except Exception as e:
                    logger.warning(f"Грешка при проверка на {path}: {str(e)}")
        
        # Ако не сме намерили кадър, опитваме да заснемем нов
        logger.info("Не е намерен съществуващ кадър, извличане на нов кадър")
        capture_success = capture_frame()
        
        if capture_success:
            # Проверяваме отново static директорията
            if os.path.exists("static/latest.jpg") and os.path.getsize("static/latest.jpg") > 0:
                logger.info("Успешно извлечен нов кадър")
                return FileResponse("static/latest.jpg", media_type="image/jpeg")
        
        # Последна опция - връщаме placeholder изображение
        logger.info("Връщане на placeholder изображение")
        return Response(content=get_placeholder_image(), media_type="image/jpeg")
        
    except Exception as e:
        logger.error(f"Грешка при достъпване на последния кадър: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        
        # Опитваме да върнем placeholder вместо грешка
        try:
            return Response(content=get_placeholder_image(), media_type="image/jpeg")
        except Exception as placeholder_err:
            logger.error(f"Не може да се създаде placeholder: {str(placeholder_err)}")
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
        "interval": config.interval,
        "width": config.width,
        "height": config.height,
        "quality": config.quality,
        "latest_url": "/capture/latest.jpg"
    })

@router.get("/capture_now")
async def api_capture():
    """Принудително извличане на нов кадър"""
    logger.info("Започване на принудително извличане на кадър")
    success = capture_frame()
    
    if success:
        config = get_capture_config()
        logger.info("Успешно извличане на кадър")
        
        # Проверка за наличие на файла
        static_path = "static/latest.jpg"
        if os.path.exists(static_path):
            file_size = os.path.getsize(static_path)
            logger.info(f"Файлът съществува, размер: {file_size} bytes")
        
        # Връщане на информация за кадъра
        return JSONResponse({
            "status": "ok",
            "message": "Кадърът е успешно извлечен",
            "last_frame_time": config.last_frame_time.isoformat() if config.last_frame_time else None,
            "latest_url": "/capture/latest.jpg",
            "file_exists": os.path.exists(static_path),
            "file_size": os.path.getsize(static_path) if os.path.exists(static_path) else 0
        })
    else:
        logger.warning("Неуспешно извличане на кадър")
        return JSONResponse({
            "status": "error",
            "message": "Не може да се извлече кадър от камерата"
        }, status_code=500)

@router.post("/config")
async def update_config(
    rtsp_url: str = Form(None),
    interval: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    quality: int = Form(None)
):
    """Обновява конфигурацията на Capture модула"""
    update_params = {}
    
    if rtsp_url is not None:
        update_params["rtsp_url"] = rtsp_url
    
    if interval is not None:
        update_params["interval"] = interval
    
    if width is not None:
        update_params["width"] = width
    
    if height is not None:
        update_params["height"] = height
    
    if quality is not None:
        update_params["quality"] = quality
    
    # Обновяваме конфигурацията
    updated_config = update_capture_config(**update_params)
    
    return JSONResponse({
        "status": "ok",
        "message": "Конфигурацията е обновена успешно",
        "config": {
            "rtsp_url": updated_config.rtsp_url,
            "interval": updated_config.interval,
            "width": updated_config.width,
            "height": updated_config.height,
            "quality": updated_config.quality
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