#! /usr/bin/env python3

import threading
import time
import logging
import signal
from datetime import datetime, timezone, timedelta
from tako.takomarket import TakoMarket
from tako.takoclient import TakoClient

log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=+9), 'JST')


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

    def how_many_order(self):
        """Calculate how many Tako order.

        Returns
        -------
        quantity : int
        """
        expected = 0
        forecast = self.get_forecast_in_next_area()
        for w in Takobot.WEATHER:
            if forecast["weather"]["text"].startswith(w):
                count = 0
                for date, pops in forecast["pops"]:
                    if date.hour < 6:
                        continue
                    expected += Takobot.EXPECTED[w][int(int(pops)/10)]
                    count += 1
                break
        return min(self.max_order_quantity()[0], int(expected/count))

    def bot(self):
        """Thread of Tako Bot
        """
        self.bot_state = "running"
        log.debug("Tako Bot is running.")
        while not self.finish.is_set():
            next_area = TakoMarket.get_next_area()
            opening_time = next_area["opening_datetime"]
            if opening_time is None:
                opening_time = datetime.fromtimestamp(0, timezone.utc)
            market_status = next_area["status"]
            now = datetime.now(JST)
            if opening_time > now and market_status == "coming_soon":
                order = min(
                    self.how_many_order(),
                    self.max_order_quantity()[0])
                TakoMarket.set_tako_quantity(
                    self.my_id,
                    next_area["date"],
                    order)
                log.debug(
                    f"ordered {order} takos for the market "
                    f"in {next_area['area']} "
                    f"on {opening_time.astimezone(JST).strftime('%Y-%d-%m')}")
                wait = min((opening_time - now).seconds, 30*60)
            else:
                wait = 60*60
                log.debug("no next market")
            log.debug(f"set wake up timer for {int(wait/60)} minutes...")
            self.finish.wait(wait)

    def run_bot(self):
        """Run a Tako Bot
            Use finish_bot() To the Tako Bot
        """
        self.finish = threading.Event()
        self.bot_thread = threading.Thread(target=self.bot)
        self.bot_state = "initializeing"
        log.debug("Tako Bot is starting...")
        self.bot_thread.start()

    def finish_bot(self):
        """Finish Tako Bot
        """
        self.finish.set()
        self.bot_thread.join()
        log.debug("Tako Bot has stoped.")
        self.bot_state = "runnable"
        self.finish.clear()

    def signal_handlar(self, signum, frame):
        """Signal handlar for finishing Takobot's therad.
        """
        signame = signal.Signals(signum).name
        log.debug(f"signal handlar received {signame}.")
        self.finish_bot()


def main():
    logging.basicConfig(level=logging.DEBUG)

    tako = Takobot("MS-06S", "Char")
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

    # print(tako.max_order_quantity())
    # print(TakoMarket.condition_all())
    # print(tako.ranking())
    # print(f"I will make {tako.how_many_order()} tako.")
    # tako.get_weather_forecast("むつ")
    # print(tako.how_many_make("晴れ", "10%"))


if __name__ == "__main__":
    main()
