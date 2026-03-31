FROM apache/airflow:2.9.0

USER root

# Instala dependências do sistema necessárias para OCR e PDF processing
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Instala pacotes Python necessários para as DAGs de OCR/PDF
RUN pip install --no-cache-dir pdfplumber pytesseract

USER airflow

