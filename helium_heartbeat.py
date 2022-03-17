#! /usr/bin/env python3

"""Collect Stats from Hotspots in Wallet."""

__authors__ = ["Sam Gutentag"]
__email__ = "developer@samgutentag.com"
__maintainer__ = "Sam Gutentag"
__version__ = "2022.03.17.0"


import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import helium_api_wrapper


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


def get_latest_active_block(hotspot=None):
    """Get most recent activity block height.

    Active is defined as "activity recorded to the Helium Blockchain"

    Args:
        hotspot (dict): a hotspot information dictionary

    Returns:
        result (int): block height hotspot was most recently active

    Raises:
        Exception: if anything goes wrong, return -1

    """
    try:
        _activity = list(
            helium_api_wrapper.hotspot_activity(hotspot["address"], max_depth=3)
        )[0]
        return _activity["height"]
    except Exception:
        return -1


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
    _heartbeat["chain_height"] = hotspot["block"]

    # get latest activity block
    _heartbeat["latest_activity_block"] = get_latest_active_block(hotspot=hotspot)

    return _heartbeat


def get_wallet_heartbeat(wallet_addr=os.environ["WALLET_ADDR"]):
    """Get heartbeat data for all hotspots in a given wallet.

    Multithreaded collection of heartbeat data for all hotspots associated to
    a given wallet

    Args:
        wallet_addr (string): a wallet address on the Helium Blockchain

    Returns:
        result (dict): dictionary of hotspots heartbeat data

    Raises:
        Exception: broad exception for when the helium API fails to
                    return a list of hotspots for the given wallet
    """

    # get list of hotspots for wallet address
    try:
        wallet_hotspots = helium_api_wrapper.hotspots_for_account(address=wallet_addr)
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
        block_heights.append(heartbeats[name]["chain_height"])
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


def record_heartbeat_data(wallet_heartbeats=None):
    """Write heartbeat data to json files.

    wallet heartbeat data is stored in JSON files for later processing
    and analysis.

    Args:
         wallet_heartbeats (dict): wallet heartbeats data

    Returns:
         info_file (string): output filepath to recorded json data

    """
    # get current utc time
    utcnow = datetime.utcnow()
    date_string = utcnow.strftime("%Y.%m.%d-%H:%M")
    date_file_str = utcnow.strftime("%Y.%m.%d-%H.%M")

    logging.debug(f"\ttimestamp:\t{date_string}")
    data = {"heartbeats": wallet_heartbeats, "timestamp": date_string}
    logging.debug(f"\tdata:\t{data}")

    # write heartbeat to json file
    logging.debug("ensuring output directory exists...")
    this_dir = os.path.dirname(os.path.realpath(__file__))
    info_dir = os.path.join(
        this_dir,
        "data",
        "wallet_heartbeats",
        f"{utcnow.strftime('%Y')}",
        f"{utcnow.strftime('%m')}",
    )
    if not os.path.isdir(info_dir):
        os.makedirs(info_dir)

    # format info filepath
    info_file = os.path.join(info_dir, f"heartbeat-{date_file_str}.json")

    logging.debug(f"Writing heartbeat data to file: {info_file}")
    with open(info_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logging.debug("\t...done")

    return info_file


def main():
    logging.debug("-" * 80)
    logging.debug("Collecting Heartbeats for wallet.")
    wallet_heartbeats = get_wallet_heartbeat()

    # write collected data to file.
    logging.debug("storing wallet heartbeat data")
    record_heartbeat_data(wallet_heartbeats=wallet_heartbeats)


if __name__ == "__main__":
    setup_logging()
    main()
