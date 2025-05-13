#!/usr/bin/env python3
"""
Инструмент за тестване на RTSP потоци
Този скрипт помага за проверка на достъпността и валидността на RTSP URL.
"""

import os
import sys
import argparse
import time
import cv2
import logging

# Настройка на логването
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rtsp_tester')

def test_rtsp_connection(rtsp_url, show_frames=False, timeout=10, frames_to_capture=5):
    """
    Тества свързаността към RTSP URL
    
    Args:
        rtsp_url: RTSP URL за тестване
        show_frames: Дали да се показват кадрите (изисква графична среда)
        timeout: Таймаут за свързване в секунди
        frames_to_capture: Брой кадри за прихващане
        
    Returns:
        bool: Дали URL-ът е валиден и достъпен
    """
    logger.info(f"Тестване на RTSP URL: {rtsp_url.replace(':L20E0658@', ':*******@')}")
    
    try:
        # Създаваме VideoCapture обект
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        
        # Задаваме малък буфер за по-бърза работа
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Проверяваме дали потокът е отворен
        if not cap.isOpened():
            logger.error("Не може да се отвори RTSP потока")
            return False
        
        logger.info("RTSP потокът е отворен успешно")
        
        # Изчакваме да се инициализира буферът
        time.sleep(1)
        
        # Проверяваме дали можем да прочетем кадър в рамките на таймаута
        start_time = time.time()
        has_frame = False
        frame_count = 0
        
        while time.time() - start_time < timeout and frame_count < frames_to_capture:
            ret, frame = cap.read()
            
            if ret and frame is not None:
                has_frame = True
                frame_count += 1
                logger.info(f"Прихванат кадър {frame_count}/{frames_to_capture}")
                
                # Показваме кадрите ако е нужно
                if show_frames:
                    cv2.imshow('RTSP Test', frame)
                    cv2.waitKey(1)
            else:
                time.sleep(0.1)
        
        # Освобождаваме ресурсите
        cap.release()
        if show_frames:
            cv2.destroyAllWindows()
        
        if not has_frame:
            logger.error("Не може да се прочете кадър от RTSP потока")
            return False
        
        logger.info(f"Успешно прихванати {frame_count} кадъра")
        return True
    
    except Exception as e:
        logger.error(f"Грешка при тестване на RTSP URL: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='RTSP Stream Tester')
    parser.add_argument('--url', help='RTSP URL за тестване')
    parser.add_argument('--show', action='store_true', help='Показва кадрите (изисква графична среда)')
    parser.add_argument('--timeout', type=int, default=10, help='Таймаут за свързване в секунди')
    parser.add_argument('--frames', type=int, default=5, help='Брой кадри за прихващане')
    
    args = parser.parse_args()
    
    # Ако не е зададен URL, използваме URL от средата или по подразбиране
    if not args.url:
        rtsp_user = os.getenv("RTSP_USER", "admin")
        rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
        rtsp_host = os.getenv("RTSP_HOST", "109.160.23.42")
        rtsp_port = os.getenv("RTSP_PORT", "554")
        
        args.url = os.getenv("RTSP_URL", 
            f"rtsp://{rtsp_user}:{rtsp_pass}@{rtsp_host}:{rtsp_port}/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif")
    
    success = test_rtsp_connection(
        args.url, show_frames=args.show, timeout=args.timeout, frames_to_capture=args.frames
    )
    
    if success:
        logger.info("✅ RTSP потокът е валиден и достъпен!")
        sys.exit(0)
    else:
        logger.error("❌ RTSP потокът не е достъпен или има проблем")
        sys.exit(1)

if __name__ == "__main__":
    main()