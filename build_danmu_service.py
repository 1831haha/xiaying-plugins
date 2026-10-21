#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 danmu-service 1.0.0 弹幕服务包 packages/danmu-service-1.0.0.zip。

侠影弹幕服务（只看不发）：按标题聚合 14 家 LogVar 弹幕源（同一套软件的
不同部署，每家库不同，聚合提高命中率），合并去重后回 JSON 列表。
包结构按本仓 SERVER_PLUGIN_SPEC.md（server.json v1）：
根部 server.json + plugin.json + danmu-service/server.sh。server.json 里的
sha256 是 server.sh 的实算摘要（安装时 App 按同一口径校验）。

调用链（与 App 内置弹幕同源语义，LogVar 部署免登录）：
  GET /api/v2/search/anime?keyword=<标题> → 取第一个 animeId
  GET /api/v2/bangumi/<animeId> → 按 episodeNumber 匹配集数，取 episodeId
  GET /api/v2/comment/<episodeId> → comments[{cid, p:"时间,模式,颜色,[来源]", m}]
单家 5 秒超时、失败跳过；多家结果合并时同文本 3 秒内只留一条，再按
timeMs 排序，上限 1000 条。搜不到/上游全挂回 []，不报错中断。

补充源：弹弹play 官方 API 现已要求应用凭证（匿名调用 403），仅当
DANDAN_APP_ID 与 DANDAN_APP_SECRET 环境变量齐全且有 sha256sum/base64
时才跑（签名算法按公开文档：base64(sha256(AppId+Timestamp+Path+Secret))）；
默认关闭，不拖慢主链路。

红线：只提供拉取接口（/healthz、/ 状态页、/danmaku），绝不加任何
发送/发表弹幕的接口；不碰播放器覆盖层、开关、缓存（合并显示由 App 侧钩子做）。

打包可复现：zip 条目固定时间戳 (2026,1,1) + Python zipfile（禁用 7-Zip），
脚本内连打三次、sha256 不一致直接报错。改 server.sh 后重跑本脚本，再把新
md5/size 同步进 market.json 并跑 check_market.py。
"""
import hashlib
import io
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_ZIP = HERE / "packages" / "danmu-service-1.0.0.zip"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)
VERSION = "1.0.0"

# 弹幕服务本体：/system/bin/sh 小服务，照 hello-service 的 sh + nc + FIFO 套路。
# PORT/SERVICE_PORT 由 App 启动时注入；server.json port 填 0，App 从 29578 起
# 自动分配（保留端口与已占端口自动顺延）。只绑 127.0.0.1。
# FIFO 一律建在 App 注入的 TMPDIR（私有目录）——共享存储 FUSE 建不了 FIFO。
# 调试：DANMU_SINGLE_REQUEST=1 时从 stdin 读一次 HTTP 请求并回响应后退出
# （不用 nc，供沙箱/真机 adb 下独立验证取数链路）。
SERVER_SH = r"""#!/system/bin/sh
# danmu-service 1.0.0: 侠影弹幕服务（只看不发）
# 按标题聚合 14 家 LogVar 弹幕源，合并去重后回 JSON 列表。
# 只提供拉取接口：GET /healthz（探活）、GET /（状态页）、
# GET /danmaku?title=<标题>&episode=<集数>（回 JSON 列表）。
# 没有任何发送/发表弹幕的接口；不碰播放器覆盖层、开关、缓存。
# PORT/SERVICE_PORT 由侠影 App 启动时注入环境变量，只绑 127.0.0.1。
# 运行：/system/bin/sh server.sh（App 经 sh 解释执行，与 hello-service 同口径）。
PORT="${PORT:-${SERVICE_PORT:-29580}}"
VERSION="1.0.0"
TMP="${TMPDIR:-/tmp}"
mkdir -p "$TMP" 2>/dev/null

# 14 家 LogVar 弹幕源（同一套软件的不同部署，每家库不同；API 走 host 根，
# 不要带各部署自己的页面路由后缀）。全部 https。
HOSTS="dm.999.team danmu.qianting168.com dm.ljiaovm.com danmu.longemby.com justdanmu.irisnb.com dandan.wenjian.de danmu.cynn.top dmfl.us.ci danmu.0000996.xyz dm.taotu.ink logvardm.278612356.xyz logvar.hhht.cc.cd dm.66608880.xyz danmu.iyo.us.ci"

