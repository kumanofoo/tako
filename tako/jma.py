#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import json
import datetime as dt
import time
import random
import urllib.request
import zipfile
import tempfile
import os
import difflib
import logging
import pathlib


log = logging.getLogger(__name__)

AREA_JSON = pathlib.Path(__file__).parent / "area.json"
POINT_META_JSON = pathlib.Path(__file__).parent / "point_meta.json"


class JmaError(Exception):
    pass


class Synop:
    """Get weather observations from SYNOP
    """
    SYNOPDAY_URL = ("https://www.data.jma.go.jp/"
                    "obd/stats/data/mdrr/synopday/data1s.html")
    SYNOPDAY_LABELS = [
        ("pressure", "station_average", "hPa"),
        ("pressure", "sea_level_average", "hPa"),
        ("pressure", "lowest_sea_level", "hPa"),
        ("pressure", "lowest_sea_level_time", ""),
        ("temperture", "average", "degree_celesius"),
        ("temperture", "highest", "degree_celesius"),
        ("temperture", "highest_time", "time"),
        ("temperture", "lowest", "degree_celesius"),
        ("temperture", "lowest_time", ""),
        ("vapor_pressure", "average", "hPa"),
        ("humidity", "average", "%"),
        ("humidity", "lowest", "%"),
        ("humidity", "lowest_time", ""),
        ("wind", "average_speed", "m/s"),
        ("wind", "maximum_speed", "m/s"),
        ("wind", "maximum_speed_direction", ""),
        ("wind", "maximum_speed_time", ""),
        ("wind", "maximum_instantaneous_speed", "m/s"),
        ("wind", "maximum_instantaneous_speed_direction", ""),
        ("wind", "maximum_instantaneous_speed_time", ""),
        ("sunshine", "duration", "hours"),
        ("global_solar_radiation", "global_solar_radiation", "MJ/m2"),
        ("cloud_amount", "average", "%/10"),
        ("rainfall", "totals", "mm"),
        ("rainfall", "1-hour_maximum", "mm"),
        ("rainfall", "1-hour_maximum_time", ""),
        ("rainfall", "10-minutes_maximum", "mm"),
        ("rainfall", "10-minutes_maximum_time", ""),
        ("snowfall", "totals", "cm"),
        ("show_depth", "maximum", "cm"),
        ("general_weather", "0600-1800", ""),
        ("general_weather", "1800-0600", ""),
    ]

    @staticmethod
    def synopday(point=None):
        """Get daily weather observations

        Parameters
        ----------
        point : str
            The weather station.
            Get it from all station if point is None.

        Reteruns
        --------
        observations : dict
            {
                "title": str
                    Meta information
                "data": {
                    ****Synop.SYNOPDAY_LABELS****
                }
            }

        Raises
        ------
        JmaError
            If can't get SYNOP data.
        """
        daily_weather_observations = {}
        daily_weather_observations["data"] = {}

        try:
            r = requests.get(Synop.SYNOPDAY_URL)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise JmaError(f"can't get SYNOP data: {e}")
        soup = BeautifulSoup(r.content, "html.parser")
        div_main = soup.find_all("div", attrs={"id": "main"})[0]
        title = div_main.find_all("div")[0].text
        tables = div_main.find_all("table", attrs={"class": "o1"})

        daily_weather_observations["title"] = title
        data = daily_weather_observations["data"]
        for table in tables:
            trs = table.find_all("tr", class_=["o1", "o2"])
            for tr in trs:
                tds = tr.find_all("td")
                pt = tds[0].text
                if point is not None and pt != point:
                    continue
                data[pt] = {}
                labels = Synop.SYNOPDAY_LABELS
                for i, td in enumerate(tds[1:]):
                    item = labels[i][0]
                    label = labels[i][1]
                    unit = labels[i][2]
                    if item not in data[pt]:
                        data[pt][item] = {}
                    data[pt][item][label] = {}
                    data[pt][item][label]["value"] = \
                        td.text.split(']')[0].split(')')[0]
                    data[pt][item][label]["unit"] = unit
        return daily_weather_observations

    @staticmethod
    def point_list(retry=5):
        """Get place names of all the weather station.

        Parameters
        ----------
        retry : int
            How many times to retry on request errors.

        Returns
        -------
        points : str list

        Raises
        ------
        JmaError
            If can't get SYNOP data.
        """
        points = []

        for _ in range(retry):
            try:
                r = requests.get(Synop.SYNOPDAY_URL)
            except requests.exceptions.RequestException as e:
                raise JmaError(f"can't get SYNOP data: {e}")
            soup = BeautifulSoup(r.content, "html.parser")
            div_mains = soup.find_all("div", attrs={"id": "main"})
            if len(div_mains) > 0:
                break
            time.sleep(5)
        if len(div_mains) == 0:
            raise JmaError("cannot get point list")

        div_main = div_mains[0]
        tables = div_main.find_all("table", attrs={"class": "o1"})

        for table in tables:
            trs = table.find_all("tr", class_=["o1", "o2"])
            for tr in trs:
                tds = tr.find_all("td")
                pt = tds[0].text
                points.append(pt)

        return points


