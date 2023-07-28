import os
import shutil
import sys
from pathlib import Path

from common import XHE_SP_SCHEMA, XHE_SHAPE_SCHAME
from generator import generate_dd


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    file_name, output_dir = sys.argv[0], "dd_xiaohe_shuangpin_xiaohe_xing"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    schema = XHE_SP_SCHEMA
    generate_dd(XHE_SP_SCHEMA, output_dir, XHE_SHAPE_SCHAME, check_db)

    dd_dir = 'lufly/win-dd/lufly-im-v4-xiaohe/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')


if __name__ == "__main__":
    main()
