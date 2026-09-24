#!/usr/bin/env python3
"""写实完整人物卡组装引擎。

卡片结构（2048 宽，从上到下）：
  标题条 → 主肖像 | 角色信息 → 人物背景 | 世界观设定
  → 统一刻度三视图 | 微表情六态 → 服饰六格 | 装备六格+注记 → 底注条

用法：
  python compose_full_card.py 角色名 [--config characters.py]

角色配置放在 characters.py（参考 characters.example.py），
分件源图建议由 AI 按提示词模板生成（见 SKILL.md / README）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from cardlib import (
    W, EDGE, GAP, BG, PANEL, INK, MUTED, ACCENT, LINE, BAND, CREAM,
    font, fill_wm, patch_wm, fit_width, fit_box_pad, _wrap,
    build_turn_with_scale, caption_grid, section_label, chip_row,
    load_characters,
)


# ---------------------------------------------------------------------------
# 角色信息面板
# ---------------------------------------------------------------------------
def build_info_panel(w: int, h: int, cfg: dict) -> Image.Image:
    panel = Image.new("RGB", (w, h), PANEL)
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 0, 6, h], fill=ACCENT)
    pad = 26

    d.text((pad, 18), "角色信息", fill=ACCENT, font=font(38, True))
    y = 74
    d.line([(pad, y), (w - pad, y)], fill=LINE, width=2)
    y += 16
    key_f, val_f = font(26), font(28)
    for k, v in cfg["info_pairs"]:
        d.text((pad, y), k, fill=MUTED, font=key_f)
        d.text((pad + 150, y - 2), v, fill=INK, font=val_f)
        y += 40
    y += 6

    for k, v in cfg["info_full"]:
        d.text((pad, y), k, fill=MUTED, font=key_f)
        d.text((pad + 150, y - 2), v, fill=INK, font=val_f)
        y += 40
    y += 10
    d.line([(pad, y), (w - pad, y)], fill=LINE, width=2)
    y += 16

    d.text((pad, y), "性格六态", fill=ACCENT, font=font(30, True))
    y = chip_row(d, pad + 170, y - 2, cfg["traits"], font(26))
    d.text((pad, y), "能力", fill=ACCENT, font=font(30, True))
    n_lines = len(_wrap(d, cfg["ability"], font(28), w - pad * 2 - 150))
    for i, line in enumerate(_wrap(d, cfg["ability"], font(28), w - pad * 2 - 150)):
        d.text((pad + 150, y + i * 36 - 2), line, fill=INK, font=font(28))
    y += 36 * max(1, n_lines) + 14
    d.line([(pad, y), (w - pad, y)], fill=LINE, width=2)
    y += 16

    d.text((pad, y), "色彩基准", fill=ACCENT, font=font(30, True))
    y += 46
    n = len(cfg["palette"])
    sw = min(96, (w - pad * 2 - (n - 1) * 14) // n)
    for i, (hexv, rgb) in enumerate(cfg["palette"]):
        x = pad + i * (sw + 14)
        d.ellipse([x, y, x + sw, y + sw], fill=rgb, outline=LINE, width=2)
        hb = d.textbbox((0, 0), hexv, font=font(20))
        d.text((x + (sw - (hb[2] - hb[0])) // 2, y + sw + 6), hexv, fill=MUTED, font=font(20))
    y += sw + 40

    d.line([(pad, y), (w - pad, y)], fill=LINE, width=2)
    y += 14
    usage = ("出图挂图：生图时挂本卡或分件源图做参考；"
             "脸与服饰以本卡为准，生成图禁画文字气泡。")
    for line in _wrap(d, usage, font(24), w - pad * 2):
        if y > h - 40:
            break
        d.text((pad, y), line, fill=MUTED, font=font(24))
        y += 32
    return panel


def build_text_row(w: int, h: int, cfg: dict) -> Image.Image:
    panel = Image.new("RGB", (w, h), PANEL)
    d = ImageDraw.Draw(panel)
    pad = 28
    half = w // 2
    title_f, body_f = font(32, True), font(28)
    lh = 42

    d.text((pad, 20), "人物背景", fill=ACCENT, font=title_f)
    d.line([(pad, 66), (half - pad, 66)], fill=LINE, width=2)
    y = 84
    for line in _wrap(d, cfg["background"], body_f, half - pad * 2):
        d.text((pad, y), line, fill=INK, font=body_f)
        y += lh

    d.text((half + pad // 2, 20), "世界观设定", fill=ACCENT, font=title_f)
    d.line([(half + pad // 2, 66), (w - pad, 66)], fill=LINE, width=2)
    y = 84
    for line in _wrap(d, cfg["world"], body_f, w - half - pad * 2 + pad // 2):
        d.text((half + pad // 2, y), line, fill=INK, font=body_f)
        y += lh
    d.line([(half, 16), (half, h - 16)], fill=LINE, width=2)
    return panel


# ---------------------------------------------------------------------------
# 组装主流程
# ---------------------------------------------------------------------------
def compose_one(name: str, cfg: dict) -> Path:
    parts: Path = cfg["parts"]
    name_prefix = cfg.get("prefix", name)

    # ---- 分件预处理（同时落盘，供后续复用）----
    bust = Image.open(parts / cfg["bust"]).convert("RGB")
    if cfg.get("bust_wm", "crop") == "copy":
        bust = patch_wm(bust)
    else:
        bust = bust.crop((0, 0, bust.width, int(bust.height * 0.938)))  # 裁掉水印带
    turn = build_turn_with_scale(parts / cfg["turn"], cfg["cm_height"],
                                 x0=cfg.get("turn_front_x", (50, 345))[0],
                                 x1=cfg.get("turn_front_x", (50, 345))[1],
                                 wm=cfg.get("turn_wm", "corner"),
                                 patch_x=cfg.get("turn_patch_x", 0.58),
                                 patch_span=cfg.get("turn_patch_span", (0.315, 0.4167)))
    turn.save(parts / f"{name_prefix}_三视图_统一刻度.png")
    expr = caption_grid(parts / cfg["expr"], cfg["expr_names"],
                        grid=cfg.get("expr_grid", (3, 2)))
    expr.save(parts / f"{name_prefix}_微表情表.png")
    acc = caption_grid(parts / cfg["acc"], cfg["acc_names"],
                       grid=cfg.get("acc_grid", (3, 2)))
    acc.save(parts / f"{name_prefix}_服饰图鉴.png")
    eq = caption_grid(parts / cfg["eq"], cfg["eq_names"])
    eq.save(parts / f"{name_prefix}_装备图鉴.png")

    rows: list[Image.Image] = []

    # ---- 标题条 ----
    th_ = 88
    title = Image.new("RGB", (W, th_), BAND)
    td = ImageDraw.Draw(title)
    td.text((EDGE, 14), cfg["title"], fill=CREAM, font=font(46, True))
    tb = td.textbbox((0, 0), cfg["subtitle"], font=font(28))
    td.text((W - EDGE - (tb[2] - tb[0]), 32), cfg["subtitle"],
            fill=(200, 214, 218), font=font(28))
    rows.append(title)

    # ---- Row1: 主肖像 | 角色信息 ----
    bust_w = 640
    bust_img = fit_width(bust, bust_w)
    info_w = W - EDGE * 2 - GAP - bust_w
    row1_h = min(920, bust_img.height)
    if bust_img.height > row1_h:
        bust_img = bust_img.crop((0, 0, bust_w, row1_h))
    info = build_info_panel(info_w, row1_h, cfg)
    row1 = Image.new("RGB", (W, row1_h), BG)
    row1.paste(bust_img, (EDGE, 0))
    row1.paste(info, (EDGE + bust_w + GAP, 0))
    rows.append(row1)

    # ---- Row2: 背景 | 世界观 ----
    rows.append(build_text_row(W, 380, cfg))

    # ---- Row3: 统一刻度三视图 | 微表情六态（等高并排）----
    turn_w = 953
    expr_w = W - EDGE * 2 - GAP - turn_w
    turn_img = fit_width(turn, turn_w)
    expr_img = fit_width(expr, expr_w)
    body_h = min(turn_img.height, expr_img.height)
    if turn_img.height > body_h:
        turn_img = turn_img.resize((round(turn_w * body_h / turn_img.height), body_h),
                                   Image.Resampling.LANCZOS)
        turn_img = fit_box_pad(turn_img, turn_w, body_h)
    if expr_img.height != body_h:  # 等比缩放到列高再横向衬底，保住底排名牌
        nw = max(1, round(expr_w * body_h / expr_img.height))
        expr_img = expr_img.resize((nw, body_h), Image.Resampling.LANCZOS)
        expr_img = fit_box_pad(expr_img, expr_w, body_h)
    lab_t = section_label(f"三视图 · 统一刻度（10cm/格 · 身高{cfg['cm_height']}cm）",
                          turn_w, 48)
    lab_e = section_label("微表情 · 六态", expr_w, 48)
    col_h = 48 + body_h
    row3 = Image.new("RGB", (W, col_h), BG)
    tc = Image.new("RGB", (turn_w, col_h), PANEL)
    tc.paste(lab_t, (0, 0)); tc.paste(turn_img, (0, 48))
    ec = Image.new("RGB", (expr_w, col_h), PANEL)
    ec.paste(lab_e, (0, 0)); ec.paste(expr_img, (0, 48))
    row3.paste(tc, (EDGE, 0))
    row3.paste(ec, (EDGE + turn_w + GAP, 0))
    rows.append(row3)

    # ---- Row4: 服饰细节 | 装备图鉴+注记 ----
    acc_w = 1090
    eq_w = W - EDGE * 2 - GAP - acc_w
    acc_img = fit_width(acc, acc_w)
    eq_img = fit_width(eq, eq_w)
    note_f = font(25)
    note_h = 30 + len(cfg["eq_notes"]) * 40 + 16
    body4 = max(acc_img.height, eq_img.height + note_h)
    lab_a = section_label(cfg.get("acc_label", "全套服饰与配件细节"), acc_w, 48)
    lab_q = section_label(cfg.get("eq_label", "随身装备"), eq_w, 48)
    col4 = 48 + body4
    row4 = Image.new("RGB", (W, col4), BG)
    ac = Image.new("RGB", (acc_w, col4), PANEL)
    ac.paste(lab_a, (0, 0)); ac.paste(acc_img, (0, 48))
    ec2 = Image.new("RGB", (eq_w, col4), PANEL)
    ec2.paste(lab_q, (0, 0)); ec2.paste(eq_img, (0, 48))
    nd = ImageDraw.Draw(ec2)
    ny = 48 + eq_img.height + 20
    for note in cfg["eq_notes"]:
        nd.text((20, ny), note, fill=INK, font=note_f)
        ny += 40
    row4.paste(ac, (EDGE, 0))
    row4.paste(ec2, (EDGE + acc_w + GAP, 0))
    rows.append(row4)

    # ---- 底注条 ----
    foot_h = 56
    foot = Image.new("RGB", (W, foot_h), BG)
    fd = ImageDraw.Draw(foot)
    msg = cfg.get("foot", "造型口径以设定文档为准 ｜ 新规则：统一刻度 + 配件细节大图")
    fb = fd.textbbox((0, 0), msg, font=font(24))
    fd.text(((W - (fb[2] - fb[0])) // 2, 16), msg, fill=MUTED, font=font(24))
    rows.append(foot)

    # ---- 堆叠 ----
    total_h = sum(r.height for r in rows) + EDGE
    canvas = Image.new("RGB", (W, total_h), BG)
    y = EDGE // 2
    for r in rows:
        canvas.paste(r, (0, y))
        y += r.height
    canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=2))
    out: Path = cfg["out"]
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "PNG", optimize=True)
    print(f"{name}: {canvas.size} -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description="写实完整人物卡组装")
    ap.add_argument("names", nargs="*", help="角色名（须已在配置中定义；缺省则组装全部）")
    ap.add_argument("--config", default="characters.py", help="角色配置文件路径")
    args = ap.parse_args()
    chars = load_characters(args.config, "CHARS")
    names = args.names or list(chars.keys())
    for n in names:
        if n not in chars:
            print(f"skip（配置中不存在）: {n}")
            continue
        compose_one(n, chars[n])


if __name__ == "__main__":
    main()
