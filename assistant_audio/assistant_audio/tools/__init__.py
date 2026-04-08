from __future__ import annotations

from pathlib import Path
import runpy


def run_top_level_tool(filename: str) -> None:
    tool_path = Path(__file__).resolve().parents[2] / 'tools' / filename
    module_globals = runpy.run_path(str(tool_path))
    main = module_globals.get('main')
    if callable(main):
        main()
