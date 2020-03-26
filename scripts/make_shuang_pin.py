"""
作者：ledao
日期：20200325
邮箱：790717479@qq.com
q群：958293407
"""

from typing import *
from dataclasses import dataclass


@dataclass 
class KeyDetail(object):
    name: str
    hand: str # "L" or "R"
    from_key: str
    location: Tuple[float, float]


@dataclass 
class ShengNum(object):
    name: str
    index: int
    num: int


@dataclass    
class YunDetail(object):
    name: str
    index: int
    shengs: List[ShengNum] # 按SHengNum.index由小到大排序


def load_keys() -> Dict[str, KeyDetail]:
    return {
        'Q': KeyDetail(name="Q", hand="L", from_key="A", location=(0.0, 0.0)),
        'W': KeyDetail(name="W", hand="L", from_key="S", location=(1.0, 0.0)),
        'E': KeyDetail(name="E", hand="L", from_key="D", location=(2.0, 0.0)),
        'R': KeyDetail(name="R", hand="L", from_key="F", location=(3.0, 0.0)),
        'T': KeyDetail(name="T", hand="L", from_key="F", location=(4.0, 0.0)),
        'Y': KeyDetail(name="Y", hand="R", from_key="J", location=(5.0, 0.0)),
        'U': KeyDetail(name="U", hand="R", from_key="J", location=(6.0, 0.0)),
        'I': KeyDetail(name="I", hand="R", from_key="K", location=(7.0, 0.0)),
        'O': KeyDetail(name="O", hand="R", from_key="L", location=(8.0, 0.0)),
        'P': KeyDetail(name="P", hand="R", from_key="L", location=(9.0, 0.0)),

        'A': KeyDetail(name="A", hand="L", from_key="A", location=(0.5, 1.0)),
        'S': KeyDetail(name="S", hand="L", from_key="S", location=(1.5, 1.0)),
        'D': KeyDetail(name="D", hand="L", from_key="D", location=(2.5, 1.0)),
        'F': KeyDetail(name="F", hand="L", from_key="F", location=(3.5, 1.0)),
        'G': KeyDetail(name="G", hand="L", from_key="F", location=(4.5, 1.0)),
        'H': KeyDetail(name="H", hand="R", from_key="J", location=(5.5, 1.0)),
        'J': KeyDetail(name="J", hand="R", from_key="J", location=(6.5, 1.0)),
        'K': KeyDetail(name="K", hand="R", from_key="K", location=(7.5, 1.0)),
        'L': KeyDetail(name="L", hand="R", from_key="L", location=(8.5, 1.0)),
        
        'Z': KeyDetail(name="Z", hand="L", from_key="A", location=(1.0, 2.0)),
        'X': KeyDetail(name="X", hand="L", from_key="D", location=(2.0, 2.0)),
        'C': KeyDetail(name="C", hand="L", from_key="F", location=(3.0, 2.0)),
        'V': KeyDetail(name="V", hand="L", from_key="F", location=(4.0, 2.0)),
        'B': KeyDetail(name="B", hand="L", from_key="F", location=(5.0, 2.0)),
        'N': KeyDetail(name="N", hand="R", from_key="J", location=(6.0, 2.0)),
        'M': KeyDetail(name="M", hand="R", from_key="J", location=(7.0, 2.0)),
    }


if __name__ == "__main__":
    keys = load_keys()
    print(keys)
