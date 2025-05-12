"""
Общи функции за логване в системата
"""

import os
import logging
from datetime import datetime

# Създаваме logs директория ако не съществува
os.makedirs("logs", exist_ok=True)

def setup_logger(name, level=logging.INFO):
    """
    Настройва логър с конзолен и файлов output
    
    Args:
        name: Име на логъра
        level: Ниво на логване
        
    Returns:
        Конфигуриран логър
    """
    # Създаваме логъра
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Проверяваме дали логърът вече има handlers
    if logger.handlers:
        return logger
    
    # Създаваме форматер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Добавяме конзолен handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Добавяме файлов handler
    today = datetime.now().strftime("%Y%m%d")
    log_file = f"logs/{name}_{today}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger