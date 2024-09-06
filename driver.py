from espn.PickEmClient import PickEmClient
from scoreboard.scoreboard import Scoreboard


def main():
    espn = PickEmClient("c4857724-1309-444b-a767-7ffbf1bff57b")
    teams = espn.get_teams()
    scoreboard = Scoreboard(teams)

    [scoreboard.submit_team_week(team, week) for team in teams for week in range(1, 19)]

    scoreboard.render("/tmp/sb-index.html")
    return


if __name__ == "__main__":
    main()
