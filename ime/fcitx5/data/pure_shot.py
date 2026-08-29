#!/usr/bin/env python3
# 候选窗纯净截图: 自动激活 lufly → 键入 → 差分提取窗体
# 用法: /usr/bin/python3 pure_shot.py <输出.png> [键入串]
import subprocess, sys, time
from PIL import ImageGrab, ImageChops, Image
from Xlib import display, X, XK
from Xlib.ext import xtest

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pure.png"
TEXT = sys.argv[2] if len(sys.argv) > 2 else "nihc"

d = display.Display()


def key(sym):
    ks = XK.string_to_keysym(sym)
    kc = d.keysym_to_keycode(ks)
    xtest.fake_input(d, X.KeyPress, kc)
    d.sync()
    time.sleep(0.012)
    xtest.fake_input(d, X.KeyRelease, kc)
    d.sync()
    time.sleep(0.03)


def ctrl_space():
    ks = XK.string_to_keysym("Control_L")
    kc = d.keysym_to_keycode(ks)
    xtest.fake_input(d, X.KeyPress, kc)
    d.sync()
    ks = XK.string_to_keysym("space")
    kc2 = d.keysym_to_keycode(ks)
    xtest.fake_input(d, X.KeyPress, kc2)
    d.sync()
    time.sleep(0.03)
    xtest.fake_input(d, X.KeyRelease, kc2)
    d.sync()
    xtest.fake_input(d, X.KeyRelease, kc)
    d.sync()
    time.sleep(0.15)


p = subprocess.Popen(["xed", "/tmp/lufly-shot.txt"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.8)
subprocess.run(["fcitx5-remote", "-s", "lufly"], capture_output=True)
time.sleep(0.2)

best = None
for attempt in range(3):
    if subprocess.run(["fcitx5-remote"], capture_output=True,
                      text=True).stdout.strip() != "2":
        ctrl_space()
    for ch in TEXT:
        key(ch)
    time.sleep(0.4)
    withwin = ImageGrab.grab()
    key("Escape")
    key("Escape")
    time.sleep(0.4)
    without = ImageGrab.grab()
    diff = ImageChops.difference(withwin.convert("RGB"), without.convert("RGB"))
    bb = diff.getbbox()
    if bb and (bb[2] - bb[0]) > 100 and (bb[3] - bb[1]) > 30:
        best = (withwin, bb)
        break
    # 清掉已上屏的字母, 重试
    for _ in TEXT:
        key("BackSpace")
    ctrl_space()

p.terminate()
if best:
    withwin, (l, t, r, b) = best
    withwin.crop((l - 15, t - 15, r + 15, b + 15)).resize(
        ((r - l + 30) * 2, (b - t + 30) * 2), Image.LANCZOS).save(OUT)
    print("saved", OUT, (l, t, r, b))
else:
    print("FAILED: 候选窗未出现")
    sys.exit(1)
