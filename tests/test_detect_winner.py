#!/usr/bin/env python3

from pathlib import Path
import os
from tako.takomarket import TakoMarket
from tako import takoconfig
from tako.takotime import JST
import freezegun
from datetime import datetime, timedelta


DATABASE = "test.db"
DATE_JST = "1970-01-01"
OWNER_NUM = 5
POINTS_SIDE_EFFECT = [
    "Zero", "One", "Two", "Three", "Four",
    "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "Eleven", "Twelve", "Ichi", "Ni", "San", "Shi",
    "Go", "Roku", "Shichi", "Hachi", "Kyu", "Ju",
]
MAX_SALES = takoconfig.MAX_SALES["sunny"] + takoconfig.MAX_SALES["cloudy"]
MIN_SALES = takoconfig.MAX_SALES["rainy"] + takoconfig.MAX_SALES["cloudy"]


def set_transaction(tm, num=5):
    owner = []
    for i in range(1000, 1000+num):
        owner_id = f"id{i}"
        name = f"name{i}"
        tm.open_account(owner_id, name)
        owner.append({
            "id": owner_id,
            "name": name,
            "balance": takoconfig.SEED_MONEY})
    tm.set_area()

    return owner


def expected_sales(balance, order_quantity):
    q = min(int(balance/takoconfig.COST_PRICE), order_quantity)
    q = min(MAX_SALES, q)
    balance += q*(takoconfig.SELLING_PRICE - takoconfig.COST_PRICE)
    return balance


def test_detect_winner(mocker):
    mocker.patch("tako.takomarket.TakoMarket.get_point",
                 side_effect=POINTS_SIDE_EFFECT)

    takoconfig.TAKO_DB = Path(DATABASE)
    if Path.exists(takoconfig.TAKO_DB):
        os.remove(takoconfig.TAKO_DB)

    with freezegun.freeze_time(f"{DATE_JST} 00:00:00+09:00") as freezer:
        tm = TakoMarket()
        owner = set_transaction(tm, num=OWNER_NUM)
        now = datetime.now(JST) + timedelta(days=1)
        freezer.move_to(now)

        assert len(tm.get_records()) == 0

        expected_max_balance = takoconfig.SEED_MONEY
        for i in range(10):
            # set quantity
            area = tm.get_next_area()
            print(area)
            q = MAX_SALES
            for o in owner:
                TakoMarket.set_tako_quantity(o["id"], area["date"], q)
                o["balance"] = expected_sales(o["balance"], q)
                q -= int((MAX_SALES - MIN_SALES)/(OWNER_NUM-1))
            expected_max_balance = max([o["balance"] for o in owner])

            # moring
            now = datetime.now(JST) + timedelta(hours=8)
            freezer.move_to(now)
            event = tm.get_next_event()
            assert event["date"] is not None
            tm.cancel_and_refund(event["date"])
            tm.make_tako(event["date"])
            tm.set_area()

            # evening
            now = datetime.now(JST) + timedelta(hours=8)
            freezer.move_to(now)
            tm.cancel_and_refund(event["date"])
            winner_exists = tm.result(event["date"], MAX_SALES)
            is_restart = []
            for o in owner:
                s = tm.get_transaction(o["id"], event["date"])[0]["status"]
                if s == "closed_and_restart":
                    is_restart.append(True)
                else:
                    is_restart.append(False)

            if expected_max_balance >= takoconfig.TARGET:
                assert winner_exists is True
                assert all(is_restart) is True
                winners = [
                    o["id"] for o in owner if o["balance"] >= takoconfig.TARGET
                ]
                records = tm.get_records(date_jst=event["date"])
                key = list(records.keys())[0]
                assert len(records[key]) == len(winners)

                # restart market
                for o in owner:
                    o["balance"] = takoconfig.SEED_MONEY
            else:
                assert winner_exists is False
                assert any(is_restart) is False
            # midnight
            now = datetime.now(JST) + timedelta(hours=8)
            freezer.move_to(now)
