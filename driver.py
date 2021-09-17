from espn.PickEmClient import PickEmClient
from scoreboard.scoreboard import Scoreboard

def main():
    espn = PickEmClient('f59398d9-bb0f-4467-83c2-d1cb17e4d023')
    teams = espn.get_teams()
    scoreboard = Scoreboard(teams)

    for week in range(1,19):
        for team in teams:
            scoreboard.submit_team_week(team, week)

    scoreboard.render('index.html')
    return

if __name__ == '__main__':
    main()
