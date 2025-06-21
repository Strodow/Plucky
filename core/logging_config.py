import logging
import sys

class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    cyan = "\x1b[96;20m"
    reset = "\x1b[0m"
    # Include filename and lineno for better debugging context
    log_format_base = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: cyan + log_format_base + reset,
        logging.INFO: grey + log_format_base + reset,
        logging.WARNING: yellow + log_format_base + reset,
        logging.ERROR: red + log_format_base + reset,
        logging.CRITICAL: bold_red + log_format_base + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logging(level=logging.DEBUG):
    """
    Configures the root logger with a custom colored formatter.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level) # Set overall logging level

    # Clear any existing handlers (e.g., from default basicConfig calls in other modules)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create a console handler and set the custom formatter
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level) # Set handler level
    ch.setFormatter(CustomFormatter())

    # Add the new console handler to the root logger
    root_logger.addHandler(ch)