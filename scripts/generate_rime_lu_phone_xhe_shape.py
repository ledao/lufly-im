import sys

from tables import *
from generator import *

if __name__ == "__main__":

    fname, output_dir = sys.argv[0], "rime_lu_shuangpin_lu_xing"
    if not Path(output_dir).exists():
        os.makedirs(output_dir)

    schema_config = SchemaConfig(
        schema_id="xiaolu_lu_shuangpin_he_xing",
        name="小鹭:鹭拼:鹤形:方案",
        version=datetime.datetime.now().strftime('%Y%m%d.%H%M%S'),
        authors=[
            "ledao <790717479@qq.com>"
        ],
        description="简单舒适音形方案",
        auto_select_pattern="^\w{6}$|^\w{8}$|^\w{10}$|^\w{12}$|^\w{14}$|^\w{16}$|^\w{18}$",
        shuangpin_schema=LU_SP_SCHEMA,
    )

    generate_rime(schema_config, output_dir)
