import os
import sys
from collections import defaultdict


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USAGE: python3 single_word_phones.py raw_single.txt filter_single.txt")
        sys.exit(1)
    _, raw_word_path, filter_word_path = sys.argv

    word_phones = defaultdict(list) 
    #with open(raw_word_path, 'r', encoding='utf8') as fin:
    with open(raw_word_path, 'r') as fin:
        for line in fin:
            if line.startswith("#"):
                continue
            line: str = line.strip()
            word, phones = line.split('\t')[:2]
            if len(word) < 2 or len(phones) != 2 * len(word) or phones in word_phones[word]: 
                continue
            word_phones[word].append(phones)
    print(len(word_phones))

    print(list(filter(lambda e: len(e[1]) > 1, word_phones.items())))

    with open(filter_word_path, 'w', encoding='utf8') as fout:
        for word, phones in sorted(word_phones.items(), key=lambda e: e[0]):
            for phone in phones:
                fout.write(f"{word}\t{phone}\n")
    pass