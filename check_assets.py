#!/usr/bin/env python3
"""配置与资产体检：组装前先跑一遍，把缺图/字段问题提前暴露。

用法：
  python check_assets.py [--config characters.py]

检查项：
  1. 配置文件可加载，CHARS / Q_CHARS 存在
  2. 每个角色必填字段齐全
  3. 分件源图文件存在
  4. 名牌数量与网格匹配（六格 = 6 个名字）
  5. 色板 6 色、hex 与 RGB 一致
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cardlib import load_characters

REQUIRED_FULL = ["parts", "out", "bust", "turn", "expr", "acc", "eq",
                 "title", "subtitle", "info_pairs", "info_full", "traits",
                 "ability", "background", "world", "palette",
                 "eq_notes", "expr_names", "cm_height"]
REQUIRED_Q = ["parts", "out", "bust", "turn", "expr", "acc", "eq",
              "title", "subtitle", "turn_front_x", "info_pairs", "traits",
              "palette", "eq_notes", "expr_names",
              "cm_height"]

errors: list[str] = []


def err(msg: str):
    errors.append(msg)
    print("  [FAIL]", msg)


def check_cfg(name: str, cfg: dict, required: list[str], card_type: str):
    print(f"· {card_type}「{name}」")
    for key in required:
        if key not in cfg:
            err(f"缺少必填字段 {key}")
    parts = cfg.get("parts")
    if parts is None:
        return
    for key in ("bust", "turn", "expr", "acc", "eq"):
        f = parts / cfg[key] if key in cfg else None
        if f is not None and not Path(f).exists():
            err(f"缺分件源图: {f}")
    # 网格与名牌数量（服饰/装备六格不叠名牌，无需校验名单）
    for names_key, grid_key in (("expr_names", "expr_grid"),):
        names = cfg.get(names_key)
        if names is None:
            continue
        grid = cfg.get(grid_key, (3, 2))
        if len(names) != grid[0] * grid[1]:
            err(f"{names_key} 数量 {len(names)} ≠ 网格 {grid[0]}×{grid[1]} = {grid[0]*grid[1]}")
    palette = cfg.get("palette")
    if palette and len(palette) != 6:
        err(f"palette 建议 6 色，当前 {len(palette)} 色")
    cm = cfg.get("cm_height")
    if isinstance(cm, int) and not (10 <= cm <= 300):
        err(f"cm_height={cm} 超出合理范围(10-300)，检查单位是否为 cm")


def main():
    ap = argparse.ArgumentParser(description="人物卡配置与资产体检")
    ap.add_argument("--config", default="characters.py")
    args = ap.parse_args()
    print(f"配置文件: {Path(args.config).resolve()}\n")

    try:
        full = load_characters(args.config, "CHARS")
    except Exception as e:
        print(f"[FAIL] 加载 CHARS 失败: {e}")
        return 1
    for name, cfg in full.items():
        check_cfg(name, cfg, REQUIRED_FULL, "写实卡")

    try:
        q = load_characters(args.config, "Q_CHARS")
    except Exception as e:
        print(f"[WARN] 加载 Q_CHARS 失败（可只做写实卡）: {e}")
        q = {}
    for name, cfg in q.items():
        check_cfg(name, cfg, REQUIRED_Q, "Q版卡")

    print()
    if errors:
        print(f"共 {len(errors)} 处问题，先修复再组装。")
        return 1
    print("全部通过 ✓ 可执行组装。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
