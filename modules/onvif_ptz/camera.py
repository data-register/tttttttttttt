"""
Контролер за ONVIF PTZ камера
"""

import time
import threading
import traceback
from datetime import datetime
from onvif import ONVIFCamera
from typing import Optional, List, Dict, Any

from .config import get_ptz_config, update_ptz_config, PTZPosition, cache_preset_position
from utils.logger import setup_logger
from utils.helpers import wait_with_interval

# Инициализиране на логър
logger = setup_logger("ptz_camera")

# Глобални променливи
ptz_thread = None
onvif_cam = None
ptz_service = None
media_service = None
imaging_service = None
profile_token = None

def initialize_camera() -> bool:
    """
    Инициализира връзка с ONVIF камерата
    
    Returns:
        bool: True ако инициализацията е успешна, False в противен случай
    """
    global onvif_cam, ptz_service, media_service, imaging_service, profile_token
    
    config = get_ptz_config()
    
    try:
        logger.info(f"Инициализиране на връзка с ONVIF камера: {config.onvif_url}")
        
        # Извличане на хост от URL
        # Очакваме URL във формат: rtsp://IP:PORT/path
        url_parts = config.onvif_url.split("//")
        if len(url_parts) > 1:
            host_port = url_parts[1].split("/")[0]
            host = host_port.split(":")[0]
            
            # Извличаме RTSP порта, но за ONVIF използваме порт 80
            if ":" in host_port:
                rtsp_port = int(host_port.split(":")[1])
            else:
                rtsp_port = 554
                
            # За ONVIF връзката използваме порт 80 вместо RTSP порта
            port = 80
                
            logger.info(f"Извлечен хост: {host}, RTSP порт: {rtsp_port}, ONVIF порт: {port}")
        else:
            host = config.onvif_url
            port = 80
            logger.warning(f"Не може да се извлече хост и порт от URL, използване по подразбиране: {host}:{port}")
        
        # Предварителна настройка на всички необходими директории за кеширане
        import os
        import sys
        from zeep.cache import SqliteCache
        from zeep.transports import Transport
        import requests
        
        # Явно задаване на директории за кеширане в различни библиотеки
        cache_dirs = [
            os.environ.get('ZEEP_CACHE_DIR', None),
            os.path.join(os.environ.get('HOME', '/app'), '.cache'),
            os.path.join(os.environ.get('PYTHONUSERBASE', '/app/.local'), '.cache'),
            '/tmp/.cache',
            './.cache'
        ]
        
        # Подготовка на всички възможни директории за кеширане
        for cache_dir in cache_dirs:
            if cache_dir:
                try:
                    logger.info(f"Подготовка на директория за кеш: {cache_dir}")
                    os.makedirs(cache_dir, exist_ok=True)
                    os.chmod(cache_dir, 0o777)
                    logger.info(f"Директория {cache_dir} създадена и настроена с права 777")
                except Exception as e:
                    logger.warning(f"Не може да се подготви {cache_dir}: {str(e)}")
        
        # Основна директория за кеш, която ще използваме
        cache_path = os.environ.get('ZEEP_CACHE_DIR',
                     os.path.join(os.environ.get('HOME', '/app'), '.cache'))
        logger.info(f"Използване на основна кеш директория: {cache_path}")
        
        # Проверка дали директорията съществува и има необходимите права
        if not os.path.exists(cache_path):
            logger.info(f"Директорията не съществува, ще се създаде: {cache_path}")
            try:
                os.makedirs(cache_path, exist_ok=True)
                os.chmod(cache_path, 0o777)
            except Exception as e:
                logger.warning(f"Грешка при създаване на кеш директория: {str(e)}")
                
        # Явна настройка на транспорта и кеша на Zeep
        db_path = os.path.join(cache_path, 'onvif.db')
        logger.info(f"Използване на SQLite файл за кеш: {db_path}")
        
        try:
            cache = SqliteCache(path=db_path, timeout=60)
            transport = Transport(cache=cache)
            logger.info("Успешно създаден Zeep транспорт с кеш")
        except Exception as e:
            logger.warning(f"Проблем при създаване на кеш, опит без кеш: {str(e)}")
            transport = Transport(cache=None)
            
        # Създаваме камера с транспорт, който има настроен кеш
        # Библиотеката не приема директно cache_location
        try:
            logger.info("Опит за създаване на ONVIF камера с транспорт")
            onvif_cam = ONVIFCamera(
                host,
                port,
                config.username,
                config.password,
                transport=transport
            )
            logger.info("Успешно създадена ONVIF камера с кеш")
        except Exception as e:
            logger.warning(f"Грешка при създаване с транспорт: {str(e)}")
            # Опит без транспорт като последна опция
            logger.info("Опит за създаване на ONVIF камера без кеш")
            onvif_cam = ONVIFCamera(
                host,
                port,
                config.username,
                config.password
            )
        
        # Инициализиране на услугите
        ptz_service = onvif_cam.create_ptz_service()
        media_service = onvif_cam.create_media_service()
        imaging_service = onvif_cam.create_imaging_service()
        
        # Получаване на профилите на камерата
        media_profiles = media_service.GetProfiles()
        if not media_profiles:
            logger.error("Не са открити медийни профили от камерата")
            return False
        
        # Използваме първия профил
        profile_token = media_profiles[0].token
        logger.info(f"Използване на медиен профил с token: {profile_token}")
        
        # Проверка дали камерата поддържа PTZ
        ptz_nodes = ptz_service.GetNodes()
        if not ptz_nodes:
            logger.error("Камерата не поддържа PTZ функционалност")
            return False
        
        # Обновяваме статуса
        update_ptz_config(status="ok")
        logger.info("ONVIF камерата е успешно инициализирана")
        
        # Опитваме да получим текущата позиция
        get_current_position()
        
        return True
    
    except Exception as e:
        logger.error(f"Грешка при инициализиране на ONVIF камерата: {str(e)}")
        update_ptz_config(status="error")
        return False

