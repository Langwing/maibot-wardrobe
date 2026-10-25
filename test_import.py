import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plugin  # noqa: E402

p = plugin.create_plugin()
tools = [n for n in dir(p) if n.startswith("wardrobe_") and not n.startswith("wardrobe_page")]
apis = [n for n in dir(p) if n.startswith("api_")]
print("PLUGIN_OK tools:", tools, "apis:", apis)
assert len(tools) == 5, f"expect 5 tools, got {tools}"
assert sorted(apis) == ["api_page_add_item", "api_page_remove_item", "api_page_set_item", "api_page_state"], apis

# 分类体系 v3 校验
assert plugin.CATEGORIES == ["上衣", "下装", "全身装", "套装", "外套", "鞋子", "袜子", "内衣", "配饰", "睡衣家居"]
assert plugin._CATEGORY_SCHEME == "v3"
ids = [i["id"] for i in plugin.PRESET_ITEMS]
assert len(ids) == len(set(ids)), "preset ids duplicated"
assert set(plugin._LEGACY_CATEGORY_MAP.values()) <= set(plugin.CATEGORIES)
cats = {i["category"] for i in plugin.PRESET_ITEMS}
assert cats <= set(plugin.CATEGORIES), cats
assert {"w046", "w047", "w048", "w049", "w050"} <= set(ids), "v2 new items missing"
assert {"w051", "w052", "w053", "w054"} <= set(ids), "v3 new items missing"
print("PRESET_OK items:", len(plugin.PRESET_ITEMS), "categories:", sorted(cats))
