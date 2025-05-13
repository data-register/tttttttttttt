"""
Конфигурация на Stream модул
"""

import os
from pydantic import BaseModel

class StreamConfig(BaseModel):
    """Конфигурационен модел за стрийминг"""
    rtsp_url: str
    status: str = "initializing"
    auth_username: str = ""
    auth_password: str = ""
    port: int = 8554
    
# Използваме RTSP URL от environment променливи или настройваме по подразбиране
# Ако не е зададен, се използва адреса от конфигурацията
rtsp_user = os.getenv("RTSP_USER", "admin")
rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
rtsp_host = os.getenv("RTSP_HOST", "109.160.23.42")
rtsp_port = os.getenv("RTSP_PORT", "554")
rtsp_url = os.getenv("RTSP_URL", f"rtsp://{rtsp_host}:{rtsp_port}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif")

# Създаваме URL с аутентикация
rtsp_url_with_auth = f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"

# Алтернативен URL за обществен поток
alternative_stream_url = "https://restream.obzorweather.com/cd84ff9e-9424-415b-8356-f47d0f214f8b.html"

# Глобална конфигурация
_config = StreamConfig(
    rtsp_url=rtsp_url_with_auth,
    auth_username=rtsp_user,
    auth_password=rtsp_pass,
    status="ok"
)

def get_stream_config() -> StreamConfig:
    """Връща текущата конфигурация на модула"""
    return _config

def update_stream_config(**kwargs) -> StreamConfig:
    """Обновява конфигурацията с нови стойности"""
    global _config
    
    # Обновяваме само валидните полета
    for key, value in kwargs.items():
        if hasattr(_config, key):
            setattr(_config, key, value)
    
    return _config