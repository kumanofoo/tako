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

## Installation
```Shell
$ pip install .
```
You can use 'takomarket', 'takocmd' and 'takobot' command.


## Configuration
You can specify the database file using the TAKO_DB variable.
The default file is './tako_storage.db'.
```Shell
export TAKO_DB=/path/to/takomarket/database.db
```

## Commands
### takomarket
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
$ export TAKOMARKET_DEBUG=debug
$ takomarket -d
```

### takobot
Run a takoyaki bot.
It calculate quantity of takoyaki depending on weather forecast and order it automatically.
The ID of bot is "MS-06S" and the name is "Char".
```Shell
$ takobot
```
You can set logging level using the TAKOBOT_DEBUG environment variable.
```Shell
$ TAKOBOT_DEBUG=info takobot
```

### takocmd
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
  quit : Quit this command.
  help : Show this message.
tako[125]: quit
```
