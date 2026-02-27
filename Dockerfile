FROM python:3.11-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dossier de travail
WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY app/ ./app/

# Dossier de stockage
RUN mkdir -p /app/storage

# Port
EXPOSE 8000

# Lancement
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
