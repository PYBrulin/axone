import logging
import sys


class CustomFormatter(logging.Formatter):
    fmt = "[%(levelname)4.4s/%(processName)s(%(process)d)] %(asctime)s %(filename)s:%(lineno)d - %(message)s"

    def format(self, record) -> str:
        formatter = logging.Formatter(CustomFormatter.fmt)
        return formatter.format(record)


class ColoredFormatter(CustomFormatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    magenta = "\x1b[35;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    FORMATS = {
        logging.DEBUG: magenta + CustomFormatter.fmt + reset,
        logging.INFO: grey + CustomFormatter.fmt + reset,
        logging.WARNING: yellow + CustomFormatter.fmt + reset,
        logging.ERROR: red + CustomFormatter.fmt + reset,
        logging.CRITICAL: bold_red + CustomFormatter.fmt + reset,
    }

    def format(self, record) -> str:
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
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
    colored_formatter = ColoredFormatter()
    stream_handler.setFormatter(colored_formatter)

    # Add handler to logger
    main_logger.handlers = []  # Remove initial handlers
    main_logger.addHandler(stream_handler)

    def exception_hook(exc_type, exc_value, exc_traceback) -> None:
        """Allows to catch all uncaught exception in the log"""
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = exception_hook
