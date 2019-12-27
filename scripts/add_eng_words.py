#encoding=utf8
import os, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from tables import db, EngWordTable
from peewee import fn
from toolz.curried import pipe, map, filter, reduceby, keymap


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"USAGE: python3 {sys.argv[0]} words.txt", file=sys.stderr)
        sys.exit(1)
    
    _, words_path = sys.argv

    exist_wordphones = pipe(EngWordTable.select(),
        map(lambda e: e.word),
        set
    )

    with open(words_path, "r", encoding='utf8') as fin:

        to_add_words = pipe(fin,
            map(lambda e: e.strip()),
            filter(lambda e: e != ''),
            filter(lambda e: e not in exist_wordphones),
            reduceby(lambda e: e, lambda e1, e2: e1),
            map(lambda e: EngWordTable(word=e, priority=1, updatedt=datetime.now())),
        )

        with db.atomic():
            EngWordTable.bulk_create(to_add_words, batch_size=100)

        # for w in to_add_words:
        #     print(f"add {w}")
        #     # w.save()

    print('done')