#! /usr/bin/env python3
import os
import logging
from pathlib import Path
TAKO_DB = Path(os.environ.get("TAKO_DB", "tako_storage.db"))

COST_PRICE = 40
SELLING_PRICE = 50
SEED_MONEY = 5000
TARGET = 30000
OPENING_TIME = "09:00"
CLOSING_TIME = "18:00"

SUNSHINE_RATIO_CORRECTION_HOUR = 2

MAX_SALES = {
    'sunny': 200,
    'cloudy': 300,
    'rainy': -200,
}

TAKOBOT = {
    "ID": "MS-06S",
    "name": "Char",
}


def set_logging_level(envrion, name):
    """Set the threshold for logger to level and the format

    Parameters
    ----------
    envrion : str
        environment variable set level.
        'notest', 'debug', 'info', 'warning', 'error' or 'critical'.
    name : str
        logger name.

    Returns
    -------
    logger
    """
    logger = logging.getLogger(name)
    ENV_DEBUG = os.environ.get(envrion)
    if ENV_DEBUG == "info":
        log_level = logging.INFO
        formatter = '%(name)s: %(message)s'
    elif ENV_DEBUG == "debug":
        log_level = logging.DEBUG
        formatter = '%(asctime)s %(name)s[%(lineno)s] ' \
                    '%(levelname)s: %(message)s'
    else:
        log_level = logging.WARNING  # default debug level
        formatter = '%(name)s: %(message)s'
    logging.basicConfig(level=log_level, format=formatter)
    return logger
