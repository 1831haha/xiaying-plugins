# -*- coding: utf-8 -*-
"""
B站热门/排行榜 PY 源（侠影）
公开接口：热门 /x/web-interface/popular、排行榜 /x/web-interface/ranking/v2、
每周必看 /x/web-interface/popular/series/one、搜索 /x/web-interface/search/type。
播放：/x/player/playurl html5 mp4（480P，免登录），带 Referer 头。
"""
import re
import json

# @header({"title": "B站热门", "searchable": 1, "quickSearch": 1, "filterable": 0})


class Spider:
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    API = "https://api.bilibili.com"

    def getName(self):
        return "B站热门"

    def init(self, extend=""):
        self.headers = {"User-Agent": self.UA, "Referer": "https://www.bilibili.com/"}
        self._s = None
        self.classes = [
            {"type_id": "popular", "type_name": "综合热门"},
            {"type_id": "weekly", "type_name": "每周必看"},
            {"type_id": "rank_0", "type_name": "全站排行"},
            {"type_id": "rank_1", "type_name": "动画"},
            {"type_id": "rank_4", "type_name": "游戏"},
            {"type_id": "rank_36", "type_name": "知识"},
            {"type_id": "rank_188", "type_name": "科技"},
            {"type_id": "rank_3", "type_name": "音乐"},
            {"type_id": "rank_211", "type_name": "美食"},
            {"type_id": "rank_217", "type_name": "动物圈"},
            {"type_id": "rank_119", "type_name": "鬼畜"},
        ]

    def _sess(self):
        if self._s is None:
            import requests
            self._s = requests.Session()
            try:
                self._s.get("https://www.bilibili.com/", headers=self.headers, timeout=10)
            except Exception:
                pass
        return self._s

    def _get(self, path, params=None):
        try:
            return self._sess().get(self.API + path, params=params, headers=self.headers, timeout=12).json()
        except Exception:
            return {}

    @staticmethod
    def _clean(s):
        return re.sub(r"<[^>]+>", "", str(s or "")).replace("&quot;", '"').replace("&amp;", "&").strip()

    @staticmethod
    def _https(u):
        u = str(u or "")
        return "https:" + u if u.startswith("//") else u.replace("http://", "https://", 1)

    @staticmethod
    def _num(n):
        try:
            n = int(n)
        except Exception:
            return ""
        return "%.1f万" % (n / 10000.0) if n >= 10000 else str(n)

    def _item(self, x):
        bvid = x.get("bvid") or ""
        cid = x.get("cid") or ""
        stat = x.get("stat") or {}
        owner = (x.get("owner") or {}).get("name") or x.get("author") or ""
        play = stat.get("view") if stat else x.get("play")
        return {
            "vod_id": "%s|%s" % (bvid, cid),
            "vod_name": self._clean(x.get("title")),
            "vod_pic": self._https(x.get("pic")),
            "vod_remarks": ("▶%s %s" % (self._num(play), owner)).strip(),
        }

    def _list(self, tid, pg):
        if tid == "popular":
            j = self._get("/x/web-interface/popular", {"ps": 20, "pn": pg})
            lst = (j.get("data") or {}).get("list") or []
            return [self._item(x) for x in lst], 20 if (j.get("data") or {}).get("no_more") is False else pg
        if tid == "weekly":
            sj = self._get("/x/web-interface/popular/series/list")
            series = ((sj.get("data") or {}).get("list") or [])
            if not series or pg > len(series):
                return [], pg
            num = series[pg - 1].get("number")
            j = self._get("/x/web-interface/popular/series/one", {"number": num})
            return [self._item(x) for x in ((j.get("data") or {}).get("list") or [])], len(series)
        if tid.startswith("rank_"):
            if pg > 1:
                return [], 1
            j = self._get("/x/web-interface/ranking/v2", {"rid": tid[5:], "type": "all"})
            return [self._item(x) for x in ((j.get("data") or {}).get("list") or [])], 1
        return [], 1

    def homeContent(self, filter=True):
        return {"class": self.classes, "filters": {}}

    def homeVideoContent(self):
        return {"list": self._list("popular", 1)[0]}

    def categoryContent(self, tid, pg=1, filter=True, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        lst, pc = self._list(str(tid), pg)
        return {"page": pg, "pagecount": pc, "limit": 20, "total": pc * 20, "list": lst}

    def detailContent(self, ids):
        out = []
        for vid in ids:
            bvid, _, cid = str(vid).partition("|")
            j = self._get("/x/web-interface/view", {"bvid": bvid})
            d = j.get("data") or {}
            pages = d.get("pages") or []
            if pages:
                urls = "#".join("%s$%s|%s" % (re.sub(r"[$#|]", " ", p.get("part") or ("P%d" % p.get("page", 1))),
                                              bvid, p.get("cid")) for p in pages)
            else:
                urls = "播放$%s|%s" % (bvid, cid)
            stat = d.get("stat") or {}
            out.append({
                "vod_id": vid,
                "vod_name": self._clean(d.get("title")) or bvid,
                "vod_pic": self._https(d.get("pic")),
                "type_name": d.get("tname", ""),
                "vod_director": (d.get("owner") or {}).get("name", ""),
                "vod_remarks": "▶%s 👍%s" % (self._num(stat.get("view")), self._num(stat.get("like"))),
                "vod_content": (d.get("desc") or "") + "\n\nhttps://www.bilibili.com/video/" + bvid,
                "vod_play_from": "B站",
                "vod_play_url": urls,
            })
        return {"list": out}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        j = self._get("/x/web-interface/search/type", {"search_type": "video", "keyword": key, "page": pg})
        res = (j.get("data") or {}).get("result") or []
        lst = [{
            "vod_id": "%s|" % x.get("bvid"),
            "vod_name": self._clean(x.get("title")),
            "vod_pic": self._https(x.get("pic")),
            "vod_remarks": "▶%s %s" % (self._num(x.get("play")), x.get("author", "")),
        } for x in res if x.get("bvid")]
        return {"list": lst, "page": pg}

    def playerContent(self, flag, id, vipFlags):
        bvid, _, cid = str(id).partition("|")
        if not cid:
            d = self._get("/x/web-interface/view", {"bvid": bvid}).get("data") or {}
            cid = d.get("cid", "")
        j = self._get("/x/player/playurl", {"bvid": bvid, "cid": cid, "qn": 64,
                                            "platform": "html5", "high_quality": 1})
        durl = (j.get("data") or {}).get("durl") or []
        if durl:
            return {"parse": 0, "url": durl[0].get("url"), "header": self.headers}
        return {"parse": 1, "url": "https://www.bilibili.com/video/" + bvid, "header": self.headers}
