from bs4 import BeautifulSoup
from splinter import Browser
import time


class PickEmClient:

    def __init__(self, group_id):
        self.teams = {} # Maps team name to Team object

        weeks_to_soups = {}
        for w in range(0,19):
            weeks_to_soups[w] = []

        with Browser('chrome', headless=True) as browser:
            browser.visit(f"https://fantasy.espn.com/games/nfl-pigskin-pickem-2021/group?id={group_id}")
            buttons = browser.find_by_text('Group Picks')
            buttons.first.click()
            # This is a hack to avoid the first page of teams turning up 0
            time.sleep(2)

            weeks = browser.find_by_xpath("//*[contains(@class, 'dropdown__select')]")


            for week in weeks.find_by_tag('option'):
                week_num = int(week.text.lower().split('week ')[-1])
                weeks.select(week.value)
                time.sleep(2)

                page_buttons = browser.find_by_xpath("//*[contains(@class, 'Pagination__list__item pointer inline-flex justify-center items-center')]")

                pick_grids = []
                for page_button in page_buttons:
                    page_button.click()
                    time.sleep(1)
                    pick_grids.append(browser.find_by_xpath("//*[contains(@class, 'GroupPickGrid-table')]").first.html)

                for pick_grid in pick_grids:
                    weeks_to_soups[week_num].append(BeautifulSoup(pick_grid, 'html.parser'))

        for week in weeks_to_soups:
            soups = weeks_to_soups[week]
            for soup in soups:
                tables = soup.find_all('table')
                idx_to_name = {}
                for table in tables:
                    if 'GROUP ENTRIES' in table.text.upper():
                        rows = table.find_all('tr')
                        for row in rows:
                            # Get the team name and id
                            idx = int(row['data-idx'])
                            name = row.find('td', {"class": "GroupPickGrid-column--entryName Table__TD"})
                            if name:
                                idx_to_name[idx] = name.text
                                if not self.teams.get(name.text):
                                    self.teams[name.text] = Team(name.text, 'owner')
                    elif 'PICKS' in table.text.upper():
                        for row in table.find_all('tr'):
                            current_team_idx = int(row['data-idx'])
                            current_team_name = idx_to_name.get(current_team_idx)
                            if current_team_name:
                                current_team = self.teams[current_team_name]
                                for pick in row.find_all('td'):
                                    # I hate the phrasing of this boolean.
                                    # We want to skip "noPick" tds and empty
                                    # tds (which have no children)
                                    if not any(x for x in pick['class'] if 'noPick' in x) and len(list(pick.children)) > 0:
                                        current_team.add_weekly_pick(week, Pick(pick))

    def get_teams(self):
        return self.teams.values()

class Pick:

    def __init__(self, pick_td):
        self.pick = pick_td
        team_icon = self.pick.find('img')
        self.team_picked = team_icon['alt']

    def is_incorrect(self):
        return any("incorrect" in x for x in self.pick['class'])

    def is_tie(self):
        tie_list = []
        if Helpers.team_name_to_abbr(self.team_picked) in tie_list:
            return True
        return False

    def is_push(self):
        return any("noPick" in x for x in self.pick['class'])

    def is_correct(self):
        circle = self.pick.find('circle')
        if circle:
            return circle['fill'] == '#0d830f'
        return False

class Team:

    def __init__(self, name, owner):
        self.name = name
        self.owner = owner
        self.weeks_to_picks = {}
        for week in range(1,19):
            self.weeks_to_picks[week] = []

    def add_weekly_pick(self, week, pick):
        self.weeks_to_picks[week].append(pick)

    def get_weekly_picks(self, week):
        return self.weeks_to_picks[week]

    def get_weekly_num_correct(self, week):
        return len([pick for pick in self.get_weekly_picks(week) if pick.is_correct()])

    def get_weekly_num_incorrect(self, week):
        # Life is suffering
        return len([pick for pick in self.get_weekly_picks(week) if pick.is_incorrect() and Helpers.team_name_to_abbr(pick.team_picked) not in Helpers.weeks_to_ties(week)])

    def get_weekly_num_ties(self, week):
        return len([pick for pick in self.get_weekly_picks(week) if pick.is_tie()])

    def get_weekly_score(self, week):
        return self.get_weekly_num_correct(week) - 2*self.get_weekly_num_incorrect(week)

    def get_weekly_record(self, week):
        return f"({self.get_weekly_num_correct(week)}-{self.get_weekly_num_incorrect(week)}-{self.get_weekly_num_ties(week)})"

class Helpers:

    @staticmethod
    def weeks_to_ties(week):
        week_tie_map = {
            1: [], # e.g. ["PHI", "ATL"]
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
            18: []
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
            "Washington": "WAS"
      }
        return abbr_map[team_name]
