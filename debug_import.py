import sys

def p(msg):
    print(msg)
    sys.stdout.flush()

p("Starting debug_import...")

p("Importing config...")
from backend.config import Config

import sys

def p(msg):
    print(msg)
    sys.stdout.flush()

p("Importing parse_service...")
from backend.services.parse_service import get_extension

p("Importing search_service...")
from backend.services.search_service import search_chunk_index

p("Importing plagiarism_service...")
from backend.services.plagiarism_service import check_plagiarism

p("Importing ai_detect_service...")
from backend.services.ai_detect_service import detect_ai_content

p("Done!")
