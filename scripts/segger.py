from typing import List, Set


class Segger(object):
    def __init__(self, words: Set[str], max_len: int=5):
        super(Segger).__init__()
        self.words: Set[str] = words
        self.max_len: int = max_len

    def cut(self, sent: str)-> List[str]:
        index = 0
        segments = []
        while index < len(sent):
            find = False
            for l in range(self.max_len, 0, -1):
                word = sent[index:index+l]
                if word in self.words:
                    segments.append(word)
                    index += l
                    find = True
                    break
            if not find:
                segments.append(sent[index])
                index += 1
                
        return segments


if __name__ == "__main__":
    segger = Segger(set(["abc", "de"]), 3)
    print(segger.cut("abcde"))