# 侠影插件编写指南（v1）

> 2026-10-14 系统学习 DsPlayer 官方插件仓库（hjdhnx/dsplayer-plugin）后编写。
> 目标：以后写插件时直接按此文档执行，不用重新调研。
> 仓库协议与 DsPlayer 官方市场兼容（字段名一致），包格式可直接互装。

## 一、插件形态（6 种，侠影支持 3 种）

| 形态 | 包特征 | 用途 | 侠影支持 |
|---|---|---|---|
| source | zip，顶层 `spider/{dr2,dr3,hipy,html,js}/` 规则文件，可选根部 `source.json` | 站源规则包 | ✅ |
| server | zip，根部 `server.json`（必填 `workDir`） | 本地服务（node/php/python） | ✅（下载管理，外部运行） |
| live | 裸 JSON，顶层 `lives` 数组 | 直播源包 | ✅ |
| import | zip，二进制/运行时 | 引擎、运行时 | ❌（引擎内置） |
| apk | apk，`assets/plugin.json` 只认 `pluginVersion` | 需系统安装的插件 | ❌（默认隐藏） |
| binary / binary-runtime | 独立服务 | Go/C 或 node/php/python 运行时服务 | ❌ |

ABI 基线：`arm64-v8a`（缺省即此）。

## 二、market.json 条目字段（与 DsPlayer 官方一致）

```json
{
  "logo": "icons/market.png",
  "name": "侠影官方插件市场",
  "desc": "...",
  "updatedAt": "2026-10-14T12:00:00Z",
  "plugins": [{
    "id": "btsow-search",
    "name": "BTSOW 磁力搜索",
    "author": "xiaoying",
    "desc": "一句话说明",
    "version": "1.0.2",
    "type": "source",
    "size": 7148,
    "url": "packages/btsow-search-1.0.2.zip",
    "icon": "icons/btsow.png",
    "tags": ["搜索"],
    "changelog": "v1.0.2：...",
    "md5": "实测32位小写",
    "platforms": ["android", "win32"],
    "category": "app",
    "minApp": "0.22.0",
    "abis": ["arm64-v8a"],
    "engine": "py"
  }]
}
```

- `type` 词表：`source` / `server` / `live` / `import` / `apk`。
- `platforms` 铁律：二进制条目恰好声明一个；数据类（source/server/live）标全平台。
- `category`：`env`（给壳子供能力）/ `app`（完整使用场景）。
- `engine` 为侠影扩展字段（DsPlayer 侧忽略）：source 插件填 `py` / `js` / `php`，缺省时 App 按包内目录嗅探。
- `url`/`icon` 可相对（按 market.json 地址拼接）或绝对。

## 三、source 插件包规范

```
btsow-search-1.0.2.zip
├── plugin.json          # manifest（推荐，见第五节）
├── source.json          # 可选，{"target":"xiaoying"}
└── spider/
    ├── hipy/xxx.py      # py 规则（侠影走 Chaquopy）
    ├── dr2/xxx.js       # drpy2 规则（侠影走 QuickJS）
    ├── dr3/xxx.js       # drpy3 规则
    └── js/xxx.js        # 通用 js
```

- 规则文件命名：`{站名}.{py|js}`，UTF-8。
- 侠影安装时：按 `engine` 字段（或嗅探）把规则文件扁平拷入 `xiaying/{py,js,php}/`。
- py 规则须实现：`homeContent` / `categoryContent` / `detailContent` / `searchContent` / `playerContent`（drpy 语义，侠影 PyApi 按此调用）。

## 四、server 插件包规范

根部 `server.json`（实测 danmu-api 1.0.0）：

```json
{
  "serviceId": "xxx",
  "serviceName": "中文名",
  "workDir": "xxx",
  "entry": "xxx/server.js",
  "port": 9321,
  "healthType": "tcp",
  "version": "1.0.0",
  "desc": "..."
}
```

- `workDir` 必填：zip 解压后服务的工作目录（相对包根）。
- `port` 避开占用：19978 / 17890 / 9978 / 8080 / 8000 / 8888；侠影预留 29578。
- 侠影当前只做下载+版本管理，服务需外部运行（App 内明示）。

## 五、plugin.json（包内 manifest，推荐）

```json
{
  "id": "btsow-search",
  "name": "BTSOW 磁力搜索",
  "version": "1.0.2",
  "type": "source",
  "platforms": ["android", "win32"],
  "abis": ["arm64-v8a"]
}
```

安装时 App 校验包内 `id`/`version` 与 market.json 条目一致，不一致拒绝安装。

## 六、live 插件规范

裸 JSON（非 zip），顶层 `lives` 数组：

```json
{"lives": [
  {"name": "央视综合", "url": "https://.../cctv1.m3u8", "logo": "...", "group": "央视", "ua": "", "epg": ""}
]}
```

- `url` 必填；`logo`/`group`/`ua`/`epg` 可选。
- `url` 可直接是 m3u8 地址，也可指向远端 .m3u 订阅（侠影按 M3U 解析）。

## 七、发版流程（铁律）

1. 包文件名带版本：`{id}-{version}.zip`；**同名包绝不覆盖重传**（升版本换文件名）。
2. 打包：Python zipfile，固定时间戳，保证 md5 可复现；禁用 7-Zip（中文名乱码）。
3. manifest 放 zip 根部；算好 `size` / `md5`（32 位小写）填 market.json。
4. 图标放 `icons/`，换图标换文件名（防缓存）。
5. 跑 `python check_market.py`，全 PASS 才 commit；README 条目表同步更新。
6. push 后确认 `https://raw.githubusercontent.com/1831haha/xiaying-plugins/main/market.json` 可访问。

## 八、原创要求

- 只收录自研/已获授权的插件；第三方插件保留原作者署名与开源协议声明，不改名洗稿。
- 参考格式可以，复制代码不行；借鉴思路必须重写实现。
