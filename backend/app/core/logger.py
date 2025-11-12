"""
Configuración de logging
"""
import logging
import logging.handlers
import os
from .config import settings

# Crear directorio de logs
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "app.log")


def get_logger(name: str) -> logging.Logger:
    """Obtener logger configurado"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Formato de log
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para archivo
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5  # 10 MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
