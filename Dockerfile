FROM python:3.11-slim

# Instala LibreOffice y las herramientas del sistema necesarias
RUN apt-get update && apt-get install -y \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e instala tus librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto de tu código al servidor
COPY . .

# Comando exacto para arrancar Streamlit usando app.py
CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]

