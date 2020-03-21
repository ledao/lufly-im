# encoding=utf8
import os
import sys
from pathlib import Path
from collections import defaultdict
from common import get_char_to_lu_shapes, get_char_to_phones, get_del_words
from peewee import fn
from toolz.curried import pipe, map, filter, curry, reduceby, valmap, groupby
from tables import CharPhoneTable, CharHeShapeTable, WordPhoneTable, EngWordTable





if __name__ == "__main__":

    if len(sys.argv) != 2 or sys.argv[1] not in ['ff', 'fb']:
        print(f"USAGE: python3 {sys.argv[0]} mode[ff|fb] ")
        sys.exit(1)

    mode = sys.argv[1]
    fname, output_dir = sys.argv[0], "xhe_phone_lu_shape_" + mode

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    char_to_shape = get_char_to_lu_shapes()
    print(f"total {len(char_to_shape)} char shapes")

    char_to_phones = get_char_to_phones()
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
        for item in CharPhoneTable.select().order_by(CharPhoneTable.priority.desc()):
            if item.char in char_to_shape:
                for shape in char_to_shape[item.char]:
                    fout.write(f"{item.char}\t{item.xhe+shape}#序40000\n")
            else:
                fout.write(f"{item.char}\t{item.xhe}#序40000\n")

    del_words = get_del_words()

    sys_word_data = f"{output_dir}/sys_word_data.txt"
    with open(sys_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-2\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统词组\n")
        for item in WordPhoneTable.select().order_by(fn.LENGTH(WordPhoneTable.word), WordPhoneTable.priority.desc()):
            if item.word in del_words:
                continue
            if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
                for shape_first in char_to_shape[item.word[0]]:
                    for shape_last in char_to_shape[item.word[-1]]:
                        if mode == 'ff':
                            fout.write(f'{item.word}\t{item.xhe+shape_first[0]+shape_last[0]}#序20000\n')
                        else:
                            fout.write(f'{item.word}\t{item.xhe+shape_first[0]+shape_last[-1]}#序20000\n')
            else:
                #fout.write(f'{item.word}\t{item.xhe}#序20000\n')
                pass

    with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-3\n")
        fout.write("---config@允许编辑=否\n")
        fout.write(f"---config@码表别名=系统英文\n")
        pipe(EngWordTable.select().where(EngWordTable.priority > 0).order_by(fn.LENGTH(EngWordTable.word), EngWordTable.priority),
             filter(lambda e: is_all_alpha(e.word)),
             map(lambda e: e.word+'\t'+e.word+"#序10000"),
             for_each(lambda e: fout.write(e+'\n')),
             )

    print('done')
