import os
import sys

code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../code"))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)
