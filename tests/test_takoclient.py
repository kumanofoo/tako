#!/usr/bin/env python3

import pytest
import os
import re
import sys
from pathlib import Path
from io import StringIO
from datetime import datetime, timedelta
from tako.takoclient import TakoClient
from tako import takoconfig
from tako.takomarket import MarketDB
from tests.takodebug import DebugClient

my_id = "MSN-02"
my_name = "ZEONG"


@pytest.mark.freeze_time("1970-01-01")
@pytest.fixture
def db():
    takoconfig.TAKO_DB = Path("test_takoclient.db")
    if os.path.exists(takoconfig.TAKO_DB):
        os.remove(takoconfig.TAKO_DB)
    with MarketDB() as mdb:
        mdb.create_db()
        mdb.set_area()
    yield
    os.remove(takoconfig.TAKO_DB)
    MarketDB.clear_context()


def test_init(db):
    _ = TakoClient("11111", "")
    with MarketDB() as mdb:
        assert mdb.get_name("11111")[1] != ""  # at random
    _ = TakoClient("11111", "aaaaa")
    with MarketDB() as mdb:
        assert mdb.get_name("11111")[1] == "aaaaa"
    _ = TakoClient("11111", "bbbbb")
    with MarketDB() as mdb:
        assert mdb.get_name("11111")[1] == "bbbbb"
    _ = TakoClient("11111", "")
    with MarketDB() as mdb:
        assert mdb.get_name("11111")[1] == "bbbbb"


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
        "area": "apple",
        "max_sales": 0,
        "weather": ""
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
        elif key == "area":
            assert len(transaction[key]) > 0
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
        elif key == "area":
            assert len(transaction[key]) > 0
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
        elif key == "area":
            assert len(transaction[key]) > 0
        else:
            assert transaction[key] == expected[key]


def test_takocommand():
    takoconfig.TAKO_DB = Path("test_takoclient.db")
    if os.path.exists(takoconfig.TAKO_DB):
        os.remove(takoconfig.TAKO_DB)

    with MarketDB() as mdb:
        mdb.create_db()

    command = [
        "125", "dooo",
        "156", "dooo",
        "195", "dooo",
        "244", "dooo",
        "305", "dooo",
        "381", "dooo",
        "476", "dooo",
        "500", "dooo",
        "500", "dooo",
        "",
        "125", "dooo",
        "",
        "quit",
    ]
    expected = r"""Ordered 125 tako
next Midnight
Ordered 156 tako
next Midnight
Ordered 195 tako
next Midnight
Ordered 244 tako
next Midnight
Ordered 305 tako
next Midnight
Ordered 381 tako
next Midnight
Ordered 476 tako
next Midnight
Ordered 500 tako
next Midnight
Ordered 500 tako
next Midnight
name10000 🐙
Balance: 5000 JPY at 1970-01-01 12:00 JST
This season is over. And next season has begun.
You were 1st🐙 with 33820 JPY.

name10000 : 33820 JPY
🐙

The following is the close to the target.
name10001 : 5000 JPY
name10002 : 5000 JPY
name10003 : 5000 JPY
name10004 : 5000 JPY

Status: closed '1970-01-10' with 25000 JPY sales at 1970-01-01 12:00 JST
        You sold 500 tako. (Ordered: 500, In stock: 500, Max: 500)

Top 3 owners
name10000: 5000 JPY
name10001: 5000 JPY
name10002: 5000 JPY

Next: Area1010
Open: 1970-01-11 09:00 JST
Close: 1970-01-11 18:00 JST

1970-01-11 Area1010
Maybe Sunny
06  12  18
10% 20% 30%
Ordered 125 tako
next Midnight
name10000 🐙
Balance: 6250 JPY at 1970-01-01 12:00 JST
Status: closed '1970-01-11' with 6250 JPY sales at 1970-01-01 12:00 JST
        You sold 125 tako. (Ordered: 125, In stock: 125, Max: 500)

Top 3 owners
name10000: 6250 JPY
name10001: 5000 JPY
name10002: 5000 JPY

Next: Area1011
Open: 1970-01-12 09:00 JST
Close: 1970-01-12 18:00 JST

1970-01-12 Area1011
Maybe Sunny
06  12  18
10% 20% 30%
"""
    dc = DebugClient(owners=5)
    io = StringIO()
    sys.stdout = io
    dc.interpret(command)
    sys.stdout = sys.__stdout__
    expected_list = expected.split("\n")
    actual_list = io.getvalue().split("\n")
    for a, e in zip(actual_list, expected_list):
        if a.startswith("Balance:") or a.startswith("Status:"):
            # except timestamp
            a = a.split(" at ")[0]
            e = e.split(" at ")[0]
        assert a == e, f"\n{a}\n{e}"
    os.remove(takoconfig.TAKO_DB)
