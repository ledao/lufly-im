import sys, os
from toolz.curried import pipe, map, filter
from tables import db, WordPhoneTable
from common import get_full, for_each, get_full_to_xhe_transformer, full_to_two
from common import get_full_to_zrm_transformmer, word_to_two


def fill_full(item: WordPhoneTable) -> WordPhoneTable:
    full = ''.join(get_full(item.word))
    item.full = full
    return item

def fill_xhe(item: WordPhoneTable, xhe: str) -> WordPhoneTable:
    item.xhe = xhe
    return item


def fill_zrm(item: WordPhoneTable, zrm: str) -> WordPhoneTable:
    item.zrm = zrm
    return item


if __name__ == "__main__":

    print("check full")
    pipe(WordPhoneTable.select().where(WordPhoneTable.full == ""),
        map(lambda e: fill_full(e)),
        for_each(lambda e: e.save()),
    )

    print("check xhe")
    full_to_xhe_transformer = get_full_to_xhe_transformer()
    pipe(WordPhoneTable.select().where(WordPhoneTable.xhe == ""),
        map(lambda e: (e, word_to_two(e.word, full_to_xhe_transformer))),
        map(lambda e: fill_xhe(e[0], e[1])),
        for_each(lambda e: e.save()),
    )
    del full_to_xhe_transformer

    print("check zrm")
    full_to_zrm_transformer = get_full_to_zrm_transformmer()
    WordPhoneTable.update(zrm = word_to_two(WordPhoneTable.word, full_to_zrm_transformer)).where(WordPhoneTable.zrm == '').execute()
    
    # pipe(WordPhoneTable.select().where(WordPhoneTable.zrm == ""),
    #     map(lambda e: (e, word_to_two(e.word, full_to_zrm_transformer))),
    #     map(lambda e: fill_zrm(e[0], e[1])),
    #     for_each(lambda e: e.save()),
    # )
    del full_to_zrm_transformer

    print("done")
