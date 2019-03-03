import sys, os
from datetime import datetime
from lufly.models.tables import db, CharPhoneTable

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 dump_char_phone_table.py char_phone.txt")
        sys.exit(1)
    
    _, char_phone_path = sys.argv
    with open(char_phone_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            cols = line.split('\t')
            if len(cols) != 2:
                print(f"ERROR line {line} in file {char_phone_path}")
                continue
            cols = list(map(lambda e: e.strip(), cols))
            exit_num = CharPhoneTable.select().where(CharPhoneTable.char == cols[0], CharPhoneTable.phones == cols[1]).count()
            if exit_num > 0:
                print(f"WARNING: char phone already exists, {line}")
                continue
            else:
                CharPhoneTable(char=cols[0], phones=cols[1], priority=1, updatedt=datetime.now()).save()
    print('done')    
    pass

