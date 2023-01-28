import os
import sys
from datetime import datetime
from pathlib import Path

from common import SchemaConfig, ZRM_SP_SCHEMA, PINYIN_SCHEMA
from generator import generate_rime


def main():
    _, output_dir = sys.argv[0], "rime_ziranma_shuangpin_xiaohe_xing"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    std_schema_config = SchemaConfig(
        schema_id="xiaolu_zrm_shuangpin_he_xing",
        name="小鹭音形系列·自然码双拼+小鹤双形",
        version=datetime.now().strftime('%Y%m%d.%H%M%S'),
        authors=[
            "ledao <790717479@qq.com>"
        ],
        description="简单舒适音形方案",
        auto_select_pattern="^\w{6}$|^\w{8}$|^\w{10}$|^\w{12}$|^\w{14}$|^\w{16}$|^\w{18}$",
        input_schema=ZRM_SP_SCHEMA,
        reverse_dict="xiaolu_fuzhu_pinyin",
    )
    generate_rime(std_schema_config, output_dir)

    assistant_schema_config = SchemaConfig(
        schema_id="xiaolu_fuzhu_pinyin",
        name="小鹭音形系列·拼音辅助",
        version=datetime.now().strftime('%Y%m%d.%H%M%S'),
        authors=[
            "ledao <790717479@qq.com>"
        ],
        description="简单舒适音形方案·辅助方案",
        auto_select_pattern="",
        input_schema=PINYIN_SCHEMA,
        check_db=False,
    )
    generate_rime(assistant_schema_config, output_dir)


if __name__ == "__main__":
    main()
