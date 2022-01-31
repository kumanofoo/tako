#!/usr/bin/env python3

from datetime import datetime, timedelta
from unittest.mock import MagicMock
import freezegun
from tako.takomarket import TakoMarket
from tako.takoclient import TakoCommand


DATE_JST = "1970-01-01"
SALES = 500


def mock_get_weather_forecast(_, name, date_jst):
    """Mock get_weather_forecast

    Returns
    -------
    texts : list of str

    Example
    -------
    1970-01-11 Area1010
    Maybe Sunny
    06  12  18
    10% 20% 30%
    """
    texts = []
    texts.append(f"{date_jst} {name}")
    texts.append("Maybe Sunny")
    texts.append("06  12  18")
    texts.append("10% 20% 30%")
    return texts


class DebugMarket:
    """Tako Market Debugger

    Attributes
    ----------
    date_jst : str
        "1970-01-01"
    time_jst : str
        "00:00:00"
    area_code : int
    owners : list
    freezetime : freezegun

    Example
    -------
    owner_num = 5
    debug = DebugMarket(owner_num=owner_num)
    for i in range(10):
        debug.next_day()
        debug.set_quantity([500]*owner_num)
        debug.open()
        debug.close()
    """
    def __init__(self, date_jst=DATE_JST, owner_num=5):
        """Initialize each attributes and database
        """
        self.date_jst = date_jst
        self.time_jst = "00:00:00"
        self.area_code = 1000
        self.owners = []
        self.freezetime = None

        TakoMarket.get_point = MagicMock(
            side_effect=self.mock_get_point)
        TakoCommand.get_weather_forecast = mock_get_weather_forecast

        with freezegun.freeze_time(f"{self.date_jst}T00:00:00+09:00"):
            self.tm = TakoMarket()
            self.tm.set_area()
            for i in range(owner_num):
                owner_id = f"id{i+10000}"
                self.tm.open_account(owner_id, name=f"name{i+10000}")
                self.owners.append(owner_id)

    def mock_get_point(self):
        self.area_code += 1
        return f"Area{self.area_code}"

    def set_quantity(self, quantities=[]):
        """Order tako
        quantities : list
            ordering quantity of each owner
        """
        for n, quantity in enumerate(quantities):
            TakoMarket.set_tako_quantity(
                self.owners[n],
                self.date_jst,
                quantity)

    def next_day(self):
        """Advance time by one day
        """
        dt = datetime.fromisoformat(f"{self.date_jst}T00:00:00+09:00")
        dt = dt + timedelta(days=1)
        self.date_jst = dt.strftime("%Y-%m-%d")

    def open(self, time="09:00"):
        """Open market

        Parameters
        ----------
        time : str
            Opening time
        """
        with freezegun.freeze_time(f"{self.date_jst} {time}:00+09:00"):
            self.tm.cancel_and_refund(self.date_jst)
            self.tm.make_tako(self.date_jst)
            self.tm.set_area()
        self.time_jst = time

    def close(self, time="18:00", sales=SALES):
        """Close market

        Parameters
        ----------
        time : str
            Closing time
        """
        with freezegun.freeze_time(f"{self.date_jst} {time}:00+09:00"):
            self.tm.cancel_and_refund(self.date_jst)
            self.tm.result(self.date_jst, sales)
        self.time_jst = time

    def freeze(self):
        """Freeze time
            Set datetime and stop time to update database.
        """
        if self.freezetime:
            self.melt()

        dt = datetime.fromisoformat(f"{self.date_jst}T{self.time_jst}+09:00")
        dt = dt + timedelta(hours=1)
        self.freezetime = freezegun.freeze_time(dt)
        self.freezetime.start()

    def melt(self):
        """Melt frozen time
        """
        if self.freezetime:
            self.freezetime.stop()
            self.freezetime = None


def debugcmd(command=None):
    owner_num = 5
    debug = DebugMarket(owner_num=owner_num)
    do = [debug.next_day, debug.open, debug.close]
    time = ["Midnight", "Morning", "Evening"]
    do_i = 0
    if command:
        command_ = command[:]

    tc = TakoCommand(debug.owners[0], "cmdtest")
    print(f"ID: {tc.my_id}, Display name: { tc.my_name}")
    while True:
        if command is None:
            cmd = input(f"tako[{tc.max_order_quantity()[0]}]: ")
        else:
            cmd = command_.pop(0)
        if cmd == "do":
            do[do_i]()
            print(time[do_i])
            do_i = (do_i + 1) % len(do)
            continue
        if cmd == "dooo":
            for _ in range(3):
                do[do_i]()
                do_i = (do_i + 1) % len(do)
            print(f"next {time[do_i]}")
            continue
        debug.freeze()
        if not tc.interpret(cmd):
            break
        debug.melt()


def fast_forward():
    owner_num = 5
    debug = DebugMarket(owner_num=owner_num)
    for i in range(10):
        debug.next_day()
        debug.set_quantity([500]*owner_num)
        debug.open()
        debug.close()


if __name__ == "__main__":
    # auto
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
    debugcmd(command)

    # interactive
    # debugcmd()

    # auto fast forwrd
    # fast_forward()
