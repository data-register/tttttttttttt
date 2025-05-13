# PTZ Camera Control - Локална версия

Това е локална версия на системата за контрол на PTZ камери, оптимизирана за работа в локална среда.

## Изисквания

1. **FFmpeg** - За извличане на кадри от RTSP поток
   ```bash
   sudo apt-get install ffmpeg
   ```

2. **Python пакети** - OpenCV и други зависимости
   ```bash
   pip install -r requirements.txt
   ```

## Стартиране на приложението

```bash
python app.py
```

По подразбиране, приложението ще се стартира на `http://localhost:7860`

## Директно извличане на кадър от RTSP поток

За директно извличане на кадър от RTSP поток можете да използвате инструмента `tools/capture_frame.py`:

```bash
# Основна употреба
./tools/capture_frame.py

# С потребителски URL
./tools/capture_frame.py --url rtsp://потребител:парола@ip:порт/пътека

# Записване в конкретен файл
./tools/capture_frame.py --output моя_снимка.jpg

# Добавяне на информация върху изображението
./tools/capture_frame.py --info

# Използване на OpenCV вместо FFmpeg
./tools/capture_frame.py --method opencv
```

## API

### Snapshot API

Извличане на моментен кадър от RTSP потока:

```
GET /stream/snapshot
```

Опционални параметри:
- `force_refresh=true` - Извлича нов кадър, игнорирайки кеша
- `rtsp_url=...` - Алтернативен RTSP URL

### Преглед на RTSP потока

```
GET /stream/view
```

## Структура на директориите

- `/frames` - Директория, където се съхраняват извлечените кадри
  - `latest.jpg` - Последният извлечен кадър
  - `frame_YYYYMMDD_HHMMSS.jpg` - Архивни копия на кадрите с времеви маркер

## Спецификации за RTSP URL

Стандартният URL за RTSP поток е:

```
rtsp://admin:admin@109.160.23.42:554/cam/realmonitor?channel=1&subtype=0
```

За друга камера заменете потребителското име, паролата и IP адреса.