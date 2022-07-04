import os
import signal
from threading import Event
from tako.takomarket import TakoMarket
from tako.takobot import Takobot
from tako import takoconfig

log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "tako")

bot_token = os.environ.get("SLACK_BOT_TOKEN")
if bot_token is None:
    log.warning("Environment variable 'SLACK_BOT_TOKEN' is not defined")
app_token = os.environ.get("SLACK_APP_TOKEN")
if app_token is None:
    log.warning("Environment variable 'SLACK_APP_TOKEN' is not defined")
webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
if webhook_url is None:
    log.warning("Environment variable 'SLACK_WEBHOOK_URL' is not defined")
if bot_token and app_token and webhook_url:
    from tako.takoslack import TakoSlackBot
else:
    TakoSlackBot = None
    log.warning("Slackbot is stopped")


class TakoWorld:
    def __init__(self):
        """Initialize each thread

        Attributes
        ----------
        do_run : threading.Event
            wait for signal
        takobot : Takobot
        takomarket : TakoMarket
        slackbot : TakoSlackBot
        """
        self.do_run = Event()
        self.takomarket = TakoMarket()
        self.takobot = Takobot()
        if TakoSlackBot:
            self.slackbot = TakoSlackBot()
        else:
            self.slackbot = None

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
        self.do_run.set()

    def run(self, market=True, bot=True, slackbot=True):
        """Run takobot, takomarket and slackbot
        """
        for sig in [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self.signal_handlar)

        if market:
            self.takomarket.run_market()
            log.info("takomarket is running")
        if bot:
            self.takobot.run_bot()
            log.info("takobot is running")
        if self.slackbot and slackbot:
            self.slackbot.run_bot()
            log.info("takoslackbot is running")

        if market or bot or (self.slackbot and slackbot):
            self.do_run.wait()  # wait for signal

        if self.slackbot and slackbot:
            self.slackbot.stop_bot()
            log.info("takoslackbot has stopped")
        if bot:
            self.takobot.stop_bot()
            log.info("takobot has stopped")
        if market:
            self.takomarket.stop_market()
            log.info("takomarket has stopped")


def main():
    takoserver_env = os.environ.get("TAKOSERVER")
    if takoserver_env:
        threads = takoserver_env.split(":")
        if "market" in threads:
            market = True
        else:
            market = False
        if "bot" in threads:
            bot = True
        else:
            bot = False
        if "slackbot" in threads:
            slackbot = True
        else:
            slackbot = False
    else:
        market = True
        bot = True
        slackbot = True

    tako = TakoWorld()
    tako.run(market=market, bot=bot, slackbot=slackbot)


if __name__ == "__main__":
    main()
