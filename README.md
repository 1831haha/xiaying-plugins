# 侠影插件仓库

侠影 App 内置「插件市场」的数据源。App 从 `market.json` 拉取插件列表，用户一键安装 / 更新 / 卸载。

市场协议兼容 **DsPlayer 官方市场**（`hjdhnx/dsplayer-plugin`）：条目字段名与之完全一致，侠影只多一个扩展字段 `engine`（源引擎提示，DsPlayer 侧忽略）。

## 协议

`market.json` 顶层：`logo` / `name` / `desc` / `updatedAt` / `plugins[]`。

条目字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| id | ✅ | 插件唯一标识，安装后即本地目录名 |
| name | ✅ | 显示名 |
| version | ✅ | 版本号，App 用它判断"有新版" |
| url | ✅ | zip 下载地址（本仓用 raw.githubusercontent 绝对地址） |
| type | | `source`（爬虫源 zip）/`server`（服务 zip）/`live`（裸 JSON 直播源）；侠影不支持 `apk`/`import`（默认隐藏） |
| engine | | 侠影扩展：`source` 对应 `py`/`js`/`php`，`server` 对应 `nodejs`；缺省时 App 按包内目录嗅探 |
| size | | 包字节数，check_market.py 校验 |
| md5 | | 包 MD5，**App 安装时强制校验**，不一致拒绝安装 |
| icon | | 图标相对路径（`icons/xxx.png`）或绝对 URL；换图必须换文件名 |
| author | | 作者 |
| desc | | 一句话描述 |
| tags | | 标签数组 |
| changelog | | 本版更新说明 |
| platforms | | `["android","win32"]`；二进制条目只声明一个平台，数据类标全平台 |
| category | | `env`（环境/能力）/`app`（应用/场景） |
| minApp | | 最低侠影版本（如 `"0.23.0"`），不满足时安装按钮置灰 |
| abis | | 缺省 `["arm64-v8a"]`；显式 `[]` = 不限 |

包内根目录 `plugin.json` 为 manifest（安装时与市场条目做 id/version 一致性校验）：

```json
{
  "id": "btsow-source",
  "name": "BTSOW 磁力搜索",
  "version": "1.0.2",
  "type": "source",
  "platforms": ["android", "win32"],
  "abis": ["arm64-v8a"],
  "desc": "一句话描述"
}
```

## 发版流程

1. 用 `build_market.py` 重打包（固定时间戳、同内容同 md5）并生成 `market.json`。
2. 跑 `python3 check_market.py`，全绿才能发。
3. 同步下表条目（版本 + 包名），commit + push。

铁律：**同名包绝不覆盖重传**——内容变化必升版本换文件名（CDN 缓存会导致 md5 假失败）；删旧版本包（git 历史留档）。

## 条目表

### 环境（env）

| 条目 | id | 版本 | type | 包 |
|---|---|---|---|---|
| 磁力转播服务 | `magnet-stream` | 1.0.5 | server | `magnet-stream-1.0.5.zip` |
| 示例服务 | `hello-service` | 1.1.0 | server | `hello-service-1.1.0.zip` |
| PY 引擎依赖包 | `py-deps` | 1.0.0 | env | `py-deps-1.0.0.zip` |
| PHP 运行时 | `php` | 8.3.35.1 | runtime | `php-8.3.35.1-static.zip` |
| 弹幕服务 | `danmu-service` | 1.0.0 | server | `danmu-service-1.0.0.zip` |

### 应用（app）

| 条目 | id | 版本 | type | 包 |
|---|---|---|---|---|
| BTSOW 磁力搜索 | `btsow-source` | 1.0.2 | source | `btsow-source-1.0.2.zip` |
| BTSOW 磁力搜索（海报版） | `btsow-source-poster` | 1.0.0 | source | `btsow-source-poster-1.0.0.zip` |
| libmpv 播放器引擎 | `mpv-player` | 1.0.0 | player | `mpv-player-1.0.0.zip` |
| 在线字幕搜索 | `subtitle-search` | 1.0.0 | subtitle | `subtitle-search-1.0.0.zip` |
| 央视卫视直播 | `cctv-live` | 1.0.4 | live | `cctv-live-1.0.4.json` |
