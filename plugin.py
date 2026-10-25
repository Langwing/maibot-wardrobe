"""衣柜插件。

给麦麦本体维护一个虚拟衣柜：预置一批符合人设的衣服，
每天在设定时间决定当日穿搭（AI 决定或插件静默决定），换装后按
"分享欲"决定要不要主动来晒（可能配图），平时聊天中可以自然地
查看衣柜、聊穿搭、逛街买新衣、扔旧衣。

核心机制：
- 每日到点掷骰：random() < share_desire → "晒"路径，向分享目标
  触发 Maisaka 主动任务，由 AI 查天气（高德 MCP）→ wardrobe_list
  → wardrobe_pick → 自然展示，按掷骰结果决定是否配绘图工具出图；
- 否则"静默"路径：插件按季节随机搭配（40% 概率标志穿搭），
  通过 maisaka.context.append 把"今天穿了什么"写成静默事实，
 麦麦聊天时自然知道自己这一身，但不会主动提起；
- 5 个 LLM 工具供聊天中随时调用；白名单/黑名单同备忘录插件。

衣服清单存放在插件配置（config.toml 的 [items.*] 表）中，
可在 WebUI 插件配置页面直接查看、编辑、新增、删除；
今日穿搭与历史记录存放在数据文件 wardrobe_state.json 中。
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from maibot_sdk import API, MaiBotPlugin, Tool
from maibot_sdk.config import Field, PluginConfigBase
from maibot_sdk.types import ToolParameterInfo, ToolParamType

try:
    import tomlkit
except ImportError:  # pragma: no cover - 容器内已随其他插件依赖安装
    tomlkit = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 预置衣柜：麦麦的初始衣服清单（id 稳定，不要改动已有编号）
# 分类体系 v3：上衣 / 下装 / 全身装 / 套装 / 外套 / 鞋子 / 袜子 / 内衣 / 配饰 / 睡衣家居
#   - 全身装：一件式的衣服（连衣裙、死库水/泳装、旗袍、和服等）
#   - 套装：上下成套设计的（JK制服、女仆套装、运动服等）
#   - 内衣：贴身衣物（文胸、内裤、吊带背心、运动内衣等）
#   - 睡衣家居：睡觉和在家穿的（睡裙、浴袍、家居服）
# ----------------------------------------------------------------------
CATEGORIES = ["上衣", "下装", "全身装", "套装", "外套", "鞋子", "袜子", "内衣", "配饰", "睡衣家居"]

# 旧分类 → 新分类（v1 的上装/连衣裙 改名；其余同名）
_LEGACY_CATEGORY_MAP = {"上装": "上衣", "连衣裙": "全身装"}

# 分类体系版本标记（数据文件 category_scheme 字段）：
# v2=九分类，v3=新增内衣分类
_CATEGORY_SCHEME = "v3"

SEASONS = ["spring", "summer", "autumn", "winter", "all"]

PRESET_ITEMS: list[dict[str, Any]] = [
    # 标志穿搭（人设初始：白色荷叶边衬衫+格纹马甲+格纹裙+过膝袜+高跟鞋+铃铛）
    {"id": "w001", "name": "白色荷叶边衬衫", "category": "上衣", "seasons": ["all"], "color": "白", "tags": ["标志", "女仆", "日常"], "signature": True},
    {"id": "w002", "name": "棕色格纹马甲", "category": "外套", "seasons": ["all"], "color": "棕", "tags": ["标志", "叠穿", "学院"], "signature": True},
    {"id": "w003", "name": "棕色格纹半身裙", "category": "下装", "seasons": ["all"], "color": "棕", "tags": ["标志", "学院"], "signature": True},
    {"id": "w004", "name": "棕色过膝袜", "category": "袜子", "seasons": ["all"], "color": "棕", "tags": ["标志"], "signature": True},
    {"id": "w005", "name": "黑色高跟鞋", "category": "鞋子", "seasons": ["all"], "color": "黑", "tags": ["标志"], "signature": True},
    {"id": "w006", "name": "红蝴蝶结金色铃铛", "category": "配饰", "seasons": ["all"], "color": "红", "tags": ["标志", "项圈"], "signature": True},
    # 上衣
    {"id": "w007", "name": "奶茶色高领针织衫", "category": "上衣", "seasons": ["winter"], "color": "奶茶色", "tags": ["温暖", "居家"]},
    {"id": "w008", "name": "淡黄色泡泡袖衬衫", "category": "上衣", "seasons": ["spring", "autumn"], "color": "淡黄", "tags": ["甜美"]},
    {"id": "w009", "name": "柑橙色连帽卫衣", "category": "上衣", "seasons": ["spring", "autumn", "winter"], "color": "柑橙", "tags": ["活力", "和发色很配"]},
    {"id": "w010", "name": "白底蓝条海魂衫", "category": "上衣", "seasons": ["summer"], "color": "白蓝", "tags": ["清爽", "海边"]},
    {"id": "w011", "name": "米白色棉麻衬衫", "category": "上衣", "seasons": ["spring", "summer", "autumn"], "color": "米白", "tags": ["透气", "日常"]},
    {"id": "w012", "name": "黑色短袖T恤", "category": "上衣", "seasons": ["summer"], "color": "黑", "tags": ["简单", "居家"]},
    {"id": "w013", "name": "姜黄色复古毛衣", "category": "上衣", "seasons": ["autumn", "winter"], "color": "姜黄", "tags": ["复古", "温暖"]},
    {"id": "w014", "name": "白色水手服上衣", "category": "上衣", "seasons": ["spring", "autumn"], "color": "白", "tags": ["学院"]},
    {"id": "w015", "name": "碎花泡泡袖衬衫", "category": "上衣", "seasons": ["summer"], "color": "白底碎花", "tags": ["田园", "甜美"]},
    # 下装
    {"id": "w016", "name": "黑色百褶裙", "category": "下装", "seasons": ["spring", "autumn", "winter"], "color": "黑", "tags": ["百搭"]},
    {"id": "w017", "name": "蓝色牛仔短裤", "category": "下装", "seasons": ["summer"], "color": "蓝", "tags": ["清凉"]},
    {"id": "w018", "name": "米色棉麻半身长裙", "category": "下装", "seasons": ["spring", "summer", "autumn"], "color": "米色", "tags": ["轻盈"]},
    {"id": "w019", "name": "卡其色工装裤", "category": "下装", "seasons": ["all"], "color": "卡其", "tags": ["利落", "做家务方便"]},
    {"id": "w020", "name": "深棕色灯芯绒长裤", "category": "下装", "seasons": ["autumn", "winter"], "color": "深棕", "tags": ["复古", "温暖"]},
    # 全身装（一件式：连衣裙、死库水等）
    {"id": "w021", "name": "黑白女仆连衣裙", "category": "全身装", "seasons": ["all"], "color": "黑白", "tags": ["工作装", "正式待客"]},
    {"id": "w022", "name": "碎花吊带连衣裙", "category": "全身装", "seasons": ["summer"], "color": "碎花", "tags": ["夏日", "甜美"]},
    {"id": "w023", "name": "奶白色针织连衣裙", "category": "全身装", "seasons": ["winter"], "color": "奶白", "tags": ["温柔"]},
    {"id": "w024", "name": "蓝白水手服连衣裙", "category": "全身装", "seasons": ["spring", "autumn"], "color": "蓝白", "tags": ["学院", "出街"]},
    {"id": "w025", "name": "橘色波点连衣裙", "category": "全身装", "seasons": ["summer"], "color": "橘", "tags": ["活泼"]},
    {"id": "w046", "name": "深蓝色死库水", "category": "全身装", "seasons": ["summer"], "color": "深蓝", "tags": ["夏日", "泳池"]},
    # 套装（上下成套）
    {"id": "w047", "name": "水手服JK套装", "category": "套装", "seasons": ["spring", "autumn"], "color": "藏青", "tags": ["学院", "经典"]},
    {"id": "w048", "name": "运动服套装", "category": "套装", "seasons": ["spring", "autumn"], "color": "灰白", "tags": ["运动", "轻便"]},
    # 外套
    {"id": "w026", "name": "米色针织开衫", "category": "外套", "seasons": ["spring", "autumn"], "color": "米色", "tags": ["居家", "温柔"]},
    {"id": "w027", "name": "牛仔短外套", "category": "外套", "seasons": ["spring", "autumn"], "color": "蓝", "tags": ["休闲"]},
    {"id": "w028", "name": "燕麦色呢子大衣", "category": "外套", "seasons": ["winter"], "color": "燕麦", "tags": ["保暖", "优雅"]},
    {"id": "w029", "name": "白色羽绒服马甲", "category": "外套", "seasons": ["winter"], "color": "白", "tags": ["轻便保暖"]},
    {"id": "w030", "name": "卡其色风衣", "category": "外套", "seasons": ["autumn"], "color": "卡其", "tags": ["利落", "挡风"]},
    # 鞋子
    {"id": "w031", "name": "小白鞋", "category": "鞋子", "seasons": ["all"], "color": "白", "tags": ["百搭", "日常"]},
    {"id": "w032", "name": "棕色小皮鞋", "category": "鞋子", "seasons": ["all"], "color": "棕", "tags": ["学院", "日常"]},
    {"id": "w033", "name": "米色毛绒居家拖鞋", "category": "鞋子", "seasons": ["all"], "color": "米色", "tags": ["居家"]},
    {"id": "w034", "name": "米白色雪地靴", "category": "鞋子", "seasons": ["winter"], "color": "米白", "tags": ["保暖"]},
    {"id": "w035", "name": "柑橙色帆布鞋", "category": "鞋子", "seasons": ["spring", "summer", "autumn"], "color": "柑橙", "tags": ["活力"]},
    # 袜子
    {"id": "w036", "name": "白色短袜", "category": "袜子", "seasons": ["all"], "color": "白", "tags": ["日常"]},
    {"id": "w037", "name": "黑色薄丝袜", "category": "袜子", "seasons": ["spring", "autumn"], "color": "黑", "tags": ["正式"]},
    {"id": "w038", "name": "奶白色加绒裤袜", "category": "袜子", "seasons": ["winter"], "color": "奶白", "tags": ["保暖"]},
    {"id": "w039", "name": "橘白条纹中筒袜", "category": "袜子", "seasons": ["all"], "color": "橘白", "tags": ["俏皮"]},
    # 内衣
    {"id": "w051", "name": "白色无钢圈文胸", "category": "内衣", "seasons": ["all"], "color": "白", "tags": ["日常", "舒适"]},
    {"id": "w052", "name": "白色纯棉内裤", "category": "内衣", "seasons": ["all"], "color": "白", "tags": ["日常"]},
    {"id": "w053", "name": "蕾丝吊带背心", "category": "内衣", "seasons": ["spring", "summer", "autumn"], "color": "白", "tags": ["内搭"]},
    {"id": "w054", "name": "灰色运动内衣", "category": "内衣", "seasons": ["spring", "summer", "autumn"], "color": "灰", "tags": ["运动"]},
    # 配饰
    {"id": "w040", "name": "柑橙色贝雷帽", "category": "配饰", "seasons": ["autumn", "winter"], "color": "柑橙", "tags": ["和耳朵很配"]},
    {"id": "w041", "name": "米色针织围巾", "category": "配饰", "seasons": ["winter"], "color": "米色", "tags": ["温暖"]},
    {"id": "w042", "name": "草编遮阳帽", "category": "配饰", "seasons": ["summer"], "color": "米", "tags": ["夏日"]},
    {"id": "w043", "name": "珍珠发夹", "category": "配饰", "seasons": ["all"], "color": "珍珠白", "tags": ["精致"]},
    {"id": "w044", "name": "白色蕾丝发带", "category": "配饰", "seasons": ["all"], "color": "白", "tags": ["女仆", "甜美"]},
    {"id": "w045", "name": "小熊挂饰", "category": "配饰", "seasons": ["all"], "color": "棕", "tags": ["可爱", "挂在包上"]},
    # 睡衣家居
    {"id": "w049", "name": "白色棉质睡裙", "category": "睡衣家居", "seasons": ["all"], "color": "白", "tags": ["睡觉", "舒适"]},
    {"id": "w050", "name": "奶黄色家居服套装", "category": "睡衣家居", "seasons": ["all"], "color": "奶黄", "tags": ["居家", "软乎乎"]},
]

_TZ = ZoneInfo("Asia/Shanghai")
_LOOP_INTERVAL_SECONDS = 60
_CAPABILITY_TIMEOUT_SECONDS = 20
_MAX_SHARE_STREAMS = 3
_CATCHUP_WINDOW_MINUTES = 90  # 超过设定时间这么多分钟后补跑，只静默不晒
_SIGNATURE_ITEM_IDS = ["w001", "w002", "w003", "w004", "w005", "w006"]
_SIGNATURE_PROBABILITY = 0.4  # 静默换装时穿标志穿搭的概率
_TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class _PluginSection(PluginConfigBase):
    """插件元信息配置节。"""

    config_version: str = "1.0.0"


class WardrobeItemConfig(PluginConfigBase):
    """单件衣服在配置页面中的结构。"""

    __ui_label__ = "衣服"

    name: str = Field(default="", description="衣服名字，如：樱粉色针织开衫")
    category: str = Field(default="上衣", description="类别：上衣/下装/全身装/套装/外套/鞋子/袜子/内衣/配饰/睡衣家居")
    seasons: list[str] = Field(
        default_factory=list,
        description="适用季节：spring/summer/autumn/winter/all，可多选",
    )
    color: str = Field(default="", description="主色，如：樱粉")
    tags: list[str] = Field(default_factory=list, description="风格标签，如：甜美、新衣服")
    signature: bool = Field(default=False, description="是否标志单品（初始穿搭的一部分，不可丢弃）")
    source: str = Field(default="初始衣柜", description="来源：初始衣柜/主人送的/麦麦自己买的")
    acquired_at: float = Field(default=0.0, description="获得时间戳（不用管）")


class WardrobeConfig(PluginConfigBase):
    """衣柜插件配置。"""

    plugin: _PluginSection = Field(default_factory=_PluginSection)
    enabled: bool = Field(default=True, description="插件总开关")
    whitelist: list[str] = Field(
        default_factory=list,
        description="允许使用衣柜功能的用户 QQ 号列表；为空时聊天功能无人可用",
    )
    blacklist: list[str] = Field(
        default_factory=list,
        description="禁止使用衣柜功能的用户 QQ 号列表，优先于白名单",
    )
    share_desire: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="分享欲滑条（0-1）：数值越高，每天越想主动晒穿搭、晒的时候越想配图",
    )
    daily_outfit_time: str = Field(
        default="08:00",
        description="每天决定当日穿搭的时间，24 小时制 HH:MM，如 08:00",
    )
    weather_city: str = Field(
        default="",
        description="查天气用的城市名（如 杭州），留空则按季节估计、不查真实天气",
    )
    share_to_streams: list[str] = Field(
        default_factory=list,
        description='主动晒穿搭的目标，格式 ["qq:private:QQ号"] 或 ["qq:group:群号"]；留空则晒给白名单用户的私聊',
    )
    image_enable: bool = Field(default=True, description="分享欲满足时是否允许配绘图效果图")
    max_items: int = Field(default=200, ge=10, le=2000, description="衣柜容量上限")
    max_history: int = Field(default=30, ge=5, le=365, description="保留的穿搭历史天数")
    items: dict[str, WardrobeItemConfig] = Field(
        default_factory=dict,
        description="衣柜里的衣服，以编号为键；可在下方表格里查看、编辑、新增、删除",
    )


def _now() -> datetime:
    return datetime.now(tz=_TZ)


def _extract_stream_id(stream_result: Any) -> str:
    stream = stream_result
    if isinstance(stream_result, dict) and isinstance(stream_result.get("stream"), dict):
        stream = stream_result["stream"]
    if not isinstance(stream, dict):
        return ""
    return str(stream.get("stream_id") or stream.get("session_id") or "").strip()


def _season_of(month: int) -> str:
    if 3 <= month <= 5:
        return "spring"
    if 6 <= month <= 8:
        return "summer"
    if 9 <= month <= 11:
        return "autumn"
    return "winter"


class WardrobeStore:
    """今日穿搭与历史记录的 JSON 持久化存储（衣服清单在插件配置中）。"""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.today: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self.last_morning_run: str = ""
        self.category_scheme: str = ""  # 分类体系版本标记（当前 v2），用于一次性升级
        self.legacy_items: dict[str, dict[str, Any]] = {}  # 旧版数据文件里的衣服，用于迁移

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("衣柜数据文件读取失败，将忽略已有数据: %s", self._path)
            return
        self.today = data.get("today") or None
        self.history = list(data.get("history") or [])
        self.last_morning_run = str(data.get("last_morning_run") or "")
        self.category_scheme = str(data.get("category_scheme") or "")
        legacy = data.get("items")
        if isinstance(legacy, dict) and legacy:
            self.legacy_items = {str(k): dict(v) for k, v in legacy.items()}

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "today": self.today,
                "history": self.history,
                "last_morning_run": self.last_morning_run,
                "category_scheme": self.category_scheme,
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except Exception:
            logger.exception("衣柜数据保存失败: %s", self._path)

    def record_outfit(
        self,
        item_ids: list[str],
        description: str,
        reason: str,
        decided_by: str,
        max_history: int = 30,
    ) -> dict[str, Any]:
        today_str = _now().strftime("%Y-%m-%d")
        entry = {
            "date": today_str,
            "item_ids": item_ids,
            "description": description,
            "reason": reason,
            "decided_by": decided_by,
            "decided_at": time.time(),
        }
        # 同一天重复决定时只更新 today；历史只收前一天及以前的
        if self.today and self.today.get("date") != today_str:
            self.history.insert(0, dict(self.today))
        self.history = self.history[: max(5, int(max_history))]
        self.today = entry
        self.save()
        return entry


class WardrobePlugin(MaiBotPlugin):
    """衣柜插件主类。"""

    config_model = WardrobeConfig

    def __init__(self) -> None:
        super().__init__()
        self._store: WardrobeStore | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._time_format_warned = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def on_load(self) -> None:
        data_dir = Path(self.ctx.paths.data_dir)
        self._store = WardrobeStore(data_dir / "wardrobe_state.json")
        self._store.load()
        self._ensure_items()
        self._upgrade_category_scheme()
        self._store.save()  # 迁移后重写数据文件（去掉旧 items 字段）
        self._loop_task = asyncio.create_task(self._schedule_loop())
        logger.info(
            "衣柜插件已加载：衣服 %d 件，分享欲 %.2f，每日换装 %s，白名单 %d 人",
            len(self.config.items),
            float(self.config.share_desire),
            self._daily_time_str(),
            len(self.config.whitelist or []),
        )

    async def on_unload(self) -> None:
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        if self._store is not None:
            self._store.save()
        self._store = None

    async def on_config_update(self, scope: str, config_data: dict[str, Any], version: str) -> None:
        del config_data, version
        if scope == "self":
            logger.info(
                "衣柜插件配置已更新（当前衣服 %d 件，分享欲 %.2f）",
                len(self.config.items),
                float(self.config.share_desire),
            )

    # ------------------------------------------------------------------
    # 衣服清单：存放于插件配置，支持 WebUI 编辑与插件写入双通道
    # ------------------------------------------------------------------

    @property
    def _config_path(self) -> Path:
        return Path(__file__).parent / "config.toml"

    def _ensure_items(self) -> None:
        """迁移旧数据或播种预置衣柜（仅当配置中没有任何衣服时）。"""
        if self.config.items:
            return
        if self._store is not None and self._store.legacy_items:
            for item_id, raw in self._store.legacy_items.items():
                self.config.items[item_id] = WardrobeItemConfig(
                    name=str(raw.get("name", "")),
                    category=str(raw.get("category", "配饰")),
                    seasons=[str(s) for s in raw.get("seasons") or []] or ["all"],
                    color=str(raw.get("color", "")),
                    tags=[str(t) for t in raw.get("tags") or []],
                    signature=bool(raw.get("signature", False)),
                    source=str(raw.get("source", "初始衣柜")),
                    acquired_at=float(raw.get("acquired_at", 0.0)),
                )
            logger.info("已从旧数据文件迁移衣柜：%d 件", len(self.config.items))
            self._save_items_to_disk()
            return
        for item in PRESET_ITEMS:
            self.config.items[item["id"]] = WardrobeItemConfig(
                name=item["name"],
                category=item["category"],
                seasons=list(item["seasons"]),
                color=item["color"],
                tags=list(item["tags"]),
                signature=bool(item.get("signature", False)),
                source="初始衣柜",
                acquired_at=0.0,
            )
        logger.info("已初始化预置衣柜：%d 件", len(self.config.items))
        self._save_items_to_disk()

    def _upgrade_category_scheme(self) -> None:
        """按数据文件 category_scheme 标记做一次性分类升级。

        v2：上装→上衣、连衣裙→全身装，补 w046-w050；
        v3：新增内衣分类，补 w051-w054。
        每档只补当次新增的衣服，不复活用户之前删掉的旧衣。
        """
        if self._store is None or self._store.category_scheme == _CATEGORY_SCHEME:
            return
        scheme = self._store.category_scheme
        renamed = 0
        added = 0
        if scheme in ("", "v1"):
            for item in self.config.items.values():
                new_cat = _LEGACY_CATEGORY_MAP.get(item.category)
                if new_cat:
                    item.category = new_cat
                    renamed += 1
        if scheme in ("", "v1", "v2"):
            # v2 数据只补 v3 新衣；更老的数据补 v2+v3 全部新衣
            id_min = "w051" if scheme == "v2" else "w046"
            for preset in PRESET_ITEMS:
                if preset["id"] >= id_min and preset["id"] not in self.config.items:
                    self.config.items[preset["id"]] = WardrobeItemConfig(
                        name=preset["name"],
                        category=preset["category"],
                        seasons=list(preset["seasons"]),
                        color=preset["color"],
                        tags=list(preset["tags"]),
                        signature=bool(preset.get("signature", False)),
                        source="初始衣柜",
                        acquired_at=0.0,
                    )
                    added += 1
        self._store.category_scheme = _CATEGORY_SCHEME
        if renamed or added:
            self._save_items_to_disk()
            logger.info(
                "衣柜分类已升级到 %s（原 %s）：改名 %d 件，补充新衣 %d 件",
                _CATEGORY_SCHEME, scheme or "无标记", renamed, added,
            )

    def _save_items_to_disk(self) -> None:
        """把当前衣服清单写回 config.toml（保留文件中其它内容与注释）。"""
        if tomlkit is None:
            logger.warning("tomlkit 不可用，衣服清单未写入 config.toml（重启后需重新迁移）")
            return
        config_path = self._config_path
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    doc = tomlkit.load(f)
            else:
                doc = tomlkit.document()

            items_table = tomlkit.table()
            for item_id, item in self.config.items.items():
                table = tomlkit.table()
                table["name"] = item.name
                table["category"] = item.category
                table["seasons"] = list(item.seasons)
                table["color"] = item.color
                table["tags"] = list(item.tags)
                table["signature"] = bool(item.signature)
                table["source"] = item.source
                table["acquired_at"] = float(item.acquired_at)
                items_table.add(item_id, table)

            doc["items"] = items_table
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                tomlkit.dump(doc, f)
        except Exception:
            logger.exception("衣服清单持久化到 config.toml 失败")

    def _items_in_season(self, season: str, category: str | None = None) -> list[tuple[str, WardrobeItemConfig]]:
        return [
            (item_id, item)
            for item_id, item in self.config.items.items()
            if (category is None or item.category == category)
            and (season in item.seasons or "all" in item.seasons)
        ]

    # ------------------------------------------------------------------
    # 权限
    # ------------------------------------------------------------------

    def _user_allowed(self, user_id: str) -> bool:
        uid = str(user_id).strip()
        if not uid:
            return False
        if uid in {str(x).strip() for x in (self.config.blacklist or []) if str(x).strip()}:
            return False
        whitelist = {str(x).strip() for x in (self.config.whitelist or []) if str(x).strip()}
        if not whitelist:
            return False
        return uid in whitelist

    def _check_caller(self, user_id: str) -> dict[str, Any] | None:
        """工具权限检查：user_id 留空视为麦麦本人（每日任务）放行。"""
        uid = str(user_id or "").strip()
        if not uid:
            return None  #麦麦自己的操作
        if not self._user_allowed(uid):
            return {
                "success": False,
                "error": f"用户 {uid} 不在衣柜白名单中。请委婉告知对方这是麦麦和主人的小功能。",
            }
        return None

    # ------------------------------------------------------------------
    # 每日换装调度
    # ------------------------------------------------------------------

    def _daily_time_str(self) -> str:
        raw = str(self.config.daily_outfit_time or "").strip()
        if _TIME_PATTERN.match(raw):
            return raw
        if not self._time_format_warned:
            logger.warning("daily_outfit_time 格式非法（%r），回退为 08:00", raw)
            self._time_format_warned = True
        return "08:00"

    async def _schedule_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_LOOP_INTERVAL_SECONDS)
                if not self.config.enabled or self._store is None:
                    continue
                now = _now()
                today_str = now.strftime("%Y-%m-%d")
                if self._store.last_morning_run == today_str:
                    continue
                hour, minute = (int(x) for x in self._daily_time_str().split(":"))
                scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now < scheduled:
                    continue
                late_minutes = (now - scheduled).total_seconds() / 60
                await self._run_morning_task(force_silent=late_minutes > _CATCHUP_WINDOW_MINUTES)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("衣柜每日调度异常")
                await asyncio.sleep(60)

    async def _run_morning_task(self, *, force_silent: bool = False) -> None:
        """每日换装：掷骰决定晒不晒，然后走 AI 路径或静默路径。"""
        assert self._store is not None
        now = _now()
        today_str = now.strftime("%Y-%m-%d")
        share_desire = max(0.0, min(1.0, float(self.config.share_desire)))
        will_share = (not force_silent) and random.random() < share_desire
        will_image = bool(self.config.image_enable) and random.random() < share_desire

        logger.info(
            "衣柜每日换装：date=%s share_desire=%.2f will_share=%s will_image=%s force_silent=%s",
            today_str, share_desire, will_share, will_image, force_silent,
        )

        shared_any = False
        if will_share:
            stream_ids = await self._resolve_share_streams()
            for stream_id in stream_ids[:_MAX_SHARE_STREAMS]:
                if await self._trigger_morning_share(stream_id, share_desire=share_desire, with_image=will_image):
                    shared_any = True
        if not shared_any:
            # 静默路径：插件自己搭配，并写入上下文让 麦麦“知道”今天穿了什么
            if self._store.today and self._store.today.get("date") == today_str:
                description = self._store.today.get("description", "")
            else:
                entry = self._silent_pick_outfit()
                description = entry["description"]
            await self._append_silent_fact(description, share_desire)

        self._store.last_morning_run = today_str
        self._store.save()

    # ------------------------------------------------------------------
    # 静默搭配
    # ------------------------------------------------------------------

    def _silent_pick_outfit(self) -> dict[str, Any]:
        """插件自己挑一身（不经过 AI）：40% 标志穿搭，否则按季节随机组合。"""
        season = _season_of(_now().month)
        yesterday_ids: set[str] = set()
        if self._store is not None:
            if self._store.history:
                yesterday_ids = set(self._store.history[0].get("item_ids") or [])
            elif self._store.today:
                yesterday_ids = set(self._store.today.get("item_ids") or [])

        chosen: list[tuple[str, WardrobeItemConfig]] = []
        description = ""
        reason = ""
        for _ in range(6):
            if random.random() < _SIGNATURE_PROBABILITY and all(
                i in self.config.items for i in _SIGNATURE_ITEM_IDS
            ):
                chosen = [(i, self.config.items[i]) for i in _SIGNATURE_ITEM_IDS]
                description = "标志性的一身：白衬衫配格纹马甲和格纹裙，过膝袜加小高跟，铃铛也没忘"
                reason = "最安心的一套，怎么都不会出错"
            else:
                chosen = []
                base_roll = random.random()
                if base_roll < 0.3:
                    dresses = self._items_in_season(season, "全身装")
                    if dresses:
                        chosen.append(random.choice(dresses))
                elif base_roll < 0.45:
                    suits = self._items_in_season(season, "套装")
                    if suits:
                        chosen.append(random.choice(suits))
                else:
                    tops = self._items_in_season(season, "上衣")
                    bottoms = self._items_in_season(season, "下装")
                    if tops and bottoms:
                        chosen.extend([random.choice(tops), random.choice(bottoms)])
                outer_prob = {"winter": 0.7, "autumn": 0.45, "spring": 0.25, "summer": 0.05}[season]
                if random.random() < outer_prob:
                    outers = self._items_in_season(season, "外套")
                    if outers:
                        chosen.append(random.choice(outers))
                shoes = self._items_in_season(season, "鞋子")
                if shoes:
                    chosen.append(random.choice(shoes))
                socks = self._items_in_season(season, "袜子")
                if socks:
                    chosen.append(random.choice(socks))
                if random.random() < 0.55:
                    if random.random() < 0.6 and "w006" in self.config.items:
                        chosen.append(("w006", self.config.items["w006"]))
                    else:
                        accs = self._items_in_season(season, "配饰")
                        if accs:
                            chosen.append(random.choice(accs))
                if not chosen:
                    continue
                description = "、".join(item.name for _, item in chosen)
                season_cn = {"spring": "春天", "summer": "夏天", "autumn": "秋天", "winter": "冬天"}[season]
                reason = f"{season_cn}随手搭配的一身"
            if {item_id for item_id, _ in chosen} != yesterday_ids:
                break

        item_ids = [item_id for item_id, _ in chosen]
        assert self._store is not None
        return self._store.record_outfit(
            item_ids, description, reason,
            decided_by="plugin", max_history=int(self.config.max_history),
        )

    async def _append_silent_fact(self, description: str, share_desire: float) -> None:
        """把今天的穿搭写成静默事实，麦麦聊天时自然记得自己穿了什么。"""
        stream_ids = await self._resolve_share_streams()
        text = (
            f"（衣柜系统记录）今天麦麦换上了：{description}。"
            f"ta没打算特意提起这件事，但如果聊到穿搭、或被问起今天穿什么，"
            f"ta清楚记得自己这一身。（当前分享欲 {share_desire:.1f}/1.0，今天不想主动晒。）"
        )
        for stream_id in stream_ids[:_MAX_SHARE_STREAMS]:
            try:
                await asyncio.wait_for(
                    self.ctx.maisaka.append_context(
                        stream_id,
                        [{"type": "text", "content": text}],
                        visible_text=text,
                        source_kind="plugin:local.wardrobe",
                        message_id=f"wardrobe-fact:{stream_id}:{int(time.time())}",
                    ),
                    timeout=_CAPABILITY_TIMEOUT_SECONDS,
                )
            except Exception:
                logger.exception("写入衣柜静默事实失败: stream_id=%s", stream_id)

    # ------------------------------------------------------------------
    # 主动晒（AI 路径）
    # ------------------------------------------------------------------

    async def _resolve_share_streams(self) -> list[str]:
        """解析主动晒/写事实的目标聊天流，去重。"""
        targets: list[tuple[str, str, str]] = []  # (platform, chat_type, target_id)
        for raw in self.config.share_to_streams or []:
            parts = str(raw).strip().split(":")
            if len(parts) == 3 and parts[1] in {"group", "private"} and parts[0] and parts[2]:
                targets.append((parts[0], parts[1], parts[2]))
        if not targets:
            for uid in self.config.whitelist or []:
                uid = str(uid).strip()
                if uid:
                    targets.append(("qq", "private", uid))

        resolved: list[str] = []
        for platform, chat_type, target_id in targets:
            stream_id = await self._resolve_stream(platform, chat_type, target_id)
            if stream_id and stream_id not in resolved:
                resolved.append(stream_id)
        if not resolved:
            logger.info("衣柜无可用分享目标（share_to_streams 与白名单均未解析到聊天流）")
        return resolved

    async def _resolve_stream(self, platform: str, chat_type: str, target_id: str) -> str:
        try:
            if chat_type == "private":
                result = await asyncio.wait_for(
                    self.ctx.chat.get_stream_by_user_id(target_id, platform=platform),
                    timeout=_CAPABILITY_TIMEOUT_SECONDS,
                )
                sid = _extract_stream_id(result)
                if sid:
                    return sid
                result = await asyncio.wait_for(
                    self.ctx.chat.open_session(
                        platform=platform, chat_type="private", user_id=target_id
                    ),
                    timeout=_CAPABILITY_TIMEOUT_SECONDS,
                )
            else:
                result = await asyncio.wait_for(
                    self.ctx.chat.open_session(
                        platform=platform, chat_type="group", group_id=target_id
                    ),
                    timeout=_CAPABILITY_TIMEOUT_SECONDS,
                )
            return _extract_stream_id(result)
        except Exception as exc:
            logger.warning(
                "解析分享目标聊天流失败: %s:%s:%s error=%s", platform, chat_type, target_id, exc
            )
            return ""

    async def _trigger_morning_share(
        self, stream_id: str, *, share_desire: float, with_image: bool
    ) -> bool:
        """触发 AI 换装+晒穿搭的主动任务，成功返回 True。"""
        city = str(self.config.weather_city or "").strip()
        weather_line = (
            f"先用你的高德地图工具查一下「{city}」今天的天气（查询失败就按当前季节估计）"
            if city
            else "按当前季节和自己的感觉估计今天冷热"
        )
        image_line = (
            "今天的分享欲让你特别想配图：展示穿搭后，可以调用你的绘图工具画一张今天的穿搭效果图一起发出来。"
            if with_image
            else "今天只用文字描述穿搭就好，不要画图。"
        )
        intent = (
            "（衣柜系统·早晨换装任务）现在是早晨换装时间，麦麦今天分享欲比较高，想跟对方聊聊今天的穿搭。请按顺序完成：\n"
            f"1. {weather_line}；\n"
            "2. 调用 wardrobe_list 浏览一下衣柜（user_id 参数留空）；\n"
            "3. 结合天气和今天的心情，调用 wardrobe_pick 确定今天的穿搭（user_id 留空，item_ids 用衣柜编号，"
            "别挑昨天刚穿过的组合，衣柜清单里会标注昨天的穿搭）；\n"
            "4. 然后像平常聊天一样，自然地向对方分享你今天的穿搭决定，可以顺带提一句天气，"
            "保持你平时的语气，不要像在做报告。\n"
            f"{image_line}\n"
            f"（当前分享欲 {share_desire:.1f}/1.0）"
        )
        try:
            result = await asyncio.wait_for(
                self.ctx.maisaka.trigger_proactive(
                    stream_id,
                    intent,
                    reason="wardrobe.daily_outfit",
                    priority="low",
                    metadata={"plugin": "local.wardrobe", "task": "morning_outfit"},
                ),
                timeout=_CAPABILITY_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("触发早晨换装分享失败: stream_id=%s", stream_id)
            return False
        if isinstance(result, dict) and result.get("success") is False:
            logger.warning("早晨换装分享被拒绝: %s", result.get("error"))
            return False
        logger.info("已触发早晨换装分享: stream_id=%s with_image=%s", stream_id, with_image)
        return True

    # ------------------------------------------------------------------
    # LLM 工具
    # ------------------------------------------------------------------

    @Tool(
        "wardrobe_list",
        description=(
            "查看麦麦的衣柜清单。当用户想看看你有哪些衣服、你自己要挑今天穿什么、"
            "或想确认某件衣服在不在时调用。返回按类别分组的衣服清单（编号、名称、颜色、风格、季节），"
            "并附上今天和昨天的穿搭记录。"
            "分类说明：上衣、下装、全身装（连衣裙/死库水等一件式）、套装（JK制服/运动服等上下成套）、"
            "外套、鞋子、袜子、内衣（贴身衣物）、配饰、睡衣家居。"
            "参数说明：user_id（可选）提问用户的 QQ 号，麦麦自己决定穿搭时留空；"
            "category（可选）只看某一类（用上面的分类名）；"
            "season（可选）只看某季节：spring/summer/autumn/winter。"
        ),
        parameters=[
            ToolParameterInfo(name="user_id", param_type=ToolParamType.STRING, description="提问用户的 QQ 号；麦麦自己用时留空", required=False),
            ToolParameterInfo(name="category", param_type=ToolParamType.STRING, description="类别筛选：上衣/下装/全身装/套装/外套/鞋子/袜子/内衣/配饰/睡衣家居", required=False),
            ToolParameterInfo(name="season", param_type=ToolParamType.STRING, description="季节筛选：spring/summer/autumn/winter", required=False),
        ],
        visibility="visible",
    )
    async def wardrobe_list(self, **kwargs: Any) -> dict[str, Any]:
        """LLM 工具：衣柜清单。"""
        deny = self._check_caller(str(kwargs.get("user_id", "") or ""))
        if deny:
            return deny
        category = str(kwargs.get("category", "") or "").strip()
        season = str(kwargs.get("season", "") or "").strip()
        if category and category not in CATEGORIES:
            return {"success": False, "error": f"category 必须是 {CATEGORIES} 之一"}
        if season and season not in {"spring", "summer", "autumn", "winter"}:
            return {"success": False, "error": "season 必须是 spring/summer/autumn/winter 之一"}

        items = sorted(
            self.config.items.items(),
            key=lambda kv: (CATEGORIES.index(kv[1].category) if kv[1].category in CATEGORIES else 99, kv[0]),
        )
        lines = [f"衣柜共有 {len(items)} 件衣服（当前季节 {_season_of(_now().month)}）："]
        current_cat = ""
        for item_id, item in items:
            if category and item.category != category:
                continue
            if season and season not in item.seasons and "all" not in item.seasons:
                continue
            if item.category != current_cat:
                current_cat = item.category
                lines.append(f"【{current_cat}】")
            mark = "★" if item.signature else " "
            season_str = "四季" if "all" in item.seasons else "/".join(item.seasons)
            extra = f"｜{'/'.join(item.tags[:3])}" if item.tags else ""
            if item.source and item.source != "初始衣柜":
                extra += f"｜{item.source}"
            lines.append(f"{mark} {item_id} {item.name}（{item.color}｜{season_str}｜{item.category}{extra}）")
        if self._store is not None:
            if self._store.today:
                lines.append(f"今天穿的：{self._store.today['description']}（{self._store.today.get('reason', '')}）")
            if self._store.history:
                y = self._store.history[0]
                lines.append(f"昨天穿的：{y.get('description', '')}（挑今天的组合时尽量别和昨天完全一样）")
        return {"success": True, "content": "\n".join(lines), "count": len(items)}

    @Tool(
        "wardrobe_today",
        description=(
            "查询麦麦今天穿了什么（以及为什么这么穿）。当用户问“你今天穿什么呀”“今天什么搭配”时调用；"
            "如果今天还没决定穿搭，返回会提示尚未决定，这时可以顺势调用 wardrobe_list 和 wardrobe_pick 帮ta决定。"
            "返回里附有当前分享欲数值，数值高时可以更热情地聊穿搭、更想配图。"
            "参数说明：user_id（可选）提问用户的 QQ 号。"
        ),
        parameters=[
            ToolParameterInfo(name="user_id", param_type=ToolParamType.STRING, description="提问用户的 QQ 号；麦麦自己用时留空", required=False),
        ],
        visibility="visible",
    )
    async def wardrobe_today(self, **kwargs: Any) -> dict[str, Any]:
        """LLM 工具：今日穿搭。"""
        deny = self._check_caller(str(kwargs.get("user_id", "") or ""))
        if deny:
            return deny
        share_desire = max(0.0, min(1.0, float(self.config.share_desire)))
        today_str = _now().strftime("%Y-%m-%d")
        if self._store is None or not self._store.today or self._store.today.get("date") != today_str:
            return {
                "success": True,
                "content": f"今天还没决定穿搭。可以调用 wardrobe_list 看看衣柜，再用 wardrobe_pick 帮麦麦挑一身。（当前分享欲 {share_desire:.1f}/1.0）",
                "decided": False,
                "share_desire": share_desire,
            }
        t = self._store.today
        return {
            "success": True,
            "content": (
                f"今天（{t['date']}）穿：{t['description']}。理由：{t.get('reason', '')}。"
                f"（当前分享欲 {share_desire:.1f}/1.0）"
            ),
            "decided": True,
            "outfit": t,
            "share_desire": share_desire,
        }

    @Tool(
        "wardrobe_pick",
        description=(
            "确定麦麦今天的穿搭（会记录下来，之后聊天都会记得今天穿了这一身）。"
            "麦麦每天早晨自己换装时会调用；聊天中主人让ta换一身/重新搭配时也调用。"
            "item_ids 必须来自 wardrobe_list 返回的衣柜编号，建议 3-6 件、至少含一件上装/下装/连衣裙，"
            "再按需搭配外套、鞋袜和配饰；尽量符合当前季节，也尽量别和昨天完全一样。"
            "description 用一句话描述这身搭配，reason 说明为什么这么穿（天气/心情/场合）。"
            "参数说明：user_id（可选）发起人 QQ 号，麦麦自己换装时留空。"
        ),
        parameters=[
            ToolParameterInfo(name="item_ids", param_type=ToolParamType.STRING, description="衣柜编号列表，逗号分隔，如 w009,w017,w035,w039", required=True),
            ToolParameterInfo(name="description", param_type=ToolParamType.STRING, description="一句话描述这身搭配", required=True),
            ToolParameterInfo(name="reason", param_type=ToolParamType.STRING, description="为什么这么穿（天气/心情/场合）", required=True),
            ToolParameterInfo(name="user_id", param_type=ToolParamType.STRING, description="发起人 QQ 号；麦麦自己用时留空", required=False),
        ],
        visibility="visible",
    )
    async def wardrobe_pick(self, **kwargs: Any) -> dict[str, Any]:
        """LLM 工具：确定今日穿搭。"""
        deny = self._check_caller(str(kwargs.get("user_id", "") or ""))
        if deny:
            return deny
        if self._store is None:
            return {"success": False, "error": "插件尚未完成初始化"}
        raw_ids = str(kwargs.get("item_ids", "") or "")
        item_ids = [x.strip() for x in re.split(r"[,，\s]+", raw_ids) if x.strip()]
        description = str(kwargs.get("description", "") or "").strip()
        reason = str(kwargs.get("reason", "") or "").strip()
        if not item_ids:
            return {"success": False, "error": "item_ids 不能为空，请传 wardrobe_list 里的编号"}
        if not description or not reason:
            return {"success": False, "error": "description 和 reason 不能为空"}

        missing = [i for i in item_ids if i not in self.config.items]
        if missing:
            return {"success": False, "error": f"衣柜里没有这些编号：{','.join(missing)}，请先 wardrobe_list 确认"}
        core = [i for i in item_ids if self.config.items[i].category in {"上衣", "下装", "全身装", "套装"}]
        if not core:
            return {"success": False, "error": "至少要有一件上衣/下装/全身装/套装"}

        season = _season_of(_now().month)
        off_season = [
            self.config.items[i].name
            for i in item_ids
            if season not in self.config.items[i].seasons and "all" not in self.config.items[i].seasons
        ]
        names = "、".join(self.config.items[i].name for i in item_ids)
        entry = self._store.record_outfit(
            item_ids, description, reason,
            decided_by="ai", max_history=int(self.config.max_history),
        )
        note = f"（提醒：{','.join(off_season)} 不太适合当前季节，可以提一句）" if off_season else ""
        logger.info("AI 确定今日穿搭: %s", names)
        return {
            "success": True,
            "content": f"已记录今天的穿搭：{names}。{note}现在到聊天里自然地继续就好。",
            "outfit": entry,
        }

    @Tool(
        "wardrobe_shop",
        description=(
            "给衣柜添一件新衣服。两种场景：主人说“给你买件新衣服吧/这件送你”时（from_user=true），"
            "或麦麦自己逛街想买新衣服时（from_user=false）。请根据对话内容起一个具体的名字"
            "（如“樱粉色针织开衫”），选择合适的类别和季节。添加成功后记得开心地回应。"
            "分类说明：上衣、下装、全身装（连衣裙/死库水/泳装/旗袍等一件式）、套装（JK制服/女仆套装等上下成套）、"
            "外套、鞋子、袜子、内衣（文胸/内裤/吊带背心等贴身衣物）、配饰（帽子围巾发饰等）、睡衣家居（睡裙/浴袍/家居服）。"
            "参数说明：name（必填）衣服名字，要具体、带颜色或款式；"
            "category（必填）用上面的分类名；"
            "seasons（必填）适用季节，从 spring/summer/autumn/winter/all 里选，多个逗号分隔；"
            "color（可选）主色；tags（可选）风格标签，逗号分隔；"
            "from_user（必填）是否是主人送的；user_id（送衣人 QQ 号，主人送时填）。"
        ),
        parameters=[
            ToolParameterInfo(name="name", param_type=ToolParamType.STRING, description="衣服名字，具体、带颜色或款式", required=True),
            ToolParameterInfo(name="category", param_type=ToolParamType.STRING, description="类别：上衣/下装/全身装/套装/外套/鞋子/袜子/内衣/配饰/睡衣家居", required=True),
            ToolParameterInfo(name="seasons", param_type=ToolParamType.STRING, description="适用季节：spring/summer/autumn/winter/all，多个逗号分隔", required=True),
            ToolParameterInfo(name="color", param_type=ToolParamType.STRING, description="主色", required=False),
            ToolParameterInfo(name="tags", param_type=ToolParamType.STRING, description="风格标签，逗号分隔", required=False),
            ToolParameterInfo(name="from_user", param_type=ToolParamType.BOOLEAN, description="是否是主人送的", required=True),
            ToolParameterInfo(name="user_id", param_type=ToolParamType.STRING, description="送衣人 QQ 号；麦麦自己买时留空", required=False),
        ],
        visibility="visible",
    )
    async def wardrobe_shop(self, **kwargs: Any) -> dict[str, Any]:
        """LLM 工具：添新衣服。"""
        deny = self._check_caller(str(kwargs.get("user_id", "") or ""))
        if deny:
            return deny
        name = str(kwargs.get("name", "") or "").strip()
        category = str(kwargs.get("category", "") or "").strip()
        raw_seasons = str(kwargs.get("seasons", "") or "").strip()
        color = str(kwargs.get("color", "") or "").strip()
        tags = [x.strip() for x in re.split(r"[,，\s]+", str(kwargs.get("tags", "") or "")) if x.strip()]
        from_user = bool(kwargs.get("from_user", False))

        if not name:
            return {"success": False, "error": "name 不能为空"}
        if category not in CATEGORIES:
            return {"success": False, "error": f"category 必须是 {CATEGORIES} 之一"}
        seasons = [s for s in re.split(r"[,，\s]+", raw_seasons) if s]
        if not seasons:
            return {"success": False, "error": "seasons 不能为空"}
        normalized: list[str] = []
        for s in seasons:
            if s == "all":
                normalized = ["all"]
                break
            if s in {"spring", "summer", "autumn", "winter"}:
                normalized.append(s)
        if not normalized:
            return {"success": False, "error": "seasons 只能是 spring/summer/autumn/winter/all"}
        if len(self.config.items) >= int(self.config.max_items):
            return {"success": False, "error": f"衣柜已满（{self.config.max_items} 件），先扔点旧衣服吧"}

        new_id = "w1046"
        existing_nums = {int(k[1:]) for k in self.config.items if k.startswith("w") and k[1:].isdigit()}
        while int(new_id[1:]) in existing_nums:
            new_id = f"w{int(new_id[1:]) + 1}"
        self.config.items[new_id] = WardrobeItemConfig(
            name=name,
            category=category,
            seasons=normalized,
            color=color or "未指定",
            tags=tags or ["新衣服"],
            signature=False,
            source="主人送的" if from_user else "麦麦自己买的",
            acquired_at=time.time(),
        )
        self._save_items_to_disk()
        logger.info("衣柜添加新衣服: %s %s", new_id, name)
        who = "主人送的" if from_user else "自己买的"
        return {
            "success": True,
            "content": f"衣柜新添了「{name}」（编号 {new_id}，{who}）。现在衣柜共 {len(self.config.items)} 件。",
            "item_id": new_id,
        }

    @Tool(
        "wardrobe_discard",
        description=(
            "把一件衣服从衣柜里处理掉（穿旧了/不喜欢了/主人让扔）。标志单品（★标记的初始穿搭）不能扔。"
            "参数说明：item_id（必填）衣柜编号；user_id（可选）发起人 QQ 号。扔之前可以稍微表达一下不舍。"
        ),
        parameters=[
            ToolParameterInfo(name="item_id", param_type=ToolParamType.STRING, description="要处理的衣服编号", required=True),
            ToolParameterInfo(name="user_id", param_type=ToolParamType.STRING, description="发起人 QQ 号；麦麦自己用时留空", required=False),
        ],
        visibility="visible",
    )
    async def wardrobe_discard(self, **kwargs: Any) -> dict[str, Any]:
        """LLM 工具：处理旧衣服。"""
        deny = self._check_caller(str(kwargs.get("user_id", "") or ""))
        if deny:
            return deny
        item_id = str(kwargs.get("item_id", "") or "").strip()
        item = self.config.items.get(item_id)
        if not item:
            return {"success": False, "error": f"衣柜里没有编号 {item_id}，请先 wardrobe_list 确认"}
        if item.signature:
            return {
                "success": False,
                "error": f"「{item.name}」是标志单品（初始穿搭的一部分），不能扔掉",
            }
        name = item.name
        del self.config.items[item_id]
        self._save_items_to_disk()
        if self._store is not None and self._store.today and item_id in (self._store.today.get("item_ids") or []):
            self._store.today["item_ids"] = [i for i in self._store.today["item_ids"] if i != item_id]
            self._store.save()
        logger.info("衣柜移除衣服: %s %s", item_id, name)
        return {"success": True, "content": f"「{name}」已经从衣柜里处理掉了。现在衣柜共 {len(self.config.items)} 件。"}

    # ------------------------------------------------------------------
    # WebUI 扩展页接口（webui/index.html 通过 maibot.query/action 调用）
    # ------------------------------------------------------------------

    def _page_categories(self) -> list[str]:
        """标准分类 + 用户自建分类（保证页面能显示一切）。"""
        extras = sorted({i.category for i in self.config.items.values() if i.category and i.category not in CATEGORIES})
        return CATEGORIES + extras

    @staticmethod
    def _normalize_page_seasons(seasons: Any) -> list[str]:
        normalized: list[str] = []
        for s in seasons or []:
            s = str(s).strip()
            if s == "all":
                return ["all"]
            if s in {"spring", "summer", "autumn", "winter"} and s not in normalized:
                normalized.append(s)
        return normalized or ["all"]

    @API("wardrobe_page_state", version="1")
    async def api_page_state(self) -> dict[str, Any]:
        """WebUI 查询：衣柜清单（按分类排序）、今日穿搭、分享欲。"""
        items = sorted(
            self.config.items.items(),
            key=lambda kv: (
                self._page_categories().index(kv[1].category) if kv[1].category in self._page_categories() else 99,
                kv[0],
            ),
        )
        today = None
        if self._store is not None and self._store.today:
            today = {k: self._store.today.get(k) for k in ("date", "description", "reason")}
        return {
            "categories": self._page_categories(),
            "items": [
                {
                    "id": item_id,
                    "name": item.name,
                    "category": item.category,
                    "seasons": list(item.seasons),
                    "color": item.color,
                    "tags": list(item.tags),
                    "signature": bool(item.signature),
                    "source": item.source,
                }
                for item_id, item in items
            ],
            "today": today,
            "share_desire": max(0.0, min(1.0, float(self.config.share_desire))),
        }

    def _validate_page_item(self, name: str, category: str) -> tuple[str, str]:
        name = str(name or "").strip()
        category = str(category or "").strip()
        if not name:
            raise ValueError("衣服名字不能为空")
        if not category:
            raise ValueError("分类不能为空")
        if category not in self._page_categories():
            raise ValueError(f"分类必须是：{'/'.join(CATEGORIES)}（或保留已有分类）")
        return name, category

    @API("wardrobe_page_set_item", version="1")
    async def api_page_set_item(
        self,
        item_id: str,
        name: str,
        category: str,
        seasons: Any = None,
        color: str = "",
        tags: Any = None,
        signature: bool = False,
    ) -> dict[str, Any]:
        """WebUI 操作：修改一件衣服。"""
        item_id = str(item_id or "").strip()
        item = self.config.items.get(item_id)
        if item is None:
            raise ValueError(f"衣柜里没有编号 {item_id}")
        if len(self.config.items) >= int(self.config.max_items) and item_id not in self.config.items:
            raise ValueError(f"衣柜已满（{self.config.max_items} 件）")
        name, category = self._validate_page_item(name, category)
        item.name = name
        item.category = category
        item.seasons = self._normalize_page_seasons(seasons)
        item.color = str(color or "").strip() or item.color or "未指定"
        item.tags = [str(t).strip() for t in (tags or []) if str(t).strip()]
        item.signature = bool(signature)
        self._save_items_to_disk()
        return {"id": item_id, "name": name}

    @API("wardrobe_page_add_item", version="1")
    async def api_page_add_item(
        self,
        name: str,
        category: str,
        seasons: Any = None,
        color: str = "",
        tags: Any = None,
        signature: bool = False,
    ) -> dict[str, Any]:
        """WebUI 操作：新增一件衣服。"""
        if len(self.config.items) >= int(self.config.max_items):
            raise ValueError(f"衣柜已满（{self.config.max_items} 件），先处理掉几件吧")
        name, category = self._validate_page_item(name, category)
        new_id = "w1046"
        existing_nums = {int(k[1:]) for k in self.config.items if k.startswith("w") and k[1:].isdigit()}
        while int(new_id[1:]) in existing_nums:
            new_id = f"w{int(new_id[1:]) + 1}"
        self.config.items[new_id] = WardrobeItemConfig(
            name=name,
            category=category,
            seasons=self._normalize_page_seasons(seasons),
            color=str(color or "").strip() or "未指定",
            tags=[str(t).strip() for t in (tags or []) if str(t).strip()] or ["新衣服"],
            signature=bool(signature),
            source="主人添置",
            acquired_at=time.time(),
        )
        self._save_items_to_disk()
        logger.info("WebUI 添加衣服: %s %s", new_id, name)
        return {"id": new_id, "name": name}

    @API("wardrobe_page_remove_item", version="1")
    async def api_page_remove_item(self, item_id: str) -> dict[str, Any]:
        """WebUI 操作：从衣柜移除一件衣服（标志单品也允许，主人说了算）。"""
        item_id = str(item_id or "").strip()
        item = self.config.items.get(item_id)
        if item is None:
            raise ValueError(f"衣柜里没有编号 {item_id}")
        name = item.name
        del self.config.items[item_id]
        if self._store is not None and self._store.today and item_id in (self._store.today.get("item_ids") or []):
            self._store.today["item_ids"] = [i for i in self._store.today["item_ids"] if i != item_id]
            self._store.save()
        self._save_items_to_disk()
        logger.info("WebUI 移除衣服: %s %s", item_id, name)
        return {"removed": item_id, "name": name}


def create_plugin() -> WardrobePlugin:
    """插件工厂函数。"""
    return WardrobePlugin()
