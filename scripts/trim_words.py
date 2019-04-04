from toolz.curried import pipe, map
from tables import db, DelWordTable, WordPhoneTable

if __name__ == "__main__":
    
    del_words = pipe(DelWordTable.select(),
        map(lambda e: e.word),
        set
    )

    num = WordPhoneTable.select().where(WordPhoneTable.word.in_(del_words)).count()
    print(f"total {num} items to delete")
    WordPhoneTable.delete().where(WordPhoneTable.word.in_(del_words)).execute()

    print("done")
