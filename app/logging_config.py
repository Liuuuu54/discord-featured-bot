import logging

import config


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
            logging.StreamHandler() if config.LOG_TO_CONSOLE else logging.NullHandler(),
        ],
    )
