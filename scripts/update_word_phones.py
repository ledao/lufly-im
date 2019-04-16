import os, sys
from pypinyin import lazy_pinyin
from tables import db, FullToTwoTable, WordPhoneTable
from common import split_sy


def full_to_double(pinyin, full_to_two):
    return [full_to_two[e[0]]+full_to_two[e[1]] for e in pinyin]


def get_double_dict():

    full_to_two = {}
    for item in FullToTwoTable.select():
        if item.full in full_to_two:
            print(f"ERROR in {item.full}")
            sys.exit(1)
        else:
            full_to_two[item.full] = item.two
    return full_to_two


if __name__ == "__main__":
    full_to_two = get_double_dict()
   
    for item in WordPhoneTable.select():
        word = item.word
        phones = item.phones
        pinyin = [split_sy(e) for e in lazy_pinyin(word)]
        # print(word, phones, pinyin)
        double = ''.join(full_to_double(pinyin, full_to_two))
        if phones != double:
            print(f"diff in {item.id}, {word}, {phones}, {double}")
            item.delete_instance()


    print("done")