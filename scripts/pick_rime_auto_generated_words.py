import sys
from typing import List

from tables import WordPhoneTable


def load_rime_export_words(path: str, sikp_words_path: str, out_path) -> List[str]:
    all_words = []
    exists_words = set()
    for item in WordPhoneTable.select():
        exists_words.add(item.word)

    with open(sikp_words_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == '': continue
            exists_words.add(line)

    with open(path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if "enc" not in line:
                continue
            if line.startswith("#"):
                continue
            line = line.split("\t")[0]
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
    skip_words_path = sys.argv[2]
    items = load_rime_export_words(filepath, skip_words_path, "to_add_rime_words.txt")

    pass


if __name__ == '__main__':
    main()