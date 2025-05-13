"""
Основно приложение на PTZ Camera Control System
Този файл инициализира FastAPI приложението и зарежда всички модули.
Оптимизирано за работа в Hugging Face Space.
"""

import os
import time
import uvicorn
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Импортиране на модули
from modules.onvif_ptz import router as ptz_router
from modules.onvif_ptz.config import get_ptz_config
from modules.capture import router as capture_router
from modules.capture.config import get_capture_config
from utils.logger import setup_logger

# Инициализиране на логване
logger = setup_logger("app")

# Създаваме FastAPI приложение
app = FastAPI(
    title="PTZ Camera Control System",
    description="Система за управление на ONVIF PTZ камера",
    version="1.0.0"
)

# Настройка на критични системни променливи за кеширане
os.environ['ZEEP_CACHE_DIR'] = os.environ.get('ZEEP_CACHE_DIR', '/tmp/.cache')
os.environ['XDG_CACHE_HOME'] = os.environ.get('XDG_CACHE_HOME', '/tmp/.cache')
logger.info(f"Настройка на ZEEP_CACHE_DIR: {os.environ['ZEEP_CACHE_DIR']}")
logger.info(f"Настройка на XDG_CACHE_HOME: {os.environ['XDG_CACHE_HOME']}")

# Създаваме всички необходими директории
logger.info("Инициализиране на директории...")
required_dirs = [
    "static", "templates", "frames", "logs", "/tmp/.cache"
]

# Допълнителни директории, които могат да бъдат нужни
additional_dirs = [
    ".cache", ".local", ".config", "/tmp"
]

# Единна функция за безопасно създаване на директория с подходящи права
def ensure_directory_exists(dir_path, mode=0o777):
    """Създава директория и задава подходящи права ако е възможно"""
    try:
        # Създава директорията ако не съществува
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Създадена директория: {dir_path}")
            
        # Опитва да зададе правата, но не е критично
        try:
            os.chmod(dir_path, mode)
            logger.debug(f"Зададени права {mode:o} за {dir_path}")
        except Exception as e:
            logger.debug(f"Не могат да се променят правата на {dir_path}: {e}")
            
        return True
    except Exception as e:
        logger.warning(f"Грешка при създаване на {dir_path}: {str(e)}")
        return False

# Създаваме критичните директории
for dir_path in required_dirs:
    ensure_directory_exists(dir_path)

# Опитваме да създадем допълнителните директории за всеки случай
for dir_path in additional_dirs:
    ensure_directory_exists(dir_path)

# Конфигуриране на статични файлове и шаблони
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Регистриране на модулите с обработка на изключения
# Инициализираме модулите

# Функция за безопасно инициализиране на модул
def initialize_module(module_name, router, prefix, tags, retries=2, retry_delay=2):
    """
    Безопасно инициализира модул с поддръжка на повторни опити
    
    Args:
        module_name: Име на модула
        router: Рутер на модула
        prefix: Префикс за URL
        tags: Тагове за документация
        retries: Брой повторни опити
        retry_delay: Забавяне между опитите
    """
    success = False
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            if attempt > 0:
                logger.info(f"Повторен опит {attempt} за инициализиране на модул {module_name}")
                
            # Регистриране на рутера
            app.include_router(router, prefix=prefix, tags=tags)
            logger.info(f"Успешно инициализиран модул {module_name}")
            success = True
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Грешка при инициализиране на модул {module_name} (опит {attempt+1}/{retries+1}): {str(e)}")
            
            if attempt < retries:
                logger.info(f"Изчакване {retry_delay} секунди преди повторен опит...")
                time.sleep(retry_delay)
                
    if not success:
        logger.error(f"Не може да се инициализира модул {module_name} след {retries+1} опита. Последна грешка: {last_error}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
    
    return success

# Инициализираме модулите в правилния ред
capture_initialized = initialize_module(
    "capture", capture_router, "/capture", ["Image Capture"]
)

ptz_initialized = initialize_module(
    "onvif_ptz", ptz_router, "/ptz", ["PTZ Control"]
)

# Определяме кои модули са инициализирани успешно
initialized_modules = []
if capture_initialized:
    initialized_modules.append("Image Capture")
if ptz_initialized:
    initialized_modules.append("ONVIF PTZ")

# Логирование, какие модули были инициализированы
logger.info(f"Инициализирани модули: {', '.join(initialized_modules)}")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главна страница с информация за системата"""
    
    # Вземаме информация от модулите
    ptz_config = get_ptz_config()
    capture_config = get_capture_config()
    
    # Добавяме информация за Hugging Face
    is_hf_space = os.environ.get('SPACE_ID') is not None
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "PTZ Camera Control System",
        "ptz_config": ptz_config,
        "capture_config": capture_config,
        "timestamp": int(time.time()) if 'time' in globals() else 0,
        "is_hf_space": is_hf_space
    })

@app.get("/health")
async def health():
    """Проверка на здравословното състояние на системата"""
    ptz_config = get_ptz_config()
    capture_config = get_capture_config()
    
    # Добавяме информация за средата
    is_hf_space = os.environ.get('SPACE_ID') is not None
    space_id = os.environ.get('SPACE_ID', 'local')
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "modules": {
            "ptz_control": ptz_config.status,
            "capture": capture_config.status
        },
        "environment": {
            "is_huggingface": is_hf_space,
            "space_id": space_id if is_hf_space else None,
            "system_time": (str(datetime.now())
                             if 'datetime' in globals() else None)
        }
    }

# Маршрут за пренасочване към последната снимка
@app.get("/latest.jpg")
async def latest_image_redirect():
    """Връща последното изображение от камерата"""
    try:
        # Списък с възможни места, където може да е изображението
        possible_paths = [
            "static/latest.jpg",
            os.path.join("frames", "latest.jpg")
        ]

        # Проверяваме в различните места
        for path in possible_paths:
            if os.path.exists(path):
                file_size = os.path.getsize(path)
                if file_size > 0:
                    logger.info(f"Serving latest.jpg from {path}, size: {file_size} bytes")
                    return FileResponse(path, media_type="image/jpeg")
        
        # Не намерихме съществуващо изображение, пренасочваме към capture модула,
        # който ще се опита да направи нова снимка
        return RedirectResponse(url="/capture/latest.jpg")
    except Exception as e:
        logger.error(f"Грешка при опит за достъп до latest.jpg: {str(e)}")
        # Пренасочване към capture модула като последна опция
        return RedirectResponse(url="/capture/latest.jpg")

# Модулите за работа с дата и време са преместени в началото на файла

if __name__ == "__main__":
    # Настройки от environment променливи
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))  # Hugging Face порт
    
    # Проверка дали работим в Hugging Face Space
    is_hf_space = os.environ.get('SPACE_ID') is not None
    if is_hf_space:
        space_info = f"в HF Space: {os.environ.get('SPACE_ID')}"
    else:
        space_info = "локално"
    
    logger.info(
        f"Стартиране на PTZ Camera Control System "
        f"на {host}:{port} {space_info}"
    )
    logger.info("Инициализирани модули: ONVIF PTZ, Image Capture")
    
    # Стартиране на сървъра с подходящи настройки за Hugging Face
    uvicorn.run(
        app, 
        host=host, 
        port=port, 
        log_level="info",
        # Настройки за Hugging Face Spaces:
        proxy_headers=True,  # Разрешаване на проксиране на заглавки
        forwarded_allow_ips="*"  # Разрешаване на IP адреси за прехвърляне
    )