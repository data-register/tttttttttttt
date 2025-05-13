"""
Помощни функции за тестване на capture модула
"""

import os
import cv2
import numpy as np
from datetime import datetime
from io import BytesIO

def create_test_image(width=640, height=480, text="Test Image", 
                     timestamp=None, save_path="static/latest.jpg"):
    """
    Създава тестово изображение с текст и timestamp
    """
    # Създаваме празно изображение
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Добавяме текст и timestamp
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    cv2.putText(
        image,
        text,
        (50, height // 2 - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2
    )
    
    cv2.putText(
        image,
        timestamp,
        (50, height // 2 + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (200, 200, 255),
        2
    )
    
    # Запазваме изображението
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, image)
    
    return save_path

def test_write_locations():
    """
    Тества запис във всички възможни локации за диагностика
    """
    results = {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    locations = [
        "static/latest.jpg",
        "frames/latest.jpg",
        "/tmp/latest.jpg"
    ]
    
    for location in locations:
        try:
            path = create_test_image(
                text=f"Test - {os.path.dirname(location)}",
                timestamp=timestamp,
                save_path=location
            )
            
            if os.path.exists(path):
                results[location] = {
                    "status": "success",
                    "size": os.path.getsize(path),
                    "created_at": timestamp
                }
            else:
                results[location] = {
                    "status": "fail",
                    "error": "File was not created"
                }
        except Exception as e:
            results[location] = {
                "status": "error",
                "error": str(e)
            }
    
    return results

def check_file_access():
    """
    Проверява достъпа до файловете в различни директории
    """
    results = {}
    directories = ["static", "frames", "/tmp"]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            
            # Проверка за запис
            test_file = os.path.join(directory, "test_access.txt")
            with open(test_file, "w") as f:
                f.write(f"Test write at {datetime.now()}")
                
            # Проверка за четене
            with open(test_file, "r") as f:
                content = f.read()
                
            # Проверка за изтриване
            os.remove(test_file)
            
            results[directory] = {
                "write": True,
                "read": True,
                "delete": True
            }
        except Exception as e:
            results[directory] = {
                "error": str(e)
            }
    
    return results