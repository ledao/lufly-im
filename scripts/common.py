import imp
import re
from tqdm import tqdm

import tables
from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from typing import Tuple, List, Dict, Set

from pypinyin import lazy_pinyin
from toolz.curried import curry, pipe, map, filter, groupby, valmap
from toolz.curried import itemmap, valfilter

from tables import CharPhoneTable, CharHeShapeTable, CharLuShapeTable, WordPhoneTable, TangshiTable, db
from tables import FullToTwoTable


class ShuangPinSchema:
    def __init__(self, name: str):
        super(ShuangPinSchema, self).__init__()
        self.name = name

    def __str__(self) -> str:
        return f"shuang pin schema {self.name}"

    def __eq__(self, other):
        return self.name == other.name


XHE_SP_SCHEMA = ShuangPinSchema("xiao he")
LU_SP_SCHEMA = ShuangPinSchema("xiao lu")
ZRM_SP_SCHEMA = ShuangPinSchema("zi ran ma")
BINGJI_SP_SCHEMA = ShuangPinSchema("bing ji")


@curry
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
    return s, y


def split_sy_bingji(pinyin: str) -> Tuple[str, str]:
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
    elif pinyin == "ai":
        s = "a"
        y = "x"
    elif pinyin == "an":
        s = "a"
        y = "g"
    elif pinyin == "ao":
        s = "a"
        y = "h"
    elif pinyin == "e":
        s = "a"
        y = "d"
    elif pinyin == "ei":
        s = "a"
        y = "m"
    elif pinyin == "en":
        s = "a"
        y = "e"
    elif pinyin == "eng":
        s = "a"
        y = "i"
    elif pinyin == "er":
        s = "a"
        y = "r"
    elif pinyin == "a":
        s = "a"
        y = "u"
    elif pinyin == "n":
        s = "a"
        y = "e"
    elif pinyin == "o":
        s = "a"
        y = "f"
    elif pinyin == "ou":
        s = "a"
        y = "w"
    elif pinyin == "ang":
        s = "a"
        y = "b"
    else:
        s = pinyin[0]
        y = pinyin[1:]
    return (s, y)


def get_full(word: str) -> List[str]:
    fulls = []
    for full in lazy_pinyin(word):
        for e in full:
            if e not in "abcdefghijklmnopqrstuvwxyz":
                raise RuntimeError(f"{e} not alphe, word is: {word}, pinyin is: {full}")
        fulls.append(full)
    return fulls


def get_full_to_xhe_transformer() -> Dict[str, str]:
    return pipe(
        FullToTwoTable().select(), map(lambda e: (e.full, e.xhe)),
        groupby(lambda e: e[0]),
        itemmap(lambda kv: (kv[0], list(map(lambda e: e[1], kv[1]))[0])), dict)


def get_full_to_zrm_transformmer() -> Dict[str, str]:
    return pipe(
        FullToTwoTable().select(), map(lambda e: (e.full, e.zrm)),
        groupby(lambda e: e[0]),
        itemmap(lambda kv: (kv[0], list(map(lambda e: e[1], kv[1]))[0])), dict)


def get_full_to_lu_transformmer() -> Dict[str, str]:
    return pipe(
        FullToTwoTable().select(), map(lambda e: (e.full, e.lu)),
        groupby(lambda e: e[0]),
        itemmap(lambda kv: (kv[0], list(map(lambda e: e[1], kv[1]))[0])), dict)


def get_full_to_bingji_transformer() -> Dict[str, str]:
    return pipe(
        FullToTwoTable().select(), map(lambda e: (e.full, e.bingji)),
        groupby(lambda e: e[0]),
        itemmap(lambda kv: (kv[0], list(map(lambda e: e[1], kv[1]))[0])), dict)


