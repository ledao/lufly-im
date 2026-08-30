#!/usr/bin/env python3
"""生成候选窗 9-patch 贴图（panel.png / highlight.png，亮暗两套）。

设计: 白色圆角卡片 + 发丝线描边 + 柔和投影（macOS 卡片风）；
高亮为浅蓝药丸。全部 4x 超采样后 LANCZOS 缩小，保证边缘与投影平滑。

用法: /usr/bin/python3 gen_theme.py   （在 ime/fcitx5 目录下运行）
"""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "theme")
SS = 4  # 超采样倍数

# ---------- panel.png: 圆角卡片 + 投影 ----------
PANEL = 96          # 1x 画布
PANEL_MARGIN = 24   # 9-patch 边距（= 影环16 + 圆角4 + 余量4）
RING = 16           # 卡片外围透明影环宽度（须等于 ShadowMargin）
RADIUS = 4          # 小圆角: 锐利、速度感

# ---------- highlight.png: 首选底纹药丸 ----------
PILL = 48
PILL_MARGIN = 8     # 须与 theme.conf 的 Highlight/Margin 一致
PILL_RADIUS = 3     # 与卡片同级的锐利小圆角

# ---------- 配色 ----------
# 首选 = 轻轻的灰色底纹 + 深色文字（与后面候选仅一层底纹之差）
LIGHT = dict(fill="#ffffff", border="#d9dee7",
             shadow_alpha=64, shadow_blur=11, shadow_dy=3,
             pill="#eef0f3")
DARK = dict(fill="#24272e", border="#3d434e",
            shadow_alpha=96, shadow_blur=13, shadow_dy=3,
            pill="#31353c")


def rounded(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def make_panel(path, spec):
    size = PANEL * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # 投影层: 圆角矩形下移 dy → 高斯模糊
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    box = (RING * SS, RING * SS + spec["shadow_dy"] * SS,
           (PANEL - RING) * SS, (PANEL - RING) * SS + spec["shadow_dy"] * SS)
    rounded(sd, box, RADIUS * SS, fill=(8, 12, 24, spec["shadow_alpha"]))
    shadow = shadow.filter(ImageFilter.GaussianBlur(spec["shadow_blur"] * SS / 2))
    img.alpha_composite(shadow)

    # 卡片层: 填充 + 发丝线描边
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    box = (RING * SS, RING * SS, (PANEL - RING) * SS, (PANEL - RING) * SS)
    rounded(cd, box, RADIUS * SS, fill=spec["fill"])
    rounded(cd, box, RADIUS * SS, outline=spec["border"], width=1 * SS)
    img.alpha_composite(card)

    img = img.resize((PANEL, PANEL), Image.LANCZOS)
    img.save(path)
    print("ok", path)


def make_pill(path, spec):
    size = PILL * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = PILL_MARGIN * SS
    rounded(d, (m, m, size - m, size - m), PILL_RADIUS * SS, fill=spec["pill"])
    img = img.resize((PILL, PILL), Image.LANCZOS)
    img.save(path)
    print("ok", path)


for name, spec in (("lufly", LIGHT), ("lufly-dark", DARK)):
    d = os.path.join(ROOT, name)
    os.makedirs(d, exist_ok=True)
    make_panel(os.path.join(d, "panel.png"), spec)
    make_pill(os.path.join(d, "highlight.png"), spec)
