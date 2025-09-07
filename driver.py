import argparse
from espn.PickEmClient import PickEmClient
from scoreboard.scoreboard import Scoreboard

def main():
    parser = argparse.ArgumentParser(description="Generate a scoreboard for an ESPN Pigskin Pick'em group.")
    parser.add_argument("--group_id", required=True, help="The ID of the ESPN Pigskin Pick'em group.")
    parser.add_argument("--output_path", default="/tmp/sb-index.html", help="The path to the output HTML file.")
    parser.add_argument("--week", type=int, help="Run for a single week.")
    args = parser.parse_args()

    espn = PickEmClient(args.group_id)
    espn.run(week=args.week)
    teams = espn.get_teams()
    scoreboard = Scoreboard(teams)

    weeks_to_run = [args.week] if args.week else range(1, 19)
    for team in teams:
        for week in weeks_to_run:
            scoreboard.submit_team_week(team, week)

    scoreboard.render(args.output_path)
    print(f"Scoreboard rendered to {args.output_path}")

if __name__ == "__main__":
    main()
