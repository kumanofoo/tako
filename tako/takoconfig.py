#! /usr/bin/env python3
import os

TAKO_DB = os.environ.get("TAKO_DB", "tako_storage.db")

COST_PRICE = 40
SELLING_PRICE = 50
SEED_MONEY = 5000
OPENING_TIME = "09:00"
CLOSING_TIME = "18:00"

SUNSHINE_RATIO_CORRECTION_HOUR = 2

MAX_SALES = {
    'sunny': 200,
    'cloudy': 300,
    'rainy': -200,
}
