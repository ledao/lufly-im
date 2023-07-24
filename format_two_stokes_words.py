from pypinyin import lazy_pinyin

def get_sheng_from_py(py: str):
    if len(py) == 0:
        raise RuntimeError("py should not be empty")

    if py.startswith('zh'):
        return 'v'
    elif py.startswith('ch'):
        return 'i'
    elif py.startswith('sh'):
        return 'u'
    else:
        return py[0]

def main():
    words = []
    with open("original_two_strokes_words.txt", 'r', encoding='utf8') as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue

            line = line.split()
            words.extend(line)
    print(words)
    print(len(words))

    with open("two_strokes_words.txt", 'w', encoding='utf8') as fout:
        for word in words:
            py = lazy_pinyin(word)
            first_sheng = get_sheng_from_py(py[0])
            second_sheng = get_sheng_from_py(py[1])
            fout.write(word + " " + first_sheng + second_sheng + '\n')


if __name__ == '__main__':
    main()