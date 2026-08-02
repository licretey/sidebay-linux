"""zh/en 双语查表。词表对齐原 Swift 版 SideBarApp.swift t() 函数。"""

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Settings": {"en": "Settings", "zh": "侧边栏模块管理"},
    "CPU": {"en": "CPU", "zh": "CPU"},
    "GPU": {"en": "GPU", "zh": "GPU"},
    "Memory": {"en": "RAM", "zh": "内存"},
    "Disk": {"en": "Disk", "zh": "磁盘"},
    "Fan": {"en": "Fan", "zh": "风扇"},
    "Network": {"en": "Network", "zh": "网络"},
    "Stock": {"en": "Stock", "zh": "股票"},
    "Countdown": {"en": "CD Timer", "zh": "倒计时"},
    "Stopwatch": {"en": "Timer", "zh": "秒表"},
    "Screen Record": {"en": "RecScreen", "zh": "录屏"},
    "Calculator": {"en": "Calculator", "zh": "计算器"},
    "Keyboard": {"en": "Keyboard", "zh": "键盘监视"},
    "Server": {"en": "Server", "zh": "服务器"},
    "Not Set": {"en": "Not Set", "zh": "未设置"},
    "Add Module": {"en": "Add Module", "zh": "新增模块"},
    "Add": {"en": "Add", "zh": "添加"},
    "Position": {"en": "Position", "zh": "位置"},
    "Left": {"en": "Left", "zh": "左边"},
    "Right": {"en": "Right", "zh": "右边"},
    "Launch at Login": {"en": "Launch at Login", "zh": "随系统启动"},
    "Hint": {
        "en": "Hint: Drag to reorder, click trash to delete.",
        "zh": "提示：按住行可以拖拽排序，点击右侧垃圾桶图标即可删除。",
    },
    "Language": {"en": "Language", "zh": "语言"},
    "Min": {"en": "Min", "zh": "分"},
    "KEYS": {"en": "KEYS", "zh": "按键"},
    "Loading...": {"en": "Loading...", "zh": "加载中..."},
    "Invalid Code": {"en": "Invalid Code", "zh": "无效代码"},
    "Waiting...": {"en": "Waiting...", "zh": "等待输入..."},
    "No Accessibility": {"en": "No Accessibility", "zh": "无辅助功能权限"},
    "SettingsTitle": {"en": "Settings", "zh": "后台设置"},
    "Width": {"en": "Width", "zh": "宽度"},
    "Select Fan": {"en": "Select Fan", "zh": "选择风扇"},
}


def t(key: str, lang: str) -> str:
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry["en"])
