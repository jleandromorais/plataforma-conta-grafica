FROM python:3.11-slim

# Tesseract com o idioma português: lê os PDFs escaneados (RET, Conciliação,
# Auditoria). Sem ele esses PDFs voltam sem valores.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESSERACT_CMD=/usr/bin/tesseract \
    PLATAFORMA_DB=/data/pmpv_data.db

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY Src ./Src

# /data é o disco persistente: o banco fica aqui e sobrevive a novos deploys.
# O volume é anexado pela plataforma (Railway Volumes, mount path /data), não aqui.
EXPOSE 8080

CMD ["python", "-m", "Src.api.serve"]
