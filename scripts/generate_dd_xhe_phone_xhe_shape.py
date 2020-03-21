# encoding=utf8
import os
import sys
from pathlib import Path
from collections import defaultdict
from tables import CharPhoneTable, CharShapeTable, WordPhoneTable, EngWordTable
from tables import DelWordTable
from peewee import fn
from toolz.curried import pipe, map, filter, curry, reduceby, valmap, groupby



if __name__ == "__main__":

    if len(sys.argv) != 1:
        print("USAGE: python3 generate_dd_txt.py ")
        sys.exit(1)

    fname, output_dir = sys.argv[0], "xhe_phone_xhe_shape"

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
                          map(lambda e: (e.char, e.xhe)),
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
            map(
                lambda e: f"{e.char}\t{e.xhe+char_to_shape[e.char]}#序40000"),
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
            WordPhoneTable.select().order_by(fn.LENGTH(WordPhoneTable.word),
                                             WordPhoneTable.priority.desc()),
            filter(lambda e: e.word not in del_words),
            map(lambda e: (f'{e.word}\t{e.xhe}', e.word[0], e.word[-1])),
            filter(lambda e: e[1] in char_to_shape and e[2] in char_to_shape),
            map(lambda e: f'{e[0]}{char_to_shape[e[1]][0]}{char_to_shape[e[2]][-1]}#序20000'),
            for_each(lambda e: fout.write(e+'\n'))
        )

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
