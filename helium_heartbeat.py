#! /usr/bin/env python3

"""Collect Stats from Hotspots in Wallet

Track the sync status, most recent block activity, ping, and other
metrics for each hotspot.

Inspiration from https://gutentag.co/google_python_docstrings
and https://gutentag.co/google_python_styleguide

Use CalVer versioning as described at https://calver.org/

"""

__authors__ = ["Sam Gutentag"]
__email__ = "developer@samgutentag.com"
__maintainer__ = "Sam Gutentag"
__version__ = "2022.03.09.0"


import json
import logging
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from tcp_latency import measure_latency

import helium_api_wrapper as pythelium


def setup_logging():
    """Set up  logging filename and ensure logging directory exists."""
    # name of this file
    this_file = os.path.splitext(os.path.basename(__file__))[0]

    # construct name of log file
    now = datetime.now().strftime("%Y%m")
    log_file = f"{this_file}_{now}.log"

    # ensure logging directory exists
    this_dir = os.path.dirname(os.path.realpath(__file__))
    log_dir = os.path.join(this_dir, "logs")
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    # logging settings
    logging.basicConfig(
        filename=os.path.join(log_dir, log_file),
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # logging.disable(logging.CRITICAL)
    logging.debug("-" * 80)


def get_most_recent_activity(hotspot=None):
    """Get most recent activity block height."""
    try:
        _activity = list(pythelium.hotspot_activity(hotspot["address"], max_depth=3))[0]
        return _activity["height"]
    except Exception:
        return -1


def get_ping_time(ip4_addr=None, port=44158):
    """Ping specific port on IP address.

    Returns dict of ping time average, median, and stdev in milliseconds

    Args:
        ip4_addr (string): public ip address to ping
        port (int): port to check connection to

    Returns:
        result (dict): keys > [avg, median, stddev]

    Raises:
        Exception: if statistic can not be computed returns a -1

    """
    latency_result = measure_latency(host=ip4_addr, port=port, runs=5)

    try:
        _avg = statistics.mean(latency_result)
    except Exception as e:
        _avg = -1
    try:
        _median = statistics.median(latency_result)
    except Exception as e:
        _median = -1
    try:
        _stdev = statistics.stdev(latency_result)
    except Exception as e:
        _stdev = -1

    result = {"avg": _avg, "median": _median, "stdev": _stdev}

    return result


def get_hotspot_heartbeat(hotspot=None):
    """Short description of this function.

    Longer description of this function.

    Args:
        argument_name (type): description

    Returns:
        return_value (type): description

    Raises:
        ErrorType: description and cause

    """
    _heartbeat = {}
    _name = hotspot["name"]
    _heartbeat["name"] = _name
    _heartbeat["status_height"] = hotspot["status"]["height"]
    _heartbeat["status_timestamp"] = hotspot["status"]["timestamp"]

    _listen_addrs = hotspot["status"]["listen_addrs"][0].split("/")[2]

    _heartbeat["status_listen_addrs"] = _listen_addrs
    _heartbeat["block"] = hotspot["block"]

    # test hotspot ping
    _heartbeat["ping_times"] = get_ping_time(ip4_addr=_listen_addrs)

    # get latest activity block
    _heartbeat["latest_activity_block"] = get_most_recent_activity(hotspot=hotspot)

    return _heartbeat


def get_heartbeats(wallet_addr=os.environ["WALLET_ADDR"]):
    """Get heartbeat data for all hotspots in a given wallet.

    Multithreaded collection of heartbeat data for all hotspots associated to
    a given wallet

    Args:
        wallet_addr (string): a wallet address on the Helium Blockchain

    Returns:
        result (dict): dictionary of hotspots heartbeat data

    Raises:
        Exception: broad exceptiopn for when the helium API fails to
                    return a list of hotspots for the given wallet
    """

    # get list of hotspots for address
    try:
        wallet_hotspots = pythelium.hotspots_for_account(address=wallet_addr)
    except Exception as e:
        return f"Something went wrong getting the Hotspots for Wallet\n{e}"

    # split work into threads
    threads = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        for hotspot in wallet_hotspots:

            threads.append(executor.submit(get_hotspot_heartbeat, hotspot))

    # parse data from threads
    heartbeats = {}
    for task in threads:
        heartbeat = task.result()
        heartbeats[heartbeat["name"]] = heartbeat

    # get max block reported
    block_heights = []
    for name in sorted(heartbeats.keys()):
        block_heights.append(heartbeats[name]["block"])
    block_height_max = max(block_heights)

    # calculate inactive gap for each hotspot
    for name in sorted(heartbeats.keys()):
        if heartbeats[name]["latest_activity_block"] == -1:
            heartbeats[name]["blocks_inactive"] = -1
        else:
            heartbeats[name]["blocks_inactive"] = (
                block_height_max - heartbeats[name]["latest_activity_block"]
            )

    return heartbeats


def update_info_files(wallet_heartbeats):
    """update cached hotspot info files with latest heartbeat data

    Writes heartbeat data for wallet hotspots to a json file.
    Only one copy is kept for each hotspot, updated with the most recent data

    Args:
         wallet_heartbeats (dict): dictionary of hotspot heartbeat data

    """
    # ensure output directory exists
    this_dir = os.path.dirname(os.path.realpath(__file__))
    info_dir = os.path.join(this_dir, "data", "hotspot_latest_info")
    if not os.path.isdir(info_dir):
        os.makedirs(info_dir)

    # for each hotspot in wallet_heartbeats, write data to json file
    for hotspot, heartbeat in wallet_heartbeats.items():

        hotspot_name = heartbeat["name"]
        info_file = os.path.join(info_dir, f"{hotspot_name}-heartbeat.json")

        # create info dictionary
        hotspot_info = {}

        # get info file if it exists
        if os.path.exists(info_file):
            ...
            # open info file to dictionary
            with open(info_file) as infile:
                hotspot_info = json.load(infile)

        # append hotspot heartbeat to key "heartbeat"
        # overwrites existing entries
        hotspot_info["heartbeat"] = heartbeat

        # save data to info file
        with open(info_file, "w", encoding="utf-8") as f:
            json.dump(hotspot_info, f, ensure_ascii=False, indent=2)


def main():
    logging.debug("-" * 80)
    logging.debug("Collecting Heartbeats for wallet.")
    wallet_heartbeats = get_heartbeats()

    # update hotspot info file with heartbeat data
    update_info_files(wallet_heartbeats)

    utcnow = datetime.utcnow()
    date_string = utcnow.strftime("%Y.%m.%d-%H:%M")
    date_file_str = utcnow.strftime("%Y.%m.%d-%H.%M")

    logging.debug(f"\ttimestamp:\t{date_string}")
    data = {"heartbeats": wallet_heartbeats, "timestamp": date_string}
    logging.debug(f"\tdata:\t{data}")

    # write heartbeat to json file
    this_dir = os.path.dirname(os.path.realpath(__file__))
    info_dir = os.path.join(
        this_dir,
        "data",
        "heartbeat_info",
        f"{utcnow.strftime('%Y')}",
        f"{utcnow.strftime('%m')}",
    )
    if not os.path.isdir(info_dir):
        os.makedirs(info_dir)
    info_file = os.path.join(info_dir, f"heartbeat-{date_file_str}.json")

    logging.debug(f"Writing heartbeat data to file: {info_file}")
    with open(info_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.debug("\t...done")


if __name__ == "__main__":
    setup_logging()
    main()
