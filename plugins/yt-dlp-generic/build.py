#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打 yt-dlp 通用解析包（yt-dlp-generic 1.0.0）。

从 PyPI 取钉选版 wheel（2026.10.21），解进 staging/pylibs/，与 wrapper
yt_generic.py、plugin.json 一起打成 market 包 packages/yt-dlp-generic-1.0.0.zip。
全量 yt_dlp 包不裁剪（裁剪会破坏 extractor/__init__ 全量 import），
功能层拦截由 yt_generic.py 的域名黑名单负责。
zip 内文件时间统一压到 2026-01-01（与 py-deps 包同款可复现风格）。
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PIN = "2026.10.21"
WHEEL = "yt_dlp-%s-py3-none-any.whl" % PIN
WHEEL_SIZE = 3188012
WHEEL_SHA256 = "94a3a3e2c423129d0bbd2f1be000c4171fa1226c29e251c84aff868f2851c247"
OUT = os.path.join(ROOT, "packages", "yt-dlp-generic-1.0.0.zip")
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_wheel():
    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/%s/json" % PIN, timeout=60) as r:
        meta = json.load(r)
    url = next(u["url"] for u in meta["urls"] if u["filename"] == WHEEL)
    tmp = os.path.join(tempfile.gettempdir(), WHEEL)
    urllib.request.urlretrieve(url, tmp)
    size = os.path.getsize(tmp)
    digest = sha256_of(tmp)
    if size != WHEEL_SIZE or digest != WHEEL_SHA256:
        raise SystemExit("wheel 校验失败：size=%d sha256=%s" % (size, digest))
    return tmp


def main():
    wheel = fetch_wheel()
    staging = tempfile.mkdtemp(prefix="ytdlp-generic-")
    pylibs = os.path.join(staging, "pylibs")
    try:
        with zipfile.ZipFile(wheel) as z:
            z.extractall(pylibs)
        shutil.copy(os.path.join(HERE, "yt_generic.py"), os.path.join(pylibs, "yt_generic.py"))
        shutil.copy(os.path.join(HERE, "plugin.json"), os.path.join(staging, "plugin.json"))
        with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as out:
            for base, _dirs, files in os.walk(staging):
                for name in sorted(files):
                    full = os.path.join(base, name)
                    arc = os.path.relpath(full, staging)
                    info = zipfile.ZipInfo(arc, FIXED_DATE)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with open(full, "rb") as f:
                        out.writestr(info, f.read())
        print("built %s (%d bytes, md5 %s)" % (
            OUT, os.path.getsize(OUT), hashlib.md5(open(OUT, "rb").read()).hexdigest()))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
