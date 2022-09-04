#! /usr/bin/env python3

import threading
import time
import logging
import signal
from datetime import datetime, timezone
from tako.takomarket import MarketDB
from tako.takoclient import TakoClient
from tako import takoconfig
from tako.takoconfig import TAKOBOT
from tako.takotime import JST
from tako.jma import JmaError

log = logging.getLogger(__name__)


class Takobot(TakoClient):
    """Takobot
    """
    EXPECTED = {
        "晴れ": [440, 420, 430, 390, 450, 450, 300, 300, 300, 300, 300],
        "くもり": [340, 340, 320, 300, 270, 250, 200, 140, 100, 100, 100],
        "雨": [300, 330, 240, 200, 160, 220, 180, 150, 110, 100, 100],
        "雪": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
    }
    WEATHER = [
        "晴れ",
        "くもり",
        "雨",
        "雪",
    ]

    def __init__(self, bot_id=TAKOBOT["ID"], bot_name=TAKOBOT["name"]):
        """Initialize bot ID and name

        Parameters
        ----------
        bot_id : str
        bot_name : str
        """
        self.stop = threading.Event()
        super().__init__(bot_id, bot_name)

    def how_many_order(self):
        """Calculate how many Tako order.

        Returns
        -------
        quantity : int
        """
        min_sales = (takoconfig.MAX_SALES["cloudy"] +
                     takoconfig.MAX_SALES["rainy"])
        try:
            forecast = self.get_forecast_in_next_area()
        except JmaError as e:
            log.warning(f"can't get weather forecast: {e}")
            return min(self.max_order_quantity()[0], min_sales)

        expected = 0
        for w in Takobot.WEATHER:
            if forecast["weather"]["text"].startswith(w):
                count = 0
                for date, pops in forecast["pops"]:
                    if date.hour < 6:
                        continue
                    expected += Takobot.EXPECTED[w][int(int(pops)/10)]
                    count += 1
                break
        return min(self.max_order_quantity()[0],
                   max(int(expected/count), min_sales))

    def bot(self):
        """Thread of Tako Bot
        """
        self.bot_state = "running"
        log.debug("Tako Bot is running.")
        while not self.stop.is_set():
            with MarketDB() as mdb:
                next_area = mdb.get_next_area()
                opening_time = next_area["opening_datetime"]
                if opening_time is None:
                    opening_time = datetime.fromtimestamp(0, timezone.utc)
                market_status = next_area["status"]
                now = datetime.now(JST)
                if opening_time > now and market_status == "coming_soon":
                    order = min(
                        self.how_many_order(),
                        self.max_order_quantity()[0])
                    mdb.set_tako_quantity(
                        self.my_id,
                        next_area["date"],
                        order)
                    log.debug(
                        f"ordered {order} takos for the market "
                        f"in {next_area['area']} on "
                        f"{opening_time.astimezone(JST).strftime('%Y-%m-%d')}")
                    wait = min((opening_time - now).seconds, 30*60)
                else:
                    wait = 60*60
                    log.debug("no next market")
            log.debug(f"set wake up timer for {int(wait/60)} minutes...")
            self.stop.wait(wait)

    def run_bot(self):
        """Run a Tako Bot
            Use stop_bot() To stop the Tako Bot
        """
        self.bot_thread = threading.Thread(target=self.bot)
        self.bot_state = "initializeing"
        log.debug("Tako Bot is starting...")
        self.bot_thread.start()

    def stop_bot(self):
        """Stop Tako Bot
        """
        self.stop.set()
        self.bot_thread.join()
        log.debug("Tako Bot has stoped.")
        self.bot_state = "runnable"
        self.stop.clear()

    def signal_handlar(self, signum, frame):
        """Signal handlar for stoping Takobot's therad.
        """
        signame = signal.Signals(signum).name
        log.debug(f"signal handlar received {signame}.")
        self.stop_bot()


def main():
    global log
    log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "takobot")

    tako = Takobot()
    for sig in [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, tako.signal_handlar)

    transaction = tako.latest_transaction()
    print("----- transaction -----")
    print(transaction)
    tako.run_bot()
    while tako.bot_state != "running":
        time.sleep(1)
    while tako.bot_state == "running":
        time.sleep(5)
    transaction = tako.latest_transaction()
    print("----- transaction -----")
    print(transaction)


if __name__ == "__main__":
    main()
