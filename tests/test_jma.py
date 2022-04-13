from tako.jma import Synop, PointMeta, Forecast
import time
from datetime import datetime, timedelta, timezone


def test_get_all_point_forecast():
    JST = timezone(timedelta(hours=9))
    points = Synop.point_list()
    assert len(points) > 0
    date_jst = datetime.now(JST).strftime("%Y-%m-%d")

    for p in points:
        meta = PointMeta.get_point_meta(p)
        if meta is None:
            continue
        assert meta.get('class10s') is not None
        class10s = meta['class10s']
        f = Forecast.get_forecast(class10s, date_jst)
        assert len(f) > 0
        assert type(f["reportDatetime"]) is datetime
        assert f["area_name"] != ""
        w_dt = f["weather"]["datetime"]
        assert w_dt.strftime("%Y-%m-%d") == date_jst
        assert f["weather"]["text"] != ""
        for dt, pops in f["pops"]:
            assert dt.astimezone(JST).strftime("%Y-%m-%d") == date_jst
            assert int(pops) >= 0 and int(pops) <= 100
        # print(f["area_name"], f["weather"]["text"])
        time.sleep(1)
