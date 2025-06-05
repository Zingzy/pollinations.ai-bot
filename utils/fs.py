import os
import aiofiles.os
from utils.logger import logger


async def list_py_files(path: str) -> list[str]:
    """
    Asynchronously list Python files in a directory with fallback to synchronous method.

    Args:
        path: Directory path to list files from

    Returns:
        List of Python filenames (without .py extension)
    """
    try:
        # Try async directory listing first
        files = await aiofiles.os.listdir(path)
        logger.debug(f"Successfully listed files asynchronously from {path}")
    except ImportError:
        # Fallback if aiofiles is not available
        logger.warning("aiofiles not available, using synchronous directory listing")
        files = os.listdir(path)
    except Exception as e:
        # Fallback for any other errors
        logger.warning(f"Async directory listing failed, falling back to sync: {e}")
        files = os.listdir(path)

    # Filter for Python files and remove .py extension, but skip base_command_cog.py
    py_files = [
        f[:-3] for f in files if f.endswith(".py") and f != "base_command_cog.py"
    ]
    logger.info(f"Found {len(py_files)} Python files in {path}: {py_files}")

    return py_files
