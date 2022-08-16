import logging
import os
import signal
from datetime import datetime, timedelta
import threading
import time
import requests
from threading import Event
from typing import Dict, List, Optional, Any, Tuple
import zulip
from tako.takomarket import TakoMarket, TakoMarketNoAccountError
from tako.takoclient import TakoClient
from tako import takoconfig, jma
from tako.takotime import JST

log = logging.getLogger(__name__)

DEFAULT_DISPLAY_NAME = "Ray"


class TakoZulipError(Exception):
    pass


class TakoZulip(TakoClient):
    def __init__(self, my_id, my_name) -> None:
        super().__init__(my_id, my_name)
        self.commands = {
            "info": self.info,
            "history": self.history,
            "help": self.help,
            "?": self.help,
        }

    def interpret(self, cmd: str) -> List[str]:
        """Interpret command

        Returns
        -------
        message : list of str
        """
        if not cmd:
            return []

        argv = cmd.split()
        c = self.commands.get(argv[0])
        if c:
            messages = c(argv)
        elif cmd.isdecimal():
            messages = self.order_tako(int(cmd))
        else:
            messages = []

        return messages

    def order_tako(self, quantity: int) -> List[str]:
        messages = []
        max_quantity = self.max_order_quantity()[0]
        if quantity >= 0 and quantity <= max_quantity:
            if self.order(quantity):
                messages.append(f"Ordered {quantity} tako")
        return messages

    def info(self, argv: List[str]) -> List[str]:
        messages = []
        messages.append(self.name_with_badge())
        messages.extend(self.balance())
        messages.append("**Latest Transaction**")
        messages.extend(self.transaction())
        messages.append("")
        messages.append("**Top 3 owners**")
        messages.extend(self.top3())
        messages.append("")
        messages.append("**Market Information**")
        messages.extend(self.market())
        return messages

    def help(self, _) -> List[str]:
        return [
            "info : Show Tako Market Information.",
            "<Number> : Order tako.",
            "history : Show History of Transactions.",
            "DELETE : Delete Takoyaki account.",
            "help : Show this message.",
        ]

    def name_with_badge(self) -> str:
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

    def balance(self) -> List[str]:
        """Show the balance

        Returns
        -------
        message : list of str

        Example
        -------
        Balance: 5000 JPY / 125 takos
        or
        Your account is not found.
        New account is open.
        """
        messages = []
        condition = TakoMarket.condition(self.my_id)
        if condition:
            messages.append(
                f"Balance: {condition['balance']} JPY / "
                f"{int(condition['balance']/takoconfig.COST_PRICE)} takos")
        else:
            messages.append("Your account is not found.\n")
            messages.append("New account is open.")

        return messages

    def transaction(self) -> List[str]:
        """Show latest transaction.

        Returns
        -------
        messages : list of str
        """
        transaction = self.latest_transaction()
        if transaction:
            market = TakoMarket.get_area(transaction["date"])
            transaction_str = [
                f"Date: {market['date']}",
                f"Place: {market['area']}",
                f"Status: {transaction['status']}",
                f"Sales: {transaction['sales']}",
                f"Ordered: {transaction['quantity_ordered']}",
                f"In stock: {transaction['quantity_in_stock']}",
                f"Weather: {transaction['weather']}",
                f"Max: {market['sales']}",
            ]
        else:
            transaction_str = []

        return transaction_str

    def top3(self) -> List[str]:
        """Show top 3 owners

        Returns
        -------
        message : list of str

        Example
        -------
        id1001: 10000 JPY
        id1002: 9000 JPY
        id1003: 5000 JPY
        """
        messages = []
        ranking = self.ranking()
        for i, owner in enumerate(ranking):
            if i == 3:
                break
            messages.append(f"{owner['name']}: {owner['balance']} JPY")

        return messages

    def get_weather_forecast(self, name: str, date_jst: str) -> List[str]:
        """Show weather forecast.

        Parameters
        ----------
        name : str
            The name of The place.
        date_jst : str

        Example
        -------
        24日 月曜日 山形
        くもり後晴れ明け方一時雪
        06  12  18
        20% 10% 10%
        """
        messages = []
        meta = jma.PointMeta.get_point_meta(name)
        f = jma.Forecast.get_forecast(meta['class10s'], date_jst)
        dow = self.DOW_JA[int(f["weather"]["datetime"].strftime("%w"))]
        weather_datetime = f["weather"]["datetime"].strftime(
            f"%e日 {dow}").strip()
        forecast_text = "".join(f["weather"]["text"].split())
        messages.append(f"{weather_datetime} {name}")
        messages.append(f"{forecast_text}")
        times = ""
        pops = ""
        for (t, p) in f["pops"]:
            if t.hour < 6:
                continue
            times += "%2s  " % t.strftime("%H")
            pops += "%2s%% " % p
        messages.append(times)
        messages.append(pops)

        return messages

    def market(self) -> List[str]:
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
        messages = []
        area = TakoMarket.get_next_area()
        if area["date"]:
            messages.append(f"Next: {area['area']}")
            tz = (+9, "JST")
            opening_time_str = self.astimezone(area['opening_datetime'], tz=tz)
            closing_time_str = self.astimezone(area['closing_datetime'], tz=tz)
            messages.append(f"  Open: {opening_time_str}")
            messages.append(f"  Close: {closing_time_str}")
            try:
                forecast = self.get_weather_forecast(
                    area["area"],
                    area["date"])
                messages.extend(["  "+m for m in forecast])
            except jma.JmaError as e:
                log.warning(f"can't get weather forecast: {e}")

        return messages

    def history(self, argv: List[str]) -> List[str]:
        """Show transaction history

        Parameters
        ----------
        argv : list of str
            argv[0] : "history"
            argv[1] : integer or "all"

        Returns
        -------
        message : list of str

        Example
        -----------------------------------
        DATE       Place  WX
        ORD STK SALES/MAX STS
        -----------------------------------
        2021-10-10 帯広　 Sunny
        125 125   125/500 closed
        -----------------------------------
        """
        if len(argv) > 1:
            if argv[1] == "all":
                num = None
            else:
                try:
                    num = int(argv[1])
                except ValueError:
                    log.debug(f"Invalid history number: '{argv[1]}'")
                    num = -1
        else:
            num = takoconfig.HISTORY_COUNT
        if num == -1:
            return ["Usage: history [number]"]

        transactions = TakoMarket.get_transaction(self.my_id)
        records = TakoMarket.get_owner_records(self.my_id)
        header = ["-"*35,
                  "DATE       Place  WX",
                  "ORD STK SALES/MAX STS",
                  "-"*35]
        messages = []
        messages.extend(header)
        for n, t in enumerate(sorted(transactions,
                                     key=lambda x: x["date"],
                                     reverse=True)):
            if n == num:
                break
            area = t['area'] + "　"*(4-len(t['area']))
            messages.append(
                "%s %4s %-7s" % (
                    t['date'],
                    area,
                    t['weather']))
            m = "%3d %3d %5d/%-3d %-8s" % (
                t['quantity_ordered'],
                t['quantity_in_stock'],
                t['sales']/takoconfig.SELLING_PRICE,
                t['max_sales'],
                t['status'])

            if t['status'] == "closed_and_restart":
                messages.append(m)
                record = records[t['date']]
                rank = record['rank']
                suffix = {1: "st🐙", 2: "nd", 3: "rd"}.get(rank, "th")
                balance = record['balance']
                messages.append(
                    f"You were {rank}{suffix} with {balance} JPY.\n")
            else:
                messages.append(m+"\n")
        messages.append("-"*35)

        return messages


