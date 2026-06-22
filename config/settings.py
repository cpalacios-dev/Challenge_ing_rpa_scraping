import os
from dotenv import load_dotenv

# Carga las variables del archivo .env si existe (entorno local)
load_dotenv()

class Settings:
    ENV: str = os.getenv("ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # URL para el Scraping
    URL_BANCO_CENTRAL: str = os.getenv("URL_BANCO_CENTRAL", "https://www.bcentral.cl")
    
    # Resiliencia y Timeouts
    TIMEOUT: int = int(os.getenv("TIMEOUT", "15"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    
    # Persistencia
    # STORAGE_BACKEND: "json" o "sqlite". Permite cambiar de motor de
    # persistencia sin tocar código (ej. distinto storage en local vs GCP).
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "json")
    OUTPUT_FILE: str = os.getenv("OUTPUT_FILE", "src/output/indicadores.json")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "src/output/indicadores.db")

settings = Settings()