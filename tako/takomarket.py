#!/usr/bin/env python3

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
import time
import requests
import json
import random
import signal
import logging
from tako import takoconfig, jma, names
from tako.takotime import TakoTime as tt
from tako.takotime import JST

log = logging.getLogger(__name__)


class TakoMarketError(Exception):
    pass


class TakoMarketNoAccountError(Exception):
    pass


class TakoMarket:
    """The Tako shop

    Attributes
    ----------
    dbfile : str
        SQLite3 database filename.
    cost_price : int
        The cost of a tako
    selling_price : int
        The selling price of a tako
    seed_money : int
        The money to set up new tako shop.
    opening_time : str
        The opening time(JST) of market
    closng_time : str
        The closing time(JST) of market
    next_event : dict
        The next opening or closing event datetime
        (date, opeinig_datetime, closing_datetime)
    scheduler_state : str
        The state of scheduler thread
    stop : str
        The flag of stoping scheduler thread
    """
    def __init__(self):
        """Initialize each attributes and database
        """
        self.dbfile = takoconfig.TAKO_DB
        self.cost_price = takoconfig.COST_PRICE
        self.selling_price = takoconfig.SELLING_PRICE
        self.seed_money = takoconfig.SEED_MONEY
        self.opening_time = takoconfig.OPENING_TIME
        self.closing_time = takoconfig.CLOSING_TIME
        self.next_event = None
        self.scheduler_state = "rannable"
        self.stop = False

        with sqlite3.connect(self.dbfile) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    tako (
                        owner_id TEXT PRIMARY KEY,
                        balance INTEGER,
                        timestamp TEXT
                    )""")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    accounts (
                        owner_id TEXT PRIMARY KEY,
                        name TEXT,
                        timestamp TEXT
                    )""")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    tako_transaction (
                        owner_id TEXT,
                        transaction_date TEXT,
                        quantity_ordered INTEGER,
                        cost INTEGER,
                        quantity_in_stock INTEGER,
                        sales INTEGER,
                        status TEXT,
                        timestamp TEXT,
                        PRIMARY KEY (owner_id, transaction_date)
                    )""")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    shop (
                        date_jst TEXT PRIMARY KEY,
                        area TEXT,
                        opening_datetime TEXT,
                        closing_datetime TEXT,
                        cost_price INTEGER,
                        selling_price INTEGER,
                        seed_money INTEGER,
                        status TEXT,
                        sales INTEGER,
                        weather TEXT,
                        timestamp TEXT
                    )""")

    def make_tako(self, date):
        """Making tako

        Parameters
        ----------
        date : str
            Market date as JST.
        """
        with sqlite3.connect(self.dbfile) as conn:
            conn.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    cost = quantity_ordered*:cost,
                    quantity_in_stock = quantity_ordered,
                    status = 'in_stock',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    transaction_date = :date
                    AND
                    status = 'ordered'
                    AND
                    (
                        SELECT
                            balance
                        FROM
                            tako t
                        WHERE
                            t.owner_id = tako_transaction.owner_id
                    )
                    - quantity_ordered*:cost >= 0
                """,
                {"date": date, "cost": self.cost_price})

            conn.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    cost = (
                        SELECT
                            balance
                        FROM
                            tako t
                        WHERE
                            t.owner_id = tako_transaction.owner_id
                        )
                        /:cost*:cost,
                    quantity_in_stock = (
                        SELECT
                            balance
                        FROM
                            tako t
                        WHERE
                            t.owner_id = tako_transaction.owner_id
                        )
                        /:cost,
                    status = 'in_stock',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    transaction_date = :date
                    AND
                    status = 'ordered'
                    AND
                    (
                        SELECT
                            balance
                        FROM
                            tako t
                        WHERE
                            t.owner_id = tako_transaction.owner_id
                    )
                    - quantity_ordered*:cost < 0
                """,
                {"date": date, "cost": self.cost_price})

            conn.execute(
                """
                UPDATE
                    tako
                SET
                    balance = balance - (
                        SELECT
                            tra.cost
                        FROM
                            tako_transaction tra
                        WHERE
                            tra.owner_id = tako.owner_id
                            AND
                            tra.transaction_date = :date
                        ),
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    tako.owner_id
                    IN
                    (
                        SELECT
                            tra.owner_id
                        FROM
                            tako_transaction tra
                        WHERE
                            tra.transaction_date = :date
                    )
                """,
                {"date": date, "cost": self.cost_price})

            conn.execute(
                """
                UPDATE
                    shop
                SET
                    status = 'open',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    date_jst = ?
                """,
                (date,))

    def result(self, date, max_sales):
        """Calculate total sales

        Parameters
        ----------
        date : text
            Market date as JST.
        max_sales : int
            Maximum sales today
        """
        with sqlite3.connect(self.dbfile) as conn:
            conn.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    sales = min(quantity_in_stock, :sales)*:price,
                    status = 'closed',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    transaction_date = :date
                    AND
                    status = 'in_stock'
                """,
                {"date": date,
                 "price": self.selling_price,
                 "sales": max_sales})

            conn.execute(
                """
                UPDATE
                    tako
                SET
                    balance = balance
                              + (
                                 SELECT
                                     tra.sales
                                 FROM
                                     tako_transaction tra
                                 WHERE
                                     tra.owner_id = tako.owner_id
                                     AND
                                     tra.transaction_date = :date
                                ),
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    tako.owner_id
                    IN
                    (
                        SELECT
                            tra.owner_id
                        FROM
                            tako_transaction tra
                        WHERE
                            tra.transaction_date = :date
                    )
                """,
                {"date": date})

            conn.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    status = 'canceled',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    transaction_date = :date
                    AND
                    status = 'ordered'
                """,
                {"date": date})

            conn.execute(
                """
                UPDATE
                    shop
                SET
                    status = 'closed',
                    sales = ?,
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    status = 'open'
                    AND
                    date_jst = ?
                """,
                (max_sales, date))

    @staticmethod
    def set_tako_quantity(owner_id, date, quantity):
        """Order tako

        Parameters
        ----------
        owner_id : str
            Owner ID
        date : str
            Market date as JST
        quantity : int
            Quantity of tako you will make

        Returns
        -------
            quantity: int
                0 if could not set
        """
        if quantity < 0:
            quantity = 0

        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = conn.execute(
                """
                SELECT
                    status
                FROM
                    tako_transaction
                WHERE
                    owner_id = ?
                    AND
                    transaction_date = ?
                """,
                (owner_id, date))
            for r in rows:
                log.debug(f"{owner_id} {date} status: {r}")
                if r[0] != 'ordered':
                    log.warning("can't change '%s' transaction: %s, %s" %
                                (r[0], owner_id, date))
                    return 0

            conn.execute(
                """
                REPLACE INTO
                    tako_transaction
                VALUES
                    (:id, :date, :quantity, 0, 0, 0, 'ordered',
                     strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                """,
                {
                    "id": owner_id,
                    "date": date,
                    "quantity": quantity
                })
        return quantity

    def cancel_and_refund(self, date):
        """Cancel transaction and refound

        Parameters
        ----------
        date : str
            Cancel all transaction before the 'date'
        """
        with sqlite3.connect(self.dbfile) as conn:
            # refund
            conn.execute(
                """
                UPDATE
                    tako
                SET
                    balance = balance + (
                        SELECT
                            sum(tra.cost)
                        FROM
                            tako_transaction tra
                        WHERE
                            tra.owner_id = tako.owner_id
                            AND
                            tra.status = 'in_stock'
                            AND
                            tra.transaction_date < :date
                        ),
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    tako.owner_id
                    IN
                    (
                        SELECT
                            tra.owner_id
                        FROM
                            tako_transaction tra
                        WHERE
                            tra.owner_id = tako.owner_id
                            AND
                            tra.status = 'in_stock'
                            AND
                            tra.transaction_date < :date
                    )
                """,
                {"date": date})
            # canceled
            conn.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    status = 'canceled',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    (
                        status = 'in_stock'
                        OR
                        status = 'ordered'
                    )
                    AND
                    transaction_date < :date
                """,
                {"date": date})
            conn.execute(
                """
                UPDATE
                    shop
                SET
                    status = 'canceled',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    status <> 'closed'
                    AND
                    date_jst < ?
                """,
                (date,))

    @staticmethod
    def open_account(owner_id, name=None):
        """Open new account

        Parameters
        ----------
        owner_id : str
            Owner ID
        name : str
            Name of Owner
            If name is None, a name is set at rundom.
        """
        if not name:
            name = names.names()

        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            conn.execute(
                """
                INSERT INTO
                    accounts
                VALUES
                    (?, ?,
                     strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                """,
                (owner_id, name))

            conn.execute(
                """
                INSERT INTO
                    tako
                VALUES
                    (?, ?,
                     strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                """,
                (owner_id, takoconfig.SEED_MONEY))

    @staticmethod
    def change_name(owner_id, name):
        """Change the owner's display name.

        Parameters
        ----------
        owner_id : str
            Owner ID.
        name : str
            Display name of the owner.
        """
        if not name:
            raise TakoMarketError("name is None or empty.")

        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            conn.execute(
                """
                UPDATE
                    accounts
                SET
                    name = :name
                WHERE
                    owner_id = :owner_id
                """,
                {
                    "owner_id": owner_id,
                    "name": name
                })

    @staticmethod
    def condition(owner_id):
        """Query tako with owner ID

        Parameters
        ----------
        owner_id : str
            Owner's ID.

        Returns
        -------
        dict
            Key/value pairs of tako for the owner.
            The keys are 'owner_id', 'balance' and 'timestamp'.
            Retrun None in case of no owner.
        """
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    *
                FROM
                    tako
                WHERE
                    owner_id=?
                """,
                (owner_id,)))

        if len(rows) == 1:
            ret = dict(zip(
                ["owner_id", "balance", "timestamp"],
                rows[0]))
        elif len(rows) == 0:
            ret = None
        else:
            raise TakoMarketError(f"multiple rows: {owner_id}")
        return ret

    @staticmethod
    def condition_all():
        """Query tako and accounts

        Returns
        -------
        list
            The list of tako.
            Each item in the list is key/value pairs.
            The keys are 'name' and 'balance'.
        """
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    a.name, t.balance
                FROM
                    tako t, accounts a
                WHERE
                    t.owner_id = a.owner_id
                """
                ))
            all = [dict(zip(["name", "balance"], r))
                   for r in rows]
        return all

    @staticmethod
    def get_transaction(owner_id, date=None):
        """Query transaction and accounts

        Parameters
        ----------
        owner_id : str
            Owner's ID.
        date : str
            Market date as JST.

        Returns
        -------
        list
            The list of transaction for the owner.
            Each item in the list is dict.
        """
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    t.owner_id,
                    a.name,
                    t.balance,
                    tra.transaction_date,
                    tra.quantity_ordered,
                    tra.cost,
                    tra.quantity_in_stock,
                    tra.sales,
                    tra.status,
                    tra.timestamp,
                    s.area,
                    s.sales,
                    s.weather
                FROM
                    tako t
                INNER JOIN
                    accounts a ON t.owner_id = a.owner_id
                INNER JOIN
                    tako_transaction tra ON t.owner_id = tra.owner_id
                INNER JOIN
                    shop s ON tra.transaction_date = s.date_jst
                WHERE
                    t.owner_id = ?
                """,
                (owner_id,)))

        if date:
            ret = [dict(zip(
                ["owner_id", "name", "balance",
                 "date", "quantity_ordered", "cost",
                 "quantity_in_stock", "sales",
                 "status", "timestamp", "area", "max_sales", "weather"],
                r)) for r in rows if r[3] == date]
        else:
            ret = [dict(zip(
                ["owner_id", "name", "balance",
                 "date", "quantity_ordered", "cost",
                 "quantity_in_stock", "sales",
                 "status", "timestamp", "area", "max_sales", "weather"],
                r)) for r in rows]
        return ret

    @staticmethod
    def get_name(owner_id):
        """Get the display name of the owner

        Parameters
        ----------
        owner_id : str
            Owner's ID.

        Returns
        -------
        str
            The display name of the owner.
        """
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    *
                FROM
                    accounts
                WHERE
                    owner_id=?
                """,
                (owner_id,)))
        if len(rows) == 0:
            raise TakoMarketNoAccountError(
                f"account is not exist in DB: {owner_id}")
        if len(rows) != 1:
            raise TakoMarketError(f"multiple rows: {owner_id}")

        return rows[0][1]

    def schedule(self, onetime=False):
        """Do a transaction

        Parameters
        ----------
        onetime : bool
            Do only transaction if onetime is True.
            Run daemon mode if onetime is False.
        """
        open_done = False
        closed_done = False
        self.next_event = self.get_next_event()
        if not self.next_event["date"]:
            self.set_area()
            self.next_event = self.get_next_event()
            if not self.next_event["date"]:
                raise TakoMarketError("can't get a next event")
        self.cancel_and_refund(self.next_event["date"])

        self.scheduler_state = "running"
        log.debug("scheduler is running.")
        while not self.stop or onetime:
            now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            if now == self.next_event["opening_datetime"]:
                if not open_done:
                    area = self.get_area(self.next_event["date"])["area"]
                    log.debug(f"Now open in {area}")
                    self.cancel_and_refund(self.next_event["date"])
                    self.make_tako(self.next_event["date"])
                    self.set_area()
                    log.debug(f"Next area is {self.get_next_area()['area']}")
                    open_done = True

                    self.next_event = self.get_next_event()
                    if not self.next_event["date"]:
                        self.set_area()
                        self.next_event = self.get_next_event()
                        if not self.next_event["date"]:
                            raise TakoMarketError("can't get a next event")
            else:
                open_done = False

            if now == self.next_event["closing_datetime"]:
                if not closed_done:
                    self.cancel_and_refund(self.next_event["date"])
                    try:
                        today_sales, weather = self.total_up_sales()
                    except ValueError:
                        log.waring("can't get weather data")
                        time.sleep(15)
                        continue
                    area = self.get_area(self.next_event["date"])["area"]
                    log.debug(f"Now close in {area}")
                    self.result(self.next_event["date"], today_sales)
                    self.log_weather(now, weather)
                    log.debug(
                        f"today_sales: {today_sales}, weather: {weather}")
                    closed_done = True

                    self.next_event = self.get_next_event()
                    if not self.next_event["date"]:
                        self.set_area()
                        self.next_event = self.get_next_event()
                        if not self.next_event["date"]:
                            raise TakoMarketError("can't get a next event")
                        log.debug("Next area is "
                                  f"{self.get_next_area()['area']}")
            else:
                closed_done = False
            if onetime:
                break
            time.sleep(1)

    def run_market(self):
        """Run a sheduler of market
          Use stop_market() To the scheduler
        """
        self.stop = False
        self.market_thread = threading.Thread(
            target=self.schedule)
        self.scheduler_state = "initializing"
        log.debug("scheduler is starting...")
        self.market_thread.start()

    def stop_market(self):
        """stop the scheduler of market
        """
        self.stop = True
        self.market_thread.join()
        log.debug("scheduler has stoped.")
        self.scheduler_state = "runnable"

    def signal_handlar(self, signum, frame):
        """Signal Handlar
           Request schedule thread to stop

        Parameters
        ----------
        signum : The signal number.
        frame : The current stack frame.
        """
        signame = signal.Signals(signum).name
        log.debug(f"signal handlar received {signame}.")
        self.stop_market()

    def get_point(self):
        """Get a weather observing station at random

        Returns
        -------
        str : The name of station.
        """
        points = jma.Synop.point_list()
        while True:
            point = random.sample(points, 1)[0]
            meta = jma.PointMeta.get_point_meta(point)
            if not meta:
                continue
            if meta.get('class10s'):
                break
        return point

    def set_area(self, date=None, tz=JST):
        """Set a area of market if not exists

        Parameters
        ----------
        date : str
            The date of tako market.
            If date is None, set tomorrow
        tz : timezone
            The timezone of opening_time and closing_time.
        """
        if not date:
            now = datetime.now(tz) + timedelta(days=1)
            date = now.date()

        if self.get_area(date):
            log.warning(f"{date} already exists.")
            return

        opening_datetime_tz = datetime.fromisoformat(
            f"{date} {self.opening_time}").replace(tzinfo=tz)
        closing_datetime_tz = datetime.fromisoformat(
            f"{date} {self.closing_time}").replace(tzinfo=tz)

        opening_datetime_utc_str = tt.as_utc_str(opening_datetime_tz)
        closing_datetime_utc_str = tt.as_utc_str(closing_datetime_tz)
        area = self.get_point()

        with sqlite3.connect(self.dbfile) as conn:
            conn.execute(
                """
                INSERT INTO
                    shop
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                """,
                (
                    date,
                    area,
                    opening_datetime_utc_str,
                    closing_datetime_utc_str,
                    self.cost_price,
                    self.selling_price,
                    self.seed_money,
                    "coming_soon",
                    0,
                    ""
                ))
            self.next_event = self.get_next_event()

    @staticmethod
    def get_area(date=None):
        """Get a area of market

        Parameters
        ----------
        date : str
            The date of tako market.
            If date is None, set today.

        Returns
        -------
        dict
            "date",
            "area",
            "opening_datetime",
            "closing_datetime",
            "cost_price",
            "selling_price",
            "seed_money",
            "status",
            "sales",
            "weather",
            "timestamp"

            If not exist, return None
        """
        if not date:
            date = datetime.now(JST).strftime("%Y-%m-%d")
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    *
                FROM
                    shop
                WHERE
                    date_jst = ?
                """,
                (date,)))
            if len(rows) == 1:
                ret = dict(zip(
                    [
                        "date",
                        "area",
                        "opening_datetime",
                        "closing_datetime",
                        "cost_price",
                        "selling_price",
                        "seed_money",
                        "status",
                        "sales",
                        "weather",
                        "timestamp"
                    ],
                    rows[0]))
                ret["opening_datetime"] = datetime.fromisoformat(
                    ret["opening_datetime"]+"+00:00")
                ret["closing_datetime"] = datetime.fromisoformat(
                    ret["closing_datetime"]+"+00:00")
            elif len(rows) == 0:
                ret = None
            else:
                raise TakoMarketError(
                    f"multiple rows in 'shop': {date}")
            return ret

    @staticmethod
    def get_area_history():
        """Get history of areas (descending order)

        Returns
        -------
        list of dict
            "date",
            "area",
            "opening_datetime",
            "closing_datetime",
            "cost_price",
            "selling_price",
            "seed_money",
            "status",
            "sales",
            "weather",
            "timestamp"

            If not exist, return None
        """
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    *
                FROM
                    shop
                ORDER BY
                    date_jst DESC
                """))
            if len(rows) == 0:
                return None
            areas = []
            for r in rows:
                area = dict(zip(
                    [
                        "date",
                        "area",
                        "opening_datetime",
                        "closing_datetime",
                        "cost_price",
                        "selling_price",
                        "seed_money",
                        "status",
                        "sales",
                        "weather",
                        "timestamp"
                    ],
                    r))
                area["opening_datetime"] = datetime.fromisoformat(
                    area["opening_datetime"]+"+00:00")
                area["closing_datetime"] = datetime.fromisoformat(
                    area["closing_datetime"]+"+00:00")
                areas.append(area)
            return areas

    @staticmethod
    def get_next_area():
        """Get next area of market

        Returns
        -------
        dict
            "date",
            "area",
            "opening_datetime",
            "closing_datetime",
            "status",
            "sales",
            "weather",
            "timestamp"

            If not exist, return None
        """
        date = tt.clear_time(datetime.now(JST))
        datetime_utc_str = tt.as_utc_str(date)
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    max(date_jst), area, opening_datetime, closing_datetime,
                    status, sales, weather, timestamp
                FROM
                    shop
                WHERE
                    date_jst >= ?
                    AND
                    status = 'coming_soon'
                """,
                (datetime_utc_str,)))

            if len(rows) != 1:
                raise TakoMarketError("multiple rows in 'shop': next area")

            ret = dict(zip(
                [
                    "date",
                    "area",
                    "opening_datetime",
                    "closing_datetime",
                    "status",
                    "sales",
                    "weather",
                    "timestamp"
                ],
                rows[0]))
            log.debug(f"get_next_area: {ret}")

            if ret["date"] is None:
                return ret

            ret["opening_datetime"] = datetime.fromisoformat(
                ret["opening_datetime"]+"+00:00")
            ret["closing_datetime"] = datetime.fromisoformat(
                ret["closing_datetime"]+"+00:00")
            return ret

    @staticmethod
    def get_next_event(now=None):
        """Get datetime of next event

        Parameters
        ----------
        now : datetime.datetime
            Timezone is UTC.

        Returns
        -------
            event datetime : dict
                {
                  "date" : str,
                  "opening_datetime" : datetime
                  "closing_datetime" : datetime
                }
        """
        if now is None:
            now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                """
                SELECT
                    min(date_jst), opening_datetime, closing_datetime
                FROM
                    shop
                WHERE
                    (
                        datetime(opening_datetime) >= datetime(:now)
                        AND
                        status = 'coming_soon'
                    )
                    OR
                    (
                        datetime(closing_datetime) >= datetime(:now)
                        AND
                        status = 'open'
                    )
                """,
                {"now": now_str}
            ))
            if len(rows) != 1:
                raise TakoMarket("multiple rows in 'shop' table: next event")

            event = dict(zip([
                        "date",
                        "opening_datetime",
                        "closing_datetime",
                    ],
                    rows[0]))

            if event["date"] is None:
                return event

            if event["opening_datetime"]:
                event["opening_datetime"] = datetime.fromisoformat(
                    event["opening_datetime"] + "+00:00")
            if event["closing_datetime"]:
                event["closing_datetime"] = datetime.fromisoformat(
                    event["closing_datetime"] + "+00:00")
        return event

    def log_weather(self, date, weather):
        """Log weather

        Parameters
        ----------
        date : datetime
            UTC
        weather : str
        """
        with sqlite3.connect(self.dbfile) as conn:
            conn.execute(
                """
                UPDATE
                    shop
                SET
                    weather = :weather,
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    date_jst = :date
                """,
                {
                    "date": date.strftime('%Y-%m-%d'),
                    "weather": weather
                })

    def total_up_sales(self):
        """Total up sales

        Returns
        -------
            (Today's sales, weather) : (int, str)
        """
        w = self.weather()
        sunshine_ratio = min(
            w['sunshine_hour'] /
            (w['day_length_hour'] -
             takoconfig.SUNSHINE_RATIO_CORRECTION_HOUR), 1.0)
        rainfall_max_mm = 5.0*w['day_length_hour']
        rainfall_ratio = min(w['rainfall_mm'], rainfall_max_mm)/rainfall_max_mm

        today_sales = int(takoconfig.MAX_SALES['cloudy']
                          + takoconfig.MAX_SALES['sunny']*sunshine_ratio
                          + takoconfig.MAX_SALES['rainy']*rainfall_ratio)
        log.info(f"sunshine_hour: {w['sunshine_hour']}, "
                 f"day_length_hour: {w['day_length_hour']}, "
                 f"sunshine_ratio: {sunshine_ratio}, "
                 f"rainfall_max_mm: {rainfall_max_mm}, "
                 f"rainfall_mm: {w['rainfall_mm']}, "
                 f"rainfall_ratio: {rainfall_ratio}, "
                 f"today_sales: {today_sales}")
        return (today_sales, w['weather'])

    def weather(self):
        """Get weather

        Returns
        -------
            weather : dict
                      {
                          "title": str,
                          "sunshine_hour": float,
                          "rainfall_mm": float,
                          "day_length_hour": float,
                          "weather": str
                      }
        """
        self.today_point = self.get_area()["area"]
        now = jma.Synop.synopday(point=self.today_point)
        point = now['data'][self.today_point]
        sunshine = float(point['sunshine']['duration']['value'])
        rainfall = now['data'][self.today_point]['rainfall']['totals']['value']
        if rainfall == "--":
            rainfall = 0
        rainfall = float(rainfall)

        meta = jma.PointMeta.get_point_meta(self.today_point)
        log.debug(f"{self.today_point}: {meta}")
        url = "https://api.sunrise-sunset.org/json"
        r = requests.get(
            f"{url}?"
            f"lat={meta['lat']}&"
            f"lng={meta['lng']}&"
            "date=today&"
            "formatted=0")
        sun = json.loads(r.content)
        day_length_hour = float(sun['results']['day_length'])/3600
        sunshine_ratio = sunshine/(day_length_hour -
                                   takoconfig.SUNSHINE_RATIO_CORRECTION_HOUR)

        weather = "cloudy"
        if sunshine_ratio > 0.1:
            weather = "suunny"
        if rainfall > 2.0*day_length_hour:
            weather = "rainy"

        today = {
            'title': now['title'],
            'sunshine_hour': sunshine,
            'rainfall_mm': rainfall,
            'day_length_hour': day_length_hour,
            'weather': weather,
        }

        return today


def tako_server():
    """Run Tako server
    """
    import argparse

    global log
    log = takoconfig.set_logging_level("TAKOMARKET_DEBUG", "tako_server")

    parser = argparse.ArgumentParser(description="Takoyaki Market")
    parser.add_argument("-d", "--daemon", action="store_true")
    args = parser.parse_args()

    tako = TakoMarket()

    if args.daemon:
        for sig in [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, tako.signal_handlar)
        print("tako server running...")
        tako.run_market()
        while tako.scheduler_state != "running":
            time.sleep(1)
        while tako.scheduler_state == "running":
            time.sleep(5)
    else:
        tako.schedule(onetime=True)


if __name__ == "__main__":
    tako_server()
