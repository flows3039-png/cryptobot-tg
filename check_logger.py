# check_logger.py
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "checks_errors.txt")

# Настраиваем логгер
logger = logging.getLogger("CheckLogger")
logger.setLevel(logging.ERROR)

# Формат: [Время] Функция: Ошибка
formatter = logging.Formatter('[%(asctime)s] %(funcName)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Запись в файл
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)

# Дублируем в консоль, чтобы видеть сразу
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def log_check_error(error: Exception, context: str = ""):
    """Логирует ошибку с контекстом."""
    msg = f"{context} | Ошибка: {type(error).__name__}: {error}" if context else f"{type(error).__name__}: {error}"
    logger.error(msg)