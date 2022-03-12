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
        forecast = jma.Forecast.get_forecast(meta["class10s"], area["date"])
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
                "date": str,
                "quantity_ordered": int,
                "cost": int,
                "quantity_in_stock": int,
                "sales": int,
                "status": str,
                "timestamp": int,
                "area": str,
                "max_sales": int,
                "weather": str,
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

    @staticmethod
    def badge_to_emoji(badge):
        """Get the display name and badges

        Parameters
        ----------
        badge : int

        Returns
        -------
        str

        Examples
        --------
        111 badges:
            ⭐🦑🐙
        29 badges:
            🦑🦑🐙🐙🐙🐙🐙🐙🐙🐙🐙
        30 badges:
            🦑🦑🦑
        """
        emoji = "⭐"*int(badge/100)
        badge -= int(badge/100)*100
        emoji += "🦑"*int(badge/10)
        badge -= int(badge/10)*10
        emoji += "🐙"*badge
        return emoji


class TakoCommand(TakoClient):
    def interpret(self, cmd):
        """Interpret command
        """
        response = []
        if cmd == "":
            response.append(self.name_with_badge())
            response.extend(self.balance())
            response.extend(self.transaction())
            response.append("")
            response.extend(self.top3())
            response.extend(self.market())
        elif cmd.isdecimal():
            quantity = int(cmd)
            max_quantity = self.max_order_quantity()[0]
            if quantity >= 0 and quantity <= max_quantity:
                if self.order(quantity):
                    response.append(f"Ordered {quantity} tako")
        elif cmd == "history":
            response.extend(self.history())
        elif cmd == "help" or cmd == "?":
            response.extend(self.help())
        elif cmd == "quit":
            return False

        print("\n".join(response))
        return True

    def name_with_badge(self):
        """Show name with badge

        Returns
        -------
        name : str

        Example
        -------
        One ⭐🦑🐙
        Two
        Three 🦑🦑🦑
        """
        name = []
        (_id, name, badges, *_) = TakoMarket.get_name(self.my_id)
        badges_str = TakoClient.badge_to_emoji(badges)
        return "%s %s" % (name, badges_str)

    def balance(self):
        """Show the balance

        Returns
        -------
        texts : list of str

        Example
        -------
        Balance: 5000 JPY at 2021-10-10 12:22 JST
        """
        texts = []
        condition = TakoMarket.condition(self.my_id)
        if condition:
            ts_str = self.astimezone(
                condition["timestamp"],
                tz=(+9, "JST"))
            balance = condition["balance"]
            texts.append(f"Balance: {balance} JPY at {ts_str}")
        else:
            texts.append(f"your account '{self.my_id}' is not found.")
            texts.append("open new account.")
        return texts

    def text_for_closed(self, transaction):
        """Show closing condition

        Parameters
        ----------
        transaction : dict
                "owner_id", "name", "balance",
                "date", "quantity_ordered", "cost",
                "quantity_in_stock", "sales",
                "status", "timestamp", "area", "max_sales", "weather"

        Returns
        -------
        texts : list of str

        Example
        -------
        Status: closed 2021-10-10 with 5000 JPY sales at 2021-10-10 15:00 JST
                You sold 200 tako. (Ordered: 200, In stock: 250, Max: 500)
        """
        texts = []
        ts_str = self.astimezone(
            transaction["timestamp"],
            tz=(+9, "JST"))
        texts.append(f"Status: closed '{transaction['date']}'"
                     f" with {transaction['sales']} JPY sales"
                     f" at {ts_str}")
        market = TakoMarket.get_area(transaction["date"])
        sales_q = int(transaction["sales"]/market["selling_price"])
        ordered_q = transaction["quantity_ordered"]
        in_stock_q = transaction["quantity_in_stock"]
        texts.append(f"        You sold {sales_q} tako."
                     f" (Ordered: {ordered_q},"
                     f" In stock: {in_stock_q},"
                     f" Max: {market['sales']})")
        return texts

    def name_balance_badge(self, record):
        """Create text of name with badges
        Parameters
        ----------
        record : dict
            {
                "name": str,
                "balance": int,
                "target": int,
                "ranking": int,
                "badge": int,
            }

        Returns
        -------
        texts : list of str

        Example
        -------
        One : 35000 JPY
        ⭐🦑🐙
        """
        texts = []
        name = record["name"]
        balance = record["balance"]
        badge = record['badge']
        text = f"{name} : {balance} JPY"
        texts.append(text)
        text = TakoClient.badge_to_emoji(badge)
        if len(text) > 0:
            texts.append(text)
        return texts

    def text_for_restart(self, transaction):
        """Show record
        Returns
        -------
        texts : list of str

        Example
        -------
        This season is over. And next season has begun.
        One : 35000 JPY
         ⭐🦑🐙
        Two : 33000 JPY\n"
         🦑🦑🐙🐙🐙🐙🐙🐙🐙🐙🐙
        Three : 31000 JPY
         🦑🦑🦑

        The following is the close to the target.
        Four : 29000 JPY
         🦑🦑🦑🦑🦑🦑🦑🦑🦑🐙🐙🐙🐙🐙🐙🐙🐙🐙

        Five : 29000 JPY
        """
        texts = []
        texts.append("This season is over. And next season has begun.")
        balance = -float("inf")
        records = TakoMarket.get_records(
            date_jst=transaction["date"],
            winner=False)
        for r in records[transaction["date"]]:
            if r["balance"] < r["target"]:
                if balance > r["balance"]:
                    break
                if balance == -float("inf"):
                    texts.append("")
                    texts.append("The following is the close to the target.")
                balance = r["balance"]
            texts.extend(self.name_balance_badge(r))
        texts.append("")
        return texts

    def transaction(self):
        """Create latest transaction.

        Returns
        -------
        texts : list of str


        Example
        -------
        Status: orderd 250 tako at 2021-10-10 19:00 JST
        or
        Status: 250 tako in stock at 2021-10-10 19:00 JST
        or
        Status: canceled 2021-10-10 at 2021-10-10 19:00 JST
        """
        texts = []
        transaction = self.latest_transaction()
        if transaction:
            ts_str = self.astimezone(transaction["timestamp"], tz=(+9, "JST"))
            if transaction["status"] == "ordered":
                texts.append(
                    f"Status: ordered {transaction['quantity_ordered']} tako"
                    f" at {ts_str}")
            if transaction["status"] == "in_stock":
                texts.append(
                    f"Status: {transaction['quantity_in_stock']}"
                    f" tako in stock at {ts_str}")
            if transaction["status"] in ["closed", "closed_and_restart"]:
                if transaction["status"] == "closed_and_restart":
                    texts.extend(self.text_for_restart(transaction))
                texts.extend(self.text_for_closed(transaction))
            if transaction["status"] == "canceled":
                texts.append(
                    f"Status: canceled '{transaction['date']}'"
                    f" at {ts_str}")
        return texts

    def history(self, number=None, reverse=True):
        """Show transaction history

        Returns
        -------
        texts : list of str

        Example
        -------
        Date       Area     weather Ordered In stock Sales/max   Status
        ------------------------------------------------------------------
        2022-01-22 帯広　　             100        0     0/0     ordered
        ------------------------------------------------------------------
        """
        texts = []
        transactions = TakoMarket.get_transaction(self.my_id)

        texts.append("Date       Area     weather "
                     "Ordered In stock Sales/max   Status  ")
        texts.append("-"*66)
        for n, t in enumerate(sorted(transactions,
                              key=lambda x: x["date"],
                              reverse=reverse)):
            if n == number:
                break
            area = t["area"] + "　"*(4-len(t["area"]))
            texts.append("%s %4s %-7s %7d %8d %5d/%-5d %-8s" % (
                t['date'],
                area,
                t['weather'],
                t['quantity_ordered'],
                t['quantity_in_stock'],
                t['sales']/takoconfig.SELLING_PRICE,
                t['max_sales'],
                t['status']))
        texts.append("-"*66)
        return texts

    def top3(self):
        """Show top 3 owners

        Returns
        -------
        texts : list of str

        Example
        -------
        Top 3 owners
        id1001: 10000 JPY
        id1002: 9000 JPY
        id1003: 5000 JPY
        """
        texts = []
        texts.append("Top 3 owners")
        runking = self.ranking()
        for i, owner in enumerate(runking):
            if i == 3:
                break
            texts.append(f"{owner['name']}: {owner['balance']} JPY")
        return texts

    def get_weather_forecast(self, name, date_jst):
        """Show weather forecast.

        Parameters
        ----------
        name : str
            The name of The place.
        date_jst : str

        Returns
        -------
        texts : list of str

        Example
        -------
        24日 月曜日 山形
        くもり後晴れ明け方一時雪
        06  12  18
        20% 10% 10%
        """
        texts = []
        meta = jma.PointMeta.get_point_meta(name)
        f = jma.Forecast.get_forecast(meta['class10s'], date_jst)
        dow = self.DOW_JA[int(f["weather"]["datetime"].strftime("%w"))]
        weather_datetime = f["weather"]["datetime"].strftime(
            f"%e日 {dow}").strip()
        forecast_text = "".join(f["weather"]["text"].split())
        texts.append(f"{weather_datetime} {name}")
        texts.append(f"{forecast_text}")
        times = ""
        pops = ""
        for (t, p) in f["pops"]:
            if t.hour < 6:
                continue
            times += "%2s  " % t.strftime("%H")
            pops += "%2s%% " % p
        texts.append(times)
        texts.append(pops)
        return texts

    def market(self):
        """Show market

        Returns
        -------
        messages : list of str

        Example
        -------
        Next: 山形
        Open: 2022-01-24 09:00 JST
        Close: 2022-01-24 18:00 JST

        24日 月曜日 山形
        くもり後晴れ明け方一時雪
        06  12  18
        20% 10% 10%
        """
        texts = []
        area = TakoMarket.get_next_area()
        if area["date"]:
            texts.append("")
            texts.append(f"Next: {area['area']}")
            tz = (+9, "JST")
            opening_time_str = self.astimezone(area['opening_datetime'], tz=tz)
            closing_time_str = self.astimezone(area['closing_datetime'], tz=tz)
            texts.append(f"Open: {opening_time_str}")
            texts.append(f"Close: {closing_time_str}")
            texts.append("")
            try:
                forecast = self.get_weather_forecast(
                    area["area"],
                    area["date"])
                texts.extend(forecast)
            except jma.JmaError as e:
                log.warning(f"can't get weather forecast: {e}")
        return texts

    def help(self):
        """Show help

        Returns
        -------
        messages : list of str
        """
        texts = []
        texts.append("  <Enter> : Show Tako Market Information.")
        texts.append("  <Number> : Order tako.")
        texts.append("  history : Show History of Transactions.")
        texts.append("  quit : Quit this command.")
        texts.append("  help : Show this message.")
        return texts


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
    print(f"ID: {tc.my_id}, Display name: {tc.my_name}")

    while True:
        cmd = input(f"tako[{tc.max_order_quantity()[0]}]: ")
        if not tc.interpret(cmd):
            break


if __name__ == "__main__":
    takocmd()
