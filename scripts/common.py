import sys
from typing import Tuple, List, Dict, Set
from toolz.curried import curry, pipe, map, filter, groupby, valmap
from toolz.curried import itemmap, valfilter
from pypinyin import lazy_pinyin
from tables import FullToTwoTable
from tables import CharPhoneTable, CharHeShapeTable, WordPhoneTable, EngWordTable, CharLuShapeTable
from tables import DelWordTable


@curry
def for_each(proc, eles):
    if type(eles) is dict:
        for (k, v) in eles.items():
            proc(k, v)
    else:
        for e in eles:
            proc(e)


for_each = curry(for_each)


def split_sy(pinyin: str) -> Tuple[str, str]:
    if pinyin == "sh":
        s = "sh"
        y = "i"
    elif pinyin.startswith("zh"):
        s = "zh"
        y = pinyin[2:]
    elif pinyin.startswith("ch"):
        s = "ch"
        y = pinyin[2:]
    elif pinyin.startswith("sh"):
        s = "sh"
        y = pinyin[2:]
    elif pinyin == "er":
        s = "e"
        y = "r"
    elif pinyin == "e":
        s = "e"
        y = "e"
    elif pinyin == "a":
        s = "a"
        y = "a"
    elif pinyin == "n":
        s = "e"
        y = "n"
    elif pinyin == "o":
        s = "o"
        y = "o"
    elif pinyin == "ang":
        s = "a"
        y = "ang"
    else:
        s = pinyin[0]
        y = pinyin[1:]
    return (s, y)


def get_full(word: str) -> List[str]:
    fulls = []
    for full in lazy_pinyin(word):
        for e in full:
            if e not in "abcdefghijklmnopqrstuvwxyz":
                raise RuntimeError(f"{e} not alphe, word is: {word}")
        fulls.append(full)
    return fulls


def get_full_to_xhe_transformer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
            map(lambda e: (e.full, e.xhe)),
            groupby(lambda e: e[0]),
            itemmap(lambda kv: (kv[0], list(
                map(lambda e: e[1], kv[1]))[0])),
            dict
            )


def get_full_to_zrm_transformmer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
                map(lambda e: (e.full, e.zrm)),
                groupby(lambda e: e[0]),
                itemmap(lambda kv: (kv[0], list(
                    map(lambda e: e[1], kv[1]))[0])),
                dict
                )


def get_full_to_lu_transformmer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
                map(lambda e: (e.full, e.lu)),
                groupby(lambda e: e[0]),
                itemmap(lambda kv: (kv[0], list(
                    map(lambda e: e[1], kv[1]))[0])),
                dict
                )


def get_xhe_to_full_transformer() -> Dict[str, List[str]]:
    return pipe(FullToTwoTable.select(),
                map(lambda e: (e.full, e.two)),
                groupby(lambda e: e[1]),
                itemmap(lambda kv: (kv[0], list(
                    filter(lambda e: e != kv[0], map(lambda e: e[0], kv[1]))))),
                itemmap(lambda kv: (kv[0], kv[1]
                                    if len(kv[1]) > 0 else [kv[0]])),
                valfilter(lambda e: len(e) == 1),
                dict
                )


def full_to_two(pinyin: str, transformer: Dict[str, str]) -> str:
    sy = split_sy(pinyin)
    if len(sy) != 2:
        raise RuntimeError(f"{sy} length != 2")
    if sy[0] not in transformer or sy[1] not in transformer:
        raise RuntimeError(f"{sy} not in transformer")
    return f"{transformer[sy[0]]}{transformer[sy[1]]}"


def word_to_two(word: str, transformer: Dict[str, str]) -> str:
    return ''.join([full_to_two(e, transformer) for e in get_full(word)])


def get_char_to_xhe_shapes() -> Dict[str, List[str]]:
    char_to_shape = pipe(CharHeShapeTable.select(),
                     map(lambda e: (e.char, e.shapes)),
                     filter(lambda e: e[0] != '' and e[1] != ''),
                     groupby(lambda e: e[0]),
                     valmap(lambda e: [s[1] for s in e]),
                     dict
                     )
    return char_to_shape


def get_char_to_lu_shapes() -> Dict[str, List[str]]:
    char_to_shape = pipe(CharLuShapeTable.select(),
                     map(lambda e: (e.char, e.shapes)),
                     filter(lambda e: e[0] != '' and e[1] != ''),
                     groupby(lambda e: e[0]),
                     valmap(lambda e: [s[1] for s in e]),
                     dict
                     )
    return char_to_shape


def get_char_to_xhe_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.xhe)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]),
                          dict
                          )
    return char_to_phones


def get_char_to_zrm_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.zrm)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]),
                          dict
                          )
    return char_to_phones


