#!/usr/bin/env python3
"""把 Rime dict.yaml 码表编译成 lufly-engine 使用的紧凑二进制格式 (v2)。

用法:
    python build_dict.py [dict.yaml] [-o output.bin]

默认输入: ../rime_xiaohe_shuangpin_xiaohe_xing/xiaolu_he_shuangpin_he_xing.dict.yaml
默认输出: ../data/xiaolu_he_he.bin

二进制格式 (小端, v2):
    magic     8 bytes  "LUFLYD02"
    count     u32      条目数
    index     count * 8 bytes  内嵌索引, 每条:
        data_off  u32  记录体中的偏移
        rank      u32  (码表中的行序, 越小优先级越高)
    records   条目依次排列 (按 code 字典序; 同 code 按行序):
        code_len  u8
        code      code_len bytes (ASCII)
        text_len  u8
        text      text_len bytes (UTF-8)

引擎端整体 mmap, 条目的 (偏移, rank) 直接从内嵌索引借用, 堆上零索引。
"""
import argparse
import struct
import sys
from pathlib import Path

MAGIC = b"LUFLYD02"


def parse_dict_yaml(path: Path):
    """解析 dict.yaml, 返回 [(text, code)], 保持文件行序."""
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

    n = len(ranked)
    index = bytearray(n * 8)
    body = bytearray()
    for i, (code, text, rank) in enumerate(ranked):
        cb = code.encode("ascii")
        tb = text.encode("utf-8")
        if len(cb) > 255 or len(tb) > 255:
            raise ValueError(f"entry too long: {code!r} {text!r}")
        data_off = 12 + n * 8 + len(body)
        struct.pack_into("<II", index, i * 8, data_off, rank)
        body.append(len(cb))
        body += cb
        body.append(len(tb))
        body += tb

    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", n)
    out += index
    out += body
    return bytes(out)


def main():
    repo = Path(__file__).resolve().parent.parent.parent
    rime = repo / "rime_xiaohe_shuangpin_xiaohe_xing"
    data = Path(__file__).resolve().parent.parent / "data"

    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default=None,
                    help="单文件模式: 指定 dict.yaml（配合 -o）")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()

    if args.input or args.output:
        entries = parse_dict_yaml(Path(args.input))
        out = Path(args.output) if args.output else data / "xiaolu_he_he.bin"
        blob = build(entries)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        print(f"entries: {len(entries)}, output: {out} ({len(blob)} bytes)")
        return

    # 默认: 一次编译主码表 + 拼音辅助码表（反查用）
    targets = [
        (rime / "xiaolu_he_shuangpin_he_xing.dict.yaml",
         data / "xiaolu_he_he.bin"),
        (rime / "xiaolu_fuzhu_pinyin.dict.yaml",
         data / "xiaolu_fuzhu.bin"),
    ]
    for src, out in targets:
        entries = parse_dict_yaml(src)
        blob = build(entries)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        print(f"entries: {len(entries)}, output: {out} ({len(blob)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
