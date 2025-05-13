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
# Вземаме данните за връзка от средовите променливи или използваме defaults
# Забележка: В URL с ONVIF часто имаме отделни credentials от обикновения RTSP достъп
rtsp_host = os.getenv("RTSP_HOST", "109.160.23.42")
rtsp_port = os.getenv("RTSP_PORT", "554")
rtsp_path = os.getenv("RTSP_PATH", "cam/realmonitor")
rtsp_user = os.getenv("RTSP_USER", "admin")
rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")

# Построяваме няколко варианта на URL-и, които да пробваме
rtsp_urls = [
    f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/{rtsp_path}?channel=1&subtype=0", # Без Onvif суфикс
    f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/{rtsp_path}?channel=1&subtype=0&unicast=true&proto=Onvif", # С пълен Onvif суфикс
    f"rtsp://{rtsp_host}:{rtsp_port}/{rtsp_path}?channel=1&subtype=0", # Без credentials
    f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/ch01/0", # Алтернативен формат
    f"rtsp://{rtsp_host}:{rtsp_port}/ch01/0", # Алтернативен формат без credentials
    os.getenv("RTSP_URL", ""), # От средова променлива ако е налична
    os.getenv("ONVIF_URL", "")  # Onvif URL ако е различен
]

# Филтрираме празните URL-и
rtsp_urls = [url for url in rtsp_urls if url]

# Използваме първия URL от списъка като основен
_config = CaptureConfig(
    rtsp_url=rtsp_urls[0] if rtsp_urls else f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/{rtsp_path}?channel=1&subtype=0",
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