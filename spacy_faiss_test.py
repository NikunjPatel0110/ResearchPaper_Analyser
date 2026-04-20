import sys
def p(msg):
    print(msg)
    sys.stdout.flush()

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

p("Importing Spacy...")
import spacy

p("Importing SentenceTransformer...")
from sentence_transformers import SentenceTransformer

p("Importing FAISS...")
import faiss

p("Done!")
