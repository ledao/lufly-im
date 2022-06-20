from common import *
from tables import db


def check_zrm_char(transformer: Dict[str, str]):
    to_update_zrm_items = []
    for item in CharPhoneTable.select():
        full = item.full
        zrm = item.zrm
        s, y = split_sy(full)
        full_zrm = transformer[s] + transformer[y]
        if zrm != full_zrm:
            to_update_zrm_items.append(item)
            item.zrm = full_zrm

    with db.atomic():
        CharPhoneTable.bulk_update(to_update_zrm_items,
                                   fields=['zrm'],
                                   batch_size=100)
    null_zrm_count = CharPhoneTable.select().where(
        CharPhoneTable.zrm == '').count()
    if null_zrm_count != 0:
        print(f'{null_zrm_count} null items, please check mannually.')

    print(to_update_zrm_items)
    print(f'update {len(to_update_zrm_items)} char items')


def check_zrm_word(transformer: Dict[str, str]):
    to_update_zrm_items = []
    for item in WordPhoneTable.select():
        fulls = item.full
        zrm = item.zrm
        full_zrms_arr = []
        for full in fulls.split(' '):
            s, y = split_sy(full)
            full_zrm = transformer[s] + transformer[y]
            full_zrms_arr.append(full_zrm)
        full_zrms = ''.join(full_zrms_arr)
        if zrm != full_zrms:
            to_update_zrm_items.append(item)
            item.zrm = full_zrms

    with db.atomic():
        WordPhoneTable.bulk_update(to_update_zrm_items,
                                   fields=['zrm'],
                                   batch_size=100)
    null_zrm_count = WordPhoneTable.select().where(
        WordPhoneTable.zrm == '').count()
    if null_zrm_count != 0:
        print(f'{null_zrm_count} null items, please check mannually.')

    print(to_update_zrm_items)
    print(f'update {len(to_update_zrm_items)} word items')


def main():
    full_to_zrm_transformer = get_full_to_zrm_transformmer()
    check_zrm_char(full_to_zrm_transformer)
    check_zrm_word(full_to_zrm_transformer)
    print("done")


if __name__ == "__main__":
    main()
