
from datetime import datetime
from collections import defaultdict
from tables import CharZrmShapeTable, CharHeShapeTable, CharLuEditShapeTable, db

def main():
    he_all_shapes = defaultdict(list)
    for item in CharHeShapeTable.select():
        he_all_shapes[item.char].append(item)

    zrm_all_shapes = defaultdict(list)
    for item in CharZrmShapeTable.select():
        zrm_all_shapes[item.char].append(item)

    lu_all_shapes = []
    for char in he_all_shapes:
        he_char_shapes = he_all_shapes[char]
        if char in zrm_all_shapes:
            for zrm_char_shapes in zrm_all_shapes[char]:
                lu_all_shapes.append(CharLuEditShapeTable(
                    id = len(lu_all_shapes),
                    char=char,
                    shapes=zrm_char_shapes.shapes,
                    he_shapes=he_char_shapes[0].shapes,
                    zrm_shapes=zrm_char_shapes.shapes,
                    priority= 1 if he_char_shapes[0].priority is None else he_char_shapes[0].priority,
                    updatedt=datetime.now(),
                ))   
        else:
            for he_char_shape in he_char_shapes:
                lu_all_shapes.append(CharLuEditShapeTable(
                    id = len(lu_all_shapes),
                    char=char,
                    shapes=he_char_shape.shapes,
                    he_shapes=he_char_shape.shapes,
                    zrm_shapes="",
                    priority=1 if he_char_shape.priority is None else he_char_shape.priority,
                    updatedt=datetime.now(),
                ))

    print(lu_all_shapes)
    with db.atomic():
        CharLuEditShapeTable.bulk_create(lu_all_shapes, batch_size=10)



if __name__ == "__main__":
    main()
