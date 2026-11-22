# Образ бота-магазина.
# Собирается из папки app/ — код магазина лежит рядом.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# сначала зависимости — слой кэшируется и не пересобирается при правках кода
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# непривилегированный пользователь: боту файлы менять не нужно
RUN useradd --create-home --shell /usr/sbin/nologin bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app
USER bot

VOLUME ["/app/data"]
ENV DB_FILE=/app/data/shop.db

# проверка конфигурации при старте контейнера
HEALTHCHECK --interval=60s --timeout=15s --start-period=20s --retries=3 \
    CMD python -c "import config,sys; sys.exit(0 if config.config.validate()==[] else 1)"

CMD ["python", "bot.py"]
