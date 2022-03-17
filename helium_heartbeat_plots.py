#! /usr/bin/env python3

"""Generate Plots From Heartbeat Data And Send Them Via Pushover."""

__authors__ = ["Sam Gutentag"]
__email__ = "developer@samgutentag.com"
__maintainer__ = "Sam Gutentag"
__version__ = "2022.03.17.0"

import json
import logging
import os
import time
from datetime import datetime, timedelta
from glob import glob

import matplotlib.pyplot as plt
import pandas as pd
import requests


def setup_logging():
    """Set up  logging filename and ensure logging directory exists."""
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


def load_data(days_back=3):
    """Load collected heartbeat data to dataframe

    Args:
         argument_name (type): description

    Returns:
         return_value (type): description

    Raises:
         ErrorType: description and cause

    """
    this_dir = os.path.dirname(os.path.realpath(__file__))
    data_dir = os.path.join(this_dir, "data", "wallet_heartbeats")
    if not os.path.isdir(data_dir):
        return -1

    # serach for files
    search_slug = os.path.join(data_dir, "*", "*", "*.json")
    files = sorted(glob(search_slug))

    # trim to online include latest (daysback * 144) files
    # 144 being the max number of files collected in 10 minute intervals
    # per day this should match the cron
    file_limit = (days_back + 1) * 144
    logging.debug(f"processing {len(files)} found files...")
    if len(files) > file_limit:
        logging.debug(f"truncating to latest {file_limit} files to speed things up")
        files = files[(-1 * file_limit) :]

    chunks = []
    for _file in files:
        with open(_file) as json_file:
            _data = json.load(json_file)

        chunk = pd.json_normalize(_data)

        # heartbeats is the data
        chunk = pd.DataFrame(_data["heartbeats"])

        chunk = chunk.transpose()

        # append timestamp
        chunk["timestamp"] = pd.to_datetime(_data["timestamp"])

        chunks.append(chunk)

    data = pd.concat(chunks)
    data.reset_index(inplace=True, drop=True)

    # drop unneeded columns
    drop_cols = [
        "status_timestamp",
        "status_height",
        "latest_activity_block",
    ]
    data.drop(drop_cols, axis=1, inplace=True)

    # set data types
    data["blocks_inactive"] = data["blocks_inactive"].astype("int")

    # prune rows with blocks_inactive less than 0
    data = data[data.blocks_inactive >= 0].copy()

    return data


