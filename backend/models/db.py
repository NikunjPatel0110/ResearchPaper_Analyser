from pymongo import MongoClient
from backend.config import Config

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(Config.MONGO_URI)
    return _client.get_default_database()

def get_collection(name):
    return get_db()[name]

# Collection shortcuts
def users():       return get_collection("users")
def invites():     return get_collection("invite_codes")
def papers():      return get_collection("papers")
def embeddings():  return get_collection("embeddings")
def comparisons(): return get_collection("comparisons")
def plag_reports():return get_collection("plagiarism_reports")
def ai_reports():  return get_collection("ai_detection_reports")


