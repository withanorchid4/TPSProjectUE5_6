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

## 3. 查找 NePy 可用 API 的方法

NePy 没有独立的 API 文档，但有两个关键文件可以作为完整的 API 参考：

### 3.1 Python 类型存根（最全的 API 参考）

**路径**：`Plugins/NePythonBinding/Tools/pystubs/ue/__init__.pyi`

- 约 19 万行，包含所有 `ue.*` 模块暴露的 Python 类型签名
- 搜索方式：在这个文件中搜索类名或方法名，如 `CreateDynamicMaterialInstance`、`KismetMaterialLibrary`
- **这是发现可用 API 最可靠的方式**，比官方文档更全面

### 3.2 C++ 绑定实现（验证 API 行为）

**路径**：`Plugins/NePythonBinding/Source/NePythonBinding/Public/NePy/Auto/engine/`

- 每个 UE 类对应一个 `NePyObject_*.cpp` 文件
- 可确认 Python API 底层调用的是哪个 C++ 函数，以及参数映射关系
- 例如 `NePyObject_KismetMaterialLibrary.cpp` 确认 `CreateDynamicMaterialInstance` 调用的是 `UKismetMaterialLibrary::CreateDynamicMaterialInstance`

### 3.3 查找流程示例

以"如何创建可用的 MaterialInstanceDynamic"为例：

1. **先在 `.pyi` 中搜索** → 找到 `KismetMaterialLibrary.CreateDynamicMaterialInstance` 的签名
2. **去 C++ 绑定验证** → 确认它调用的是 `UKismetMaterialLibrary::CreateDynamicMaterialInstance`（UE 的标准工厂方法）
3. **使用** → `ue.KismetMaterialLibrary.CreateDynamicMaterialInstance(self, parent_mat, "Name")`

### 3.4 重要经验：NewObject vs 工厂方法

- `ue.NewObject(ue.MaterialInstanceDynamic)` 只创建 UObject 壳子，**不会初始化渲染资源**，用作 OverlayMaterial 会显示灰白
- 正确做法是用 UE 暴露的工厂方法（如 `KismetMaterialLibrary.CreateDynamicMaterialInstance`），它们会完成完整的初始化
- **原则**：如果 UE C++ 中某个类型有 `Create()` / `CreateInstance()` 等静态工厂方法，优先使用，不要用 `NewObject`
