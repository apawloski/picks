from espn.helpers import Helpers

class Pick:
    def __init__(self, pick_td):
        self.pick = pick_td
        team_icon = self.pick.find("img")
        self.team_picked = team_icon["alt"]

    def is_incorrect(self):
        legacy_crossmark = self.pick.find(class_="css-8wf538") is not None
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
        correct_check_mark = self.pick.find(class_="css-1skkwww") is not None
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
