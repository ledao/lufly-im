from typing import Dict

from common import split_sy, get_full_to_bingji_transformer, BINGJI_SP_SCHEMA, check_words_pinyin, check_chars_pinyin
from tables import db, CharPhoneTable, WordPhoneTable


def check_bingji_char(transformer: Dict[str, str]):
    check_chars_pinyin(transformer, BINGJI_SP_SCHEMA)


def check_bingji_word(transformer: Dict[str, str]):
    check_words_pinyin(transformer, BINGJI_SP_SCHEMA)


def main():
    full_to_bingji_transformer = get_full_to_bingji_transformer()
    check_bingji_char(full_to_bingji_transformer)
    check_bingji_word(full_to_bingji_transformer)
    print("done")


if __name__ == "__main__":
    main()
