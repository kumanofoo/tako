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
You will run a takoyaki shop.
You are given 5000 yen at the start.
Its goal is to make 30000 yen faster than other shops.
When someone reaches 30000 yen,
the series of markets are once closed.
And then it is reset to 5000 yen and new market starts.

The cost of one takoyaki is 40 yen and the selling price is 50 yen.
The number of takoyakis sold in a day depends on the weather.
About 500 takoyakis would sell on a sunny day.
About 300 on a cloudy day, and about 100 on a rainy or snowy day.
So you should look carefully at the weather forecast
for the next day before making up your mind
about how many you will make.
Takoyaki does not last long, so all unsold takoyakis are discarded.

The place of the market is changed every day and
the next is announced at 9:00 a.m.
The takoyaki market opens at 9:00 a.m. every day.
By the opening time, you need to decide how many takoyakis to make.
Please remember to check the weather forecast.
It closes at 6:00 p.m. and the sales are calculated.
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
