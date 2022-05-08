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
import tako
from tako.takomarket import TakoMarket
from tako import jma, takoconfig
from tako.takoclient import TakoClient
from tako.takotime import JST

log = logging.getLogger(__name__)

bot_channel = os.environ.get("SLACK_TAKO_CHANNEL")
slack_app = App()
slack_handler = SocketModeHandler(slack_app)


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


def create_home_view(user_id):
    view = {}
    view["type"] = "home"
    view["blocks"] = []

    tako_slack = TakoSlack(user_id, None)
    (_id, name, badges, *_) = TakoMarket.get_name(user_id)
    badges_str = TakoClient.badge_to_emoji(badges)
    view["blocks"].append({
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": f"Hey {name}!\n{badges_str}\n\n",
            "emoji": True
        }
    })
    condition = TakoMarket.condition(user_id)
    balance = condition["balance"]
    takos = int(condition["balance"]/takoconfig.COST_PRICE)
    view["blocks"].append({
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": f"Balance: {balance} JPY / {takos} takos"
        }
    })
    news = News()
    news_str = "\n".join(news.check_market())
    if news_str == "":
        news_str = "Umm... No news..."
    view["blocks"].append({
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": news_str
        }
    })
    view["blocks"].append({
        "type": "divider"
    })
    transaction_list = ["*Latest transaction*"]
    transaction_list.extend(tako_slack.transaction())
    transaction_str = "\n".join(transaction_list)
    top3_list = ["*Top 3 owners*"]
    top3_list.extend(tako_slack.top3())
    top3_str = "\n".join(top3_list)
    next_market, forecast = tako_slack.market_info()
    next_market_list = ["*Next*"]
    next_market_list.extend(next_market)
    next_market_str = "\n".join(next_market_list)
    forecast_list = ["*Weather Forecast*"]
    if forecast:
        forecast_list.extend(forecast[:2])
        for h, p in zip(forecast[2].split(), forecast[3].split()):
            forecast_list.append(f"{h}: {p}")
    forecast_str = "\n".join(forecast_list)
    view["blocks"].append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": transaction_str + "\n"
            },
            {
                "type": "mrkdwn",
                "text": top3_str + "\n"
            },
            {
                "type": "mrkdwn",
                "text": next_market_str + "\n"
            },
            {
                "type": "mrkdwn",
                "text": forecast_str + "\n"
            }
        ]
    })
    view["blocks"].append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Order"
                },
                "style": "primary",
                "action_id": "input_order_modal"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "History"
                },
                "action_id": "show_history_modal"
            },
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Story"
                },
                "action_id": "show_story_modal"
            }
        ]
    })
    view["blocks"].append({
        "type": "divider"
    })
    view["blocks"].append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"_Version {tako.__version__}_"
        }
    })
    return view


@slack_app.event("app_home_opened")
def tako_home_open(client, event):
    log.debug(f"{event['user']} opened home tab.")
    user_id = event["user"]
    view = create_home_view(user_id)
    try:
        client.views_publish(
            user_id=event["user"],
            view=view)
    except Exception as e:
        log.error(f"Error publishing home tab: {e}")


@slack_app.action("input_order_modal")
def input_order_modal(ack, body, client):
    log.debug(f"{body['user']['id']} opened input_order modal.")
    ack()
    user_id = body["user"]["id"]
    condition = TakoMarket.condition(user_id)
    balance = condition["balance"]
    takos = int(balance/takoconfig.COST_PRICE)
    max_sales = takoconfig.MAX_SALES["sunny"] + takoconfig.MAX_SALES["cloudy"]
    max_order = min(takos, max_sales)
    view = {
        "type": "modal",
        "callback_id": "order_result",
        "title": {
            "type": "plain_text",
            "text": "Order takoyaki"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit",
        },
        "close": {
            "type": "plain_text",
            "text": "Close"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Balance: {balance} JPY / {takos} takos"
                }
            },
            {
                "type": "input",
                "block_id": "input_tako_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "submit_order",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Number of takoyaki"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": f"How many tako do you order? (0-{max_order})"
                }
            }
        ]
    }
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=view
        )
    except Exception as e:
        log.error(f"Error opening input_order_modal: {e}")


@slack_app.view("order_result")
def order_result(ack, body, client, view):
    user_id = body["user"]["id"]
    condition = TakoMarket.condition(user_id)
    balance = condition["balance"]
    max_sales = takoconfig.MAX_SALES["sunny"] + takoconfig.MAX_SALES["cloudy"]
    takos = min(int(balance/takoconfig.COST_PRICE), max_sales)
    input_tako_block = view["state"]["values"]["input_tako_block"]
    input_value = input_tako_block["submit_order"]["value"]
    log.debug(f"{user_id} ordered {input_value}.")
    errors = {}
    try:
        quantity = int(input_value)
    except ValueError:
        errors["input_tako_block"] = "Only Integers."
        ack(response_action="errors", errors=errors)
        log.debug("The order canceled due to ValueError.")
        return

    if quantity < 0:
        errors["input_tako_block"] = "Zero or more."
        ack(response_action="errors", errors=errors)
        log.debug("The order canceled due to negative.")
        return

    if quantity > takos:
        errors["input_tako_block"] = f"You can order up to {takos} takos."
        ack(response_action="errors", errors=errors)
        log.debug(f"The order exceed {takos}.")
        return
    ack()
    tako_slack = TakoSlack(user_id, None)
    tako_slack.order(quantity)
    try:
        client.views_publish(
            user_id=user_id,
            view=create_home_view(user_id))
        log.debug("Update home tab")
    except Exception as e:
        log.error(f"Error publishing home tab: {e}")


