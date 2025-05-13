#!/usr/bin/env python3
"""
Инструмент за тестване на FFmpeg интеграцията за извличане на кадри
"""

import os
import sys
import argparse
import time
import logging

# Настройка на логването
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ffmpeg_tester')

# Добавяме root директорията към Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.stream.ffmpeg_utils import check_ffmpeg_installed, capture_frame_from_stream, get_frame_from_public_stream, add_timestamp_to_frame
import cv2

def test_ffmpeg_installation():
    """Проверка за наличието на FFmpeg"""
    ffmpeg_available = check_ffmpeg_installed()
    if ffmpeg_available:
        logger.info("✅ FFmpeg е инсталиран и достъпен")
    else:
        logger.error("❌ FFmpeg не е намерен или не е достъпен - повечето функции няма да работят")

def test_frame_capture(url, output_path=None):
    """Тест за извличане на кадър от URL"""
    logger.info(f"Тест за извличане на кадър от {url}")
    
    success, path, error = capture_frame_from_stream(url, output_path)
    
    if success:
        logger.info(f"✅ Успешно извлечен кадър: {path}")
        if path and os.path.exists(path):
            size = os.path.getsize(path)
            logger.info(f"   Размер на файла: {size:,} bytes")
            
            # Проверяваме дали файлът е валидно изображение
            try:
                img = cv2.imread(path)
                if img is not None:
                    h, w = img.shape[:2]
                    logger.info(f"   Размери: {w}x{h}")
                else:
                    logger.warning("   Файлът не може да се зареди като изображение")
            except Exception as e:
                logger.warning(f"   Грешка при четене на изображението: {str(e)}")
    else:
        logger.error(f"❌ Грешка при извличане на кадър: {error}")

def test_public_stream_frame():
    """Тест за извличане на кадър от публичен поток"""
    logger.info("Тест за извличане на кадър от публичен поток")
    
    frame = get_frame_from_public_stream()
    
    if frame is not None:
        logger.info("✅ Успешно извлечен кадър от публичен поток")
        h, w = frame.shape[:2]
        logger.info(f"   Размери: {w}x{h}")
        
        # Добавяме timestamp и запазваме изображението за проверка
        frame_with_timestamp = add_timestamp_to_frame(frame, text="FFmpeg Test")
        filename = f"test_snapshot_{int(time.time())}.jpg"
        cv2.imwrite(filename, frame_with_timestamp)
        logger.info(f"   Запазен като: {filename}")
    else:
        logger.error("❌ Не може да се извлече кадър от публичния поток")

def main():
    parser = argparse.ArgumentParser(description='FFmpeg Integration Tester')
    parser.add_argument('--url', help='URL за тестване (RTSP, HLS, etc.)')
    parser.add_argument('--output', help='Изходен файл за запазване на кадър')
    parser.add_argument('--public', action='store_true', help='Тест на публичния поток')
    
    args = parser.parse_args()
    
    # Проверка за FFmpeg
    test_ffmpeg_installation()
    
    # Ако е поискан тест на публичния поток
    if args.public:
        test_public_stream_frame()
    
    # Ако е подаден URL за тестване
    if args.url:
        test_frame_capture(args.url, args.output)
    
    # Ако няма подадени аргументи, показваме помощ
    if not args.url and not args.public:
        logger.info("""
Примерна употреба:
  python test_ffmpeg.py --public             # Тест на публичния поток
  python test_ffmpeg.py --url rtsp://...     # Тест на конкретен RTSP URL
  python test_ffmpeg.py --url https://...    # Тест на HLS или друг поток
        """)

if __name__ == "__main__":
    main()