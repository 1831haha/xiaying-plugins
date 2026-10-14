#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""侠影插件市场对账闸门（参照 DsPlayer check_market.py 七项校验，简化版）。

发版前必跑；退出码非零 = 拒绝发布：
  1. market.json 可解析、条目 id 唯一、四要素（id/name/version/url）齐全
  2. url 指向本仓 packages/ 的包存在；packages/ 无孤儿文件
  3. 本地包 md5/size == 索引声明
  4. platforms 非空且词表内（android/win32）
  5. abis 词法：缺省 = arm64-v8a；显式 [] = 不限；词表内
  6. README 条目表：行数 == 条目数；逐行 id/版本/包名与 market.json 一致
  7. 顶层 updatedAt 存在且 ISO8601 格式合法

用法：在仓库根目录执行 python3 check_market.py
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
MARKET = os.path.join(HERE, "market.json")
README = os.path.join(HERE, "README.md")
PKGS = os.path.join(HERE, "packages")
RAW_PREFIX = "https://raw.githubusercontent.com/1831haha/xiaying-plugins/main/packages/"
VALID_PLATFORMS = {"android", "win32"}
VALID_ABIS = {"arm64-v8a", "armeabi-v7a", "x86_64", "x86"}
REQUIRED = ("id", "name", "version", "url")

fails = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(name)


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_readme_rows():
    """解析 README 条目表 → {(id): (version, 包名)}。表头：| 条目 | id | 版本 | type | 包 |"""
    rows = {}
    with open(README, encoding="utf-8") as f:
        in_table = False
        for line in f:
            s = line.strip()
            if s.startswith("### "):
                in_table = "（env）" in s or "（app）" in s
                continue
            if not in_table or not s.startswith("|"):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) < 5 or cells[0] in ("条目", "---") or set(cells[0]) <= {"-", " "}:
                continue
            val = lambda c: (re.search(r"`([^`]+)`", c) or [None, c.strip()])[1]
            rows[val(cells[1])] = (cells[2].strip(), val(cells[4]))
    return rows


def main():
    try:
        market = json.load(open(MARKET, encoding="utf-8"))
    except Exception as e:
        check("market.json 可解析", False, str(e))
        sys.exit(1)
    plugins = market.get("plugins")
    check("market.json 可解析", isinstance(plugins, list))

    ids = [p.get("id", "") for p in plugins]
    check("id 唯一", len(set(ids)) == len(ids), f"{len(ids)} 条")
    missing = [p.get("id", "?") for p in plugins
               if any(not p.get(k) for k in REQUIRED)]
    check("四要素齐全(id/name/version/url)", not missing, f"缺失：{missing}" if missing else "")

    # url → 本地包
    local = {}
    bad_url = []
    for p in plugins:
        url = p.get("url", "")
        if url.startswith(RAW_PREFIX):
            local[p["id"]] = os.path.join(PKGS, url[len(RAW_PREFIX):])
        else:
            bad_url.append(p["id"])
    check("url 指向本仓 packages/", not bad_url, f"异常：{bad_url}" if bad_url else "")
    absent = [i for i, path in local.items() if not os.path.isfile(path)]
    check("包文件存在", not absent, f"缺失：{absent}" if absent else "")
    orphans = set(os.listdir(PKGS)) - {os.path.basename(p) for p in local.values()}
    check("packages/ 无孤儿", not orphans, f"孤儿：{sorted(orphans)}" if orphans else "")

    # md5 / size
    bad_md5, bad_size = [], []
    for i, path in local.items():
        p = next(x for x in plugins if x["id"] == i)
        if os.path.isfile(path):
            if md5_of(path) != (p.get("md5") or "").lower():
                bad_md5.append(i)
            if os.path.getsize(path) != p.get("size"):
                bad_size.append(i)
    check("md5 与实测一致", not bad_md5, f"不一致：{bad_md5}" if bad_md5 else "")
    check("size 与实测一致", not bad_size, f"不一致：{bad_size}" if bad_size else "")

    # platforms / abis 词法
    bad_pf = [p["id"] for p in plugins
              if not p.get("platforms") or not set(p["platforms"]) <= VALID_PLATFORMS]
    check("platforms 词表合法", not bad_pf, f"异常：{bad_pf}" if bad_pf else "")
    bad_abi = [p["id"] for p in plugins
               if "abis" in p and not set(p["abis"]) <= VALID_ABIS]
    check("abis 词法合法", not bad_abi, f"异常：{bad_abi}" if bad_abi else "")

    # README 条目表
    try:
        rows = parse_readme_rows()
    except FileNotFoundError:
        rows = None
    if rows is None:
        check("README 条目表一致", False, "README.md 不存在")
    else:
        diff = []
        if len(rows) != len(plugins):
            diff.append(f"行数 {len(rows)} != 条目数 {len(plugins)}")
        for p in plugins:
            r = rows.get(p["id"])
            pkg = os.path.basename(local[p["id"]]) if p["id"] in local else ""
            if r is None:
                diff.append(f"{p['id']} 缺行")
            elif r[0] != p["version"] or r[1] != pkg:
                diff.append(f"{p['id']} 行内容不符（表：{r}，实际：{(p['version'], pkg)}）")
        check("README 条目表一致", not diff, "; ".join(diff))

    # updatedAt
    try:
        datetime.strptime(market.get("updatedAt", ""), "%Y-%m-%dT%H:%M:%SZ")
        check("updatedAt ISO8601 合法", True)
    except ValueError:
        check("updatedAt ISO8601 合法", False, market.get("updatedAt", ""))

    print(f"\n{'全部通过' if not fails else '失败项：' + ', '.join(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
