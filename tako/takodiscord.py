import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import threading
import signal
import asyncio
import zoneinfo
from datetime import datetime, timezone, timedelta
from tako.takomarket import MarketDB, TakoMarketNoAccountError
from tako.takoclient import TakoClient
from tako import jma, takoconfig
import logging

# log = logging.getLogger(__name__)
log = takoconfig.set_logging_level("TAKO_LOGGING_LEVEL", "takodiscordbot")


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if TOKEN is None:
    log.critical("No DISCORD_BOT_TOKEN")
    exit(1)

JST = timezone(timedelta(hours=9))


class TakoDiscordError(Exception):
    pass

class News:
    def __init__(self,
                 closed_news_expiration_days: int = 1,
                 open_news_expiration_hours: int = 8):
        """Initialize each attributes
        """
        self.closed_news_expiration_days = closed_news_expiration_days
        self.open_news_expiration_hours = open_news_expiration_hours
        self.news: list[dict[str, object]] = []

    def check_market(self) -> list[str]:
        """Check Takoyaki market

        Returns
        -------
        text: list of str
            Takoyaki Market News
        """
        texts: list[str] = []
        with MarketDB() as mdb:
            news = mdb.get_area_history()
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
        """Extract name, balance and badge from record, which is score in a season
        
        Parameters
        ----------
        record : dict
            { date_jst, owner_id, name, balance, target, badge }

        Returns
        ----------
        text : str
            'Yamada: 19200 JPY\n⭐🦑🐙'
        """
        name = record["name"]
        balance = record["balance"]
        badge = record['badge']
        text = f"{name} : {balance} JPY"
        text += "\n "
        text += TakoClient.badge_to_emoji(badge)
        return text

    def create_text(self, news_source: dict[str, object]) -> str:
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
            with MarketDB() as mdb:
                records = mdb.get_records(
                    date_jst=news_source["date"],
                    winner=False)
                condition_all = mdb.condition_all()
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
                    condition_all,
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


