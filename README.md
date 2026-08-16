# 📢 OvOrange-B站开播推送

AstrBot 插件，联动 bilimonitor 的开播状态接口，主播开播时自动推送通知到指定会话。

## 💡 核心功能

- **开播即推**：轮询 `/api/status` 接口，检测到主播开播立即推送。
- **防重复推送**：上次开播状态持久化存储，重启插件不会重复推送。
- **防误报**：状态查询失败时跳过本轮，服务恢复后不会误报。
- **信息自动补全**：从 `/api/rooms` 获取主播名和直播标题，失败时自动降级为房间号。
- **模板可定制**：通知文案支持 `{uname}` `{title}` `{room_id}` `{url}` 占位符。

## 📂 项目结构

```text
astrbot_plugin_live_notify/
├── main.py           # 插件主体，轮询与推送
├── _conf_schema.json # 配置项
├── metadata.yaml     # 插件元数据
├── logo.png          # 插件 Logo
└── README.md         # 项目说明
```

## 🎮 指令清单

| 指令 | 说明 |
| :--- | :--- |
| `/live_notify bind` | 绑定当前会话为推送目标 |
| `/live_notify unbind` | 解绑当前会话 |
| `/live_notify list` | 查看监控房间和推送目标 |
| `/live_notify status` | 手动查询一次开播状态 |

## ⚙️ 插件设置说明

在 AstrBot Web 面板的插件配置中填写：

- **接口地址 api_base**：bilimonitor 服务地址，如 `http://127.0.0.1:8080`。
- **监控房间 room_ids**：要监控开播的房间号，逗号或换行分隔，支持短号。
- **轮询间隔 interval**：状态轮询间隔，单位秒，建议不小于 15。
- **推送目标 target_umos**：推送会话列表，一行一个，也可用 `/live_notify bind` 绑定。
- **信息补全 fetch_meta**：是否从 `/api/rooms` 获取主播名和直播标题，默认开启。
- **通知模板 message_template**：推送文案，支持 `{uname}` `{title}` `{room_id}` `{url}`。

## 🚀 安装

1. 将 `astrbot_plugin_live_notify` 目录放入 AstrBot 的 `data/plugins/`。
2. 在 AstrBot WebUI 中启用并重载插件。
3. 在目标会话发送 `/live_notify bind` 绑定推送目标。

## 📌 注意事项

- 主动推送依赖平台适配器支持主动消息，QQ 官方接口和企业微信不支持。
- 需要 bilimonitor 提供 `/api/status` 开播状态接口，请先确认接口可用。
- 接口状态缓存 30 秒，轮询间隔小于 30 秒也无法更实时。

---

**仓库地址：** https://github.com/KuAasagi/OvOrange-api
*本插件仅供技术交流使用，请合理使用接口并遵守相关法律法规。*
