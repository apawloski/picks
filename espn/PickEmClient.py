import random
from bs4 import BeautifulSoup
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from splinter import Browser
from splinter.exceptions import ElementDoesNotExist
import time
import os
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

class PickEmClient:
    def __init__(self, group_id):
        self.teams = {}  # Maps team name to Team object

        weeks_to_soups = {}
        for w in range(0, 19):
            weeks_to_soups[w] = []

        with Browser("chrome", headless=True) as browser:
            browser.visit(
                f"https://fantasy.espn.com/games/nfl-pigskin-pickem-2024/group?id={group_id}"
            )

            buttons = browser.find_by_text("Group Picks")
            buttons.first.click()

            # Wait for the dropdown to appear on the page
            wait = WebDriverWait(browser.driver, 5)
            try:
                wait.until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//*[contains(@class, 'dropdown__select')]")
                    ),
                    "The Group Picks' 'weeks' dropdown did not appear within 3 seconds",
                )
                weeks = browser.find_by_xpath(
                    "//*[contains(@class, 'dropdown__select')]"
                )
                weeks_to_select = weeks.find_by_tag("option")
            except TimeoutException:
                weeks_to_select = [None]

            weeks = browser.find_by_xpath("//*[contains(@class, 'dropdown__select')]")
            weeks_to_select = weeks.find_by_tag("option")

            for week in weeks_to_select:
                week_num = int(week.text.lower().split("week ")[-1])
                weeks.select(week.value)
                time.sleep(2)  # Wait for the page to load

                pick_grids = []
                self.go_to_first_page(browser)

                page_num = 1
                while True:
                    logger.info(f"Processing Week {week_num}, Page {page_num}")
                    
                    # Handle the current page
                    try:
                        pick_grid = browser.find_by_xpath("//*[contains(@class, 'GroupPickGrid-table')]").first
                        # Scroll the pick_grid into view
                        browser.execute_script("arguments[0].scrollIntoView(true);", pick_grid._element)
                        time.sleep(1)  # Wait for the scroll to complete
                        
                        pick_grid_html = pick_grid['outerHTML']

                        # Debug: Save the grids/screenshots
                        # Create output directory
                        output_dir = "pick_grid_output"
                        os.makedirs(output_dir, exist_ok=True)
                        
                        # Save the pick_grid to an HTML file
                        html_filename = f"week_{week_num}_page_{page_num}.html"
                        html_filepath = os.path.join(output_dir, html_filename)
                        with open(html_filepath, 'w', encoding='utf-8') as f:
                            f.write("<html><body>")
                            f.write(pick_grid_html)
                            f.write("</body></html>")
                        logger.info(f"Saved pick grid HTML to {html_filepath}")
                        
                        # Save a screenshot of the pick_grid
                        png_filename = f"week_{week_num}_page_{page_num}.png"
                        png_filepath = os.path.join(output_dir, png_filename)

                        # Wait for the element to be visible
                        browser.is_element_visible_by_xpath("//*[contains(@class, 'GroupPickGrid-table')]", wait_time=10)

                        # Take screenshot of the entire page
                        browser.driver.save_screenshot(png_filepath)
                        logger.info(f"Saved pick grid screenshot to {png_filepath}")

                        # Actually queue it for processing
                        pick_grids.append(pick_grid_html)
                        logger.info(f"Appended pick grid for Week {week_num}, Page {page_num}")                        
                    except ElementDoesNotExist:
                        logger.error(f"Warning: No pick grid found for Week {week_num}, Page {page_num}")

                    # Try to find the next page button
                    try:
                        next_button = browser.find_by_xpath("//button[contains(@class, 'Pagination__Button--next') and not(@disabled)]").first
                        if next_button:
                            browser.execute_script("arguments[0].scrollIntoView(true);", next_button._element)
                            time.sleep(2)
                            browser.execute_script("arguments[0].click();", next_button._element)
                            time.sleep(2)
                            page_num += 1
                        else:
                            logger.info(f"No more pages for Week {week_num}")
                            break
                    except ElementDoesNotExist:
                        logger.info(f"No more pages for Week {week_num}")
                        break

                # Process pick_grids for this week
                for pick_grid in pick_grids:
                    weeks_to_soups[week_num].append(BeautifulSoup(pick_grid, "html.parser"))


        for week in weeks_to_soups:
            soups = weeks_to_soups[week]
            for soup in soups:
                tables = soup.find_all("table")
                idx_to_name = {}
                for table in tables:
                    if "GROUP ENTRIES" in table.text.upper():
                        rows = table.find_all("tr")
                        # Skip first two rows which are not teams
                        for row in rows[2:]:
                            # Get the team name and id
                            idx = int(row["data-idx"])
                            name_row = row.find(
                                "td",
                                {
                                    "class": "Table__TD GroupPickGrid-column--entryName Table__TD"
                                },
                            )
                            name = name_row.find_all(
                                "a", {"class": "GroupPickGrid-entryLink"}
                            )[-1]
                            if name:
                                idx_to_name[idx] = name.text
                                if not self.teams.get(name.text):
                                    self.teams[name.text] = Team(name.text, "owner")
                    elif "PICKS" in table.text.upper():
                        for row in table.find_all("tr"):
                            current_team_idx = int(row["data-idx"])
                            current_team_name = idx_to_name.get(current_team_idx)
                            if current_team_name:
                                current_team = self.teams[current_team_name]
                                for pick in row.find_all(
                                    "td", {"class": "GroupPickGrid-column--pick"}
                                ):
                                    # I hate the phrasing of this boolean.
                                    # We want to skip "noPick" tds and empty
                                    # tds (which have no children)
                                    if (
                                        not any(
                                            x for x in pick["class"] if "noPick" in x
                                        )
                                        and len(list(pick.children)) > 0
                                    ):
                                        current_team.add_weekly_pick(week, Pick(pick))

    def get_teams(self):
        return self.teams.values()

    def go_to_first_page(self, browser):
        while True:
            try:
                prev_button = browser.find_by_xpath("//button[contains(@class, 'Pagination__Button--prev') and not(@disabled)]").first
                if prev_button:
                    browser.execute_script("arguments[0].scrollIntoView(true);", prev_button._element)
                    time.sleep(2)
                    try:
                        prev_button.click()
                    except ElementClickInterceptedException:
                        logger.error("ElementClickInterceptedException occurred. Taking screenshot.")
                        browser.driver.save_screenshot("error_screenshot.png")
                        logger.error("Screenshot saved as 'error_screenshot.png'")
                        raise  # Re-raise the exception to exit the function
                    time.sleep(2)
                else:
                    break
            except ElementDoesNotExist:
                break


