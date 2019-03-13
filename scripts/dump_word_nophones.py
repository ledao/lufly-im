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

        word_phones = []
        for line in fin:
            line = line.strip()
            if line == "" or line.startswith(";"):
                continue
            word = "".join([e for e in line if e not in "abcdefghijklmnopqrstuvwxyz"])
            if len(word) > 3: 
                continue
            
            phones = []
            for char in word:
                if char not in char_to_phones:
                    print(f"A: {char} no phones")
                    break
                phones.append(char_to_phones[char])
            
            if len(phones) != len(word):
                continue
            
            if len(phones) == 2:
                for c1 in phones[0]:
                    for c2 in phones[1]:
                        word_phones.append((word, f"{c1}{c2}"))
            elif len(phones) == 3:
                for c1 in phones[0]:
                    for c2 in phones[1]:
                        for c3 in phones[2]:
                            word_phones.append((word, f"{c1}{c2}{c3}"))
            else:
                print(f"{word} {phones} lenght great than 3, exiting...")
                sys.exit(1)
            
        to_add_items = [] 
        exist_items = set()
        for (word, phones) in word_phones:
            if f"{word}{phones}" in exist_items:
                continue
            if len(phones) != len(word)*2:
                print(f"D: {word} {phones} wrong.")
                continue
            num = WordPhoneTable.select().where(WordPhoneTable.word == word, WordPhoneTable.phones == phones).count()
            if num > 0:
                continue
            to_add_items.append(WordPhoneTable(word=word, phones=phones, priority=1, updatedt=datetime.now()))
            exist_items.add(f"{word}{phones}")
            # WordPhoneTable(word=word, phones=phones, priority=1, updatedt=datetime.now()).save()
        print(f"add length {len(to_add_items)}")
        with db.atomic():
            WordPhoneTable.bulk_create(to_add_items, batch_size=100)
    print('done')
    pass

