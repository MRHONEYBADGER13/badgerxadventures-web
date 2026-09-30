"""IP address -> rough location, for the admin panel's visitor/IP lists.

Uses ipwho.is (https, no API key needed, generous free-tier rate limit) to
turn an IP into a "City, ST" (or "City, Country" outside the US) label.
Results are cached in memory for the life of the process -- an IP's
location essentially never changes, so once we know it we never ask again.
Same fail-quiet approach as weather.py: a lookup that errors out (network
hiccup, rate limit, private IP) just yields no location, never a crash.
"""
import ipaddress
import json
import urllib.error
import urllib.request

USER_AGENT = "BADGERxADVENTURES/1.0 (contact: mrxbadger6@yahoo.com)"

_cache = {}  # ip -> label string, or "" for "looked up, nothing useful found"


def _is_public(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast
    )


def _fetch(ip):
    req = urllib.request.Request(
        f"https://ipwho.is/{ip}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=4) as resp:
        return json.loads(resp.read().decode("utf-8"))


def locate(ip):
    """Best-effort "City, ST" (or "City, Country") for one IP, or None."""
    if not ip:
        return None
    if ip in _cache:
        return _cache[ip] or None
    if not _is_public(ip):
        _cache[ip] = ""
        return None
    label = ""
    try:
        data = _fetch(ip)
        if data.get("success", True):
            city = (data.get("city") or "").strip()
            country = (data.get("country") or "").strip()
            country_code = (data.get("country_code") or "").strip()
            state = (data.get("region_code") or data.get("region") or "").strip()
            if city and country_code == "US" and state:
                label = f"{city}, {state}"
            elif city and country:
                label = f"{city}, {country}"
            elif country:
                label = country
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        pass
    _cache[ip] = label
    return label or None


def locate_many(ips):
    """{ip: label-or-None} for a batch of IPs, hitting the network only for
    the ones we haven't already resolved this process."""
    return {ip: locate(ip) for ip in dict.fromkeys(ip for ip in ips if ip)}