# 弹弹play 官方补充源（默认关闭）：官方现已要求应用凭证，匿名调用 403。
DANDAN_HOST="api.dandanplay.net"

# ---- 工具探测（启动时一次）----
if command -v curl >/dev/null 2>&1; then FETCH_TOOL="curl"
elif command -v wget >/dev/null 2>&1; then FETCH_TOOL="wget"
else FETCH_TOOL=""; fi
if command -v awk >/dev/null 2>&1; then HAVE_AWK=1; else HAVE_AWK=0; fi

echo "[danmu-service] 弹幕服务 $VERSION 启动，监听 127.0.0.1:$PORT（取数工具：${FETCH_TOOL:-无}，只看不发）"

# ---- 取数：curl 优先，wget 兜底；单家 5 秒超时 ----
fetch_url() {
  # $1 = 完整 URL（调用方已做编码）
  if [ "$FETCH_TOOL" = "curl" ]; then
    curl -s --max-time 5 -H "User-Agent: movieshell-danmu/1.0" "$1" 2>/dev/null
  elif [ "$FETCH_TOOL" = "wget" ]; then
    wget -qO- -T 5 -U "movieshell-danmu/1.0" "$1" 2>/dev/null
  else
    return 1
  fi
}

# ---- URL 编码（逐字节：安全字符直通，其余 %XX 大写）----
urlencode() {
  _in=$1 _out=
  while [ -n "$_in" ]; do
    _rest=${_in#?}
    _c=${_in%"$_rest"}
    _in=$_rest
    case "$_c" in
      [A-Za-z0-9._~-]) _out="$_out$_c" ;;
      *)
        for _b in $(printf '%s' "$_c" | od -An -tx1 -v | tr -s ' ' '\n' | grep -v '^$'); do
          _out="$_out%$(printf '%s' "$_b" | tr 'a-f' 'A-F')"
        done
        ;;
    esac
  done
  printf '%s' "$_out"
}

# ---- URL 解码（%XX → 字节，+ → 空格）----
urldecode() {
  _in=$1 _out=
  while [ -n "$_in" ]; do
    _rest=${_in#?}
    _c=${_in%"$_rest"}
    _in=$_rest
    if [ "$_c" = "%" ]; then
      _rest=${_in#?}
      _h1=${_in%"$_rest"}
      _in=$_rest
      _rest=${_in#?}
      _h2=${_in%"$_rest"}
      _in=$_rest
      case "$_h1$_h2" in
        [0-9A-Fa-f][0-9A-Fa-f])
          _dec=$((0x$_h1$_h2))
          _out="$_out$(printf "\\$(printf '%03o' "$_dec")")"
          ;;
        *) _out="$_out%$_h1$_h2" ;;
      esac
    elif [ "$_c" = "+" ]; then
      _out="$_out "
    else
      _out="$_out$_c"
    fi
  done
  printf '%s' "$_out"
}

# ---- 秒（可带小数）→ 毫秒整数 ----
sec_to_ms() {
  if [ "$HAVE_AWK" = "1" ]; then
    awk -v t="$1" 'BEGIN { printf "%d", t * 1000 }' 2>/dev/null || printf '%s' "${1%%.*}000"
  else
    printf '%s' "${1%%.*}000"
  fi
}

# ---- 十进制颜色 → #RRGGBB ----
color_hex() {
  _c=$(($1 & 16777215))
  printf '#%06X' "$_c"
}

# ---- 弹幕 JSON → TSV（timeMs、text、color、mode），追加到 $2 ----
# p 格式："时间,模式,颜色,[来源]"；m 原样输出（源 JSON 里的转义形式本身就是
# 合法 JSON 字符串内容，无需反转义）。p/m 缺失或非法时跳过该条。
comments_to_tsv() {
  _pfile="$2.p"; _mfile="$2.m"
  printf '%s' "$1" | grep -oE '"p":"([^"\\]|\\.)*"' | sed 's/^"p":"//;s/"$//' > "$_pfile"
  printf '%s' "$1" | grep -oE '"m":"([^"\\]|\\.)*"' | sed 's/^"m":"//;s/"$//' > "$_mfile"
  exec 3<"$_pfile"; exec 4<"$_mfile"
  while IFS= read -r _p <&3 && IFS= read -r _m <&4; do
    [ -n "$_m" ] || continue
    _t=${_p%%,*}; _r=${_p#*,}
    case "$_t" in ''|*[!0-9.]*) continue ;; esac
    _mode=${_r%%,*}; _r2=${_r#*,}; _col=${_r2%%,*}
    case "$_mode" in ''|*[!0-9]*) _mode=1 ;; esac
    case "$_col" in ''|*[!0-9]*) continue ;; esac
    _ms=$(sec_to_ms "$_t")
    case "$_mode" in
      4) _mode_s="bottom" ;;
      5) _mode_s="top" ;;
      *) _mode_s="scroll" ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$_ms" "$_m" "$(color_hex "$_col")" "$_mode_s" >> "$2"
  done
  exec 3<&-; exec 4<&-
  rm -f "$_pfile" "$_mfile"
  return 0
}

