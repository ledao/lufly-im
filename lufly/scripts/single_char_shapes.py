import os
import sys
from collections import defaultdict


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USAGE: python3 single_char_phones.py raw_single.txt filter_single.txt")
        sys.exit(1)
    _, raw_char_path, filter_char_path = sys.argv

    char_phones = defaultdict(list) 
    with open(raw_char_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line: str = line.strip()
            char, phones = line.split('\t')
            if len(phones) < 4 or phones[:4] in char_phones[char]: 
                continue
            char_phones[char].append(phones[:4])
    print(len(char_phones))

    with open(filter_char_path, 'w', encoding='utf8') as fout:
        for char, phones in sorted(char_phones.items(), key=lambda e: e[0]):
            for phone in phones:
                fout.write(f"{char}\t{phone[2:]}\n")
    pass