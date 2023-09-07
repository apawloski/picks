import datetime
import jinja2


class Scoreboard:
    def __init__(self, teams):
        self.winner = None
        self.teams_to_weekly_scores = {}
        self.teams_to_weekly_records = {}

        for team in teams:
            # This is a map of team_name -> array of week scores for that team
            # Each element in a team's array is that team's total score for that week
            self.teams_to_weekly_scores[team.name] = [0] * 18

            # This is a map of team_name -> array of week records for that team
            # Each element in a team's array is that teams record (W-L-T) for that week
            self.teams_to_weekly_records[team.name] = [0] * 18

    def render(self, out_file):
        unranked_team_totals = {}
        for team in self.teams_to_weekly_scores:
            unranked_team_totals[team] = sum(self.teams_to_weekly_scores[team])

        # Sort the teams -- highest season-score first
        sorted_team_totals = {
            k: v
            for k, v in sorted(
                unranked_team_totals.items(), key=lambda item: item[1], reverse=True
            )
        }

        # Generates list of tuples (Rank, Team, Score)
        ranked_team_totals = []
        rank = 1
        last_score = None
        for i, team in enumerate(sorted_team_totals):
            score = sorted_team_totals[team]
            if score != last_score:
                rank = i + 1
            ranked_team_totals.append((rank, team, score))
            last_score = score

        templateLoader = jinja2.FileSystemLoader(searchpath="./scoreboard/")
        templateEnv = jinja2.Environment(loader=templateLoader)
        TEMPLATE_FILE = "scoreboard_template.html.jinja2"
        template = templateEnv.get_template(TEMPLATE_FILE)
        output = template.render(
            ranked_team_totals=ranked_team_totals,
            teams_to_weekly_scores=self.teams_to_weekly_scores,
            teams_to_weekly_records=self.teams_to_weekly_records,
            now=datetime.datetime.now(),
        )

        with open(out_file, "w") as f:
            f.write(output)

    def submit_team_week(self, team, week):
        self.teams_to_weekly_scores[team.name][week - 1] = team.get_weekly_score(week)

        self.teams_to_weekly_records[team.name][week - 1] = team.get_weekly_record(week)
        return
