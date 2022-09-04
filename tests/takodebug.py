#!/usr/bin/env python3

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock
import freezegun
from tako.takomarket import MarketDB
from tako.takoclient import TakoCommand
from tako import takoconfig


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
    """Tako Market for Debug with fast-forward

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
    debug = DebugMarket(owner_num=owner_num, owner_num=owner_num)
    for i in range(10):
        debug.next_day()
        debug.set_quantity([500]*owner_num)
        debug.open()
        debug.close()
    """
    def __init__(self, date_jst=DATE_JST, owner_num=5):
        """Initialize each attributes and database

        Parameters
        ----------
        date_jst : str
            Start datetime.
        owner_num : integer
            Number of owners.
        """
        self.date_jst = date_jst
        self.time_jst = "00:00:00"
        self.area_code = 1000
        self.owners = []
        self.freezetime = None

        MarketDB._get_point = MagicMock(
            side_effect=self.mock_get_point)
        TakoCommand.get_weather_forecast = mock_get_weather_forecast

        with freezegun.freeze_time(f"{self.date_jst}T00:00:00+09:00"):
            with MarketDB() as mdb:
                mdb.create_db()
                mdb.set_area()
                for i in range(owner_num):
                    owner_id = f"id{i+10000}"
                    try:
                        mdb.open_account(owner_id, name=f"name{i+10000}")
                    except sqlite3.IntegrityError:
                        pass
                    self.owners.append(owner_id)

    def mock_get_point(self):
        self.area_code += 1
        return f"Area{self.area_code}"

    def set_quantity(self, quantities=[]):
        """Order tako
        quantities : list
            ordering quantity of each owner
        """
        with MarketDB() as mdb:
            for n, quantity in enumerate(quantities):
                mdb.set_tako_quantity(
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
            with MarketDB() as mdb:
                mdb.cancel_and_refund(self.date_jst)
                mdb.make_tako(self.date_jst)
                mdb.set_area()
        self.time_jst = time

    def close(self, time="18:00", sales=SALES):
        """Close market

        Parameters
        ----------
        time : str
            Closing time
        """
        with freezegun.freeze_time(f"{self.date_jst} {time}:00+09:00"):
            with MarketDB() as mdb:
                mdb.cancel_and_refund(self.date_jst)
                mdb.result(self.date_jst, sales)
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


class DebugClient:
    """Command client for debug

    Attributes
    ----------
    market : object
        DebugMarket instance.
    do : list
        DebugMarket methods.
    """
    def __init__(self, owners=5):
        """Initialize each attributes

        Parameters
        ----------
        owners : integer
            Number of owners.
        """
        self.commands = {
            "help": self.help,
            "?": self.help,
            "do": self.do,
            "dooo": self.dooo,
            "list": self.list_owners,
            "owner": self.change_current_owner,
        }
        self.market = DebugMarket(owner_num=owners)
        self.task = [self.market.next_day, self.market.open, self.market.close]
        self.now = ["Midnight", "Morning", "Evening"]
        self.task_index = 0
        self.owners = [TakoCommand(o, None) for o in self.market.owners]
        self.owner = self.owners[0]

    def interpret(self, commands=[]):
        commands_ = commands[:]
        while True:
            if len(commands) == 0:
                cmd = input(f"{self.owner.my_name}"
                            f"[{self.owner.max_order_quantity()[0]}]"
                            f"[{self.now[self.task_index]}]: ")
            else:
                if len(commands_) == 0:
                    break
                cmd = commands_.pop(0)
            if not self.run(cmd):
                break

    def run(self, command):
        """Run command

        Parameters
        ----------
        command : str

        Returns
        -------
        continue : bool
            Flase if command is 'quit'.
        """
        cmd = command.split()
        if len(cmd) > 0:
            f = self.commands.get(cmd[0])
        else:
            f = None
        if f:
            f(cmd[1:])
        else:
            self.market.freeze()
            ret = self.owner.interpret(command)
            self.market.melt()
            return ret
        return True

    def do(self, args=[]):
        """Do task of market

        Parameters
        ----------
        args : list
        """
        if len(args) > 0:
            return
        self.task[self.task_index]()
        self.task_index = (self.task_index + 1) % len(self.task)

    def dooo(self, args=[]):
        """Do a series of tasks

        Parameters
        ----------
        args : list
        """
        if len(args) > 0:
            return
        for _ in range(len(self.task)):
            self.do()
        print(f"next {self.now[self.task_index]}")

    def list_owners(self, args=[]):
        """List owners

        Parameters
        ----------
        args : list
        """
        if len(args) > 0:
            return
        for i, o in enumerate(self.owners):
            if self.owner == o:
                print("*", end="")
            else:
                print(" ", end="")
            print(f"{i}: {o.my_id} {o.my_name}")

    def change_current_owner(self, args=[]):
        """Change current owner

        Parameters
        ----------
        args : list
            If args is empty, show current owner.
            If args is a integer, change current owner.
        """
        if len(args) == 0:
            n = self.owners.index(self.owner)
            print(f"{n}: {self.owner.my_name}")
        elif len(args) == 1:
            try:
                n = int(args[0])
            except ValueError:
                return
            if n < 0 or n >= len(self.owners):
                return
            self.owner = self.owners[n]
        else:
            print("bad number")

    def help(self, args=None):
        """Display help

        Parameters
        ----------
        args : list
        """
        if len(args) > 0:
            return
        print("Debug Command: ")
        print("  owner : Change current owner.")
        print("  list : List owners.")
        print("  do : Advance time.")
        print("  dooo : Advance time 1 day.")
        print("Current Owner Command: ")
        self.owner.interpret("help")


def fast_forward():
    owner_num = 5
    debug = DebugMarket(owner_num=owner_num)
    for i in range(10):
        debug.next_day()
        debug.set_quantity([500]*owner_num)
        debug.open()
        debug.close()


def auto_input():
    commands = [
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
    dc = DebugClient()
    dc.interpret(commands=commands)


if __name__ == "__main__":
    import argparse
    global log
    log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "Virtual Tako")

    parser = argparse.ArgumentParser(description="Takoyaki Virtual Market")
    parser.add_argument("-o", "--owners",
                        type=int,
                        default=5,
                        help="Number of owners. Default is 5.")
    parser.add_argument("-d", "--database",
                        help="Takoyaki DB file.")
    parser.add_argument("-c", "--commands",
                        help="Commands file with one command per line.")
    args = parser.parse_args()
    if args.database:
        takoconfig.TAKO_DB = Path(args.database)
    commands = []
    if args.commands:
        try:
            f = open(args.commands)
        except FileNotFoundError as e:
            print(f"can't read {args.commands}: {e}")
            exit(1)
        else:
            with open(args.commands) as f:
                commands = f.read().split('\n')
    dc = DebugClient(owners=args.owners)
    dc.interpret(commands)

    # auto fast forwrd
    # fast_forward()

    # auto input
    # auto_input()
