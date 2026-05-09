from __future__ import annotations

import json
import sys
from pathlib import Path

from screen_activity_agent.agent import ScreenActivityAgent
from screen_activity_agent.config import load_settings


def main() -> int:
    settings = load_settings(Path.cwd())
    agent = ScreenActivityAgent(settings)
    try:
        record = agent.analyze_once()
    except Exception as exc:
        print(f"识别失败：{exc}", file=sys.stderr)
        return 1

    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
