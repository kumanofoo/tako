# Takoyaki
<img alt="Slack Takoyaki Shop" src="./img/screenshot_home.png">


You will run a takoyaki shop.
You are given 5000 yen at the start.
Its goal is to make 30000 yen faster than other shops.
When someone reaches 30000 yen,
the series of markets are once closed.
And then it is reset to 5000 yen and new market starts.

The cost of one takoyaki is 40 yen and the selling price is 50 yen.
The number of takoyakis sold in a day depends on the weather.
About 500 takoyakis would sell on a sunny day.
About 300 on a cloudy day, and about 100 on a rainy or snowy day.
So you should look carefully at the weather forecast
for the next day before making up your mind
about how many you will make.
Takoyaki does not last long, so all unsold takoyakis are discarded.

The place of the market is changed every day and
the next is announced at 9:00 a.m. the day before.
The takoyaki market opens at 9:00 a.m. every day.
By the opening time, you need to decide how many takoyakis to make.
Please remember to check the weather forecast.
It closes at 6:00 p.m. and the sales are calculated.

Summary of Timeline:
1. At 9:00 a.m. the next place of the market is announced.
2. By tomorrow 9:00 a.m. decide how many takoyakis to make referring to the weather forecast.
3. At 6:00 p.m. the market is closed.
4. Decide how many tomorrow after checking your balance and the weather forecast.

Command Line Client:
```Shell
ID: RB-79, Display name: Ball
tako[125]:
Balance: 5000 JPY at 2022-01-31 09:38 JST

Top 3 owners
Ball: 5000 JPY
Char: 5000 JPY
Mirai: 5000 JPY

Next: 潮岬
Open: 2022-02-01 09:00 JST
Close: 2022-02-01 18:00 JST

1日 火曜日 潮岬
晴れ昼過ぎから時々くもり
06  12  18
 0% 10% 10%
tako[125]: 125
Ordered 125 tako
tako[125]:
Balance: 5000 JPY at 2022-01-31 09:38 JST
Status: ordered 125 tako at 2022-01-31 10:03 JST

Top 3 owners
Ball: 5000 JPY
Char: 5000 JPY
Mirai: 5000 JPY

Next: 潮岬
Open: 2022-02-01 09:00 JST
Close: 2022-02-01 18:00 JST

1日 火曜日 潮岬
晴れ昼過ぎから時々くもり
06  12  18
 0% 10% 10%
tako[125]:
```

## Installation
### Commands
```Shell
$ pip install .
```
You can use commands: `takomarket`, `takocmd`, `takobot`, `takoslackbot` and `takoserver`.

### Installation with test (Option)
```Shell
$ pip install .[dev]
```

### Takoyaki Service for linux (Option)
```
$ sudo bash install.sh install
```
If you are going to run the slackbot, you will need to set 'App-level token',
'Bot token' and 'Webhook URL' in `/etc/default/takoserver`.
The webhook is used for the market news feeds.
```Shell
TAKO_DB=/opt/takoserver/tako.db
SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
SLACK_WEBHOOK_URL='https://hooks.slack.com/services/AAAAAAAAA/BBBBBBBBBBB/xxxxxxxxxxxxxxxxxxxxxxxx'
```

## Configuration
### SQLite3 database
You can specify the database file using the TAKO_DB variable.
The default file is `./tako.db`.
```Shell
export TAKO_DB=/path/to/tako.db
```

### Slackbot
Slackbot to Tako market is required two tokens: App-level token and Bot token.
```Shell
export SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
export SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
```
And also Incomming Webhook URL for the market news feeds is required.
```Shell
export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/AAAAAAAAA/BBBBBBBBBBB/xxxxxxxxxxxxxxxxxxxxxxxx'
```

The following is an app manifest file 'App_Manifest.yaml' for creating new slack app.
```YAML
display_information:
  name: TAKO
  description: Takoyaki Shop
  background_color: "#2c2d30"
features:
  app_home:
    home_tab_enabled: true
    messages_tab_enabled: false
    messages_tab_read_only_enabled: false
  bot_user:
    display_name: TAKO
    always_online: false
oauth_config:
  scopes:
    bot:
      - im:history
      - incoming-webhook
      - users:read
      - chat:write
settings:
  event_subscriptions:
    bot_events:
      - app_home_opened
      - message.im
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```


## Commands
<img alt="Takoyaki Commands" src="./img/tako.svg">

### `takomarket`
Run a takoyaki market server.
It chooses a market place every day,
calculates sales depending on the weather in the palce and
updates each owner's balance.
```Shell
$ takomarket --help
usage: takomarket [-h] [-d]

Takoyaki Market

optional arguments:
  -h, --help    show this help message and exit
  -d, --daemon
```
You can set logging level using the TAKO_LOGGING_LEVEL environment variable.
```Shell
$ export TAKO_LOGGING_LEVEL=debug
$ takomarket -d
```

### `takobot`
Run a takoyaki bot.
It calculate quantity of takoyaki depending on weather forecast and order it automatically.
The ID of bot is "MS-06S" and the name is "Char".
```Shell
$ takobot
```
You can set logging level using the TAKO_LOGGING_LEVEL environment variable.
```Shell
$ TAKO_LOGGING_LEVEL=info takobot
```

### `takoslackbot`
Run a takoyaki slackbot, which serves user interface and news feeds.
```Shell
$ export SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyy
$ export SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
$ export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/AAAAAAAAA/BBBBBBBBBBB/xxxxxxxxxxxxxxxxxxxxxxxx'
$ takoslackbot
```

### `takocmd`
You can run some takoyaki commands by command line.
```Shell
$ takocmd --help
usage: takocmd [-h] [-i ID] [-n NAME]

optional arguments:
  -h, --help            show this help message and exit
  -i ID, --id ID        Owner ID
  -n NAME, --name NAME  Owner name
$ 
$ takocmd
ID: RB-79, Display name: Ball
tako[125]: help
  <Enter> : Show Tako Market Information.
  <Number> : Order tako.
  history : Show History of Transactions.
  quit : Quit this command.
  help : Show this message.
tako[125]: quit
```

### `takoserver`
You can run takomarket, takobot and takoslackbot all at once.
```Shell
$ export SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyy
$ export SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
$ export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/AAAAAAAAA/BBBBBBBBBBB/xxxxxxxxxxxxxxxxxxxxxxxx'
$ takoserver
```
You can set logging level using the TAKO_LOGGING_LEVEL environment variable.
```Shell
$ TAKO_LOGGING_LEVEL=debug takoserver
```
