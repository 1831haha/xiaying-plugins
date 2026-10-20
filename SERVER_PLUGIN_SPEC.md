# 服务型插件规范（server.json v1）

> 2026-10-20，v0.120.0 C1。框架管道部分（不含 PHP 本体）。
> 与《PLUGIN_AUTHORING.md》第四节 server 插件包规范呼应：本规范是"App 内可安装、可启动、可管理"的完整版；
> 旧字段 `entry` 更名为 `command`（语义更准：可执行文件相对路径），旧包按新字段重发一版即可。

## 一、包结构

```
some-service-1.0.0.zip
├── server.json          # 根部必填，本规范定义
├── plugin.json          # 推荐（见 PLUGIN_AUTHORING.md 第五节，App 校验 id/version 一致性）
└── <workDir>/           # 服务工作目录，command 相对它解析
    └── ...
```

- 安装落盘：`filesDir/server_plugins/<id>/`（App 私有目录；native 场景下公开目录可能 noexec）。
- 安装时整包解压，解压前逐条目做 zip-slip 防护（目标必须落在安装目录内），非法路径直接拒绝安装。
- 同 id 新版本覆盖安装：先停掉正在运行的进程，再解压覆盖（正在跑的旧进程不允许边跑边换文件）。

## 二、server.json 字段

```json
{
  "id": "magnet-stream",
  "name": "磁力转播服务",
  "version": "1.0.5",
  "workDir": "magnet-stream",
  "command": "server.js",
  "args": ["--port", "${PORT}"],
  "port": 0,
  "healthPath": "/healthz",
  "env": {"NODE_ENV": "production"},
  "sha256": "3a7f…（64 位十六进制）"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 唯一标识，`[a-z0-9._-]+`；即安装目录名、注册表主键 |
| `name` | 是 | 中文显示名 |
| `version` | 是 | 语义版本，与 market.json / plugin.json 做一致性校验 |
| `workDir` | 是 | 相对包根的工作目录；进程 workingDirectory 设为它 |
| `command` | 是 | 相对 workDir 的可执行文件路径；安装时 App 会尝试 `chmod +x` 兜底 |
| `args` | 否 | 数组，传给可执行文件的参数；支持 `${PORT}` 占位（也可用环境变量） |
| `port` | 否 | `0` = 自动分配（从 29578 起顺序找空闲，见第四节）；非 0 = 指定端口 |
| `healthPath` | 否 | 健康检查路径，默认 `/healthz`；App 以 `GET http://127.0.0.1:<port><healthPath>` 探活 |
| `env` | 否 | 键值对，注入进程环境变量；App 额外注入 `PORT` 与 `SERVICE_PORT`（分配到的端口） |
| `sha256` | 二选一必填 | 对 `command` 可执行文件的 SHA-256（64 位十六进制小写） |
| `md5` | 二选一必填 | 兼容旧口径；`sha256` 存在时优先用 `sha256` |

关于签名口径（两层，不另造）：

1. 整包传输校验——复用现有 `PluginMarket.verifyMd5` 口径：从市场安装时用 market.json 条目的 `md5` 校验下载到的 zip（`PLUGIN_AUTHORING.md` 第二节）。
2. 可执行文件校验——`server.json` 内的 `sha256`（优先）或 `md5`，是对 `command` 可执行文件本身的摘要，安装解压后计算比对。
   只签可执行文件不签整包的原因：整包的摘要若放在包内，会把自身包含进去，无法自校验。

## 三、market.json 条目

沿用 `PLUGIN_AUTHORING.md` 第二节字段，`type` 填 `server`。示例：

```json
{
  "id": "magnet-stream",
  "name": "磁力转播服务",
  "version": "1.0.5",
  "type": "server",
  "url": "packages/magnet-stream-1.0.5.zip",
  "md5": "32 位小写",
  "platforms": ["android"],
  "abis": ["arm64-v8a"]
}
```

## 四、端口铁律（硬约束）

- 禁止使用 DS 已占用端口：`5757`、`5758`、`9321`、`17890`、`19978`、`9978`，以及常见端口 `8080`、`8000`、`8888`。
  `port` 填上述值或与其他已装服务插件冲突时，拒绝安装（报错明示）。
- `port: 0` 自动分配：从 `29578` 起顺序探测，跳过保留端口与已分配端口，第一个能成功 bind 的即用；冲突顺延。
- 自家服务进程只绑 `127.0.0.1`，不绑 `0.0.0.0`。服务实现里监听地址必须写死回环；
  App 侧健康检查与调用一律走 `http://127.0.0.1:<port>`。
