import os
from pathlib import Path
from peewee import SqliteDatabase, Model, CharField, IntegerField, DateTimeField

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
        return f"<{self.id},{self.word},{self.full},{self.xhe},{self.zrm},{self.lu},{self.priority},{self.updatedt}>"


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
    freq = CharField()
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


create_tables()
