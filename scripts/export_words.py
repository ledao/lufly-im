from tables import db, WordPhoneTable

def export_words():
    with open("words.txt", "w", encoding="utf-8") as f:
        f.write("word\tfull\tpriority\txhe\tzrm\tlu\tbingji\n")
        for item in WordPhoneTable.select():
            f.write(item.word + "\t" + item.full + "\t" + str(item.priority) + "\t" + item.xhe + "\t" + item.zrm + "\t" + item.lu + "\t" + item.bingji +"\n")

if __name__ == '__main__':
    export_words()
