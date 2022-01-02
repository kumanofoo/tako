#! /usr/bin/env python3

from datetime import datetime, timedelta, time, timezone


JST = timezone(timedelta(hours=9))
UTC = timezone.utc


class TakoTime:
    @staticmethod
    def date_with_tz(date_str=None, utc_offset=0):
        """Transform string date into datetime as JST

        Parameters
        ----------
        date_str : str
            The string date like 'YYYY-MM-DD'.
        utc_offset : int
            UTC offset. Default is 0(UTC).
        Returns
        -------
        timezone-aware datetime
            The time part is 00:00:00 and the timezone is JST
            like 'YYYY-MM-DD 00:00:00 +0900'.
            If data_str is None, return today's date.
        """
        offset = timezone(timedelta(hours=utc_offset))
        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            date_tz = date.replace(tzinfo=offset)
        else:
            today = datetime.now(offset).date()
            date = datetime.combine(today, time())
            date_tz = date.replace(tzinfo=offset)
        return date_tz

    @staticmethod
    def as_utc_str(dt):
        """Get datetime as UTC string

        Parameters
        ----------
        date : timezone-aware datetime

        Returns
        -------
        timezone-aware datetime
            as UTC string like 'YYYY-MM-DDThh:mm:ss'
            None if date is native.
        """
        if not dt.tzinfo:
            return None
        utc = dt.astimezone(UTC)
        utc_str = utc.strftime("%Y-%m-%dT%H:%M:%S")
        return utc_str

    def clear_time(date):
        """Clear time part of datetime

        Parameters
        ----------
        date : datetime

        Returns
        -------
        datetime at midnight
        """
        return date.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0)


def _test():
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


if __name__ == "__main__":
    _test()
