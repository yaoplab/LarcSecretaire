import os
import sys

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from LarcSecretaire.main import main

if __name__ == "__main__":
    main()
