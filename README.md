# Takoyaki
You have to run a takoyaki's shop and make money.

The cost of takoyaki is 40 yen per piece and the selling price is 50 yen.
The number of takoyaki sold in a day depends on the weather:
about 500 takoyakis sold on a sunny day,
about 300 on a cloudy day and
about 100 on a rainy or snowy day.
So look carefully at the weather forecast for the next day and
make up your mind how many you will make.
Takoyaki does not last long, so all unsold takoyakis are discarded.
The winner is the first person who starts with 5,000 yen and exceeds 30,000 yen.

The takoyaki market opens at 9:00 a.m. every day.
So you need to decide how many takoyaki to make, and order them by the time.
The market closes at 18:00 p.m. and the sales are calculated. 

The place of market is changed every day and the next is announced at 9:00 a.m.
You can decide how many to make to consider weather forecast in the place.

```Shell
ID: RB-79, Display name: Ball
tako[125]:
Balance: 5000 JPY at 2022-01-31 09:38 JST

Top 3 owners
Ball: 5000 JPY
Char: 0 JPY
Mirai: 0 JPY

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
Char: 0 JPY
Mirai: 0 JPY

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
If you are going to run the slackbot, you will need to set 'App-level token', 'Bot token' and 'Channel ID' in `/etc/default/takoserver`.
The channel is used for the market news feeds.
```Shell
SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
SLACK_TAKO_CHANNEL=SSSSSSSSSSS
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
And also Slack channel ID for the market news feeds is required.
```Shell
export SLACK_TAKO_CHANNEL=CXXXXXXXX
```


## Commands
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
You can set logging level using the TAKOMARKET_DEBUG environment variable.
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
You can set logging level using the TAKOBOT_DEBUG environment variable.
```Shell
$ TAKO_LOGGING_LEVEL=info takobot
```

### `takoslackbot`
Run a takoyaki slackbot, which serves user interface and news feeds.
```Shell
$ export SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyy
$ export SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
$ export SLACK_TAKO_CHANNEL=CXXXXXXXX
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
```
$ export SLACK_APP_TOKEN=xapp-1-XXXXXXXXXXX-0123456789012-yyyyyyyyyyyyyyyy
$ export SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxx-YYYYYYYYYYYYYYYYYYYYYYYY
$ export SLACK_TAKO_CHANNEL=CXXXXXXXX
$ takoserver
```
You can set logging level using the TAKO_LOGGING_LEVEL environment variable.
```Shell
$ TAKO_LOGGING_LEVEL=debug takoserver
```