import logging
import sys
from config.settings import settings

def setup_logger():
    logger = logging.getLogger("RPA_Fintech")
    
    if not logger.handlers:
        logger.setLevel(settings.LOG_LEVEL)
        
        # Formato limpio para consola y Cloud Logging en GCP
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()