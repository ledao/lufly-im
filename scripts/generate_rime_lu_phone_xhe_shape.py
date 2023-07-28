import os
import sys
from datetime import datetime
from pathlib import Path

from common import SchemaConfig, LU_SP_SCHEMA, PINYIN_SCHEMA
from generator import generate_rime


def main():
    check_db = len(sys.argv) > 1 and sys.argv[1] == "check"

    fname, output_dir = sys.argv[0], "rime_xiaolu_shuangpin_xiaohe_xing"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    std_schema_config = SchemaConfig(
        schema_id="xiaolu_lu_shuangpin_he_xing",
        name="小鹭音形·鹭拼+鹤形",
        version=datetime.now().strftime('%Y%m%d.%H%M%S'),
        authors=[
            "ledao <790717479@qq.com>"
        ],
        description="简单舒适音形方案",
        auto_select_pattern="^\w{6}$|^\w{8}$|^\w{10}$|^\w{12}$|^\w{14}$|^\w{16}$|^\w{18}$",
        input_schema=LU_SP_SCHEMA,
        reverse_dict="xiaolu_fuzhu_pinyin",
        check_db=check_db,
    )
    generate_rime(std_schema_config, output_dir)

    assistant_schema_config = SchemaConfig(
        schema_id="xiaolu_fuzhu_pinyin",
        name="小鹭音形·拼音辅助",
        version=datetime.now().strftime('%Y%m%d.%H%M%S'),
        authors=[
            "ledao <790717479@qq.com>"
        ],
        description="小鹭拼音辅助",
        auto_select_pattern="",
        input_schema=PINYIN_SCHEMA,
        check_db=False,
    )
    generate_rime(assistant_schema_config, output_dir)


if __name__ == "__main__":
    main()