class News:
    """Send Takoyaki News to Zulip

    Attributes
    ----------
    closed_news_expiration_days : int
    open_news_expiration_hours : int
    news : dict
        The latest news
    """
    def __init__(self,
                 closed_news_expiration_days: int = 1,
                 open_news_expiration_hours: int = 8):
        """Initialize each attributes
        """
        self.closed_news_expiration_days = closed_news_expiration_days
        self.open_news_expiration_hours = open_news_expiration_hours
        self.news: List[Dict[str, Any]] = []

    def check_market(self) -> List[str]:
        """Check Takoyaki market

        Returns
        -------
        text: list of str
            Takoyaki Market News
        """
        texts: List[str] = []
        news = TakoMarket.get_area_history()
        if news is None:
            log.debug("no news")
            return texts

        if len(self.news) == 0:
            latest = news[0:1]
            log.debug("Has got first news")
        else:
            oldest_date = min(n["date"] for n in self.news)
            latest = [n for n in news if n["date"] >= oldest_date]

        log.debug(f"latest: {latest}")
        for n in latest:
            published_news = [
                o for o in self.news if o.get("date") == n["date"]]
            if len(published_news) == 0:
                p = {}
            else:
                if len(published_news) > 1:
                    log.error("there are same dates")
                p = published_news[0]
                if n == p:
                    log.debug("same news")
                    continue
                if n["status"] == p.get("status"):
                    log.debug("almost same news")
                    continue

            text = self.create_text(n)
            if text:
                texts.append(text)

        if latest:
            self.news = latest

        return texts

    def name_balance_badge(self, record: dict) -> str:
        name = record["name"]
        balance = record["balance"]
        badge = record['badge']
        text = f"{name} : {balance} JPY"
        text += "\n "
        text += TakoClient.badge_to_emoji(badge)
        return text

    def create_text(self, news_source: Dict[str, Any]) -> str:
        """Create text

        Parameters
        ----------
        news_source : dict
            'shop' record of tako DB

        Returns
        ----------
        text : str
        """
        text = ""
        now = datetime.now(JST)
        if news_source["status"] == "coming_soon":
            jst = news_source['opening_datetime'].astimezone(JST)
            if jst < now:
                log.debug("Old news of 'comming_soon'")
                return text
            opening_dt_str = jst.strftime("%Y-%m-%d %H:%M")
            text = (f"Market in {news_source['area']} will open soon "
                    f"at {opening_dt_str}.")
        if news_source["status"] == "open":
            jst = news_source['opening_datetime'].astimezone(JST)
            if jst < now - timedelta(hours=self.open_news_expiration_hours):
                log.debug("Old news of 'open'")
                return text
            opening_dt_str = jst.strftime("%Y-%m-%d %H:%M")
            text = (f"Market is opening in "
                    f"{news_source['area']} at {opening_dt_str}.")
        if news_source["status"] == "closed":
            jst = news_source['closing_datetime'].astimezone(JST)
            if jst < now - timedelta(days=self.closed_news_expiration_days):
                log.debug("Old news of 'closed'")
                return text
            closing_dt_str = jst.strftime("%Y-%m-%d %H:%M")
            records = TakoMarket.get_records(
                date_jst=news_source["date"],
                winner=False)
            if len(records) == 0:
                """
                Example
                -------

                Market is closed in 網代 at 2021-10-10 18:00.
                Max sales: 309 Weather: cloudy
                Top 3 Owners
                id1001: 51290 JPY
                id1002: 33700 JPY
                id1003: 28750 JPY
                """
                text = (f"Market is closed in {news_source['area']} "
                        f"at {closing_dt_str}."
                        "\n"
                        f"Max sales: {news_source['sales']} "
                        f"Weather: {news_source['weather']}"
                        "\n"
                        "**Top 3 Owners**"
                        "\n")
                ranking = sorted(
                    TakoMarket.condition_all(),
                    key=lambda x: x['balance'],
                    reverse=True
                )
                for i, owner in enumerate(ranking):
                    if i == 3:
                        break
                    text += f"  {owner['name']}: {owner['balance']} JPY"
                    text += "\n"
            else:
                """
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
                text = "This season is over. And next season has begun."
                balance = -float("inf")
                for r in records[news_source["date"]]:
                    if r["balance"] < r["target"]:
                        if balance > r["balance"]:
                            break
                        if balance == -float("inf"):
                            text += "\n"
                            text += "\n"
                            text += "The following is the close to the target."
                        balance = r["balance"]
                    text += "\n"
                    text += self.name_balance_badge(r)
        if news_source["status"] == "canceled":
            text = (f"Market in {news_source['area']} at "
                    f"{news_source['date']} "
                    f"was canceled.")

        return text


class TakoZulipBot:
    @staticmethod
    def check_environment_variables() -> bool:
        try:
            _ = os.environ["ZULIP_EMAIL"]
            _ = os.environ["ZULIP_API_KEY"]
            _ = os.environ["ZULIP_SITE"]
            _ = os.environ["ZULIP_TAKO_STREAM"]
        except KeyError:
            return False
        return True

    def __init__(self):
        self.client = zulip.Client()
        self.zulipbot_thread = None
        self.zulipbot_state = "runnable"
        self.my_email = os.environ.get("ZULIP_EMAIL")
        log.debug(f"Zulip bot ID: {self.my_email}")
        self.client_id = self.my_email.split("@")[1]
        log.debug(f"Zulip client ID: {self.client_id}")
        try:
            tako_stream = os.environ["ZULIP_TAKO_STREAM"]
        except KeyError:
            self.stream = None
            self.topic = None
            self.news_feed_state = "closed"
            raise TakoZulipError(
                "Environment variable 'ZULIP_TAKO_STREAM' is not defined.")
        try:
            self.stream, self.topic = tako_stream.split(":")
        except ValueError:
            self.stream = None
            self.topic = None
            self.news_feed_state = "closed"
            raise TakoZulipError(
                "'ZULIP_TAKO_STREAM' value format is invalid.")
        self.exit_loop = Event()
        self.news_feed_thread = None
        self.news_feed_state = "runnable"
        self.interval_of_checking_news_sec = 60*30  # default

    def news_feed(self) -> None:
        if self.stream:
            news = News()
        else:
            log.warning(
                "Environment variable 'ZULIP_TAKO_STREAM' is not defined.")
            log.warning("Takoyaki News is closed.")

        self.news_feed_state = "running"
        while not self.exit_loop.is_set():
            if news:
                text = "\n\n".join(news.check_market())
                if text:
                    result = self.client.send_message({
                        "type": "stream",
                        "to": self.stream,
                        "topic": self.topic,
                        "content": text,
                    })
                    if result["result"] != "success":
                        log.warning(result["msg"])
                    log.debug(result)
            self.exit_loop.wait(self.interval_of_checking_news_sec)
        log.info("Zulip news feed stopped")

    def call_on_each_message(self) -> None:
        def do_register() -> Tuple[str, int]:
            while True:
                res = self.client.register(
                    event_types=["message"],
                    # narrow=[["is", "private"]])
                    )
                if "error" in res["result"]:
                    log.warning(f"Server returned error:\n{res['msg']}")
                    time.sleep(1)
                else:
                    return (res["queue_id"], res["last_event_id"])
        queue_id = None
        self.zulipbot_state = "running"
        while not self.exit_loop.is_set():
            if queue_id is None:
                (queue_id, last_event_id) = do_register()
            try:
                res = self.client.get_events(
                    queue_id=queue_id,
                    last_event_id=last_event_id)
            except (
                requests.exceptions.Timeout,
                requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
            ) as e:
                log.warning(f"Connection error fetching events:\n {e}")
                time.sleep(1)
                continue
            except Exception as e:
                log.warning(f"Unexpected error:\n {e}")
                time.sleep(1)
                continue
            if "error" in res["result"]:
                if res["result"] == "http-error":
                    log.warning("HTTP error fetching events -- "
                                "probably a server restart")
                else:
                    log.warning(f"Server returned error:\n{res['msg']}")
                    if (res.get("code") == "BAD_EVENT_QUEUE_ID" or
                            res["msg"].startswith("Bad event queue id:")):
                        queue_id = None
                    time.sleep(1)
                    continue
            for event in res["events"]:
                last_event_id = max(last_event_id, int(event["id"]))
                if event["type"] == "message":
                    self.handler(event["message"])
        log.info("Zulipbot stopped")

    def run_bot(self,
                interval_of_checking_news_sec: Optional[int] = None) -> None:
        if interval_of_checking_news_sec:
            self.interval_of_checking_news_sec = interval_of_checking_news_sec
        self.news_feed_state = "initializing"
        self.news_feed_thread = threading.Thread(target=self.news_feed)

        self.zulipbot_state = "initializing"
        self.zulipbot_thread = threading.Thread(
            target=self.call_on_each_message
        )

        self.news_feed_thread.start()
        log.info("Running Zulip news feed")

        self.zulipbot_thread.start()
        log.info("Running Zulipbot")

    def stop_bot(self) -> None:
        self.exit_loop.set()
        log.info("Stopping Zulip news feed")
        log.info("Stopping Zulipbot")
        self.news_feed_state = "stopping"
        self.zulipbot_state = "stopping"
        self.news_feed_thread.join()
        self.zulipbot_thread.join()
        self.exit_loop.clear()
        self.news_feed_state = "runnable"
        self.zulipbot_state = "runnable"

    def handler(self, msg: Dict[str, Any]) -> None:
        log.debug(msg)
        response = self.bot_reception(msg)
        log.debug(f"response: {response}")
        if response:
            result = self.client.send_message({
                "type": "private",
                "to": msg["sender_email"],
                "content": response,
            })
            if result["result"] != "success":
                log.warning(result["msg"])
            log.debug(result)

    def bot_reception(self, message: dict) -> str:
        """Zulip Event Handler

        Parameters
        ----------
        message : dict
            Zulip message

        Returns
        -------
        responst : str
        """
        if self.my_email is None:
            log.warning(
                "Environment variable 'ZULIP_EMAIL' is not defined.")
            return ""
        if message["sender_email"] == self.my_email:
            return ""
        if message["type"] != "private":
            # private message only
            return "Sorry. Could you talk to you in private."

        arg = message["content"]
        user_id = f"{message['sender_id']}@{self.client_id}"
        user_name = None
        try:
            _ = TakoMarket.get_name(user_id)
        except TakoMarketNoAccountError:
            # New user
            cmd = arg.split()
            if len(cmd) == 0:
                return ""
            if cmd[0] == "JOIN":
                user_name = arg.lstrip("JOIN").strip()
                if user_name == "":
                    full_name = message.get("sender_full_name")
                    if full_name:
                        user_name = full_name
                    else:
                        log.warning("cannot find user name")
                        user_name = DEFAULT_DISPLAY_NAME
                _ = TakoZulip(user_id, user_name)
                return (f"Thank you for joining us, {user_name}."
                        " If you need something, try to enter 'help'.")
            else:
                return ("Hi there! I don't think we've met before.\n"
                        "Please try to use the command: JOIN [display name].\n"
                        "You can also use 'JOIN' without 'dispay name'"
                        " if you want to use ZULIP FULL NAME.")
        # Delete account
        if arg == "DELETE":
            return ("If you would like to delete your Takoyaki account, "
                    "enter 'DELETE DELETE'.")
        if arg == "DELETE DELETE":
            if TakoMarket.delete_account(user_id) == user_id:
                log.info(f"{user_id}'s account was deleted")
                return "Your Takoyaki account was deleted."
            else:
                log.warning(f"can't delete account {user_id}")
                return "Your Takoyaki account was NOT able to be deleted."
        # Interpret command
        tako_zulip = TakoZulip(user_id, user_name)
        msg = tako_zulip.interpret(arg)
        if msg:
            return "\n".join(msg)
        else:
            return f"Unknown command: '{arg}'"


def main():
    global log
    log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "takozulipbot")

    zulipbot = TakoZulipBot()

    def signal_handler(signum, frame) -> None:
        """Signal handler
            Stopping Slack bot
        """
        log.info('Signal handler called with signal %d' % signum)
        zulipbot.stop_bot()

    signal.signal(signal.SIGTERM, signal_handler)
    zulipbot.run_bot()
    while (zulipbot.news_feed_state != "running" and
           zulipbot.zulipbot_state != "running"):
        time.sleep(1)
    while (zulipbot.news_feed_state == "running" or
           zulipbot.zulipbot_state == "running"):
        time.sleep(1)


if __name__ == "__main__":
    main()
