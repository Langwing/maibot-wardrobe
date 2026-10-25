# 衣柜 | Wardrobe

> MaiBot 插件 · id: `local.wardrobe` · 版本 1.3.0 · 作者 GLM-5.3(flash提供前端) · MIT 协议（1.3.0：新增内衣分类，分类体系 v3）

## 安装

1. 把本仓库放进 MaiBot 的插件目录（git clone 或下载解压均可，目录名随意）：
   ```bash
   cd <你的 MaiBot>/plugins
   git clone https://github.com/Langwing/maibot-wardrobe.git
   ```
2. 重启 MaiBot，日志出现「衣柜插件已加载」即成功（首次加载自动播种 54 件预置衣服）；
3. 管理网页 → 插件管理 → 衣柜 → 配置：`whitelist` 填你的 QQ 号（**不填则功能基本不生效**），`weather_city` 可选填城市名。

> 🇨🇳 **国内源**：本插件与同系列的「可可喵的厨房」「备忘录待办」插件在 Gitee 均有国内镜像仓库，GitHub 访问不便时可从 Gitee 获取（镜像链接待补充）。

---

## 一、给人看的说明（使用者指南）

### 这是什么

给麦麦本体的一座虚拟衣柜。ta会每天换一身穿搭，心情好（分享欲高）的时候主动来找你晒，还可能画一张穿搭效果图；平时聊天里问ta"今天穿什么"，ta也记得清清楚楚。

### ta会怎么表现

- **每天到点换装**：时间在网页后台设置（默认 08:00）。换装时ta会看真实天气（使用高德MCP，需要在插件中自己配置）
- **分享欲滑条（0–1）**：这是本插件的灵魂设置——
  - 数值越高，ta越可能**主动来找你晒**今天的穿搭（概率=数值）
  - 数值越高，晒的时候越可能**配一张绘图工具画的效果图**（概率=数值）
  - 数值低的日子，ta就安安静静换好衣服，你不问ta不说
- **聊天里随时能玩**（限白名单用户）：

| 你说 | 麦麦会 |
|---|---|
| "你今天穿什么呀" | 告诉你今天这身和为什么这么穿 |
| "给我看看你的衣柜" | 列出所有衣服（带编号、颜色、季节） |
| "换一身搭配吧" | 重新挑一身并记下来 |
| "给你买件新衣服吧，樱粉色针织开衫" | 开心收下，挂进衣柜 |
| "这件旧衣服扔了吧" | 处理掉（标志穿搭不能扔） |

- **初始衣柜**：54 件衣服（作者创作时，麦麦性别为女性，所以衣柜里都是女生的衣服，可以自行替换，如果你喜欢女装大佬也不是不行）

### 使用前要做的两件事（网页后台 → 插件管理 → 衣柜 → 配置）

1. `whitelist` 填你的 QQ 号（**不填的话聊天功能谁都用不了**）
2. `weather_city` 填城市名（如"杭州"），换装时会查真实天气；不填就按季节估计

### 在网页后台管理衣服（1.2.0：专属页面）

**主入口**：网页后台侧边栏 → **可可喵的衣柜**（独立页面，不是配置表格）。页面顶部显示今天穿了什么和分享欲，中间是按分类筛选的衣服卡片（点分类圆片筛选），底部是新增栏。每张卡片上可以直接改名字/分类/颜色/季节（勾选四季=全季）/标签/是否标志★，按"存"生效，"删"移除（有确认弹窗）。改完立即生效，不用重启。

**备用入口**：插件管理 → 衣柜 → 配置里的 items 表格仍然可用（两处编辑的是同一份数据）。

### 分类体系（v3，共 10 类）

| 分类 | 放什么 | 例子 |
|---|---|---|
| 上衣 | 上半身穿的 | 衬衫、卫衣、毛衣、blouse |
| 下装 | 半身裙、裤子 | 格纹半身裙、工装裤 |
| 全身装 | 一件式的 | 连衣裙、死库水、泳装、旗袍 |
| 套装 | 上下成套设计的 | JK制服、女仆套装、运动服 |
| 外套 | 罩在最外面的 | 马甲、开衫、大衣 |
| 鞋子 | — | 高跟鞋、小白鞋、拖鞋 |
| 袜子 | — | 过膝袜、裤袜 |
| 内衣 | 贴身衣物 | 文胸、内裤、吊带背心、运动内衣 |
| 配饰 | 帽子围巾发饰挂件 | 铃铛项圈、贝雷帽 |
| 睡衣家居 | 睡觉和居家 | 睡裙、家居服、浴袍 |

升级历史：1.2.0 时旧分类自动改名（上装→上衣、连衣裙→全身装）并补 5 件新衣（深蓝色死库水、水手服JK套装、运动服套装、白色棉质睡裙、奶黄色家居服套装）；1.3.0 新增内衣分类并补 4 件（白色无钢圈文胸、白色纯棉内裤、蕾丝吊带背心、灰色运动内衣）。不想要的新衣可在页面里删，升级不会复活已删衣物。

