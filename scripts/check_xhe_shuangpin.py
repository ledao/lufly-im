from typing import Dict

from common import split_sy, get_full_to_xhe_transformer, XHE_SP_SCHEMA, check_words_pinyin, check_chars_pinyin
from tables import db, WordPhoneTable, CharPhoneTable


def check_xhe_char(transformer: Dict[str, str]):
    check_chars_pinyin(transformer, XHE_SP_SCHEMA)


def check_xhe_word(transformer: Dict[str, str]):
    check_words_pinyin(transformer, XHE_SP_SCHEMA)


def main():
    full_to_xhe_transformer = get_full_to_xhe_transformer()
    check_xhe_char(full_to_xhe_transformer)
    check_xhe_word(full_to_xhe_transformer)
    print("done")


if __name__ == "__main__":
    main()
