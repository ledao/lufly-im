import sys
from typing import Dict, List, Tuple

from common import get_full
from tables import CharPhoneTable, WordPhoneTable, db


def load_char_phones() -> Dict[str, List[str]]:
    result = {}
    for item in CharPhoneTable.select():
        if item.char in result:
            result[item.char].append(item.full)
        else:
            result[item.char] = [item.full]
    return result


def update_word_full(char_phones: Dict[str, List[str]]):
    to_update_items = []
    for item in WordPhoneTable.select():
        words: str = item.word
        full: str = item.full
        if len(words) == len(full.split(' ')):
            continue
        if full == '':
            full = ' '.join(get_full(words))
            item.full = full
            to_update_items.append(item)
            continue

        words_candidate_fulls: List[List[str]] = []
        for char in words:
            if char not in char_phones:
                print(f"{char} not in phone table")
                continue
                # FIXME:
                # raise RuntimeError(f"{char} in phone table")
            else:
                words_candidate_fulls.append(sorted(char_phones[char], key=lambda e: -len(e)))
        full_arr: List[Tuple[List[str], str]] = []
        for word_candidate_fulls in words_candidate_fulls:
            if len(full_arr) <= 0:  # 第一个字
                for candidate_full in word_candidate_fulls:
                    if full.startswith(candidate_full):
                        full_arr.append(([candidate_full], full[len(candidate_full):]))
            else:
                broken_segments = []
                this_full_arr: List[Tuple[List[str], str]] = []
                for pre_segment in full_arr:
                    next_full = pre_segment[1]
                    for candidate_full in word_candidate_fulls:
                        if next_full.startswith(candidate_full):
                            this_segments = []
                            this_segments.extend(pre_segment[0])
                            this_segments.append(candidate_full)
                            this_next_full = next_full[len(candidate_full):]
                            this_full_arr.append((this_segments, this_next_full))
                full_arr = this_full_arr
        full_arr = [e for e in full_arr if len(e[0]) > 0 and e[1] == '']
        if  len(full_arr) != 1:
            print(f"wrong format: {item}, {full_arr}")
            # FIXME:
            # raise RuntimeError(f"get full pinyin fails, {item}")
        else:
            item.full = ' '.join(full_arr[0][0])
            to_update_items.append(item)

    if len(to_update_items) > 0:
        print(f"total have {len(to_update_items)} items to update")
        with db.atomic():
            WordPhoneTable.bulk_update(to_update_items,
                                       fields=['full'],
                                       batch_size=100)
    print("done")


def main():
    char_phones = load_char_phones()
    update_word_full(char_phones)

    pass


if __name__ == '__main__':
    main()
