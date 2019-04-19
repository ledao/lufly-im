import sys, os
from toolz.curried import pipe, map, filter
from tables import db, WordPhoneTable
from common import get_full, for_each, get_full_to_xhe_transformer, full_to_two
from common import get_full_to_zrm_transformmer, word_to_two, get_full_to_lu_transformmer


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


def fill_lu(item: WordPhoneTable, lu: str) -> WordPhoneTable:
    item.lu = lu
    return item


if __name__ == "__main__":

    print("check full")
    to_update_full_items = pipe(WordPhoneTable.select().where(WordPhoneTable.full == ""),
        map(lambda e: fill_full(e)),
    )
    with db.atomic():
        WordPhoneTable.bulk_update(to_update_full_items, fields=['full'], batch_size=100)
    del to_update_full_items

    print("check xhe")
    full_to_xhe_transformer = get_full_to_xhe_transformer()
    to_update_xhe_items = pipe(WordPhoneTable.select().where(WordPhoneTable.xhe == ""),
        map(lambda e: (e, word_to_two(e.word, full_to_xhe_transformer))),
        map(lambda e: fill_xhe(e[0], e[1])),
    )
    with db.atomic():
        WordPhoneTable.bulk_update(to_update_xhe_items, fields=['xhe'], batch_size=100)
    del to_update_xhe_items
    del full_to_xhe_transformer

    print("check zrm")
    full_to_zrm_transformer = get_full_to_zrm_transformmer()
    to_update_zrm_items = pipe(WordPhoneTable.select().where(WordPhoneTable.zrm == ""),
        map(lambda e: (e, word_to_two(e.word, full_to_zrm_transformer))),
        map(lambda e: fill_zrm(e[0], e[1])),
    )
    with db.atomic():
        WordPhoneTable.bulk_update(to_update_zrm_items, fields=["zrm"], batch_size=100)
    del to_update_zrm_items
    del full_to_zrm_transformer

    print('check lu')
    full_to_lu_transformer = get_full_to_lu_transformmer()
    to_update_lu_items = pipe(WordPhoneTable.select().where(WordPhoneTable.lu == ''),
        map(lambda e: (e, word_to_two(e.word, full_to_lu_transformer))),
        map(lambda e: fill_lu(e[0], e[1])),
    )
    with db.atomic():
        WordPhoneTable.bulk_update(to_update_lu_items, fields=['lu'], batch_size=100)
    del to_update_lu_items
    del full_to_lu_transformer


    print("done")
