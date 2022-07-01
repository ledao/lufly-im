from common import *
from tables import db


def check_zrm_char(transformer: Dict[str, str]):
    check_chars_pinyin(transformer, ZRM_SP_SCHEMA)


def check_zrm_word(transformer: Dict[str, str]):
    check_words_pinyin(transformer, ZRM_SP_SCHEMA)


def main():
    full_to_zrm_transformer = get_full_to_zrm_transformmer()
    check_zrm_char(full_to_zrm_transformer)
    check_zrm_word(full_to_zrm_transformer)
    print("done")


if __name__ == "__main__":
    main()
