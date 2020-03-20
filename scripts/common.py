import sys
from typing import Tuple, List, Dict, Set
from toolz.curried import curry, pipe, map, filter, groupby, valmap
from toolz.curried import itemmap, valfilter
from pypinyin import lazy_pinyin
from tables import FullToTwoTable
from tables import CharPhoneTable, CharHeShapeTable, WordPhoneTable, EngWordTable, CharLuShapeTable
from tables import DelWordTable

def for_each(proc, eles):
    if type(eles) is dict:
        for (k, v) in eles.items():
            proc(k, v)
    else:
        for e in eles:
            proc(e)


for_each = curry(for_each)


def split_sy(pinyin: str) -> Tuple[str, str]:
    if pinyin == "sh":
        s = "sh"
        y = "i"
    elif pinyin.startswith("zh"):
        s = "zh"
        y = pinyin[2:]
    elif pinyin.startswith("ch"):
        s = "ch"
        y = pinyin[2:]
    elif pinyin.startswith("sh"):
        s = "sh"
        y = pinyin[2:]
    elif pinyin == "er":
        s = "e"
        y = "r"
    elif pinyin == "e":
        s = "e"
        y = "e"
    elif pinyin == "a":
        s = "a"
        y = "a"
    elif pinyin == "n":
        s = "e"
        y = "n"
    elif pinyin == "o":
        s = "o"
        y = "o"
    elif pinyin == "ang":
        s = "a"
        y = "ang"
    else:
        s = pinyin[0]
        y = pinyin[1:]
    return (s, y)


def get_full(word: str) -> List[str]:
    fulls = []
    for full in lazy_pinyin(word):
        for e in full:
            if e not in "abcdefghijklmnopqrstuvwxyz":
                raise RuntimeError(f"{e} not alphe, word is: {word}")
        fulls.append(full)
    return fulls


def get_full_to_xhe_transformer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
            map(lambda e: (e.full, e.xhe)),
            groupby(lambda e: e[0]),
            itemmap(lambda kv: (kv[0], list(
                map(lambda e: e[1], kv[1]))[0])),
            dict
            )


def get_full_to_zrm_transformmer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
                map(lambda e: (e.full, e.zrm)),
                groupby(lambda e: e[0]),
                itemmap(lambda kv: (kv[0], list(
                    map(lambda e: e[1], kv[1]))[0])),
                dict
                )


def get_full_to_lu_transformmer() -> Dict[str, str]:
    return pipe(FullToTwoTable().select(),
                map(lambda e: (e.full, e.lu)),
                groupby(lambda e: e[0]),
                itemmap(lambda kv: (kv[0], list(
                    map(lambda e: e[1], kv[1]))[0])),
                dict
                )


def get_xhe_to_full_transformer() -> Dict[str, List[str]]:
    return pipe(FullToTwoTable.select(),
                map(lambda e: (e.full, e.two)),
                groupby(lambda e: e[1]),
                itemmap(lambda kv: (kv[0], list(
                    filter(lambda e: e != kv[0], map(lambda e: e[0], kv[1]))))),
                itemmap(lambda kv: (kv[0], kv[1]
                                    if len(kv[1]) > 0 else [kv[0]])),
                valfilter(lambda e: len(e) == 1),
                dict
                )


def full_to_two(pinyin: str, transformer: Dict[str, str]) -> str:
    sy = split_sy(pinyin)
    if len(sy) != 2:
        raise RuntimeError(f"{sy} length != 2")
    if sy[0] not in transformer or sy[1] not in transformer:
        raise RuntimeError(f"{sy} not in transformer")
    return f"{transformer[sy[0]]}{transformer[sy[1]]}"

def word_to_two(word: str, transformer: Dict[str, str]) -> str:
    return ''.join([full_to_two(e, transformer) for e in get_full(word)])


def get_char_to_shapes() -> Dict[str, List[str]]:
    char_to_shape = pipe(CharHeShapeTable.select(),
                     map(lambda e: (e.char, e.shapes)),
                     filter(lambda e: e[0] != '' and e[1] != ''),
                     groupby(lambda e: e[0]),
                     valmap(lambda e: [s[1] for s in e]),
                     dict
                     )
    return char_to_shape


def get_char_to_lu_shapes() -> Dict[str, List[str]]:
    char_to_shape = pipe(CharLuShapeTable.select(),
                     map(lambda e: (e.char, e.shapes)),
                     filter(lambda e: e[0] != '' and e[1] != ''),
                     groupby(lambda e: e[0]),
                     valmap(lambda e: [s[1] for s in e]),
                     dict
                     )
    return char_to_shape


def get_char_to_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.xhe)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]),
                          dict
                          )
    return char_to_phones


def get_del_words() -> Set[str]:
    del_words = pipe(
        DelWordTable.select(),
        map(lambda e: e.word),
        filter(lambda e: e != ''),
        set
    )
    return del_words

