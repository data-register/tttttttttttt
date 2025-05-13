"""
Конфигурация на Capture модул
"""

import os
from pydantic import BaseModel
from datetime import datetime

class CaptureConfig(BaseModel):
    """Конфигурационен модел за захващане на кадри"""
    rtsp_url: str
    save_dir: str
    interval: int
    width: int
    height: int
    quality: int
    last_frame_path: str = None
    last_frame_time: datetime = None
    status: str = "initializing"
    running: bool = True

# Камера URL данни
rtsp_user = os.getenv("RTSP_USER", "admin")
rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
rtsp_host = os.getenv("RTSP_HOST", "109.160.23.42")
rtsp_port = os.getenv("RTSP_PORT", "554")

# Точен URL адрес, предоставен от клиента
rtsp_url = "rtsp://109.160.23.42:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"

# Глобална конфигурация на модула
_config = CaptureConfig(
    rtsp_url=os.getenv("RTSP_URL", rtsp_url),
    save_dir=os.getenv("SAVE_DIR", "frames"),
    interval=int(os.getenv("INTERVAL", "30")),
    width=int(os.getenv("WIDTH", "1280")),
    height=int(os.getenv("HEIGHT", "720")),
    quality=int(os.getenv("QUALITY", "85"))
)

def get_capture_config() -> CaptureConfig:
    """Връща текущата конфигурация на модула"""
    return _config

def update_capture_config(**kwargs) -> CaptureConfig:
    """Обновява конфигурацията с нови стойности"""
    global _config
    
    # Обновяваме само валидните полета
    for key, value in kwargs.items():
        if hasattr(_config, key):
            setattr(_config, key, value)
    
    return _config

# Създаваме директорията за запазване на кадри
os.makedirs(_config.save_dir, exist_ok=True)