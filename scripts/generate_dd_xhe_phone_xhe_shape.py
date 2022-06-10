# encoding=utf8
import shutil
import sys

from common import *
from tables import *

if __name__ == "__main__":

    if len(sys.argv) != 1:
        print(f"USAGE: python3 {sys.argv[0]}")
        sys.exit(1)

    file_name, output_dir = sys.argv[0], "xhe_phone_xhe_shape"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    char_to_shape = get_char_to_xhe_shapes()
    print(f"total {len(char_to_shape)} char shapes")

    char_to_phones = get_char_to_xhe_phones()
    print(f"total {len(char_to_phones)} char phones")

    sys_top_chars_data = f"{output_dir}/sys_top_chars_data.txt"
    with open(sys_top_chars_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-1\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=简码单字\n")
        for item in generate_one_hit_char():
            fout.write(f"{item.decode}\t{item.encode}#序{90000}\n")
        for item in generate_topest_char(char_to_phones):
            fout.write(f"{item.decode}\t{item.encode}#序{80000}\n")

    sys_single_char_data = f"{output_dir}/sys_single_char_data.txt"
    with open(sys_single_char_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-2\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统单字\n")
        for item in generate_single_chars(char_to_shape):
            fout.write(f"{item.decode}\t{item.encode}#序{70000}\n")

    high_freq_words, low_freq_words = generate_simpler_words(char_to_shape, 100, 2000)
    sys_high_freq_word_data = f"{output_dir}/sys_high_word_data.txt"
    with open(sys_high_freq_word_data, 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-3\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=高频简词\n")
        for item in high_freq_words:
            fout.write(f"{item.decode}\t{item.encode}#序{75000}\n")
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
        for item in generate_full_words(char_to_shape):
            fout.write(f"{item.decode}\t{item.encode}#序{60000}\n")

    with open(f'{output_dir}/sys_eng_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-6\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统英文\n")
        for item in generate_eng():
            fout.write(f"{item}#序{50000}\n")

    with open(f'{output_dir}/sys_simpler_data.txt', 'w',
              encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-7\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=系统简码\n")
        for item in generate_simpler():
            fout.write(f"{item}\t#序{40000}\n")

    with open(f'{output_dir}/sys_cmd_data.txt', 'w', encoding='utf8') as fout:
        fout.write("---config@码表分类=主码-8\n")
        fout.write("---config@允许编辑=是\n")
        fout.write(f"---config@码表别名=直通车\n")
        cmds = get_dd_cmds()
        for cmd in cmds:
            fout.write(f"{cmd}\n")

    dd_dir = 'lufly/win-dd/lufly-im-v4/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')
