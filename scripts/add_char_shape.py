import sys
from datetime import datetime

from tables import db, CharHeShapeTable


def load_chars(filepath: str):
    exist_chars = set()
    for e in CharHeShapeTable.select():
        exist_chars.add(e.char)

    chars = []
    with open(filepath, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if len(line) == 0: continue
            cols = line.split(" ")
            if len(cols) != 2:
                print(f"{line} broken")
                continue
            if cols[0] in exist_chars:
                print(f"{line} exists already")
                continue
            chars.append(CharHeShapeTable(
                char=cols[0],
                shapes=cols[1],
                priority=1,
                updatedt=datetime.now(),
            ))
            exist_chars.add(cols[0])

    return chars


def main():
    if len(sys.argv) != 2:
        print(f"使用方法: python3 {sys.argv[0]} chars.txt", file=sys.stderr)
        print("文件行格式:char shape")
        print("举例:你 rx")
        sys.exit(1)

    _, chars_path = sys.argv

    add_chars = load_chars(chars_path)
    print(add_chars)
    with db.atomic():
        CharHeShapeTable.bulk_create(add_chars, batch_size=100)

    print('done')


if __name__ == "__main__":
    main()
