from dataclasses import dataclass
from typing import List, Dict, Tuple
from tqdm import trange

from peewee import fn

import check_lu_shuangpin
import check_xhe_shuangpin
import check_bingji_shuangpin
import check_zrm_shuangpin
from common import ShuangPinSchema, XHE_SP_SCHEMA, get_char_to_xhe_phones, LU_SP_SCHEMA, get_char_to_lu_phones, \
    ZRM_SP_SCHEMA, get_char_to_zrm_phones, BINGJI_SP_SCHEMA, get_char_to_bingji_phones, get_char_to_xhe_shapes, \
    is_all_alpha, SchemaConfig, get_exists_words
from tables import CharPhoneTable, WordPhoneTable, EngWordTable, SimplerTable, TangshiTable


@dataclass
class EncodeDecode(object):
    encode: str
    decode: str
    weight: float


def generate_one_hit_char() -> List[EncodeDecode]:
    items = [
        "去\tq",
        "我\tw",
        "二\te",
        "人\tr",
        "他\tt",
        "一\ty",
        "是\tu",
        "出\ti",
        "哦\to",
        "平\tp",
        "啊\ta",
        "三\ts",
        "的\td",
        "非\tf",
        "个\tg",
        "和\th",
        "就\tj",
        "可\tk",
        "了\tl",
        "在\tz",
        "小\tx",
        "才\tc",
        "这\tv",
        "不\tb",
        "你\tn",
        "没\tm",
    ]
    return [EncodeDecode(encode=e.split("\t")[1], decode=e.split("\t")[0], weight=100000000) for e in items]


def generate_topest_char(schema: ShuangPinSchema) -> List[EncodeDecode]:
    chars = """去 我 二 人 他  一 是 出 哦 平 啊 三 的 非 个 和 就 可 了 小 才 这 不 你 没 阿 爱 安 昂 奥 把 白 办 帮 报 被 本 蹦 比 边 表 别 滨 并 拨 部 擦 菜 参 藏 藏 草 测 岑 曾 拆 产 超 车 陈 成 吃 冲 抽 处 揣 传 窗 吹 纯 戳 次 差 从 凑 粗 窜 催 村 错 大 代 但 当 到 得 得 等 地 点 跌 定 丢 动 都 读 段 对 顿 多 额 欸 恩 嗯 而 法 反 放 费 分 风 佛 否 副 嘎 该 干 刚 高 各 给 跟 更 共 够 古 挂 怪 关 光 贵 滚 过 哈 还 含 行 好 何 黑 很 横 红 后 户 话 坏 换 黄 会 混 或 几 加 间 将 叫 接 进 经 久 据 卷 均 卡 开 看 抗 靠 克 剋 肯 坑 空 口 酷 夸 快 宽 况 亏 困 扩 拉 来 浪 老 月 乐 类 冷 里 连 两 料 列 林 另 刘 龙 楼 路 乱 论 落 率 吗 买 慢 忙 毛 么 每 们 梦 米 面 秒 灭 民 名 末 某 目 那 难 囊 闹 呢 内 嫩 能 泥 年 鸟 捏 您 宁 牛 弄 怒 暖 虐 挪 女 欧 怕 排 盘 旁 跑 配 盆 碰 批 片 票 撇 品 凭 破 剖 普 其 恰 前 强 桥 且 请 亲 穷 求 区 全 却 群 然 让 绕 热 任 仍 日 容 肉 如 软 若 撒 赛 散 扫 色 森 僧 啥 晒 山 上 少 设 深 生 时 受 帅 拴 双 水 顺 四 送 搜 苏 算 岁 所 她 太 谈 汤 套 特 疼 体 天 调 贴 听 同 头 图 团 推 托 挖 外 完 王 为 问 翁 喔 握 无 系 下 先 想 笑 些 新 熊 修 需 选 学 亚 眼 样 要 也 以 因 应 哟 用 有 与 元 云 咋 再 早 则 贼 怎 增 扎 占 长 长 找 着 真 正 只 中 周 主 抓 拽 转 装 追 桌 字 总 走 组 最 做"""
    if schema == XHE_SP_SCHEMA:
        char_to_phones = get_char_to_xhe_phones()
    elif schema == LU_SP_SCHEMA:
        char_to_phones = get_char_to_lu_phones()
    elif schema == ZRM_SP_SCHEMA:
        char_to_phones = get_char_to_zrm_phones()
    elif schema == BINGJI_SP_SCHEMA:
        char_to_phones = get_char_to_bingji_phones()
    else:
        raise RuntimeError(f"{schema} not found")

    exists_chars = set()
    items: List[EncodeDecode] = []
    for char in filter(lambda e: e != "", chars.strip().split(" ")):
        if char in exists_chars:
            continue
        exists_chars.add(char)
        if char not in char_to_phones:
            print(f"A: {char} has no phones.")
            continue
        for phone in char_to_phones[char]:
            items.append(EncodeDecode(encode=phone, decode=char, weight=10000000))

    return items