def get_del_words() -> Set[str]:
    del_words = pipe(
        DelWordTable.select(),
        map(lambda e: e.word),
        filter(lambda e: e != ''),
        set
    )
    return del_words


def generate_one_hit_char(priority):
    items = {
        "去\tq": priority, "我\tw": priority, "二\te": priority, "人\tr": priority, "他\tt": priority, "一\ty": priority, "是\tu": priority, "出\ti": priority, "哦\to": priority, "平\tp": priority,
        "啊\ta": priority, "三\ts": priority, "的\td": priority, "非\tf": priority, "个\tg": priority, "和\th": priority, "就\tj": priority, "可\tk": priority, "了\tl": priority,
        "在\tz": priority, "小\tx": priority, "才\tc": priority, "这\tv": priority, "不\tb": priority, "你\tn": priority, "没\tm": priority,
    }
    return items


def generate_topest_char(char_to_phones, prioroty):
    chars = """去 我 二 人 他  一 是 出 哦 平 啊 三 的 非 个 和 就 可 了 在 小 才 这 不 你 没 阿 爱 安 昂 奥 把 白 办 帮 报 被 本 蹦 比 边 表 别 滨 并 拨 部 擦 菜 参 藏 藏 草 测 岑 曾 拆 产 超 车 陈 成 吃 冲 抽 处 揣 传 窗 吹 纯 戳 次 差 从 凑 粗 窜 催 村 错 大 代 但 当 到 得 得 等 地 点 跌 定 丢 动 都 读 段 对 顿 多 额 欸 恩 嗯 而 法 反 放 费 分 风 佛 否 副 嘎 该 干 刚 高 各 给 跟 更 共 够 古 挂 怪 关 光 贵 滚 过 哈 还 含 行 好 何 黑 很 横 红 后 户 话 坏 换 黄 会 混 或 几 加 间 将 叫 接 进 经 久 据 卷 均 卡 开 看 抗 靠 克 剋 肯 坑 空 口 酷 夸 快 宽 况 亏 困 扩 拉 来 浪 老 月 乐 类 冷 里 连 两 料 列 林 另 刘 龙 楼 路 乱 论 落 率 吗 买 慢 忙 毛 么 每 们 梦 米 面 秒 灭 民 名 末 某 目 那 难 囊 闹 呢 内 嫩 能 泥 年 鸟 捏 您 宁 牛 弄 怒 暖 虐 挪 女 欧 怕 排 盘 旁 跑 配 盆 碰 批 片 票 撇 品 凭 破 剖 普 其 恰 前 强 桥 且 请 亲 穷 求 区 全 却 群 然 让 绕 热 任 仍 日 容 肉 如 软 若 撒 赛 散 扫 色 森 僧 啥 晒 山 上 少 设 深 生 时 受 帅 拴 双 水 顺 四 送 搜 苏 算 岁 所 她 太 谈 汤 套 特 疼 体 天 调 贴 听 同 头 图 团 推 托 挖 外 完 王 为 问 翁 喔 握 无 系 下 先 想 笑 些 新 熊 修 需 选 学 亚 眼 样 要 也 以 因 应 哟 用 有 与 元 云 咋 再 早 则 贼 怎 增 扎 占 长 长 找 着 真 正 只 中 周 主 抓 拽 转 装 追 桌 字 总 走 组 最 做"""

    exists_chars = set()
    items = {}
    for char in filter(lambda e: e != "", chars.strip().split(" ")):
        if char in exists_chars:
            continue
        if char not in char_to_phones:
            print(f"A: {char} has no phones.")
            continue
        for phone in char_to_phones[char]:
            items[f"{char}\t{phone}"] = prioroty

        exists_chars.add(char)
    return items


def is_all_alpha(s: str)->bool:
    for e in s:
        if e.lower() in "abcdefghijklmnopqrstuvwxyz":
            continue
        else:
            return False
    return True