def get_presets() -> List[Dict[str, Any]]:
    """
    Получава списък с наличните пресети на камерата
    
    Returns:
        List[Dict]: Списък с пресетите
    """
    global ptz_service, profile_token
    
    if not ptz_service or not profile_token:
        logger.error("PTZ услугата не е инициализирана")
        return []
    
    try:
        presets = ptz_service.GetPresets({'ProfileToken': profile_token})
        
        # Форматираме резултата
        result = []
        for i, preset in enumerate(presets):
            # Интроспекция за дебъгване
            preset_attrs = dir(preset)
            logger.info(f"Preset attributes: {preset_attrs}")
            
            # Безопасно извличане на атрибути
            if hasattr(preset, 'token'):
                token = preset.token
            elif hasattr(preset, 'Token'):
                token = preset.Token
            else:
                token = f"preset_{i}"
                
            if hasattr(preset, 'Name'):
                name = preset.Name
            else:
                name = f"Preset {i}"
                
            preset_info = {
                'token': token,
                'name': name,
                'index': i
            }
            result.append(preset_info)
            logger.info(f"Добавен пресет: {preset_info}")
        
        logger.info(f"Получени {len(result)} пресета от камерата")
        return result
    
    except Exception as e:
        logger.error(f"Грешка при получаване на пресетите: {str(e)}")
        return []

def get_current_position() -> Optional[PTZPosition]:
    """
    Получава текущата позиция на камерата
    
    Returns:
        PTZPosition или None при грешка
    """
    global ptz_service, profile_token
    
    if not ptz_service or not profile_token:
        logger.error("PTZ услугата не е инициализирана")
        return None
    
    try:
        # Получаваме текущата позиция
        status = ptz_service.GetStatus({'ProfileToken': profile_token})
        position = status.Position
        
        # Създаваме обект за позицията
        ptz_position = PTZPosition(
            preset_token="",
            preset_name="Current",
            pan=float(position.PanTilt.x) if hasattr(position, 'PanTilt') and hasattr(position.PanTilt, 'x') else 0.0,
            tilt=float(position.PanTilt.y) if hasattr(position, 'PanTilt') and hasattr(position.PanTilt, 'y') else 0.0,
            zoom=float(position.Zoom.x) if hasattr(position, 'Zoom') and hasattr(position.Zoom, 'x') else 0.0
        )
        
        # Обновяваме конфигурацията
        update_ptz_config(position=ptz_position)
        
        return ptz_position
    
    except Exception as e:
        logger.error(f"Грешка при получаване на текуща позиция: {str(e)}")
        return None

