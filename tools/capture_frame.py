#!/usr/bin/env python3
"""
Инструмент за командния ред за директно извличане на кадри от RTSP потоци
"""

import os
import sys
import argparse
import time
from datetime import datetime
from pathlib import Path

# Добавяме root директорията на проекта в sys.path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.insert(0, str(root_dir))

# Импортираме нужните модули
try:
    from modules.stream.ffmpeg_utils import get_frame_from_public_stream, check_ffmpeg_installed
    import cv2
except ImportError as e:
    print(f"Грешка при импортиране на модули: {e}")
    print("Проверете дали сте инсталирали OpenCV и другите зависимости:")
    print("  pip install opencv-python-headless numpy")
    sys.exit(1)

def main():
    """Главна функция за извличане на кадри от камерата"""
    parser = argparse.ArgumentParser(description="Извличане на кадри от RTSP камера")
    
    parser.add_argument(
        "--url", "-u",
        default="rtsp://admin:admin@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0",
        help="RTSP URL на камерата"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Изходен файл (по подразбиране: frames/capture_TIMESTAMP.jpg)"
    )
    
    parser.add_argument(
        "--latest", "-l",
        action="store_true",
        help="Запазва също копие в latest.jpg"
    )
    
    parser.add_argument(
        "--method", "-m",
        choices=["ffmpeg", "opencv"],
        default="ffmpeg",
        help="Метод за извличане на кадър (по подразбиране: ffmpeg)"
    )
    
    parser.add_argument(
        "--info", "-i",
        action="store_true",
        help="Добавя информационен текст върху изображението"
    )
    
    args = parser.parse_args()
    
    # Проверяваме дали FFmpeg е наличен
    if args.method == "ffmpeg" and not check_ffmpeg_installed():
        print("FFmpeg не е намерен. Моля инсталирайте ffmpeg или използвайте метода --method=opencv")
        sys.exit(1)
    
    # Генерираме име на изходния файл ако не е подадено
    if not args.output:
        # Убеждаваме се, че директорията frames съществува
        frames_dir = os.path.join(root_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Генерираме име с текущ timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(frames_dir, f"capture_{timestamp}.jpg")
    
    print(f"Извличане на кадър от {args.url}...")
    
    # Използваме функцията за извличане
    start_time = time.time()
    frame = get_frame_from_public_stream(stream_url=args.url, force_refresh=True)
    elapsed = time.time() - start_time
    
    if frame is not None:
        # Добавяме информационен текст ако е поискано
        if args.info:
            # Добавяме текст със заглавие
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cv2.putText(
                frame,
                "PTZ Camera - Obzor",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )
            
            cv2.putText(
                frame,
                f"Време: {timestamp} | Метод: {args.method}",
                (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (200, 200, 255),
                1
            )
        
        # Записваме изображението
        cv2.imwrite(args.output, frame)
        print(f"✅ Успешно извлечен кадър за {elapsed:.2f} секунди!")
        print(f"✅ Записан в: {args.output}")
        
        # Ако е поискано, записваме и в latest.jpg
        if args.latest:
            latest_path = os.path.join(os.path.dirname(args.output), "latest.jpg")
            cv2.imwrite(latest_path, frame)
            print(f"✅ Копие записано в: {latest_path}")
        
        return 0
    else:
        print(f"❌ Грешка при извличане на кадър!")
        return 1

if __name__ == "__main__":
    sys.exit(main())