import os
import json
from pprint import pprint

# Connect to db
from pymongo import MongoClient
from bson import ObjectId

# Load config
from backend.config import Config

print("Testing Plagiarism Detection DB...")

client = MongoClient(Config.MONGO_URI)
db = client.paperiq
papers_coll = db.papers
plag_coll = db.plag_reports

# Get all papers
all_papers = list(papers_coll.find({}, {"title": 1, "status": 1}))
print("Total papers in DB:", len(all_papers))
for p in all_papers:
    print(p)

pid_to_test = "69de80765eaea0b6d2dcf706"
for p in all_papers:
    if p["_id"] == ObjectId(pid_to_test):
        print(f"Testing against {p['title']}")
        break

print(f"\nTesting against pid: {pid_to_test}")

from backend.services.plagiarism_service import check_plagiarism

res, status = check_plagiarism(pid_to_test)
print(f"Status: {status}")
print("Response keys:", list(res.keys()))
if "data" in res and res["data"]:
    data = res["data"]
    print("overall_score:", data.get("overall_similarity") or data.get("overall_score"))
    print("matches:", len(data.get("matches") or data.get("flagged_chunks") or []))
    if data.get("matches"):
        print("First match:")
        pprint(data["matches"][0])
    elif data.get("flagged_chunks"):
        print("First flagged chunk:")
        pprint(data["flagged_chunks"][0])
else:
    print("Error:", res.get("error"))