class TakoCommandBot(commands.Bot):
    """
    Tako bot wrapper Class for Discord bot

    Attributes
    ----------
    token : str
        Discord API token
    tako_channel : str | None
        webhook for Tako News Channel
    news : News
        News instance
    """
    @staticmethod
    def check_environment_variables() -> bool:
        """Check environment valiables of the token
        
        Returns
        -------
        existance: bool
        """
        try:
            _ = os.environ["DISCORD_BOT_TOKEN"]
        except KeyError:
            return False
        return True
    
    def __init__(self):
        try:
            self.token = os.environ["DISCORD_BOT_TOKEN"]
        except KeyError:
            raise TakoDiscordError(
                "Environment variable 'DISCORD_BOT_TOKEN' is not defined."
            )

        try:
            self.tako_channel = os.environ["DISCORD_TAKO_CHANNEL"]
        except:
            self.tako_channel = None
            log.warning("'DISCORD_TAKO_CHANNEL' not found")

        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.news = News()
        self._thread = None
        self._loop = None
        self._running = False

    async def setup_hook(self):
        self.news_feed.start()
        guild_id = os.getenv("DISCORD_BOT_GUILD_ID")
        if guild_id is None:
            # self.tree.clear_commands(guild=None)
            # synced = await self.tree.sync()
            self.tree.add_command(TakoCmd())
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} slash commands globally.")
        else:
            guild = discord.Object(id=int(guild_id))
            # self.tree.clear_commands(guild=None)
            # synced = await self.tree.sync()
            # print(f"Synced {len(synced)} slash commands for global")
            self.tree.clear_commands(guild=guild)
            self.tree.add_command(TakoCmd(), guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(f"Synced {len(synced)} slash commands for '{guild_id}'")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")

    @tasks.loop(minutes=1)
    async def news_feed(self):
        """Send tako news to tako channel of discord
        """
        now = datetime.now(JST).strftime("%H:%M")

        text = ""
        if now == "09:20":
            text = "\n".join(self.news.check_market())
        elif now == "18:20":
            text = "\n".join(self.news.check_market())
        else:
            text = ""

        if text:
            if self.tako_channel is None:
                log.info("There is no Tako channel available.")
                return
            for guild in self.guilds:
                channel = discord.utils.get(guild.text_channels, name=self.tako_channel)
                if channel:
                    try:
                        await channel.send(text)
                    except discord.Forbidden:
                        log.warning(f"Permission error in {guild.name}")

    @news_feed.before_loop
    async def before_news_feed(self):
        await self.wait_until_ready()

    async def close(self):
        """Shutdown this Bot
        """
        log.info("Bot is shutting down...")
        self.news_feed.cancel()
        await super().close()


class TakoDiscord(TakoClient):
    """
    Tako market client wrapper class for Discord bot
    """

    def order_tako(self, quantity: int) -> list[str]:
        """Order takos

        Parameters
        ----------
        quantity: int
            number of takos for order

        Returns
        -------
        messages: list[str]
            response to order
        """
        messages = []
        max_quantity = self.max_order_quantity()[0]
        if quantity >= 0 and quantity <= max_quantity:
            if self.order(quantity):
                messages.append(f"Ordered {quantity} tako")
            else:
                log.warning(f"The order of {self.my_name}({self.my_id}) could not be accepted.")
                messages.append(f"Sorry. Your order could not be accepted.")
        else:
            messages.append(f"Your order **{quantity}** takos could not be accepted.")
            messages.append(f"You can order up to **{max_quantity}**.")
        return messages

    def transaction(self) -> list[str]:
        """Show latest transaction.

        Returns
        -------
        message : list of str
        """
        transaction = self.latest_transaction()
        if transaction:
            with MarketDB() as mdb:
                market = mdb.get_area(transaction["date"])
            if market is None:
                transaction_str = []
            else:
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

    def result(self) -> str | None:
        """Result in this season

        Returns
        -------
        result: str

        Example
        -------
        You were 3rd with 30100 JPY.
        """
        t = self.latest_transaction()
        if t:
            if t["status"] == "closed_and_restart":
                date = t["date"]
                with MarketDB() as mdb:
                    record = mdb.get_owner_records(self.my_id).get(date)
                if record is None:
                    return None
                balance = record["balance"]
                rank = record["rank"]
                suffix = {1: "st🐙", 2: "nd", 3: "rd"}.get(rank, "th")
                return f"*You were {rank}{suffix} with {balance} JPY.*"
        return None

    def top3(self) -> list[str]:
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
        with MarketDB() as mdb:
            area = mdb.get_next_area()
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

    
    pass


HISTORY_MAX = 25 # Due to Discord's embed fields constraints, maximum 25

class TakoCmd(app_commands.Group):
    """
    Discord slash commands
    """

    NO_TAKO_ID = ("Hi there! I don't think we've met before.\n"
                  "Please try to use the command: **/tako join <display name>**.\n")

    TAKO_ID_EXISTS = ("Hi! You are already registered for the Tako Market.\n"
                      "If you wish to delete all of your registered information,"
                      " please use the **/tako delete** command.")

    def __init__(self):
        super().__init__(name="tako", description="Tako commands")

    def _tako_id(self, interaction: discord.Interaction) -> str:
        """Get tako market ID
        Parameters
        ----------
        interactioin: discord.Interaction

        Returns
        -------
        markert_id: str
            "{user_id}@{guild_id}.discord.com"
        """
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        return f"{user_id}@{guild_id}.discord.com"

    def _tako_id_exist_on_db(self, tako_id: str) -> bool:
        """Check if the Tako market ID exists in the DB

        Parameters
        ----------
        tako_id: str
            Tako market ID
            "{user_id}@{guild_id}.discord.com"

        Returns
        -------
            result: bool
        """
        try:
            with MarketDB() as mdb:
                _ = mdb.get_name(tako_id)
            return True
        except TakoMarketNoAccountError:
            return False
        except Exception as e:
            log.error(f"{e}")
            return False

    def _status_emoji(self, status, weather, max_sales) -> str:
        STATUS_EMOJI = {
            "cloudy": ":cloud:",
            "rainy": ":umbrella:",
            "sunny": ":sunny:",
        }
        emoji = ""
        if status == "canceled":
            emoji = ":no_entry:"
        elif status == "ordered":
            emoji = ""
        elif status == "closed" or status == "closed_and_restart":
            emoji = f"{STATUS_EMOJI.get(weather)}{max_sales}"
            if emoji is None:
                log.error(f"Unknown weather code: {weather}")
                emoji = ""
        else:
            log.error(f"Unknown status : {status}")

        return emoji

    async def _send_followup(self, interaction: discord.Interaction, content, embeds=None):
        try:
            if embeds is None:
                await interaction.followup.send(content=content)
            else:
                await interaction.followup.send(content=content, embeds=embeds)
        except Exception as e:
            log.error(f"{e}")

    def _balance(self, tako_id: str) -> list[str]:
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
        with MarketDB() as mdb:
            condition = mdb.condition(tako_id)
        if condition:
            messages.append(
                f"Balance: {condition['balance']} JPY / "
                f"{int(condition['balance']/takoconfig.COST_PRICE)} takos")
        else:
            messages.append("Your account is not found.\n")
            messages.append("New account is open.")

        return messages

    @app_commands.command(name="help", description="Show the usage")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        text = (
            "**/tako info** : Show Tako Market Information\n"
            "**/tako order <n>** : Order N takos\n"
            "**/tako history** : Show the history of the transaction.\n"
            "**/tako join <display name>** : Join to Tako Market\n"
            "**/tako delete** : Delete this account.\n"
            "**/tako help** : Show this message."
        )
        await self._send_followup(interaction, text)

    @app_commands.command(name="info", description="Show Tako Market Information")
    async def info_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tako_id = self._tako_id(interaction)
        with MarketDB() as mdb:
            (_id, name, badges, *_) = mdb.get_name(tako_id)
        badges_str = TakoClient.badge_to_emoji(badges)
        
        if not self._tako_id_exist_on_db(tako_id):
            await self._send_followup(interaction, TakoCmd.NO_TAKO_ID)
            return
        news = News()
        news_str = "\n".join(news.check_market())
        if news_str == "":
            news_str = "Umm... No news..."
        content = "Hey %s! %s\n%s\n%s" % (
            name,
            badges_str,
            '\n'.join(self._balance(tako_id)),
            news_str
        )
        embed = discord.Embed(
            title="Market Information",
            color=0xffcc5c,
        )
        tako_discord = TakoDiscord(tako_id, None)
        result = tako_discord.result()
        if result is None:
            embed.description = result
        embed.add_field(
            name="Latest Transaction",
            value="\n".join(tako_discord.transaction()),
            inline=True
        )
        embed.add_field(
            name="Top 3 Owners",
            value="\n".join(tako_discord.top3()),
            inline=True
        )
        next_market, forecast = tako_discord.market_info()
        embed.add_field(
            name="Next",
            value="\n".join(next_market),
            inline=True
        )
        if forecast:
            forecast_list = forecast[:2]
            for h, p in zip(forecast[2].split(), forecast[3].split()):
                forecast_list.append(f"{h}: {p}")
            embed.add_field(
                name="Weather Forecast",
                value="\n".join(forecast_list),
                inline=True
            )
        await self._send_followup(interaction, content, [embed])

    @app_commands.command(name="history", description="Show the history of transaction")
    @app_commands.describe(line=f"Optional number of history (up to {HISTORY_MAX})")
    async def history_cmd(self, interaction: discord.Interaction, line: str | None = None):
        await interaction.response.defer(ephemeral=True)
        history_max = HISTORY_MAX
        if line is not None: 
            try:
                history_max = min(HISTORY_MAX, int(line))
            except Exception as e:
                await self._send_followup(interaction, "**line** is 1 or greater, or None.")
                return

        tako_id = self._tako_id(interaction)
        if not self._tako_id_exist_on_db(tako_id):
            await self._send_followup(interaction, TakoCmd.NO_TAKO_ID)
            return
        with MarketDB() as mdb:
            transactions = mdb.get_transaction(tako_id)
            records = mdb.get_owner_records(tako_id)
        embed = discord.Embed(
            title="Sales Report",
            description=f"The latest {history_max}",
            color=0xffcc5c,
        )
        for n, t in enumerate(sorted(transactions,
                                     key=lambda x: x["date"],
                                     reverse=True)):
            if n == history_max:
                break
            value = "ORD %d  STK %d  SAL %d" % (
                t['quantity_ordered'],
                t['quantity_in_stock'],
                t['sales']/takoconfig.SELLING_PRICE)
            if t['status'] == "closed_and_restart":
                record = records[t['date']]
                rank = record['rank']
                suffix = {1: "st🐙", 2: "nd", 3: "rd"}.get(rank, "th")
                balance = record['balance']
                result = f"You were {rank}{suffix} with {balance} JPY."
                value += "\n" + result
            emoji_status = self._status_emoji(t['status'], t['weather'], t['max_sales'])
            embed.add_field(
                name=f"{t['date']} {t['area']} {emoji_status}",
                value=value,
                inline=False
            )
        if len(embed.fields) == 0:
            await self._send_followup(interaction, "No history yet!")
        else:
            await self._send_followup(interaction, "", [embed])

    @app_commands.command(name="order", description="Order Takos")
    @app_commands.describe(n="Number of Tako")
    async def order_cmd(self, interaction: discord.Interaction, n: int):
        await interaction.response.defer(ephemeral=True)
        tako_id = self._tako_id(interaction)
        if not self._tako_id_exist_on_db(tako_id):
            await self._send_followup(interaction, TakoCmd.NO_TAKO_ID)
            return

        tako_discord = TakoDiscord(tako_id, None)
        message = tako_discord.order_tako(n)
        if len(message) == 0:
            message = ["You can order 0 or greater takos."]

        await self._send_followup(interaction, "\n".join(message))

    @app_commands.command(name="join", description="Join to Tako Market")
    @app_commands.describe(display_name="Display name in Tako Market")
    async def join_cmd(self, interaction: discord.Interaction, display_name: str):
        await interaction.response.defer(ephemeral=True)
        tako_id = self._tako_id(interaction)
        if self._tako_id_exist_on_db(tako_id):
            await self._send_followup(interaction, TakoCmd.TAKO_ID_EXISTS)
            return
        try:
            _ = TakoClient(tako_id, display_name)
            message = (f"Thank you for joining us, {display_name}."
                        " If you need something, try to enter **/tako help**.")
            await self._send_followup(interaction, message)
        except Exception as e:
            log.error(f"Error: {e}")

    @app_commands.command(name="delete", description="Delete this account")
    @app_commands.describe(confirmation="'DELETE' and delete this account")
    async def delete_cmd(self, interaction: discord.Interaction, confirmation: str):
        await interaction.response.defer(ephemeral=True)
        tako_id = self._tako_id(interaction)
        message = None
        if confirmation == "DELETE":
            with MarketDB() as mdb:
                if mdb.delete_account(tako_id) == tako_id:
                    log.info(f"{tako_id}'s account was deleted")
                    message = "Your Takoyaki account was deleted."
                else:
                    log.warning(f"can't delete account {tako_id}")
                    message = "Your Takoyaki account was NOT able to be deleted."
        else:
            message = "If you want to delete the account, enter 'DELETE'."
        await self._send_followup(interaction, message)


class TakoDiscordBot:
    """
    Run and stop Discord bot in asyncio event loop
    """
    @staticmethod
    def check_environment_variables() -> bool:
        try:
            _ = os.environ["DISCORD_BOT_TOKEN"]
        except KeyError:
            return False
        return True
    
    def __init__(self):
        try:
            self._token = os.environ["DISCORD_BOT_TOKEN"]
        except KeyError:
            raise TakoDiscordError(
                "Environment variable 'DISCORD_BOT_TOKEN' is not defined."
            )
        
        self._running = False

    def run_bot(self):
        if self._running:
            log.warning("Discord Bot is already running")
            return

        self._loop = asyncio.new_event_loop()
        def _run():
            asyncio.set_event_loop(self._loop)
            self._running = True
            try:
                self._loop.run_until_complete(self._tako.start(self._token))
            except Exception as e:
                log.error("Discord bot error: {e}")
            finally:
                self._loop.run_until_complete(self._tako.close())
                self._loop.close()
                self._running = False
        
        self._tako = TakoCommandBot()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        log.info("Discord bot started in thread")

    def stop_bot(self):
        if not self._running:
            log.warning("Discord bot is not running")
            return

        asyncio.run_coroutine_threadsafe(self._tako.close(), self._loop)
        if self._thread is None:
            log.warning("Thread of bot not found")
            return
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            log.warning("Discord bot did not stop gracefully")
        else:
            log.info("Discord bot stopped")
            self._running = False


def run():
    try:
        tako = TakoDiscordBot()
    except TakoDiscordError as e:
        log.error(f"TakoDiscordError: {e}")
        exit(1)

    def signal_handler(signum, frame):
        log.info("\nReceived interrupt signal. shutting down gracefully...")
        tako.stop_bot()
        exit(0)

    signals = (signal.SIGINT, signal.SIGTERM)
    for s in signals:
        signal.signal(s, signal_handler)

    log.info("Starting Discord bot...")
    tako.run_bot()
    try:
        signal.pause()
        log.info("exit signal.pause()")
    except KeyboardInterrupt:
        pass
    log.info("Successfully shut down.")


def main():
    """
    news = News()
    n = news.check_market()
    print(f"news1: {n}")
    n = news.check_market()
    print(f"news2: {n}")
    exit(0)
    """
    try:
       run()
    except KeyboardInterrupt:
        pass
    
if __name__ == "__main__":
    main()
