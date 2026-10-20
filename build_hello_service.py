#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 hello-service 正式版服务包 packages/hello-service-1.1.0.zip。

hello-service 是侠影官方示例服务（服务型插件参考模板）：现在唯一能真跑的
服务示例。包结构按本仓 SERVER_PLUGIN_SPEC.md（server.json v1）：
根部 server.json + plugin.json + hello-service/server.sh。server.json 里的
sha256 是 server.sh 的实算摘要（安装时 App 按同一口径校验）。

打包可复现：zip 条目固定时间戳 (2026,1,1) + Python zipfile（禁用 7-Zip），
脚本内连打两次、md5 不一致直接报错。改 server.sh 后重跑本脚本，再把新
md5/size 同步进 market.json 并跑 check_market.py。
"""
import hashlib
import io
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_ZIP = HERE / "packages" / "hello-service-1.1.0.zip"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)
VERSION = "1.1.0"

# 示例服务本体：/system/bin/sh 小服务。PORT/SERVICE_PORT 由 App 启动时注入；
# 有 nc 时用 FIFO 双工模式提供极简 HTTP（/healthz 回 OK、/ 与其余路径回文本
# 状态页），nc 不可用/参数不兼容就打日志转心跳保活（进程存活即状态 RUNNING）。
# FIFO 一律建在 App 注入的 TMPDIR（私有目录）——共享存储 FUSE 建不了 FIFO。
SERVER_SH = r"""#!/system/bin/sh
# hello-service 1.1.0: 侠影示例服务（服务型插件参考模板）
# PORT/SERVICE_PORT 由侠影 App 启动时注入环境变量，只绑 127.0.0.1。
PORT="${PORT:-${SERVICE_PORT:-29578}}"
echo "[hello-service] 侠影示例服务 1.1.0 启动，监听 127.0.0.1:$PORT，时间 $(date '+%Y-%m-%d %H:%M:%S')"

# 处理一次请求：从 stdin 读请求行，响应写 stdout（调用方把 stdout 接到 FIFO 喂回 nc）。
serve_once() {
  IFS=' ' read -r _METHOD _PATH _REST || exit 0
  _PATH="${_PATH%%\?*}"
  case "$_PATH" in
    /healthz)
      printf 'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK'
      ;;
    *)
      BODY="侠影示例服务 hello-service 1.1.0
状态：运行中
时间：$(date '+%Y-%m-%d %H:%M:%S')
监听：127.0.0.1:$PORT
探活：GET /healthz"
      LEN=$(printf '%s' "$BODY" | wc -c | tr -d ' ')
      printf 'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: %s\r\nConnection: close\r\n\r\n%s' "$LEN" "$BODY"
      ;;
  esac
}

heartbeat() {
  echo "[hello-service] 心跳保活模式，每 5 秒一条日志（端口 $PORT 未提供 HTTP）"
  while true; do
    echo "[hello-service] heartbeat $(date '+%H:%M:%S')"
    sleep 5
  done
}

if command -v nc >/dev/null 2>&1; then
  FIFO="${TMPDIR:-.}/.hello_resp_fifo"
  rm -f "$FIFO"
  if mkfifo "$FIFO" 2>/dev/null; then
    echo "[hello-service] 使用 nc 在 127.0.0.1:$PORT 提供 HTTP（/healthz 探活、/ 状态页）"
    # FIFO 双工：nc 的 stdin 从 FIFO 读响应，请求经管道进 serve_once，
    # serve_once 的 stdout 重定向回 FIFO——两端在启动时互相 rendezvous。
    while true; do
      nc -l -p "$PORT" 127.0.0.1 <"$FIFO" | serve_once >"$FIFO" || break
    done
    echo "[hello-service] nc 服务循环退出（参数可能不兼容），转入心跳保活"
    rm -f "$FIFO"
  else
    echo "[hello-service] 无法创建 FIFO，转入心跳保活"
  fi
else
  echo "[hello-service] 系统无 nc，跳过 HTTP，转入心跳保活"
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
        "id": "hello-service",
        "name": "示例服务",
        "desc": "侠影官方示例服务：验证服务插件安装/启动/探活全链路，根路径回文本状态页，/healthz 探活；无实际业务功能，是编写服务型插件的参考模板。",
        "version": VERSION,
        "workDir": "hello-service",
        "command": "server.sh",
        "args": [],
        "port": 29578,
        "env": {},
        "healthMode": "HTTP",
        "healthPath": "/healthz",
        "autoStart": False,
        "sha256": sha256,
    }
    plugin_json = {
        "id": "hello-service",
        "name": "示例服务",
        "version": VERSION,
        "type": "server",
        "platforms": ["android"],
        "abis": ["arm64-v8a"],
        "desc": "侠影官方示例服务（服务型插件参考模板）",
    }
    json_bytes = (json.dumps(server_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest_bytes = (json.dumps(plugin_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zip_info("hello-service/server.sh", executable=True), sh_bytes)
        zf.writestr(zip_info("plugin.json"), manifest_bytes)
        zf.writestr(zip_info("server.json"), json_bytes)
    return buf.getvalue()


def main() -> None:
    data1 = build()
    data2 = build()
    md5_1 = hashlib.md5(data1).hexdigest()
    md5_2 = hashlib.md5(data2).hexdigest()
    if data1 != data2:
        raise SystemExit(f"打包不可复现：两次 md5 不一致 {md5_1} vs {md5_2}")
    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    OUT_ZIP.write_bytes(data1)
    print(f"wrote {OUT_ZIP} ({len(data1)} bytes)")
    print(f"zip md5 = {md5_1}（连打两次一致，可复现）")


if __name__ == "__main__":
    main()
