# encoding=utf8
import os
import sys
import re
from typing import List
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from tables import db, CharPhoneTable, CharShapeTable, WordPhoneTable
from tables import DelWordTable
from peewee import fn
from toolz.curried import pipe, map, groupby, filter, keymap, curry, take
from common import split_sy, get_double_dict, full_to_double
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
            proc(e)


@curry
def cols_to_item(cols: List[str])->Item:
    if len(cols) == 1:
        return Item(word=cols[0])
    elif len(cols) == 2:
        return Item(word=cols[0], priority=int(cols[1]))
    else:
        raise RuntimeError("cols length not in [1,2]")


def contain_alpha(word: str) -> bool:
    for c in word:
        if c.lower() in "abcdefghijklmnopqrstuvwxyz":
            return True

    return False


def contain_symbols(word: str) -> bool:
    if re.match('[1234567890’!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~，。！@#$%^&*………_+}{}]+', word) is None:
        return False
    else:
        return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"USAGE: python3 {sys.argv[0]} words.txt", file=sys.stderr)
        sys.exit(1)

    _, words_path = sys.argv

    exist_words = set()
    exist_words = pipe(WordPhoneTable.select(),
                       map(lambda e: e.word),
                       set
                       )

    exist_words = exist_words | pipe(DelWordTable.select(),
                                     map(lambda e: e.word),
                                     set
                                     )

    with open(words_path, "r", encoding='utf8') as fin:

        #FIXME: bug to fix, we have more phone type now.
        ft_dict = get_double_dict()

        to_add_words = pipe(fin,
                            map(lambda e: e.strip().split('\t')),
                            filter(lambda e: len(e) in (1, 2)),
                            filter(lambda e: len(e[0]) <= 5),
                            filter(lambda e: not contain_alpha(
                                e[0]) and not contain_symbols(e[0])),
                            filter(lambda e: e[0] not in exist_words),
                            map(cols_to_item),
                            map(lambda e: (
                                e, map(lambda e: split_sy(e), lazy_pinyin(e.word)))),
                            map(lambda e: attr.evolve(e[0], phones=''.join(
                                full_to_double(e[1], ft_dict)))),
                            map(lambda e: WordPhoneTable(word=e.word, phones=e.phones,
                                                         priority=e.priority, updatedt=datetime.now())),
                            )

        with db.atomic():
            WordPhoneTable.bulk_create(to_add_words, batch_size=100)

    print('done')
