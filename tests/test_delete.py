#!/usr/bin/env python3

import sqlite3
from tako import takoconfig
from tako.takomarket import MarketDB
from tako.takoclient import TakoCommand
from tests.takodebug import DebugMarket
from pathlib import Path
import os
import re


class TestDelete:
    def count_table_records(self, table, owner_id):
        scrubbed_table = ''.join(c for c in table if re.match(
            r"[a-zA-Z0-9_]", c))
        with sqlite3.connect(takoconfig.TAKO_DB) as conn:
            rows = list(conn.execute(
                f"""
                SELECT
                    *
                FROM
                    {scrubbed_table}
                WHERE
                    owner_id=?
                """,
                (owner_id,)))
            return len(rows)

    def test_delete(self):
        takoconfig.TAKO_DB = Path("delete_test.db")
        if Path.exists(takoconfig.TAKO_DB):
            os.remove(takoconfig.TAKO_DB)
        OWNERS = 5
        QUANTITIES = [100, 200, 300, 400, 500]  # each owrner
        DAYS = 10
        TABLES = [
            # table, records before deleting, after
            ("records", int(DAYS/9), 0),
            ("tako_transaction", DAYS, 0),
            ("tako", 1, 0),
            ("accounts", 1, 0),
        ]

        market = DebugMarket(owner_num=OWNERS)
        owners = [TakoCommand(i, None) for i in market.owners]

        for day in range(DAYS):
            market.next_day()
            market.set_quantity(QUANTITIES)
            market.open()
            market.close()

        for o in owners:
            for table, expected, _ in TABLES:
                actual = self.count_table_records(table, o.my_id)
                assert actual == expected, f"{o.my_id} in '{table}'"

        with MarketDB() as mdb:
            actual = mdb.delete_account("")
            assert actual is None
            actual = mdb.delete_account("unknown_owner_id")
            assert actual is None

        for o in owners:
            with MarketDB() as mdb:
                actual = mdb.delete_account(o.my_id)
                assert actual == o.my_id
            for table, _, expected in TABLES:
                actual = self.count_table_records(table, o.my_id)
                assert actual == 0, f"{o.my_id} in '{table}' is not zero."

        if Path.exists(takoconfig.TAKO_DB):
            os.remove(takoconfig.TAKO_DB)


if __name__ == "__main__":
    test = TestDelete()
    test.test_delete()
