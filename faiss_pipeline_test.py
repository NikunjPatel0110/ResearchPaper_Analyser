import sys
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

def p(msg):
    print(msg)
    sys.stdout.flush()

p("Importing FAISS...")
import faiss

p("Importing Torch...")
import torch

p("Importing Pipeline...")
from transformers import pipeline

p("Done!")
