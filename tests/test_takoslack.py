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
     ("2021-10-10", "Apple", "comming_soon", 0, ""),
     0),
    # Almost same news
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     ("2021-10-10", "Banana", "comming_soon", 0, ""),
     0),
    # difference of status
    ([("2021-10-10", "Apple", "comming_soon", 0, "")],
     ("2021-10-10", "Apple", "open", 0, ""),
     1),
    # Normal update
    ([("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "open", 0, ""),
      ("2021-10-08", "Cherry", "canceled", 0, "")],
     ("2021-10-09", "Banana", "comming_soon", 0, ""),
     2),
    # Normal update with canceled
    ([("2021-10-10", "Apple", "comming_soon", 0, ""),
      ("2021-10-09", "Banana", "open", 0, ""),
      ("2021-10-08", "Cherry", "canceled", 0, ""),
      ("2021-10-07", "Durian", "closed", 0, "")],
     ("2021-10-08", "Cherry", "open", 0, ""),
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
        news.news = parameter_maker([init])[0]

    news.check_market()
    news.check_market()  # not create same text
    assert create_text_mock.call_count == expected


publish_parameters = [
    (("2021-10-09", "Apple", "coming_soon", 0, ""),
     r""),
    (("2021-10-11", "Apple", "coming_soon", 0, ""),
     r"Market in Apple will open soon at 2021-10-11 09:00."),
    (("2021-10-10", "Apple", "open", 0, ""),
     r"Market is opening in Apple at 2021-10-10 09:00."),
    (("2021-10-09", "Apple", "open", 0, ""),
     r""),
    (("2021-10-10", "Apple", "closed", 500, "Sunny"),
     "Market is closed in Apple at 2021-10-10 09:00.\n"
     "Max sales: 500 Weather: Sunny\n"
     "Top 3 Owners\n"
     "  Four: 5000 JPY\n"
     "  Three: 3000 JPY\n"
     "  Two: 2000 JPY\n"),
]


@pytest.mark.skipif("os.environ.get('SLACK_APP_TOKEN') is None",
                    "os.environ.get('SLACK_BOT_TOKEN') is None",
                    reason="Need environment variables of Slack")
@pytest.mark.freeze_time(datetime(2021, 10, 10, tzinfo=JST))
@pytest.mark.parametrize("param, expected", publish_parameters)
def test_create_text(mocker, param, expected):
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
    news = News()
    area = parameter_maker([param])
    assert news.create_text(area[0]) == expected
