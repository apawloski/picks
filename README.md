# Winners and Losers Scoreboard 2021

This is the code that makes https://picks.apawl.com. It scrapes the EPSPN site and applies the +1/-2 scoring scheme. It replaces the old by-hand scoring system that was done once a week.

## How it works

The bulk of the work is done by `PickEmClient.py` in the `espn/` directory. It opens a browser, navigates to the ESPN group, navigates to the "group pick grid," and for each week, pages through each page of picks.

It defines Team and Pick classes that are initialized with content from the ESPN site. Each Team has a list of Picks for each week, and methods for computing scores.

`driver.py` takes the teams (and their picks) from `espn.PickEmClient` and submits them to a Scoreboard object (`scoreboard/scoreboard.py`). The Scoreboard object ranks the teams and renders to an ouput file. By default this is `/tmp/sb-index.html`

## Installation

This uses splinter/selenium to open a browser and click around the site. You'll need a [chrome driver](https://sites.google.com/chromium.org/driver/) installed.

```bash
uv sync
```

## CLI Usage

The main tool is accessed through `driver.py` with the following usage:

### Basic Command Structure
```bash
uv run driver.py --group_id <ESPN_GROUP_ID> [OPTIONS]
```

### Required Arguments
- `--group_id` - The ID of the ESPN Pigskin Pick'em group (required)

### Optional Arguments
- `--output_path` - Path for the output HTML file (default: `/tmp/sb-index.html`)
- `--week` - Run for a single specific week instead of all weeks (1-18)

### Usage Examples

1. **Generate scoreboard for entire season:**
```bash
uv run driver.py --group_id 123456
```

2. **Generate scoreboard for specific week:**
```bash
uv run driver.py --group_id 123456 --week 5
```

3. **Custom output location:**
```bash
uv run driver.py --group_id 123456 --output_path ./my_scoreboard.html
```

4. **Full example with all options:**
```bash
uv run driver.py --group_id 123456 --week 10 --output_path ./week10_scoreboard.html
```

### Output

The tool generates an HTML file containing:
- Ranked team standings with total scores
- Weekly breakdown of scores and records
- Timestamp of generation
- Custom "+1/-2" scoring scheme results

The generated HTML file can be opened in any web browser or deployed to a web server.