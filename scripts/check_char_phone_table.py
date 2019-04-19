import sys
from typing import Dict, List, Tuple
from toolz.curried import pipe, map, filter
from pypinyin import lazy_pinyin
from tables import db, CharPhoneTable
from common import for_each, get_full, full_to_two, get_full_to_xhe_transformer, split_sy, get_full_to_zrm_transformmer
from common import get_xhe_to_full_transformer


def update_full(item: CharPhoneTable, full: str) -> CharPhoneTable:
    item.full = full
    return item

def fill_zrm(item: CharPhoneTable, transformer: Dict[str, str]) -> CharPhoneTable:
    sy = split_sy(item.full)
    if sy[0] not in transformer or sy[1] not in transformer:
        raise RuntimeError(f"{sy} not in transformer")
    item.zrm = transformer[sy[0]] + transformer[sy[1]]
    return item


if __name__ == "__main__":

    null_xhe_count = CharPhoneTable.select().where(CharPhoneTable.phones == '').count()
    if null_xhe_count != 0:
        print(f'{null_xhe_count} null xhe phones, please check manually.')

    null_full_count = CharPhoneTable.select().where(CharPhoneTable.full == '').count()
    if null_full_count != 0:
        to_update_full_items = pipe(null_full_items,
             map(lambda e: (e, ''.join(get_full(e.char)))),
             map(lambda e: update_full(e[0], e[1])),
             )
        with db.atomic():
            CharPhoneTable.bulk_update(to_update_full_items, fields=['full'], batch_size=100)
        del to_update_full_items
        null_full_count = CharPhoneTable.select().where(CharPhoneTable.full == '').count()
        if null_full_count != 0:
            print(f'{null_full_count} null full full phones, please check manually.')
    
    null_zrm_count = CharPhoneTable.select().where(CharPhoneTable.zrm == '').count()
    if null_zrm_count != 0:
        full_to_zrm_transformaer = get_full_to_zrm_transformmer()
        to_update_zrm_items = pipe(null_zrm_items,
             map(lambda e: fill_zrm(e, full_to_zrm_transformaer)),
             )
        with db.atomic():
            CharPhoneTable.bulk_update(to_update_zrm_items, fields=['zrm'], batch_size=100)
        del to_update_zrm_items
        del full_to_zrm_transformaer
        null_zrm_count = CharPhoneTable.select().where(CharPhoneTable.zrm == '').count()
        if null_zrm_count != 0:
            print(f'{null_zrm_count} null items, please check mannually.')

    print("done")