# ---- 十六进制 → 二进制字节（写 stdout，供弹弹play 签名用）----
hex2bin() {
  _hex=$1
  while [ -n "$_hex" ]; do
    _rest=${_hex#??}
    _h=${_hex%"$_rest"}
    _hex=$_rest
    _dec=$((0x$_h))
    printf "\\$(printf '%03o' "$_dec")"
  done
}

# ---- 单家取数：search → bangumi → comment，写 TSV 到 $4 ----
fetch_host() {
  # $1=host $2=标题 $3=集数 $4=输出 TSV
  _search=$(fetch_url "https://$1/api/v2/search/anime?keyword=$(urlencode "$2")") || return 1
  [ -n "$_search" ] || return 1
  _anime=$(printf '%s' "$_search" | grep -o '"animeId":[0-9]*' | head -1 | cut -d: -f2)
  [ -n "$_anime" ] || return 1
  _bangumi=$(fetch_url "https://$1/api/v2/bangumi/$_anime") || return 1
  [ -n "$_bangumi" ] || return 1
  # episodes 配对：episodeId 与 episodeNumber 按出现顺序配对（两种键序都兼容）
  _pairs=$(printf '%s' "$_bangumi" | grep -oE '"episodeId":[0-9]+|"episodeNumber":"[^"]*"' | awk '
    /"episodeId"/ { sub(/.*:/, ""); id = $0 }
    /"episodeNumber"/ { sub(/.*"episodeNumber":"/, ""); sub(/".*/, ""); num = $0 }
    (id != "" && num != "") { print num " " id; id = ""; num = "" }
  ')
  [ -n "$_pairs" ] || return 1
  _ep=""; _idx=0
  while IFS=' ' read -r _num _id; do
    _idx=$((_idx + 1))
    if [ "$_num" = "$3" ]; then _ep="$_id"; break; fi
    if [ -z "$_ep" ] && [ "$_idx" = "$3" ]; then _ep="$_id"; fi
  done <<EOF
$_pairs
EOF
  if [ -z "$_ep" ]; then
    _ep=$(printf '%s\n' "$_pairs" | head -1 | cut -d' ' -f2)
  fi
  [ -n "$_ep" ] || return 1
  _comments=$(fetch_url "https://$1/api/v2/comment/$_ep") || return 1
  [ -n "$_comments" ] || return 1
  comments_to_tsv "$_comments" "$4"
  return 0
}

# ---- 弹弹play 官方补充源：仅凭证齐全且有 sha256sum/base64 时跑 ----
# 签名算法（公开文档）：base64(sha256(AppId + Timestamp + Path + AppSecret))，
# 请求头 X-AppId / X-Timestamp / X-Signature。未验证（无凭证可测），默认关闭。
dandan_fetch() {
  # $1=标题 $2=集数 $3=输出 TSV
  [ -n "$DANDAN_APP_ID" ] && [ -n "$DANDAN_APP_SECRET" ] || return 1
  command -v sha256sum >/dev/null 2>&1 || return 1
  command -v base64 >/dev/null 2>&1 || return 1
  command -v curl >/dev/null 2>&1 || return 1
  _q=$(urlencode "$1")
  _ts=$(date +%s)
  _path="/api/v2/search/anime?keyword=$_q"
  _sig=$(printf '%s' "$DANDAN_APP_ID$_ts$_path$DANDAN_APP_SECRET" | sha256sum | cut -d' ' -f1 | hex2bin | base64 | tr -d '\n')
  _search=$(curl -s --max-time 5 -H "User-Agent: movieshell-danmu/1.0" -H "X-AppId: $DANDAN_APP_ID" -H "X-Timestamp: $_ts" -H "X-Signature: $_sig" "https://$DANDAN_HOST$_path" 2>/dev/null) || return 1
  [ -n "$_search" ] || return 1
  _anime=$(printf '%s' "$_search" | grep -o '"animeId":[0-9]*' | head -1 | cut -d: -f2)
  [ -n "$_anime" ] || return 1
  _path2="/api/v2/comment/$_anime/$2"
  _sig2=$(printf '%s' "$DANDAN_APP_ID$_ts$_path2$DANDAN_APP_SECRET" | sha256sum | cut -d' ' -f1 | hex2bin | base64 | tr -d '\n')
  _comments=$(curl -s --max-time 5 -H "User-Agent: movieshell-danmu/1.0" -H "X-AppId: $DANDAN_APP_ID" -H "X-Timestamp: $_ts" -H "X-Signature: $_sig2" "https://$DANDAN_HOST$_path2" 2>/dev/null) || return 1
  [ -n "$_comments" ] || return 1
  comments_to_tsv "$_comments" "$3"
  return 0
}

# ---- /danmaku：聚合 14 家 + 补充源，合并去重排序回 JSON 数组 ----
danmaku_json() {
  # $1=标题 $2=集数
  if [ -z "$1" ] || [ -z "$FETCH_TOOL" ]; then printf '[]'; return 0; fi
  _i=0
  for _h in $HOSTS; do
    _i=$((_i + 1))
    ( fetch_host "$_h" "$1" "$2" "$TMP/danmu_$$_part_$_i.tsv" >/dev/null 2>&1 ) &
  done
  ( dandan_fetch "$1" "$2" "$TMP/danmu_$$_part_dd.tsv" >/dev/null 2>&1 ) &
  wait
  _tab=$(printf '\t')
  _merged=$(cat "$TMP"/danmu_$$_part_*.tsv 2>/dev/null | sort -t "$_tab" -k1,1n)
  if [ "$HAVE_AWK" = "1" ]; then
    _merged=$(printf '%s\n' "$_merged" | awk -v FS="$_tab" '{ if (!($2 in last) || $1 - last[$2] > 3000) { print; last[$2] = $1 } }')
  fi
  _merged=$(printf '%s\n' "$_merged" | head -1000)
  rm -f "$TMP"/danmu_$$_part_*.tsv
  if [ -z "$_merged" ]; then printf '[]'; return 0; fi
  _json=""; _first=1
  while IFS="$_tab" read -r _ms _text _color _mode; do
    if [ "$_first" = "1" ]; then _first=0; else _json="$_json,"; fi
    _json="$_json{\"timeMs\":$_ms,\"text\":\"$_text\",\"color\":\"$_color\",\"mode\":\"$_mode\"}"
  done <<EOF
$_merged
EOF
  printf '[%s]' "$_json"
}

# ---- HTTP 一次请求处理：从 stdin 读请求行+请求头，响应写 stdout ----
serve_once() {
  IFS=' ' read -r _METHOD _PATH _REST || exit 0
  # 消费请求头直到空行（GET 无 body）
  _cr=$(printf '\r')
  while IFS= read -r _h; do
    if [ -z "$_h" ] || [ "$_h" = "$_cr" ]; then break; fi
  done
  _path=${_PATH%%\?*}
  case "$_path" in
    /healthz)
      _body="OK"; _type="text/plain; charset=utf-8"; _code="200 OK" ;;
    /)
      _body="侠影弹幕服务 danmu-service $VERSION
状态：运行中
监听：127.0.0.1:$PORT
上游：14 家 LogVar 弹幕源聚合（单家 5 秒超时、失败跳过）
接口：GET /healthz（探活）、GET /danmaku?title=标题&episode=集数（回 JSON 列表）
红线：只看不发，无发送接口
取数工具：${FETCH_TOOL:-无（未找到 curl/wget，/danmaku 将回空列表）}"
      _type="text/plain; charset=utf-8"; _code="200 OK" ;;
    /danmaku)
      _query=""
      case "$_PATH" in *\?*) _query=${_PATH#*\?} ;; esac
      _title=""; _ep="1"
      set -f
      _oldifs=$IFS; IFS='&'
      for _kv in $_query; do
        case "$_kv" in
          title=*) _title=$(urldecode "${_kv#title=}") ;;
          episode=*) _ep=$(printf '%s' "${_kv#episode=}" | tr -cd '0-9'); [ -n "$_ep" ] || _ep=1 ;;
        esac
      done
      IFS=$_oldifs
      set +f
      _body=$(danmaku_json "$_title" "$_ep")
      _type="application/json; charset=utf-8"; _code="200 OK" ;;
    *)
      _body="404 Not Found"; _type="text/plain; charset=utf-8"; _code="404 Not Found" ;;
  esac
  _len=$(printf '%s' "$_body" | wc -c | tr -d ' ')
  printf 'HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s' "$_code" "$_type" "$_len" "$_body"
}

