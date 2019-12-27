import sys, os
from typing import List
from toolz.curried import pipe, map, concat, filter, groupby, valmap
from tables import db, WordPhoneTable, CharFreqTable
from segger import Segger


def mean(lst: List[int]) -> int:
    if len(lst) == 0:
        return 1
    else:
        return int(sum(lst)/len(lst))
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} sents.txt", file=sys.stderr)
        sys.exit(1)
    _, sents_path = sys.argv

    exist_words = pipe(WordPhoneTable.select(),
        map(lambda e: e.word),
        set
    )
    seg = Segger(exist_words, 5)

    with open(sents_path, 'r', encoding='utf8') as fin:
        word_freq = pipe(fin,
            map(lambda e: e.strip().replace(" ", "").replace("\t", "")),
            filter(lambda e: e != "" and not e.startswith("#")),
            map(lambda e: seg.cut(e)),
            concat,
            groupby(lambda e: e),
            valmap(lambda e: len(e)),
            dict
        )

    index = 0
    for item in WordPhoneTable.select():
        index += 1
        if index == 1000:
            print(item)
            index = 0
        word = item.word
        if word in word_freq:
            freq = word_freq[word]
        else:
            freq = 1
        if freq == item.priority:
            continue
        else:
            item.priority = freq
            item.save()
    print('done')