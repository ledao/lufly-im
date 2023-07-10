from tables import CharPhoneTable

def export_words():
    with open("chars.txt", "w", encoding="utf-8") as f:
        f.write("word\tfull\tpriority\txhe\tzrm\tlu\tbingji\n")
        for item in CharPhoneTable.select():
            f.write(item.char + "\t" + item.full + "\t" + str(item.priority) + "\t" + item.xhe + "\t" + item.zrm + "\t" + item.lu + "\t" + item.bingji +"\n")

if __name__ == '__main__':
    export_words()