class Forecast:
    """Get forecast from JMA
    """
    FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast"

    @staticmethod
    def get_office_code(class10s):
        """Get office code

        Parameters
        ----------
        class10s : str
            The 'class10s' area code

        Returns
        -------
            office code : str
        """
        with open(AREA_JSON, 'r', encoding='utf-8') as area_json:
            areas = json.load(area_json)
        return areas['class10s'][class10s]['parent']

    @staticmethod
    def get_class10s_code(city_name, with_name=False):
        """Get class10s area code

        Parameters
        ----------
        city_name : str
        with_name : bool
            If with_name is True, return tapple list of class10s and city name.
            If with_name is False, return list of class10s
        Returns
        -------
            class10s : list of str or tupple
        """
        with open(AREA_JSON, 'r') as area_json:
            areas = json.load(area_json)
        codes = []
        names = []
        for i in areas['class20s']:
            if areas['class20s'][i]['name'].startswith(city_name):
                codes.append(
                    areas['class15s'][areas['class20s'][i]['parent']]['parent']
                    )
                names.append(areas['class20s'][i]['name'])
        if with_name:
            return [(c, n) for c, n in zip(codes, names)]
        else:
            return codes

    @staticmethod
    def get_forecast(class10s, date_jst):
        """Get forecast

        Parameters
        ----------
        class10s : str
        date_jst : str

        Returns
        -------
        forecast : dict
            {
                "reportDatetime": datetime as UTC
                "area_name": str
                "weather": dict
                    {
                        "datetime": datetime
                        "text": str
                            The weather summary
                    }
                "pops": list of tupple (str, str)
                      [(time, Probability of Precipitation),...]
            }

        Raises
        ------
        JmaError
            If can't get forecast.
        """
        target_date = dt.date.fromisoformat(date_jst)

        office = Forecast.get_office_code(class10s)
        try:
            r = requests.get(f"{Forecast.FORECAST_URL}/{office}.json")
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise JmaError(f"can't get forecast: {e}")
        data = json.loads(r.content)

        area_index = None
        for i, area in enumerate(data[0]['timeSeries'][0]['areas']):
            if area['area']['code'] == class10s:
                area_index = i

        if area_index is None:
            return None

        forecast = {}
        forecast['reportDatetime'] = dt.datetime.fromisoformat(
            data[0]['reportDatetime'])
        areas = data[0]['timeSeries'][2]['areas']
        forecast['area_name'] = areas[area_index]['area']['name']

        forecast['weather'] = {'datetime': None, 'text': None}
        for i, ts in enumerate(data[0]['timeSeries'][0]['timeDefines']):
            forecast_datetime = dt.datetime.fromisoformat(ts)
            if target_date == forecast_datetime.date():
                forecast['weather']['datetime'] = forecast_datetime
                areas = data[0]['timeSeries'][0]['areas']
                forecast['weather']['text'] = areas[area_index]['weathers'][i]
                break

        forecast['pops'] = []
        for i, ts in enumerate(data[0]['timeSeries'][1]['timeDefines']):
            forecast_datetime = dt.datetime.fromisoformat(ts)
            if target_date == forecast_datetime.date():
                forecast['pops'].append((
                    forecast_datetime,
                    data[0]['timeSeries'][1]['areas'][area_index]['pops'][i]))

        return forecast


