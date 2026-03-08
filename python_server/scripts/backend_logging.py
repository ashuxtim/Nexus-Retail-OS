import logging
import os
import traceback


def get_logger(name):
    import sys
    # Determine log path
    if "NEXUS_USER_DATA" in os.environ:
        _base = os.environ["NEXUS_USER_DATA"]
    elif sys.platform == "win32":
        _base = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
    else:
        _base = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")
        
    log_dir = os.path.join(_base, "logs")

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "backend_errors.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.ERROR)

    # Avoid duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        # Fixed syntax here: removed citation artifacts
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_critical_error(logger, error, context=""):
    """Captures full traceback for Data Science debugging."""
    error_msg = f"Context: {context} | Error: {str(error)}\n{traceback.format_exc()}"
    logger.error(error_msg)
