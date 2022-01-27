#!/usr/bin/env python3

import sqlite3
from tako.takomarket import TakoMarket
from tako import takoconfig
from pathlib import Path
import os
import subprocess


class TestRecords:
    def id_name(self, i, begin=1000):
        serial = i+begin
        return f"id{serial}", f"name{serial}"

    def id2serial(self, owner_id, begin=1000):
        serial = owner_id.split("id")[1]
        return int(serial)-begin

    def balances_ap(self, n, difference=5000):
        """Calculate Arithmetic progression

        Parameters
        ----------
        n : int
            n-th
        difference : int

        Returns
        -------
        n-th value : int
        """
        return takoconfig.SEED_MONEY + n*difference

    def balances_mod(self, n, modulus=3, difference=15000):
        """Calculate Arithmetic progression with modulo

        Parameters
        ----------
        n : int
            n-th
        modulus : int
        difference : int

        Returns
        -------
        n-th value : int
        """
        return (n % modulus + 1)*difference

    def initialize_db(self, n, func=balances_ap):
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            for i in range(n):
                owner_id, name = self.id_name(i)
                conn.execute(
                    """
                    INSERT INTO
                        accounts
                    VALUES
                        (?, ?, ?,
                         strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                    """,
                    (owner_id, name, 0))
                conn.execute(
                    """
                    INSERT INTO
                        tako
                    VALUES
                        (?, ?,
                         strftime('%Y-%m-%dT%H:%M:%f', 'now'))
                    """,
                    (owner_id, func(i)))
        return n

    def set_balance(self, n, func=balances_ap):
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            for i in range(n):
                owner_id, _ = self.id_name(i)
                conn.execute(
                    """
                    UPDATE
                        tako
                    SET
                        balance = ?
                    WHERE
                        owner_id = ?
                    """,
                    (func(i), owner_id))

    def show_table(self, table):
        """Show table via stdout

        Parameters
        ----------
        table : str
        """
        print(f"[{table}]")
        subprocess.run([
            "sqlite3",
            str(takoconfig.TAKO_DB),
            ".headers on",
            ".mode column",
            f"""
            SELECT
                *
            FROM
                {table}
            """])

    def table2dict(self, table):
        table_list = ["tako", "accounts", "records"]
        if table not in table_list:
            print(f"{table} is not found in list")
            return []

        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT
                    *
                FROM
                    {table}
                """)
            return [dict(r) for r in rows]
        return []

    def test_records(self):
        takoconfig.TAKO_DB = Path("debug.db")
        if Path.exists(takoconfig.TAKO_DB):
            os.remove(takoconfig.TAKO_DB)

        tm = TakoMarket()
        n = 10
        self.initialize_db(n, func=self.balances_ap)
        date_jst = ["2021-01-01", "2021-09-09"]

        takoconfig.TARGET = 30000
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            res = tm.detect_winner_and_restart(conn, date_jst[0])
        assert res is True
        if res:
            owners = self.table2dict("tako")
            for o in owners:
                assert o["balance"] == takoconfig.SEED_MONEY
            owners = [o for o in self.table2dict("records")
                      if o["date_jst"] == date_jst[0]
                      and o["balance"] >= takoconfig.TARGET]
            expected_owners = [
                i for i in range(n) if self.balances_ap(i) >= takoconfig.TARGET
            ]
            badge_owners = [o for o in self.table2dict("accounts")
                            if o["badge"] == 1]
            for o, e, b in zip(owners, expected_owners, badge_owners):
                assert o["owner_id"] == self.id_name(e)[0]
                assert o["balance"] == self.balances_ap(e)
                assert b["owner_id"] == self.id_name(e)[0]

        self.set_balance(n, func=self.balances_mod)
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            res = tm.detect_winner_and_restart(conn, date_jst[1])
        assert res is True
        # show_table("records")
        parameters = [
            ({"date_jst": None, "top": float("inf"), "winner": True},
             (2, 5, 6)),
            ({"date_jst": date_jst[1], "top": float("inf"), "winner": True},
             (1, 0, 6)),
            ({"date_jst": date_jst[0], "top": float("inf"), "winner": False},
             (1, 10, 0)),
            ({"date_jst": date_jst[0], "top": 3, "winner": False},
             (1, 3, 0)),
            ({"date_jst": date_jst[1], "top": 4, "winner": True},
             (1, 0, 6)),
        ]
        for param, expected in parameters:
            actual = TakoMarket.get_records(**param)
            assert len(actual) == expected[0]
            assert len(actual.get(date_jst[0], [])) == expected[1]
            assert len(actual.get(date_jst[1], [])) == expected[2], f"{param}"


if __name__ == "__main__":
    print("Run test...", end="")
    rt = TestRecords()
    rt.test_records()
    print(" done.")