class Pick:
    def __init__(self, pick_td):
        self.pick = pick_td
        team_icon = self.pick.find("img")
        self.team_picked = team_icon["alt"]

    def is_incorrect(self):
        legacy_crossmark = self.pick.find(class_="ct-crossMark") is not None
        return legacy_crossmark or self.pick.find(class_="PickIncorrect-crossMark") is not None

    def is_tie(self, week):
        tie_list = Helpers.weeks_to_ties(week)
        if Helpers.team_name_to_abbr(self.team_picked) in tie_list:
            return True
        return False

    def is_push(self):
        return any("noPick" in x for x in self.pick["class"])
    
    def is_correct(self):
        # It looks like ESPN will use either of these..
        correct_check_mark = self.pick.find(class_="ct-checkMark") is not None
        return correct_check_mark or self.pick.find(class_="PickCorrect-checkMark") is not None

class Team:
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner
        self.weeks_to_picks = {}
        for week in range(1, 19):
            self.weeks_to_picks[week] = []

    def add_weekly_pick(self, week, pick):
        self.weeks_to_picks[week].append(pick)

    def get_weekly_picks(self, week):
        return self.weeks_to_picks[week]

    def get_weekly_num_correct(self, week):
        return len([pick for pick in self.get_weekly_picks(week) if pick.is_correct()])

    def get_weekly_num_incorrect(self, week):
        # Life is suffering
        return len(
            [
                pick
                for pick in self.get_weekly_picks(week)
                if pick.is_incorrect()
                and Helpers.team_name_to_abbr(pick.team_picked)
                not in Helpers.weeks_to_ties(week)
            ]
        )

    def get_weekly_num_ties(self, week):
        return len([pick for pick in self.get_weekly_picks(week) if pick.is_tie(week)])

    def get_weekly_score(self, week):
        return self.get_weekly_num_correct(week) - 2 * self.get_weekly_num_incorrect(
            week
        )

    def get_weekly_record(self, week):
        return f"({self.get_weekly_num_correct(week)}-{self.get_weekly_num_incorrect(week)}-{self.get_weekly_num_ties(week)})"


class Helpers:
    @staticmethod
    def weeks_to_ties(week):
        week_tie_map = {
            1: [],  # e.g. ["PHI", "ATL"]
            2: [],
            3: [],
            4: [],
            5: [],
            6: [],
            7: [],
            8: [],
            9: [],
            10: [],
            11: [],
            12: [],
            13: [],
            14: [],
            15: [],
            16: [],
            17: [],
            18: [],
        }
        return week_tie_map[week]

    @staticmethod
    def team_name_to_abbr(team_name):
        abbr_map = {
            "Arizona Cardinals": "ARI",
            "Atlanta Falcons": "ATL",
            "Baltimore Ravens": "BAL",
            "Buffalo Bills": "BUF",
            "Carolina Panthers": "CAR",
            "Chicago Bears": "CHI",
            "Cincinnati Bengals": "CIN",
            "Cleveland Browns": "CLE",
            "Dallas Cowboys": "DAL",
            "Denver Broncos": "DEN",
            "Detroit Lions": "DET",
            "Green Bay Packers": "GB",
            "Houston Texans": "HOU",
            "Indianapolis Colts": "IND",
            "Jacksonville Jaguars": "JAC",
            "Kansas City Chiefs": "KC",
            "Las Vegas Raiders": "LV",
            "Los Angeles Chargers": "LAC",
            "Los Angeles Rams": "LAR",
            "Miami Dolphins": "MIA",
            "Minnesota Vikings": "MIN",
            "New England Patriots": "NE",
            "New Orleans Saints": "NO",
            "New York Giants": "NYG",
            "New York Jets": "NYJ",
            "Philadelphia Eagles": "PHI",
            "Pittsburgh Steelers": "PIT",
            "San Francisco 49ers": "SF",
            "Seattle Seahawks": "SEA",
            "Tampa Bay Buccaneers": "TB",
            "Tennessee Titans": "TEN",
            "Washington Commanders": "WAS",
        }
        return abbr_map[team_name]
