import sys

from tables import YeFengWordTable


def filter_word(word: str) -> bool:
    if len(word) <= 2 or len(word) > 5:
        return False
    if "了" in word or\
       "一" in word or\
       "二" in word or\
       "三" in word or\
       "四" in word or\
       "五" in word or\
       "六" in word or\
       "七" in word or\
       "八" in word or\
       "九" in word or\
       "十" in word or\
       "与" in word or\
       "〇" in word or\
       "是" in word or\
       "而" in word or\
       "却" in word or\
       "不太" in word or\
       "着" in word or\
       "个" in word or\
       "在" in word or\
       "吗" in word or\
       "呢" in word or\
       "啊" in word or\
       "不" in word or\
       "且" in word or\
       "为" in word or\
       "乃" in word or\
       "得" in word or\
       "了" in word or\
       "么" in word or\
       "他" in word or\
       "她" in word or\
       "的" in word or\
       "地" in word or\
       "上" in word or\
       "下" in word or\
       "和" in word or\
       "以" in word or\
       "从" in word or\
       "于" in word or\
       word.endswith("儿") or\
       "你" in word:
        return False
    return True


if __name__ == "__main__":
    with open("yefeng_words.txt", 'w', encoding='utf8') as fout:
        for item in YeFengWordTable.raw('''
SELECT * FROM yefengwordtable 
WHERE 
	length(word) > 2
	and length(word) <=5 
    AND priority > 1 
	AND word NOT LIKE '%了%' 
	AND word NOT LIKE '%一%'
	AND word NOT LIKE '%二%'
	AND word NOT LIKE '%三%'
	AND word NOT LIKE '%四%'
	AND word NOT LIKE '%五%'
	AND word NOT LIKE '%六%'
	AND word NOT LIKE '%七%'
	AND word NOT LIKE '%八%'
	AND word NOT LIKE '%九%'
	AND word NOT LIKE '%与%'
	AND word NOT LIKE '%〇%'
	AND word NOT LIKE '%是%'
	AND word NOT LIKE '%而%'
	AND word NOT LIKE '%却%'
	AND word NOT LIKE '%不太%'
	AND word NOT LIKE '%着%'
	AND word NOT LIKE '%个%'
	AND word NOT LIKE '%在%'
	AND word NOT LIKE '%吗%'
	AND word NOT LIKE '%呢%'
	AND word NOT LIKE '%啊%'
	AND word NOT LIKE '%不%'
	AND word NOT LIKE '%且%'
	AND word NOT LIKE '%为%'
	AND word NOT LIKE '%乃%'
	AND word NOT LIKE '%也%'
	AND word NOT LIKE '%得%'
	AND word NOT LIKE '%了%'
	AND word NOT LIKE '%么%'
	AND word NOT LIKE '%他%'
	AND word NOT LIKE '%她%'
	AND word NOT LIKE '%的%'
	AND word NOT LIKE '%地%'
	AND word NOT LIKE '%上%'
	AND word NOT LIKE '%下%'
	AND word NOT LIKE '%和%'
	AND word NOT LIKE '%以%'
	AND word NOT LIKE '%从%'
	AND word NOT LIKE '%你%'
	and word NOT IN (SELECT word FROM wordphonetable) ORDER BY word;
        ''').execute():
            print(item.word, item.py, item.priority)
            pys = item.py.split("'")
            if len(item.word) != len(pys):
                print("format error: ", item.word, item.py)
                continue

            phones = []
            for py in pys:
                if len(py) == 0:
                    continue
                if len(py) == 1:
                    phones.append(py + py)
                else:
                    phones.append(py)

            fout.write(f"{item.word} {item.priority} {' '.join(phones)}\n")