def get_xhe_to_full_transformer() -> Dict[str, List[str]]:
    return pipe(
        FullToTwoTable.select(), map(lambda e: (e.full, e.two)),
        groupby(lambda e: e[1]),
        itemmap(lambda kv: (
            kv[0],
            list(filter(lambda e: e != kv[0], map(lambda e: e[0], kv[1]))))),
        itemmap(lambda kv: (kv[0], kv[1] if len(kv[1]) > 0 else [kv[0]])),
        valfilter(lambda e: len(e) == 1), dict)


def full_to_two(pinyin: str, transformer: Dict[str, str], bingji=False) -> str:
    if not bingji:
        sy = split_sy(pinyin)
    else:
        sy = split_sy_bingji(pinyin)
    if len(sy) != 2:
        raise RuntimeError(f"{sy} length != 2")
    if sy[0] not in transformer or sy[1] not in transformer:
        raise RuntimeError(f"{sy} not in transformer")
    if not bingji:
        s = transformer[sy[0]]
        y = transformer[sy[1]]
    else:
        s = transformer[sy[0]] if sy[0] != "a" else "a"
        y = transformer[sy[1]] if sy[0] != "a" else sy[1]
    return f"{s}{y}"


def word_to_two(word: str, transformer: Dict[str, str], bingji=False) -> str:
    return ''.join(
        [full_to_two(e, transformer, bingji) for e in get_full(word)])


def get_char_to_xhe_shapes() -> Dict[str, List[str]]:
    char_to_shape = pipe(CharHeShapeTable.select(),
                         map(lambda e: (e.char, e.shapes)),
                         filter(lambda e: e[0] != '' and e[1] != ''),
                         groupby(lambda e: e[0]),
                         valmap(lambda e: [s[1] for s in e]), dict)
    return char_to_shape


def get_char_to_lu_shapes() -> Dict[str, List[str]]:
    char_to_shapes = defaultdict(list)
    for item in CharLuShapeTable.select().where(CharLuShapeTable.shapes != "-",
                                                CharLuShapeTable.shapes != ''):
        char = item.char
        shapes = item.shapes
        if char == '' or shapes == '':
            continue
        char_to_shapes[char].append(shapes)

    return char_to_shapes


def get_char_to_xhe_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.xhe)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]), dict)
    return char_to_phones


def get_char_to_zrm_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.zrm)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]), dict)
    return char_to_phones


def get_char_to_bingji_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.bingji)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]), dict)
    return char_to_phones


def get_char_to_lu_phones() -> Dict[str, List[str]]:
    char_to_phones = pipe(CharPhoneTable.select(),
                          map(lambda e: (e.char, e.lu)),
                          filter(lambda e: e[0] != '' and e[1] != ''),
                          groupby(lambda e: e[0]),
                          valmap(lambda phones: [e[1] for e in phones]), dict)
    return char_to_phones


def get_del_words() -> Set[str]:
    # del_words = pipe(DelWordTable.select(), map(lambda e: e.word),
    #                  filter(lambda e: e != ''), set)
    # return del_words
    return set()


def is_all_alpha(s: str) -> bool:
    for e in s:
        if e.lower() in "abcdefghijklmnopqrstuvwxyz":
            continue
        else:
            return False
    return True


@dataclass
class SchemaConfig(object):
    schema_id: str
    name: str
    version: str
    authors: List[str]
    description: str
    auto_select_pattern: str
    shuangpin_schema: ShuangPinSchema


def get_exists_chars() -> Set[str]:
    exist_chars = set()
    for e in CharPhoneTable.select():
        exist_chars.add(e.char)
    return exist_chars


def get_exists_charyinpins() -> Set[str]:
    results = set()
    for item in tables.CharPhoneTable.select():
        results.add(f"{item.char}{item.full}")
    return results


def get_exists_words() -> Set[str]:
    exist_words = set()

    exist_words.union(get_exists_chars())

    for e in WordPhoneTable.select():
        exist_words.add(e.word)

    for e in TangshiTable.select():
        exist_words.add(e.word)

    return exist_words

