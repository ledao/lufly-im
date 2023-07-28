from datetime import datetime

from tables import db, CharZrmShapeTable


def main():
    result = []
    with open("ZRM_Aux-code_4.3.txt", "r", encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == '' or line.startswith('#'): continue
            cols = line.split("=")
            if len(cols) != 2:
                raise Exception(f"format error: {line}")
            char = cols[0]
            shapes = cols[1]
            if len(shapes) != 2:
                continue
            
            result.append(CharZrmShapeTable(char=char, shapes=shapes, priority=1, updatedt=datetime.now()))

    with db.atomic():
        CharZrmShapeTable.bulk_create(result, batch_size=100)

    print('done')


if __name__ == "__main__":
    main()