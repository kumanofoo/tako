#!/usr/bin/env python3

from typing import Optional, Dict, List, Tuple, Any
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
import time
import random
import signal
import logging
import ephem
from tako import takoconfig, jma, names
from tako.takotime import TakoTime as tt
from tako.takotime import JST

log = logging.getLogger(__name__)


class TakoMarketError(Exception):
    pass


class TakoMarketNoAccountError(Exception):
    pass


class SunriseSunsetError(Exception):
    pass


class Context:
    def __init__(self):
        self.conn = sqlite3.connect(takoconfig.TAKO_DB)
        self.cur = self.conn.cursor()
        self.nest_level = 0


class MarketDB:
    """Takomarket DB
    """
    context: Dict[int, Dict[int, Context]] = {}

    @staticmethod
    def clear_context():
        MarketDB.context = {}

    def __init__(self, retry: int = -1):
        self.retry = retry
        db = id(takoconfig.TAKO_DB)
        if not MarketDB.context.get(db):
            MarketDB.context[db] = {}
        th = threading.get_ident()
        if not MarketDB.context[db].get(th):
            MarketDB.context[db][th] = Context()
        self.conn = MarketDB.context[db][th].conn
        self.cur = MarketDB.context[db][th].cur
        self.con = MarketDB.context[db][th]
        self.db = db
        self.th = th

    def __enter__(self):
        self.con.nest_level += 1
        if self.con.nest_level == 1:
            retry = self.retry
            while True:
                try:
                    self.cur.execute("BEGIN EXCLUSIVE")
                    break
                except sqlite3.OperationalError as e:
                    if retry == 0:
                        log.warning("give up connecting to DB")
                        raise
                    log.info(f"waiting for DB({retry}):\n\t{e}")
                    retry -= 1
                    time.sleep(5)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.con.nest_level == 1:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        self.con.nest_level -= 1

    def rollback(self):
        self.conn.rollback()

    def commit(self):
        self.conn.commit()

    def create_db(self):
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS
                tako (
                    owner_id TEXT PRIMARY KEY,
                    balance INTEGER,
                    timestamp TEXT
                )""")
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS
                accounts (
                    owner_id TEXT PRIMARY KEY,
                    name TEXT,
                    badge INTEGER,
                    timestamp TEXT
                )""")
        self.cur.execute(
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
        self.cur.execute(
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
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS
                records (
                    date_jst TEXT,
                    owner_id TEXT,
                    balance INTEGER,
                    target INTEGER,
                    timestamp TEXT,
                    PRIMARY KEY(date_jst, owner_id)
                )""")

    def make_tako(self, date: str) -> None:
        """Making tako

        Parameters
        ----------
        date : str
            Market date as JST.
        """
        self.cur.execute(
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
            {"date": date, "cost": takoconfig.COST_PRICE})

        self.cur.execute(
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
            {"date": date, "cost": takoconfig.COST_PRICE})

        self.cur.execute(
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
            {"date": date, "cost": takoconfig.COST_PRICE})

        self.cur.execute(
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

    def result(self, date: str, max_sales: int) -> bool:
        """Calculate total sales

        Parameters
        ----------
        date : text
            Market date as JST.
        max_sales : int
            Maximum sales today

        Returns
        -------
        winner_exists : bool
        """
        self.cur.execute(
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
             "price": takoconfig.SELLING_PRICE,
             "sales": max_sales})

        self.cur.execute(
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

        self.cur.execute(
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

        self.cur.execute(
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

        winner_exists = self.detect_winner_and_restart(date)
        if winner_exists:
            self.cur.execute(
                """
                UPDATE
                    tako_transaction
                SET
                    status = 'closed_and_restart',
                    timestamp = strftime('%Y-%m-%dT%H:%M:%f', 'now')
                WHERE
                    transaction_date = :date
                    AND
                    status = 'closed'
                """,
                {"date": date})

        return winner_exists

    def detect_winner_and_restart(self, date_jst: str) -> bool:
        """Detect winner and restart market

        Parameters
        ----------
        date_jst : str

        Returns
        -------
        winner_exists : bool
        """
        # detect winner
        rows = list(self.cur.execute(
            """
            SELECT
                *
            FROM
                tako
            WHERE
                balance >= ?
            """,
            (takoconfig.TARGET,)))
        if len(rows) == 0:
            return False
        # restart market
        self.cur.execute(
            """
            INSERT INTO
                records
            SELECT
                ?, owner_id, balance, ?,
                strftime('%Y-%m-%dT%H:%M:%f', 'now')
            FROM
                tako
            """,
            (date_jst, takoconfig.TARGET))
        self.cur.execute(
            """
            UPDATE
                tako
            SET
                balance = ?
            """,
            (takoconfig.SEED_MONEY,))
        self.cur.execute(
            """
            UPDATE
                accounts
            SET
                badge = badge + 1
            WHERE
                owner_id in (
                    SELECT
                        owner_id
                    FROM
                        records
                    WHERE
                        date_jst = :date_jst
                    AND
                        balance >= :target
                )
            """,
            {
                "date_jst": date_jst,
                "target": takoconfig.TARGET,
            })
        return True

    def set_tako_quantity(
            self,
            owner_id: str,
            date: str,
            quantity: int) -> int:
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

        rows = self.cur.execute(
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

        self.cur.execute(
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

    def cancel_and_refund(self, date: str) -> None:
        """Cancel transaction and refound

        Parameters
        ----------
        date : str
            Cancel all transaction before the 'date'
        """
        # refund
        self.cur.execute(
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
        self.cur.execute(
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
        self.cur.execute(
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

    def get_records(
            self,
            date_jst: Optional[str] = None,
            top: float = float("inf"),
            winner: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Get records

        Parameters
        ----------
        date_jst : str
        top : int
        winnter : bool
            only owners reach target.

        Returns
        -------
        ranking : dict
            {
                "YYYY-MM-DD": [
                    {
                        "name": str,
                        "balance": int,
                        "target": int,
                        "ranking": int,
                        "badge": int,
                    },
                    {....}],
                ....,
            }
        """
        results = self.cur.execute(
            """
            SELECT
                r.date_jst, r.owner_id, a.name,
                r.balance, r.target, a.badge
            FROM
                records r, accounts a
            WHERE
                (
                    r.date_jst = :date
                OR
                    :date IS NULL
                )
            AND
                r.owner_id = a.owner_id
            AND
                (
                    r.balance >= r.target
                OR
                    :winner = 0
                )
            """,
            {"date": date_jst, "winner": winner})
        results_dict: Dict[str, List[tuple]] = {}
        for result in results:
            if not results_dict.get(result[0]):
                results_dict[result[0]] = []
            results_dict[result[0]].append(result[1:])
        ret = {}
        for date_jst in results_dict.keys():
            r = []
            for o in results_dict[date_jst]:
                c = len([u for u in results_dict[date_jst] if o[2] < u[2]])
                c += 1
                if c <= top:
                    r.append({
                        "name": o[1],
                        "balance": o[2],
                        "target": o[3],
                        "ranking": c,
                        "badge": o[4]
                    })
            ret[date_jst] = sorted(r, key=lambda x: x["ranking"])
        return ret

    def get_owner_records(self, owner_id: str) -> Dict[str, Dict[str, int]]:
        """Get records by owner

        Parameters
        ----------
        owner_id : str

        Returns:
        records : dict
            {
                "YYYY-MM-DD": {
                        "balance": int,
                        "target": int,
                        "ranking": int,
                },
                ....,
            }
        """
        rows = list(self.cur.execute(
            """
            SELECT
                date_jst, balance, rank, target
            FROM (
                SELECT
                    date_jst, owner_id,
                    balance, target,
                    RANK() OVER(
                        PARTITION BY date_jst
                        ORDER BY balance DESC
                    ) AS rank
                FROM
                    records
            )
            WHERE
                owner_id = ?
            """,
            (owner_id,)))

        records = {}
        for row in rows:
            records[row[0]] = dict(zip(
                ["balance", "rank", "target"],
                row[1:]))
        return records

    def open_account(
            self,
            owner_id: str,
            name: Optional[str] = None) -> None:
        """Open new account

        Parameters
        ----------
        owner_id : str
            Owner ID
        name : str
            Name of Owner
            If name is None, a name is set at random.
        """
        if not name:
            name = names.names()

        self.cur.execute(
            """
            INSERT INTO
                accounts
            VALUES
                (?, ?, ?,
                 strftime('%Y-%m-%dT%H:%M:%f', 'now'))
            """,
            (owner_id, name, 0))

        self.cur.execute(
            """
            INSERT INTO
                tako
            VALUES
                (?, ?,
                 strftime('%Y-%m-%dT%H:%M:%f', 'now'))
            """,
            (owner_id, takoconfig.SEED_MONEY))

    def delete_account(self, owner_id: str) -> Optional[str]:
        """Delete account

        Parameters
        ----------
        owner_id : str
            Owner ID

        Returns
        -------
        owner_id : str
            If deleting failed, return None
        """
        if not owner_id:
            return None
        try:
            _ = self.get_name(owner_id)
        except TakoMarketNoAccountError:
            return None

        self.cur.execute(
            """
            DELETE FROM
                records
            WHERE
                owner_id = ?
            """, (owner_id,))
        self.cur.execute(
            """
            DELETE FROM
                tako_transaction
            WHERE
                owner_id = ?
            """, (owner_id,))
        self.cur.execute(
            """
            DELETE FROM
                tako
            WHERE
                owner_id = ?
            """, (owner_id,))
        self.cur.execute(
            """
            DELETE FROM
                accounts
            WHERE
                owner_id = ?
            """, (owner_id,))
        return owner_id

    def change_name(self, owner_id: str, name: str) -> None:
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

        self.cur.execute(
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

    def condition(self, owner_id: str) -> Optional[Dict[str, Any]]:
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
        rows = list(self.cur.execute(
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

    def condition_all(self) -> List[Dict[str, Any]]:
        """Query tako and accounts

        Returns
        -------
        list
            The list of tako.
            Each item in the list is key/value pairs.
            The keys are 'name' and 'balance'.
        """
        rows = list(self.cur.execute(
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

    def get_transaction(
            self,
            owner_id: str,
            date: Optional[str] = None) -> List[Dict[str, Any]]:
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
        rows = list(self.cur.execute(
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

    def get_name(self, owner_id: str) -> Tuple[str, str, int]:
        """Get the display name of the owner

        Parameters
        ----------
        owner_id : str
            Owner's ID.

        Returns
        -------
        Tuple
            (owner_id_str, name_str, badge_int)
        """
        rows = list(self.cur.execute(
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

        return rows[0]

    def _get_point(self):
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

    def set_area(
            self,
            date: Optional[str] = None,
            tz: timezone = JST) -> None:
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
            date = now.date().isoformat()

        if self.get_area(date):
            log.warning(f"{date} already exists.")
            return

        opening_datetime_tz = datetime.fromisoformat(
            f"{date} {takoconfig.OPENING_TIME}").replace(tzinfo=tz)
        closing_datetime_tz = datetime.fromisoformat(
            f"{date} {takoconfig.CLOSING_TIME}").replace(tzinfo=tz)

        opening_datetime_utc_str = tt.as_utc_str(opening_datetime_tz)
        closing_datetime_utc_str = tt.as_utc_str(closing_datetime_tz)
        try:
            area = self._get_point()
        except jma.JmaError as e:
            log.warning(f"can't get a pint of weather station: {e}")
            return

        self.cur.execute(
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
                takoconfig.COST_PRICE,
                takoconfig.SELLING_PRICE,
                takoconfig.SEED_MONEY,
                "coming_soon",
                0,
                ""
            ))

    def get_area(self, date: Optional[str] = None) -> Optional[Dict[str, Any]]:
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
        rows = list(self.cur.execute(
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

    def get_area_history(self) -> List[Dict[str, Any]]:
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
        """
        rows = list(self.cur.execute(
            """
            SELECT
                *
            FROM
                shop
            ORDER BY
                date_jst DESC
            """))
        if len(rows) == 0:
            return []
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

    def get_next_area(self) -> Dict[str, Any]:
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
        rows = list(self.cur.execute(
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

    def get_next_event(
            self,
            now: Optional[datetime] = None) -> Dict[str, Any]:
        """Get datetime of next event
        Before open: return today's event time
        Open: return tommorrow

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
        rows = list(self.cur.execute(
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
            raise TakoMarketError("multiple rows in 'shop' table: next event")

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

    def log_weather(self, date: datetime, weather: str) -> None:
        """Log weather

        Parameters
        ----------
        date : datetime
            UTC
        weather : str
        """
        self.cur.execute(
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


class TakoMarket:
    """The Tako shop

    Attributes
    ----------
    scheduler_state : str
        The state of scheduler thread
    stop : str
        The flag of stoping scheduler thread
    """
    def __init__(self):
        """Initialize each attributes and database
        """
        self.scheduler_state = "rannable"
        self.stop = False
        with MarketDB() as mdb:
            mdb.create_db()

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
        with MarketDB() as mdb:
            next_event = mdb.get_next_event()
            if not next_event["date"]:
                mdb.set_area()
                next_event = mdb.get_next_event()
            while not next_event["date"] and not self.stop and not onetime:
                log.warning("next event not found")
                time.sleep(30)
                mdb.set_area()
                next_event = mdb.get_next_event()

            mdb.cancel_and_refund(next_event["date"])

        self.scheduler_state = "running"
        log.debug("scheduler is running.")
        wait_sec = 0
        while not self.stop or onetime:
            time.sleep(wait_sec)
            wait_sec = 0
            with MarketDB() as mdb:
                next_event = mdb.get_next_event()
                if not next_event["date"]:
                    mdb.set_area()
                    next_event = mdb.get_next_event()
                    if next_event["date"]:
                        log.debug(
                            f"Next area is {self.get_next_area()['area']}")

            if not next_event["date"]:
                log.warning("next event not found")
                wait_sec = 60
                continue

            now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            if now == next_event["opening_datetime"]:
                if not open_done:
                    with MarketDB() as mdb:
                        area = mdb.get_area(next_event["date"])["area"]
                        log.debug(f"Now open in {area}")
                        mdb.cancel_and_refund(next_event["date"])
                        mdb.make_tako(next_event["date"])
                        mdb.set_area()
                        log.debug(
                            f"Next area is {mdb.get_next_area()['area']}")
                        open_done = True
            else:
                open_done = False

            if now == next_event["closing_datetime"]:
                if not closed_done:
                    try:
                        today_sales, weather = self.total_up_sales()
                    except (jma.JmaError, SunriseSunsetError) as e:
                        log.warning(f"can't get weather data: {e}")
                        wait_sec = 15
                        continue

                    with MarketDB() as mdb:
                        mdb.cancel_and_refund(next_event["date"])
                        area = mdb.get_area(next_event["date"])["area"]
                        log.debug(f"Now close in {area}")
                        if mdb.result(next_event["date"], today_sales):
                            log.debug("detected winner and restart market")
                        mdb.log_weather(now, weather)
                        log.debug(
                            f"today_sales: {today_sales}, weather: {weather}")
                        closed_done = True
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

    def total_up_sales(self):
        """Total up sales

        Returns
        -------
            (Today's sales, weather) : (int, str) or None
                                       Return None if can't get weather.
        """
        w = self.weather()
        sunshine_ratio = min(
            w['sunshine_hour'] /
            (w['day_length_hour'] -
             takoconfig.SUNSHINE_RATIO_CORRECTION_HOUR), 1.0)
        hard_rain_mm_par_hour = 5.0
        rainfall_max_mm = hard_rain_mm_par_hour*w['day_length_hour']
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

    def get_day_length_hour_today(self,
                                  latitude,
                                  longitude,
                                  time_difference_from_utc=+9):
        """Get day length today

        Parameters
        ----------
            latitude : float
            longitude : float
            time_difference_from_utc : int

        Returns
        -------
            day_length_hour : float
        """
        td = timedelta(hours=time_difference_from_utc)
        today = (datetime.utcnow() + td).date()
        midnigyt_utc = datetime.combine(today, datetime.min.time()) - td
        point = ephem.Observer()
        point.lat = str(latitude)
        point.lon = str(longitude)
        point.date = midnigyt_utc
        sun = ephem.Sun()
        day_length_day = point.next_setting(sun) - point.next_rising(sun)
        return day_length_day*24

    def weather(self):
        """Get weather

        Returns
        -------
            weather : dict or None
                      {
                          "title": str,
                          "sunshine_hour": float,
                          "rainfall_mm": float,
                          "day_length_hour": float,
                          "weather": str
                      }
                      Return None if can't get SYNOP weather data.
        """
        with MarketDB() as mdb:
            self.today_point = mdb.get_area()["area"]
        now = jma.Synop.synopday(point=self.today_point)
        point = now['data'][self.today_point]
        sunshine = float(point['sunshine']['duration']['value'])
        rainfall = now['data'][self.today_point]['rainfall']['totals']['value']
        if rainfall == "--":
            rainfall = 0
        rainfall = float(rainfall)

        meta = jma.PointMeta.get_point_meta(self.today_point)
        log.debug(f"{self.today_point}: {meta}")
        day_length_hour = self.get_day_length_hour_today(
            meta['lat'],
            meta['lng'])
        sunshine_ratio = sunshine/(day_length_hour -
                                   takoconfig.SUNSHINE_RATIO_CORRECTION_HOUR)

        weather = "cloudy"
        if sunshine_ratio > 0.1:
            weather = "sunny"
        rainfall_mm_par_hour = 2.0
        if rainfall > rainfall_mm_par_hour*day_length_hour:
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
    log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "tako_server")

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
