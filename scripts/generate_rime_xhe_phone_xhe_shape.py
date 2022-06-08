# encoding=utf8
import sys
import time

from common import *
from tables import *

if __name__ == "__main__":

    if len(sys.argv) != 2 or sys.argv[1] not in ['ff', 'fb']:
        print(f"USAGE: python3 {sys.argv[0]} mode[ff|fb] ")
        sys.exit(1)

    mode = sys.argv[1]
    fname, output_dir = sys.argv[0], "rime_xhe_" + mode

    if not Path(output_dir).exists():
        os.makedirs(output_dir)
    version = int(time.time())

    with open(output_dir + "/luyinxing.schema.yaml", 'w', encoding='utf8') as fout:
        fout.write(f"# 鹭音形输入方案\n")
        fout.write("# encoding: utf-8\n")
        fout.write("# 机器生成，请勿修改\n")
        fout.write("\n")

        fout.write("\nschema:\n")
        fout.write("  schema_id: luyinxing\n")
        fout.write("  name: 鹭音形输入方案\n")
        fout.write(f'  version: "{version}"\n')
        fout.write(f'  author: \n')
        fout.write(f'    - ledao <790717479@qq.com> \n')
        fout.write(f'  description: |\n')
        fout.write(f'     一款简单、舒服的音形输入方案\n')

        fout.write("\nswitches:\n")
        fout.write("  - name: ascii_mode \n")
        fout.write("    reset: 0\n")
        fout.write("  - name: full_shape\n")
        fout.write("  - name: zh_simp\n")
        fout.write("    reset: 1\n")
        fout.write("    states: [ 繁, 简 ]\n")
        fout.write("  - name: ascii_punct\n")
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
        #fout.write("  alphabet: ';zyxwvutsrqponmlkjihgfedcba'\n")
        fout.write("  alphabet: ';zyxwvutsrqponmlkjihgfedcba'\n")
        fout.write("  initials: 'abcdefghijklmnopqrstuvwxyz;'\n")
        #fout.write("  finals: '/'\n")
        fout.write("  auto_select: true\n")
        fout.write(
            "  auto_select_pattern: ^\w{4}$|^\w{5}$|^\w{6}$|^\w{7}$|^\w{8}$|^\w{9}$|^\w{10}$|^\w{11}$|^\w{12}$|^\w{13}$|^\w{14}$|^\w{15}$|^\w{16}$|^\w{17}$|^\w{18}$\n")

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
        fout.write("    - {accept: dollar, send: 2, when: composing}\n")
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
        fout.write("  page_size: 5\n")

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
        fout.write("# 鹭音形输入法码表\n")
        fout.write("# 机器生成，请勿修改\n")

        fout.write("\n---\n")
        fout.write("name: luyinxing\n")
        fout.write(f'version: "{version}"\n')
        # fout.write(f'sort: original\n')
        fout.write(f'sort: by_weight\n')
        fout.write(f'use_preset_vocabulary: false\n')
        fout.write('columns:\n')
        fout.write('  - text\n')
        fout.write('  - code\n')

        # fout.write('encoder:\n')
        # fout.write('  exclude_patterns:\n')
        # fout.write("    - '^z.*$'\n")
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 2\n')
        # fout.write('      formula: "AaAbBaBbAcBc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 3\n')
        # fout.write('      formula: "AaAbBaBbCaCbAcCc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 4\n')
        # fout.write('      formula: "AaAbBaBbCaCbDaDbAcDc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 5\n')
        # fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbAcEc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 6\n')
        # fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbAcFc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 7\n')
        # fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbAcGc"\n')
        # fout.write('  rules:\n')
        # fout.write('    - length_equal: 8\n')
        # fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbHaHbAcHc"\n')

        fout.write("...\n")

        fout.write("\n# 单字\n")

        one_hit_char_items = generate_one_hit_char()
        top_single_chars_items = generate_topest_char(char_to_phones)
        for item in one_hit_char_items:
            fout.write(f"{item}\n")
        # for item in top_single_chars_items:
        #     fout.write(f"{item}\n")

        for item in generate_single_chars(char_to_shape):
            fout.write(f"{item[0:-2]}\n")
            fout.write(f"{item}\n")

        fout.write("\n# 词语\n")

        # high_freq_words, low_freq_words = generate_simpler_words(char_to_shape, 100, 2000)
        # for item in high_freq_words:
        #     fout.write(f"{item}\n")
        # for item in low_freq_words:
        #     fout.write(f"{item}\n")

        for item in generate_full_words(char_to_shape):
            fout.write(f"{item[0:-2]}\n")
            fout.write(f"{item}\n")

    with open(output_dir + "/luyinxing.custom.yaml", 'w', encoding='utf8') as fout:
        fout.write("# luyinxing custom config\n")
        fout.write("# encoding: utf-8\n")
        fout.write("# \n")
        fout.write("# 鹭音形输入方案\n")
        fout.write("# 机器生成，请勿修改\n")

        fout.write(f"patch:\n")
        fout.write(f"  punctuator/half_shape:\n")
        fout.write(f"    '/': '、'\n")
