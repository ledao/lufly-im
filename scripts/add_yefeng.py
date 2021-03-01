#encoding=utf8
import os, sys
from tables import YeFengWordTable, db
from datetime import datetime

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"USAGE: python3 {sys.argv[0]} words.txt", file=sys.stderr)
        sys.exit(1)

    _, words_path = sys.argv

    words = []
    with open(words_path, "r", encoding='utf8') as fin:
        for line in fin:
            cols = line.strip().split("\t")
            if len(cols) != 3: continue
            pys = cols[0]
            word = cols[1]
            freq = cols[2]
            words.append(
                YeFengWordTable(
                    word=word,
                    py=pys,
                    priority=freq,
                    updatedt=datetime.now(),
                ))

    with db.atomic():
        YeFengWordTable.bulk_create(words, batch_size=100)

    print(len(words))
    print('done')