### 常见问题

- **为什么ta从不主动来晒？** 检查白名单/晒的目标（`share_to_streams`）是否解析到了聊天流；分享欲很低（如 0.1）时十天里也就来一两天，属正常
- **想让ta天天来晒、次次带图？** 把 `share_desire` 调到 1.0
- **换装时间想改？** 改 `daily_outfit_time`（24 小时制 HH:MM），保存即生效，不用重启
- **衣服数据在哪？** MaiBot 数据目录下 `data/plugins/local.wardrobe/wardrobe_state.json`，普通文本文件可直接看

---

## 二、给 AI 看的说明（维护者文档）

> 写作时环境：MaiBot Host 1.x、maibot-plugin-sdk 2.x、Python 3.13（bot 人设"可可喵"）。

### 文件结构

```
maibot-wardrobe/
├── _manifest.json   # 清单（capabilities: chat.get_stream_by_user_id / chat.open_session /
│                   #   maisaka.context.append / maisaka.proactive.trigger）
├── webui.json       # WebUI 扩展页声明（页面 + queries/actions → @API 映射）
├── webui/index.html # 衣柜页面（自包含 HTML，maibot.query/action 桥）
├── plugin.py        # 全部逻辑+预置衣柜数据+4 个 @API（api_page_*，单文件）
├── config.toml      # 带中文注释的配置模板（items 表由插件/页面维护）
├── pyproject.toml
├── test_import.py
├── LICENSE
└── README.md
```

⚠️ **必须是单文件插件**。曾尝试把预置衣柜拆成 `preset_wardrobe.py` 同目录导入，Runner 报 `No module named 'preset_wardrobe'`——插件目录不在 sys.path，兄弟模块导入不可用。`PRESET_ITEMS` 因此内联在 plugin.py 顶部。

### 架构与组件

单类 `WardrobePlugin(MaiBotPlugin)`，无 HookHandler（与备忘录插件不同：这里不需要监听消息，聊天交互全靠 AI 主动调工具）。

**1. 每日调度**（`_schedule_loop`，60 秒一拍）：当前时间过 `daily_outfit_time`（配置，格式非法回退 08:00）且今天未跑过（`last_morning_run` 持久化，重启不重跑）→ `_run_morning_task`。迟到超过 90 分钟（`_CATCHUP_WINDOW_MINUTES`）→ `force_silent=True`，只静默换装不来晒。

**2. 每日换装两条路径**（由分享欲掷骰决定）：
- **晒路径**（`random() < share_desire` 且未 force_silent）：向每个分享目标流（≤3 个）`maisaka.trigger_proactive`，intent 是给 AI 的分步任务书：① 用高德 MCP 工具查 `weather_city` 天气（未配置则按季节）→ ② `wardrobe_list`（user_id 留空）→ ③ `wardrobe_pick` 定穿搭 → ④ 用平时语气自然分享；配图与否由插件掷的第二颗骰子决定并写进 intent（"调用绘图工具画穿搭效果图"/"只用文字"）。绘图走 AI 已有的绘图工具，本插件不直接碰绘图。
- **静默路径**（不晒/触发全失败）：`_silent_pick_outfit` 纯插件随机搭配——40% 标志套装；否则按当月季节选 连衣裙或上装+下装 +概率外套（冬 0.7→夏 0.05）+鞋+袜+55% 配饰（其中 60% 是铃铛 w006），重试至多 6 次避免与昨天完全同套。然后 `maisaka.append_context` 写**静默事实**（`[{"type":"text","content":...}]`，source_kind=`plugin:local.wardrobe`），让 keke 在该聊天流"知道"今天穿了什么但不主动提。

**3. 五个 LLM 工具**（user_id 均为可选：**留空=keke 本人操作放行**，填了则查白名单/黑名单——这是"白名单制"与"keke 自主性"并存的关键设计）：
- `wardrobe_list(user_id?, category?, season?)` — 分类分组清单，附今天+昨天穿搭（提示 AI 别重复昨天的组合）
- `wardrobe_today(user_id?)` — 今日穿搭/未决定提示 + 当前 share_desire（供 AI 感知自己"今天想不想聊穿搭"）
- `wardrobe_pick(item_ids*, description*, reason*, user_id?)` — item_ids 为逗号分隔编号（STRING 而非 ARRAY，更稳）；校验编号存在、必含上装/下装/连衣裙；反季节仅提醒不拦截
- `wardrobe_shop(name*, category*, seasons*, color?, tags?, from_user*, user_id?)` — 添新衣；新编号从 w1046 起；source 区分"主人送的/自己买的"
- `wardrobe_discard(item_id*, user_id?)` — signature 单品拒绝丢弃（人设底线）

### 分享目标解析（`_resolve_share_streams`）

`share_to_streams`（格式 `qq:private:QQ号` / `qq:group:群号`）优先；为空则回退为白名单每个用户的私聊流。私聊解析顺序：`get_stream_by_user_id` → `open_session(private)`；群聊 `open_session(group)`。全部失败则只记日志、静默换装照常。⚠️ 白名单为空时**没有任何分享目标**，静默事实也无处可写——所以白名单空 = 功能基本不生效，这是设计使然不是 bug。

