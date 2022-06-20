from typing import Dict

from tables import db, CharPhoneTable, WordPhoneTable
from common import get_full_to_lu_transformmer, split_sy


def check_lu_char(transformer: Dict[str, str]):
    to_update_lu_items = []
    for item in CharPhoneTable.select():
        full = item.full
        lu = item.lu
        s, y = split_sy(full)
        full_lu = transformer[s] + transformer[y]
        if lu != full_lu:
            to_update_lu_items.append(item)
            item.lu = full_lu

    with db.atomic():
        CharPhoneTable.bulk_update(to_update_lu_items,
                                   fields=['lu'],
                                   batch_size=100)
    null_lu_count = CharPhoneTable.select().where(
        CharPhoneTable.lu == '').count()
    if null_lu_count != 0:
        print(f'{null_lu_count} null items, please check mannually.')

    print(to_update_lu_items)
    print(f'update {len(to_update_lu_items)} char items')


def check_lu_word(transformer: Dict[str, str]):
    to_update_lu_items = []
    for item in WordPhoneTable.select():
        fulls = item.full
        lu = item.lu
        full_lus_arr = []
        for full in fulls.split(' '):
            s, y = split_sy(full)
            full_lu = transformer[s] + transformer[y]
            full_lus_arr.append(full_lu)
        full_lus = ''.join(full_lus_arr)
        if lu != full_lus:
            to_update_lu_items.append(item)
            item.lu = full_lus

    with db.atomic():
        WordPhoneTable.bulk_update(to_update_lu_items,
                                   fields=['lu'],
                                   batch_size=100)
    null_lu_count = WordPhoneTable.select().where(
        WordPhoneTable.lu == '').count()
    if null_lu_count != 0:
        print(f'{null_lu_count} null items, please check mannually.')

    print(to_update_lu_items)
    print(f'update {len(to_update_lu_items)} word items')


def main():
    full_to_lu_transformer = get_full_to_lu_transformmer()
    check_lu_char(full_to_lu_transformer)
    check_lu_word(full_to_lu_transformer)
    print("done")


if __name__ == "__main__":
    main()
