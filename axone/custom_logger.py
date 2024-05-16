import logging
import sys


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    magenta = "\x1b[35;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "[%(levelname)1.1s] %(asctime)s %(filename)s:%(lineno)d - %(message)s"
    datefmt = '%H:%M:%S'

    FORMATS = {
        logging.DEBUG: magenta + fmt + reset,
        logging.INFO: grey + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset,
    }

    def format(self, record) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt=self.datefmt)
        return formatter.format(record)


def setup_logger(**kwargs) -> None:
    """Set up the logging."""
    # Set up the main logger
    logging_level = logging.INFO if not kwargs.get("debug", False) else logging.DEBUG
    main_logger = logging.getLogger()
    main_logger.setLevel(logging_level)

    # Set up the filelock logger
    logging.getLogger("filelock").setLevel(logging.INFO)

    # Set up a stream handler to log to the console
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging_level)
    formatter = CustomFormatter()
    stream_handler.setFormatter(formatter)

    # Add handler to logger
    main_logger.handlers = []  # Remove initial handlers
    main_logger.addHandler(stream_handler)

    def exception_hook(exc_type, exc_value, exc_traceback) -> None:
        """Allows to catch all uncaught exception in the log"""
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = exception_hook
