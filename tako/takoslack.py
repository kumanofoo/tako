#! /usr/bin/env python3
import logging
import os
import signal
from datetime import datetime, timedelta
import threading
import time
from threading import Event
from slack_bolt import App
from slack_bolt.error import BoltError
from slack_bolt.adapter.socket_mode import SocketModeHandler
from tako.takomarket import TakoMarket
from tako import jma, takoconfig
from tako.takoclient import TakoClient
from tako.takotime import JST

log = logging.getLogger(__name__)


bot_token = os.environ.get("SLACK_BOT_TOKEN")
if bot_token is None:
    log.critical("Environment value 'SLACK_BOT_TOKEN' is not defined")
    exit(1)
app_token = os.environ.get("SLACK_APP_TOKEN")
if app_token is None:
    log.critical("Environment value 'SLACK_APP_TOKEN' is not defined")
    exit(1)
bot_channel = os.environ.get("SLACK_TAKO_CHANNEL")

slack_app = App(token=bot_token)
slack_handler = SocketModeHandler(slack_app, app_token)


@slack_app.event("message")
def tako_reception(ack, say, message):
    ack()
    if message["channel_type"] != "im":
        return

    arg = message["text"]
    user_id = message["user"]
    user_info = get_user_info(user_id)
    user_name = user_info["profile"]["display_name"]
    tako_slack = TakoSlack(user_id, user_name)
    msg = tako_slack.interpret(arg)
    say("```" + "\n".join(msg) + "```")