def plot_data(data=None, days_back=3, warning_threshold=450):
    """Plot hotspot heartbeat data"""

    # hotspot status represented in
    wallet_status = []

    latest_date = data.timestamp.max()
    min_date = latest_date - timedelta(days=days_back)
    data = data[data.timestamp >= min_date].copy()
    logging.debug(f"plotting data from {min_date} to {latest_date}")

    # get hotspot count for charts
    hotspot_count = len(data.name.unique())

    fig, axes = plt.subplots(
        ncols=1, nrows=hotspot_count, figsize=(15, hotspot_count * 2), sharex=True
    )

    for idx, hotspot in enumerate(sorted(data.name.unique())):

        hotspot_status = "Y"

        d = data[data.name == hotspot].copy()

        d.sort_values(["timestamp"], inplace=True)
        d.set_index(["timestamp"], inplace=True, drop=True)

        d = d.resample("10T").max()

        d.fillna(method="ffill", inplace=True)

        # get latest value
        latest_value = int(d["blocks_inactive"].values[-1])
        if latest_value > warning_threshold:
            hotspot_status = "N"
        color = "r" if latest_value > warning_threshold else "b"

        marker = "d" if d.shape[0] < 30 else ""

        d["blocks_inactive"].plot(
            ax=axes[idx],
            label=f"[{latest_value}] {hotspot}",
            color=color,
            marker=marker,
        )

        # plot rolling median
        try:
            latest_value_median = int(
                d["blocks_inactive"].rolling(30).median().values[-1]
            )
            d["blocks_inactive"].rolling(30).median().plot(
                ax=axes[idx],
                label=f"[{latest_value_median}] rolling median",
                color="k",
                alpha=0.5,
            )
        except ValueError:
            logging.debug(f"not enough data collected to plot rolling median, skipping")

        axes[idx].legend(loc=2)

        y_max = max(
            [
                latest_value,
                int(d.blocks_inactive.max() * 1.25),
                int(warning_threshold * 1.25),
            ]
        )

        if y_max > warning_threshold:
            y_max = int(warning_threshold * 1.25)

        axes[idx].set_ylim(0, y_max)
        axes[idx].axhline(y=warning_threshold, color="k", alpha=0.75, linestyle=":")

        if latest_value > warning_threshold:
            axes[idx].fill_between(
                x=d.index,
                # y1=warning_threshold,
                y1=0,
                y2=d.blocks_inactive,
                color="r",
                alpha=0.6,
                where=d.blocks_inactive > warning_threshold,
            )

        # draw vertical lines on dates
        date_lines = d.index.map(lambda x: x.date()).unique().values[1:]
        for date_line in date_lines:
            axes[idx].axvline(x=date_line, alpha=0.2)

        axes[idx].set_xticks(ticks=date_lines)

        xtick_labels = [x.strftime("%b %d") for x in date_lines]
        axes[idx].set_xticklabels(xtick_labels)

        # write hotspot data to file
        this_dir = os.path.dirname(os.path.realpath(__file__))
        csv_dir = os.path.join(
            this_dir,
            "data",
            "heartbeat_info",
            "hotspots",
            hotspot,
        )
        if not os.path.isdir(csv_dir):
            os.makedirs(csv_dir)
        csv_file = os.path.join(csv_dir, f"{hotspot}-blocks-inactive.csv")
        d.to_csv(csv_file)

        wallet_status.append(hotspot_status)

    charts_dir = os.path.join(this_dir, "charts")
    if not os.path.isdir(charts_dir):
        os.makedirs(charts_dir)
    chart_file = os.path.join(charts_dir, "heartbeats.png")

    axes[0].set_title("Inactive Block Counters")
    plt.tight_layout()
    plt.xlabel("")

    plt.savefig(chart_file)
    plt.close()

    wallet_status = "".join(sorted(wallet_status))

    return wallet_status, chart_file


def get_previous_wallet_status(wallet_status=None, alert_stale_hours=8):
    """Get Previous Wallet Status, and overwrite with new report.

    Args:
         argument_name (type): description

    Returns:
         return_value (type): description

    Raises:
         ErrorType: description and cause

    """
    previous_wallet_status = {"timestamp": 0, "wallet_status": ""}
    current_wallet_status = {
        "timestamp": int(time.time()),
        "wallet_status": wallet_status,
    }
    logging.debug(f"current wallet status -> {current_wallet_status}")

    # ensure wallet status directory exists
    this_dir = os.path.dirname(os.path.realpath(__file__))
    wallet_status_dir = os.path.join(
        this_dir,
        "data",
        "wallet_status",
    )
    if not os.path.isdir(wallet_status_dir):
        os.makedirs(wallet_status_dir)

    wallet_status_file = os.path.join(wallet_status_dir, "wallet_status.json")

    # if previous wallet_status file exists, read it in
    if os.path.exists(wallet_status_file):
        with open(wallet_status_file) as json_file:
            previous_wallet_status = json.load(json_file)

        # ensure previous_wallet_status timestamp is an integer
        previous_wallet_status["timestamp"] = int(previous_wallet_status["timestamp"])

    logging.debug(f"previous wallet status -> {previous_wallet_status}")

    # check if wallet_status matches previous status
    wallet_change = (
        False
        if previous_wallet_status["wallet_status"]
        == current_wallet_status["wallet_status"]
        else True
    )

    # data is stale if more than alert_stale_hours hours since previous update
    stale_time = int(current_wallet_status["timestamp"] - (alert_stale_hours * 3600))
    data_stale = True if previous_wallet_status["timestamp"] < stale_time else False
    # if data_stale:
    logging.debug(f"previous time:\t{previous_wallet_status['timestamp']}")
    logging.debug(f"current time:\t{current_wallet_status['timestamp']}")
    logging.debug(f"cutoff time: {stale_time}")

    # update previous wallet status file with current data if changed or stale
    if data_stale or wallet_change:
        logging.debug(
            f"previous status update was more than {alert_stale_hours} hours ago or wallet_status has changed, updating file"
        )

        # write current wallet status to update file
        with open(wallet_status_file, "w", encoding="utf-8") as f:
            json.dump(current_wallet_status, f, ensure_ascii=False, indent=2)

    result = {
        "data_stale": data_stale,
        "wallet_change": wallet_change,
        "previous_status": previous_wallet_status,
    }
    logging.debug(f"previous wallet status -> {result}")
    return result


