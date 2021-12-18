#!/usr/bin/env python3

import pytest
import os
import re
from datetime import datetime, timedelta
from tako.takoclient import TakoClient
from tako import takoconfig
from tako.takomarket import TakoMarket

my_id = "MSN-02"
my_name = "ZEONG"


@pytest.mark.freeze_time("1970-01-01")
@pytest.fixture
def db():
    takoconfig.TAKO_DB = "tako_test.db"
    if os.path.exists(takoconfig.TAKO_DB):
        os.remove(takoconfig.TAKO_DB)
    tm = TakoMarket()  # create new database
    tm.set_area()


def test_init(db):
    _ = TakoClient("11111", "")
    assert TakoMarket.get_name("11111") != ""  # at random
    _ = TakoClient("11111", "aaaaa")
    assert TakoMarket.get_name("11111") == "aaaaa"
    _ = TakoClient("11111", "bbbbb")
    assert TakoMarket.get_name("11111") == "bbbbb"
    _ = TakoClient("11111", "")
    assert TakoMarket.get_name("11111") == "bbbbb"


def test_astimezone(db):
    tc = TakoClient(my_id, my_name)
    test_pattern = [
        ((+9, "JST"), "1970-01-01 09:00 JST"),
        ((-5, "EST"), "1969-12-31 19:00 EST"),
    ]
    for (tz, expected) in test_pattern:
        assert tc.astimezone("1970-01-01T00:00:00", tz=tz) == expected
        assert tc.astimezone("1970-01-01 00:00", tz=tz) == expected
    assert tc.astimezone("1970-01-01 00:00") == "1970-01-01 09:00 JST"


def test_ranking(db):
    tc = TakoClient(my_id, my_name)
    for owner in tc.ranking():
        assert owner["name"] == my_name
        assert owner["balance"] == takoconfig.SEED_MONEY


@pytest.mark.freeze_time("1970-01-01")
def test_order_and_latest_transaction(db):
    expected = {
        "owner_id": my_id,
        "name": my_name,
        "balance": takoconfig.SEED_MONEY,
        "date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "quantity_ordered": 0,
        "cost": 0,
        "quantity_in_stock": 0,
        "sales": 0,
        "status": "ordered",
    }
    tc = TakoClient(my_id, my_name)

    quantity, balance = tc.max_order_quantity()
    assert quantity == takoconfig.SEED_MONEY/takoconfig.COST_PRICE
    assert balance == takoconfig.SEED_MONEY
    assert tc.order(quantity) is True
    expected["quantity_ordered"] = quantity
    transaction = tc.latest_transaction()
    for key in transaction.keys():
        if key == "timestamp":
            assert re.match(
                r"\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\d",
                transaction[key])
        else:
            assert transaction[key] == expected[key]

    quantity = quantity*2
    assert tc.order(quantity) is True
    expected["quantity_ordered"] = quantity
    transaction = tc.latest_transaction()
    for key in transaction.keys():
        if key == "timestamp":
            assert re.match(
                r"\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\d",
                transaction[key])
        else:
            assert transaction[key] == expected[key]

    quantity = -1
    assert tc.order(quantity) is True
    expected["quantity_ordered"] = 0
    transaction = tc.latest_transaction()
    for key in transaction.keys():
        if key == "timestamp":
            assert re.match(
                r"\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d\d\d",
                transaction[key])
        else:
            assert transaction[key] == expected[key]
