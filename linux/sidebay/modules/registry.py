"""模块注册表：类型 -> 工厂。"""

from sidebay.modules.base import Module
from sidebay.modules.calculator import CalculatorModule
from sidebay.modules.fan import FanModule
from sidebay.modules.network import NetworkModule
from sidebay.modules.stock import StockModule
from sidebay.modules.usage import UsageModule

MODULE_TYPES = ["CPU", "GPU", "Memory", "Disk", "Fan", "Network",
                "Stock", "Countdown", "Stopwatch", "Calculator", "Keyboard"]


def create_module(type_: str, store, module_id: str, monitor) -> Module:
    if type_ in ("CPU", "GPU", "Memory", "Disk"):
        return UsageModule(store, module_id, monitor, kind=type_)
    if type_ == "Fan":
        return FanModule(store, module_id, monitor)
    if type_ == "Network":
        return NetworkModule(store, module_id, monitor)
    if type_ == "Calculator":
        return CalculatorModule(store, module_id)
    if type_ == "Stock":
        return StockModule(store, module_id)
    from sidebay.modules.countdown import CountdownModule
    from sidebay.modules.stopwatch import StopwatchModule

    if type_ == "Countdown":
        return CountdownModule(store, module_id)
    if type_ == "Stopwatch":
        return StopwatchModule(store, module_id)
    raise ValueError(f"module type not wired yet: {type_}")
