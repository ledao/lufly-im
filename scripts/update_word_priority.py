import sys, os
from lufly.models.tables import db, WordPhoneTable, CharFreqTable

if __name__ == "__main__":
    char_freqs = {}
    for char_freq in CharFreqTable.select():
        char_freqs[char_freq.char] = int(char_freq.freq)
    
    for word in WordPhoneTable.select():
        nums = [char_freqs[e] for e in word.word if e in char_freqs]
        if len(nums) == 0:
            continue
        word.priority = int(sum(nums) / len(nums))
        word.save()
    print('done')