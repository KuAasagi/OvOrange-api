"""开播推送：轮询 bilimonitor 开播状态接口，主播开播时向绑定会话推送通知。"""
import asyncio
import re

import httpx

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star

_STATE_KEY = "live_state"


def parse_rooms(text):
    """解析房间号，逗号、换行、空白分隔，自动去重。"""
    rooms = []
    for token in re.split(r"[,，\n\r\t\s]+", text or ""):
        token = token.strip()
        if not token.isdigit():
            continue
        rid = int(token)
        if rid > 0 and rid not in rooms:
            rooms.append(rid)
    return rooms


class LiveNotifyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.client = httpx.AsyncClient(timeout=15, trust_env=False)  # 不走 AstrBot 全局代理，直连内部接口
        self.task = None

    async def initialize(self):
        self.task = asyncio.create_task(self.loop())
        logger.info(f"开播推送已启动，轮询间隔 {self.interval} 秒")

    async def terminate(self):
        if self.task:
            self.task.cancel()
        await self.client.aclose()

    @property
    def api_base(self):
        return str(self.config.get("api_base") or "http://127.0.0.1:8080").rstrip("/")

    @property
    def interval(self):
        try:
            value = int(self.config.get("interval"))
        except (TypeError, ValueError):
            value = 30
        return value if 10 <= value <= 3600 else 30

    @property
    def rooms(self):
        return parse_rooms(self.config.get("room_ids", ""))

    @property
    def targets(self):
        return [t.strip() for t in re.split(r"[\n,，]+", str(self.config.get("target_umos", ""))) if t.strip()]

    async def loop(self):
        while True:
            try:
                await self.check_once()
            except Exception:
                logger.exception("开播推送轮询异常")
            await asyncio.sleep(self.interval)

    async def fetch_status(self, rooms):
        """查询开播状态，失败返回 None。"""
        try:
            resp = await self.client.get(
                f"{self.api_base}/api/status",
                params=[("room_id", rid) for rid in rooms],
            )
            resp.raise_for_status()
            return {int(i["room_id"]): bool(i["live"]) for i in resp.json().get("items", [])}
        except Exception as e:
            logger.warning(f"状态查询失败：{e}")
            return None

    async def fetch_meta(self, rooms):
        """从 /api/rooms 补充主播名和直播标题，失败返回空字典。"""
        if not self.config.get("fetch_meta", True):
            return {}
        try:
            resp = await self.client.get(f"{self.api_base}/api/rooms")
            resp.raise_for_status()
            wanted = set(rooms)
            return {int(row["room_id"]): row for row in resp.json() if int(row["room_id"]) in wanted}
        except Exception as e:
            logger.warning(f"元信息获取失败：{e}")
            return {}

    async def check_once(self):
        rooms = self.rooms
        if not rooms or not self.targets:
            return
        status = await self.fetch_status(rooms)
        if status is None:
            return
        prev = await self.get_kv_data(_STATE_KEY, {}) or {}
        meta = await self.fetch_meta(rooms)
        for rid, live in status.items():
            if live and not prev.get(str(rid)):
                await self.notify(rid, meta.get(rid, {}))
        merged = {**prev, **{str(k): v for k, v in status.items()}}
        if merged != prev:
            await self.put_kv_data(_STATE_KEY, merged)

    async def notify(self, rid, meta):
        template = self.config.get("message_template") or "🎤 {uname} 开播啦！\n{title}\n{url}"
        text = (
            template.replace("{uname}", meta.get("uname") or f"房间 {rid}")
            .replace("{title}", meta.get("title") or "")
            .replace("{room_id}", str(rid))
            .replace("{url}", f"https://live.bilibili.com/{rid}")
        )
        chain = MessageChain([Plain(text)])
        for umo in self.targets:
            try:
                ok = await self.context.send_message(umo, chain)
                if ok:
                    logger.info(f"开播推送成功：{rid} -> {umo}")
                else:
                    logger.warning(f"找不到 {umo} 对应的平台")
            except Exception as e:
                logger.error(f"开播推送失败 {umo}：{e}")

    @filter.command("live_notify")
    async def live_notify(self, event: AstrMessageEvent, action: str = "help"):
        """开播推送管理。"""
        umo = event.unified_msg_origin
        if action == "bind":
            targets = self.targets
            if umo in targets:
                yield event.plain_result("当前会话已在推送目标中。")
                return
            self.config["target_umos"] = "\n".join(targets + [umo])
            self.config.save_config()
            yield event.plain_result(f"已绑定推送目标：{umo}")
        elif action == "unbind":
            self.config["target_umos"] = "\n".join(t for t in self.targets if t != umo)
            self.config.save_config()
            yield event.plain_result("已解绑当前会话。")
        elif action == "list":
            yield event.plain_result(
                f"监控房间：{'、'.join(map(str, self.rooms)) or '未配置'}\n"
                f"推送目标：{len(self.targets)} 个\n"
                f"轮询间隔：{self.interval} 秒"
            )
        elif action == "status":
            rooms = self.rooms
            if not rooms:
                yield event.plain_result("未配置监控房间。")
                return
            status = await self.fetch_status(rooms)
            if status is None:
                yield event.plain_result("状态查询失败，请检查 api_base 配置。")
                return
            meta = await self.fetch_meta(rooms)
            lines = [
                f"{'🟢' if status.get(r) else '⚫'} {meta.get(r, {}).get('uname') or f'房间 {r}'}（{r}）"
                for r in rooms
            ]
            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result(
                "开播推送插件\n"
                "/live_notify bind —— 绑定当前会话为推送目标\n"
                "/live_notify unbind —— 解绑当前会话\n"
                "/live_notify list —— 查看配置\n"
                "/live_notify status —— 手动查询开播状态"
            )