def goto_preset(preset_number: int) -> bool:
    """
    Придвижва камерата към определен пресет
    
    Args:
        preset_number: Номер на пресета (0-4)
        
    Returns:
        bool: True ако операцията е успешна, False в противен случай
    """
    global ptz_service, profile_token
    
    if not ptz_service or not profile_token:
        logger.error("PTZ услугата не е инициализирана")
        return False
    
    config = get_ptz_config()
    
    try:
        # Получаваме списъка с пресети
        presets = get_presets()
        
        if not presets:
            logger.error("Няма налични пресети")
            # Опитваме да вземем presets директно, с отделен метод
            logger.info("Опит за директно извличане на пресети")
            try:
                raw_presets = ptz_service.GetPresets({'ProfileToken': profile_token})
                logger.info(f"Получени {len(raw_presets)} сурови пресета")
                
                # Логване на информация за дебъгване
                for i, p in enumerate(raw_presets):
                    logger.info(f"Пресет {i}: {dir(p)}")
            except Exception as e:
                logger.error(f"Грешка при директно извличане на пресети: {str(e)}")
            
            return False
        
        # Проверяваме дали пресетът е валиден
        if preset_number < 0 or preset_number >= len(presets):
            logger.error(f"Невалиден номер на пресет: {preset_number}. Налични са само {len(presets)} пресета.")
            return False
        
        preset_token = presets[preset_number]['token']
        preset_name = presets[preset_number]['name']
        
        logger.info(f"Придвижване към пресет {preset_number} ({preset_name}), token: {preset_token}")
        
        # Изпращаме команда за придвижване
        ptz_service.GotoPreset({
            'ProfileToken': profile_token,
            'PresetToken': preset_token,
            'Speed': {'PanTilt': {'x': 1.0, 'y': 1.0}, 'Zoom': {'x': 1.0}}
        })
        
        # Изчакваме малко време за да се придвижи камерата
        time.sleep(2)
        
        # Получаваме новата позиция
        new_position = get_current_position()
        if new_position:
            new_position.preset_token = preset_token
            new_position.preset_name = preset_name
            
            # Кешираме позицията
            cache_preset_position(preset_number, new_position)
        
        # Обновяваме състоянието
        update_ptz_config(
            current_preset=preset_number,
            last_move_time=datetime.now()
        )
        
        logger.info(f"Успешно придвижване към пресет {preset_number}")
        return True
    
    except Exception as e:
        logger.error(f"Грешка при придвижване към пресет {preset_number}: {str(e)}")
        return False

