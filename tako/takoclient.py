#! /usr/bin/env python3
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
import argparse
from tako.takomarket import TakoMarket
from tako import jma, takoconfig

log = logging.getLogger(__name__)

my_id = "RB-79"
my_name = "Ball"


class TakoClient:
    """Tako user library

    Attributes
    ----------
    my_id : str
        The owner ID.
    my_name : str
        The nickname of owner.
    """
    DOW_JA = ["日曜日", "月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日"]

    def __init__(self, my_id, my_name):
        self.my_id = my_id
        self.my_name = my_name
        """
        ---------------------------------------------
                    |   ID exists   |   not exists
        ------------+---------------+----------------
         name exist | change_name() | open_account()
        ------------+---------------+----------------
            None    | do nothing    | open_account()
        ---------------------------------------------
        """
        try:
            TakoMarket.open_account(self.my_id, self.my_name)
            log.debug(f"Create new account '{self.my_id}'.")
        except sqlite3.IntegrityError:
            # ID already exists
            if self.my_name:
                TakoMarket.change_name(self.my_id, self.my_name)
                log.debug(f"{self.my_id} already exists")

    def astimezone(self, datetime_utc, tz=(+9, "JST")):
        """Convert datetime as UTC to string with timezone

        Parameters
        ----------
        datetime_utc : str or datetime
            ISO format string or datetime object.
        tz : (int, str)
            The timezone and the name of timezone.

        Returns
        -------
        datetime : str
        """
        if type(datetime_utc) == str:
            ts_utc_native = datetime.fromisoformat(datetime_utc)
        else:
            ts_utc_native = datetime_utc
        ts_utc_aware = ts_utc_native.replace(tzinfo=timezone.utc)
        ts_tz = ts_utc_aware.astimezone(timezone(timedelta(hours=tz[0])))
        return ts_tz.strftime(f"%Y-%m-%d %H:%M {tz[1]}")

    def max_order_quantity(self):
        """Calculate maximum quantity to order.

        Returns
        -------
        (quantity, balance) : (int, int)
        """
        condition = TakoMarket.condition(self.my_id)
        balance = None
        if condition:
            balance = condition["balance"]
            quantity = int(balance/takoconfig.COST_PRICE)
        return (quantity, balance)

    def ranking(self):
        """Get the ranking of all owners.

        Returns
        -------
        conditions : [{"name": str, "balance": int},...]
            The name is owner's nickname.
        """
        condition_all = sorted(
            TakoMarket.condition_all(),
            key=lambda x: x['balance'],
            reverse=True
        )
        return condition_all

    def get_forecast_in_next_area(self):
        """Get forecast in next area

        Returns
        -------
        forecast : dict
            {
                "reportDatetime": datetime as UTC
                "area_name": str
                "weather": dict
                    {
                        "datetime": datetime
                        "text": str
                            The weather summary
                    }
                "pops": list of tupple (str, str)
                      [(time, Probability of Precipitation),...]
            }
        """
        area = TakoMarket.get_next_area()
        if not area["date"]:
            return None

        meta = jma.PointMeta.get_point_meta(area["area"])
        forecast = jma.Forecast.get_forecast(meta['class10s'])
        return (forecast)

    def latest_transaction(self):
        """Get latest transaction.

        Returns
        -------
        transaction : dict
            {
                "owner_id": str,
                "name": str,
                "balance": str,
                "transaction_date": str,
                "quantity_ordered": int,
                "cost": int,
                "quantity_in_stock": int,
                "sales": int,
                "status": str,
                "timestamp": int
            }
        """
        transactions = TakoMarket.get_transaction(self.my_id)
        if not transactions:
            return None
        return sorted(transactions, key=lambda x: x["date"], reverse=True)[0]

    def order(self, quantity):
        """Order Tako.

        Parameters
        ----------
        quantity : int

        Returns
        -------
        result : bool
        """
        area = TakoMarket.get_next_area()
        if area["date"]:
            TakoMarket.set_tako_quantity(self.my_id, area["date"], quantity)
            return True
        else:
            log.warning("Next market is not found.")
            return False


