# encoding=utf8
import os
import sys
from pathlib import Path
from collections import defaultdict
from tables import *
from peewee import fn
from toolz.curried import *
from datetime import datetime
from common import *


if __name__ == "__main__":

    if len(sys.argv) != 2 or sys.argv[1] not in ['ff', 'fb']:
        print(f"USAGE: python3 {sys.argv[0]} mode[ff|fb] ")
        sys.exit(1)

    mode = sys.argv[1]
    fname, output_dir = sys.argv[0], "rime_xhe_" + mode

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


    char_to_phones = get_char_to_xhe_phones()
    print(f"total {len(char_to_phones)} char phones")

    char_to_shape = get_char_to_xhe_shapes()
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

        one_hit_char_items = generate_one_hit_char(0)
        top_single_chars_items = generate_topest_char(char_to_phones, 0)
        for item in one_hit_char_items.items():
            #fout.write(f"{item[0]}\t{item[1]}\n")
            fout.write(f"{item[0]}\n")
        for item in top_single_chars_items.items():
            #fout.write(f"{item[0]}\t{item[1]}\n")
            fout.write(f"{item[0]}\n")

        for item in CharPhoneTable.select().order_by(CharPhoneTable.priority.desc()):
            if item.char in char_to_shape:
                fout.write(f"{item.char}\t{item.xhe}\n")
                for shape in char_to_shape[item.char]:
                    fout.write(f"{item.char}\t{item.xhe}{shape}\n")
            else:
                fout.write(f"{item.char}\t{item.xhe}\n")

        fout.write("\n# 词语\n")

        del_words = get_del_words()

        for item in  WordPhoneTable.select().where(WordPhoneTable.priority >= 1).order_by(fn.LENGTH(WordPhoneTable.word),
                                             WordPhoneTable.priority.desc()):
            if item.word in del_words:
                continue
            if item.word[0] in char_to_shape and item.word[-1] in char_to_shape:
                fout.write(f"{item.word}\t{item.xhe}\n")
                for shape_first in char_to_shape[item.word[0]]:
                    for shape_last in char_to_shape[item.word[-1]]:
                        if mode == 'ff':
                            fout.write(f"{item.word}\t{item.xhe}{shape_first[0]}{shape_last[0]}\n") 
                        else:
                            fout.write(f"{item.word}\t{item.xhe}{shape_first[0]}{shape_last[-1]}\n") 
            else:
                pass
