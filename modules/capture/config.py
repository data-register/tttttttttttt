"""
Конфигурация на Image Capture модул
"""

import os
from pydantic import BaseModel
from datetime import datetime

class CaptureConfig(BaseModel):
    """Конфигурационен модел за захващане на изображения"""
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

# Глобална конфигурация на модула
# В Hugging Face Space не можем да използваме реални RTSP потоци, затова използваме публичен тестов URL
# За локална работа можете да зададете RTSP_URL като environment променлива
_config = CaptureConfig(
    # Демо видео вместо реален RTSP поток
    rtsp_url=os.getenv("RTSP_URL", os.getenv("ONVIF_URL", "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4")),
    save_dir=os.getenv("SAVE_DIR", "frames"),
    interval=int(os.getenv("INTERVAL", "10")),
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