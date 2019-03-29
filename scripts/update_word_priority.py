import sys, os
from typing import List
from lufly.models.tables import db, WordPhoneTable, CharFreqTable

def mean(lst: List[int]) -> int:
    if len(lst) == 0:
        return 1
    else:
        return int(sum(lst)/len(lst))
    

if __name__ == "__main__":
    char_freqs = {}
    for char_freq in CharFreqTable.select():
        char_freqs[char_freq.char] = int(char_freq.freq)

    
    # WordPhoneTable.update(priority= mean([char_freqs[e] for e in WordPhoneTable.word])).where(WordPhoneTable.priority == 1).execute()
    
    for word in WordPhoneTable.select().where(WordPhoneTable.priority == 1):
        nums = [char_freqs[e] for e in word.word if e in char_freqs]
        if len(nums) == 0:
            continue
        word.priority = int(sum(nums) / len(nums))
        word.save()
    print('done')