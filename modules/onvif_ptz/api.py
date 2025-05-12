"""
API маршрути за ONVIF PTZ модул
"""

import os
import time
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List

from .config import get_ptz_config, update_ptz_config
from .camera import goto_preset, get_presets, get_current_position, toggle_scheduled_mode, start_ptz_thread, stop_ptz_thread
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("ptz_api")

# Регистриране на API router
router = APIRouter()

# Настройване на шаблони
templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/", response_class=HTMLResponse)
async def ptz_index(request: Request):
    """Страница за PTZ контрол"""
    config = get_ptz_config()
    presets = get_presets()
    
    return templates.TemplateResponse("ptz_control.html", {
        "request": request,
        "config": config,
        "presets": presets,
        "timestamp": int(time.time()),
        "last_move": config.last_move_time.strftime("%H:%M:%S") if config.last_move_time else "Няма",
        "status": config.status,
        "status_text": "OK" if config.status == "ok" else "Грешка" if config.status == "error" else "Инициализация",
        "automatic_mode": config.is_scheduled_mode
    })

@router.get("/status")
async def ptz_status():
    """Връща текущия статус на PTZ камерата"""
    config = get_ptz_config()
    position = get_current_position()
    
    return JSONResponse({
        "status": config.status,
        "current_preset": config.current_preset,
        "last_move_time": config.last_move_time.isoformat() if config.last_move_time else None,
        "position": {
            "pan": position.pan if position else 0,
            "tilt": position.tilt if position else 0,
            "zoom": position.zoom if position else 0
        } if position else None,
        "automatic_mode": config.is_scheduled_mode
    })

@router.get("/presets")
async def api_presets():
    """Връща списък с пресетите на камерата"""
    presets = get_presets()
    
    if not presets:
        return JSONResponse({
            "status": "error",
            "message": "Не са открити пресети или има проблем с камерата"
        }, status_code=404)
    
    return JSONResponse({
        "status": "ok",
        "presets": presets
    })

@router.get("/goto/{preset_number}")
async def api_goto_preset(preset_number: int):
    """Придвижва камерата към определен пресет"""
    try:
        success = goto_preset(preset_number)
        
        if success:
            return JSONResponse({
                "status": "ok",
                "message": f"Камерата е успешно придвижена към пресет {preset_number}",
                "preset": preset_number
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": f"Не може да се придвижи камерата към пресет {preset_number}"
            }, status_code=500)
    except Exception as e:
        logger.error(f"Грешка при придвижване към пресет {preset_number}: {str(e)}")
        return JSONResponse({
            "status": "error",
            "message": f"Грешка: {str(e)}"
        }, status_code=500)

@router.post("/config")
async def update_config(
    home_preset: int = Form(None),
    dwell_time: int = Form(None),
    home_dwell_time: int = Form(None),
    capture_delay: int = Form(None),
    onvif_url: str = Form(None),
    username: str = Form(None),
    password: str = Form(None)
):
    """Обновява конфигурацията на PTZ модула"""
    update_params = {}
    
    if home_preset is not None:
        update_params["home_preset"] = home_preset
    
    if dwell_time is not None:
        update_params["dwell_time"] = dwell_time
    
    if home_dwell_time is not None:
        update_params["home_dwell_time"] = home_dwell_time
    
    if capture_delay is not None:
        update_params["capture_delay"] = capture_delay
    
    if onvif_url is not None:
        update_params["onvif_url"] = onvif_url
    
    if username is not None:
        update_params["username"] = username
    
    if password is not None and password.strip():
        update_params["password"] = password
    
    # Обновяваме конфигурацията
    updated_config = update_ptz_config(**update_params)
    
    # Скриваме паролата в отговора
    config_response = {k: v for k, v in updated_config.dict().items() if k != 'password'}
    
    return JSONResponse({
        "status": "ok",
        "message": "Конфигурацията е обновена успешно",
        "config": config_response
    })

@router.get("/automatic/{state}")
async def set_automatic_mode(state: str):
    """Включва или изключва автоматичния режим"""
    if state.lower() in ["on", "true", "1"]:
        success = toggle_scheduled_mode(True)
        message = "Автоматичният режим е включен"
    elif state.lower() in ["off", "false", "0"]:
        success = toggle_scheduled_mode(False)
        message = "Автоматичният режим е изключен"
    else:
        return JSONResponse({
            "status": "error",
            "message": f"Невалидно състояние: {state}. Използвайте 'on' или 'off'."
        }, status_code=400)
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": message,
            "automatic_mode": get_ptz_config().is_scheduled_mode
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": "Не може да се промени режимът"
        }, status_code=500)

@router.get("/start")
async def start_ptz():
    """Стартира процеса за обхождане на пресетите"""
    success = start_ptz_thread()
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": "PTZ thread started successfully"
        })
    else:
        return JSONResponse({
            "status": "warning",
            "message": "PTZ thread is already running"
        })

@router.get("/stop")
async def stop_ptz():
    """Спира процеса за обхождане на пресетите"""
    success = stop_ptz_thread()
    
    if success:
        return JSONResponse({
            "status": "ok",
            "message": "PTZ thread stopping"
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": "Failed to stop PTZ thread"
        }, status_code=500)