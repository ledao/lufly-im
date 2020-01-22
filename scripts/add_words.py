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
from common import get_full_to_xhe_transformer, get_full_to_zrm_transformmer, get_full_to_lu_transformmer, get_full, word_to_two
from common import full_to_two
from pypinyin import lazy_pinyin
# import attr


# @attr.s(frozen=True)
# class Item(object):
#     word = attr.ib(type=str,)
#     priority = attr.ib(type=int, default=1)
#     phones = attr.ib(type=list, default=list())


@curry
def for_each(proc, eles):
    if type(eles) is dict:
        for (k, v) in eles.items():
            proc(k, v)
    else:
        for e in eles:
            proc(e)


# @curry
# def cols_to_item(cols: List[str])->Item:
#     if len(cols) == 1:
#         return Item(word=cols[0])
#     elif len(cols) == 2:
#         return Item(word=cols[0], priority=int(cols[1]))
#     elif len(cols) == 2 + len(cols[0]):
#         return Item(word=cols[0], priority=cols[1], phones=list(filter(lambda e: len(e) != 0, [e.srtip() for e in cols[2:]])))
#     else:
#         raise RuntimeError("cols length not in [1,2]")

@curry
def cols_to_word_phone_table(cols: List[str], xhe_transformer, zrm_transformer) -> WordPhoneTable:
    if len(cols) == 1:
        word = cols[0]
        priority = 1
        full = get_full(word)
    elif len(cols) == 2:
        word = cols[0]
        priority = cols[1]
        full = get_full(word)
    elif len(cols) == 2 + len(cols[0]):
        word = cols[0]
        priority = cols[1]
        full = list(filter(lambda e: len(e) > 0, [e.strip() for e in cols[2:]]))
    else:
        raise RuntimeError("word item should be: 你好 [priority n i h ao]")

    return WordPhoneTable(
        word=word, 
        full=''.join(full),
        xhe=''.join([full_to_two(e, xhe_transformer) for e in full]),
        zrm=''.join([full_to_two(e, zrm_transformer) for e in full]),
        lu="",
        priority=priority, 
        updatedt=datetime.now()
    )



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
        print("words format:word prioroty w1_yin w2_yin ...")
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

    xhe_transformer = get_full_to_xhe_transformer();
    zrm_transformer = get_full_to_zrm_transformmer();
    lu_transformer = get_full_to_lu_transformmer();

    with open(words_path, "r", encoding='utf8') as fin:
        to_add_words = pipe(fin,
                            map(lambda e: e.strip().split(' ')),
                            # filter(lambda e: len(e) in (1, 2)),
                            filter(lambda e: len(e[0]) <= 5),
                            filter(lambda e: not contain_alpha(
                                e[0]) and not contain_symbols(e[0])),
                            filter(lambda e: e[0] not in exist_words),
                            map(lambda e: cols_to_word_phone_table(e, xhe_transformer, zrm_transformer))
                            )

        with db.atomic():
            WordPhoneTable.bulk_create(to_add_words, batch_size=100)

    print('done')
