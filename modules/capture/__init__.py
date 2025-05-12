"""
Capture модул за PTZ Camera Control System
"""

# Този файл е ключов - той трябва да импортира и експортира router правилно

# Първо създаваме APIRouter
from fastapi import APIRouter

# След това го подаваме на api модула
from . import api

# Най-накрая експортираме router от api модула
router = api.router

# Експортираме router за регистрация в главното приложение
__all__ = ["router"]