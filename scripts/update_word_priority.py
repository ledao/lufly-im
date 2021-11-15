import sys, os
from typing import List
from toolz.curried import pipe, map, concat, filter, groupby, valmap
from tables import db, WordPhoneTable, CharFreqTable
from segger import Segger


def mean(lst: List[int]) -> int:
    if len(lst) == 0:
        return 1
    else:
        return int(sum(lst) / len(lst))


def get_priority(lst: List[int]) -> int:
    weights = {
        2: (0.8, 0.2),
        3: (0.7, 0.2, 0.1),
        4: (0.7, 0.1, 0.1, 0.1),
        5: (0.6, 0.1, 0.1, 0.1, 0.1),
    }
    size = len(lst)
    if size not in (2, 3, 4, 5):
        raise (f"only 2, 3, 4, 5 length words supported")
    priority = 0
    for i in range(size):
        priority += int(weights[size][i] * lst[i])

    return priority


if __name__ == "__main__":
    if len(sys.argv) != 1:
        print(f"Usage: python3 {sys.argv[0]} ", file=sys.stderr)
        sys.exit(1)
    #_, sents_path = sys.argv

    #exist_words = pipe(WordPhoneTable.select(), map(lambda e: e.word), set)
    #seg = Segger(exist_words, 5)

    #with open(sents_path, 'r', encoding='utf8') as fin:
    #    word_freq = pipe(
    #        fin, map(lambda e: e.strip().replace(" ", "").replace("\t", "")),
    #        filter(lambda e: e != "" and not e.startswith("#")),
    #        map(lambda e: seg.cut(e)), concat, groupby(lambda e: e),
    #        valmap(lambda e: len(e)), dict)

    chars_freq = {}
    for item in CharFreqTable.select():
        if item.char in chars_freq:
            raise ("duplicated " + item.char)
        chars_freq[item.char] = item.freq

    index = 0
    tosave_items = []
    for item in WordPhoneTable.select().where(WordPhoneTable.priority <= 0):
        index += 1
        if index == 10000:
            print(item)
            index = 0
            with db.atomic():
                WordPhoneTable.bulk_update(tosave_items,
                                           [WordPhoneTable.priority],
                                           batch_size=200)
            tosave_items.clear()

        word = item.word
        #if word in word_freq:
        #    freq = word_freq[word]
        #else:
        #    freq = 1

        freqs = [(chars_freq[word[e]] if word[e] in chars_freq else 10)
                 for e in range(len(word))]
        # print(freqs)
        priority = get_priority(freqs)
        item.priority = priority
        tosave_items.append(item)
        #if freq == item.priority:
        #    continue
        #else:
        #    item.priority = freq
        #    item.save()
    print('done')