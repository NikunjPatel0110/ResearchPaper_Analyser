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

p("Calling torch.cuda.is_available()...")
print(torch.cuda.is_available())

p("Done!")
