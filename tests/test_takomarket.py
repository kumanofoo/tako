import os
from datetime import datetime, timedelta, timezone
import time
import logging
import freezegun
import pytest
import tempfile
from pathlib import Path
from tako.takomarket import TakoMarket
from tako.takomarket import TakoMarketNoAccountError, TakoMarketError
from tako import takoconfig

log = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))


class TakoMarketTest:
    def __init__(self, market, number_of_accounts):
        self.mk = market
        self.owner = []
        self.create_owner(number_of_accounts)
        self.pre_tra = {}

    def show_transaction(self):
        width = {}
        align = {}
        self.transaction_keys = {}
        self.transaction_values = ""

        tra = {}
        for o in self.owner:
            tra[o['owner_id']] = self.mk.get_transaction(o['owner_id'])
            if not self.pre_tra.get(o['owner_id']):
                self.pre_tra[o['owner_id']] = tra[o['owner_id']]

        for o in self.owner:
            for t in tra[o['owner_id']]:
                for k in t.keys():
                    if len(k) > len(str(t[k])):
                        w = len(k)
                    else:
                        w = len(str(t[k]))

                    if width.get(k, 0) < w:
                        width[k] = w
                    if type(t[k]) is int:
                        align[k] = '>'
                    else:
                        align[k] = '<'
        header = ""
        values_fmt = ""
        for o in self.owner:
            for t in tra[o['owner_id']]:
                if len(header) == 0:
                    for k in t.keys():
                        fmt = "{:" + align[k] + str(width[k]) + "}  "
                        header += fmt.format(k)
                        values_fmt += fmt
                    print(header)

                p = None
                for pre in self.pre_tra[o['owner_id']]:
                    if pre['date'] == t['date']:
                        p = pre
                        break
                if p:
                    color_fmt = ""
                    for k in t.keys():
                        fmt = "{:" + align[k] + str(width[k]) + "}  "
                        if t[k] != p[k]:
                            fmt = TextColor.GREEN + fmt + TextColor.END
                        color_fmt += fmt
                    print(color_fmt.format(*list(t.values())))
                else:
                    print(
                        TextColor.YELLOW
                        + values_fmt.format(*list(t.values()))
                        + TextColor.END)

        self.pre_tra = tra

    def create_owner(self, number_of_accounts):
        step = self.mk.seed_money/self.mk.cost_price/number_of_accounts
        for i in range(0, number_of_accounts):
            o = {}
            o['owner_id'] = "id%06d" % i
            o['name'] = "name%02X" % i
            o['quantity'] = step*(i+1)
            self.owner.append(o)

    def get_name(self):
        test_owner_id = "xxxyyyzzz"
        c = self.mk.condition(test_owner_id)
        assert c is None
        try:
            _ = self.mk.get_name(test_owner_id)
        except TakoMarketNoAccountError:
            pass

        for o in self.owner:
            self.mk.open_account(o['owner_id'], name=o['name'])
            actual = self.mk.condition(o['owner_id'])
            assert o['owner_id'] == actual['owner_id']
            assert self.mk.seed_money == actual['balance']

        for o in self.owner:
            actual = self.mk.get_name(o['owner_id'])[0]
            assert o['owner_id'] == actual
            actual = self.mk.get_name(o['owner_id'])[1]
            assert o['name'] == actual
            actual = self.mk.get_name(o['owner_id'])[2]
            assert 0 == actual

    def change_name(self):
        test_set = [
            ("apple", "red", "green"),
            ("banana", None, "yellow"),
        ]
        for owner_id, name1, name2 in test_set:
            c = self.mk.condition(owner_id)
            assert c is None
            with pytest.raises(TakoMarketNoAccountError):
                _ = self.mk.get_name(owner_id)
            self.mk.open_account(owner_id, name=name1)
            self.mk.change_name(owner_id, name=name2)
            actual = self.mk.get_name(owner_id)[1]
            assert name2 == actual

        test_owner_id = "cherry"
        c = self.mk.condition(test_owner_id)
        assert c is None
        with pytest.raises(TakoMarketNoAccountError):
            _ = self.mk.get_name(test_owner_id)
        self.mk.open_account(test_owner_id)
        with pytest.raises(TakoMarketError):
            self.mk.change_name(test_owner_id, name=None)

    def set_tako_quantity(self, date):
        for o in self.owner:
            balance = self.mk.condition(o['owner_id'])['balance']
            self.mk.set_tako_quantity(o['owner_id'], date, o['quantity'])
            t = self.mk.get_transaction(o['owner_id'], date)
            assert len(t) == 1, f"expected: 1, actual: {len(t)}"
            actual = t[0]
            assert o['owner_id'] == actual['owner_id']
            assert balance == actual['balance']
            assert date == actual['date']
            assert o['quantity'] == actual['quantity_ordered']
            assert 0 == actual['cost']
            assert 0 == actual['quantity_in_stock']
            assert 0 == actual['sales']
            assert "ordered" == actual['status']

    def make_tako(self, date):
        balances = dict([
            (o['owner_id'], self.mk.condition(o['owner_id'])['balance'])
            for o in self.owner
        ])
        self.mk.make_tako(date)
        for o in self.owner:
            t = self.mk.get_transaction(o['owner_id'], date)
            assert len(t) == 1, f"expected: 1, actual: {len(t)}"
            actual = t[0]
            assert o['owner_id'] == actual['owner_id']
            expected_cost = min(
                int(self.mk.seed_money/self.mk.cost_price),
                o['quantity'])*self.mk.cost_price
            assert balances[o['owner_id']] - expected_cost == actual['balance']
            assert date == actual['date']
            assert o['quantity'] == actual['quantity_ordered']
            assert expected_cost == actual['cost']
            assert actual['quantity_in_stock'] == min(
                int(self.mk.seed_money/self.mk.cost_price),
                o['quantity'])
            assert 0 == actual['sales']
            assert "in_stock" == actual['status']

    def result(self, date, sales):
        balances = {}
        expected_status = {}
        for o in self.owner:
            c = self.mk.condition(o['owner_id'])
            balances[o['owner_id']] = c['balance']

            t = self.mk.get_transaction(o['owner_id'], date)
            assert len(t) == 1
            expected_status[o['owner_id']] = "unknown"
            if t[0]['status'] == 'ordered':
                expected_status[o['owner_id']] = "canceled"
            if t[0]['status'] == 'in_stock':
                expected_status[o['owner_id']] = "closed"

        self.mk.result(date, sales)
        for o in self.owner:
            t = self.mk.get_transaction(o['owner_id'], date)
            assert len(t) == 1, f"expected: 1, actual: {len(t)}"
            actual = t[0]
            assert actual['owner_id'] == o['owner_id']
            stock = actual['quantity_in_stock']
            expect = (
                    balances[o['owner_id']]
                    + min(sales, stock)*self.mk.selling_price
                )
            assert expect == actual['balance']
            assert date == actual['date']
            assert o['quantity'] == actual['quantity_ordered']
            assert stock*self.mk.cost_price == actual['cost']
            assert min(sales, stock)*self.mk.selling_price == actual['sales']
            assert expected_status[o['owner_id']] == actual['status']

    def cancel_and_refund(self, date):
        owner_with_cancel = []
        for o in self.owner:
            transactions = self.mk.get_transaction(o['owner_id'])
            if len(transactions) == 0:
                continue

            for t in transactions:
                if t['date'] < date and t['status'] in ['in_stock', 'ordered']:
                    owner_with_cancel.append((
                        o['owner_id'],
                        t['balance'],
                        t['date'],
                        t['cost']))
        self.mk.cancel_and_refund(date)
        for o in owner_with_cancel:
            transactions = self.mk.get_transaction(o[0], o[2])
            assert o[1] + o[3] == transactions[0]['balance']
            assert 'canceled' == transactions[0]['status']

    def schedule(self, schedules):
        start_date, timeline = schedules[0]
        start_time, _, _, _ = timeline[0]
        start_datetime_jst_str = f"{start_date} {start_time}+09:00"
        with freezegun.freeze_time(start_datetime_jst_str) as freezer:
            #
            # control time
            for schedule in schedules:
                date, timeline = schedule
                log.debug(
                    TextColor.REVERSE +
                    f"=============== Today is {date} ===============" +
                    TextColor.END)
                for t in timeline:
                    now = datetime.fromisoformat(
                        f"{date} {t[0]}+09:00")
                    freezer.move_to(now)
                    log.debug(f"---------- {now} {t[3]} ----------")
                    if t[3] == "initialize":
                        self.mk.run_market()
                        time.sleep(2)
                        continue
                    if t[3] == "shutdown":
                        self.mk.stop_market()
                        time.sleep(2)
                        continue
                    if t[3] == "order":
                        next_area = self.mk.get_next_area()
                        assert next_area["date"] is not None

                        log.debug(
                            "next market is in " +
                            next_area["area"] +
                            " at " +
                            next_area["date"])
                        self.set_tako_quantity(next_area["date"])
                        self.show_transaction()

                    time.sleep(2)
                    if not t[1]:
                        continue

                    end = datetime.fromisoformat(
                        f"{date} {t[1]}+09:00")
                    dt = timedelta(seconds=t[2])
                    while now < end:
                        now += dt
                        freezer.move_to(now)
                        log.debug(f"move to {now}")
                        time.sleep(2)
                    if t[3] in ("open", "close"):
                        self.show_transaction()
            self.mk.stop_market()


