#!/usr/bin/env python3
# 候选窗纯净截图: 自动激活 lufly → 键入 → 差分提取窗体
# 用法: /usr/bin/python3 pure_shot.py <输出.png> [键入串]
import subprocess, sys, time
from PIL import ImageGrab, ImageChops, Image
from Xlib import display, X, XK
from Xlib.ext import xtest

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pure.png"
TEXT = sys.argv[2] if len(sys.argv) > 2 else "nihc"

# xed 单实例: 同名文件只会聚焦旧窗口（其 IC 可能还挂在别的输入法上）。
# 每次用唯一文件名 + 清掉残留，保证开的是全新窗口/全新 IC。
import os
subprocess.run(["pkill", "-f", "lufly-shot"], capture_output=True)
time.sleep(0.3)
SHOT = f"/tmp/lufly-shot-{os.getpid()}.txt"
open(SHOT, "w").close()

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


p = subprocess.Popen(["gnome-terminal", "--", "bash", "-c", "sleep 25"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.8)

# 显式把 X 输入焦点钉到新窗口（新窗口不一定自动拿焦点，
# fcitx5-remote -s 只作用于焦点 IC，焦点错了全部白搭）
# 注意: IC 的 InputState 按程序作用域继承，xed 的作用域已被旧测试污染
def focus_xed():
    root = d.screen().root
    for w in root.query_tree().children:
        try:
            cls = w.get_wm_class()
        except Exception:
            continue
        if cls and any("gnome-terminal" in part.lower() for part in cls):
            w.configure(stack_mode=X.Above)
            w.set_input_focus(X.RevertToParent, X.CurrentTime)
            d.sync()
            return True
    return False

for _ in range(10):
    if focus_xed():
        break
    time.sleep(0.3)

# ShareInputState=No 时每个新窗口 IC 默认用分组 DefaultIM；
# 必须对着焦点 IC 反复切到 lufly 直到生效
for _ in range(5):
    subprocess.run(["fcitx5-remote", "-s", "lufly"], capture_output=True)
    time.sleep(0.15)
    cur = subprocess.run(["fcitx5-remote", "-n"], capture_output=True,
                         text=True).stdout.strip()
    if cur == "lufly":
        break
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