@slack_app.action("show_history_modal")
def show_history_modal(ack, body, client):
    log.debug(f"{body['user']['id']} opened history modal.")
    ack()
    user_id = body["user"]["id"]
    tako_slack = TakoSlack(user_id, None)
    history_list = tako_slack.history(number=30)
    history_str = "\n".join(history_list)
    view = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": "History of Transactions"
        },
        "close": {
            "type": "plain_text",
            "text": "Close"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "```" + history_str + "```"
                }
            }
        ]
    }
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=view
        )
    except Exception as e:
        log.error(f"Error opening input_order_modal: {e}")


@slack_app.action("show_story_modal")
def show_story_modal(ack, body, client):
    log.debug(f"{body['user']['id']} opened history modal.")
    ack()
    view = {
        "type": "modal",
        "title": {
            "type": "plain_text",
            "text": "Takoyaki Story"
        },
        "close": {
            "type": "plain_text",
            "text": "Close"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": takoconfig.TAKO_STORY
                }
            }
        ]
    }
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=view
        )
    except Exception as e:
        log.error(f"Error opening input_order_modal: {e}")


class TakoSlack(TakoClient):
    def interpret(self, cmd):
        """Interpret command

        Returns
        -------
        messages : list of str
        """
        messages = []
        if cmd == "info":
            messages.append(self.name_with_badge())
            messages.extend(self.balance())
            messages.append("Latest Transaction:")
            messages.extend(["  " + x for x in self.transaction()])
            messages.append("")
            messages.append("Top 3 owners:")
            messages.extend(["  " + x for x in self.top3()])
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
        message : list of str

        Example
        -------
        Balance: 5000 JPY / 125 takos
        or
        Your account is not found.
        New account is open.
        """
        message = []
        condition = TakoMarket.condition(self.my_id)
        if condition:
            message.append(
                f"Balance: {condition['balance']} JPY / "
                f"{int(condition['balance']/takoconfig.COST_PRICE)} takos")
        else:
            message.append("Your account is not found.\n")
            message.append("New account is open.")

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

    def history(self, number=None, reverse=True):
        """Show transaction history

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

    def get_weather_forecast(self, name, date_jst):
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

    def market_info(self):
        """Show market

        Returns
        -------
        messages : list of str

        Example
        -------
        Place: 山形
        Open: 2022-01-24 09:00 JST
        Close: 2022-01-24 18:00 JST
        Forecast: 24日 月曜日 山形\nくもり後晴れ明け方一時雪
        06: 20%
        12: 10%
        18: 10%
        """
        next_place = []
        forecast = []
        area = TakoMarket.get_next_area()
        if area["date"]:
            next_place.append(f"Place: {area['area']}")
            tz = (+9, "JST")
            opening_time_str = self.astimezone(area['opening_datetime'], tz=tz)
            closing_time_str = self.astimezone(area['closing_datetime'], tz=tz)
            next_place.append(f"Open: {opening_time_str}")
            next_place.append(f"Close: {closing_time_str}")
            try:
                forecast = self.get_weather_forecast(
                    area["area"],
                    area["date"])
            except jma.JmaError as e:
                log.warning(f"can't get weather forecast: {e}")

        return next_place, forecast

    def help(self):
        """Show help

        Returns
        -------
        messages : list of str
        """
        messages = []
        messages.append("info : Show Tako Market Information.")
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

    def name_balance_badge(self, record):
        name = record["name"]
        balance = record["balance"]
        badge = record['badge']
        text = f"{name} : {balance} JPY"
        text += "\n "
        text += TakoClient.badge_to_emoji(badge)
        return text

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


class TakoSlackBot():
    def __init__(self):
        self.exit_loop = Event()
        self.bot_thrad = None
        self.bot_state = "runnable"
        self.interval_of_checking_news_sec = 60*30

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

    def bot(self):
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
                self.exit_loop.wait(self.interval_of_checking_news_sec)
        finally:
            slack_handler.close()
            log.info("Slack Bot stopped.")

    def run_bot(self, interval_of_checking_news_sec=None):
        """Run Takoyaki Slack Bot
            Use stop_bot to stop the Slack bot

        Parameters
        ----------
        interval_of_checking_news_sec : int
        """
        if interval_of_checking_news_sec:
            self.interval_of_checking_news_sec = interval_of_checking_news_sec
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
    log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "takoslackbot")

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
