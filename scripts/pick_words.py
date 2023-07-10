
def main():
    words = []
    # with open("words.txt", "r", encoding='utf8') as f:
    #     for line in f:
    #         line = line.strip()
    #         if len(line) == 0 or line[0] == "#":
    #             continue
    #         cols = line.split("\t")
    #         words.append(cols[0])
    
    with open("chars.txt", 'r', encoding='utf8') as f:
        for line in f:
            line = line.strip()
            if len(line) == 0 or line[0] == "#":
                continue
            cols = line.split("\t")
            words.append(cols[0])

    with open("all_words.txt", "w", encoding='utf8') as f:
        for word in words:
            f.write(word + "\n")


if __name__ == "__main__":
    main()