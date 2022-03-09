#! /usr/bin/env python3

"""Wrapper Functions for the Helium API


Inspiration from https://gutentag.co/google_python_docstrings
and https://gutentag.co/google_python_styleguide

Use CalVer versioning as described at https://calver.org/

"""

__authors__ = ["Sam Gutentag"]
__email__ = "developer@samgutentag.com"
__maintainer__ = "Sam Gutentag"
__version__ = "2022.03.09.0"

from os.path import basename

import requests

API_HELIUM = "api.helium.io"
HEADERS = {
    "User-Agent": f"solitaryPixels_{basename(__file__)}/{__version__}",
    "From": f"{__email__}",
}


def hotspot_activity(address, cursor="", max_depth=2, api_url=API_HELIUM):
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


def hotspots_for_account(address, cursor="", api_url=API_HELIUM):
    baseurl = f"https://{api_url}/v1/accounts/{address}/hotspots"
    while True:
        _url = f"{baseurl}?cursor={cursor}"
        r = requests.get(_url, headers=HEADERS).json()
        try:
            for record in r["data"]:
                yield record
            cursor = r["cursor"]
        except KeyError:
            break
