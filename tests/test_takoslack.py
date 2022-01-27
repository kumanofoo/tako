import pytest
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
JST = timezone(timedelta(hours=+9))


def parameter_maker(param, time=("09:00:00+09:00", "18:00:00+09:00")):
    if param is None:
        return None

    now = datetime.now()
    param_keys = ("date", "area", "status", "sales", "weather")

    history = []
    for p in param:
        area = {}
        if p[0]:
            date = p[0]
        else:
            date = now.strftime("%Y-%m-%d")
        area["date"] = date
        area["opening_datetime"] = datetime.fromisoformat(date+"T"+time[0])
        area["closing_datetime"] = datetime.fromisoformat(date+"T"+time[0])

        for i, p in enumerate(p[1:]):
            area[param_keys[i+1]] = p
        history.append(area)

    return history


check_market_parameters = [
    (None, None, 0),
    # First news
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     None,
     1),
    # Same news
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     [("2021-10-10", "Apple", "comming_soon", 0, "")],
     0),
    # Almost same news
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     [("2021-10-10", "Banana", "comming_soon", 0, "")],
     0),
    # difference of status
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     [("2021-10-10", "Apple", "open", 0, "")],
     1),
    # Normal update
    ([("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "open", 0, ""),
      ("2021-10-08", "Cherry", "canceled", 0, "")],
     [("2021-10-09", "Banana", "comming_soon", 0, "")],
     2),
    # Normal update
    ([("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "closed", 0, ""),
      ("2021-10-08", "Cherry", "canceled", 0, "")],
     [("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "open", 0, "")],
     1),
    # Normal update with canceled
    ([("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "open", 0, ""),
      ("2021-10-08", "Cherry", "canceled", 0, ""),
      ("2021-10-07", "Durian", "closed", 0, "")],
     [("2021-10-08", "Cherry", "open", 0, "")],
     3),
]


@pytest.mark.skipif("os.environ.get('SLACK_APP_TOKEN') is None",
                    "os.environ.get('SLACK_BOT_TOKEN') is None",
                    reason="Need environment variables of Slack")
@pytest.mark.parametrize("param, init, expected", check_market_parameters)
def test_check_market(mocker, param, init, expected):
    from tako.takoslack import News
    create_text_mock = mocker.patch("tako.takoslack.News.create_text")
    area_history = parameter_maker(param)
    mocker.patch(
        "tako.takomarket.TakoMarket.get_area_history",
        return_value=area_history)
    news = News()
    if init:
        news.news = parameter_maker(init)

    news.check_market()
    news.check_market()  # not create same text
    assert create_text_mock.call_count == expected


publish_parameters = [
    (("2021-10-09", "Apple", "coming_soon", 0, ""), False,
     r""),
    (("2021-10-11", "Apple", "coming_soon", 0, ""), False,
     r"Market in Apple will open soon at 2021-10-11 09:00."),
    (("2021-10-10", "Apple", "open", 0, ""), False,
     r"Market is opening in Apple at 2021-10-10 09:00."),
    (("2021-10-09", "Apple", "open", 0, ""), False,
     r""),
    (("2021-10-10", "Apple", "closed", 500, "Sunny"), False,
     "Market is closed in Apple at 2021-10-10 09:00.\n"
     "Max sales: 500 Weather: Sunny\n"
     "Top 3 Owners\n"
     "  Four: 5000 JPY\n"
     "  Three: 3000 JPY\n"
     "  Two: 2000 JPY\n"),
    (("2021-10-10", "Apple", "closed", 400, "Sunny"), True,
     "This season is over. And next season has begun.\n"
     "One : 35000 JPY\n"
     " ⭐🦑🐙\n"
     "Two : 33000 JPY\n"
     " 🦑🦑🐙🐙🐙🐙🐙🐙🐙🐙🐙\n"
     "Three : 31000 JPY\n"
     " 🦑🦑🦑\n"
     "\n"
     "The following is the close to the target.\n"
     "Four : 29000 JPY\n"
     " 🦑🦑🦑🦑🦑🦑🦑🦑🦑🐙🐙🐙🐙🐙🐙🐙🐙🐙\n"
     "Five : 29000 JPY\n"
     " "
     ),
]

get_records_closed_and_restart = {
    "2021-10-10": [
        {
            "name": "One",
            "balance": 35000,
            "target": 30000,
            "ranking": 1,
            "badge": 111,
        },
        {
            "name": "Two",
            "balance": 33000,
            "target": 30000,
            "ranking": 2,
            "badge": 29,
        },
        {
            "name": "Three",
            "balance": 31000,
            "target": 30000,
            "ranking": 3,
            "badge": 30,
        },
        {
            "name": "Four",
            "balance": 29000,
            "target": 30000,
            "ranking": 4,
            "badge": 99,
        },
        {
            "name": "Five",
            "balance": 29000,
            "target": 30000,
            "ranking": 4,
            "badge": 0,
        },
        {
            "name": "Six",
            "balance": 28000,
            "target": 30000,
            "ranking": 6,
            "badge": 6,
        },
    ]
}


@pytest.mark.skipif("os.environ.get('SLACK_APP_TOKEN') is None",
                    "os.environ.get('SLACK_BOT_TOKEN') is None",
                    reason="Need environment variables of Slack")
@pytest.mark.freeze_time(datetime(2021, 10, 10, tzinfo=JST))
@pytest.mark.parametrize("param, restart, expected", publish_parameters)
def test_create_text(mocker, param, restart, expected):
    from tako.takoslack import News
    condition_all = [
        {"name": "Three", "balance": 3000},
        {"name": "One", "balance": 1000},
        {"name": "Two", "balance": 2000},
        {"name": "Four", "balance": 5000},
    ]
    mocker.patch(
        "tako.takomarket.TakoMarket.condition_all",
        return_value=condition_all)
    if restart:
        mocker.patch(
            "tako.takomarket.TakoMarket.get_records",
            return_value=get_records_closed_and_restart)
    else:
        mocker.patch(
            "tako.takomarket.TakoMarket.get_records",
            return_value={})
    news = News()
    area = parameter_maker([param])
    actual = news.create_text(area[0])
    assert actual == expected, f"{actual}"
