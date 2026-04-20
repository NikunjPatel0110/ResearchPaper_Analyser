import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import sys
try:
    import backend.app
    print("Backend imported successfully with KMP_DUPLICATE_LIB_OK=TRUE!")
except Exception as e:
    print(f"Exception caught during import: {e}")

print("Reached end of test")
