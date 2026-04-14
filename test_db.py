import json
from bson import ObjectId
from pymongo import MongoClient

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

docs = list(MongoClient('mongodb://localhost:27017/paperiq').get_default_database().papers.find({'title': '1706.03762v7'}, {'summary': 1, 'keywords': 1}))
with open('db_out.json', 'w', encoding='utf-8') as f:
    json.dump(docs, f, cls=JSONEncoder)
