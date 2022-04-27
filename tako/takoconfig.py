#! /usr/bin/env python3
import os
import logging
from pathlib import Path
TAKO_DB = Path(os.environ.get("TAKO_DB", "tako.db"))

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

TAKO_STORY = """
You have to run a takoyaki's shop and make money.

The cost of takoyaki is 40 yen per piece and the selling price is 50 yen.
The number of takoyaki sold in a day depends on the weather:
about 500 takoyakis sold on a sunny day,
about 300 on a cloudy day and
about 100 on a rainy or snowy day.
So look carefully at the weather forecast for the next day and
make up your mind how many you will make.
Takoyaki does not last long, so all unsold takoyakis are discarded.
The winner is the first person who starts with 5,000 yen and
exceeds 30,000 yen.

The takoyaki market opens at 9:00 a.m. every day.
So you need to decide how many takoyaki to make, and order them by the time.
The market closes at 18:00 p.m. and the sales are calculated.

The place of market is changed every day and the next is announced at 9:00 a.m.
You can decide how many to make to consider weather forecast in the place.
"""


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
    ENV_LOGGING_LEVEL = os.environ.get(envrion)
    if ENV_LOGGING_LEVEL == "info":
        log_level = logging.INFO
        formatter = '%(name)s: %(message)s'
    elif ENV_LOGGING_LEVEL == "debug":
        log_level = logging.DEBUG
        formatter = '%(asctime)s %(name)s[%(lineno)s] ' \
                    '%(levelname)s: %(message)s'
    else:
        log_level = logging.WARNING  # default debug level
        formatter = '%(name)s: %(message)s'
    logging.basicConfig(level=log_level, format=formatter)
    return logger
