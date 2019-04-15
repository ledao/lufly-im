# encoding=utf8
import os
import sys
from typing import List
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from tables import db, CharPhoneTable, CharShapeTable, WordPhoneTable
from tables import DelWordTable
from peewee import fn
from toolz.curried import pipe, map, groupby, filter, keymap, curry, take
from update_word_phones import split_sy, get_double_dict, full_to_double
from pypinyin import lazy_pinyin
import attr


@attr.s(frozen=True)
class Item(object):
    word = attr.ib(type=str,)
    priority = attr.ib(type=int, default=1)
    phones = attr.ib(type=str, default='')


@curry
def for_each(proc, eles):
    if type(eles) is dict:
        for (k, v) in eles.items():
            proc(k, v)
    else:
        for e in eles:
            print(e)


@curry
def cols_to_item(cols: List[str])->Item:
    if len(cols) == 1:
        return Item(word=cols[0])
    elif len(cols) == 2:
        return Item(word=cols[0], priority=int(cols[1]))
    else:
        raise RuntimeError("cols length not in [1,2]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"USAGE: python3 {sys.argv[0]} words.txt", file=sys.stderr)
        sys.exit(1)

    _, words_path = sys.argv

    exist_wordphones = set()
    exist_wordphones = pipe(WordPhoneTable.select(),
                            map(lambda e: e.word+e.phones),
                            set
                            )

    exist_wordphones = exist_wordphones | pipe(DelWordTable.select(),
                                               map(lambda e: e.word),
                                               set
                                               )

    with open(words_path, "r", encoding='utf8') as fin:
        ft_dict = get_double_dict()

        to_add_words = pipe(fin,
                            map(lambda e: e.strip().split('\t')),
                            filter(lambda e: len(e) in (1, 2)),
                            map(cols_to_item),
                            groupby(lambda e: e),
                            map(lambda e: (
                                e, map(lambda e: split_sy(e), lazy_pinyin(e.word)))),
                            map(lambda e: attr.evolve(e[0], phones=''.join(
                                full_to_double(e[1], ft_dict)))),
                            #filter(lambda e: not exist_word_phones(e[0], e[1])),
                            filter(lambda e: e.word + \
                                   e.phones not in exist_wordphones),
                            map(lambda e: WordPhoneTable(word=e.word, phones=e.phones,
                                                         priority=e.priority, updatedt=datetime.now())),
                            )

        with db.atomic():
            WordPhoneTable.bulk_create(to_add_words, batch_size=100)

    print('done')
