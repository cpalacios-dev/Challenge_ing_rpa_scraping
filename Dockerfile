# Imagen oficial de Playwright para Python: ya incluye Chromium,
# sus dependencias de sistema (fonts, libs gráficas, etc.) y Python
# preinstalado. Evita tener que instalar manualmente todas las
# dependencias del navegador headless en una imagen base genérica.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Copiamos primero solo requirements.txt para aprovechar el cache
# de capas de Docker: si el código cambia pero no las dependencias,
# este paso no se repite en cada build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código del proyecto
COPY . .

# Cloud Run Jobs no expone puerto HTTP (a diferencia de Cloud Run
# Services): el contenedor simplemente ejecuta el comando y termina.
# El exit code determina éxito/fallo de la ejecución ante Cloud
# Scheduler / Cloud Logging.
ENTRYPOINT ["python", "main.py"]