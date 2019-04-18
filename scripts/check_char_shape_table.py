import sys
from tables import db, CharShapeTable
from toolz.curried import pipe, map, filter
from common import for_each



if __name__ == "__main__":
    null_lu_shape_items = pipe(CharShapeTable.select().where(CharShapeTable.lu_shapes == ''),
        list,
    )
    if len(null_lu_shape_items) != 0:
        print(f"{len(null_lu_shape_items)} null lushape items.", file=sys.stderr)
        sys.exit(1)
    del null_lu_shape_items

    lu_shape_ne_xhe_items = pipe(CharShapeTable.select().where(CharShapeTable.shapes != CharShapeTable.lu_shapes),
        list
    )
    if len(lu_shape_ne_xhe_items) != 0:
        print(f"{len(lu_shape_ne_xhe_items)} lu shape != xhe shapes.", file=sys.stderr)
        pipe(lu_shape_ne_xhe_items,
            for_each(lambda e: print(e)),
        )

    print("done") 
    