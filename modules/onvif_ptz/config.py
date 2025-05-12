"""
Конфигурация на ONVIF PTZ модул
"""

import os
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict

class PTZPosition(BaseModel):
    """Модел за PTZ позиция"""
    preset_token: str
    preset_name: str
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0

class PTZConfig(BaseModel):
    """Конфигурационен модел за ONVIF PTZ"""
    onvif_url: str
    username: str
    password: str
    home_preset: int = 0
    presets: List[int] = [0, 1, 2, 3, 4]
    current_preset: int = 0
    dwell_time: int = 30  # време за престой на всяка позиция в секунди
    home_dwell_time: int = 600  # време за престой в начална позиция (10 мин)
    capture_delay: int = 10  # време за изчакване преди снимка (в секунди)
    status: str = "initializing"
    last_move_time: Optional[datetime] = None
    position: Optional[PTZPosition] = None
    positions_cache: Dict[int, PTZPosition] = {}
    running: bool = True
    is_scheduled_mode: bool = True  # дали да се изпълнява автоматичния цикъл
    ptz_enabled: bool = True  # дали PTZ камерата е включена

# Глобална конфигурация на модула
# В Hugging Face Space трябва да използваме публични тестови URL-и
_config = PTZConfig(
    # Демо камера за тест в HF Space
    onvif_url=os.getenv("ONVIF_URL", "rtsp://demo:demo@ipvmdemo.dyndns.org:5541/onvif-media/media.amp"),
    username=os.getenv("ONVIF_USERNAME", "demo"),
    password=os.getenv("ONVIF_PASSWORD", "demo"),
    current_preset=int(os.getenv("CURRENT_PRESET", "0")),
    dwell_time=int(os.getenv("DWELL_TIME", "30")),
    home_dwell_time=int(os.getenv("HOME_DWELL_TIME", "600")),
    capture_delay=int(os.getenv("CAPTURE_DELAY", "10"))
)

def get_ptz_config() -> PTZConfig:
    """Връща текущата конфигурация на модула"""
    return _config

def update_ptz_config(**kwargs) -> PTZConfig:
    """Обновява конфигурацията с нови стойности"""
    global _config
    
    # Обновяваме само валидните полета
    for key, value in kwargs.items():
        if hasattr(_config, key):
            setattr(_config, key, value)
    
    return _config

def cache_preset_position(preset_number: int, position: PTZPosition):
    """Запазва позиция в кеша"""
    global _config
    _config.positions_cache[preset_number] = position

def get_cached_position(preset_number: int) -> Optional[PTZPosition]:
    """Връща кеширана позиция, ако съществува"""
    return _config.positions_cache.get(preset_number)