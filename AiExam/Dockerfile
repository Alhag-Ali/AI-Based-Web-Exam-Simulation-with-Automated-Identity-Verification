FROM python:3.12-slim

ENV PIP_REQUIRE_HASHES=0
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-deu \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Schwere Pakete zuerst (eigener Layer = besserer Cache, weniger Timeout)
RUN pip install --no-cache-dir "tensorflow>=2.20" "tf-keras>=2.20"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD python manage.py migrate --noinput && \
    python create_demo_accounts.py && \
    python manage.py runserver 0.0.0.0:8000
