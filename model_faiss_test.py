import sys
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

def p(msg):
    print(msg)
    sys.stdout.flush()

p("Importing Spacy + ST...")
from sentence_transformers import SentenceTransformer

p("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

p("Importing FAISS...")
import faiss

p("Done!")
