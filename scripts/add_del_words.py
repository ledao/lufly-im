#encoding=utf8
import os, sys
from datetime import datetime
from tables import db, DelWordPhoneTable
from toolz.curried import map, filter, pipe, groupby, keymap


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 add_del_words.py words.txt")
        sys.exit(1)
    
    _, words_path = sys.argv

    exist_wordphones = pipe(DelWordPhoneTable.select(),
        map(lambda e: e.word+e.phones),
        set
    )

    with open(words_path, "r", encoding='utf8') as fin:
        to_add_words = pipe(fin,
            map(lambda e: e.strip()),
            filter(lambda e: e != ''),
            groupby(lambda e: e),
            keymap(lambda e: e.split(" ")),
            filter(lambda e: len(e) == 2),
            map(lambda e: DelWordPhoneTable(word=e[0], phones=e[1], updatedt=datetime.now())),
        )

        with db.atomic():
            DelWordPhoneTable.bulk_create(to_add_words, batch_size=100)

        # for w in to_add_words:
        #     print(f"add {w}")
        #     # w.save()

    print('done')