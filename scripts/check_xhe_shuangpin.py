from common import *
from tables import db


def check_xhe_char(transformer: Dict[str, str]):
    to_update_xhe_items = []
    for item in CharPhoneTable.select():
        full = item.full
        xhe = item.xhe
        s, y = split_sy(full)
        full_xhe = transformer[s] + transformer[y]
        if xhe != full_xhe:
            to_update_xhe_items.append(item)
            item.xhe = full_xhe

    with db.atomic():
        CharPhoneTable.bulk_update(to_update_xhe_items,
                                   fields=['xhe'],
                                   batch_size=100)
    null_xhe_count = CharPhoneTable.select().where(
        CharPhoneTable.xhe == '').count()
    if null_xhe_count != 0:
        print(f'{null_xhe_count} null items, please check mannually.')

    print(to_update_xhe_items)
    print(f'update {len(to_update_xhe_items)} char items')


def check_xhe_word(transformer: Dict[str, str]):
    to_update_xhe_items = []
    for item in WordPhoneTable.select():
        fulls = item.full
        xhe = item.xhe
        full_xhes_arr = []
        for full in fulls.split(' '):
            s, y = split_sy(full)
            full_xhe = transformer[s] + transformer[y]
            full_xhes_arr.append(full_xhe)
        full_xhes = ''.join(full_xhes_arr)
        if xhe != full_xhes:
            to_update_xhe_items.append(item)
            item.xhe = full_xhes

    with db.atomic():
        WordPhoneTable.bulk_update(to_update_xhe_items,
                                   fields=['xhe'],
                                   batch_size=100)
    null_xhe_count = WordPhoneTable.select().where(
        WordPhoneTable.xhe == '').count()
    if null_xhe_count != 0:
        print(f'{null_xhe_count} null items, please check mannually.')

    print(to_update_xhe_items)
    print(f'update {len(to_update_xhe_items)} word items')


def main():
    full_to_xhe_transformer = get_full_to_xhe_transformer()
    check_xhe_char(full_to_xhe_transformer)
    check_xhe_word(full_to_xhe_transformer)
    print("done")


if __name__ == "__main__":
    main()
