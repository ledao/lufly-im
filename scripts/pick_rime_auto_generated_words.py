import sys
from typing import List

from tables import WordPhoneTable


def load_rime_export_words(path: str, out_path) -> List[str]:
    all_words = []
    exists_words = set()
    for item in WordPhoneTable.select():
        exists_words.add(item.word)
    with open(path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if "enc" not in line:
                continue
            line = line.split("\t")[0]
            if line.startswith("把"):
                continue
            if line.startswith("了"):
                continue
            if line.startswith("在"):
                continue
            if line.startswith("的"):
                continue
            if line.startswith("不"):
                continue
            if line.startswith("等"):
                continue
            if line.startswith("到"):
                continue
            if line.startswith("但"):
                continue
            if line.startswith("对"):
                continue
            if line.startswith("跟"):
                continue
            if line.startswith("就"):
                continue
            if line.startswith("是"):
                continue
            if line.startswith("我"):
                continue
            if line.startswith("为"):
                continue
            if line.startswith("要"):
                continue
            if line.startswith("被"):
                continue
            if line.startswith("否"):
                continue
            if line.startswith("和"):
                continue
            if line.startswith("克"):
                continue

            if line.endswith("的"):
                continue
            if line.endswith("在"):
                continue
            if line.endswith("是"):
                continue
            if line.endswith("了"):
                continue
            if line.endswith("在"):
                continue
            if line.endswith("有"):
                continue
            if line.endswith("不"):
                continue
            if line.endswith("就"):
                continue
            if line.endswith("么"):
                continue
            if line.endswith("有"):
                continue
            if line.endswith("都"):
                continue
            if line.endswith("对"):
                continue
            if line.endswith("很"):
                continue
            if line.endswith("想"):
                continue

            cols = line.split('\t')
            if len(cols) <= 0:
                continue
            word = cols[0]
            if len(word) > 3:
                continue
            if word in exists_words:
                continue
            exists_words.add(word)
            all_words.append(word)

    all_words = sorted(all_words, key=lambda e: -len(e))
    exists_words = set()
    with open(out_path, 'w', encoding='utf8') as fout:
        for word in all_words:
            for i in range(len(word)):
                this_word = word[:i + 1]
                if this_word not in exists_words:
                    exists_words.add(this_word)
            fout.write(f"{word}\n")




def main():
    filepath = sys.argv[1]
    items = load_rime_export_words(filepath, "to_add_rime_words.txt")

    pass


if __name__ == '__main__':
    main()