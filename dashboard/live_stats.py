
import json
import os
import tempfile
from pathlib import Path


STATS_FILE = Path("dashboard/live_stats.json")


def publish_stats(stats):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix="stats_",
        suffix=".tmp",
        dir=str(STATS_FILE.parent),
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(stats, file)
            file.flush()

        os.replace(temp_path, STATS_FILE)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def read_stats():
    if not STATS_FILE.exists():
        return {}

    try:
        with STATS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
