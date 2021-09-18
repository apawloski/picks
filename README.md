# Winners and Losers Scoreboard 2021

This is the code that makes https://picks.apawl.com. It scrapes the EPSPN site and applies the +1/-2 scoring scheme. It replaces the old by-hand scoring system that was done once a week.

## How it works

The bulk of the work is done by `PickEmClient.py` in the `espn/` directory. It opens a browser, navigates to the ESPN group, navigates to the "group pick grid," and for each week, pages through each page of picks.

It defines Team and Pick classes that are initialized with content from the ESPN site. Each Team has a list of Picks for each week, and methods for computing scores.

`driver.py` takes the teams (and their picks) from `espn.PickEmClient` and submits them to a Scoreboard object (`scoreboard/scoreboard.py`). The Scoreboard object ranks the teams and renders to an ouput file. By default this is `/tmp/sb-index.html`

## Installation

This uses splinter/selenium to open a browser and click around the site. You'll need a [chrome driver](https://sites.google.com/chromium.org/driver/) installed.

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
python driver.py
```

It will save a single html file to /tmp/sb-scoreboard.html
