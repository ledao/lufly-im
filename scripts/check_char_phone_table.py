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


def is_diff_s_same_y_full(item: CharPhoneTable, transformer: Dict[str, str]) -> bool:
    two = full_to_two(item.full, transformer)
    if two[0] != item.phones[0] and two[1] == item.phones[1]:
        return True
    else:
        return False


def fix_diff_s_same_y_full(item: CharPhoneTable) -> CharPhoneTable:
    full_sy = split_sy(item.full)
    correct_s = item.phones[0]
    if correct_s == "u":
        correct_s = "sh"
    elif correct_s == "i":
        correct_s = "ch"
    elif correct_s == "v":
        correct_s = "zh"
    item.full = correct_s+full_sy[1]
    return item


def fix_full_from_xhe(item: CharPhoneTable, transformer: Dict[str, List[str]]) -> Tuple[CharPhoneTable, bool]:
    xhe = item.phones
    if xhe[1] in 'ivu':
        y = xhe[1]
    elif xhe[1] in transformer:
        y = transformer[xhe[1]][0]
    else:
        return item, False

    if xhe[0] == "i":
        s = "ch"
    elif xhe[0] == "u":
        s = "sh"
    elif xhe[0] == "v":
        s = "zh"
    else:
        s = xhe[0]

    item.full = s + y
    return item, True


def fill_zrm(item: CharPhoneTable, transformer: Dict[str, str]) -> Tuple[CharPhoneTable, bool]:
    sy = split_sy(item.full)
    if sy[0] not in transformer or sy[1] not in transformer:
        print(f"{sy} not in transformer", file=sys.stderr)
        return item, False
    item.zrm = transformer[sy[0]] + transformer[sy[1]]
    return item, True


if __name__ == "__main__":

    null_phones_items = pipe(CharPhoneTable.select().where(CharPhoneTable.phones == ''),
                             list,
                             )
    if len(null_phones_items) != 0:
        pipe(null_phones_items,
             for_each(lambda e: print(e)),
             )
        print(f"null phones item is: {len(null_phones_items)}")
        sys.exit(1)

    del null_phones_items

    null_full_items = pipe(CharPhoneTable.select().where(CharPhoneTable.full == ''),
                           list,
                           )
    if len(null_full_items) != 0:
        print(f"null full items is {len(null_full_items)}")
        pipe(null_full_items,
             map(lambda e: (e, ''.join(get_full(e.char)))),
             map(lambda e: update_full(e[0], e[1])),
             for_each(lambda e: e.save()),
             )
    del null_full_items

    full_to_xhe_transformer = get_full_to_xhe_transformer()
    xhe_full_neq_items = pipe(CharPhoneTable.select(),
                              filter(lambda e: e.phones != full_to_two(
                                  e.full, full_to_xhe_transformer)),
                              list,
                              )
    if len(xhe_full_neq_items) != 0:
        print(f"xhe full not equal len is {len(xhe_full_neq_items)}")

        pipe(xhe_full_neq_items,
             filter(lambda e: is_diff_s_same_y_full(
                 e, full_to_xhe_transformer)),
             map(fix_diff_s_same_y_full),
             for_each(lambda e: e.save()),
             )

        xhe_to_full_transformer = get_xhe_to_full_transformer()
        pipe(xhe_full_neq_items,
             filter(lambda e: not is_diff_s_same_y_full(
                 e, full_to_xhe_transformer)),
             map(lambda e: fix_full_from_xhe(e, xhe_to_full_transformer)),
             filter(lambda e: e[1]),
             for_each(lambda e: e[0].save()),
             )

        pipe(xhe_full_neq_items,
             filter(lambda e: not is_diff_s_same_y_full(
                 e, full_to_xhe_transformer)),
             filter(lambda e: not fix_full_from_xhe(
                 e, xhe_to_full_transformer)[1]),
             for_each(lambda e: print(e)),
             # TODO: fix this wrong items.
             )

    del xhe_full_neq_items

    null_zrm_items = pipe(CharPhoneTable.select().where(CharPhoneTable.zrm == ''),
                          list,
                          )
    if len(null_zrm_items) != 0:
        print(f"null zrm items is {len(null_zrm_items)}")
        full_to_zrm_transformaer = get_full_to_zrm_transformmer()

        pipe(null_zrm_items,
             map(lambda e: fill_zrm(e, full_to_zrm_transformaer)),
             filter(lambda e: e[1]),
             for_each(lambda e: e[0].save()),
             )

        not_auto_fill_zrm_items = pipe(null_zrm_items,
                                       filter(lambda e: not fill_zrm(
                                           e, full_to_zrm_transformaer)[1]),
                                       list
                                       )
        if len(not_auto_fill_zrm_items) != 0:
            print(f"{len(not_auto_fill_zrm_items)} item cannot auto fill zrm.")

        del not_auto_fill_zrm_items

    del null_zrm_items

    print("done")
