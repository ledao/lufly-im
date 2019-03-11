import os, sys

from lufly.models.tables import CharPhoneTable, CharShapeTable, WordPhoneTable

if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("USAGE: python3 generate_dd_txt.py sys_words_table.txt")
        sys.exit(1)

    fname, sys_words_table = sys.argv

    items = {}
    char_to_shape = {}
    for item in CharShapeTable.select():
        if item.char in char_to_shape:
            print(f"M: {item.char} multiply shapes.")
            continue
        else:
            char_to_shape[item.char] = item.shapes
    print(f"total {len(char_to_shape)} char shapes")

    for item in CharPhoneTable.select():
        charphone = f'{item.char}\t{item.phones}'
        # if charphone in items:
        #     print(f"M: {charphone} multiply items in charphonetable")
        #     continue
        # else:
        #     items[charphone] = 60000
        
        if item.char not in char_to_shape:
            print(f"A: {item.char} has no shapes in charphonetable")
            continue
        else:
            items[f"{item.char}\t{item.phones+char_to_shape[item.char]}"] = 40000
    
    for item in WordPhoneTable.select():
        wordphones = f"{item.word}\t{item.phones}"
        # if wordphones in items:
        #     print(f"M: {wordphones} multiply items in wordphonetable")
        #     continue
        # else:
        #     items[wordphones] = 30000
        
        first_char = item.word[0]
        last_char = item.word[-1]
        if first_char not in char_to_shape:
            print(f"A: {first_char} has no shapes in wordphonetable")
            continue
        elif last_char not in char_to_shape:
            print(f"A: {last_char} has no shapes in wordshapetable")
            continue
        else:
            items[f"{item.word}\t{item.phones+char_to_shape[first_char]+char_to_shape[last_char]}"] = 20000

    with open(sys_words_table, 'w', encoding='utf8') as fout:
        for item in items.items():
            fout.write(f"{item[0]}#序{item[1]}\n")
    
    print('done')