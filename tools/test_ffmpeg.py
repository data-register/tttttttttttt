#!/usr/bin/env python3
"""
Инструмент за тестване на FFmpeg интеграцията в PTZ Camera Control System
Този скрипт проверява FFmpeg функционалността и извлича тестови кадри от потоци
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Добавяме root директорията на проекта в sys.path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
sys.path.insert(0, str(root_dir))

# Импортираме модулите от нашето приложение
try:
    from modules.stream.ffmpeg_utils import (
        check_ffmpeg_installed, 
        capture_frame_from_stream, 
        get_frame_from_public_stream, 
        add_timestamp_to_frame
    )
    from utils.logger import setup_logger
except ImportError as e:
    print(f"Грешка при импортиране на модулите: {e}")
    print("Моля, уверете се че сте в правилната директория и всички зависимости са инсталирани")
    print(f"Текуща директория: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

# Инициализираме логъра
logger = setup_logger("ffmpeg_test")

def print_section(title):
    """Принтира секция със заглавие"""
    print("\n" + "=" * 60)
    print(f" {title} ".center(60, "="))
    print("=" * 60)

def check_ffmpeg():
    """Проверява дали FFmpeg е инсталиран и достъпен"""
    print_section("Проверка на FFmpeg")
    
    print("Проверка дали FFmpeg е инсталиран...")
    ffmpeg_available = check_ffmpeg_installed()
    
    if ffmpeg_available:
        print("✅ FFmpeg е наличен и работи правилно!")
    else:
        print("❌ FFmpeg не е наличен!")
        print("Моля, инсталирайте FFmpeg за да продължите:")
        print("  Debian/Ubuntu: sudo apt-get install ffmpeg")
        print("  CentOS/RHEL: sudo yum install ffmpeg")
        print("  MacOS: brew install ffmpeg")
        sys.exit(1)

def test_capture_frame(stream_url, output_path=None):
    """Тества извличането на кадър от указан поток"""
    print_section(f"Тест на извличане на кадър")
    print(f"URL на потока: {stream_url}")
    
    if output_path is None:
        # Създаваме временна директория за тестови изображения
        test_dir = root_dir / "test_output"
        test_dir.mkdir(exist_ok=True)
        
        # Създаваме уникално име на файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = test_dir / f"test_frame_{timestamp}.jpg"
    
    # Записваме времето за измерване на производителността
    start_time = time.time()
    
    # Извличаме кадър
    success, frame_path, error_msg = capture_frame_from_stream(
        stream_url, 
        output_path=str(output_path),
        timeout=15
    )
    
    elapsed_time = time.time() - start_time
    
    if success:
        print(f"✅ Кадърът е успешно извлечен за {elapsed_time:.2f} секунди!")
        print(f"   Записан в: {frame_path}")
    else:
        print(f"❌ Грешка при извличане на кадър ({elapsed_time:.2f} секунди)")
        print(f"   Грешка: {error_msg}")
    
    return success, frame_path, error_msg

def test_public_stream_frame():
    """Тества извличане на кадър от публичен поток"""
    print_section("Тест на публичен поток")
    
    # Записваме времето за измерване на производителността
    start_time = time.time()
    
    # Извличаме кадър с вградената функция
    frame = get_frame_from_public_stream()
    
    elapsed_time = time.time() - start_time
    
    if frame is not None:
        print(f"✅ Кадърът е успешно извлечен за {elapsed_time:.2f} секунди!")
        print(f"   Размер на кадъра: {frame.shape}")
        
        # Записваме кадъра за проверка
        test_dir = root_dir / "test_output"
        test_dir.mkdir(exist_ok=True)
        
        import cv2
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = test_dir / f"public_stream_{timestamp}.jpg"
        
        # Добавяме timestamp към кадъра
        frame_with_timestamp = add_timestamp_to_frame(
            frame, 
            position="bottom-right", 
            text="Test FFmpeg"
        )
        
        # Запазваме кадъра
        cv2.imwrite(str(output_path), frame_with_timestamp)
        print(f"   Записан в: {output_path}")
    else:
        print(f"❌ Грешка при извличане на кадър ({elapsed_time:.2f} секунди)")
    
    return frame is not None

def test_all(stream_url=None):
    """Изпълнява всички тестове"""
    # Първо проверяваме дали FFmpeg е инсталиран
    check_ffmpeg()
    
    # Тестваме извличане от публичен поток
    public_stream_success = test_public_stream_frame()
    
    # Ако е предоставен URL, тестваме и него
    if stream_url:
        test_capture_frame(stream_url)
    
    # Извеждаме общо резюме
    print_section("Резюме на тестовете")
    print(f"FFmpeg наличен: ✅")
    print(f"Публичен поток: {'✅' if public_stream_success else '❌'}")
    if stream_url:
        print(f"Потребителски поток ({stream_url}): {'✅' if success else '❌'}")
    print("\nВсички тестови изображения са записани в директорията test_output")

def main():
    """Главна функция за изпълнение на тестовете"""
    parser = argparse.ArgumentParser(
        description="Тестове на FFmpeg интеграцията в PTZ Camera Control System"
    )
    parser.add_argument(
        "--url", 
        help="URL на видео поток за тестване (по избор)"
    )
    parser.add_argument(
        "--output", 
        help="Път за съхранение на тестовия кадър (по избор)"
    )
    parser.add_argument(
        "--test-public", 
        action="store_true",
        help="Тестване само на публичния поток"
    )
    parser.add_argument(
        "--check-only", 
        action="store_true",
        help="Само проверка дали FFmpeg е инсталиран"
    )

    args = parser.parse_args()
    
    if args.check_only:
        check_ffmpeg()
    elif args.test_public:
        check_ffmpeg()
        test_public_stream_frame()
    elif args.url:
        check_ffmpeg()
        test_capture_frame(args.url, args.output)
    else:
        test_all(args.url)

if __name__ == "__main__":
    main()