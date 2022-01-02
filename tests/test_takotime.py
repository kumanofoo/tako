from tako.takotime import TakoTime, JST, UTC
from datetime import datetime


def test_takotime():
    expect_jst = datetime(2021, 10, 1, 0, 0, 0)
    expect_jst = expect_jst.replace(tzinfo=JST)
    assert expect_jst == TakoTime.date_with_tz("2021-10-01", utc_offset=9)

    expect_today_jst = datetime.now(JST)
    expect_today_jst_str = expect_today_jst.strftime("%Y-%m-%d 00:00:00 +0900")
    actual_today_jst = TakoTime.date_with_tz(utc_offset=9)
    actual_today_jst_str = actual_today_jst.strftime("%Y-%m-%d %H:%M:%S %z")
    assert expect_today_jst_str == actual_today_jst_str

    expect_today_utc = datetime.now(UTC)
    expect_today_utc_str = expect_today_utc.strftime("%Y-%m-%d 00:00:00 +0000")
    actual_today_utc = TakoTime.date_with_tz()
    actual_today_utc_str = actual_today_utc.strftime("%Y-%m-%d %H:%M:%S %z")
    assert expect_today_utc_str == actual_today_utc_str

    expect_utc_str = "2021-09-30T15:00:00"
    assert expect_utc_str == TakoTime.as_utc_str(expect_jst)
