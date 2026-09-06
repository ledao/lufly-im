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


# 显式把 X 输入焦点钉到「本次新开的」窗口。快照差分法: spawn 前记录全部
# 终端窗口 id，spawn 后取新增者——按类名/栈顶找都可能命中旧终端（本会话
# 终端的 IC 残存 rime 态，打字全进旧 IC，截图看到的是 rime 的 ~码注候选）。
def terminal_windows():
    # 每次用全新连接: 之前的 X 协议错误会毒化旧连接，query_tree 之后
    # 静默返回空——拿不到窗口列表还自以为成功了
    dx = display.Display()
    out = set()
    for w in dx.screen().root.query_tree().children:
        try:
            cls = w.get_wm_class()
        except Exception:
            continue
        if cls and any("gnome-terminal" in part.lower() for part in cls):
            out.add(w.id)
    return out


BEFORE = terminal_windows()
p = subprocess.Popen(["gnome-terminal", "--", "bash", "-c", "sleep 25"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.8)


def activate_window(wid):
    # X SetInputFocus 騗不过 Mutter（WM 焦点另有一套），必须走 EWMH
    # _NET_ACTIVE_WINDOW 客户端消息，让 WM 自己把窗口提到前台并给焦点。
    from Xlib import protocol
    root = d.screen().root
    w = d.create_resource_object("window", wid)
    ev = protocol.event.ClientMessage(
        window=w, client_type=d.intern_atom("_NET_ACTIVE_WINDOW"),
        data=(32, [1, 0, 0, 0, 0]))
    root.send_event(ev, event_mask=(X.SubstructureRedirectMask
                                    | X.SubstructureNotifyMask))
    d.sync()


def focus_xed():
    fresh = terminal_windows() - BEFORE
    target = fresh.pop() if fresh else None
    if target is None:
        return False
    activate_window(target)
    return True

for _ in range(10):
    if focus_xed():
        break
    time.sleep(0.3)

# ShareInputState=No 时每个新窗口 IC 默认用分组 DefaultIM；
# 必须对着焦点 IC 反复切到 lufly 直到生效。
# 顺序坑: 新窗口焦点进来晚于 -s 循环时，-n 读到的是旧 IC 的 lufly、循环
# 空转，随后新 IC 以自己的 rime 激活——打字全进 rime。所以聚焦后必须
# 再切一轮并最终验证。
def activate_lufly():
    ok = False
    for _ in range(5):
        subprocess.run(["fcitx5-remote", "-s", "lufly"], capture_output=True)
        time.sleep(0.15)
        if subprocess.run(["fcitx5-remote", "-n"], capture_output=True,
                          text=True).stdout.strip() == "lufly":
            ok = True
            break
    return ok


for _ in range(10):
    if focus_xed():
        break
    time.sleep(0.3)

activate_lufly()
time.sleep(0.3)
# 新 IC 焦点此时才真正进来: 重聚焦 + 重切 + 验证
focus_xed()
time.sleep(0.3)
if not activate_lufly():
    print("FAILED: 无法把焦点 IC 切到 lufly")
    sys.exit(1)
time.sleep(0.2)

best = None
for attempt in range(3):
    # 激活必须用 -o: fcitx5 默认 EnumerateWithTriggerKeys，Ctrl+Space 在
    # 枚举开关打开时不是「激活」而是「切到下一个 IM」（lufly→下一个），
    # 曾让截图脚本整场拿到别的输入法的候选窗
    subprocess.run(["fcitx5-remote", "-o"], capture_output=True)
    time.sleep(0.2)
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
    subprocess.run(["fcitx5-remote", "-c"], capture_output=True)

p.terminate()
if best:
    withwin, (l, t, r, b) = best
    withwin.crop((l - 15, t - 15, r + 15, b + 15)).resize(
        ((r - l + 30) * 2, (b - t + 30) * 2), Image.LANCZOS).save(OUT)
    print("saved", OUT, (l, t, r, b))
else:
    print("FAILED: 候选窗未出现")
    sys.exit(1)
