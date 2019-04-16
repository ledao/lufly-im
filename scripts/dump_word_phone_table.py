import sys
import os
from datetime import datetime
from tables import db, WordPhoneTable

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 dump_char_phone_table.py word_phone.txt")
        sys.exit(1)

    _, word_phone_path = sys.argv
    with open(word_phone_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            cols = line.split('\t')
            if len(cols) != 2:
                print(f"ERROR line {line} in file {word_phone_path}")
                continue
            cols = list(map(lambda e: e.strip(), cols))
            exit_num = WordPhoneTable.select().where(
                WordPhoneTable.word == cols[0], WordPhoneTable.phones == cols[1]).count()
            if exit_num > 0:
                print(f"WARNING: word phone already exists, {line}")
                continue
            else:
                WordPhoneTable(word=cols[0], phones=cols[1],
                               priority=1, updatedt=datetime.now()).save()
    print('done')
    pass
