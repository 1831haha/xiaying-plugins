# -*- coding: utf-8 -*-
"""
每日一句·听歌 PY 源（侠影）：hitokoto 一言 × 氛围电台
每张卡片是一句随机的话（动画/漫画/游戏/文学/影视/诗词/哲学/网易云），刷新就换；
点进去读完整句子与出处，「播放」是一路 Lo-Fi/氛围电台，边听边看。
"""
import random

# @header({"title": "每日一句", "searchable": 0, "quickSearch": 0, "filterable": 0})


class Spider:
    TYPES = [("all", "随机"), ("a", "动画"), ("b", "漫画"), ("c", "游戏"), ("d", "文学"),
             ("h", "影视"), ("i", "诗词"), ("j", "网易云"), ("k", "哲学")]
    STATIONS = [
        ("Lo-Fi 夜波", "https://radio.plaza.one/mp3"),
        ("冰淇淋 Chill", "https://play.nicecream.fm/blue.aac"),
        ("纯自然白噪音", "https://purenature-mynoise.radioca.st/stream"),
        ("月光助眠", "https://radio.das.pub/stream.mp3"),
        ("冥想", "https://mahakatharadio.com/api/station/live.mp3"),
    ]
    BUNDLE = ["https://cdn.jsdelivr.net/gh/hitokoto-osc/sentences-bundle@latest/sentences/%s.json",
              "https://fastly.jsdelivr.net/gh/hitokoto-osc/sentences-bundle@latest/sentences/%s.json",
              "https://raw.githubusercontent.com/hitokoto-osc/sentences-bundle/master/sentences/%s.json"]
    COLORS = ["5B3E96", "0B57D0", "146C2E", "B3261E", "8B4A00", "00696F", "7B2C9C"]

    def getName(self):
        return "每日一句"

    def init(self, extend=""):
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self._cache = {}
        self._bundle = {}

    def _pool(self, t):
        """句库：hitokoto 官方句子包（按类别整包缓存，本地随机，不受一言接口限流影响）。"""
        if t in self._bundle:
            return self._bundle[t]
        import requests
        pool = []
        for tpl in self.BUNDLE:
            try:
                pool = requests.get(tpl % t, headers=self.headers, timeout=15).json()
                if pool:
                    break
            except Exception:
                pool = []
        self._bundle[t] = pool
        return pool

    def _batch(self, t, n=12):
        if t == "all":
            res = []
            for c in random.sample([k for k, _ in self.TYPES[1:]], 4):
                p = self._pool(c)
                res += random.sample(p, min(len(p), n // 4 + 1))
            random.shuffle(res)
            res = res[:n]
        else:
            p = self._pool(t)
            res = random.sample(p, min(len(p), n))
        out, seen = [], set()
        for x in res:
            if x["uuid"] in seen:
                continue
            seen.add(x["uuid"])
            self._cache[x["uuid"]] = x
            src = x.get("from_who") or x.get("from") or ""
            out.append({
                "vod_id": x["uuid"],
                "vod_name": x["hitokoto"],
                "vod_pic": "https://dummyimage.com/300x400/%s/ffffff.png&text=%s" % (
                    random.choice(self.COLORS), "%E4%B8%80%E8%A8%80"),
                "vod_remarks": ("—— " + src)[:20] if src else "",
            })
        return out

    def homeContent(self, filter=True):
        return {"class": [{"type_id": k, "type_name": v} for k, v in self.TYPES], "filters": {}}

    def homeVideoContent(self):
        return {"list": self._batch("all", 9)}

    def categoryContent(self, tid, pg=1, filter=True, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        return {"page": pg, "pagecount": 99, "limit": 12, "total": 9999, "list": self._batch(str(tid))}

    def detailContent(self, ids):
        out = []
        for u in ids:
            x = self._cache.get(u) or {}
            text = x.get("hitokoto", "（这句话飘走了，回去刷新一下吧）")
            src = "%s%s" % (x.get("from", ""), ("·" + x["from_who"]) if x.get("from_who") else "")
            out.append({
                "vod_id": u,
                "vod_name": text[:30],
                "vod_pic": "",
                "vod_remarks": src,
                "vod_content": "「%s」\n\n—— %s\n\n点「播放」挑一路氛围电台，边听边想。" % (text, src or "佚名"),
                "vod_play_from": "氛围电台",
                "vod_play_url": "#".join("%s$%s" % s for s in self.STATIONS),
            })
        return {"list": out}

    def searchContent(self, key, quick=False, pg="1"):
        return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id, "header": {"User-Agent": "Mozilla/5.0"}}
