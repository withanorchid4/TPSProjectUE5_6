# 角色控制模块设计文档

> 日期：2026年4月5日
> 状态：已批准

---

## 1. 概述

实现 TPS 第三人称射击游戏的角色控制模块，包括：
- WASD 8向移动
- 空格跳跃
- TPS 越肩摄像机跟随
- 鼠标左键射击

---

## 2. 技术选型

| 项目 | 选择 | 说明 |
|------|------|------|
| 角色模型 | UE Third Person Mannequin | 使用引擎自带资源 |
| 摄像机模式 | 经典越肩视角 | 固定在角色右后方 |
| 输入处理 | Python 实现，结构化设计 | 可扩展支持 UE Input 系统 |
| 射击动画 | 暂不实现 | 先完成核心逻辑 |

---

## 3. 架构设计

### 3.1 目录结构

```
Content/Scripts/
├── character/
│   ├── __init__.py          # 模块导出
│   ├── base_character.py    # 基础角色类
│   ├── movement.py          # 移动组件
│   ├── camera.py            # 摄像机组件
│   ├── shooting.py          # 射击组件
│   └── input_handler.py     # 输入处理器基类
├── character.py             # 主角色类定义
└── input_handlers/
    ├── __init__.py
    └── keyboard_handler.py  # 键盘输入处理
```

### 3.2 类职责

| 类/模块 | 职责 |
|---------|------|
| `TPSCharacter` | 主角色类，组合各组件 |
| `MovementComponent` | WASD 移动、跳跃 |
| `CameraComponent` | TPS 越肩摄像机 |
| `ShootingComponent` | 射击、子弹生成 |
| `InputHandler` | 输入处理抽象基类 |
| `KeyboardInputHandler` | 键盘/鼠标输入实现 |

### 3.3 数据流

```
键盘/鼠标输入
    ↓
KeyboardInputHandler
    ↓
TPSCharacter
    ├── MovementComponent → AddMovementInput()
    ├── CameraComponent → 更新摄像机位置
    └── ShootingComponent → SpawnActor(子弹)
```

---

## 4. 输入映射

| 按键 | 动作 | 方法 |
|------|------|------|
| W/S | 前后移动 | `MoveForward(value)` |
| A/D | 左右移动 | `MoveRight(value)` |
| Space | 跳跃 | `Jump()` |
| Mouse Left | 射击 | `Shoot()` |
| Mouse Move | 视角旋转 | `Turn(value)` |

---

## 5. 组件设计

### 5.1 MovementComponent

```python
class MovementComponent:
    - move_speed: float        # 移动速度
    - jump_velocity: float     # 跳跃初速度
    
    + MoveForward(value)       # 前后移动
    + MoveRight(value)         # 左右移动
    + Jump()                   # 跳跃
    + IsGrounded() -> bool     # 是否在地面
```

### 5.2 CameraComponent

```python
class CameraComponent:
    - camera_offset: Vector    # 摄像机偏移
    - rotation_speed: float    # 旋转速度
    
    + Update(delta_time)       # 更新位置
    + SetOffset(offset)        # 设置偏移
```

### 5.3 ShootingComponent

```python
class ShootingComponent:
    - bullet_class: UClass     # 子弹类
    - fire_rate: float         # 射击间隔
    - last_fire_time: float    # 上次射击时间
    
    + Shoot()                  # 射击
    + CanShoot() -> bool       # 是否可射击
```

---

## 6. 扩展性设计

### 6.1 输入系统扩展

当前使用 Python 直接处理输入，后续可扩展支持 UE Input 系统：

```python
# input_handler.py (基类)
class InputHandler(ABC):
    @abstractmethod
    def bind(self, character): pass
    
    @abstractmethod
    def unbind(self): pass

# keyboard_handler.py (当前实现)
class KeyboardInputHandler(InputHandler):
    ...

# ue_input_handler.py (未来扩展)
class UEInputHandler(InputHandler):
    # 使用 UE 项目设置中的 Input 系统
    ...
```

### 6.2 组件扩展

新增功能只需添加新组件：

```python
# 未来扩展
from character.skill import SkillComponent
from character.buff import BuffComponent
```

---

## 7. 待实现功能

- [ ] 基础移动 (WASD)
- [ ] 跳跃
- [ ] TPS 摄像机
- [ ] 射击核心逻辑
- [ ] 子弹类

---

## 8. 后续优化

- 添加射击动画
- 添加角色状态机（站立、奔跑、跳跃等）
- 添加 footsteps 音效
- 优化摄像机碰撞检测

---

> 设计批准时间：2026年4月5日
> 批准人：用户确认
