# -*- coding: utf-8 -*-
"""
NASA 太空影像 PY 源（侠影）：NASA Image and Video Library 公开视频（公有领域）
分类即主题关键词，每次刷新随机翻页；播放 images-assets.nasa.gov 直链 mp4。
"""
import random
import urllib.parse

# @header({"title": "NASA 太空影像", "searchable": 1, "quickSearch": 0, "filterable": 0})


class Spider:
    API = "https://images-api.nasa.gov"
    TOPICS = [("mars", "火星探索"), ("moon", "月球"), ("black hole", "黑洞宇宙"),
              ("space station", "国际空间站"), ("rocket launch", "火箭发射"),
              ("earth from space", "太空看地球"), ("hubble", "哈勃"), ("webb", "韦布望远镜"),
              ("astronaut", "宇航员日常"), ("sun", "太阳")]

    def getName(self):
        return "NASA 太空影像"

    def init(self, extend=""):
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self._pages = {}

    def _json(self, url, params=None):
        try:
            import requests
            return requests.get(url, params=params, headers=self.headers, timeout=15).json()
        except Exception:
            return {}

    def _search(self, q, page):
        j = self._json(self.API + "/search", {"q": q, "media_type": "video", "page": page, "page_size": 24})
        c = j.get("collection") or {}
        out = []
        for it in c.get("items") or []:
            d = (it.get("data") or [{}])[0]
            pic = next((l.get("href") for l in it.get("links") or [] if l.get("render") == "image"), "")
            out.append({
                "vod_id": d.get("nasa_id", ""),
                "vod_name": d.get("title", ""),
                "vod_pic": (pic or "").replace(" ", "%20"),
                "vod_remarks": str(d.get("date_created", ""))[:10],
            })
        return (c.get("metadata") or {}).get("total_hits", 0), [x for x in out if x["vod_id"]]

    def homeContent(self, filter=True):
        return {"class": [{"type_id": k, "type_name": v} for k, v in self.TOPICS], "filters": {}}

    def homeVideoContent(self):
        k = random.choice(self.TOPICS)[0]
        return {"list": self._search(k, random.randint(1, 5))[1]}

    def categoryContent(self, tid, pg=1, filter=True, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        total = self._pages.get(tid)
        if total is None:
            hits, first = self._search(tid, 1)
            total = self._pages[tid] = max(1, min((hits + 23) // 24, 40))
            if pg == 1:
                random.shuffle(first)
                return {"page": 1, "pagecount": total, "limit": 24, "total": hits, "list": first}
        _, lst = self._search(tid, pg)
        random.shuffle(lst)
        return {"page": pg, "pagecount": total, "limit": 24, "total": total * 24, "list": lst}

    def detailContent(self, ids):
        out = []
        for nid in ids:
            meta = self._json(self.API + "/search", {"nasa_id": nid})
            it = ((meta.get("collection") or {}).get("items") or [{}])[0]
            d = (it.get("data") or [{}])[0]
            assets = self._json(self.API + "/asset/" + urllib.parse.quote(str(nid)))
            hrefs = [x.get("href", "") for x in ((assets.get("collection") or {}).get("items") or [])]
            mp4 = [h for h in hrefs if h.lower().endswith(".mp4")]
            pref = ["~mobile.mp4", "~medium.mp4", "~small.mp4", "~orig.mp4"]
            mp4.sort(key=lambda h: next((i for i, p in enumerate(pref) if h.endswith(p)), 9))
            names = {"~mobile.mp4": "流畅", "~medium.mp4": "标清", "~small.mp4": "小", "~orig.mp4": "原画"}
            eps = ["%s$%s" % (next((v for k, v in names.items() if h.endswith(k)), "播放"),
                              h.replace("http://", "https://").replace(" ", "%20")) for h in mp4[:4]]
            pic = next((l.get("href") for l in it.get("links") or [] if l.get("render") == "image"), "")
            out.append({
                "vod_id": nid,
                "vod_name": d.get("title", nid),
                "vod_pic": (pic or "").replace(" ", "%20"),
                "vod_year": str(d.get("date_created", ""))[:4],
                "vod_director": d.get("center", ""),
                "vod_content": d.get("description", ""),
                "vod_play_from": "NASA",
                "vod_play_url": "#".join(eps),
            })
        return {"list": out}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        return {"list": self._search(key, pg)[1], "page": pg}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id}
