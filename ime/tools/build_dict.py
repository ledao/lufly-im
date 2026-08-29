#!/usr/bin/env python3
"""把 Rime dict.yaml 码表编译成 lufly-engine 使用的紧凑二进制格式。

用法:
    python build_dict.py [dict.yaml] [-o output.bin]

默认输入: ../rime_xiaolu_shuangpin_xiaolu_xing/xiaolu_lu_shuangpin_lu_xing.dict.yaml
默认输出: ../data/xiaolu_lu_lu.bin

二进制格式 (小端):
    magic     8 bytes  "LUFLYD01"
    count     u32      条目数
    条目 (按 code 字典序排列):
        code_len  u8
        code      code_len bytes (ASCII)
        text_len  u8
        text      text_len bytes (UTF-8)
        rank      u32  (码表中的行序, 越小优先级越高)
"""
import argparse
import struct
import sys
from pathlib import Path

MAGIC = b"LUFLYD01"


def parse_dict_yaml(path: Path):
    """解析 dict.yaml, 返回 [(text, code, rank)], 保持文件行序."""
    entries = []
    in_data = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not in_data:
            # 数据段从 "..."(YAML 文档结束符) 之后开始
            if line.strip() == "...":
                in_data = True
            continue
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        text, code = parts[0].strip(), parts[1].strip()
        if not text or not code:
            continue
        entries.append((text, code))
    return entries


def build(entries):
    # 按 code 排序; 同 code 保持文件行序(rank)
    ranked = [(code, text, rank) for rank, (text, code) in enumerate(entries)]
    ranked.sort(key=lambda e: (e[0], e[2]))

    buf = bytearray()
    buf += MAGIC
    buf += struct.pack("<I", len(ranked))
    for code, text, rank in ranked:
        cb = code.encode("ascii")
        tb = text.encode("utf-8")
        if len(cb) > 255 or len(tb) > 255:
            raise ValueError(f"entry too long: {code!r} {text!r}")
        buf.append(len(cb))
        buf += cb
        buf.append(len(tb))
        buf += tb
        buf += struct.pack("<I", rank)
    return bytes(buf)


def main():
    repo = Path(__file__).resolve().parent.parent.parent
    default_in = repo / "rime_xiaolu_shuangpin_xiaolu_xing" / "xiaolu_lu_shuangpin_lu_xing.dict.yaml"
    default_out = Path(__file__).resolve().parent.parent / "data" / "xiaolu_lu_lu.bin"

    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default=str(default_in))
    ap.add_argument("-o", "--output", default=str(default_out))
    args = ap.parse_args()

    entries = parse_dict_yaml(Path(args.input))
    data = build(entries)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"entries: {len(entries)}, output: {out} ({len(data)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
