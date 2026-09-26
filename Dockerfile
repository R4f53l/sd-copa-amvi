#pega uma versao mais leve do python
FROM python:3.12-slim

#nao cria arquivos pyc e retorna os logs imediatamnte
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

#instala as dependencias
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

#copia o codigo pro conteiner
COPY . /app/