#encoding=utf8
import os, sys
from pathlib import Path
from collections import defaultdict
from tables import CharPhoneTable, CharShapeTable, WordPhoneTable, EngWordTable
from tables import DelWordTable
from peewee import fn
from toolz.curried import pipe, map, filter, curry, reduceby, valmap, groupby


def generate_one_hit_char(priority):
    items = {
        "去\tq": priority,"我\tw": priority,"二\te": priority,"人\tr": priority,"他\tt": priority,"一\ty": priority,"是\tu": priority,"出\ti": priority,"哦\to": priority,"平\tp": priority,
        "啊\ta": priority,"三\ts": priority,"的\td": priority,"非\tf": priority,"个\tg": priority,"和\th": priority,"就\tj": priority,"可\tk": priority,"了\tl": priority,
        "在\tz": priority,"小\tx": priority,"才\tc": priority,"这\tv": priority,"不\tb": priority,"你\tn": priority,"没\tm": priority,
    }
    return items


def generate_topest_char(char_to_phones, prioroty):
    chars = """去 我 二 人 他  一 是 出 哦 平 啊 三 的 非 个 和 就 可 了 在 小 才 这 不 你 没 阿 爱 安 昂 奥 把 白 办 帮 报 被 本 蹦 比 边 表 别 滨 并 拨 部 擦 菜 参 藏 藏 草 测 岑 曾 拆 产 超 车 陈 成 吃 冲 抽 处 揣 传 窗 吹 纯 戳 次 差 从 凑 粗 窜 催 村 错 大 代 但 当 到 得 得 等 地 点 跌 定 丢 动 都 读 段 对 顿 多 额 欸 恩 嗯 而 法 反 放 费 分 风 佛 否 副 嘎 该 干 刚 高 各 给 跟 更 共 够 古 挂 怪 关 光 贵 滚 过 哈 还 含 行 好 何 黑 很 横 红 后 户 话 坏 换 黄 会 混 或 几 加 间 将 叫 接 进 经 久 据 卷 均 卡 开 看 抗 靠 克 剋 肯 坑 空 口 酷 夸 快 宽 况 亏 困 扩 拉 来 浪 老 月 乐 类 冷 里 连 两 料 列 林 另 刘 龙 楼 路 乱 论 落 率 吗 买 慢 忙 毛 么 每 们 梦 米 面 秒 灭 民 名 末 某 目 那 难 囊 闹 呢 内 嫩 能 泥 年 鸟 捏 您 宁 牛 弄 怒 暖 虐 挪 女 欧 怕 排 盘 旁 跑 配 盆 碰 批 片 票 撇 品 凭 破 剖 普 其 恰 前 强 桥 且 亲 请 穷 求 区 全 却 群 然 让 绕 热 任 仍 日 容 肉 如 软 若 撒 赛 散 扫 色 森 僧 啥 晒 山 上 少 设 深 生 时 受 说 数 帅 拴 双 谁 水 顺 四 送 搜 苏 算 岁 所 她 太 谈 汤 套 特 疼 体 天 调 贴 听 同 头 图 团 推 托 挖 外 完 王 为 问 翁 喔 握 无 系 下 先 想 笑 些 新 熊 修 需 选 学 亚 眼 样 要 也 以 因 应 哟 用 有 与 元 云 咋 再 早 则 贼 怎 增 扎 占 长 长 找 着 真 正 只 中 周 主 抓 拽 转 装 追 桌 字 总 走 组 最 做"""

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
        if e.isalpha():
            continue
        else:
            return False
    return True

@curry
def for_each(proc, eles):
    for e in eles:
        proc(e)


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("USAGE: python3 generate_dd_txt.py output_dir")
        sys.exit(1)

    fname, output_dir = sys.argv

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

     char_to_shape = pipe(CharShapeTable.select(),
        map(lambda e: (e.char, e.shapes)),
        reduceby(lambda e: e[0], lambda e1, e2: e1),
        valmap(lambda e: e[1]),
        dict
    )
    print(f"total {len(char_to_shape)} char shapes")

    char_to_phones = pipe(CharPhoneTable.select(),
        map(lambda e: (e.char, e.phones)),
        groupby(lambda e: e[0]),
        valmap(lambda phones: [e[1] for e in phones]),
        dict
    )
    print(f"total {len(char_to_phones)} char phones")

    one_hit_char_items = generate_one_hit_char(60000)
    top_single_chars_items = generate_topest_char(char_to_phones, 60000)
    sys_top_chars_data = f"{output_dir}/sys_top_chars_data.txt"
    with open(sys_top_chars_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-1\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=简码单字\n")
        for item in one_hit_char_items.items():
            fout.write(f"{item[0]}#序{item[1]}\n")
        for item in top_single_chars_items.items():
            fout.write(f"{item[0]}#序{item[1]}\n")
 
    sys_single_char_data = f"{output_dir}/sys_single_char_data.txt"
    with open(sys_single_char_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-系统码表\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统单字\n")
        pipe(
            CharPhoneTable.select().order_by(CharPhoneTable.priority.desc()),
            filter(lambda e: e.char in char_to_shape),
            map(lambda e: f"{e.char}\t{e.phones+char_to_shape[e.char]}#序40000"),
            for_each(lambda e: fout.write(e+'\n')),
        )

    del_words = pipe(
        DelWordTable.select(),
        map(lambda e: e.word),
        set
    )
    sys_word_data = f"{output_dir}/sys_word_data.txt"
    with open(sys_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-2\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统词组\n")
        pipe(
            WordPhoneTable.select().order_by(fn.LENGTH(WordPhoneTable.word), WordPhoneTable.priority.desc()),
            filter(lambda e: e.word not in del_words),
            map(lambda e: (f'{e.word}\t{e.phones}', e.word[0], e.word[-1])),
            filter(lambda e: e[1] in char_to_shape and e[2] in char_to_shape),
            map(lambda e: f'{e[0]}{char_to_shape[e[1]][0]}{char_to_shape[e[2]][-1]}#序20000'),
            for_each(lambda e: fout.write(e+'\n'))
        )

    with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout: 
        fout.write("---config@码表分类=主码-3\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统英文\n")
        pipe(EngWordTable.select().where(EngWordTable.priority > 100).order_by(fn.LENGTH(EngWordTable.word), EngWordTable.priority),
            filter(lambda e: is_all_alpha(e.word)),
            map(lambda e: e.word+'\t'+e.word+"#序10000"),
            for_each(lambda e: fout.write(e+'\n')),
        )

    print('done')