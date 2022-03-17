#! /usr/bin/env python3

"""Wrapper Functions for the Helium API."""

__authors__ = ["Sam Gutentag"]
__email__ = "developer@samgutentag.com"
__maintainer__ = "Sam Gutentag"
__version__ = "2022.03.17.0"

from os import getlogin
from os.path import basename

import requests

HEADERS = {
    "User-Agent": f"solitaryPixels_{basename(__file__)}/{__version__}",
    "From": f"{getlogin()}.{basename(__file__)}@heliumheartbeat.com",
}


def hotspots_for_account(address, cursor="", max_depth=3, api_url="api.helium.io"):
    baseurl = f"https://{api_url}/v1/accounts/{address}/hotspots"
    depth = 0
    while True and depth < max_depth:
        depth += 1
        _url = f"{baseurl}?cursor={cursor}"
        r = requests.get(_url, headers=HEADERS).json()
        try:
            for record in r["data"]:
                yield record
            cursor = r["cursor"]
        except KeyError:
            break


def hotspot_activity(address, cursor="", max_depth=3, api_url="api.helium.io"):
    baseurl = f"https://{api_url}/v1/hotspots/{address}/roles"
    depth = 0
    while True and depth < max_depth:
        depth += 1
        _url = f"{baseurl}?cursor={cursor}"
        r = requests.get(_url, headers=HEADERS).json()
        try:
            for record in r["data"]:
                yield record
            cursor = r["cursor"]
        except KeyError:
            break