class PointMeta:
    """Meta data of the point, weather observing station.
    """
    POINT_MASTER_FILE = "smaster.index"

    @staticmethod
    def download_master(destdir="."):
        """Download the file of weather observing station.

        Parameters
        ----------
        destdir : str
            The destination directory.

        Returns
        -------
        path : str
            The path to the downloaded file.
        """
        url = ("https://www.data.jma.go.jp/"
               "obd/stats/data/mdrr/chiten/meta/"
               f"{PointMeta.POINT_MASTER_FILE}.zip")
        tmpdir = tempfile.TemporaryDirectory()
        master_zip = os.path.join(
            tmpdir.name,
            f"{PointMeta.POINT_MASTER_FILE}.zip")
        urllib.request.urlretrieve(url, master_zip)
        with zipfile.ZipFile(master_zip) as zf:
            zf.extract(PointMeta.POINT_MASTER_FILE, destdir)
        return os.path.join(destdir, PointMeta.POINT_MASTER_FILE)

    @staticmethod
    def get_point_meta(point, meta_json=POINT_META_JSON):
        """Get meta data of weather observing station.

        Parameters
        ----------
        point : str
            The name of the place of the weather observing station.
        meta_json : str
            The path to the meta file.

        Returns
        -------
        meta : dict
            {
                "lat": float
                    The latitude in deg format.
                "lng": float
                    The longitude in deg format.
                "class10s": str
                    The class10s area code.
            }
        """
        with open(meta_json, "r", encoding="utf-8") as meta_json:
            point_meta = json.load(meta_json)
            return point_meta.get(point, None)

    @staticmethod
    def diff_point_meta_json(filename="point_meta.json"):
        """Show differences between the existing file and downloaded it.

        Parameters
        ----------
        finename : str
            The existing file.
        """
        tmpdir = tempfile.TemporaryDirectory()
        download = os.path.join(tmpdir.name, "download_meta.json")
        PointMeta.create_point_meta(filename=download)
        with open(filename, "r") as your:
            with open(download, "r") as down:
                diff = difflib.unified_diff(
                    down.readlines(),
                    your.readlines(),
                    fromfile="download flie",
                    tofile="point_meta.json")
        for line in diff:
            print(line, end='')

    @staticmethod
    def __get_data(record, field):
        """Get the field data from SYNOP point meta record.

        Parameters
        ----------
        record : str
            The SYNOP meta.

        field : str
            The field name of the SYNOP point meta record.
            "number", "obsv_cnt", "amedas", "roman",
            "lat", "lng" and "kanji".

        Returns
        -------
        data : str
        """
        position = {
            'number': (3, 1),
            'obsv_cnt': (1, 6),
            'amedas': (2, 13),
            'roman': (12, 25),
            'lat': (6, 37),
            'lng': (7, 43),
            'kanji': (12, 81),
        }
        space = str.maketrans({
            '\u3000': '',
        })
        if field not in position:
            return None

        n = position[field][0]
        s = position[field][1]-1
        return record[s:s+n].decode('sjis').translate(space)

    @staticmethod
    def create_point_meta(filename=None, smaster=None):
        """Create the meta data file of the weather observing station points.

        Parameters
        ----------
        filename : str
            The output filename.
            If filename is None, show point meta.
        smaster : str
            The SYNOP point meta data filename.
            If smaster is None, download the point meta file.
        """
        if filename:
            if os.path.exists(filename):
                raise JmaError(f"{filename} already exists")

        if not smaster:
            tmpdir = tempfile.TemporaryDirectory()
            smaster = PointMeta.download_master(destdir=tmpdir.name)

        with open(smaster, "rb") as f:
            point = {}
            while True:
                record = f.read(146+1)
                if not record:
                    break
                kanji = PointMeta.__get_data(record, 'kanji')
                if not kanji:
                    continue
                if not PointMeta.__get_data(record, 'obsv_cnt').isdecimal():
                    continue
                if int(PointMeta.__get_data(record, 'obsv_cnt')) == 0:
                    continue
                if kanji not in point:
                    point[kanji] = {}
                    lat_dmm = int(PointMeta.__get_data(record, 'lat'))
                    lat_deg = int(lat_dmm/10000) + int(lat_dmm % 10000)/100/60
                    # Round off lat_deg to 4th decimal places
                    point[kanji]['lat'] = int(lat_deg*10000+0.5)/10000
                    lng_dmm = int(PointMeta.__get_data(record, 'lng'))
                    lng_deg = int(lng_dmm/10000) + int(lng_dmm % 10000)/100/60
                    # Round off lng_deg to 4th decimal places
                    point[kanji]['lng'] = int(lng_deg*10000+0.5)/10000
                class10s = Forecast.get_class10s_code(kanji, with_name=True)
                if len(class10s) == 1:
                    point[kanji]['class10s'] = class10s[0][0]
                elif len(class10s) > 1:
                    point[kanji]['class10s'] = class10s

        if filename:
            with open(filename, "w") as f:
                f.write(json.dumps(point, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(point, indent=2, ensure_ascii=False))


def main():
    points = Synop.point_list()
    name = ''
    while True:
        name = random.sample(points, 1)[0]
        meta = PointMeta.get_point_meta(name)
        if meta:
            if meta.get('class10s'):
                class10s = meta['class10s']
                break
        print(f"skip {name} which have no class10s code")

    print(f"[{name}] ({meta['lat']}:{meta['lng']})")
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    f = Forecast.get_forecast(class10s, now.strftime(r"%Y-%m-%d"))
    area_name = f['area_name']
    forecast_date = f['reportDatetime'].strftime("%b %d")
    forecast_time = f['reportDatetime'].strftime("%H%M")
    print(f"({area_name} Last updated {forecast_date} at {forecast_time})")
    weather_datetime = f['weather']['datetime'].strftime("%a %e")
    print(f"{weather_datetime} {f['weather']['text']}")
    times = 'hour '
    pops = 'pops '
    for (t, p) in f['pops']:
        if t.hour < 6:
            continue
        times += "%2s " % t.strftime("%H")
        pops += "%2s " % p
    print(times)
    print(pops)

    now = Synop.synopday(point=name)
    sunshine = float(now['data'][name]['sunshine']['duration']['value'])
    rainfall = now['data'][name]['rainfall']['totals']['value']
    if rainfall == "--":
        rainfall = 0
    rainfall = float(rainfall)
    title = now['title']
    print()
    print(title)
    print(f"sunshine: {sunshine} hour")
    print(f"rainfall: {rainfall} mm")


if __name__ == "__main__":
    # PointMeta.create_point_meta()
    # PointMeta.diff_point_meta_json()
    main()
