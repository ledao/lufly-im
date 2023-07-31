import os
import shutil
import sys
from pathlib import Path

from generator import generate_dd, XHE_SHAPE_SCHAME
from common import ZRM_SP_SCHEMA


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    fname, output_dir = sys.argv[0], "dd_ziranma_shuangpin_xiaohe_xing"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    generate_dd(ZRM_SP_SCHEMA, output_dir, XHE_SHAPE_SCHAME, check_db, True)

    dd_dir = 'lufly/win-dd/lufly-im-v4-ziranma/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')


if __name__ == "__main__":
    main()