def check_wordphonetable_pinyin(transformer: Dict[str, str], schema: ShuangPinSchema):
    to_update_items = []
    with tqdm(total=len(WordPhoneTable), desc="检查词的拼音") as pbar:
        for item in WordPhoneTable.select():
            fulls = item.full
            if schema == XHE_SP_SCHEMA:
                shuangpin = item.xhe
            elif schema == LU_SP_SCHEMA:
                shuangpin = item.lu
            elif schema == ZRM_SP_SCHEMA:
                shuangpin = item.zrm
            elif schema == BINGJI_SP_SCHEMA:
                shuangpin = item.bingji
            else:
                raise RuntimeError(f'unknown schema: {schema}')

            full_shuangpins_arr = []
            for full in fulls.split(' '):
                s, y = split_sy(full)
                sp = transformer[s] + transformer[y]
                full_shuangpins_arr.append(sp)
            full_shuangpins = ''.join(full_shuangpins_arr)
            if full_shuangpins != shuangpin:
                if schema == XHE_SP_SCHEMA:
                    item.xhe = full_shuangpins
                elif schema == LU_SP_SCHEMA:
                    item.lu = full_shuangpins
                elif schema == ZRM_SP_SCHEMA:
                    item.zrm = full_shuangpins
                elif schema == BINGJI_SP_SCHEMA:
                    item.bingji = full_shuangpins
                else:
                    raise RuntimeError(f'unknown schema: {schema}')
                to_update_items.append(item)
                pbar.set_postfix(OrderedDict(word=item.word, before=shuangpin, after=full_shuangpins))
            pbar.update()

    with db.atomic():
        if schema == XHE_SP_SCHEMA:
            WordPhoneTable.bulk_update(to_update_items,
                                       fields=['xhe'],
                                       batch_size=100)
        elif schema == LU_SP_SCHEMA:
            WordPhoneTable.bulk_update(to_update_items,
                                       fields=['lu'],
                                       batch_size=100)
        elif schema == ZRM_SP_SCHEMA:
            WordPhoneTable.bulk_update(to_update_items,
                                       fields=['zrm'],
                                       batch_size=100)
        elif schema == BINGJI_SP_SCHEMA:
            WordPhoneTable.bulk_update(to_update_items,
                                       fields=['bingji'],
                                       batch_size=100)
        else:
            raise RuntimeError(f'unknown schema: {schema}')

    print(to_update_items)
    print(f'update {len(to_update_items)} wordphonetable items')


def check_tangshitable_pinyin(transformer: Dict[str, str], schema: ShuangPinSchema):
    to_update_items = []
    with tqdm(total=len(TangshiTable), desc="检查诗词的拼音") as pbar:
        for item in TangshiTable.select():
            fulls = item.full
            if schema == XHE_SP_SCHEMA:
                shuangpin = item.xhe
            elif schema == LU_SP_SCHEMA:
                shuangpin = item.lu
            elif schema == ZRM_SP_SCHEMA:
                shuangpin = item.zrm
            elif schema == BINGJI_SP_SCHEMA:
                shuangpin = item.bingji
            else:
                raise RuntimeError(f'unknown schema: {schema}')

            full_shuangpins_arr = []
            for full in fulls.split(' '):
                s, y = split_sy(full)
                sp = transformer[s] + transformer[y]
                full_shuangpins_arr.append(sp)
            full_shuangpins = ''.join(full_shuangpins_arr)
            if full_shuangpins != shuangpin:
                if schema == XHE_SP_SCHEMA:
                    item.xhe = full_shuangpins
                elif schema == LU_SP_SCHEMA:
                    item.lu = full_shuangpins
                elif schema == ZRM_SP_SCHEMA:
                    item.zrm = full_shuangpins
                elif schema == BINGJI_SP_SCHEMA:
                    item.bingji = full_shuangpins
                else:
                    raise RuntimeError(f'unknown schema: {schema}')
                to_update_items.append(item)
                pbar.set_postfix(OrderedDict(word=item.word, before=shuangpin, after=full_shuangpins))
            pbar.update()

    with db.atomic():
        if schema == XHE_SP_SCHEMA:
            TangshiTable.bulk_update(to_update_items,
                                       fields=['xhe'],
                                       batch_size=100)
        elif schema == LU_SP_SCHEMA:
            TangshiTable.bulk_update(to_update_items,
                                       fields=['lu'],
                                       batch_size=100)
        elif schema == ZRM_SP_SCHEMA:
            TangshiTable.bulk_update(to_update_items,
                                       fields=['zrm'],
                                       batch_size=100)
        elif schema == BINGJI_SP_SCHEMA:
            TangshiTable.bulk_update(to_update_items,
                                       fields=['bingji'],
                                       batch_size=100)
        else:
            raise RuntimeError(f'unknown schema: {schema}')

    print(to_update_items)
    print(f'update {len(to_update_items)} tangshitable items')


