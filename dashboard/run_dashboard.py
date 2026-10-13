
from dashboard.live_stats import read_stats
from dashboard.terminal_dashboard import TerminalDashboard


def main():
    dashboard = TerminalDashboard()
    dashboard.run(stats_provider=read_stats)


if __name__ == "__main__":
    main()
