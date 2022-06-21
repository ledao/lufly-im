import os
import shutil
import sys
from pathlib import Path

from common import XHE_SP_SCHEMA
from generator import generate_dd

if __name__ == "__main__":

    file_name, output_dir = sys.argv[0], "dd_xiaohe_shuangpin_xiaohe_xing"

    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    schema = XHE_SP_SCHEMA
    generate_dd(XHE_SP_SCHEMA, output_dir)

    dd_dir = 'lufly/win-dd/lufly-im-v4/$码表文件/'
    if os.path.exists(dd_dir):
        shutil.rmtree(dd_dir)
    shutil.copytree(output_dir, dd_dir)

    print('done')
