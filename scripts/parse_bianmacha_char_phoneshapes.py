import sys

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USAGE: python3 parse_bianmacha_char_phoneshapes.py bianmacha.txt char_phoneshapes.txt")
        sys.exit(1)
    _, bianmacha_path, char_phoneshapes_path = sys.argv
    
    char_pses = set()
    with open(bianmacha_path, 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if line == '' or '● ' in line: continue
            if line[1] == '：':
                cols = line.split("：")
                char = cols[0].strip()
                pses = list(filter(lambda e: e != '' and len(e) >= 4, cols[1].replace('*','').split(' ')))[1:]
                print(char)
                print(pses)
                for ps in pses:
                    item = f'{char}\t{ps}'
                    if item in char_pses:
                        continue
                    else:
                        char_pses.add(item)
    
    print(len(char_pses))

    with open(char_phoneshapes_path, 'w', encoding='utf8') as fout:
        for ps in char_pses:
            fout.write(f'{ps}\n')
    print('done')