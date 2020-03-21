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
        print("USAGE: python3 generate_dd_txt.py \n" + '''
百度手机输入法：  
可进入“高级设置→管理双拼方案→常用双拼方案”选择“小鹤双拼”，完成双拼方案设置；
再进入“高级设置→管理个性短语→导入个性短语”导入“xiaolu_word_for_baidu.ini”文件即可。
        ''')
        sys.exit(1)

    fname, output_dir = sys.argv[0], "baidu_mobile_ini"

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

    all_items = []
    #单字部分
    all_items.extend([tuple(e.split("\t")) for e in generate_one_hit_char(60000).keys()])
    all_items.extend([tuple(e.split("\t")) for e in generate_topest_char(char_to_phones, 60000)])

    #系统单字部分
    all_items.extend(pipe(
        CharPhoneTable.select(),
        filter(lambda e: e.char in char_to_shape),
        map(lambda e: (e.char, f"{e.xhe+char_to_shape[e.char]}")),
        list
    ))

    del_words = pipe(
        DelWordTable.select(),
        map(lambda e: e.word),
        set
    )
    all_items.extend(pipe(
        WordPhoneTable.select(),
        filter(lambda e: e.word not in del_words),
        map(lambda e: (e.word, e.xhe, e.word[0], e.word[-1])),
        filter(lambda e: e[2] in char_to_shape and e[3] in char_to_shape),
        map(lambda e: (e[0], e[1] + char_to_shape[e[2]][0]+char_to_shape[e[3]][0])),
        list
    ))

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(output_dir+"/xiaolu_word_for_baidu.ini", 'w', encoding='utf8') as fout:
        
        for key, value in groupby(lambda e: e[1], sorted(all_items, key=lambda e: (e[1]))).items():
            for i in range(len(value)):
                fout.write(f"{value[i][1]}={i+1},{value[i][0]}\n")

    print('done')
