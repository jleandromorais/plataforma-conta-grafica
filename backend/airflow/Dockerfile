FROM apache/airflow:2.9.0

USER root

# Instala dependências do sistema para OCR e Processamento de PDF
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    poppler-utils \
    build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copia o requirements para dentro da imagem
COPY requirements.txt /requirements.txt

# Volta para o utilizador airflow para instalar pacotes Python com segurança
USER airflow

# Instala todas as dependências do projeto
RUN pip install --no-cache-dir -r /requirements.txt