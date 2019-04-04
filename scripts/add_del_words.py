#encoding=utf8
import os, sys
from datetime import datetime
from tables import db, DelWordTable
from toolz.curried import map, filter, pipe, groupby, keymap


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 add_del_words.py words.txt")
        sys.exit(1)
    
    _, words_path = sys.argv

    exist_wordphones = pipe(DelWordTable.select(),
        map(lambda e: e.word),
        set
    )

    with open(words_path, "r", encoding='utf8') as fin:
        to_add_words = pipe(fin,
            map(lambda e: e.strip()),
            filter(lambda e: e != ''),
            filter(lambda e: e not in exist_wordphones),
            groupby(lambda e: e),
            keymap(lambda e: DelWordTable(word=e, updatedt=datetime.now())),
        )

        with db.atomic():
            DelWordTable.bulk_create(to_add_words, batch_size=100)

        # for w in to_add_words:
        #     print(f"add {w}")
        #     # w.save()

    print('done')