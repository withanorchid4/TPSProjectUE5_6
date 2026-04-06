# NePy Python 类注册问题排查记录

**日期**: 2026-04-05  
**问题**: TPSCharacter 类无法在 UE 编辑器中作为 Blueprint 基类被找到

---

## 问题描述

在 UE 5.6 + NePy 插件环境下，创建了 `TPSCharacter` Python 类并使用 `@ue.uclass()` 装饰器，但在编辑器中创建 Blueprint 时无法搜索到该类。

---

## 问题根因分析

### 问题 1: 文件名与目录冲突

**现象**: 
- `import character` 后，`TPSCharacter` 类没有被注册
- `on_init` 中导入模块没有报错，但类不出现在 Blueprint 列表中

**根因**:
```
Content/Scripts/
├── character.py          # 包含 TPSCharacter 类
└── character/            # Python 包目录
    ├── __init__.py
    ├── base_character.py
    └── ...
```

Python 导入规则：当文件和目录同名时，`import character` 会导入**目录（包）**而不是**文件**。

**解决方案**:
将 `character.py` 重命名为 `tps_character.py`，并在 `nepyinit.py` 中改为：
```python
import tps_character  # 而不是 import character
```

---

### 问题 2: `__init__` 方法不允许

**现象**:
```
LogNePython: Warning: User defined '__init__' in subclassing type 'BaseCharacter', 
which is not allowed and will take no effect. 
Use '__init_default__' instead if you want to define default values in unreal type. 
Use '__init_pyobj__' instead if you want to define python variables.
```

**根因**:
NePy 的 `@ue.uclass()` 装饰的类不能使用标准的 `__init__` 方法。

**解决方案**:
```python
# 错误写法
class BaseCharacter(ue.Character):
    def __init__(self):
        super().__init__()
        self.movement = None

# 正确写法
@ue.uclass()
class BaseCharacter(ue.Character):
    def __init_pyobj__(self):
        """初始化 Python 变量"""
        self.movement = None
```

---

### 问题 3: InputSettings API 调用方式错误

**现象**:
```
AttributeError: 'module' object has no attribute 'GetInputSettings'
```

**根因**:
`GetInputSettings` 是 `InputSettings` 类的静态方法，不是 `ue` 模块的直接属性。

**解决方案**:
```python
# 错误写法
input_settings = ue.GetInputSettings()

# 正确写法
input_settings = ue.InputSettings.GetInputSettings()
```

---

### 问题 4: 基类缺少 `@ue.uclass()` 装饰器

**现象**:
- 子类 `TPSCharacter` 有装饰器，但基类 `BaseCharacter` 没有
- 类仍然无法注册

**根因**:
NePy 要求所有作为 Blueprint 基类的 Python 类（包括继承链中的基类）都必须有 `@ue.uclass()` 装饰器。

**解决方案**:
```python
# 错误写法
class BaseCharacter(ue.Character):  # 缺少装饰器
    pass

# 正确写法
@ue.uclass()
class BaseCharacter(ue.Character):
    pass
```

---

## 最佳实践总结

### 1. 文件命名规范

- 避免模块文件与目录同名
- 建议命名方式：
  - `tps_character.py` - 具体角色类
  - `character/` - 角色相关组件包目录

### 2. NePy 类定义规范

```python
import ue

@ue.uclass()
class MyCharacter(ue.Character):
    """使用 __init_pyobj__ 初始化 Python 变量"""
    
    def __init_pyobj__(self):
        self.my_variable = None
    
    def ReceiveBeginPlay(self):
        """覆写 UE 事件"""
        super().ReceiveBeginPlay()
        ue.LogWarning(f"{self} started!")
```

### 3. 类注册时机

Python 类必须在 `on_init()` 回调中导入，才能在编辑器启动时注册：

```python
# nepyinit.py
def on_init():
    ue.LogWarning('NePy initialized!')
    
    # 注册 Python 类（必须在 on_init 中导入）
    import tps_character
    
    # 其他初始化...
```

### 4. API 调用检查

使用 NePy API 前，检查 `ue/__init__.pyi` 类型存根文件确认正确的调用方式：
- 实例方法：`obj.Method()`
- 静态方法：`ue.ClassName.StaticMethod()`

---

## 调试技巧

### 1. 添加日志确认模块加载

```python
def on_init():
    ue.LogWarning('NePy initialized!')
    
    try:
        import tps_character
        ue.LogWarning('tps_character module loaded successfully!')
    except Exception as e:
        ue.LogError(f'Failed to load tps_character: {e}')
```

### 2. 检查 Output Log

在 UE 编辑器中：
- `Tools` → `Output Log`
- 过滤 `LogNePython` 查看所有 Python 相关日志

### 3. 常见错误日志

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `ModuleNotFoundError: No module named 'xxx'` | 模块导入失败 | 检查文件路径和 sys.path |
| `User defined '__init__' ... not allowed` | uclass 不能用 `__init__` | 改用 `__init_pyobj__` |
| 类不在 Blueprint 列表 | 类未注册 | 在 `on_init` 中导入，添加 `@ue.uclass()` |

---

## 参考文档

- NePy 官方文档：`nepy_mini/NEPYDoc/game-developing/character-and-controller.md`
- UE 类型存根：`Plugins/NePythonBinding/Tools/pystubs/ue/__init__.pyi`
