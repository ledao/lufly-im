import os
import sys
from datetime import datetime
from pathlib import Path

from common import XHE_SP_SCHEMA, XHE_SHAPE_SCHAME
from generator import generate_shouxin


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    fname, output_dir = sys.argv[0], "shouxin_xiaohe_shuangpin_xiaohe_xing"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    generate_shouxin(XHE_SP_SCHEMA, output_dir, XHE_SHAPE_SCHAME, check_db, True)

if __name__ == "__main__":
    main()