"""打印小程序 10 组命令数组的结构（groupId / index / cmd0 / cmd1 / 原始字节），
并列出插件 COMMANDS 里没有覆盖到的 (cmd0, cmd1)。

用法：
    python tools/dump_command_table.py [app-service.js 路径]
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = ROOT / "custom_components" / "smart_bidet"

_pkg = types.ModuleType("sb")
_pkg.__path__ = [str(PKG_DIR)]
sys.modules["sb"] = _pkg


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"sb.{name}", PKG_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"sb.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")

DEFAULT_JS = Path.home() / "Downloads" / "wxf105815db957545f_unpacked" / "app-service.js"


def nested_arrays(js: str) -> list[list[list[int]]]:
    start = js.index("i = [")
    depth = 0
    token = ""
    groups: list[list[list[int]]] = []
    rows: list[list[int]] = []
    row: list[int] = []
    for ch in js[start + 4 :]:
        if ch.isdigit():
            token += ch
            continue
        if token:
            row.append(int(token))
            token = ""
        if ch == "[":
            depth += 1
            if depth == 1:
                groups = []
            elif depth == 2:
                rows = []
            else:
                row = []
        elif ch == "]":
            if depth == 3:
                rows.append(row)
            elif depth == 2:
                groups.append(rows)
            depth -= 1
            if depth == 0:
                break
        elif ch == ";" and depth == 0:
            break
    return groups


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JS
    groups = nested_arrays(path.read_text(encoding="utf-8", errors="ignore"))
    commands = const.COMMANDS
    covered = {(c[0], c[1]) for c in commands.values()}

    print(f"组数：{len(groups)}，各组条数：" + ", ".join(f"g{i}={len(g)}" for i, g in enumerate(groups)))
    for gid, rows in enumerate(groups):
        print(f"\n== 组 {gid} ==")
        for idx, row in enumerate(rows):
            c0, c1 = row[3], row[4]
            mark = "已覆盖" if (c0, c1) in covered else "缺失"
            print(f"  [{gid},{idx:2d}] cmd0={c0:#04x} cmd1={c1:#04x}  {mark}  raw={row}")

    pairs = {(row[3], row[4]) for rows in groups for row in rows}
    unused = sorted((c[0], c[1], k) for k, c in commands.items() if (c[0], c[1]) not in pairs)
    if unused:
        print("\n插件里有、原始表里没有：")
        for c0, c1, k in unused:
            print(f"  {k}: {c0:#04x} {c1:#04x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