- 每插件分配到的端口记入注册表（`filesDir/server_plugins_registry.json`），App 重启后沿用，不重新分配。

## 五、进程模型（App 侧）

- `ProcessBuilder` 启动：`command` 解析到 workDir 下的可执行文件，`workingDirectory = workDir`，
  环境变量 = `env` + `PORT`/`SERVICE_PORT`。
- 子进程 stdout/stderr 合并，进每插件环形缓冲（最近 200 行），同时进 `LogBus`（tag `ServicePlugin`）；
  日志读取线程随进程退出自动回收。
- 状态：`RUNNING`（进程存活）/`STOPPED`（未运行）/`ERROR`（进程非 0 退出；用户主动 stop 不算异常）。
- `stop` 先 `destroy()`，3 秒未退出则 `destroyForcibly()`。
- 注册表只存期望态（id/name/version/port/是否期望运行）；`Process` 对象只在内存，不持久化。

## 六、环境自检（App 内"服务插件"页）

安装/启动前可跑一遍，逐项给成功/失败 + 细节，并记 `LogBus`：

1. 私有目录可执行：往 `filesDir` 写一段 `echo` 小脚本，`chmod +x` 后真实执行一次（脚本短、安全、可重复跑）。
2. 当前 ABI：`android.os.Build.SUPPORTED_ABIS`。
3. 首个可用端口：从 29578 起探测。
4. 私有目录可写：`filesDir` 建临时文件写删。

## 七、发版流程

沿用 `PLUGIN_AUTHORING.md` 第七节铁律（包文件名带版本、同名包不覆盖、可复现打包、`check_market.py` 全 PASS）。

## 附录：exec 可行性调研（2026-10-20，v0.120.0）

**结论：能。PHP 服务插件（P1）可走 Termux 提取路线，代价为插件体积约 30–60MB + 版本钉死维护；唯一硬门禁是真机自检（本节第 4 条）。**

1. **二进制来源明确：Termux 官方仓 php 包（aarch64）**。Termux packages 主线 php 版本 8.5.1（`packages/php/build.sh`，TERMUX_PKG_VERSION=8.5.1），NDK 交叉编译、bionic 动态链接，从 packages.termux.dev 的 pool 拆 .deb 即可得 `bin/php`（含 CLI 内置服务器 `php -S`，正是 T4-PHP 19978 的同款形态）与扩展 .so。
2. **依赖树**：TERMUX_PKG_DEPENDS 共 20 个运行时包——capstone、libandroid-glob、libandroid-support、libbz2、libc++、libcurl、libffi、libgmp、libiconv、libicu、libresolv-wrapper、libsqlite、libxml2、libxslt、libzip、oniguruma、openssl、pcre2、readline、tidy、zlib。需整树随插件下发到 workDir/lib，启动时注入 `LD_LIBRARY_PATH=<workDir>/lib`、`TMPDIR=<workDir>/tmp`（Android 无 /tmp，不设会话/临时文件会坏）、`HOME=<workDir>`。Termux 全家桶安装体积约 100–150MB，php 子树（本树）压缩后估计 30–60MB；具体数字以首次打包实测为准。精简路线（自编 --disable-all 只留 T4 需要的扩展）可显著减小，但要自维护 NDK 构建链，P1 先走提取路线验证。
3. **App 内嵌先例存在**：社区已有把自编 PHP 打进 Android App 的完整先例（re-ws.pl 的 PHP-for-Android 打包方案：php.so + libsqlite3.so 以 jniLibs 形态随 APK 分发，LD_LIBRARY_PATH 指向自带库目录、非 root 设备可跑）。说明 exec 自有二进制这条路在 Android 上工程可行。
4. **硬门禁：Android 16（用户机 REDMI K80 / HyperOS 3）上从 App 私有目录 exec 私有二进制**，历史上 Termux 等应用长期如此工作，但必须以「服务插件」页的环境自检（写脚本→chmod→真实执行）真机结果为准。自检不过，P1 暂停、不硬编方案；自检通过则 P1 按提取路线打包 php 运行时插件（端口 29578，已预留）。
5. 静态 PHP 方案（static-php.dev/phpmicro、FrankenPHP）目前只覆盖桌面 Linux/mac/Windows，无现成 Android aarch64 预构建，不作为 P1 路线。
