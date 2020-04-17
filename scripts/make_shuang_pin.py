"""
作者：ledao
日期：20200325
邮箱：790717479@qq.com
q群：958293407
"""

from typing import *
from dataclasses import dataclass
import json
import os, sys


@dataclass
class KeyDetail(object):
    name: str
    hand: str  # "L" or "R"
    from_key: str
    location: Tuple[float, float]


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


def load_yun_infos(yun_info_file: str) -> List[Dict]:
    with open(yun_info_file, 'r', encoding='utf8') as fin:
        return json.loads(fin.read())


def load_pre_locked_yuns() -> Dict[str, str]:
    return {
        "i": "I",
        "e": "E",
        "u": "U",
        "a": "A",
        "o_uo": "O",
        "v_ui": "V",
    }


def load_jointed_yuns() -> List[Tuple]:
    return [
        ("uai", "king"),
        ("iang", "uang"),
        ("o", "uo"),
        ("v", "ui"),
        ("ia", "ua"),
        ("iong", "uong")
    ]


def get_yun_info(yun_name: str, yun_details: List[Dict]) -> Dict:
    for detail in yun_details:
        if detail['name'] == yun_name:
            return detail

    return None


def get_yun_shengs_info(yun_name: str, neighbors: List[str], yun_details: List[Dict]):
    yun_info = get_yun_info(yun_name, yun_details)
    if yun_info is None:
        print(f'{yun_name} do not have sheng infos. It is a series error, exiting...')
        sys.exit(1)
    print(yun_info)
    neighbors_info = [get_yun_info(e, yun_details) for e in neighbors]
    if None in neighbors_info:
        print(f"{neighbors[neighbors_info.find(None)]} do not have shengs. It is a series error, exiting...")
        sys.exit(1)
    print(neighbors)
    # TODO:


def generate_drafts(yun_details: List[Dict], manual_yuns: Dict[str, str], neighbors: Dict[str, List[str]]):
    drafts = []
    for yun in yun_details:
        yun_name = yun['name']
        if yun_name in manual_yuns:
            print(f"yun: {yun_name} manually selected.")
            drafts.append(Draft(key_name=manual_yuns[yun_name], yuns=[yun_name]))
        else:
            print(f"process yun: {yun_name}")
            if yun_name in neighbors:
                print(f"{yun_name} has neighbor: {neighbors[yun_name]}, merge shengs info.")
                # TODO:
            print(f'get {yun_name} shengs info')
            shengs = get_yun_shengs_info(yun_name, [], yun_details)
            # TODO:
            sys.exit(1)


def get_yun_info(yun_infos: List[Dict], yun: str) -> Union[Dict, None]:
    for info in yun_infos:
        if yun == info['name']:
            return info
    return None


def merge_jointed_yuns_info(yun_infos: List[Dict], jointed_yuns: List[Tuple[str, str]]) -> List[Dict]:
    for yuns in jointed_yuns:
        yun1 = yuns[0]
        yun2 = yuns[1]
        name = yun1 + "_" + yun2
        yun1_info = get_yun_info(yun_infos, yun1)
        yun2_info = get_yun_info(yun_infos, yun2)
        index = yun1_info['index'] if yun1_info['index'] <= yun2_info['index'] else yun2_info['index']
        raw_shengs = []
        raw_shengs.extend(yun1_info['shengs'])

    pass


if __name__ == "__main__":
    keys = load_keys()
    yun_infos = load_yun_infos("yun_details.json")
    manual_yuns = load_pre_locked_yuns()
    jointed_yuns = load_jointed_yuns()
    yun_infos = merge_jointed_yuns_info(yun_infos, jointed_yuns)
    # generate_drafts(yun_details, manual_yuns, neighbors)