class TakoCommand(TakoClient):
    def interpret(self, cmd):
        """Interpret command
        """
        if cmd == "":
            self.balance()
            self.transaction()
            print()
            self.top3()
            self.market()
        elif cmd.isdecimal():
            quantity = int(cmd)
            max_quantity = self.max_order_quantity()[0]
            if quantity >= 0 and quantity <= max_quantity:
                if self.order(quantity):
                    print(f"Ordered {quantity} tako")
        elif cmd == "history":
            self.history()
        elif cmd == "help" or cmd == "?":
            self.help()
        elif cmd == "quit":
            return False

        return True

    def balance(self):
        """Show the balance
        """
        condition = TakoMarket.condition(self.my_id)
        balance = None
        if condition:
            ts_str = self.astimezone(condition["timestamp"], tz=(+9, "JST"))
            balance = condition["balance"]
            print(f"Balance: {balance} JPY"
                  f" at {ts_str}")
        else:
            print(f"your account '{self.my_id}' is not found.")
            print("open new account.")

    def transaction(self):
        """Show latest transaction.
        """
        transaction = self.latest_transaction()
        if transaction:
            ts_str = self.astimezone(transaction["timestamp"], tz=(+9, "JST"))
            if transaction["status"] == "ordered":
                print(f"Status: ordered {transaction['quantity_ordered']} tako"
                      f" at {ts_str}")
            if transaction["status"] == "in_stock":
                print(f"Status: {transaction['quantity_in_stock']}"
                      f" tako in stock at {ts_str}")
            if transaction["status"] == "closed":
                print(f"Status: closed '{transaction['date']}'"
                      f" with {transaction['sales']} JPY sales"
                      f" at {ts_str}")
                market = TakoMarket.get_area(transaction["date"])
                sales_q = int(transaction["sales"]/market["selling_price"])
                ordered_q = transaction["quantity_ordered"]
                in_stock_q = transaction["quantity_in_stock"]
                print(f"        You sold {sales_q} tako."
                      f" (Ordered: {ordered_q},"
                      f" In stock: {in_stock_q},"
                      f" Max: {market['sales']})")
            if transaction["status"] == "canceled":
                print(f"Status: canceled '{transaction['date']}'"
                      f" at {ts_str}")

    def history(self, number=None, reverse=True):
        """Show transaction history
        """
        transactions = TakoMarket.get_transaction(self.my_id)

        print("Date       Area     weather "
              "Ordered In stock Sales/max   Status  ")
        print("-"*66)
        for n, t in enumerate(sorted(transactions,
                              key=lambda x: x["date"],
                              reverse=reverse)):
            if n == number:
                break
            area = t["area"] + "　"*(4-len(t["area"]))
            print("%s %4s %-7s %7d %8d %5d/%-5d %-8s" % (
                    t['date'],
                    area,
                    t['weather'],
                    t['quantity_ordered'],
                    t['quantity_in_stock'],
                    t['sales']/takoconfig.SELLING_PRICE,
                    t['max_sales'],
                    t['status']))
        print("-"*66)

    def top3(self):
        """Show top 3 owners
        """
        print("Top 3 owners")
        runking = self.ranking()
        for i, owner in enumerate(runking):
            if i == 3:
                break
            print(f"{owner['name']}: {owner['balance']} JPY")

    def get_weather_forecast(self, name):
        """Show weather forecast.

        Parameters
        ----------
        name : str
            The name of The place.
        """
        meta = jma.PointMeta.get_point_meta(name)
        f = jma.Forecast.get_forecast(meta['class10s'])
        dow = self.DOW_JA[int(f["weather"]["datetime"].strftime("%w"))]
        weather_datetime = f["weather"]["datetime"].strftime(
            f"%e日 {dow}").strip()
        forecast_text = "".join(f["weather"]["text"].split())
        print(f"{weather_datetime} {name}")
        print(f"{forecast_text}")
        times = ""
        pops = ""
        for (t, p) in f["pops"]:
            if t.hour < 6:
                continue
            times += "%2s  " % t.strftime("%H")
            pops += "%2s%% " % p
        print(times)
        print(pops)

    def market(self):
        """Show market
        """
        area = TakoMarket.get_next_area()
        if area["date"]:
            print()
            print(f"Shop: {area['area']}")
            tz = (+9, "JST")
            opening_time_str = self.astimezone(area['opening_datetime'], tz=tz)
            closing_time_str = self.astimezone(area['closing_datetime'], tz=tz)
            print(f"Open: {opening_time_str}")
            print(f"Close: {closing_time_str}")
            print()
            self.get_weather_forecast(area["area"])

    def help(self):
        """Show help
        """
        print("  <Enter> : Show Tako Market Information.")
        print("  <Number> : Order tako.")
        print("  quit : Quit this command.")
        print("  help : Show this message.")


def takocmd():
    global my_id, my_name

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id",  help="Owner ID")
    parser.add_argument("-n", "--name",  help="Owner name")
    args = parser.parse_args()

    if args.id:
        my_id = args.id

    if args.name:
        my_name = args.name

    tc = TakoCommand(my_id, my_name)
    print(f"ID: {tc.my_id}, Display name: { tc.my_name}")

    while True:
        cmd = input(f"tako[{tc.max_order_quantity()[0]}]: ")
        if not tc.interpret(cmd):
            break


if __name__ == "__main__":
    takocmd()