def get_dd_cmds():
    cmds = [
        '$ddcmd(<date.z> <time.hh>时<time.mm>分)\touj',
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


def generate_single_chars(schema: ShuangPinSchema) -> List[EncodeDecode]:
    char_to_shape = get_char_to_xhe_shapes()

    result: List[EncodeDecode] = []
    for item in CharPhoneTable.select().order_by(
            CharPhoneTable.priority.desc(), CharPhoneTable.id.asc()):
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.char in char_to_shape:
            used_shapes = set()
            for shape in char_to_shape[item.char]:
                if shape in used_shapes:
                    continue
                used_shapes.add(shape)
                result.append(EncodeDecode(decode=item.char, encode=phones + shape, weight=item.priority))
        else:
            print(f"没有形码的字：{item.char}")
            result.append(EncodeDecode(decode=item.char, encode=phones, weight=item.priority))
    return result


def generate_simpler_words(char_threshold: int, word_threshold: int, schema: ShuangPinSchema) -> Tuple[
    List[EncodeDecode], List[EncodeDecode]]:
    char_to_shape = get_char_to_xhe_shapes()
    single_chars: Dict[str, CharPhoneTable] = {}
    for item in CharPhoneTable.select().order_by(
            CharPhoneTable.priority.desc(), CharPhoneTable.id.asc()):
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.char in char_to_shape:
            used_shapes = set()
            for shape in char_to_shape[item.char]:
                if shape in used_shapes:
                    continue
                used_shapes.add(shape)
                single_chars[phones + shape] = item
        else:
            print(f"{item}, have no shapes")
            single_chars[phones] = item

    high_pri_simpler_words: List[EncodeDecode] = []
    low_pri_simpler_words: List[EncodeDecode] = []
    exit_word_phones = set()
    for item in WordPhoneTable.select().order_by(
            fn.LENGTH(WordPhoneTable.word),
            WordPhoneTable.priority.desc(), WordPhoneTable.id.asc()):
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.word + ":" + phones in exit_word_phones:
            continue
        exit_word_phones.add(item.word + ":" + phones)
        if len(item.word) > 2:
            continue
        if phones in single_chars:
            if item.priority >= word_threshold and single_chars[phones].priority < char_threshold:
                high_pri_simpler_words.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
            else:
                low_pri_simpler_words.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
    return high_pri_simpler_words, low_pri_simpler_words


def generate_full_words(schema: ShuangPinSchema) -> List[EncodeDecode]:
    char_to_shape = get_char_to_xhe_shapes()
    result: List[EncodeDecode] = []
    exit_word_phones = set()
    for item in WordPhoneTable.select().order_by(
            fn.LENGTH(WordPhoneTable.word),
            WordPhoneTable.priority.desc(), WordPhoneTable.id.asc()):
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.word + ":" + phones in exit_word_phones:
            print(f"重复的记录: {item}")
            continue
        exit_word_phones.add(item.word + ":" + phones)
        if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
            used_shapes = set()
            for shape_first in char_to_shape[item.word[0]]:
                for shape_last in char_to_shape[item.word[-1]]:
                    shapes = [
                        shape_first[0] + shape_last[0],
                    ]
                    for shape in shapes:
                        if shape in used_shapes:
                            continue
                        used_shapes.add(shape)
                        encode = phones + shape
                        decode = item.word
                        result.append(EncodeDecode(encode=encode, decode=decode, weight=item.priority))
        else:
            print(f"没有形码的词：{item.word}")
            result.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
            continue

    return result


def generate_eng() -> List[str]:
    result = []
    for local_item in EngWordTable.select().where(
            EngWordTable.priority > 0).order_by(fn.LENGTH(EngWordTable.word), EngWordTable.priority):
        if not is_all_alpha(local_item.word):
            continue
        result.append(f"{local_item.word}\t{local_item.word}")
    return result


def generate_simpler() -> List[EncodeDecode]:
    result = []
    for item in SimplerTable.select().where(
            SimplerTable.priority > 0).order_by(SimplerTable.priority.desc()):
        encode = item.keys
        decode = item.words
        rule = f"{decode}\t{encode}"
        result.append(EncodeDecode(encode=encode, decode=decode, weight=item.priority))

    return result


def generate_schema(config: SchemaConfig, outpath: str):
    with open(outpath, 'w', encoding='utf8') as fout:
        fout.write(f"# 小鹭音形系列方案\n")
        fout.write(f"# encoding: utf-8\n")
        fout.write(f"# 机器生成，请勿修改\n")
        fout.write(f"\n")

        fout.write(f"\nschema:\n")
        fout.write(f"  schema_id: {config.schema_id}\n")
        fout.write(f"  name: {config.name}\n")
        fout.write(f'  version: "{config.version}"\n')
        fout.write(f'  author: \n')
        for author in config.authors:
            fout.write(f'    - {author} \n')
        fout.write(f'  description: |\n')
        fout.write(f'     {config.description}\n')

        fout.write(f"\nswitches:\n")
        fout.write(f"  - name: ascii_mode \n")
        fout.write(f"    reset: 0\n")
        fout.write(f"  - name: full_shape\n")
        fout.write(f"  - name: zh_simp\n")
        fout.write(f"    reset: 1\n")
        fout.write(f"    states: [ 繁, 简 ]\n")
        fout.write(f"  - name: ascii_punct\n")
        fout.write(f"    reset: 0\n")

        fout.write(f"\nengine:\n")
        fout.write(f"  processors:\n")
        fout.write(f"    - ascii_composer\n")
        fout.write(f"    - recognizer\n")
        fout.write(f"    - key_binder\n")
        fout.write(f"    - speller\n")
        fout.write(f"    - punctuator\n")
        fout.write(f"    - selector\n")
        fout.write(f"    - navigator\n")
        fout.write(f"    - express_editor\n")
        fout.write(f"  segmentors:\n")
        fout.write(f"    - ascii_segmentor\n")
        fout.write(f"    - matcher\n")
        fout.write(f"    - abc_segmentor\n")
        fout.write(f"    - punct_segmentor\n")
        fout.write(f"    - fallback_segmentor\n")
        fout.write(f"  translators:\n")
        fout.write(f"    - punct_translator\n")
        fout.write(f"    - table_translator\n")
        fout.write(f"  filters:\n")
        fout.write(f"    - simplifier\n")
        fout.write(f"    - uniquifier\n")

        fout.write("\n")

        fout.write(f"speller:\n")
        fout.write(f"  alphabet: 'zyxwvutsrqponmlkjihgfedcba'\n")
        fout.write(f"  initials: 'abcdefghijklmnopqrstuvwxyz'\n")
        fout.write(f"  auto_select: true\n")
        fout.write(f"  auto_select_pattern: {config.auto_select_pattern}\n")

        fout.write(f"\n")

        fout.write(f"translator:\n")
        fout.write(f"  dictionary: {config.schema_id}\n")
        fout.write(f"  enable_charset_filter: false\n")
        fout.write(f"  enable_sentence: false\n")
        fout.write(f"  enable_completion: true\n")
        fout.write(f"  enable_user_dict: true\n")
        fout.write(f"  enable_encoder: true\n")
        fout.write(f"  encode_commit_history: true\n")
        fout.write(f"  max_phrase_length: 3\n")

        fout.write(f"\n\n")

        fout.write(f"punctuator:\n")
        fout.write(f"  import_preset: default\n")

        fout.write(f"\n")

        fout.write(f"key_binder:\n")
        fout.write(f"  import_preset: default\n")
        fout.write(f"  bindings:\n")
        fout.write(f"    - {{accept: comma, send: comma, when: paging}} #注销逗号翻页\n")
        fout.write(f"    - {{accept: period, send: period, when: has_menu}} #注销句号翻页\n")
        fout.write(f"    - {{accept: semicolon, send: 2, when: has_menu}} #分号次选\n")
        fout.write(f"    - {{accept: apostrophe, send: 3, when: has_menu}} #单引号3选\n")
        fout.write(f"    - {{accept: bracketleft, send: 4, when: has_menu}} #单引号4选\n")
        fout.write(f"    - {{accept: bracketright, send: 5, when: has_menu}} #单引号5选\n")
        fout.write(f"    - {{accept: dollar, send: 2, when: composing}}\n")
        fout.write(f"    - {{accept: Release+dollar, send: period, when: composing}}\n")
        fout.write(f"    - {{accept: Release+period, send: period, when: composing}}\n")
        fout.write(f"    - {{accept: bar, send: 2, when: composing}}\n")
        fout.write(f"    - {{accept: Release+bar, send: comma, when: composing}}\n")
        fout.write(f"    - {{accept: Release+comma, send: comma, when: composing}}\n")
        fout.write(f'    - {{accept: "Tab", send: Page_Down, when: has_menu}}\n')
        fout.write(f'    - {{accept: "Tab", send: Escape, when: composing}}\n')
        fout.write(f'    - {{accept: "Caps_Lock", send: Escape, when: composing}}\n')
        fout.write(f'    - {{accept: "Shift_R", send: Escape, when: composing}}\n')
        fout.write(f'    - {{accept: "Shift+space", toggle: full_shape, when: always}} #切换全半角\n')
        fout.write(f'    - {{accept: "Control+period", toggle: ascii_punct, when: always}}\n')

        fout.write(f"\n")

        fout.write(f"menu:\n")
        fout.write(f"  page_size: 5\n")

        fout.write(f"style:\n")
        fout.write(f"  horizontal: true\n")


def generate_dict(config: SchemaConfig, outpath: str):
    if config.shuangpin_schema == XHE_SP_SCHEMA:
        char_to_phones = get_char_to_xhe_phones()
    elif config.shuangpin_schema == LU_SP_SCHEMA:
        char_to_phones = get_char_to_lu_phones()
    elif config.shuangpin_schema == ZRM_SP_SCHEMA:
        char_to_phones = get_char_to_zrm_phones()
    elif config.shuangpin_schema == BINGJI_SP_SCHEMA:
        char_to_phones = get_char_to_bingji_phones()
    else:
        raise RuntimeError(f"{config.shuangpin_schema} not found")

    print(f"total {len(char_to_phones)} char phones")

    char_to_shape = get_char_to_xhe_shapes()
    print(f"total {len(char_to_shape)} char shapes")

    with open(outpath, 'w', encoding='utf8') as fout:
        fout.write(f"# {config.schema_id} dictionary\n")
        fout.write(f"# encoding: utf-8\n")
        fout.write(f"# \n")
        fout.write(f"# {config.name}码表\n")
        fout.write(f"# 机器生成，请勿修改\n")

        fout.write(f"\n---\n")
        fout.write(f"name: {config.schema_id}\n")
        fout.write(f'version: "{config.version}"\n')
        fout.write(f'sort: original\n')
        fout.write(f'use_preset_vocabulary: false\n')  # 是否使用预设词表

        fout.write(f'columns:\n')
        fout.write(f'  - text\n')
        fout.write(f'  - code\n')

        fout.write(f'encoder:\n')
        fout.write(f'  rules:\n')
        fout.write(f'    - length_equal: 2\n')
        fout.write(f'      formula: "AaAbBaBb"\n')
        fout.write(f'    - length_equal: 3\n')
        fout.write(f'      formula: "AaAbBaBbCaCb"\n')
        fout.write(f'    - length_equal: 4\n')
        fout.write(f'      formula: "AaAbBaBbCaCbDaDb"\n')
        fout.write(f'    - length_equal: 5\n')
        fout.write(f'      formula: "AaAbBaBbCaCbDaDbEaEb"\n')
        fout.write(f'    - length_equal: 6\n')
        fout.write(f'      formula: "AaAbBaBbCaCbDaDbEaEbFaFb"\n')
        fout.write(f'    - length_equal: 7\n')
        fout.write(f'      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGb"\n')
        fout.write(f'    - length_equal: 8\n')
        fout.write(f'      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbHaHb"\n')

        fout.write(f"...\n")

        fout.write(f"\n# 单字\n")

        with trange(6, desc="writing chars", position=0) as pbar: # 6个单字处理
            pbar.set_postfix_str("writing one hit chars")
            for item in generate_one_hit_char():
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()
            
            pbar.set_postfix_str("writing topest chars")
            for item in generate_topest_char(config.shuangpin_schema):
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing single chars")
            single_chars = generate_single_chars(config.shuangpin_schema)
            for item in single_chars:
                fout.write(f"{item.decode}\t{item.encode[:-1]}\n")
            pbar.update()

            pbar.set_postfix_str("writing simpler words")
            special_words = set()
            high_word, low_words = generate_simpler_words(100, 2000, config.shuangpin_schema)
            for item in high_word:
                special_words.add(item.decode)
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing single chars (full code)")
            for item in single_chars:
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing special words")
            for item in low_words:
                special_words.add(item.decode)
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

        fout.write(f"\n# 词语\n")

        with trange(4, desc="writing words") as pbar: # 4个词语处理
            pbar.set_postfix_str("writing full words")
            for item in generate_full_words(config.shuangpin_schema):
                if item.decode not in special_words:
                    fout.write(f"{item.decode}\t{item.encode[0:-2]}\n")
                fout.write(f"{item.decode}\t{item.encode[0:-1]}\n")
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing tangshi words")
            for item in generate_tangshi_words(config.shuangpin_schema):
                fout.write(f"{item.decode}\t{item.encode[0:-2]}\n")
                fout.write(f"{item.decode}\t{item.encode[0:-1]}\n")
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing 4 len word simpler items")
            for item in generate_4_len_word_simpler_items(config.shuangpin_schema):
                fout.write(f"{item.decode}\t{item.encode[0:-2]}\n")
                fout.write(f"{item.decode}\t{item.encode[0:-1]}\n")
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()

            pbar.set_postfix_str("writing simpler words")
            for item in generate_simpler():
                fout.write(f"{item.decode}\t{item.encode}\n")
            pbar.update()


def generate_schema_custom(config: SchemaConfig, outpath: str):
    with open(outpath, 'w', encoding='utf8') as fout:
        fout.write(f"# {config.schema_id} custom settings\n")
        fout.write(f"# encoding: utf-8\n")
        fout.write(f"# \n")
        fout.write(f"# {config.name} custom settings\n")
        fout.write(f"# 机器生成，请勿修改\n")

        fout.write(f"patch:\n")
        fout.write(f"  punctuator/half_shape:\n")
        fout.write(f"    '/': '、'\n")
        fout.write(f"    '<': '《'\n")
        fout.write(f"    '>': '》'\n")

        fout.write(f'\n')

        fout.write(f'  "ascii_composer/switch_key/Shift_L": commit_code\n')
        fout.write(f'  "ascii_composer/switch_key/Shift_R": commit_code\n')

        fout.write(f'\n')

        fout.write(f'  "style/display_tray_icon": true\n')
        fout.write(f'  "style/horizontal": true\n')  # 横排显示
        fout.write(f'  "style/font_face": "Microsoft YaHei"\n')  # 字体
        fout.write(f'  "style/font_point": 12\n')  # 字体大小
        fout.write(f'  "style/inline_preedit": true\n')  # 嵌入式候选窗单行显示
        fout.write(f'  "style/layout/border_width": 0\n')
        fout.write(f'  "style/layout/border": 0\n')
        fout.write(f'  "style/layout/margin_x": 7\n')  # 候选字左右边距
        fout.write(f'  "style/layout/margin_y": 7\n')  # 候选字上下边距
        fout.write(f'  "style/layout/hilite_padding": 8\n')  # 候选字背景色色块高度 若想候选字背景色块无边界填充候选框，仅需其高度和候选字上下边距一致即可
        fout.write(f'  "style/layout/hilite_spacing": 1\n')  # 序号和候选字之间的间隔
        fout.write(f'  "style/layout/spacing": 7\n')  # 作用不明
        fout.write(f'  "style/layout/candidate_spacing": 8\n')  # 候选字间隔
        fout.write(f'  "style/layout/round_corner": 5\n')  # 候选字背景色块圆角幅度


def generate_weasel_custom(config: SchemaConfig, outpath: str):
    with open(outpath, 'w', encoding='utf8') as fout:
        fout.write(f'customization:\n')
        fout.write(f'  distribution_code_name: Weasel\n')
        fout.write(f'  distribution_version: 0.14.3\n')
        fout.write(f'  generator: "Rime::SwitcherSettings"\n')
        fout.write(f'  modified_time: "Mon Jun  6 16:28:09 2022"\n')
        fout.write(f'  rime_version: 1.5.3\n')

        fout.write(f'\n')

        fout.write(f'patch:\n')
        fout.write(f'  "style/color_scheme": LuColor\n')
        fout.write(f'  "preset_color_schemes/LuColor":\n')
        fout.write(f'    name: "LuColor"\n')
        fout.write(f'    author: "ledao"\n')
        fout.write(f'    back_color: 0xffffff\n')  # 候选框 背景色
        fout.write(f'    corner_redius: 5\n')
        fout.write(f'    border_color: 0xE6E6E6\n')  # 候选框 边框颜色
        fout.write(f'    text_color: 0x000000\n')  # 已选择字 文字颜色
        fout.write(f'    hilited_text_color: 0x000000\n')  # 已选择字右侧拼音 文字颜色
        fout.write(f'    hilited_back_color: 0xffffff\n')  # 已选择字右侧拼音 背景色
        fout.write(f'    hilited_candidate_text_color: 0x000000\n')  # 候选字颜色
        fout.write(f'    hilited_candidate_back_color: 0xE6E6E6\n')  # 候选字背景色
        fout.write(f'    hilited_corner_radius: 5\n')
        fout.write(f'    candidate_text_color: 0x000000\n')  # 未候选字颜ch色


def generate_dd(schema: ShuangPinSchema, output_dir: str):
    if schema == XHE_SP_SCHEMA:
        check_xhe_shuangpin.main()
    elif schema == LU_SP_SCHEMA:
        check_lu_shuangpin.main()
    elif schema == ZRM_SP_SCHEMA:
        check_zrm_shuangpin.main()
    elif schema == BINGJI_SP_SCHEMA:
        check_bingji_shuangpin.main()
    else:
        raise RuntimeError(f"{schema} not found")

    sys_top_chars_data = f"{output_dir}/sys_top_chars_data.txt"
    single_chars = generate_single_chars(schema)
    with open(sys_top_chars_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-1\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=简码单字\n")
        for item in generate_one_hit_char():
            fout.write(f"{item.decode}\t{item.encode}#序{90000}\n")
        for item in generate_topest_char(schema):
            fout.write(f"{item.decode}\t{item.encode}#序{80000}\n")
        for item in single_chars:
            fout.write(f"{item.decode}\t{item.encode[:-1]}#序{75000}\n")

    high_freq_words, low_freq_words = generate_simpler_words(100, 2000, schema)
    sys_high_freq_word_data = f"{output_dir}/sys_high_word_data.txt"
    with open(sys_high_freq_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-3\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=高频简词\n")
        for item in high_freq_words:
            fout.write(f"{item.decode}\t{item.encode}#序{75000}\n")

    sys_single_char_data = f"{output_dir}/sys_single_char_data.txt"
    with open(sys_single_char_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-2\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统单字\n")
        for item in single_chars:
            fout.write(f"{item.decode}\t{item.encode}#序{70000}\n")

    sys_low_freq_word_data = f"{output_dir}/sys_low_word_data.txt"
    with open(sys_low_freq_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-4\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=低频简词\n")
        for item in low_freq_words:
            fout.write(f"{item.decode}\t{item.encode}#序{65000}\n")

    sys_word_data = f"{output_dir}/sys_word_data.txt"
    with open(sys_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-5\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统词组\n")
        for item in generate_full_words(schema):
            fout.write(f"{item.decode}\t{item.encode}#序{60000}\n")

    sys_simpler_word_data = f"{output_dir}/sys_simpler_word_data.txt"
    with open(sys_simpler_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-6\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统简词\n")
        for item in generate_4_len_word_simpler_items(schema):
            fout.write(f"{item.decode}\t{item.encode}#序{55000}\n")

    sys_tangshi_data = f"{output_dir}/sys_tangshi_word_data.txt"
    with open(sys_tangshi_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-7\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统唐诗\n")
        for item in generate_tangshi_words(schema):
            fout.write(f"{item.decode}\t{item.encode}#序{52000}\n")

    with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-8\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统英文\n")
        for item in generate_eng():
            fout.write(f"{item}#序{50000}\n")

    with open(f'{output_dir}/sys_simpler_data.txt', 'w',
              encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-9\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统简码\n")
        for item in generate_simpler():
            fout.write(f"{item.decode}\t{item.encode}#序{40000}\n")

    with open(f'{output_dir}/sys_cmd_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-10\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=直通车\n")
        cmds = get_dd_cmds()
        for cmd in cmds:
            fout.write(f"{cmd}\n")


def generate_rime(schema_config: SchemaConfig, output_dir: str):
    if schema_config.shuangpin_schema == XHE_SP_SCHEMA:
        check_xhe_shuangpin.main()
    elif schema_config.shuangpin_schema == LU_SP_SCHEMA:
        check_lu_shuangpin.main()
    elif schema_config.shuangpin_schema == ZRM_SP_SCHEMA:
        check_zrm_shuangpin.main()
    elif schema_config.shuangpin_schema == BINGJI_SP_SCHEMA:
        check_bingji_shuangpin.main()
    else:
        raise RuntimeError(f"{schema_config.shuangpin_schema} not found")

    generate_schema(schema_config, output_dir + f"/{schema_config.schema_id}.schema.yaml")
    generate_dict(schema_config, output_dir + f"/{schema_config.schema_id}.dict.yaml")
    generate_schema_custom(schema_config, output_dir + f"/{schema_config.schema_id}.custom.yaml")
    generate_weasel_custom(schema_config, output_dir + f"/weasel.custom.yaml")


def generate_4_len_wordphonetable_words(schema: ShuangPinSchema) -> List[EncodeDecode]:
    char_to_shape = get_char_to_xhe_shapes()
    result: List[EncodeDecode] = []
    exit_word_phones = set()
    for item in WordPhoneTable.select().order_by(
            fn.LENGTH(WordPhoneTable.word),
            WordPhoneTable.priority.desc(), WordPhoneTable.id.asc()):
        if len(item.word) <= 3:
            continue
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        simpler_phones = ""
        for i in range(len(phones)):
            if i % 2 == 0:
                simpler_phones += phones[i]
        phones = simpler_phones

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.word + ":" + phones in exit_word_phones:
            print(f"重复的记录: {item}")
            continue
        exit_word_phones.add(item.word + ":" + phones)
        if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
            used_shapes = set()
            for shape_first in char_to_shape[item.word[0]]:
                for shape_last in char_to_shape[item.word[-1]]:
                    shapes = [
                        shape_first[0] + shape_last[0],
                    ]
                    for shape in shapes:
                        if shape in used_shapes:
                            continue
                        used_shapes.add(shape)
                        encode = phones + shape
                        decode = item.word
                        result.append(EncodeDecode(encode=encode, decode=decode, weight=item.priority))
        else:
            print(f"没有形码的词：{item.word}")
            result.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
            continue

    return result


def generate_4_len_tangshi_words(schema: ShuangPinSchema) -> List[EncodeDecode]:
    char_to_shape = get_char_to_xhe_shapes()
    result: List[EncodeDecode] = []
    exit_word_phones = set()
    for item in TangshiTable.select().order_by(
            fn.LENGTH(TangshiTable.word),
            TangshiTable.priority.desc(), TangshiTable.id.asc()):
        if len(item.word) <= 3:
            continue
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        simpler_phones = ""
        for i in range(len(phones)):
            if i % 2 == 0:
                simpler_phones += phones[i]
        phones = simpler_phones

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.word + ":" + phones in exit_word_phones:
            print(f"重复的记录: {item}")
            continue
        exit_word_phones.add(item.word + ":" + phones)
        if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
            used_shapes = set()
            for shape_first in char_to_shape[item.word[0]]:
                for shape_last in char_to_shape[item.word[-1]]:
                    shapes = [
                        shape_first[0] + shape_last[0],
                    ]
                    for shape in shapes:
                        if shape in used_shapes:
                            continue
                        used_shapes.add(shape)
                        encode = phones + shape
                        decode = item.word
                        result.append(EncodeDecode(encode=encode, decode=decode, weight=item.priority))
        else:
            print(f"没有形码的词：{item.word}")
            result.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
            continue

    return result


def generate_4_len_word_simpler_items(schema: ShuangPinSchema) -> List[EncodeDecode]:
    result = []
    result.extend(generate_4_len_wordphonetable_words(schema))
    result.extend(generate_4_len_tangshi_words(schema))
    return result


def generate_tangshi_words(schema: ShuangPinSchema) -> List[EncodeDecode]:
    char_to_shape = get_char_to_xhe_shapes()
    result: List[EncodeDecode] = []
    exit_word_phones = set()
    for item in TangshiTable.select().order_by(
            fn.LENGTH(TangshiTable.word),
            TangshiTable.priority.desc(), TangshiTable.id.asc()):
        if schema == XHE_SP_SCHEMA:
            phones = item.xhe
        elif schema == LU_SP_SCHEMA:
            phones = item.lu
        elif schema == ZRM_SP_SCHEMA:
            phones = item.zrm
        elif schema == BINGJI_SP_SCHEMA:
            phones = item.bingji
        else:
            raise RuntimeError(f"schema not found {schema}")

        if phones == "":
            raise RuntimeError(f"empty phones, {item}")

        if item.word + ":" + phones in exit_word_phones:
            print(f"重复的记录: {item}")
            continue
        exit_word_phones.add(item.word + ":" + phones)

        if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
            used_shapes = set()
            for shape_first in char_to_shape[item.word[0]]:
                for shape_last in char_to_shape[item.word[-1]]:
                    shapes = [
                        shape_first[0] + shape_last[0],
                    ]
                    for shape in shapes:
                        if shape in used_shapes:
                            continue
                        used_shapes.add(shape)
                        encode = phones + shape
                        decode = item.word
                        result.append(EncodeDecode(encode=encode, decode=decode, weight=item.priority))
        else:
            print(f"没有形码的词：{item.word}")
            result.append(EncodeDecode(encode=phones, decode=item.word, weight=item.priority))
            continue

    return result
