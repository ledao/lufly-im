import os
import sys
from datetime import datetime
from pathlib import Path

from common import SchemaConfig, LU_SP_SCHEMA, PINYIN_SCHEMA, LU_SHAPE_SCHEMA
from generator import generate_shouxin


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    fname, output_dir = sys.argv[0], "shouxin_xiaolu_shuangpin_xiaolu_xing"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    generate_shouxin(LU_SP_SCHEMA, output_dir, LU_SHAPE_SCHEMA, check_db, True)

if __name__ == "__main__":
    main()