def check_words_pinyin(transformer: Dict[str, str], schema: ShuangPinSchema):
    check_wordphonetable_pinyin(transformer, schema)
    check_tangshitable_pinyin(transformer, schema)


def check_chars_pinyin(transformer: Dict[str, str], schema: ShuangPinSchema):
    to_update_items = []
    with tqdm(total=len(CharPhoneTable), desc="检查字的拼音") as pbar:
        for item in CharPhoneTable.select():
            full = item.full
            if schema == XHE_SP_SCHEMA:
                shuangpin = item.xhe
            elif schema == LU_SP_SCHEMA:
                shuangpin = item.lu
            elif schema == ZRM_SP_SCHEMA:
                shuangpin = item.zrm
            elif schema == BINGJI_SP_SCHEMA:
                shuangpin = item.bingji
            else:
                raise RuntimeError(f"unkonwn schame {schema}")
            s, y = split_sy(full)
            sp = transformer[s] + transformer[y]
            if shuangpin != sp:
                if schema == XHE_SP_SCHEMA:
                    item.xhe = sp
                elif schema == LU_SP_SCHEMA:
                    item.lu = sp
                elif schema == ZRM_SP_SCHEMA:
                    item.zrm = sp
                elif schema == BINGJI_SP_SCHEMA:
                    item.bingji = sp
                else:
                    raise RuntimeError(f"unkonwn schame {schema}")
                to_update_items.append(item)
                pbar.set_postfix(to_update=item.char)
                pbar.set_postfix(OrderedDict(char=item.char, before=shuangpin, after=sp))
            pbar.update()

    with db.atomic():
        if schema == XHE_SP_SCHEMA:
            CharPhoneTable.bulk_update(to_update_items,
                                       fields=['xhe'],
                                       batch_size=100)
        elif schema == LU_SP_SCHEMA:
            CharPhoneTable.bulk_update(to_update_items,
                                       fields=['lu'],
                                       batch_size=100)
        elif schema == ZRM_SP_SCHEMA:
            CharPhoneTable.bulk_update(to_update_items,
                                       fields=['zrm'],
                                       batch_size=100)
        elif schema == BINGJI_SP_SCHEMA:
            CharPhoneTable.bulk_update(to_update_items,
                                       fields=['bingji'],
                                       batch_size=100)
        else:
            raise RuntimeError(f"unkonwn schame {schema}")

    print(to_update_items)
    print(f'update {len(to_update_items)} char items')


def contain_alpha(word: str) -> bool:
    for c in word:
        if c.lower() in "abcdefghijklmnopqrstuvwxyz":
            return True

    return False


def contain_symbols(word: str) -> bool:
    if re.match(
            '[1234567890’!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~，。！@#$%^&*………_+}{}]+',
            word) is None:
        return False
    else:
        return True

