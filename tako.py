import signal
from threading import Event
from tako.takomarket import TakoMarket
from tako.takobot import Takobot
from tako.takoslack import TakoSlackBot
from tako import takoconfig

log = takoconfig.set_logging_level("TAKO_DEBUG", "tako")


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
        self.slackbot = TakoSlackBot()

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

    def run(self):
        """Run takobot, takomarket and slackbot
        """
        for sig in [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self.signal_handlar)

        self.takomarket.run_market()
        self.takobot.run_bot()
        self.slackbot.run_bot()

        self.do_run.wait()  # wait for signal

        self.slackbot.stop_bot()
        self.takobot.stop_bot()
        self.takomarket.stop_market()


def main():
    tako = TakoWorld()
    tako.run()


if __name__ == "__main__":
    main()