def ptz_cycle_routine():
    """
    Основен цикъл за движение между пресетите
    """
    config = get_ptz_config()
    
    # Първоначално отиваме на позиция 0 (начална)
    logger.info("Стартиране на цикъл между пресетите. Отиваме към начална позиция.")
    goto_preset(config.home_preset)
    
    while config.running:
        config = get_ptz_config()
        
        # Проверяваме дали сме в режим на автоматичен цикъл и дали PTZ e активен
        if not config.is_scheduled_mode or not config.ptz_enabled:
            logger.info(f"Цикълът е спрян. Автоматичен режим: {config.is_scheduled_mode}, PTZ активен: {config.ptz_enabled}. Изчакваме...")
            time.sleep(10)
            continue
        
        try:
            # Изчакваме в начална позиция (намалено време за тестове - 60 секунди)
            actual_home_dwell = min(60, config.home_dwell_time)  # Максимум 60 секунди за тестване
            logger.info(f"Изчакване в начална позиция за {actual_home_dwell} секунди")
            
            # Проверяваме дали сме спрени на всеки 5 секунди
            if not wait_with_interval(actual_home_dwell, 5.0,
                lambda: not get_ptz_config().running or
                        not get_ptz_config().is_scheduled_mode or
                        not get_ptz_config().ptz_enabled):
                logger.info("Изчакването в начална позиция е прекратено")
                continue
            
            logger.info("Започваме обхождане на пресетите")
            # Обхождаме всички пресети (без началния, който е обикновено 0)
            for preset in config.presets:
                # Проверяваме отново дали сме активни
                current_config = get_ptz_config()
                if not current_config.running or not current_config.is_scheduled_mode or not current_config.ptz_enabled:
                    logger.info("Цикълът е прекратен по време на обхождане на пресетите")
                    break
                    
                if preset == config.home_preset:
                    logger.info(f"Пропускаме началния пресет {preset}")
                    continue
                
                # Отиваме към текущия пресет
                logger.info(f"Преминаване към пресет {preset}")
                success = goto_preset(preset)
                
                if not success:
                    logger.error(f"Не може да се премине към пресет {preset}, пропускаме")
                    continue
                
                # Изчакваме преди да направим снимка
                logger.info(f"Изчакване {config.capture_delay} секунди преди снимка")
                time.sleep(config.capture_delay)  # Просто изчакване без прекъсване
                
                # Опитваме да направим снимка (с повече опити)
                try:
                    from modules.capture.capture import capture_frame
                    logger.info("====== Опит за заснемане на кадър ======")
                    
                    # Правим 3 опита за снимане
                    result = False
                    for attempt in range(1, 4):
                        logger.info(f"Опит за снимане #{attempt}")
                        result = capture_frame()
                        if result:
                            logger.info(f"Снимането успешно на опит {attempt}")
                            break
                        
                        # Кратко изчакване преди следващия опит
                        time.sleep(2)
                    
                    logger.info(f"Краен резултат от заснемането: {'успешно' if result else 'неуспешно след 3 опита'}")
                except Exception as e:
                    logger.error(f"Грешка при заснемане на кадър: {str(e)}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                
                # Изчакваме на тази позиция
                logger.info(f"Изчакване на пресет {preset} за {config.dwell_time} секунди")
                time.sleep(config.dwell_time)  # Просто изчакване без прекъсване
            
            # Връщаме се в начална позиция
            logger.info("Връщане към начална позиция")
            goto_preset(config.home_preset)
            
        except Exception as e:
            logger.error(f"Грешка в цикъла между пресетите: {str(e)}")
            # Опитваме се да се върнем в начална позиция при грешка
            try:
                goto_preset(config.home_preset)
            except:
                pass
            
            # Изчакваме малко преди следващия опит
            time.sleep(30)

def start_ptz_thread():
    """Стартира фонов процес за цикъл между пресетите"""
    global ptz_thread
    
    if ptz_thread is None or not ptz_thread.is_alive():
        ptz_thread = threading.Thread(target=ptz_cycle_routine)
        ptz_thread.daemon = True
        ptz_thread.start()
        logger.info("PTZ thread started")
        return True
    
    return False

def stop_ptz_thread():
    """Спира фоновия процес за цикъл между пресетите"""
    update_ptz_config(running=False)
    logger.info("PTZ thread stopping")
    return True

def toggle_scheduled_mode(enabled: bool):
    """Включва или изключва режима на автоматичен цикъл"""
    update_ptz_config(is_scheduled_mode=enabled)
    logger.info(f"Автоматичен цикъл {'включен' if enabled else 'изключен'}")
    return True

# Функция за инициализиране на модула
def initialize():
    """Инициализира модула"""
    try:
        # Опит за инициализация на ONVIF камерата
        success = initialize_camera()
        
        if success:
            # Стартираме thread за цикъл между пресетите
            start_ptz_thread()
            logger.info("ONVIF PTZ модул инициализиран успешно")
            update_ptz_config(status="ok", ptz_enabled=True)
            return True
        else:
            # Грешка при инициализация, но модулът продължава да работи
            # с ограничена функционалност
            logger.warning("ONVIF PTZ модул инициализиран с ограничена функционалност")
            update_ptz_config(status="limited", ptz_enabled=False)
            return False
    except Exception as e:
        # Глобална грешка при инициализация
        logger.error(f"Грешка при инициализиране на ONVIF PTZ модул: {str(e)}")
        try:
            update_ptz_config(status="error", ptz_enabled=False)
        except:
            pass
        return False

# Автоматично инициализиране с повторни опити при неуспех
try:
    if not initialize():
        logger.warning("Първи опит за инициализация не успя, опитваме отново след 2 секунди")
        time.sleep(2)
        initialize()
except Exception as e:
    logger.error(f"Критична грешка при инициализация на модула: {str(e)}")