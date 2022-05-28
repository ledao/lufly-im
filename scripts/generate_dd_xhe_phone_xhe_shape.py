# encoding=utf8
import os
import sys
import shutil
from pathlib import Path
from collections import defaultdict
from common import *
from peewee import fn
from toolz.curried import *
from tables import *

if __name__ == "__main__":

    if len(sys.argv) != 1:
        print(f"USAGE: python3 {sys.argv[0]}")
        sys.exit(1)

    fname, output_dir = sys.argv[0], "xhe_phone_xhe_shape"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    char_to_shape = get_char_to_xhe_shapes()
    print(f"total {len(char_to_shape)} char shapes")

    char_to_phones = get_char_to_xhe_phones()
    print(f"total {len(char_to_phones)} char phones")

    one_hit_char_items = generate_one_hit_char(90000)
    top_single_chars_items = generate_topest_char(char_to_phones, 80000)
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
        fout.write("---config@码表分类=主码-2\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统单字\n")
        for item in CharPhoneTable.select().order_by(
                CharPhoneTable.priority.desc()):
            if item.char in char_to_shape:
                used_shapes = set()
                for shape in char_to_shape[item.char]:
                    if shape in used_shapes:
                        continue
                    used_shapes.add(shape)
                    fout.write(f"{item.char}\t{item.xhe+shape}#序{70000}\n")
            else:
                fout.write(f"{item.char}\t{item.xhe}#序{70000}\n")

    del_words = get_del_words()

    sys_word_data = f"{output_dir}/sys_word_data.txt"
    with open(sys_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-3\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统词组\n")
        exit_word_phones = set()
        for item in WordPhoneTable.select().order_by(
                fn.LENGTH(WordPhoneTable.word),
                WordPhoneTable.priority.desc()):
            if item.word in del_words:
                continue
            if item.word + ":" + item.xhe in exit_word_phones:
                continue
            exit_word_phones.add(item.word + ":" + item.xhe)
            if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
                used_shapes = set()
                for shape_first in char_to_shape[item.word[0]]:
                    for shape_last in char_to_shape[item.word[-1]]:
                        shape = shape_first[0] + ":" + shape_last[0]
                        if shape in used_shapes:
                            continue
                        used_shapes.add(shape)
                        encode = item.xhe + shape_first[0] + shape_last[0]
                        decode = item.word
                        fout.write(f'{decode}\t{encode}#序{60000}\n')
            else:
                pass

    with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-4\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统英文\n")
        for e in EngWordTable.select().where(
                EngWordTable.priority > 0).order_by(
                    fn.LENGTH(EngWordTable.word), EngWordTable.priority):
            if not is_all_alpha(e.word):
                continue
            #item = e.word + '\t' + e.word + f"#序{10000}"
            item = e.word + '\t' + e.word + f"#序{50000}"
            fout.write(item + "\n")

    with open(f'{output_dir}/sys_simpler_data.txt', 'w',
              encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-5\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统简码\n")
        for e in SimplerTable.select().where(
                SimplerTable.priority > 0).order_by(
                    SimplerTable.priority.desc()):
            encode = e.keys
            decode = e.words
            rule = f"{decode}\t{encode}"
            item = rule + f"#序{40000}"
            fout.write(item + "\n")

    with open(f'{output_dir}/sys_cmd_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-6\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=直通车\n")
        cmds = get_dd_cmds()
        for cmd in cmds:
            fout.write(f"{cmd}\n")

    dd_dir = 'lufly/win-dd/lufly-im-v4/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')
