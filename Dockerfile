# Paso 1: Usar una imagen base oficial de Python
FROM python:3.12-slim

# Paso 2: Instalar las dependencias del sistema operativo, incluyendo Tesseract y el paquete de idioma español
# El "-y" responde "sí" automáticamente a cualquier pregunta
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Paso 3: Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Paso 4: Copiar el archivo de requisitos e instalar las librerías de Python
# Esto se hace por separado para aprovechar el caché de Docker y acelerar futuras construcciones
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Paso 5: Copiar el resto del código de la aplicación al contenedor
COPY . .

# Paso 6: Exponer el puerto que Gunicorn usará y definir el comando de inicio
# Render necesita que la app escuche en 0.0.0.0 en un puerto específico
EXPOSE 10000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]

