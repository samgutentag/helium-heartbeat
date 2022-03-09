# Helium Heartbeat

![hotspot-heartbeats](./_assets/sample_output_warning.png)

## A Quick Overview

This script collects data for every hotspot in a given wallet, comparing the Helium Blockchain Height to the most recent activity block of each hotspot over time. This data is plotted and sent to the user via the [Pushover][pushover-link] API on a `Timely` and `Alert` basis.

[pushover-link]: https://pushover.net/

## Blog Post

You can find a more detailed walk through on the implementation on [my blog][blog-post-link]

[blog-post-link]: https://gutentag.co/3MzZNAb

## Setup

### virtualenv

This code was written with Python3.9, though I suspect it will work well with Python3.6+ (it uses `f-strings` quite a bit)

Create a virutal environment and install the `requirements` using

```bash
pip install -r requirements.txt
```

### Pushover API Keys

Two [Pushover][pushover-link] Apps are ercommended, at least one is necessary

---
