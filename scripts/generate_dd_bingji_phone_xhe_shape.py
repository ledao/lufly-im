import os
import shutil
import sys
from pathlib import Path

from generator import generate_dd
from common import BINGJI_SP_SCHEMA

if __name__ == "__main__":
    file_name, output_dir = sys.argv[0], "dd_bingji_shuangpin_xiaohe_xing"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    generate_dd(BINGJI_SP_SCHEMA, output_dir)

    dd_dir = 'lufly/win-dd/lufly-im-v4/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')
