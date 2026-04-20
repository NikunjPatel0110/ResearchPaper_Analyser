import sys
import traceback

try:
    import backend.app
    print("Backend imported successfully!")
except Exception as e:
    print(f"Exception caught during import: {e}")
    traceback.print_exc()
except BaseException as be:
    print(f"BaseException caught: type {type(be)}")
    traceback.print_exc()

print("Reached end of app_test.py")
