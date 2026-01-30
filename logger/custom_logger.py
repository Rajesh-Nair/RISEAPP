import os
import logging
from datetime import datetime
import structlog

# Module-level variables to ensure single configuration
_logging_configured = False
_shared_log_file_path = None
_structlog_configured = False


class CustomLogger:
    def __init__(self, log_dir="logs"):
        # Log directory setup - FIX: use self.log_dir instead of log_dir
        self.log_dir = os.path.join(os.getcwd(), log_dir)
        os.makedirs(self.log_dir, exist_ok=True)

        # Time-stamped log file path - use shared path to avoid multiple files
        global _shared_log_file_path
        if _shared_log_file_path is None:
            log_file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            _shared_log_file_path = os.path.join(self.log_dir, log_file)
        
        self.log_file_path = _shared_log_file_path

    def get_logger(self, name=__file__):
        logger_name = os.path.basename(name)

        global _logging_configured, _structlog_configured

        # Configure logging only once
        if not _logging_configured:
            # Get root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.INFO)

            # Check if file handler already exists to avoid duplicates
            # Normalize paths for cross-platform compatibility
            normalized_log_path = os.path.normpath(os.path.abspath(self.log_file_path))
            has_file_handler = any(
                isinstance(h, logging.FileHandler) and 
                os.path.normpath(os.path.abspath(h.baseFilename)) == normalized_log_path
                for h in root_logger.handlers
            )
            
            # Check if console handler already exists
            has_console_handler = any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                for h in root_logger.handlers
            )

            # Add file handler if it doesn't exist
            if not has_file_handler:
                file_handler = logging.FileHandler(self.log_file_path, mode='a', encoding='utf-8')
                file_handler.setLevel(logging.INFO)
                file_handler.setFormatter(logging.Formatter("%(message)s"))
                root_logger.addHandler(file_handler)

            # Add console handler if it doesn't exist
            if not has_console_handler:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                console_handler.setFormatter(logging.Formatter("%(message)s"))
                root_logger.addHandler(console_handler)

            _logging_configured = True

        # Configure structlog only once
        if not _structlog_configured:
            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
                    structlog.processors.add_log_level,
                    structlog.processors.EventRenamer(to="event"),
                    structlog.processors.JSONRenderer()
                ],
                logger_factory=structlog.stdlib.LoggerFactory(),
                cache_logger_on_first_use=True,
            )
            _structlog_configured = True

        return structlog.get_logger(logger_name)


# --- Usage Example ---
if __name__ == "__main__":
    logger = CustomLogger().get_logger(__file__)
    logger.info("Word info sought", user_id=123, word="flabergasted")
    logger.error("Word doesnt exist", error="Failed to find word qweasrt", user_id=456)