### 数据存储（1.1.0 起双通道）

**衣服清单 → 插件配置** `config.toml` 的 `[items.wXXX]` 表（WardrobeItemConfig：name/category/seasons/color/tags/signature/source/acquired_at，dict 键=编号）。这是**单一事实来源**，两个写入通道：
- **WebUI 编辑**：配置页 items 表格增删改 → Runner 注入新配置 + 调 `on_config_update`（插件只打日志，`self.config.items` 已是最新）
- **插件写入**（播种/迁移/wardrobe_shop/wardrobe_discard）：改内存 `self.config.items` 后调 `_save_items_to_disk()`——tomlkit 读改写 config.toml，**保留注释与其它字段**（社区提醒类插件通用的持久化模式）

首件加载：config.items 为空时，优先从旧版数据文件迁移 `legacy_items`，否则播种 `PRESET_ITEMS`（source="初始衣柜"）。pyproject 依赖 tomlkit>=0.12.0。

**今日穿搭与历史 → 数据文件** `<data_dir>/wardrobe_state.json`（即 MaiBot 数据目录下 `data/plugins/local.wardrobe/`）：

```json
{
  "today":   { "date":"YYYY-MM-DD","item_ids":[],"description":"","reason":"","decided_by":"plugin|ai","decided_at":ts } | null,
  "history": [ 同 today 结构，倒序 ],
  "last_morning_run": "YYYY-MM-DD"
}
```

`today` 换日时旧值进 `history`（截到 `max_history`，默认 30）。写盘为 tmp+replace 原子写。history 里的 item_ids 允许指向已被删除的衣服（展示用 description 字符串，不反查）。

### 部署 / 更新 / 验证

```bash
# 同步到运行环境的 plugins/ 目录后重启 MaiBot（或在管理页面重载插件）
# 验证日志：应见「衣柜插件已加载：衣服 N 件…」且 失败=0

# 改完先做导入自测再重启，省一轮重启：
python -m py_compile plugin.py
python -c "import sys; sys.path.insert(0,'.'); import plugin; \
  p=plugin.create_plugin(); print([n for n in dir(p) if n.startswith('wardrobe_')])"
```

### 踩坑记录（2026-10-25 首次部署 / 1.1.0 升级）

1. **兄弟模块导入不可用**（见上文文件结构警告），插件必须单文件。
2. manifest 的 `author.url`/`urls.repository` 必填（占位网址即可）；配置模型必须含 `[plugin]` 节+`config_version`——与备忘录插件相同，属 MaiBot 通用坑。
3. `maisaka.append_context` 必须传 stream_id：事实是"写给某个聊天流看的"，不是全局记忆；本插件只写给分享目标流，其他流靠工具查询。
4. `trigger_proactive` 可能返回 `{"success": false}`（被 Maisaka 拒绝），需当失败处理走静默兜底，不能只捕异常。
5. 天气数据本插件不自己取——需要 bot 已配置天气/地图类 MCP 工具（如高德），让 AI 在主动任务里自己查，插件只负责把城市名写进 intent。
6. **WebUI 编辑配置会保留注释**：Runner 的 `_save_plugin_config` 用 tomlkit 把新值合并进现有文档（源码注释"保留插件配置注释失败，将回退为整文件重写"）；但**新增配置字段**（文档里没有的键）会触发整文件重写、丢注释——所以升级插件加字段时，同步把带注释的 config.toml 一起部署。
7. **HomeCard 是静态的**：内容在装饰器声明时固定，无运行时更新能力接口 → 放弃用首页卡片做衣柜展示。
8. **webui.json 的坑（1.2.0 实测）**：① `type: "array"` 参数必须声明 `items`（每项的子 schema），否则 pydantic 报"array 参数必须声明 items"；② 声明了数组等结构化参数后，`required_capabilities` 必须加 `"structured_arguments"`，否则报"结构化参数需要声明 required_capabilities"。数组校验失败会导致**整个插件注册失败**（不止页面不生效）。参考 local.keke-kitchen（只有标量参数，无需 structured_arguments）。
9. WebUI 页面 JS 桥：`await maibot.ready` 后用 `maibot.query("<query名>")` / `maibot.action("<action名>", {...})`，名字对应 webui.json 的 queries/actions 映射，最终落到插件 `@API` 方法；页面放在 `/extensions/<插件id>/<页面id>`，`placement: "sidebar"` 出现在侧边栏。

### 可扩展方向（未实现）

- 换季整理：季节切换时 AI 自己"收箱换箱"聊一段
- 穿搭打分/投票：晒完让主人打分，攒"最喜欢穿搭榜"
- 和备忘录插件联动：买衣服待办（"记得给猫猫买冬装"）
- 连续穿搭 streak 统计、出图 prompt 模板库（不同季节风格）
