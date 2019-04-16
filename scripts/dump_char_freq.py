import sys, os
from collections import defaultdict
from datetime import datetime
from tables import db, CharFreqTable

#这里还要一些中文文本，里面有很多中国的东西

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 dump_char_freq.py chars.txt") 
        sys.exit(1)
    _, filepath = sys.argv

    char_freqs = defaultdict(lambda : 0)
    with open(filepath, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip().replace("\t\n ", "")
            for char in line:
                char_freqs[char] += 1
    items = [CharFreqTable(char=e, freq=char_freqs[e], updatedt=datetime.now()) for e in char_freqs]
    if CharFreqTable.table_exists():
        CharFreqTable.drop_table()
    CharFreqTable.create_table()
    with db.atomic():
        CharFreqTable.bulk_create(items, batch_size=100)
    
    print('done')


    
