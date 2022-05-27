# encoding=utf8
import os, sys
from dataclasses import dataclass
from typing import List, Set

from tables import YeFengWordTable, db, CharLuShapeTable, WordPhoneTable
from datetime import datetime


@dataclass
class Yefeng(object):
    word: str
    pinyin: str
    freq: int


def get_yefeng_words(filepath: str, exists_words: Set[str]) -> List[Yefeng]:
    words: List[Yefeng] = []
    with open(words_path, "r", encoding='utf8') as fin:
        for line in fin:
            cols = line.strip().split("\t")
            if len(cols) != 3: continue
            pys = cols[0].replace("'", " ")
            word = cols[1]
            freq = int(cols[2])
            if len(word) < 2 or len(word) > 7: continue
            if freq < 100 and len(word) < 4: continue
            if word in exists_words: continue
            if word.startswith("的"): continue
            if word.startswith("第"): continue
            if word.startswith("三百"): continue
            if word.endswith("的"): continue
            if '九' in word: continue
            if '的' in word: continue
            if '了' in word: continue


            words.append(Yefeng(pinyin=pys, word=word, freq=freq))
    return words


def get_words() -> Set[str]:
    result = set()
    for item in WordPhoneTable.select():
        result.add(item.word)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"USAGE: python3 {sys.argv[0]} yefeng.txt", file=sys.stderr)
        sys.exit(1)

    exists_words = get_words()
    _, words_path = sys.argv
    yefeng_words = get_yefeng_words(words_path, exists_words)
    print(yefeng_words)
    print(len(yefeng_words))

    with open("toadd_words.txt", 'w', encoding='utf8') as fout:
        yefeng_words = sorted(yefeng_words, key=lambda e: e.word)
        for yefeng in yefeng_words:
            fout.write(f"{yefeng.word} {yefeng.freq} {yefeng.pinyin}\n")

    print('done')
