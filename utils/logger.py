import sys
from loguru import logger
from config.manager import settings

# Get log directory from settings, with a fallback for safety
try:
    log_dir = settings.system.log_dir
except AttributeError:
    log_dir = "./logs" # Fallback directory

log_path = f"{log_dir}/proxy/deeproleplay.log"

# Configure logger
logger.remove()

# Console handler with a simple format
logger.add(
    sys.stderr, 
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# File handler for structured JSON logging
logger.add(
    log_path, 
    rotation="10 MB", 
    retention="10 days", 
    level="DEBUG", 
    encoding="utf-8", 
    enqueue=True,  # Make it process-safe
    serialize=True # Write logs in JSON format
)

# The logger is now configured and ready to be imported and used directly.