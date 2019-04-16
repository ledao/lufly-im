import sys, os
from datetime import datetime
from typing import Dict
from tables import db, WordPhoneShapeTable

def read_shapes(shape_path: str) -> Dict[str, str]:
    char_shapes = {}
    with open(shape_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            cols = line.split('\t')
            if cols[0] in char_shapes:
                print(f"WARNING: multiply char {cols[0]} with shapes, {cols[1]} {char_shapes[cols[0]]}")
                continue
            char_shapes[cols[0]] = cols[1]
    print("donw reading  char shapes")
    return char_shapes


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USAGE: python3 dump_word_phone_shape_table.py word_phone.txt char_shape.txt")
        sys.exit(1)
    
    _, word_phone_path, char_shape_path = sys.argv
    char_shapes = read_shapes(char_shape_path)
    print(f"we get {len(char_shapes)} char shapes")

    with open(word_phone_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            cols = line.split('\t')
            if len(cols) != 2:
                print(f"ERROR line {line} in file {word_phone_path}")
                continue
            cols = list(map(lambda e: e.strip(), cols))
            first_word = cols[0][0]
            last_word = cols[0][-1]

            if first_word not in char_shapes or last_word not in char_shapes:
                print(f"{cols[0]} have none shapes, drop it")
                continue

            exit_num = WordPhoneShapeTable.select().where(WordPhoneShapeTable.word == cols[0], WordPhoneShapeTable.phoneshapes == cols[1]+char_shapes[first_word][0]+char_shapes[last_word][-1]).count()
            if exit_num > 0:
                print(f"WARNING: char phoneshape already exists, {line}")
                continue
            else:
                WordPhoneShapeTable(word=cols[0], phoneshapes=cols[1]+char_shapes[first_word][0]+char_shapes[last_word][-1], priority=1, updatedt=datetime.now()).save()
    print('done')    
    pass

