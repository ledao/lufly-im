import sys
from typing import Tuple, List, Dict
from toolz.curried import curry, pipe, map, filter, groupby
from toolz.curried import itemmap, valfilter
from pypinyin import lazy_pinyin
from tables import FullToTwoTable, FullToZrmTable, FullToZrmTable


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
    elif pinyin.startswith("er"):
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
    full_to_two = {}
    for item in FullToTwoTable.select():
        if item.full in full_to_two:
            print(f"ERROR in {item.full}")
            sys.exit(1)
        else:
            full_to_two[item.full] = item.two
    return full_to_two


def get_full_to_zrm_transformmer() -> Dict[str, str]:
    return pipe(FullToZrmTable().select(),
                map(lambda e: (e.full, e.two)),
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
