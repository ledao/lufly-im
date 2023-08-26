import os
import datetime
from pathlib import Path
from peewee import SqliteDatabase, Model, CharField, IntegerField, DateTimeField, BooleanField

pwd = Path(__file__).parent

db = SqliteDatabase(str(Path(pwd) / "../lufly/sys_data/sys_table.sqlite"))


class BaseModel(Model):
    class Meta:
        database = db


class CharPhoneTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    xhe = CharField()
    full = CharField()
    zrm = CharField()
    lu = CharField()
    bingji = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.char},{self.xhe},{self.full},{self.zrm},{self.lu},{self.bingji},{self.priority},{self.updatedt}>"


class CharHeShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    shapes = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.char},{self.shapes},{self.priority},{self.updatedt}>"


class CharLuShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    shapes = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.char},{self.shapes},{self.priority},{self.updatedt}>"


class CharLuEditShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    shapes = CharField()
    he_shapes = CharField()
    zrm_shapes = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.char},{self.shapes},{self.he_shapes},{self.zrm_shapes},{self.priority},{self.updatedt}>"


class CharZrmShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    shapes = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.char},{self.shapes},{self.priority},{self.updatedt}>"


class WordPhoneTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    full = CharField()
    xhe = CharField()
    zrm = CharField()
    lu = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")
    bingji = CharField()

    def __str__(self):
        return f"<{self.id},{self.word},{self.full},{self.xhe},{self.zrm},{self.lu},{self.priority},{self.updatedt},{self.bingji}>"


class FullToTwoTable(BaseModel):
    id = IntegerField(primary_key=True)
    full = CharField()
    xhe = CharField()
    zrm = CharField()
    lu = CharField()
    bingji = CharField()


class CharFreqTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = CharField()
    freq = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class DelWordTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class EngWordTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField(unique=True)
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class YeFengWordTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    py = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class SimplerTable(BaseModel):
    id = IntegerField(primary_key=True)
    keys = CharField()
    words = CharField()
    priority = IntegerField()
    create_date = DateTimeField("%Y-%m-%d %H:%M:%S",
                                default=datetime.datetime.now())

    def __str__(self):
        return f"<{self.id},{self.keys},{self.words},{self.priority},{self.create_date}>"


class TangshiTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    full = CharField()
    xhe = CharField()
    zrm = CharField()
    lu = CharField()
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")
    bingji = CharField()

    def __str__(self):
        return f"<{self.id},{self.word},{self.full},{self.xhe},{self.zrm},{self.lu},{self.priority},{self.updatedt},{self.bingji}>"


class TwoStrokesWordsTable(BaseModel):
    id = IntegerField(primary_key=True, column_name="id")
    word = CharField()
    encode = CharField()
    is_first = BooleanField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return f"<{self.id},{self.word},{self.encode},{self.is_first},{self.updatedt}>"


def create_tables():
    if not CharPhoneTable.table_exists():
        CharPhoneTable.create_table()
    if not CharHeShapeTable.table_exists():
        CharHeShapeTable.create_table()
    if not CharLuShapeTable.table_exists():
        CharLuShapeTable.create_table()
    if not WordPhoneTable.table_exists():
        WordPhoneTable.create_table()
    if not FullToTwoTable.table_exists():
        FullToTwoTable.create_table()
    if not CharFreqTable.table_exists():
        CharFreqTable.create_table()
    if not DelWordTable.table_exists():
        DelWordTable.create_table()
    if not EngWordTable.table_exists():
        EngWordTable.create_table()
    if not YeFengWordTable.table_exists():
        YeFengWordTable.create_table()
    if not SimplerTable.table_exists():
        SimplerTable.create_table()
    if not TangshiTable.table_exists():
        TangshiTable.create_table()
    if not TwoStrokesWordsTable.table_exists():
        TwoStrokesWordsTable.create_table()
    if not CharZrmShapeTable.table_exists():
        CharZrmShapeTable.create_table()
    if not CharLuEditShapeTable.table_exists():
        CharLuEditShapeTable.create_table()

create_tables()
