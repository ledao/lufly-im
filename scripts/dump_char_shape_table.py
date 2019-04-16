import sys, os
from datetime import datetime
from tables import db, CharShapeTable

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 dump_char_shape_table.py char_shape.txt")
        sys.exit(1)
    
    _, char_shape_path = sys.argv
    with open(char_shape_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == "":
                continue
            cols = line.split('\t')
            if len(cols) != 2:
                print(f"ERROR line {line} in file {char_shape_path}")
                continue
            cols = list(map(lambda e: e.strip(), cols))
            exit_num = CharShapeTable.select().where(CharShapeTable.char == cols[0], CharShapeTable.shapes == cols[1]).count()
            if exit_num > 0:
                print(f"WARNING: char shape already exists, {line}")
                continue
            else:
                CharShapeTable(char=cols[0], shapes=cols[1], priority=1, updatedt=datetime.now()).save()
    print('done')    
    pass