heartbeat() {
  echo "[danmu-service] 心跳保活模式，每 5 秒一条日志（端口 $PORT 未提供 HTTP）"
  while true; do
    echo "[danmu-service] heartbeat $(date '+%H:%M:%S')"
    sleep 5
  done
}

# 调试模式：从 stdin 读一次 HTTP 请求并回响应后退出（不用 nc）
if [ -n "$DANMU_SINGLE_REQUEST" ]; then
  serve_once
  exit 0
fi

if command -v nc >/dev/null 2>&1; then
  FIFO="$TMP/.danmu_resp_fifo"
  rm -f "$FIFO"
  if mkfifo "$FIFO" 2>/dev/null; then
    echo "[danmu-service] 使用 nc 在 127.0.0.1:$PORT 提供 HTTP（/healthz 探活、/ 状态页、/danmaku 取数）"
    # FIFO 双工：nc 的 stdin 从 FIFO 读响应，请求经管道进 serve_once，
    # serve_once 的 stdout 重定向回 FIFO——两端在启动时互相 rendezvous。
    while true; do
      nc -l -p "$PORT" 127.0.0.1 <"$FIFO" | serve_once >"$FIFO" || break
    done
    echo "[danmu-service] nc 服务循环退出（参数可能不兼容），转入心跳保活"
    rm -f "$FIFO"
  else
    echo "[danmu-service] 无法创建 FIFO，转入心跳保活"
  fi
