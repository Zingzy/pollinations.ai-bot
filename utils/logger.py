import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import logging
from loguru import logger

# Create logs directory if it doesn't exist
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


class DiscordLogger:
    """Custom logger for Discord.py integration with Loguru"""

    @staticmethod
    def setup_logging():
        """Configure the logging system"""
        # Remove default logger
        logger.remove()

        # Configure log format with time, level, and location
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        )

        # Add handlers for different log files
        # Latest log file
        logger.add(
            LOGS_DIR / "latest.log",
            format=log_format,
            level="INFO",
            rotation="00:00",  # Rotate at midnight
            retention="30 days",
            compression="zip",
            enqueue=True,
        )

        # Error log file
        logger.add(
            LOGS_DIR / "error.log",
            format=log_format,
            level="ERROR",
            rotation="100 MB",
            retention="90 days",
            compression="zip",
            enqueue=True,
        )

        # Console output
        logger.add(sys.stdout, format=log_format, level="INFO", colorize=True)

        # Intercept discord.py logging
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.INFO)

        # Create handler for discord.py logs
        class InterceptHandler(logging.Handler):
            def emit(self, record):
                # Get corresponding Loguru level if it exists
                try:
                    level = logger.level(record.levelname).name
                except ValueError:
                    level = record.levelno

                # Find caller from where originated the logged message
                frame, depth = logging.currentframe(), 2
                while frame.f_code.co_filename == logging.__file__:
                    frame = frame.f_back
                    depth += 1

                logger.opt(depth=depth, exception=record.exc_info).log(
                    level, record.getMessage()
                )

        discord_handler = InterceptHandler()
        logging.getLogger("discord").addHandler(discord_handler)

    @staticmethod
    def _format_metadata(metadata: Dict[str, Any]) -> str:
        """Format metadata as JSON string"""
        return json.dumps(metadata, default=str)

    @staticmethod
    def log_bot_event(action: str, status: str, details: str = None):
        """Log bot lifecycle events"""
        metadata = {
            "event_type": "bot_lifecycle",
            "metadata": {
                "action": action,
                "status": status,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        logger.info(f"Bot Event: {action} | {DiscordLogger._format_metadata(metadata)}")

    @staticmethod
    def log_command(
        command_name: str,
        execution_time: float,
        status: str,
        error_type: Optional[str] = None,
    ):
        """Log command execution"""
        metadata = {
            "event_type": "command",
            "metadata": {
                "command_name": command_name,
                "execution_time": execution_time,
                "status": status,
                "error_type": error_type,
            },
        }
        logger.info(
            f"Command: {command_name} | {DiscordLogger._format_metadata(metadata)}"
        )

    @staticmethod
    def log_image_generation(
        action: str,
        model: str,
        dimensions: Dict[str, int],
        generation_time: float,
        status: str,
        error_type: Optional[str] = None,
        cached: bool = False,
    ):
        """Log image generation events"""
        metadata = {
            "event_type": "image_generation",
            "metadata": {
                "action": action,
                "model": model,
                "dimensions": dimensions,
                "generation_time": generation_time,
                "status": status,
                "error_type": error_type,
                "cached": cached,
            },
        }
        logger.info(
            f"Image Generation: {action} | {DiscordLogger._format_metadata(metadata)}"
        )

    @staticmethod
    def log_error(
        error_type: str,
        error_message: str,
        traceback: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log error events"""
        metadata = {
            "event_type": "error",
            "metadata": {
                "error_type": error_type,
                "error_message": error_message,
                "traceback": traceback,
                "context": context,
            },
        }
        logger.error(
            f"Error: {error_type} | {DiscordLogger._format_metadata(metadata)}"
        )


# Initialize logging when module is imported
DiscordLogger.setup_logging()

# Create global logger instance
discord_logger = DiscordLogger()

# Export logger for use in other modules
__all__ = ["discord_logger", "logger"]
