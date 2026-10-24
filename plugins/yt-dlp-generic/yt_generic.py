"""yt-dlp 通用解析 wrapper（侠影插件 yt-dlp-generic 1.0.0）。

只做通用提取：调用方（ParseApi type=99）传视频页地址，返回可播直链或空串。
硬边界：以下站点的地址在 import yt_dlp 之前就拦截，绝不交给 yt-dlp：
youtube.com、youtu.be、twitter.com、x.com、instagram.com、twitch.tv（含子域名）。
yt_dlp 本体是全量包（972 个提取器模块），裁剪会破坏 extractor/__init__ 的
全量 import，故不裁剪，改由本 wrapper 的域名黑名单在功能层拦截。
"""

_BLOCKED = ("youtube.com", "youtu.be", "twitter.com", "x.com", "instagram.com", "twitch.tv")


def _blocked(url):
    try:
        host = url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0].lower()
    except Exception:
        return True
    return any(host == d or host.endswith("." + d) for d in _BLOCKED)


def _pick(info):
    """从 extract_info 结果挑一条可播直链：顶层 url 优先，否则挑带音视频的最高格式。"""
    if not isinstance(info, dict):
        return ""
    url = info.get("url")
    if isinstance(url, str) and url:
        return url
    entries = info.get("entries")
    if isinstance(entries, list) and entries:
        for entry in entries:
            got = _pick(entry)
            if got:
                return got
        return ""
    formats = info.get("formats")
    if not isinstance(formats, list):
        return ""
    cands = [f for f in formats
             if isinstance(f, dict) and isinstance(f.get("url"), str) and f["url"]]
    if not cands:
        return ""

    def combined(f):
        return f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")

    pool = [f for f in cands if combined(f)] or cands
    pool.sort(key=lambda f: (f.get("height") or 0), reverse=True)
    return pool[0]["url"]


def resolve(url, timeout=30):
    """解析视频页地址为可播直链；被拦截、失败、未装 yt_dlp 时一律返回空串，不抛。"""
    if not isinstance(url, str) or not url or _blocked(url):
        return ""
    try:
        from yt_dlp import YoutubeDL
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "cachedir": False,
            "socket_timeout": timeout,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return _pick(info)
    except Exception:
        return ""