class TakoSlack(TakoClient):
    def interpret(self, cmd):
        """Interpret command

        Returns
        -------
        messages : list of str
        """
        messages = []
        if cmd == "now":
            messages.extend(self.balance())
            messages.extend(self.transaction())
            messages.append("")
            messages.extend(self.top3())
            messages.append("")
            messages.extend(self.market())
        elif cmd.isdecimal():
            quantity = int(cmd)
            max_quantity = self.max_order_quantity()[0]
            if quantity >= 0 and quantity <= max_quantity:
                if self.order(quantity):
                    messages.extend([f"Ordered {quantity} tako"])
        elif cmd == "history":
            messages.extend(self.history())
        elif cmd == "help" or cmd == "?":
            messages.extend(self.help())

        return messages

    def balance(self):
        """Show the balance

        Returns
        -------
        message : list of str
        """
        message = []
        condition = TakoMarket.condition(self.my_id)
        if condition:
            message.append(
                f"Balance: {condition['balance']} JPY / "
                f"{int(condition['balance']/takoconfig.COST_PRICE)} takos")
        else:
            message.append("your account is not found.\n")
            message.append("open new account.")

        return message

    def transaction(self):
        """Show latest transaction.

        Returns
        -------
        message : list of str
        """
        transaction = self.latest_transaction()
        if transaction:
            market = TakoMarket.get_area(transaction["date"])
            transaction_str = [
                "Latest transaction:",
                f"  Date: {market['date']}",
                f"  Place: {market['area']}",
                f"  Status: {transaction['status']}",
                f"  Sales: {transaction['sales']}",
                f"  Ordered: {transaction['quantity_ordered']}",
                f"  In stock: {transaction['quantity_in_stock']}",
                f"  Weather: {transaction['weather']}",
                f"  Max: {market['sales']}",
            ]
        else:
            transaction_str = []

        return transaction_str

    def history(self, number=None, reverse=True):
        """Show transaction history

        Returns
        -------
        message : list of str
        """
        transactions = TakoMarket.get_transaction(self.my_id)

        messages = []
        messages.append("-"*35)
        messages.append("DATE       Place  WX")
        messages.append("ORD STK SALES/MAX STS")
        messages.append("-"*35)
        for n, t in enumerate(sorted(transactions,
                              key=lambda x: x["date"],
                              reverse=reverse)):
            if n == number:
                break
            area = t["area"] + "　"*(4-len(t["area"]))
            messages.append(
                "%s %4s %-7s" % (
                    t['date'],
                    area,
                    t['weather']))
            messages.append(
                "%3d %3d %5d/%-3d %-8s\n" % (
                    t['quantity_ordered'],
                    t['quantity_in_stock'],
                    t['sales']/takoconfig.SELLING_PRICE,
                    t['max_sales'],
                    t['status']))
        messages.append("-"*35)

        return messages

    def top3(self):
        """Show top 3 owners

        Returns
        -------
        message : list of str
        """
        messages = ["Top 3 owners:"]
        ranking = self.ranking()
        for i, owner in enumerate(ranking):
            if i == 3:
                break
            messages.append(f"  {owner['name']}: {owner['balance']} JPY")

        return messages

    def get_weather_forecast(self, name):
        """Show weather forecast.

        Parameters
        ----------
        name : str
            The name of The place.
        """
        messages = []
        meta = jma.PointMeta.get_point_meta(name)
        f = jma.Forecast.get_forecast(meta['class10s'])
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

    def market(self):
        """Show market

        Returns
        -------
        messages : list of str
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
                forecast = self.get_weather_forecast(area["area"])
                messages.extend(["  "+m for m in forecast])
            except jma.JmaError as e:
                log.warning(f"can't get weather forecast: {e}")

        return messages

    def help(self):
        """Show help

        Returns
        -------
        messages : list of str
        """
        messages = []
        messages.append("now : Show Tako Market Information.")
        messages.append("<Number> : Order tako.")
        messages.append("history : Show History of Transactions.")
        messages.append("help : Show this message.")

        return messages


def get_user_info(user):
    user_info = None
    try:
        result = slack_app.client.users_info(user=user)
        if result["ok"]:
            user_info = result["user"]
        else:
            log.warning(f"can't get user info: {result['error']}")
    except BoltError as err:
        log.warning(f"can't get user info: {err}")

    return user_info


class News:
    """Send Takoyaki News to Slack

    Attributes
    ----------
    closed_news_expiration_days : int
    open_news_expiration_hours : int
    news : dict
        The latest news
    """
    def __init__(self,
                 closed_news_expiration_days=1,
                 open_news_expiration_hours=8):
        """Initialize each attributes
        """
        self.closed_news_expiration_days = closed_news_expiration_days
        self.open_news_expiration_hours = open_news_expiration_hours
        self.news = []

    def check_market(self):
        """Check Takoyaki market

        Returns
        -------
        text: list of str
            Takoyaki Market News
        """
        texts = []
        news = TakoMarket.get_area_history()
        if news is None:
            log.debug("no news")
            return

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

    def create_text(self, news_source):
        """Create text

        Parameters
        ----------
        news_source : dict
            'shop' record of tako DB
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
            text = (f"Market is closed in {news_source['area']} "
                    f"at {closing_dt_str}."
                    "\n"
                    f"Max sales: {news_source['sales']} "
                    f"Weather: {news_source['weather']}"
                    "\n"
                    "Top 3 Owners"
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
        if news_source["status"] == "canceled":
            text = (f"Market in {news_source['area']} at "
                    f"{news_source['date']} "
                    f"was canceled.")

        return text


class TakoSlackBot():
    def __init__(self):
        self.exit_loop = Event()
        self.bot_thrad = None
        self.bot_state = "runnable"

    def send_message(self, text):
        """Send message to Slack

        Parameters
        ----------
        text: str
        """
        try:
            result = slack_app.client.chat_postMessage(
                channel=bot_channel,
                text=text)
            if result["ok"] is False:
                log.warning(f"can't send message: {result['error']}")
        except BoltError as err:
            log.warning(f"can't send message: {err}")

    def bot(self, interval_of_checking_nows=60):
        """Start to run slack bot
            Stop bot to send SIGTERM
        """
        news = None
        if bot_channel:
            news = News()
        else:
            log.warning("Slack channel is not defined.")
            log.warning("Takoyaki News is closed.")

        try:
            slack_handler.connect()
            self.bot_state = "running"
            while not self.exit_loop.is_set():
                if news:
                    for n in news.check_market():
                        self.send_message(n)
                self.exit_loop.wait(interval_of_checking_nows)
        finally:
            slack_handler.close()
            log.info("Slack Bot stopped.")

    def run_bot(self):
        """Run Takoyaki Slack Bot
            Use stop_bot to stop the Slack bot
        """
        self.bot_state = "initializeing"
        self.bot_thread = threading.Thread(target=self.bot)
        self.bot_thread.start()
        log.info("Running Slack Bot")

    def stop_bot(self):
        """Stop Takoyaki Slack Bot
        """
        self.exit_loop.set()
        log.info("Stopping Slack Bot")
        self.bot_state = "stopping"
        self.bot_thread.join()
        self.exit_loop.clear()
        self.bot_state = "runnable"


def main():
    global log
    log = takoconfig.set_logging_level("TAKOSLACK_DEBUG", "takoslackbot")

    slackbot = TakoSlackBot()

    def signal_handler(signum, frame):
        """Signal handler
            Stopping Slack bot
        """
        log.info('Signal handler called with signal %d' % signum)
        slackbot.stop_bot()

    signal.signal(signal.SIGTERM, signal_handler)
    slackbot.run_bot()
    while slackbot.bot_state != "running":
        time.sleep(1)
    while slackbot.bot_state == "running":
        time.sleep(1)


if __name__ == "__main__":
    main()