else
  echo "[danmu-service] 系统无 nc，跳过 HTTP，转入心跳保活"
fi
heartbeat
"""


def zip_info(name: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3  # unix，保证 external_attr 权限位稳定
    info.external_attr = (0o755 if executable else 0o644) << 16
    return info


def build() -> bytes:
    sh_bytes = SERVER_SH.encode("utf-8")
    sha256 = hashlib.sha256(sh_bytes).hexdigest()
    server_json = {
        "id": "danmu-service",
        "name": "弹幕服务",
        "desc": "弹幕服务：按标题聚合拉取弹幕（LogVar 弹幕源聚合），供播放器合并显示；只看不发，无发送接口。",
        "version": VERSION,
        "workDir": "danmu-service",
        "command": "server.sh",
        "args": [],
        "port": 0,
        "env": {},
        "healthMode": "HTTP",
        "healthPath": "/healthz",
        "autoStart": False,
        "sha256": sha256,
    }
    plugin_json = {
        "id": "danmu-service",
        "name": "弹幕服务",
        "version": VERSION,
        "type": "server",
        "platforms": ["android"],
        "abis": ["arm64-v8a"],
        "desc": "弹幕服务：按标题聚合拉取弹幕（LogVar 弹幕源聚合），供播放器合并显示；只看不发，无发送接口。",
    }
    json_bytes = (json.dumps(server_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_bytes = (json.dumps(plugin_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zip_info("danmu-service/server.sh", executable=True), sh_bytes)
        zf.writestr(zip_info("plugin.json"), manifest_bytes)
        zf.writestr(zip_info("server.json"), json_bytes)
    return buf.getvalue()


def main() -> None:
    builds = [build() for _ in range(3)]
    sha = [hashlib.sha256(b).hexdigest() for b in builds]
    if len(set(sha)) != 1:
        raise SystemExit(f"打包不可复现：三次 sha256 不一致 {sha}")
    if builds[0] != builds[1] or builds[1] != builds[2]:
        raise SystemExit("打包不可复现：三次字节不一致")
    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    OUT_ZIP.write_bytes(builds[0])
    print(f"wrote {OUT_ZIP} ({len(builds[0])} bytes)")
    print(f"zip md5 = {hashlib.md5(builds[0]).hexdigest()}（连打三次一致，可复现）")
    print(f"zip sha256 = {sha[0]}")


if __name__ == "__main__":
    main()
