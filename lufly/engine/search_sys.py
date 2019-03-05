from typing import List
from lufly.models.tables import CharPhoneTable
from lufly.models.tables import CharPhoneShapeTable
from lufly.models.tables import WordPhoneTable
from lufly.models.tables import WordPhoneShapeTable


class QResult(object):
    def __init__(self, word: str, phones: str, priority: int):
        super(QResult, self).__init__()
        self.word = word
        self.phones = phones
        self.priority = priority

    def __str__(self):
        return f"<{self.word},{self.phones},{self.priority}>"


class Searcher(object):
    def __init__(self):
        super(Searcher, self).__init__()
    
    def query_char_phones(self, q: str) -> List[QResult]:
        return sorted([QResult(e.char, e.phones, e.priority) for e in CharPhoneTable.select().where(CharPhoneTable.phones % f"{q}*")], key=lambda e: e.priority, reverse=True)
            
    def query_char_phone_shapes(self, q: str) -> List[QResult]:
        return sorted([QResult(e.char, e.phoneshapes, e.priority) for e in CharPhoneShapeTable.select().where(CharPhoneShapeTable.phoneshapes % f"{q}*")], key=lambda e: e.priority, reverse=True)

    def query_word_phones(self, q: str) -> List[QResult]:
        return sorted([QResult(e.word, e.phones, e.priority) for e in WordPhoneTable.select().where(WordPhoneTable.phones % f"{q}*")], key=lambda e: e.priority, reverse=True)

    def query_word_phone_shapes(self, q: str) -> List[QResult]:
        return sorted([QResult(e.word, e.phoneshapes, e.priority) for e in WordPhoneShapeTable.select().where(WordPhoneShapeTable.phoneshapes % f"{q}*")], key=lambda e: e.priority, reverse=True)

