# --- base layer ----------------------------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости (ssl, tz)
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- deps layer ----------------------------------------------------
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- final image ---------------------------------------------------
FROM base
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# копируем исходники
COPY . /app

# создаём папку для данных и логов
RUN mkdir -p /app/data /app/logs

CMD ["python", "main.py"]
