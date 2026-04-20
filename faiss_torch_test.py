import sys
def p(msg):
    print(msg)
    sys.stdout.flush()

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

p("Importing FAISS...")
import faiss

p("Importing Torch...")
import torch

p("Done!")
