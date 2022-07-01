from typing import Dict

from tables import db, CharPhoneTable, WordPhoneTable
from common import get_full_to_lu_transformmer, split_sy, LU_SP_SCHEMA, check_words_pinyin, check_chars_pinyin


def check_lu_char(transformer: Dict[str, str]):
    check_chars_pinyin(transformer, LU_SP_SCHEMA)


def check_lu_word(transformer: Dict[str, str]):
    check_words_pinyin(transformer, LU_SP_SCHEMA)


def main():
    full_to_lu_transformer = get_full_to_lu_transformmer()
    check_lu_char(full_to_lu_transformer)
    check_lu_word(full_to_lu_transformer)
    print("done")


if __name__ == "__main__":
    main()
