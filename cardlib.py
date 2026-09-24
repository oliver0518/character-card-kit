#!/usr/bin/env python3
"""人物卡共享绘图库。

包含：跨平台中文字体加载、AI 生成图的水印修补、统一刻度三视图（cm 刻度线）、
网格逐格名牌（caption_grid）、性格 chips、文字换行等全部卡片组装共用函数。

 compose_full_card.py（写实完整卡）与 compose_q_card.py（Q 版卡）都从本库导入。
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 画布与配色（浅色主题；分件源图底色建议 ≈ (240, 237, 231)，组装后色带才齐）
# ---------------------------------------------------------------------------
W = 2048          # 成品卡宽度
EDGE = 24         # 画布留边
GAP = 12          # 板块间距

BG = (240, 237, 231)        # 画布底色
PANEL = (250, 248, 244)     # 面板底色
INK = (43, 46, 44)          # 正文墨色
MUTED = (112, 118, 114)     # 弱化文字
ACCENT = (47, 90, 102)      # 强调色（墨青）
LINE = (198, 190, 174)      # 分隔线
BAND = (42, 59, 66)         # 名牌深青
CREAM = (245, 242, 236)     # 名牌文字奶油色

# ---------------------------------------------------------------------------
# 跨平台中文字体：按顺序探测，也可用环境变量 CARD_FONT 强制指定
# ---------------------------------------------------------------------------
_FONT_CANDIDATES = [
    os.environ.get("CARD_FONT", ""),                      # 用户强制指定
    "/System/Library/Fonts/Hiragino Sans GB.ttc",         # macOS 冬青黑
    "/System/Library/Fonts/PingFang.ttc",                 # macOS 苹方
    "/System/Library/Fonts/STHeiti Light.ttc",            # macOS 旧版黑体
    "C:/Windows/Fonts/msyh.ttc",                          # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",                        # Windows 黑体
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",   # Linux Noto
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",           # Linux 文泉驿
]

_font_path: str | None = None


def _resolve_font() -> str:
    global _font_path
    if _font_path:
        return _font_path
    for cand in _FONT_CANDIDATES:
        if cand and Path(cand).exists():
            _font_path = cand
            return cand
    raise RuntimeError(
        "未找到可用的中文字体。请安装系统中文字体，或设置环境变量 "
        "CARD_FONT=/path/to/字体.ttf(ttc) 后重试。"
    )


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _resolve_font()
    try:
        return ImageFont.truetype(path, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.truetype(path, size)


# ---------------------------------------------------------------------------
# AI 生成图右下角水印修补（生成平台自带水印时按需选用）
# ---------------------------------------------------------------------------
def fill_wm(im: Image.Image) -> Image.Image:
    """右下水印区用角部底色填充（仅平整背景图适用）。"""
    W_, H_ = im.size
    bg = im.crop((10, 10, 70, 70)).resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    ImageDraw.Draw(im).rectangle(
        [int(W_ * 0.85), int(H_ * 0.94), W_ - 1, H_ - 1], fill=bg
    )
    return im


def patch_wm(im: Image.Image, src_x0: float = 0.58) -> Image.Image:
    """水印压在人物/深色物上时：从同行左侧复制同尺寸干净块贴盖。"""
    W_, H_ = im.size
    x0, y0 = int(W_ * 0.845), int(H_ * 0.935)
    box_w, box_h = W_ - x0, H_ - y0
    sx = int(W_ * src_x0)
    patch = im.crop((sx, y0, sx + box_w, y0 + box_h))
    im.paste(patch, (x0, y0))
    return im


def fit_width(im: Image.Image, width: int) -> Image.Image:
    h = max(1, round(im.height * width / im.width))
    return im.resize((width, h), Image.Resampling.LANCZOS)


def fit_box_pad(im: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """居中衬底到目标框（不再缩放）。"""
    canvas = Image.new("RGB", (box_w, box_h), PANEL)
    if im.width > box_w:
        x0 = (im.width - box_w) // 2
        im = im.crop((x0, 0, x0 + box_w, im.height))
    canvas.paste(im, ((box_w - im.width) // 2, (box_h - im.height) // 2))
    return canvas


def _wrap(d: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    """逐字换行（中文无空格分词，逐字测宽最稳）。"""
    lines, line = [], ""
    for ch in text:
        if d.textbbox((0, 0), line + ch, font=fnt)[2] <= max_w:
            line += ch
        else:
            if line:
                lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# 人物最高点/脚线检测（统一刻度的地基）
# ---------------------------------------------------------------------------
def detect_figure_span(im: Image.Image, x0: int, x1: int,
                       ref: tuple[int, int, int] | None = (233, 231, 226),
                       thr: int = 36) -> tuple[int, int]:
    """在 x0..x1 列范围内检测人物的最低点(脚线)与最高点(头顶)。

    ref=None 时自动从四角采样背景色（各源图背景色不一致时必须用，
    否则头顶/脚线会漂移，导致刻度线整体错位）。
    """
    if ref is None:
        import numpy as np
        a = np.asarray(im.convert("RGB")).astype(int)
        corners = np.concatenate([
            a[:40, :40].reshape(-1, 3), a[:40, -40:].reshape(-1, 3),
            a[-40:, :40].reshape(-1, 3), a[-40:, -40:].reshape(-1, 3),
        ])
        ref = tuple(int(v) for v in np.median(corners, axis=0))
    px = im.load()
    lows, highs = [], []
    for x in range(x0, x1, 4):
        low = high = None
        for y in range(im.height - 1, 20, -1):
            r, g, b = px[x, y][:3]
            if (r - ref[0]) ** 2 + (g - ref[1]) ** 2 + (b - ref[2]) ** 2 > thr * thr:
                low = y
                break
        for y in range(20, im.height):
            r, g, b = px[x, y][:3]
            if (r - ref[0]) ** 2 + (g - ref[1]) ** 2 + (b - ref[2]) ** 2 > thr * thr:
                high = y
                break
        if low and high:
            lows.append(low)
            highs.append(high)
    lows.sort()
    highs.sort()
    base = lows[int(len(lows) * 0.85)] if lows else im.height - 30
    top = highs[int(len(highs) * 0.15)] if highs else 40
    return base, top


def _draw_scale_lines(im: Image.Image, base: int, top: int, cm_height: int) -> Image.Image:
    """在图上绘制统一刻度：10cm 细线、50cm 粗线 + 数字、身高虚线。"""
    ppm = (base - top) / cm_height
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for cm in range(0, int(cm_height * 1.04) + 1, 10):
        y = base - round(cm * ppm)
        if y < 8:
            break
        if cm % 50 == 0:
            d.line([(0, y), (im.width, y)], fill=(70, 110, 150, 190), width=2)
        else:
            d.line([(0, y), (im.width, y)], fill=(90, 130, 160, 90), width=1)
    yh = base - round(cm_height * ppm)
    for x in range(0, im.width, 36):  # 身高虚线
        d.line([(x, yh), (min(x + 20, im.width), yh)], fill=(176, 83, 63, 230), width=2)
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    for cm in range(50, cm_height + 1, 50):
        y = base - round(cm * ppm)
        if y > 4:
            d.text((10, y - 30), f"{cm}", fill=(70, 110, 150), font=font(28, True))
    d.text((10, yh - 30), f"{cm_height}", fill=(176, 83, 63), font=font(28, True))
    return im


def build_turn_with_scale(src: Path, cm_height: int, x0: int = 50, x1: int = 345,
                          wm: str = "corner", patch_x: float = 0.58,
                          patch_span: tuple[float, float] = (0.315, 0.4167)) -> Image.Image:
    """统一刻度三视图：自动检测正面人物脚线/头顶 → 1cm=PPM 像素。

    wm: "corner" = 角部底色填充（仅平整背景）；
        "copy"   = 左侧同高度干净块贴盖；
        "stretch"= 取人物间地面空隙（patch_span 比例区间）水平拉伸贴盖
                   （地面有阴影渐变时用，否则 patch 会出现色块）。
    x0/x1: 正面视图所在的横向像素区间（用于脚线检测）。
    """
    src_im = Image.open(src).convert("RGB")
    W_, H_ = src_im.size
    if wm == "stretch":
        im = src_im.copy()
        x0w, y0w = int(W_ * 0.845), int(H_ * 0.935)
        bw, bh = W_ - x0w, H_ - y0w
        sx0, sx1 = int(W_ * patch_span[0]), int(W_ * patch_span[1])
        patch = src_im.crop((sx0, y0w, sx1, y0w + bh)).resize((bw, bh), Image.LANCZOS)
        im.paste(patch, (x0w, y0w))
    elif wm == "copy":
        im = patch_wm(src_im, src_x0=patch_x)
    else:
        im = fill_wm(src_im)
    base, top = detect_figure_span(im, x0, x1, ref=None)
    return _draw_scale_lines(im, base, top, cm_height)


# ---------------------------------------------------------------------------
# 网格逐格名牌（微表情 / 服饰 / 装备六格通用）
# ---------------------------------------------------------------------------
def caption_grid(src: Path, names: list[str], fsize: int = 40, band_h: int = 58,
                 grid: tuple[int, int] = (3, 2)) -> Image.Image:
    """网格逐格底部名牌（默认 3×2，可 2×3）；名牌同时盖住右下水印。

    ⚠️ 源图必须与 grid 匹配：3 列 ×2 行请出横版 1536×1024；
    方图会导致名牌与格子错位。
    """
    im = Image.open(src).convert("RGB")
    cols, rows = grid
    cw, ch = im.width // cols, im.height // rows
    d = ImageDraw.Draw(im, "RGBA")
    f_ = font(fsize)
    for idx, name in enumerate(names):
        r, c = divmod(idx, cols)
        x0, y0 = c * cw, r * ch
        d.rectangle([x0, y0 + ch - band_h, x0 + cw - 2, y0 + ch - 2], fill=BAND + (235,))
        tb = d.textbbox((0, 0), name, font=f_)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        d.text(
            (x0 + (cw - tw) // 2 - tb[0], y0 + ch - band_h + (band_h - th) // 2 - tb[1]),
            name, fill=CREAM, font=f_,
        )
    return im


def section_label(text: str, width: int, height: int = 52) -> Image.Image:
    bar = Image.new("RGB", (width, height), BAND)
    d = ImageDraw.Draw(bar)
    d.text((16, 9), text, fill=CREAM, font=font(30, True))
    return bar


def chip_row(d: ImageDraw.ImageDraw, x: int, y: int, labels: list[str], fnt) -> int:
    """性格 chips，返回行底部 y。"""
    for t in labels:
        tb = d.textbbox((0, 0), t, font=fnt)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        d.rounded_rectangle([x, y, x + tw + 28, y + th + 18], radius=8,
                            outline=ACCENT, width=2, fill=(235, 242, 243))
        d.text((x + 14, y + 9 - tb[1]), t, fill=ACCENT, font=fnt)
        x += tw + 44
    return y + 60


# ---------------------------------------------------------------------------
# 用户配置（characters.py）加载
# ---------------------------------------------------------------------------
def load_characters(config_path: str | Path, card_key: str) -> dict:
    """从用户配置文件加载角色 dict，并把相对路径解析到 BASE_DIR 下。

    配置文件须定义：CHARS = {角色名: {...}}，可选 BASE_DIR（默认 = 配置文件所在目录）。
    card_key: "CHARS" / "Q_CHARS" 等，方便扩展。
    """
    import importlib.util
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(
            f"找不到配置文件 {config_path}。请参考 characters.example.py "
            f"复制一份 characters.py 并填入你的角色配置。"
        )
    spec = importlib.util.spec_from_file_location("user_characters", config_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    base = Path(getattr(mod, "BASE_DIR", config_path.parent)).resolve()
    chars: dict = getattr(mod, card_key, None)
    if chars is None:
        raise KeyError(f"配置文件 {config_path} 中未定义 {card_key}")
    for name, cfg in chars.items():
        if isinstance(cfg.get("parts"), str):
            cfg["parts"] = base / cfg["parts"]
        if isinstance(cfg.get("out"), str):
            cfg["out"] = base / cfg["out"]
    return chars
