import sys, os
from collections import defaultdict
from datetime import datetime
from lufly.models.tables import db, WordPhoneTable, CharPhoneTable

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USAGE: python3 dump_word_nophones.py word.txt")
        sys.exit(1)

    _, word_txt_path = sys.argv

    char_to_phones = defaultdict(list)
    for item in CharPhoneTable.select():
        if item.phones not in char_to_phones[item.char]:
            char_to_phones[item.char].append(item.phones)
    
    with open(word_txt_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == "" or line.startswith(";"):
                continue
            word = "".join([e for e in line if e not in "abcdefghijklmnopqrstuvwxyz"])
            if len(word) > 2: 
                continue
            
            phones = []
            for char in word:
                if char not in char_to_phones:
                    print(f"A: {char} no phones")
                    break
                phones.append(char_to_phones[char][0])
            phones = ''.join(phones)
            num = WordPhoneTable.select().where(WordPhoneTable.word == word, WordPhoneTable.phones == phones).count()
            if num > 0:
                continue
            WordPhoneTable(word=word, phones=phones, priority=1, updatedt=datetime.now()).save()
            
    print('done')
    pass

