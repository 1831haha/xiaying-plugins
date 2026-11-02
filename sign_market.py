#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""侠影官方插件市场签名工具（v0.294.48 落地）。

签什么、怎么签，必须和 App 里 PluginSignature.kt 逐字对齐，否则 App 验不过：
- 插件包签名：对包文件原始字节做 SHA256withECDSA 签名，Base64 结果写
  该插件的 signature 字段；同时把包的 sha256 写进 sha256 字段（App 有
  sha256 时会同步校验，没 sha256 时跳过该项）。
- 市场索引签名：对全部插件按市场顺序拼成的规范字符串做 SHA256withECDSA
  签名，Base64 结果写 market.json 顶层的 signature 字段。规范字符串每
  插件 7 行，顺序固定为 id、version、type、url、md5、sha256、signature，
  每行后换行。注意：url 用 market.json 里的原值——官方市场 url 全是绝对
  地址，App 解析后原样不变；相对 url 的市场不要用本脚本直接签。

私钥保管铁律：
- 私钥绝不进仓库、不进聊天、不进 App。本脚本只接受 --key 指定的外部
  私钥文件，且私钥文件在仓库目录内时直接拒绝，避免手滑提交。
- ECDSA 签名每次结果都不同（随机 k），重签后 signature 字段变化是正常
  的，不要拿签名是否相同判断对错，只看验签是否通过。
- 签名流程是“先在内存里算完并自验，全部通过才写盘”：中途任何一项
  失败，market.json 一个字都不动。

用法（在仓库根目录）：
    python3 sign_market.py --key /path/to/official-market-private.pem
    python3 sign_market.py --key /path/to/official-market-private.pem --check-only
发版顺序：先签好 market.json 并推上线，再发带公钥的 App——旧版 App
（公钥未配置）读带签名的市场只警告不拦截，所以先推市场是安全的；
反过来先发 App、市场还没签，官方插件安装会被新版 App 拒绝。

依赖：openssl 命令行（签名与自验都走它，与 Java 的 SHA256withECDSA
DER 签名格式一致）。
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MARKET = os.path.join(HERE, "market.json")
PKGS = os.path.join(HERE, "packages")
RAW_PREFIX = "https://raw.githubusercontent.com/1831haha/xiaying-plugins/main/packages/"


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd, input_bytes=None):
    r = subprocess.run(cmd, input=input_bytes, capture_output=True)
    if r.returncode != 0:
        fail(f"命令失败 {' '.join(cmd)}：{r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_bytes(key_path, data):
    """openssl dgst 签名，返回 Base64(DER)。"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        der = run(["openssl", "dgst", "-sha256", "-sign", key_path, tmp])
    finally:
        os.unlink(tmp)
    return base64.b64encode(der).decode()


def sign_file(key_path, path):
    with open(path, "rb") as f:
        data = f.read()
    return sign_bytes(key_path, data)


def verify_bytes(pub_pem, data, sig_b64):
    """openssl 自验：通过返回 True，失败返回 False（不直接退出，留给调用方汇总）。"""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(data)
        data_tmp = f.name
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(base64.b64decode(sig_b64))
        sig_tmp = f.name
    try:
        r = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", pub_pem, "-signature", sig_tmp, data_tmp],
            capture_output=True,
        )
        return r.returncode == 0
    finally:
        os.unlink(data_tmp)
        os.unlink(sig_tmp)


def canonical_text(plugins):
    """必须和 PluginSignature.canonicalMarketText 逐字一致。"""
    out = []
    for p in plugins:
        for field in ("id", "version", "type", "url", "md5", "sha256", "signature"):
            out.append(str(p.get(field) or ""))
    return "".join(line + "\n" for line in out)


def main():
    ap = argparse.ArgumentParser(description="签名侠影官方市场 market.json")
    ap.add_argument("--key", required=True, help="EC P-256 私钥 PEM 文件（必须在仓库外）")
    ap.add_argument("--check-only", action="store_true", help="只验现有签名，不改写 market.json")
    args = ap.parse_args()

    key_path = os.path.abspath(args.key)
    if not os.path.isfile(key_path):
        fail(f"私钥文件不存在：{key_path}")
    if os.path.commonpath([key_path, HERE]) == HERE:
        fail("私钥文件在仓库目录内，拒绝使用：请把私钥放仓库外保管")
    pub_pem = run(["openssl", "ec", "-in", key_path, "-pubout", "-outform", "PEM"])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as f:
        f.write(pub_pem)
        pub_tmp = f.name

    try:
        market = json.load(open(MARKET, encoding="utf-8"))
        plugins = market.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            fail("market.json 里没有 plugins 数组")

        if args.check_only:
            ok = True
            for p in plugins:
                url = p.get("url", "")
                if not url.startswith(RAW_PREFIX):
                    print(f"[SKIP] {p.get('id')}：url 不是本仓 packages/，不验包签名")
                    continue
                path = os.path.join(PKGS, os.path.basename(url))
                good = bool(p.get("signature")) and verify_bytes(
                    pub_tmp, open(path, "rb").read(), p["signature"]
                )
                print(f"[{'PASS' if good else 'FAIL'}] 包签名 {p.get('id')}")
                ok = ok and good
            top = market.get("signature", "")
            good_top = bool(top) and verify_bytes(
                pub_tmp, canonical_text(plugins).encode("utf-8"), top
            )
            print(f"[{'PASS' if good_top else 'FAIL'}] 索引签名")
            sys.exit(0 if (ok and good_top) else 1)

        # 1. 包签名 + sha256（先算，不写盘）
        for p in plugins:
            url = p.get("url", "")
            if not url.startswith(RAW_PREFIX):
                fail(f"{p.get('id')}：url 不是本仓 packages/，无法定位本地包签名")
            path = os.path.join(PKGS, os.path.basename(url))
            if not os.path.isfile(path):
                fail(f"{p.get('id')}：本地包不存在：{path}")
            if md5_of(path) != (p.get("md5") or "").lower():
                fail(f"{p.get('id')}：本地包 md5 与索引声明不一致，先修 market.json 再签")
            if os.path.getsize(path) != p.get("size"):
                fail(f"{p.get('id')}：本地包 size 与索引声明不一致，先修 market.json 再签")
            p["sha256"] = sha256_of(path)
            p["signature"] = sign_file(key_path, path)

        # 2. 索引签名（用填好 sha256/signature 后的最终值拼规范串）
        market["signature"] = sign_bytes(key_path, canonical_text(plugins).encode("utf-8"))

        # 3. 自验全部通过才写盘
        for p in plugins:
            url = p["url"]
            path = os.path.join(PKGS, os.path.basename(url))
            if not verify_bytes(pub_tmp, open(path, "rb").read(), p["signature"]):
                fail(f"{p['id']}：包签名自验失败，不写盘")
        if not verify_bytes(pub_tmp, canonical_text(plugins).encode("utf-8"), market["signature"]):
            fail("索引签名自验失败，不写盘")

        with open(MARKET, "w", encoding="utf-8") as f:
            json.dump(market, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已签名 {len(plugins)} 个插件 + 索引，market.json 已更新")
        for p in plugins:
            print(f"  {p['id']} sha256={p['sha256'][:12]}… sig={p['signature'][:20]}…")
    finally:
        os.unlink(pub_tmp)


if __name__ == "__main__":
    main()
