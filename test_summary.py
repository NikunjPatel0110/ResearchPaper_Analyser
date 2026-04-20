import os
#added below 2 lines
from dotenv import load_dotenv
load_dotenv()
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import fitz, glob
from backend.services.nlp_service import summarise, _extract_abstract

# Pick any uploaded PDF
pdfs = glob.glob(r"uploads\**\*.pdf", recursive=True)
if not pdfs:
    print("No PDFs found!")
    exit()

pdf_path = pdfs[0]
print(f"Testing with: {pdf_path}")
doc = fitz.open(pdf_path)
text = "\n".join(page.get_text() for page in doc)
doc.close()

print(f"Total text length: {len(text)} chars")
print(f"First 500 chars:\n{text[:500]}\n")
print("---")

abstract = _extract_abstract(text)
print(f"Extracted abstract:\n{abstract}\n")
print("---")

summary = summarise(text)
print(f"Summary:\n{summary}")
