from config.settings import settings
from src.pipeline.logger import logger
from src.storage.base_storage import BaseStorage
from src.storage.json_storage import JSONStorage
from src.storage.sqlite_storage import SQLiteStorage


def get_storage() -> BaseStorage:
    """Devuelve la implementación de storage configurada vía
    la variable de entorno STORAGE_BACKEND ('json' o 'sqlite')."""
    backend = settings.STORAGE_BACKEND.lower().strip()

    if backend == "json":
        logger.info("Storage backend configurado: JSON")
        return JSONStorage()
    elif backend == "sqlite":
        logger.info("Storage backend configurado: SQLite")
        return SQLiteStorage()
    else:
        raise ValueError(
            f"STORAGE_BACKEND='{backend}' no es válido. Usa 'json' o 'sqlite'."
        )