from typing import Dict, List, Tuple
from toolz.curried import pipe, map, filter
from pypinyin import lazy_pinyin
from tables import db, CharPhoneTable
from common import for_each, get_full, full_to_two, get_full_to_xhe_transformer, split_sy


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


if __name__ == "__main__":

    null_phones_items = pipe(CharPhoneTable.select().where(CharPhoneTable.phones == ''),
        list,
    ) 
    if len(null_phones_items) != 0:
        print(f"null phones item is: {len(null_phones_items)}")
        #TODO: 添加自动添加phones代码
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
        filter(lambda e: e.phones != full_to_two(e.full, full_to_xhe_transformer)),
        list,
    )
    if len(xhe_full_neq_items) != 0:
        print(f"xhe full not equal len is {len(xhe_full_neq_items)}")

        pipe(xhe_full_neq_items,
            filter(lambda e: is_diff_s_same_y_full(e, full_to_xhe_transformer)),
            map(fix_diff_s_same_y_full),
            for_each(lambda e: e.save()),
        )

        pipe(xhe_full_neq_items,
            filter(lambda e: not is_diff_s_same_y_full(e, full_to_xhe_transformer)),
            for_each(lambda e: print(e)),
            #TODO:
        )


    del xhe_full_neq_items

    null_zrm_items = pipe(CharPhoneTable.select().where(CharPhoneTable.zrm == ''),
        list,
    )
    if len(null_zrm_items) != 0:
        print(f"null zrm items is {len(null_zrm_items)}")
    del null_zrm_items

    print("done")