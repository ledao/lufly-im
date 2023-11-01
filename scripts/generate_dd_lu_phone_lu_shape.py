import os
import shutil
import sys
from pathlib import Path

from common import LU_SP_SCHEMA, LU_SHAPE_SCHEMA
from generator import generate_dd


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    file_name, output_dir = sys.argv[0], "dd_xiaolu_shuangpin_xiaolu_xing"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    generate_dd(LU_SP_SCHEMA, output_dir, LU_SHAPE_SCHEMA, check_db, True)

    dd_dir = 'lufly/win-dd/lufly-im-v4-xiaolu/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')


if __name__ == "__main__":
    main()