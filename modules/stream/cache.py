"""
Кеш механизъм за съхранение на кадри от камерата
"""

import time
import threading
from datetime import datetime
import numpy as np
from utils.logger import setup_logger

# Инициализиране на логър
logger = setup_logger("stream_cache")

class FrameCache:
    """
    Клас за кеширане на кадри от камерата за подобряване на производителността
    и намаляване на натоварването върху камерата.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton патерн - осигурява една инстанция на кеша в цялото приложение"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FrameCache, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Инициализира кеша ако това не е направено вече"""
        if self._initialized:
            return
            
        # Защитаваме достъпа до кеша с lock
        self._cache_lock = threading.Lock()
        
        # Структура на кеша: {source_id -> {'frame': np.array, 'timestamp': float, 'metadata': dict}}
        self._cache = {}
        
        # Конфигурация на кеша
        self._default_max_age = 10  # Максимална възраст на кадър в секунди
        
        # Флаг за инициализация
        self._initialized = True
        logger.info("Инициализиран кеш за кадри от камерата")
    
    def store_frame(self, frame, source_id="default", metadata=None, max_age=None):
        """
        Съхранява кадър в кеша
        
        Args:
            frame (numpy.ndarray): Кадър като numpy масив
            source_id (str): Идентификатор на източника (например URL на потока)
            metadata (dict): Допълнителни метаданни за кадъра
            max_age (int): Максимална възраст на кадъра в секунди преди да се счита за невалиден
        """
        if frame is None:
            logger.warning(f"Опит за кеширане на None кадър от източник {source_id}")
            return False
            
        with self._cache_lock:
            # Съхраняваме кадъра, текущото време и метаданните
            self._cache[source_id] = {
                'frame': frame.copy(),  # Копираме кадъра, за да избегнем промени в оригинала
                'timestamp': time.time(),
                'metadata': metadata or {},
                'max_age': max_age or self._default_max_age
            }
            
            logger.debug(f"Кеширан кадър от източник {source_id}, размер: {frame.shape}")
            return True
    
    def get_frame(self, source_id="default", max_age=None):
        """
        Извлича кадър от кеша ако е актуален
        
        Args:
            source_id (str): Идентификатор на източника
            max_age (int): Максимална допустима възраст в секунди
            
        Returns:
            tuple: (кадър, метаданни) или (None, None) ако кадърът не е в кеша или е твърде стар
        """
        with self._cache_lock:
            if source_id not in self._cache:
                logger.debug(f"Кадър за източник {source_id} не е намерен в кеша")
                return None, None
                
            cache_entry = self._cache[source_id]
            current_time = time.time()
            
            # Проверяваме дали кадърът е още валиден
            entry_age = current_time - cache_entry['timestamp']
            max_allowed_age = max_age or cache_entry.get('max_age', self._default_max_age)
            
            if entry_age > max_allowed_age:
                logger.debug(f"Кадърът от източник {source_id} е твърде стар: {entry_age:.2f}s > {max_allowed_age}s")
                # Изтриваме изтеклия кадър, за да не заема памет
                if source_id in self._cache:
                    del self._cache[source_id]
                return None, None
                
            logger.debug(f"Използване на кеширан кадър от източник {source_id}, възраст: {entry_age:.2f}s")
            return cache_entry['frame'].copy(), cache_entry['metadata']
    
    def clear_cache(self, source_id=None):
        """
        Изчиства кеша за определен източник или всички източници
        
        Args:
            source_id (str): Идентификатор на източника или None за изчистване на целия кеш
        """
        with self._cache_lock:
            if source_id is None:
                # Изчистваме целия кеш
                self._cache.clear()
                logger.info("Изчистен целият кеш за кадри")
            elif source_id in self._cache:
                # Изтриваме само един източник
                del self._cache[source_id]
                logger.info(f"Изчистен кешът за източник {source_id}")
    
    def get_cache_status(self):
        """
        Връща статус информация за кеша
        
        Returns:
            dict: Информация за състоянието на кеша
        """
        with self._cache_lock:
            cache_info = {}
            
            for source_id, entry in self._cache.items():
                # Изчисляваме възрастта на всеки кадър
                age = time.time() - entry['timestamp']
                # Форматираме датата за по-добра четимост
                timestamp = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                
                # Запазваме информация за всеки запис в кеша
                cache_info[source_id] = {
                    'shape': str(entry['frame'].shape) if entry.get('frame') is not None else "None",
                    'age': f"{age:.2f}s",
                    'timestamp': timestamp,
                    'max_age': f"{entry.get('max_age', self._default_max_age)}s",
                    'metadata': entry.get('metadata', {})
                }
                
            return {
                'entries': len(self._cache),
                'sources': list(self._cache.keys()),
                'details': cache_info
            }

# Глобална инстанция на кеша
frame_cache = FrameCache()