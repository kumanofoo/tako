from tako.jma import Synop, PointMeta, Forecast
import time


def test_get_all_point_forecast():
    points = Synop.point_list()
    assert len(points) > 0
    for p in points:
        meta = PointMeta.get_point_meta(p)
        if meta is None:
            continue
        assert meta.get('class10s') is not None
        class10s = meta['class10s']
        f = Forecast.get_forecast(class10s)
        assert len(f) > 0
        #print(f["area_name"], f["weather"]["text"])
        time.sleep(1)
