import sys

from common import get_exists_words, meanless_word


def load_shouxin_export_words(path: str, sikp_words_path: str, out_path):
    all_words = []
    exists_words = get_exists_words()

    with open(sikp_words_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == '': continue
            exists_words.add(line.split(" ")[0])

    with open(path, 'r', encoding='utf16') as fin:
        for line in fin:
            line = line.strip()
            if line == '' or line.startswith("#"):
                continue
            
            cols = line.split("\t")
            if len(cols) != 3:
                print(f"error line: {line}")
                continue

            word = cols[0]
            if meanless_word(word):
                continue
            if word in exists_words:
                continue
            exists_words.add(word)
            pinyin = cols[1].replace("'", " ")
            
            all_words.append((word, pinyin))

    all_words = sorted(all_words, key=lambda e: -len(e))
    with open(out_path, 'w', encoding='utf8') as fout:
        for word_pinyin in all_words:
            word = word_pinyin[0]
            pinyin = word_pinyin[1]
            fout.write(f"{word} {pinyin}\n")


def main():
    filepath = sys.argv[1]
    skip_words_path = sys.argv[2]
    load_shouxin_export_words(filepath, skip_words_path, "to_add_shouxin_words.txt")

    pass


if __name__ == '__main__':
    main()