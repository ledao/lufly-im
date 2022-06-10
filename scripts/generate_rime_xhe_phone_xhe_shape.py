# encoding=utf8
import sys
import time

from common import *
from tables import *

if __name__ == "__main__":

    fname, output_dir = sys.argv[0], "rime_xhe"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)
    version = datetime.datetime.now().strftime('%Y%m%d.%H%M%S')

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
        fout.write(f'     简单舒适音形方案\n')

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
        fout.write("  filters:\n")
        fout.write("    - simplifier\n")
        fout.write("    - uniquifier\n")

        fout.write("\n")

        fout.write("speller:\n")
        fout.write("  alphabet: ';zyxwvutsrqponmlkjihgfedcba'\n")
        fout.write("  initials: 'abcdefghijklmnopqrstuvwxyz;'\n")
        fout.write("  auto_select: true\n")
        fout.write(
            "  auto_select_pattern: ^\w{6}$|^\w{8}$|^\w{10}$|^\w{12}$|^\w{14}$|^\w{16}$|^\w{18}$\n")

        fout.write("\n")

        fout.write("translator:\n")
        fout.write("  dictionary: luyinxing\n")
        fout.write("  enable_charset_filter: false\n")
        fout.write("  enable_sentence: false\n")
        fout.write("  enable_completion: true\n")
        fout.write("  enable_user_dict: true\n")
        fout.write("  enable_encoder: true\n")
        fout.write("  encode_commit_history: true\n")
        fout.write("  max_phrase_length: 4\n")

        fout.write("\n\n")

        fout.write("punctuator:\n")
        fout.write("  import_preset: default\n")

        fout.write("\n")

        fout.write("key_binder:\n")
        fout.write("  import_preset: default\n")
        fout.write("  bindings:\n")
        # fout.write("    - {accept: bracketleft, send: Page_Up, when: paging} # [上翻页\n")
        # fout.write("    - {accept: bracketright, send: Page_Down, when: has_menu} # ]下翻页\n")
        fout.write("    - {accept: comma, send: comma, when: paging} #注销逗号翻页\n")
        fout.write("    - {accept: period, send: period, when: has_menu} #注销句号翻页\n")
        fout.write("    - {accept: semicolon, send: 2, when: has_menu} #分号次选\n")
        fout.write("    - {accept: apostrophe, send: 3, when: has_menu} #单引号3选\n")
        fout.write("    - {accept: bracketleft, send: 4, when: has_menu} #单引号4选\n")
        fout.write("    - {accept: bracketright, send: 5, when: has_menu} #单引号5选\n")
        fout.write("    - {accept: dollar, send: 2, when: composing}\n")
        fout.write("    - {accept: Release+dollar, send: period, when: composing}\n")
        fout.write("    - {accept: Release+period, send: period, when: composing}\n")
        fout.write("    - {accept: bar, send: 2, when: composing}\n")
        fout.write("    - {accept: Release+bar, send: comma, when: composing}\n")
        fout.write("    - {accept: Release+comma, send: comma, when: composing}\n")
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
        fout.write(f'sort: original\n')
        fout.write(f'use_preset_vocabulary: false\n') #是否使用预设词表

        fout.write('columns:\n')
        fout.write('  - text\n')
        fout.write('  - code\n')

        fout.write('encoder:\n')
        # fout.write('  exclude_patterns:\n')
        # fout.write("    - '^z.*$'\n")
        fout.write('  rules:\n')
        fout.write('    - length_equal: 2\n')
        fout.write('      formula: "AaAbBaBbAcBc"\n')
        fout.write('    - length_equal: 3\n')
        fout.write('      formula: "AaAbBaBbCaCbAcCc"\n')
        fout.write('    - length_equal: 4\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbAcDc"\n')
        fout.write('    - length_equal: 5\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbAcEc"\n')
        fout.write('    - length_equal: 6\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbAcFc"\n')
        fout.write('    - length_equal: 7\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbAcGc"\n')
        fout.write('    - length_equal: 8\n')
        fout.write('      formula: "AaAbBaBbCaCbDaDbEaEbFaFbGaGbHaHbAcHc"\n')

        fout.write("...\n")

        fout.write("\n# 单字\n")

        one_hit_char_items = generate_one_hit_char()
        top_single_chars_items = generate_topest_char(char_to_phones)
        for item in one_hit_char_items:
            fout.write(f"{item.decode}\t{item.encode}\n")
        for item in top_single_chars_items:
            fout.write(f"{item.decode}\t{item.encode}\n")

        for item in generate_single_chars(char_to_shape):
            fout.write(f"{item.decode}\t{item.encode[:-2]}\n")
            fout.write(f"{item.decode}\t{item.encode[:-1]}\n")
            fout.write(f"{item.decode}\t{item.encode}\n")

        fout.write("\n# 词语\n")

        for item in generate_full_words(char_to_shape):
            fout.write(f"{item.decode}\t{item.encode[0:-2]}\n")
            fout.write(f"{item.decode}\t{item.encode[0:-1]}\n")
            fout.write(f"{item.decode}\t{item.encode}\n")

    with open(output_dir + "/luyinxing.custom.yaml", 'w', encoding='utf8') as fout:
        fout.write("# luyinxing custom config\n")
        fout.write("# encoding: utf-8\n")
        fout.write("# \n")
        fout.write("# 鹭音形输入方案\n")
        fout.write("# 机器生成，请勿修改\n")

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

    with open(output_dir + "/weasel.custom.yaml", 'w', encoding='utf8') as fout:
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

