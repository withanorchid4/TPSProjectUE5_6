# 开发参考文档

## 1. NePy 官方文档

**路径**：`C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\【客户端专精】Client 客户端UE资源、脚本、插件、样例等\NewClient\NEPYDoc`

重点章节：
- `subclassing/` — Python 定义 UE 类（uclass、ufunction、uproperty）
- `game-developing/ticker-and-timer.md` — Tick 与 Timer 机制
- `game-developing/character-and-controller.md` — 角色与控制器
- `game-developing/spawn-actor.md` — Actor 生成
- `advance-topics/` — 高级话题（对象生命周期、性能分析等）

## 2. NePy Subclassing 中无法使用 ReceiveTick

**问题**：`@ue.ufunction(override=True)` 覆写 `ReceiveTick` 不会被引擎调用。

**原因**：UE 优化——蓝图中没有 Tick 节点时，C++ 层不会注册 Ticker，Python 的 ReceiveTick 永远不会触发。即使手动 `SetActorTickEnabled(True)` 也无效（底层 `bCanEverTick` 为 False）。

**解决方案**：使用 `ue.AddTicker` 替代 ReceiveTick。

项目已封装 `system/tickable.py` 的 `TickableMixin`：

```python
from system.tickable import TickableMixin

@ue.uclass()
class MyActor(ue.Actor, TickableMixin):
    def __init_pyobj__(self):
        self._ticker_handle = None

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        self._start_ticker()

    def on_tick(self, delta_time):
        # 替代 ReceiveTick，在此写每帧逻辑
        pass
```

**注意**：Actor 销毁前必须调用 `_stop_ticker()`，否则 ticker 回调会在已销毁对象上执行并抛 RuntimeError。
