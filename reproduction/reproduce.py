"""Entry point shipped at the root of the offline reproduction bundle."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'runner'))
from runtime import main

if __name__ == '__main__':
    main(Path(__file__).resolve().parent)
