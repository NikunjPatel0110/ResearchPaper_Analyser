from backend.models.db import papers, plag_reports, ai_reports
from bson import ObjectId

# Delete all papers so fresh uploads get re-analysed with the new summariser
result = papers().delete_many({})
plag_reports().delete_many({})
ai_reports().delete_many({})
print(f"Deleted {result.deleted_count} paper(s) and related reports from DB.")
print("Re-upload your PDFs to get clean summaries.")
