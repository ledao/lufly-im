from common import *
from tables import db


def check_bingji_char(transformer: Dict[str, str]):
    to_update_bingji_items = []
    for item in CharPhoneTable.select():
        full = item.full
        bingji = item.bingji
        s, y = split_sy(full)
        full_bingji = transformer[s] + transformer[y]
        if bingji != full_bingji:
            to_update_bingji_items.append(item)
            item.bingji = full_bingji

    with db.atomic():
        CharPhoneTable.bulk_update(to_update_bingji_items,
                                   fields=['bingji'],
                                   batch_size=100)
    null_bingji_count = CharPhoneTable.select().where(
        CharPhoneTable.bingji == '').count()
    if null_bingji_count != 0:
        print(f'{null_bingji_count} null items, please check mannually.')

    print(to_update_bingji_items)
    print(f'update {len(to_update_bingji_items)} char items')


def check_bingji_word(transformer: Dict[str, str]):
    to_update_bingji_items = []
    for item in WordPhoneTable.select():
        fulls = item.full
        bingji = item.bingji
        full_bingjis_arr = []
        for full in fulls.split(' '):
            s, y = split_sy(full)
            full_bingji = transformer[s] + transformer[y]
            full_bingjis_arr.append(full_bingji)
        full_bingjis = ''.join(full_bingjis_arr)
        if bingji != full_bingjis:
            to_update_bingji_items.append(item)
            item.bingji = full_bingjis

    with db.atomic():
        WordPhoneTable.bulk_update(to_update_bingji_items,
                                   fields=['bingji'],
                                   batch_size=100)
    null_bingji_count = WordPhoneTable.select().where(
        WordPhoneTable.bingji == '').count()
    if null_bingji_count != 0:
        print(f'{null_bingji_count} null items, please check mannually.')

    print(to_update_bingji_items)
    print(f'update {len(to_update_bingji_items)} word items')


def main():
    full_to_bingji_transformer = get_full_to_bingji_transformer()
    check_bingji_char(full_to_bingji_transformer)
    check_bingji_word(full_to_bingji_transformer)
    print("done")


if __name__ == "__main__":
    main()
