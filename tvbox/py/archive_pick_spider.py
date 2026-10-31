# -*- coding: utf-8 -*-
"""
今天看什么 PY 源（侠影）：Internet Archive 公版老电影/动画随机抽片
每次刷新随机翻到不同页 → 推荐都不一样；详情附一句「每日一句」（hitokoto）。
接口：archive.org advancedsearch + metadata；播放 archive.org/download 直链 mp4。
内容均为 Internet Archive 公有领域/公开授权馆藏。
"""
import random
import urllib.parse

# @header({"title": "今天看什么", "searchable": 1, "quickSearch": 0, "filterable": 0})


class Spider:
    UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
    COLS = {
        "random": ("🎲 随机惊喜", "collection:(feature_films OR animationandcartoons OR SciFi_Horror OR silent_films OR classic_tv) AND year:[1900 TO 1989]"),
        "feature": ("经典老电影", "collection:feature_films"),
        "cartoon": ("复古动画", "collection:animationandcartoons AND year:[1900 TO 1979]"),
        "scifi": ("科幻恐怖", "collection:SciFi_Horror"),
        "silent": ("默片时代", "collection:silent_films"),
        "tv": ("怀旧电视", "collection:classic_tv"),
    }

    def getName(self):
        return "今天看什么"

    def init(self, extend=""):
        self.headers = {"User-Agent": self.UA}
        self._total = {}

    def _json(self, url, params=None):
        try:
            import requests
            return requests.get(url, params=params, headers=self.headers, timeout=15).json()
        except Exception:
            return {}

    def _search(self, q, page, rows=24):
        j = self._json("https://archive.org/advancedsearch.php", {
            "q": q + " AND mediatype:movies", "fl[]": ["identifier", "title", "year"],
            "rows": rows, "page": page, "output": "json"})
        r = j.get("response") or {}
        return r.get("numFound", 0), [{
            "vod_id": d["identifier"],
            "vod_name": d.get("title") if isinstance(d.get("title"), str) else d["identifier"],
            "vod_pic": "https://archive.org/services/img/" + d["identifier"],
            "vod_remarks": str(d.get("year") or ""),
        } for d in r.get("docs") or [] if d.get("identifier")]

    def _random(self, key, rows=24):
        q = self.COLS[key][1]
        total = self._total.get(key)
        if not total:
            total, _ = self._search(q, 1, 1)
            self._total[key] = total
        pages = max(1, min(total // rows, 400))
        _, lst = self._search(q, random.randint(1, pages), rows)
        random.shuffle(lst)
        return lst

    def homeContent(self, filter=True):
        return {"class": [{"type_id": k, "type_name": v[0]} for k, v in self.COLS.items()], "filters": {}}

    def homeVideoContent(self):
        return {"list": self._random("random", 20)}

    def categoryContent(self, tid, pg=1, filter=True, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        tid = tid if tid in self.COLS else "random"
        # 每一页都是重新随机抽，越翻越多惊喜
        return {"page": pg, "pagecount": 999, "limit": 24, "total": 99999, "list": self._random(tid)}

    def _quote(self):
        j = self._json("https://v1.hitokoto.cn/", {"c": ["h", "d", "i"]})
        if j.get("hitokoto"):
            return "「%s」—— %s" % (j["hitokoto"], j.get("from_who") or j.get("from") or "")
        return ""

    def detailContent(self, ids):
        out = []
        for ident in ids:
            m = self._json("https://archive.org/metadata/" + urllib.parse.quote(str(ident)))
            meta = m.get("metadata") or {}
            files = m.get("files") or []
            vids = [f for f in files if str(f.get("name", "")).lower().endswith(".mp4")]
            # 优先较小的 h.264 派生版，手机流量友好
            vids.sort(key=lambda f: int(f.get("size") or 0))
            seen, eps = set(), []
            for f in vids:
                base = f["name"].rsplit(".", 1)[0].replace(".ia", "").replace("_512kb", "")
                if base in seen:
                    continue
                seen.add(base)
                eps.append("%s$https://archive.org/download/%s/%s" % (
                    base.replace("$", "").replace("#", "")[:40], ident, urllib.parse.quote(f["name"])))
            desc = meta.get("description") or ""
            if isinstance(desc, list):
                desc = "\n".join(desc)
            import re
            desc = re.sub(r"<[^>]+>", "", desc)[:600]
            q = self._quote()
            out.append({
                "vod_id": ident,
                "vod_name": meta.get("title") if isinstance(meta.get("title"), str) else ident,
                "vod_pic": "https://archive.org/services/img/" + ident,
                "vod_year": str(meta.get("year") or meta.get("date") or "")[:4],
                "vod_remarks": "公有领域",
                "vod_content": ((q + "\n\n") if q else "") + desc,
                "vod_play_from": "Archive",
                "vod_play_url": "#".join(eps[:30]),
            })
        return {"list": out}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        _, lst = self._search('title:(%s) AND %s' % (key, self.COLS["random"][1]), pg)
        return {"list": lst, "page": pg}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id, "header": self.headers}
