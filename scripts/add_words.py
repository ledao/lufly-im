#encoding=utf8
import os, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from lufly.models.tables import CharPhoneTable, CharShapeTable, WordPhoneTable
from peewee import fn
from toolz.curried import pipe, map, filter, do, groupby, keymap
from update_word_phones import split_sy, get_double_dict, full_to_double
from pypinyin import lazy_pinyin

def exist_word_phones(word, phones):
    num = WordPhoneTable.select().where(WordPhoneTable.word == word, WordPhoneTable.phones == phones).count()
    return num > 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 add_words.py words.txt")
        sys.exit(1)
    
    _, words_path = sys.argv

    with open(words_path, "r", encoding='utf8') as fin:
        ft_dict = get_double_dict()

        to_add_words = pipe(fin,
            map(lambda e: e.strip()),
            filter(lambda e: e != ''),
            groupby(lambda e: e),
            keymap(lambda e: (e, map(lambda e: split_sy(e), lazy_pinyin(e)))),
            map(lambda e: (e[0], ''.join(full_to_double(e[1], ft_dict)))),
            filter(lambda e: not exist_word_phones(e[0], e[1])),
            map(lambda e: WordPhoneTable(word=e[0], phones=e[1], priority=1, updatedt=datetime.now())),
        )

        for w in to_add_words:
            print(f"add {w}")
            w.save()

    print('done')