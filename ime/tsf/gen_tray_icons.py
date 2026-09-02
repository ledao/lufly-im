#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成任务栏三个托盘图标：lufly-zh.ico / lufly-en.ico / lufly.ico。

统一风格：透明底 + 白圆角块 + 纯黑字形（黑字白底；灰被否：看着像禁用态）。
- 中/EN：白块轮廓取自天鹅源图（三图标圆角形状一致），纯黑微软雅黑粗体
- 天鹅：取 fcitx5/data/lufly.png 原图配色——黑天鹅 + 白色圆角底块，
  只裁掉底块外空白，不剥底块不改色

高分辨率出图后 LANCZOS 缩到各目标尺寸，多尺寸层保证高 DPI 清晰。
用法: python gen_tray_icons.py   （任意目录；路径按仓库布局解析）
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SWAN_SRC = HERE.parent / "fcitx5" / "data" / "lufly.png"
FONT = Path(r"C:\Windows\Fonts\msyhbd.ttc")  # 微软雅黑 Bold

BLACK = (0, 0, 0, 255)  # 纯黑字形（128 灰被否：看着像禁用态）
HI = 512  # 中/EN 的高分辨率画布
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (48, 48)]
# 白块占画布比例：中/EN 同一块同大小，天鹅（块里已有黑天鹅）略收
FILL = {"zh": 0.94, "en": 0.94, "swan": 0.92}
INNER = 0.78  # 字形占白块边长的比例，留白呼吸


def white_block(side: int) -> Image.Image:
    """白色圆角块：轮廓取天鹅源图的 alpha（三图标圆角形状一致）。"""
    src = Image.open(SWAN_SRC).convert("RGBA")
    alpha = src.split()[3]
    bbox = alpha.getbbox()
    block = Image.new("RGBA", (bbox[2] - bbox[0], bbox[3] - bbox[1]),
                      (255, 255, 255, 255))
    block.putalpha(alpha.crop(bbox))
    bw, bh = block.size
    k = side / max(bw, bh)
    return block.resize((max(1, round(bw * k)), max(1, round(bh * k))),
                        Image.LANCZOS)


def render_text(text: str, fill: float) -> Image.Image:
    """黑字白底：白圆角块 + 纯黑微软雅黑粗体字形，共同居中。"""
    # 黑字形：高分辨率渲染后按实际包围盒裁紧
    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    d = ImageDraw.Draw(probe)
    size = HI // 2
    while True:
        font = ImageFont.truetype(str(FONT), size)
        tb = d.textbbox((0, 0), text, font=font)
        if tb[2] - tb[0] >= HI * 2 or size > HI * 4:
            break
        size *= 2

    gw, gh = tb[2] - tb[0], tb[3] - tb[1]
    margin = size // 2
    pad = Image.new("RGBA", (gw + 2 * margin, gh + 2 * margin), (0, 0, 0, 0))
    d = ImageDraw.Draw(pad)
    origin = (margin - tb[0], margin - tb[1])
    d.text(origin, text, font=font, fill=BLACK)
    glyph = pad.crop(d.textbbox(origin, text, font=font))

    # 布局：白块占画布 fill，字形缩进块内占 INNER，对中叠放
    block = white_block(int(HI * fill))
    inner = int(HI * fill * INNER)
    k = min(inner / glyph.width, inner / glyph.height)
    glyph = glyph.resize((max(1, round(glyph.width * k)),
                          max(1, round(glyph.height * k))), Image.LANCZOS)

    out = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    out.paste(block, ((HI - block.width) // 2, (HI - block.height) // 2), block)
    out.paste(glyph, ((HI - glyph.width) // 2, (HI - glyph.height) // 2), glyph)
    return out


def render_swan() -> Image.Image:
    """fcitx5 源图原样配色：黑天鹅 + 白色圆角底块，只裁掉底块外空白。"""
    src = Image.open(SWAN_SRC).convert("RGBA")
    return fit_center(src.crop(src.split()[3].getbbox()), HI, FILL["swan"])


def fit_center(glyph: Image.Image, canvas: int, fill: float) -> Image.Image:
    """等比缩放到目标填充率，居中贴到 canvas×canvas 透明画布。"""
    target = int(canvas * fill)
    w, h = glyph.size
    if w >= h:
        nw, nh = target, max(1, round(target * h / w))
    else:
        nh, nw = target, max(1, round(target * w / h))
    glyph = glyph.resize((nw, nh), Image.LANCZOS)

    # 保留字形自身颜色（黑 中/EN、黑白 天鹅），不再统一染色
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.paste(glyph, ((canvas - nw) // 2, (canvas - nh) // 2), glyph)
    return out


def ascii_preview(img: Image.Image, cols: int = 32) -> None:
    """按明暗预览：# 黑字形 + 白块 . 透明。"""
    rows = cols // 2
    small = img.resize((cols, rows), Image.LANCZOS)
    px = small.load()
    for y in range(rows):
        line = []
        for x in range(cols):
            r, g, b, a = px[x, y]
            if a < 40:
                line.append(".")
            elif (r + g + b) / 3 < 128:
                line.append("#")
            else:
                line.append("+")
        print("".join(line))


for name, img in (("zh", render_text("中", FILL["zh"])),
                  ("en", render_text("EN", FILL["en"])),
                  ("swan", render_swan())):
    out = HERE / {"swan": "lufly.ico"}.get(name, f"lufly-{name}.ico")
    img.save(out, format="ICO", sizes=SIZES)
    print(f"== {out.name} ==")
    ascii_preview(img)
print("done")
