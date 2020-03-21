# encoding=utf8
import os
import sys
from pathlib import Path
from collections import defaultdict
from tables import CharPhoneTable, CharShapeTable, WordPhoneTable, EngWordTable
from tables import DelWordTable
from peewee import fn
from toolz.curried import pipe, map, filter, curry, reduceby, valmap, groupby
from datetime import datetime


if __name__ == "__main__":

    if len(sys.argv) != 1:
        print(f"USAGE: python3 {sys.argv[0]} ")
        sys.exit(1)

    fname, output_dir = sys.argv[0], "rime_xhe_ff"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)
    now = datetime.now()
    
    with open(output_dir + "/luyinxing.schema.yaml", 'w', encoding='utf8') as fout:
        fout.write(f"# luyinxing 输入法\n")
        fout.write("# encoding: utf-8\n")
        fout.write("# 机器生成，请勿修改\n")
        fout.write("\n")

        fout.write("\nschema:\n")
        fout.write("  schema_id: luyinxing\n")
        fout.write("  name: Lu音形输入方案\n")
        fout.write(f'  version: "{now.year}.{now.month}.{now.day}"\n')
        fout.write(f'  author: \n')
        fout.write(f'    - ledao/xiuyingbala <790717479@qq.com> \n')
        fout.write(f'  description: |\n')
        fout.write(f'     一款简单、舒服的音形输入方案\n')
        
        fout.write("\nswitches:\n")
        fout.write("  - name: ascii_mode \n")
        fout.write("    reset: 0\n")
        # fout.write("    states: [ 中文, 英文 ]\n")
        fout.write("  - name: full_shape\n")
        # fout.write("    states: [ 半角, 全角 ]\n")
        fout.write("  - name: zh_simp\n")
        fout.write("    reset: 1\n")
        fout.write("    states: [ 繁, 简 ]\n")
        fout.write("  - name: ascii_punct\n")
        # fout.write("    states: [ 。，, ．， ]\n")
        fout.write("    reset: 0\n")
 
        fout.write("\nengine:\n")
        fout.write("  processors:\n")
        fout.write("    - ascii_composer\n")
        fout.write("    - recognizer\n")
        fout.write("    - key_binder\n")
        fout.write("    - speller\n")
        fout.write("    - punctuator\n")
        fout.write("    - selector\n")
        fout.write("    - navigator\n")
        fout.write("    - express_editor\n")
        fout.write("  segmentors:\n")
        fout.write("    - ascii_segmentor\n")
        fout.write("    - matcher\n")
        fout.write("    - abc_segmentor\n")
        fout.write("    - punct_segmentor\n")
        fout.write("    - fallback_segmentor\n")
        fout.write("  translators:\n")
        fout.write("    - punct_translator\n")
        fout.write("    - table_translator\n")
        # fout.write("    - reverse_lookup_translator\n")
        # fout.write("    - history_translator@history\n")
        fout.write("  filters:\n")
        fout.write("    - simplifier\n")
        fout.write("    - uniquifier\n")

        fout.write("\n")

        fout.write("speller:\n")
        fout.write("  alphabet: '/;zyxwvutsrqponmlkjihgfedcba'\n")
        fout.write("  initials: 'abcdefghijklmnopqrstuvwxyz;'\n")
        fout.write("  finals: '/'\n")
        # fout.write("  max_code_length: 4\n")
        fout.write("  auto_select: true\n")
        fout.write("  auto_select_pattern: ^\w{4}$|^\w{5}$|^\w{6}$|^\w{7}$|^\w{8}$|^\w{9}$|^\w{10}$|^\w{11}$|^\w{12}$|^\w{13}$|^\w{14}$|^\w{15}$|^\w{16}$|^\w{17}$|^\w{18}$\n")
        # fout.write("  auto_clear: max_length\n")

        fout.write("\n")
        
        fout.write("translator:\n")
        fout.write("  dictionary: luyinxing\n")
        fout.write("  enable_charset_filter: false\n")
        fout.write("  enable_sentence: false\n")
        fout.write("  enable_completion: true\n")
        fout.write("  enable_user_dict: true\n")

        fout.write("\n")
 
        # fout.write("history:\n")
        # fout.write("  input: ;f\n")
        # fout.write("  size: 1\n")
        # fout.write("  initial_quality: 1\n")
        
        fout.write("\n")
        
        fout.write("punctuator:\n")
        fout.write("  import_preset: default\n")

        fout.write("\n")
        
        fout.write("key_binder:\n")
        fout.write("  import_preset: default\n")
        fout.write("  bindings:\n")
        fout.write("    - {accept: bracketleft, send: Page_Up, when: paging} # [上翻页\n")
        fout.write("    - {accept: bracketright, send: Page_Down, when: has_menu} # ]下翻页\n")
        fout.write("    - {accept: comma, send: comma, when: paging} #注销逗号翻页\n")
        fout.write("    - {accept: period, send: period, when: has_menu} #注销句号翻页\n")
        fout.write("    - {accept: semicolon, send: 2, when: has_menu} #分号次选\n")
        fout.write("    - {accept:  dollar, send: 2, when: composing}\n")
        fout.write("    - {accept: Release+dollar, send: period, when: composing}\n")
        fout.write("    - {accept: Release+period, send: period, when: composing}\n")
        fout.write("    - {accept: bar, send: 2, when: composing}\n")
        fout.write("    - {accept: Release+bar, send: comma, when: composing}\n")
        fout.write("    - {accept: Release+comma, send: comma, when: composing}\n")
        fout.write("\n")
        fout.write('    - {accept: "Tab", send: Page_Down, when: has_menu}\n')
        fout.write('    - {accept: "Tab", send: Escape, when: composing}\n')
        fout.write('    - {accept: "Caps_Lock", send: Escape, when: composing}\n')
        fout.write('    - {accept: "Shift_R", send: Escape, when: composing}\n')
        fout.write('    - {accept: "Shift+space", toggle: full_shape, when: always} #切换全半角\n')
        fout.write('    - {accept: "Control+period", toggle: ascii_punct, when: always}\n')

        fout.write("\n")
        
        fout.write("menu:\n")
        fout.write("  page_size: 6\n")

        fout.write("style:\n")
        fout.write("  horizontal: true\n")


    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.xhe)),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]),
                          dict
                          )
    print(f"total {len(char_to_phones)} char phones")

    char_to_shape = pipe(CharShapeTable.select(),
                         map(lambda e: (e.char, e.shapes)),
                         reduceby(lambda e: e[0], lambda e1, e2: e1),
                         valmap(lambda e: e[1]),
                         dict
                         )
    print(f"total {len(char_to_shape)} char shapes")

    with open(output_dir + "/luyinxing.dict.yaml", 'w', encoding='utf8') as fout:
        fout.write("# luyinxing dictionary\n")
        fout.write("# encoding: utf-8\n")
        fout.write("# \n")
        fout.write("# lu音形输入法码表\n")
        fout.write("# 机器生成，请勿修改\n")

        fout.write("\n---\n")
        fout.write("name: luyinxing\n")
        fout.write(f'version: "{now.hour}"\n')
        fout.write(f'sort: original\n')
        # fout.write(f'sort: by_weight\n')
        fout.write(f'use_preset_vocabulary: true\n')
        fout.write('columns:\n')
        fout.write('  - text\n')
        fout.write('  - code\n')
        # fout.write('  - stem\n')

        fout.write('encoder:\n')
        fout.write('  exclude_patterns:\n')
        fout.write("    - '^z.*$'\n")
        fout.write('  rules:\n')
        fout.write('    - length_equal: 2\n')
        fout.write('      formula: "AaAbBaBbAcBc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 3\n')
        fout.write('      formula: "AaAbBaBbCaCbAcCc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 4\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbAcDc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 5\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbAcEc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 6\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbAcFc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 7\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbAcGc"\n')
        fout.write('  rules:\n')
        fout.write('    - length_equal: 8\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbHaHbAcHc"\n')

        fout.write("...\n")
        
        fout.write("\n# 单字\n")

        one_hit_char_items = generate_one_hit_char(10000000)
        top_single_chars_items = generate_topest_char(char_to_phones, 9000000)
        for item in one_hit_char_items.items():
            #fout.write(f"{item[0]}\t{item[1]}\n")
            fout.write(f"{item[0]}\n")
        for item in top_single_chars_items.items():
            #fout.write(f"{item[0]}\t{item[1]}\n")
            fout.write(f"{item[0]}\n")

        pipe(
            CharPhoneTable.select().order_by(CharPhoneTable.priority.desc()),
            filter(lambda e: e.char in char_to_shape),
            #map(lambda e: f"{e.char}\t{e.xhe+char_to_shape[e.char]}\t{e.priority}"),
            map(lambda e: (f"{e.char}\t{e.xhe}", f"{e.char}\t{e.xhe}{char_to_shape[e.char]}")),
            for_each(lambda e: fout.write(e[0]+'\n' + e[1] + '\n')),
        )

        fout.write("\n# 词语\n")

        del_words = pipe(
            DelWordTable.select(),
            map(lambda e: e.word),
            set
        )
        
        pipe(
            WordPhoneTable.select().where(WordPhoneTable.priority >= 1).order_by(fn.LENGTH(WordPhoneTable.word),
                                             WordPhoneTable.priority.desc()),
            filter(lambda e: e.word not in del_words),
            map(lambda e: (f'{e.word}\t{e.xhe}', e.word[0], e.word[-1], e.priority)),
            filter(lambda e: e[1] in char_to_shape and e[2] in char_to_shape),
            #map(lambda e: f'{e[0]}{char_to_shape[e[1]][0]}{char_to_shape[e[2]][0]}\t{e[3]}'),
            map(lambda e: (f'{e[0]}', f'{e[0]}{char_to_shape[e[1]][0]}{char_to_shape[e[2]][0]}')),
            for_each(lambda e: fout.write(e[0]+'\n' + e[1] + '\n'))
        )



        pass    
    # with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout:
    #     fout.write("---config@码表分类=主码-3\n")
    #     fout.write("---config@允许编辑=否\n")
    #     fout.write(f"---config@码表别名=系统英文\n")
    #     pipe(EngWordTable.select().where(EngWordTable.priority > 0).order_by(fn.LENGTH(EngWordTable.word), EngWordTable.priority),
    #          filter(lambda e: is_all_alpha(e.word)),
    #          map(lambda e: e.word+'\t'+e.word+"#序10000"),
    #          for_each(lambda e: fout.write(e+'\n')),
    #          )

    # print('done')
