import sys
from datetime import datetime
import tables
import common


def load_chars(filepath: str):
    exist_charpinyins = common.get_exists_charyinpins()

    chars = []
    shapes = []
    with open(filepath, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if len(line) == 0: continue
            cols = line.split(" ")
            if len(cols) < 2:
                print(f"{line} broken")
                continue

            pinyin = None
            priority = 1
            if len(cols) == 2:
                char = cols[0]
                shape = cols[1]
            elif len(cols) == 3:
                char = cols[0]
                shape = cols[1]
                pinyin = cols[2]
            elif len(cols) == 4:
                char = cols[0]
                shape = cols[1]
                pinyin = cols[2]
                priority = int(cols[3])
            else:
                print(f"broken line {line}")
                continue

            if common.contain_alpha(word=char) or common.contain_alpha(word=char):
                print(f"broken line {line}")
                continue
            if len(char) != 1:
                print(f"broken line {line}")
                continue
            if shape is None or not shape.isalpha():
                print(f"broken line {line}")
                continue
            if pinyin is not None and not pinyin.isalpha():
                print(f"broken line {line}")
                continue
            if pinyin is None:
                pinyin = ''.join(common.get_full(char))
            if priority is None or priority < 1:
                priority = 1

            if char + pinyin in exist_charpinyins:
                print(f"already exists {line}")
                continue
            exist_charpinyins.add(char+pinyin)
            chars.append(tables.CharPhoneTable(
                char=char,
                full=pinyin,
                xhe='',
                lu='',
                zrm='',
                bingji='',
                priority=priority,
                updatedt=datetime.now(),
            ))
            shapes.append(tables.CharHeShapeTable(
                char=char,
                shapes=shape,
                priority=priority,
                updatedt=datetime.now(),
            ))

    with tables.db.atomic():
        tables.CharHeShapeTable.bulk_create(shapes, batch_size=100)
    print(f"add he shape: {shapes}")
    print(f"add he shape num: {len(shapes)}")

    with tables.db.atomic():
        tables.CharPhoneTable.bulk_create(chars, batch_size=100)
    print(f"add char phone: {chars}")
    print(f"add char phone num: {len(chars)}")


def main():
    if len(sys.argv) != 2:
        print(f"使用方法: python3 {sys.argv[0]} chars.txt", file=sys.stderr)
        print("文件行格式:char shape [pinyin priority]")
        print("举例:你 rx ni 1")
        print("多音字请写多行")
        sys.exit(1)

    _, chars_path = sys.argv

    add_chars = load_chars(chars_path)

    print('done')


if __name__ == "__main__":
    main()
