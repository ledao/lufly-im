from peewee import *

db = SqliteDatabase("/home/ledao/projects/py_workspace/lufly-im/lufly/sys_data/sys_table.sqlitedb")

class BaseModel(Model):
    class Meta:
        database = db


class CharPhoneTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = FixedCharField(2)
    phones = FixedCharField(2)
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class CharPhoneShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    char = FixedCharField(2)
    phones = FixedCharField(2)
    priority = IntegerField()
    updatedt = DateTimeField("%Y-%m-%d %H:%M:%S")


class WordPhoneTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    phones = CharField()
    priority = IntegerField()
    updatedt = DateField("%Y-%m-%d %H:%M:%S")


class WordPhoneShapeTable(BaseModel):
    id = IntegerField(primary_key=True)
    word = CharField()
    phones = CharField()
    priority = IntegerField()
    updatedt = DateField("%Y-%m-%d %H:%M:%S")


def create_tables():
    if not CharPhoneTable.table_exists():
        CharPhoneTable.create_table()
    if not CharPhoneShapeTable.table_exists():
        CharPhoneShapeTable.create_table()
    if not WordPhoneTable.table_exists():
        WordPhoneTable.create_table()
    if not WordPhoneShapeTable.table_exists():
        WordPhoneShapeTable.create_table()

create_tables()