def get_dd_cmds():
    cmds = [
            '$ddcmd(<date.yyyy>年<date.m>月<date.d>日,[2011年1月1日])\torq',
            '$ddcmd(<date.z> <time.hh>时<time.mm>分,[星期五 08时05分])\touj',
            '$ddcmd(run(calc.exe),[计算器])\tojsq',
            '$ddcmd(<last.1>,★)\tz',
            '$ddcmd(run(%apppath%\\),[安装目录])\toav',
            '$ddcmd(<date.yyyy>年<date.m>月<date.d>日,<date.yyyy>年<date.m>月<date.d>日)\torq',
            '$ddcmd(<date.YYYY>年<date.M>月<date.D>日,<date.YYYY>年<date.M>月<date.D>日)\torq',
            '$ddcmd(<date.yyyy>-<date.mm>-<date.dd>,<date.yyyy>-<date.mm>-<date.dd>)\torq',
            '$ddcmd(<date.z> <time.h>:<time.mm>,<date.z> <time.h>:<time.mm>)\touj',
            '$ddcmd(run(https://www.baidu.com/s?wd=<last.0>),[百度]：<last.0>)\toss',
            '$ddcmd(run(https://www.zdic.net/hans/?q=<last.1>),[汉典]：<last.1>)\tohd',
            '$ddcmd(run(http://www.xhup.club/?search_word=<last.1>),[小鹤查形]：<last.1>)\tohd',
            '$ddcmd(run(cmd.exe),[命令提示行])\tocm',
            '$ddcmd(run(::{20D04FE0-3AEA-1069-A2D8-08002B30309D}),[我的电脑])\todn',
            '$ddcmd(run(control.exe),[控制面板])\tokv',
            '$ddcmd(run(::{450D8FBA-AD25-11D0-98A8-0800361B1103}),[我的文档])\towd',
            '$ddcmd(run(winword.exe),[word])\towd',
            '$ddcmd(run(excel.exe),[excel])\toec',
            '$ddcmd(run(mspaint.exe),[画图])\toht',
            '$ddcmd(run(notepad.exe),[记事本])\toju',
            '$ddcmd(keyboard(<32+Alt><78>),[最小化])\tozx',
            '$ddcmd(keyboard(<83+Shift+Win>),[截屏])\tojp',
            '$ddcmd(keyboard(<68+Win>),[桌面])\tovm',
            '$ddcmd(help(keyboardmap.html,600,500),[键盘图])\tojp',
            '$ddcmd(config(/do anjianshezhi),[按键定义])\toaj',
            '$ddcmd(config(/do 常用),[常用项])\toiy',
            '$ddcmd(config(/do 界面),[界面项])\tojm',
            '$ddcmd(config(/do 码表),[码表项])\tomb',
            '$ddcmd(config(/do 高级),[高级项])\togj',
            '$ddcmd(config(/do gaojishezhi),[高级设置])\togj',
            '$ddcmd(config(/do about),[关于项])\togy',
            '$ddcmd(set([-IME设置-],嵌入文本内容=嵌入编码),[嵌入编码])\toiq',
            '$ddcmd(set([-IME设置-],嵌入文本内容=嵌入首选),[嵌入首选])\toiq',
            '$ddcmd(set([-IME设置-],嵌入文本内容=传统样式),[传统样式])\toiq',
            '$ddcmd(set([-IME设置-],隐藏候选窗口=切换),[显隐候选窗])\toic',
            '$ddcmd(set([-SKIN设置-],候选列表排列样式=横排),[横排窗口])\toih',
            '$ddcmd(set([-SKIN设置-],候选列表排列样式=竖排),[竖排窗口])\toih',
            '$ddcmd(set([-DME设置-],查询输入只查单字=切换),[万能键查字词切换])\toiz',
            '$ddcmd(config(/do 输出反查),[反查]：<last.1>)\tofi',
            '$ddcmd(config(/do 剪贴板反查),[剪贴板反查])\tofi',
            '$ddcmd(config(/do 在线加词),[在线加词])\tojc',
            '$ddcmd(convert(中英文标点,切换),[中英文标点切换])\tovy',
            '$ddcmd(convert(全半角,切换),[全半角切换])\toqb',
            '$ddcmd(convert(繁体输出,切换),[简繁切换])\tojf',
            '$ddcmd(keyboard(<35><36+Shift><46>),[删当前行])\toui',
            '$ddcmd(keyboard(<35><36+Shift><46>),[删当前行])\toiu',
            '$ddcmd(config(/dict <last.1>),[字典]：<last.1>)\tozd',
            '$ddcmd(set([-IME设置-],禁用鼠标悬停词典=切换),[候选窗字典开关])\tozd',
            '$ddcmd(set([-IME设置-],检索次显码表=是),[启用单字全码])\toqm',
            '$ddcmd(set([-IME设置-],检索次显码表=否),[关闭])\toqm',
            '$ddcmd(set([-IME设置-],输入方案=主+辅),[启用词语辅助])\tocf',
            '$ddcmd(set([-IME设置-],输入方案=主),[关闭])\tocf',
            '$ddcmd(set([-SKIN设置-],使用皮肤名称=切换),[换肤])\tohf',
            '$ddcmd(set([-SKIN设置-],使用皮肤名称=fw.col),[默认])\tohf',
            '$ddcmd(keyboard(<173>),[静音开关])\tojy',
            '$ddcmd(run(https://flypy.com),[小鹤官网])\txhgw',
            '$ddcmd(run(https://bbs.flypy.com),[小鹤论坛])\txhlt',
            '$ddcmd(run(http://flypy.ys168.com),[小鹤网盘])\txhwp',

        ]
    return cmds


