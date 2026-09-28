"""Live weather for the Lake Cumberland map, from the National Weather Service's
free public API (api.weather.gov -- no API key needed).

"Now" conditions come from one airport station (Somerset-Pulaski County,
KSME) and are shown on every place card, same as the original design: one
station covers the whole lake well enough for a "what's it like out there"
glance, and NWS doesn't run a station at every cove. Each place gets its own
3-period forecast (today/tonight/tomorrow) from the NWS gridpoint nearest its
own coordinates, so forecasts do vary a little place to place.

Water temperature has no reliable free public API (the original design used
a paid/scraped source called LakeMonster) -- we simply omit the "water" key
when we don't have a number, and the front end already handles that.

Lake level (pool elevation) *does* have a reliable free public API: NOAA's
National Water Prediction Service (api.water.noaa.gov -- no API key needed,
same NWS family as the weather.gov calls above). Gauge WLCK2 ("Cumberland
River at Lake Cumberland") is the AHPS gauge for Wolf Creek Dam and reports
the lake's current pool elevation in feet as its "primary" observation. We
compare that to Lake Cumberland's published full (summer) pool elevation of
723 ft to show how far up or down the lake is. Same omit-the-key-on-failure
approach as water temperature.

Results are cached in memory for CACHE_TTL seconds so a burst of page loads
doesn't hammer NWS, and a request that fails reuses the last good cache
(marking it stale) rather than showing nothing.
"""
import time
import urllib.request
import urllib.error
import json

CACHE_TTL = 20 * 60  # 20 minutes
STATION = "KSME"  # Somerset-Pulaski County Airport
USER_AGENT = "BADGERxADVENTURES/1.0 (contact: mrxbadger6@yahoo.com)"

LAKE_GAUGE = "WLCK2"  # NWS AHPS gauge: Cumberland River at Lake Cumberland (Wolf Creek Dam)
LAKE_FULL_POOL_FT = 723.0  # published full/summer pool elevation, Lake Cumberland

PLACES = [
    {"id": "dam", "name": "Wolf Creek Dam", "lat": 36.868, "lon": -85.061},
    {"id": "jamestown", "name": "Jamestown", "lat": 36.988, "lon": -85.062},
    {"id": "monticello", "name": "Monticello", "lat": 36.833, "lon": -84.849},
    {"id": "burnside", "name": "Burnside", "lat": 36.988, "lon": -84.607},
    {"id": "somerset", "name": "Somerset", "lat": 37.092, "lon": -84.604},
]

_cache = {"data": None, "at": 0}


def _get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json, application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _icon_for(short_forecast):
    s = (short_forecast or "").lower()
    if "thunder" in s or "storm" in s:
        return "storm"
    if "rain" in s or "shower" in s or "drizzle" in s or "snow" in s:
        return "rain"
    if "cloudy" in s or "overcast" in s:
        if "partly" in s or "mostly sunny" in s or "mostly clear" in s:
            return "pcloud"
        return "cloud"
    if "sunny" in s or "clear" in s or "fair" in s:
        return "sun"
    return "cloud"


def _c_to_f(c):
    if c is None:
        return None
    return round(c * 9 / 5 + 32)


def _kmh_to_mph(kmh):
    if kmh is None:
        return 0
    return round(kmh * 0.621371)


def _fetch_now():
    """One shared 'now' reading from the airport station."""
    data = _get_json(f"https://api.weather.gov/stations/{STATION}/observations/latest")
    props = data.get("properties") or {}
    temp_c = (props.get("temperature") or {}).get("value")
    wind_kmh = (props.get("windSpeed") or {}).get("value")
    humidity = (props.get("relativeHumidity") or {}).get("value")
    text = props.get("textDescription") or "Fair"
    return {
        "f": _c_to_f(temp_c),
        "t": text,
        "ic": _icon_for(text),
        "mph": _kmh_to_mph(wind_kmh),
        "hum": round(humidity) if humidity is not None else None,
    }


def _fetch_forecast(lat, lon):
    """Today/Tonight/Tomorrow for one place's own gridpoint."""
    point = _get_json(f"https://api.weather.gov/points/{lat},{lon}")
    forecast_url = (point.get("properties") or {}).get("forecast")
    if not forecast_url:
        return []
    fc = _get_json(forecast_url)
    periods = (fc.get("properties") or {}).get("periods") or []
    out = []
    for p in periods[:3]:
        out.append({
            "k": p.get("name") or "",
            "t": "high" if p.get("isDaytime") else "low",
            "f": p.get("temperature"),
            "pop": (p.get("probabilityOfPrecipitation") or {}).get("value") or 0,
        })
    return out


def _fetch_lake_level():
    """Current Lake Cumberland pool elevation from NOAA's NWPS gauge API."""
    data = _get_json(f"https://api.water.noaa.gov/nwps/v1/gauges/{LAKE_GAUGE}")
    obs = (data.get("status") or {}).get("observed") or {}
    elev = obs.get("primary")
    if elev is None or elev <= -900:  # NWPS uses -999 as a "no data" sentinel
        return None
    return {
        "elevFt": round(elev, 1),
        "asOf": obs.get("validTime"),
        "fullPoolFt": LAKE_FULL_POOL_FT,
        "belowFullFt": round(LAKE_FULL_POOL_FT - elev, 1),
        "src": "NWS gauge WLCK2",
    }


def _build_fresh():
    now = _fetch_now()
    places = []
    for p in PLACES:
        try:
            fc = _fetch_forecast(p["lat"], p["lon"])
        except Exception:
            fc = []
        places.append({
            "id": p["id"],
            "name": p["name"],
            "obs": "Somerset airport",
            "now": now,
            "fc": fc,
        })
    try:
        lake = _fetch_lake_level()
    except Exception:
        lake = None
    result = {
        "v": 1,
        "asOf": int(time.time() * 1000),
        "note": "Air and forecasts: National Weather Service. \"Now\" is from "
                "Somerset airport for every spot. A live snapshot, refreshed "
                "every 20 minutes.",
        "places": places,
    }
    if lake:
        result["lake"] = lake
    return result


def get_weather():
    """Cached weather payload, shaped exactly like the front end expects.
    Never raises -- on any failure it returns the last good cache (if any)
    or a minimal empty-but-valid payload so the map still renders.
    """
    now = time.time()
    if _cache["data"] is not None and (now - _cache["at"]) < CACHE_TTL:
        return _cache["data"]
    try:
        fresh = _build_fresh()
        _cache["data"] = fresh
        _cache["at"] = now
        return fresh
    except Exception:
        if _cache["data"] is not None:
            return _cache["data"]
        return {"v": 1, "asOf": int(now * 1000), "note": "Weather is temporarily unavailable.", "places": []}
