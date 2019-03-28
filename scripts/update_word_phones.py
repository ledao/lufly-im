import os, sys
from pypinyin import lazy_pinyin
from lufly.models.tables import db, FullToTwoTable, WordPhoneTable

def split_sy(pinyin: str):
    if pinyin.startswith("zh"):
        s = "zh"
        y = pinyin[2:]
    elif pinyin.startswith("ch"):
        s = "ch"
        y = pinyin[2:]
    elif pinyin.startswith("sh"):
        s = "sh"
        y = pinyin[2:]
    elif pinyin.startswith("er"):
        s = "e"
        y = "r"
    elif pinyin == "e":
        s = "e"
        y = "e"
    elif pinyin == "a":
        s = "a"
        y = "a"
    elif pinyin == "n":
        s = "e"
        y = "n"
    elif pinyin == "o":
        s = "o"
        y = "o"
    elif pinyin == "ang":
        s = "a"
        y = "ang"
    else:
        s = pinyin[0]
        y = pinyin[1:]
    return (s, y)


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