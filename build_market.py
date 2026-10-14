#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xiaying-plugins 发版构建：重打包（补 plugin.json）+ 图标 + market.json。
铁律：同名包绝不覆盖重传——内容变化必升版本换文件名。"""
import hashlib
import json
import os
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PKGS = os.path.join(HERE, "packages")
ICONS = os.path.join(HERE, "icons")
FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # 固定时间戳 → 同内容同 md5
RAW = "https://raw.githubusercontent.com/1831haha/xiaying-plugins/main"

os.makedirs(ICONS, exist_ok=True)


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repack(src_zip, dst_name, extra_files):
    """解旧包 → 追加 extra_files{arcname: bytes} → 固定时间戳重打包。"""
    dst = os.path.join(PKGS, dst_name)
    stage = {}
    with zipfile.ZipFile(os.path.join(PKGS, src_zip)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            stage[info.filename] = z.read(info.filename)
    stage.update(extra_files)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(stage):
            zi = zipfile.ZipInfo(name, FIXED_DATE)
            zi.create_system = 3
            zi.external_attr = (0o644 << 16)
            z.writestr(zi, stage[name])
    os.remove(os.path.join(PKGS, src_zip))  # 删旧版本包（git 历史留档）
    return dst


def make_icon(path, letter, c1, c2):
    from PIL import Image, ImageDraw
    s = 192
    img = Image.new("RGB", (s, s), c1)
    d = ImageDraw.Draw(img)
    for i in range(s):  # 纵向渐变
        r = i / s
        d.line([(0, i), (s, i)],
               fill=tuple(int(c1[k] + (c2[k] - c1[k]) * r) for k in range(3)))
    d.ellipse([s * 0.28, s * 0.28, s * 0.72, s * 0.72],
              fill=(255, 255, 255, 40), outline=(255, 255, 255))
    d.text((s / 2, s / 2), letter, fill=(255, 255, 255), anchor="mm")
    img.save(path)


# 1. 图标
make_icon(f"{ICONS}/market.png", "侠", (20, 24, 48), (88, 60, 180))
make_icon(f"{ICONS}/btsow-source.png", "搜", (24, 48, 40), (40, 140, 110))
make_icon(f"{ICONS}/magnet-stream.png", "播", (48, 28, 60), (150, 70, 190))

def manifest(**kw):
    return json.dumps(kw, ensure_ascii=False, indent=2).encode()


btsow_zip = repack("btsow-source-1.0.1.zip", "btsow-source-1.0.2.zip", {
    "plugin.json": manifest(
        id="btsow-source", name="BTSOW 磁力搜索", version="1.0.2",
        type="source", platforms=["android", "win32"],
        abis=["arm64-v8a"], desc="BTSOW 磁力搜索 PY 爬虫源"),
})
magnet_zip = repack("magnet-stream-1.0.4.zip", "magnet-stream-1.0.5.zip", {
    "plugin.json": manifest(
        id="magnet-stream", name="磁力转播服务", version="1.0.5",
        type="server", platforms=["android", "win32"],
        abis=["arm64-v8a"], desc="磁力链接转 HTTP 视频流服务"),
})

# 3. market.json（DsPlayer 兼容 schema）
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
market = {
    "logo": "icons/market.png",
    "name": "侠影官方插件市场",
    "desc": "侠影 App 内置「插件市场」的数据源（兼容 DsPlayer 市场协议）",
    "updatedAt": now,
    "plugins": [
        {
            "id": "btsow-source",
            "name": "BTSOW 磁力搜索",
            "author": "侠影",
            "desc": "BTSOW 磁力搜索 PY 爬虫源：站内 JSON 接口搜片，拿磁链",
            "version": "1.0.2",
            "type": "source",
            "engine": "py",
            "size": os.path.getsize(btsow_zip),
            "url": f"{RAW}/packages/btsow-source-1.0.2.zip",
            "icon": "icons/btsow-source.png",
            "tags": ["搜索", "磁力"],
            "changelog": "v1.0.2：补 plugin.json manifest（id/version/type/platforms），供安装时一致性校验；图标上架。",
            "md5": md5_of(btsow_zip),
            "platforms": ["android", "win32"],
            "category": "app",
            "minApp": "0.22.0",
            "abis": ["arm64-v8a"],
        },
        {
            "id": "magnet-stream",
            "name": "磁力转播服务",
            "author": "侠影",
            "desc": "把磁力链接转成 HTTP 视频流，供播放器直接播放",
            "version": "1.0.5",
            "type": "server",
            "engine": "nodejs",
            "size": os.path.getsize(magnet_zip),
            "url": f"{RAW}/packages/magnet-stream-1.0.5.zip",
            "icon": "icons/magnet-stream.png",
            "tags": ["服务", "磁力"],
            "changelog": "v1.0.5：补 plugin.json manifest，供安装时一致性校验；图标上架。",
            "md5": md5_of(magnet_zip),
            "platforms": ["android", "win32"],
            "category": "env",
            "minApp": "0.22.0",
            "abis": ["arm64-v8a"],
        },
    ],
}
with open(os.path.join(HERE, "market.json"), "w", encoding="utf-8") as f:
    json.dump(market, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("market.json 已生成：", now)
print("btsow:", os.path.basename(btsow_zip), md5_of(btsow_zip))
print("magnet:", os.path.basename(magnet_zip), md5_of(magnet_zip))