def send_pushover_mesage(wallet_previous_status=None, image_file=None, days_back=3):
    """Short description of this function.

    Longer description of this function.

    Args:
         argument_name (type): description

    Returns:
         return_value (type): description

    Raises:
         ErrorType: description and cause

    """
    # check for pushover tokens
    try:
        pushover_report_token = os.environ["PUSHOVER_APP_TOKEN_HNT_REPORT"]
    except KeyError:
        logging.debug(
            "Could not find `PUSHOVER_APP_TOKEN_HNT_REPORT` in environment variables, can not send message"
        )
        return 0

    try:
        pushover_alert_token = os.environ["PUSHOVER_APP_TOKEN_HNT_ALERT"]
    except KeyError:
        logging.debug(
            "Could not find `PUSHOVER_APP_TOKEN_HNT_ALERT` in environment variables, defaulting to pushover_report_token"
        )
        pushover_alert_token = pushover_report_token

    try:
        user_token = os.environ["PUSHOVER_USER_TOKEN"]
    except KeyError:
        logging.debug(
            "Could not find `PUSHOVER_USER_TOKEN` in environment variables, can not send message"
        )
        return 0

    try:
        pushover_group_token = os.environ["PUSHOVER_GROUP_TOKEN"]
    except KeyError:
        logging.debug(
            "Could not find `PUSHOVER_GROUP_TOKEN` in environment variables, defaulting to user_token"
        )
        pushover_group_token = user_token

    # default status message
    status_message = f"Innactive Block Chart previous {days_back} days"

    # if current wallet status does not match previous wallet status or
    # if it has been more than alert_stale_hours hours, send message
    if wallet_previous_status["wallet_change"] or wallet_previous_status["data_stale"]:
        if wallet_previous_status["wallet_change"]:
            logging.debug(
                f"Sending Message -> wallet_status changed from `{wallet_previous_status['previous_status']['wallet_status']}`to `{wallet_status}`"
            )
            status_message = "Hotspot Status has Changed"
            pushover_token = pushover_alert_token

        if wallet_previous_status["data_stale"]:
            logging.debug("Sending Message -> data is stale")
            status_message = "Timely Update"
            pushover_token = pushover_report_token

        # send image
        _resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": pushover_token,
                "user": pushover_group_token,
                "message": status_message,
            },
            files={"attachment": ("image.jpg", open(image_file, "rb"), "image/jpeg")},
        )
        logging.debug(f"message sent: {_resp}")
        return 0
    logging.debug("no update sent, data is not stale or has not changed")
    return 0


def main():
    """Sample Main Function"""
    days_back = 3

    logging.debug(f"collecting data with the previous {days_back} days")
    data = load_data(days_back=days_back)

    logging.debug("plotting data")
    wallet_status, image_file = plot_data(data, days_back=days_back)
    alert_stale_hours = 4

    # store wallet status to file
    wallet_previous_status = get_previous_wallet_status(
        wallet_status=wallet_status, alert_stale_hours=alert_stale_hours
    )

    send_pushover_mesage(wallet_previous_status, image_file, days_back)


if __name__ == "__main__":
    setup_logging()

    # suppress matplitlib font manager debug messages
    logging.getLogger("matplotlib.font_manager").disabled = True

    main()
