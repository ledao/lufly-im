from tables import TwoStrokesWordsTable, db
from datetime import datetime

def main():
    items = [] 
    with open("two_strokes_words.txt", 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            cols = line.split()
            if len(cols) != 2:
                print(f"invalid line: {line}")
                continue
            word = cols[0]
            encode = cols[1]
            is_first = True 
            items.append(TwoStrokesWordsTable(word=word, encode=encode, is_first=is_first, updatedt=datetime.now()))
    print(items, len(items))

    with db.atomic():
        TwoStrokesWordsTable.bulk_create(items, batch_size=100)


if __name__ == '__main__':
    main()