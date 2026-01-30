# logger/__init__.py
from .custom_logger import CustomLogger
from pathlib import Path
import os

# Determine the base directory
BASE_DIR = Path(__file__).resolve().parent.parent
project = os.path.basename(BASE_DIR)

# Create a logger instance for this module
logger = CustomLogger().get_logger(__file__)
logger.info("Logger module initialized", project=project)
