# 侠影插件仓库

侠影 App 内置「插件市场」的数据源。App 从 `market.json` 拉取插件列表，用户一键安装 / 更新 / 卸载。

## 协议

`market.json`：

```json
{
  "version": 1,
  "updated": "2026-10-14",
  "plugins": [
    {
      "id": "btsow-source",
      "name": "BTSOW 磁力搜索",
      "version": "1.0.1",
      "type": "source",
      "engine": "py",
      "md5": "ac3938ab0e7eaa5a4394c45d5e1fb77e",
      "url": "https://raw.githubusercontent.com/1831haha/xiaying-plugins/main/packages/btsow-source-1.0.1.zip",
      "desc": "一句话描述"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| id | 插件唯一标识，安装后即本地目录名 |
| name | 显示名 |
| version | 版本号，App 用它判断"有新版" |
| type | `source`（爬虫源）/`server`（本地服务） |
| engine | `source` 对应 `py`（Chaquopy）/`js`（QuickJS）/`php`（T4）；`server` 对应 `nodejs` |
| md5 | zip 包 MD5，**App 安装时强制校验**，不一致拒绝安装 |
| url | zip 下载地址 |
| desc | 一句话描述 |

## 发版流程

1. 把新 zip 放进 `packages/`（文件名含版本号，如 `xxx-1.0.2.zip`）。
2. `md5sum packages/<file>` 取实测值。
3. 在 `market.json` 里新增或更新对应条目（`updated` 改成当天日期）。
4. commit + push，App 下次打开市场页即能看到。

注意：同名 zip 绝不覆盖重传（md5 即内容校验），改内容必须换文件名+升 version。
