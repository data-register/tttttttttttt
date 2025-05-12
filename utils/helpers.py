"""
Помощни функции за PTZ Camera Control System
"""

import time
from datetime import datetime

def get_timestamp_str():
    """
    Връща текущата дата и час във формат подходящ за имена на файлове
    
    Returns:
        str: Форматирана дата и час (например '20250511_153045')
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def wait_with_interval(seconds, check_interval=1.0, stop_check_func=None):
    """
    Изчаква определен брой секунди с проверка на условие за прекратяване
    
    Args:
        seconds: Време за изчакване в секунди
        check_interval: Интервал между проверките за прекратяване
        stop_check_func: Функция, която при връщане на True прекратява изчакването
        
    Returns:
        bool: True ако е изчакано цялото време, False ако изчакването е прекратено
    """
    start_time = time.time()
    end_time = start_time + seconds
    
    while time.time() < end_time:
        # Проверяваме дали трябва да прекратим изчакването
        if stop_check_func and stop_check_func():
            return False
        
        # Изчисляваме оставащото време
        remaining = end_time - time.time()
        if remaining <= 0:
            break
            
        # Изчакваме до следваща проверка (по-малкото от remaining и check_interval)
        sleep_time = min(remaining, check_interval)
        time.sleep(sleep_time)
    
    return True