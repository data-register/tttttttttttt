FROM python:3.9-slim

# Метаданни за Hugging Face Space
LABEL space.title="PTZ Camera Control"
LABEL space.emoji="📹"

WORKDIR /app

# Инсталиране на необходимите пакети
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копиране и инсталиране на Python зависимости
COPY requirements.txt .
# Специално фиксираме numpy на по-стара версия преди инсталиране на opencv
RUN pip install --no-cache-dir numpy==1.24.3 && \
    pip install --no-cache-dir -r requirements.txt

# Настройка на директории за кеширане
ENV HOME="/app"
ENV ZEEP_CACHE_DIR="/app/.cache"
ENV PYTHONUSERBASE="/app/.local"
ENV PATH="/app/.local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Създаваме всички необходими директории и задаваме права
RUN mkdir -p /app/.cache && chmod 777 /app/.cache && \
    mkdir -p /app/.local && chmod 777 /app/.local && \
    mkdir -p /app/.config && chmod 777 /app/.config && \
    mkdir -p /tmp && chmod 777 /tmp

# Създаване на структура на директории и задаване на правилните права
# Създаваме всички директории преди стартиране на приложението
USER root

# Първо създаваме всички основни директории
RUN mkdir -p /app/frames && \
    mkdir -p /app/templates && \
    mkdir -p /app/modules && \
    mkdir -p /app/modules/onvif_ptz && \
    mkdir -p /app/modules/capture && \
    mkdir -p /app/utils && \
    mkdir -p /app/logs && \
    mkdir -p /app/static && \
    mkdir -p /app/.cache && \
    mkdir -p /app/.local && \
    mkdir -p /app/.config && \
    mkdir -p /tmp/.cache

# След това задаваме правилните права
RUN chmod -R 777 /app && \
    chmod 777 /tmp && \
    chmod 777 /tmp/.cache

# Създаваме нов потребител с по-ниски права за изпълнение на приложението
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app /tmp/.cache

# Допълнителни разрешения за папките, за да работят в HF Space
RUN chmod -R 777 /app/

# Копиране на модулите
COPY modules/ /app/modules/
COPY utils/ /app/utils/
COPY templates/ /app/templates/
COPY app.py .

# Порт, на който ще работи приложението
EXPOSE 7860

# Стартиране на приложението
# Експлицитно задаваме променливите на средата тук, за да е сигурно че са достъпни
ENV HOME="/app"
ENV ZEEP_CACHE_DIR="/tmp/.cache"
ENV PYTHONUSERBASE="/app/.local"
ENV XDG_CACHE_HOME="/tmp/.cache"
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Стартираме приложението с правата на потребителя appuser
USER appuser
CMD ["python", "app.py"]