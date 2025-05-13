#!/usr/bin/env python3
"""
Тестов скрипт за проверка на FFmpeg функционалността
"""

import os
import sys
import subprocess
import logging
from datetime import datetime

# Настройка на логване
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_ffmpeg")

def main():
    """Основна тестова функция"""
    logger.info("=== Стартиране на тестове за FFmpeg ===")
    
    # 1. Проверка за наличие на FFmpeg
    logger.info("Проверка за FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            ffmpeg_version = result.stdout.decode('utf-8', errors='ignore').split('\n')[0]
            logger.info(f"✅ FFmpeg е наличен: {ffmpeg_version}")
        else:
            logger.error("❌ FFmpeg не е намерен или не работи правилно!")
            return False
    except Exception as e:
        logger.error(f"❌ Грешка при проверка за FFmpeg: {e}")
        return False
    
    # 2. Проверка на директориите
    logger.info("Проверка на директориите...")
    dirs = ['frames', 'static']
    for dir_path in dirs:
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"✅ Директория {dir_path} е създадена/съществува")
            
            # Тест за запис
            test_file = os.path.join(dir_path, 'test_write.txt')
            with open(test_file, 'w') as f:
                f.write(f"Test at {datetime.now()}")
            logger.info(f"✅ Успешен запис в {test_file}")
            os.remove(test_file)
        except Exception as e:
            logger.error(f"❌ Проблем с директория {dir_path}: {e}")
            return False
    
    # 3. Тест за приложение на FFmpeg за извличане на кадър
    logger.info("Тест за извличане на кадър с FFmpeg...")
    
    # Създаваме изходен файл
    output_path = os.path.join('frames', 'test_ffmpeg.jpg')
    
    # Подготвяме URL с автентикация
    rtsp_user = os.getenv("RTSP_USER", "admin")
    rtsp_pass = os.getenv("RTSP_PASS", "L20E0658")
    rtsp_url = f"rtsp://{rtsp_user}:{rtsp_pass}@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0&unicast=true&proto=Onvif"
    
    # Маскираме URL за логовете
    log_url = rtsp_url.replace(rtsp_pass, "*****")
    logger.info(f"URL за тестване: {log_url}")
    
    # FFmpeg команда
    command = [
        'ffmpeg', 
        '-rtsp_transport', 'tcp',
        '-timeout', '15000000',
        '-y',
        '-i', rtsp_url,
        '-frames:v', '1',
        '-q:v', '2',
        output_path
    ]
    
    logger.info(f"Изпълняване на FFmpeg команда...")
    try:
        result = subprocess.run(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            timeout=20
        )
        
        # Проверка за успех
        if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logger.error(f"❌ FFmpeg не успя да извлече кадър: {error_msg}")
            return False
        
        # Проверка на файла
        file_size = os.path.getsize(output_path)
        logger.info(f"✅ Успешно заснет и запазен кадър: {output_path}, размер: {file_size} байта")
        
        # Копираме в static директорията за лесен достъп
        if not os.path.exists('static'):
            os.makedirs('static', exist_ok=True)
        
        import shutil
        static_path = os.path.join('static', 'test_ffmpeg.jpg')
        shutil.copy(output_path, static_path)
        logger.info(f"✅ Копирано в: {static_path}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Грешка при тестване на FFmpeg: {e}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False
    
if __name__ == "__main__":
    success = main()
    if success:
        logger.info("✅ Всички тестове са успешни!")
        sys.exit(0)
    else:
        logger.error("❌ Някои тестове не успяха!")
        sys.exit(1)