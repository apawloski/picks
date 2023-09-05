from espn.PickEmClient import PickEmClient
from scoreboard.scoreboard import Scoreboard

def main():
    espn = PickEmClient('fb23255b-65c1-41a0-a55b-b14cfa617a7b')
    teams = espn.get_teams()
    scoreboard = Scoreboard(teams)

    [scoreboard.submit_team_week(team, week) for team in teams for week in range(1,19)]

    scoreboard.render('/tmp/sb-index.html')
    return

if __name__ == '__main__':
    main()