class TextColor:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    END = "\033[0m"
    BOLD = "\033[1m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    INVISIBLE = "\033[08m"
    REVERSE = "\033[07m"


@pytest.fixture
def tmpdb():
    global tempdir
    tempdir = tempfile.TemporaryDirectory()
    takoconfig.TAKO_DB = str(Path(tempdir.name) / "tako_storage.db")


def test_get_area_history(tmpdb):
    date_pattern = [
        "1971-01-01",
        "1970-02-02",
        "1970-02-01",
        "1971-02-02",
        "1970-01-01",
    ]
    tm = TakoMarket()

    area_history = tm.get_area_history()
    assert area_history is None

    for d in date_pattern:
        tm.set_area(d)
    area_history = tm.get_area_history()
    assert len(area_history) == len(date_pattern)
    for h, d in zip(area_history, sorted(date_pattern, reverse=True)):
        assert h["date"] == d, f"{area_history}\n{date_pattern}"


get_point_side_effect = [
    "Zero", "One", "Two", "Three", "Four",
    "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "Eleven", "Twelve", "Ichi", "Ni", "San", "Shi",
    "Go", "Roku", "Shichi", "Hachi", "Kyu", "Ju",
]

weather_side_effect = [
     {
         "title": "weather news one",
         "sunshine_hour": 6.5,
         "rainfall_mm": 10,
         "day_length_hour": 13.1,
         "weather": "cloudy",
     },
     {
         "title": "weather news two",
         "sunshine_hour": 0.5,
         "rainfall_mm": 30,
         "day_length_hour": 10.2,
         "weather": "Rainy",
     },
     {
         "title": "weather news three",
         "sunshine_hour": 8.5,
         "rainfall_mm": 0,
         "day_length_hour": 9.2,
         "weather": "Sunny",
     },
]
weather_side_effect.extend([
    {
         "title": "weather news four",
         "sunshine_hour": 8.5,
         "rainfall_mm": 0,
         "day_length_hour": 9.2,
         "weather": "Sunny",
     },
]*30)


def test_takomarket(mocker):
    mocker.patch("tako.takomarket.TakoMarket.get_point",
                 side_effect=get_point_side_effect)
    mocker.patch("tako.takomarket.TakoMarket.weather",
                 side_effect=weather_side_effect)
    logging.basicConfig(level=logging.DEBUG)

    number_of_accounts = 5
    cases = [
        {
            "title": "birthday",
            "date": "2019-08-06",
            "open_time": "2019-08-06T09:00:00+09:00",
            "closed_time": "2019-08-06T18:00:00+09:00",
            "quantity_of_sales": 100,
            "making": True,
            "selling": True,
            "schedule": False,
        },
        {
            "title": "blackout",
            "date": "2019-09-06",
            "open_time": "2019-09-06T09:00:00+09:00",
            "closed_time": "2019-09-06T18:00:00+09:00",
            "quantity_of_sales": 100,
            "making": True,
            "selling": False,
            "schedule": False,
        },
        {
            "title": "oversleep",
            "date": "2020-02-08",
            "open_time": "2020-02-08T09:00:00+09:00",
            "closed_time": "2020-02-08T18:00:00+09:00",
            "quantity_of_sales": 150,
            "making": False,
            "selling": True,
            "schedule": False,
        },
        {
            "title": "lockdown",
            "date": "2021-09-05",
            "open_time": "2021-10-05T09:00:00+09:00",
            "closed_time": "2021-10-05T18:00:00+09:00",
            "quantity_of_sales": 200,
            "making": False,
            "selling": False,
            "schedule": False,
        }]

    schedules_jst = [
        ("2021-10-01", [
            ("00:00:00", None, None, "initialize"),
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("10:00:00", None, None, None),
            ("17:59:00", "18:01:00", 20, "close"),
            ]),
        ("2021-10-02", [
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("10:00:00", None, None, None),
            ("17:59:00", "18:01:00", 20, "close"),
            ]),
        ("2021-10-03", [
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("10:00:00", None, None, "order"),
            ("17:59:00", "18:01:00", 20, "close"),
            ]),
        ("2021-10-04", [
            ("08:00:00", None, None, "order"),
            ("08:05:00", None, None, "shutdown"),
            ]),
        ("2021-10-05", [
            ("07:00:00", None, None, "initialize"),
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("10:00:00", None, None, None),
            ("17:59:00", "18:01:00", 20, "close"),
            ]),
        ("2021-10-06", [
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("10:00:00", None, None, "shutdown"),
            ("23:00:00", None, None, "initialize"),
            ]),
        ("2021-10-07", [
            ("08:00:00", None, None, "order"),
            ("08:59:00", "09:01:00", 20, "open"),
            ("17:59:00", "18:01:00", 20, "close"),
            ]),
    ]

    if os.path.exists(takoconfig.TAKO_DB):
        os.remove(takoconfig.TAKO_DB)

    s = TakoMarket()
    print(f"cost price: {s.cost_price}")
    print(f"selling price: {s.selling_price}")
    print(f"seed_money: {s.seed_money}")

    mktest = TakoMarketTest(s, number_of_accounts)
    print("\n# Test get_name")
    mktest.get_name()
    mktest.change_name()

    for case in cases:
        s.set_area(date=case['date'])
        print("get_area:", s.get_area())
        print(case['date'])

        print(f"\n# Case '{case['title']}'")
        print(f"\n## Cancel and refund({case['date']})")
        mktest.cancel_and_refund(case['date'])
        mktest.show_transaction()
        print("get_area:", s.get_area(case['date']))

        print(f"\n## set_tako_quantity({case['date']})")
        mktest.set_tako_quantity(case['date'])
        mktest.show_transaction()
        print("get_area:", s.get_area(case['date']))

        if case['making']:
            print(f"\n## Cancel and refund({case['date']})")
            mktest.cancel_and_refund(case['date'])
            mktest.show_transaction()

            print(f"\n## make_tako({case['date']})")
            mktest.make_tako(case['date'])
            mktest.show_transaction()
        else:
            print("\n## skip making tako")

        print("get_area:", s.get_area(case['date']))

        if case['selling']:
            print(f"\n## Cancel and refund({case['date']})")
            mktest.cancel_and_refund(case['date'])
            mktest.show_transaction()

            print(f"\n## sell_tako({case['date']},"
                  f"{case['quantity_of_sales']})")
            mktest.result(case['date'], case['quantity_of_sales'])
            mktest.show_transaction()
        else:
            print("\n## skip selling tako")

        print("get_area:", s.get_area(case['date']))

    print("\n# Test schedule")
    mktest.schedule(schedules_jst)


if __name__ == "__main__":
    test_takomarket()
