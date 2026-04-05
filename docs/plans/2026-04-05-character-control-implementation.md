# 角色控制模块实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 TPS 角色的移动、跳跃、摄像机跟随和射击功能

**Architecture:** 模块化组件设计，TPSCharacter 组合 MovementComponent、CameraComponent、ShootingComponent，输入通过 InputHandler 抽象层处理

**Tech Stack:** Python 3.12 + NePy (UE5.6 Python 绑定)

---

## Task 1: 创建目录结构

**Files:**
- Create: `Content/Scripts/character/__init__.py`
- Create: `Content/Scripts/character/base_character.py`
- Create: `Content/Scripts/character/movement.py`
- Create: `Content/Scripts/character/camera.py`
- Create: `Content/Scripts/character/shooting.py`
- Create: `Content/Scripts/character/input_handler.py`
- Create: `Content/Scripts/input_handlers/__init__.py`
- Create: `Content/Scripts/input_handlers/keyboard_handler.py`

**Step 1: 创建 character 模块目录**

在 `Content/Scripts/` 下创建 `character/` 目录，添加 `__init__.py`:

```python
# -*- encoding: utf-8 -*-
from .base_character import BaseCharacter
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent
from .input_handler import InputHandler

__all__ = [
    'BaseCharacter',
    'MovementComponent',
    'CameraComponent',
    'ShootingComponent',
    'InputHandler',
]
```

**Step 2: 创建 input_handlers 模块目录**

在 `Content/Scripts/` 下创建 `input_handlers/` 目录，添加 `__init__.py`:

```python
# -*- encoding: utf-8 -*-
from .keyboard_handler import KeyboardInputHandler

__all__ = ['KeyboardInputHandler']
```

**Step 3: 提交**

```bash
git add Content/Scripts/character/ Content/Scripts/input_handlers/
git commit -m "feat: create character module directory structure"
```

---

## Task 2: 实现移动组件 (MovementComponent)

**Files:**
- Create: `Content/Scripts/character/movement.py`

**Step 1: 创建 MovementComponent 类**

```python
# -*- encoding: utf-8 -*-
import ue


class MovementComponent:
    """处理角色的移动和跳跃逻辑"""
    
    DEFAULT_MOVE_SPEED = 600.0
    DEFAULT_JUMP_VELOCITY = 420.0
    
    def __init__(self, owner):
        self.owner = owner  # type: ue.Character
        self.move_speed = self.DEFAULT_MOVE_SPEED
        self.jump_velocity = self.DEFAULT_JUMP_VELOCITY
    
    def move_forward(self, value: float):
        """前后移动"""
        if value != 0.0:
            forward = self.owner.GetActorForwardVector()
            self.owner.AddMovementInput(forward, value * self.move_speed)
    
    def move_right(self, value: float):
        """左右移动"""
        if value != 0.0:
            right = self.owner.GetActorRightVector()
            self.owner.AddMovementInput(right, value * self.move_speed)
    
    def jump(self):
        """跳跃"""
        if self.is_grounded():
            self.owner.Jump()
    
    def is_grounded(self) -> bool:
        """检测是否在地面"""
        return self.owner.GetMovementComponent().IsFalling() == False
```

**Step 2: 提交**

```bash
git add Content/Scripts/character/movement.py
git commit -m "feat: implement MovementComponent for character movement"
```

---

## Task 3: 实现摄像机组件 (CameraComponent)

**Files:**
- Create: `Content/Scripts/character/camera.py`

**Step 1: 创建 CameraComponent 类**

```python
# -*- encoding: utf-8 -*-
import ue


class CameraComponent:
    """TPS 越肩摄像机控制"""
    
    # 默认摄像机偏移（右后方）
    DEFAULT_CAMERA_OFFSET = ue.Vector(300.0, 50.0, 100.0)
    
    def __init__(self, owner):
        self.owner = owner  # type: ue.Character
        self.camera_component = None
        self.camera_offset = self.DEFAULT_CAMERA_OFFSET
        self.rotation_speed = 2.0
    
    def setup(self):
        """设置摄像机组件"""
        # 查找或创建 SpringArm
        spring_arm = self.owner.FindComponentByClass(ue.SpringArmComponent)
        if not spring_arm:
            spring_arm = ue.NewObject(ue.SpringArmComponent, self.owner, "CameraSpringArm")
            spring_arm.SetupAttachment(self.owner.GetCapsuleComponent())
            spring_arm.bUsePawnControlRotation = True
        
        # 查找或创建 Camera
        camera = self.owner.FindComponentByClass(ue.CameraComponent)
        if not camera:
            camera = ue.NewObject(ue.CameraComponent, spring_arm, "TPSCamera")
        
        spring_arm.TargetArmLength = self.camera_offset.X
        spring_arm.SocketOffset = ue.Vector(0.0, self.camera_offset.Y, self.camera_offset.Z)
        
        self.camera_component = camera
        self.spring_arm = spring_arm
    
    def update_rotation(self, yaw_delta: float, pitch_delta: float):
        """更新摄像机旋转"""
        self.owner.AddControllerYawInput(yaw_delta * self.rotation_speed)
        self.owner.AddControllerPitchInput(pitch_delta * self.rotation_speed)
```

**Step 2: 提交**

```bash
git add Content/Scripts/character/camera.py
git commit -m "feat: implement CameraComponent for TPS camera"
```

---

## Task 4: 实现射击组件 (ShootingComponent)

**Files:**
- Create: `Content/Scripts/character/shooting.py`

**Step 1: 创建 ShootingComponent 类**

```python
# -*- encoding: utf-8 -*-
import ue


class ShootingComponent:
    """处理射击逻辑"""
    
    DEFAULT_FIRE_RATE = 0.1  # 射击间隔（秒）
    
    def __init__(self, owner):
        self.owner = owner  # type: ue.Character
        self.bullet_class = None  # 子弹类，后续设置
        self.fire_rate = self.DEFAULT_FIRE_RATE
        self.last_fire_time = 0.0
    
    def set_bullet_class(self, bullet_class):
        """设置子弹类"""
        self.bullet_class = bullet_class
    
    def can_shoot(self) -> bool:
        """检查是否可以射击"""
        if not self.bullet_class:
            ue.LogWarning("Bullet class not set!")
            return False
        
        current_time = ue.GetGameTimeInSeconds()
        return (current_time - self.last_fire_time) >= self.fire_rate
    
    def shoot(self):
        """执行射击"""
        if not self.can_shoot():
            return
        
        # 获取射击位置和方向
        spawn_location = self.owner.GetActorLocation() + ue.Vector(100.0, 0.0, 50.0)
        spawn_rotation = self.owner.GetControlRotation()
        
        # 生成子弹
        world = self.owner.GetWorld()
        bullet = world.SpawnActor(
            self.bullet_class,
            spawn_location,
            spawn_rotation
        )
        
        if bullet:
            self.last_fire_time = ue.GetGameTimeInSeconds()
            ue.Log(f"Shot fired at {spawn_location}")
```

**Step 2: 提交**

```bash
git add Content/Scripts/character/shooting.py
git commit -m "feat: implement ShootingComponent for firing bullets"
```

---

## Task 5: 实现输入处理器基类

**Files:**
- Create: `Content/Scripts/character/input_handler.py`

**Step 1: 创建 InputHandler 抽象基类**

```python
# -*- encoding: utf-8 -*-
from abc import ABC, abstractmethod
import ue


class InputHandler(ABC):
    """输入处理器抽象基类"""
    
    def __init__(self, owner):
        self.owner = owner  # type: ue.Character
        self.movement = None
        self.camera = None
        self.shooting = None
    
    def set_components(self, movement, camera, shooting):
        """设置组件引用"""
        self.movement = movement
        self.camera = camera
        self.shooting = shooting
    
    @abstractmethod
    def bind(self):
        """绑定输入"""
        pass
    
    @abstractmethod
    def unbind(self):
        """解绑输入"""
        pass
    
    @abstractmethod
    def tick(self, delta_time: float):
        """每帧更新"""
        pass
```

**Step 2: 提交**

```bash
git add Content/Scripts/character/input_handler.py
git commit -m "feat: implement InputHandler abstract base class"
```

---

## Task 6: 实现键盘输入处理器

**Files:**
- Create: `Content/Scripts/input_handlers/keyboard_handler.py`

**Step 1: 创建 KeyboardInputHandler 类**

```python
# -*- encoding: utf-8 -*-
import ue
from character.input_handler import InputHandler


class KeyboardInputHandler(InputHandler):
    """键盘/鼠标输入处理器"""
    
    def __init__(self, owner):
        super().__init__(owner)
        
        # 按键状态
        self.keys_pressed = {
            'W': False,
            'S': False,
            'A': False,
            'D': False,
            'Space': False,
        }
        
        # 鼠标状态
        self.mouse_left_pressed = False
        self.mouse_delta_x = 0.0
        self.mouse_delta_y = 0.0
    
    def bind(self):
        """绑定输入事件"""
        controller = self.owner.GetController()
        if not controller:
            return
        
        self.owner.EnableInput(controller)
        
        # 绑定按键
        input_comp = self.owner.InputComponent
        
        # 移动 - 使用 UE Input 系统（如果已配置）
        # 或者我们在 tick 中手动检测
        
        # 跳跃
        input_comp.BindAction('Jump', ue.EInputEvent.IE_Pressed, self._on_jump_pressed)
        input_comp.BindAction('Jump', ue.EInputEvent.IE_Released, self._on_jump_released)
        
        # 射击
        input_comp.BindAction('Fire', ue.EInputEvent.IE_Pressed, self._on_fire_pressed)
        input_comp.BindAction('Fire', ue.EInputEvent.IE_Released, self._on_fire_released)
        
        ue.Log("Keyboard input handler bound")
    
    def unbind(self):
        """解绑输入"""
        # UE 的 InputComponent 会自动清理
        pass
    
    def tick(self, delta_time: float):
        """每帧处理输入"""
        # 处理移动
        forward_value = 0.0
        right_value = 0.0
        
        if self.keys_pressed.get('W', False):
            forward_value += 1.0
        if self.keys_pressed.get('S', False):
            forward_value -= 1.0
        if self.keys_pressed.get('D', False):
            right_value += 1.0
        if self.keys_pressed.get('A', False):
            right_value -= 1.0
        
        if self.movement:
            if forward_value != 0:
                self.movement.move_forward(forward_value)
            if right_value != 0:
                self.movement.move_right(right_value)
        
        # 处理摄像机旋转
        if self.camera and (self.mouse_delta_x != 0 or self.mouse_delta_y != 0):
            self.camera.update_rotation(self.mouse_delta_x, self.mouse_delta_y)
            self.mouse_delta_x = 0.0
            self.mouse_delta_y = 0.0
        
        # 处理射击
        if self.mouse_left_pressed and self.shooting:
            self.shooting.shoot()
    
    def _on_jump_pressed(self):
        if self.movement:
            self.movement.jump()
    
    def _on_jump_released(self):
        self.owner.StopJumping()
    
    def _on_fire_pressed(self):
        self.mouse_left_pressed = True
    
    def _on_fire_released(self):
        self.mouse_left_pressed = False
```

**Step 2: 提交**

```bash
git add Content/Scripts/input_handlers/keyboard_handler.py
git commit -m "feat: implement KeyboardInputHandler for keyboard/mouse input"
```

---

## Task 7: 实现基础角色类

**Files:**
- Create: `Content/Scripts/character/base_character.py`

**Step 1: 创建 BaseCharacter 类**

```python
# -*- encoding: utf-8 -*-
import ue
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent


class BaseCharacter(ue.Character):
    """角色基类，组合各功能组件"""
    
    def __init__(self):
        super().__init__()
        
        # 组件实例
        self.movement = None
        self.camera = None
        self.shooting = None
        self.input_handler = None
    
    def ReceiveBeginPlay(self):
        """角色开始播放时调用"""
        ue.Log(f"{self} ReceiveBeginPlay")
        
        # 初始化组件
        self._init_components()
        
        # 设置输入
        self._setup_input()
    
    def _init_components(self):
        """初始化所有组件"""
        self.movement = MovementComponent(self)
        self.camera = CameraComponent(self)
        self.shooting = ShootingComponent(self)
        
        # 设置摄像机
        self.camera.setup()
        
        ue.Log("Components initialized")
    
    def _setup_input(self):
        """设置输入处理"""
        controller = self.owner.GetController()
        if controller:
            self.owner.PossessedBy(controller)
    
    def ReceiveTick(self, delta_seconds: float):
        """每帧更新"""
        if self.input_handler:
            self.input_handler.tick(delta_seconds)
    
    def set_input_handler(self, handler):
        """设置输入处理器"""
        self.input_handler = handler
        handler.set_components(self.movement, self.camera, self.shooting)
        handler.bind()
    
    def set_bullet_class(self, bullet_class):
        """设置子弹类"""
        if self.shooting:
            self.shooting.set_bullet_class(bullet_class)
```

**Step 2: 提交**

```bash
git add Content/Scripts/character/base_character.py
git commit -m "feat: implement BaseCharacter with component composition"
```

---

## Task 8: 创建 TPS 主角色类

**Files:**
- Modify: `Content/Scripts/character.py`

**Step 1: 创建 TPSCharacter 类**

```python
# -*- encoding: utf-8 -*-
import ue
from character.base_character import BaseCharacter
from input_handlers.keyboard_handler import KeyboardInputHandler


@ue.uclass()
class TPSCharacter(BaseCharacter):
    """TPS 第三人称射击游戏角色"""
    
    def ReceiveBeginPlay(self):
        """重写 BeginPlay，添加 TPS 特有逻辑"""
        super().ReceiveBeginPlay()
        
        # 设置键盘输入处理器
        self.set_input_handler(KeyboardInputHandler(self))
        
        ue.LogWarning(f"TPSCharacter {self} initialized!")
```

**Step 2: 提交**

```bash
git add Content/Scripts/character.py
git commit -m "feat: create TPSCharacter main character class"
```

---

## Task 9: 更新 nepyinit.py

**Files:**
- Modify: `Content/Scripts/nepyinit.py`

**Step 1: 确保 character 模块正确加载**

```python
# -*- encoding: utf-8 -*-
import ue
import traceback


def on_init():
    ue.LogWarning('NePy initialized!')
    
    if ue.GIsEditor:
        try:
            import reload_monitor
            reload_monitor.start()
        except:
            traceback.print_exc()
        
        try:
            import gmcmds
            gmcmds.debug()
        except:
            traceback.print_exc()
    
    # 加载角色模块
    import character


def on_post_engine_init():
    """引擎初始化完成后调用"""
    ue.LogWarning('Post engine init - loading game modules')


def on_shutdown():
    ue.LogWarning('NePy shutdown!')


def on_debug_input(cmd_str):
    import gmcmds
    return gmcmds.handle_debug_input(cmd_str)


def on_tick(dt):
    pass
```

**Step 2: 提交**

```bash
git add Content/Scripts/nepyinit.py
git commit -m "refactor: update nepyinit for TPS character module"
```

---

## Task 10: 编辑器配置 - 输入映射

**操作步骤:**

1. 打开 UE 编辑器
2. 菜单: **编辑 → 项目设置 → 输入**
3. 添加 **Axis Mappings**:
   - `MoveForward`: W = 1.0, S = -1.0
   - `MoveRight`: D = 1.0, A = -1.0
4. 添加 **Action Mappings**:
   - `Jump`: Space Bar
   - `Fire`: Left Mouse Button

**验证:** 在 Python 控制台测试:

```python
import ue
# 检查输入是否正确绑定
```

---

## Task 11: 测试角色移动

**测试步骤:**

1. 在编辑器中创建新关卡
2. 放置一个 Third Person Character 或使用 PlayerStart
3. 将其替换为 TPSCharacter
4. 运行游戏 (PIE)
5. 测试 WASD 移动、空格跳跃

**预期结果:**
- W/S 前后移动正常
- A/D 左右移动正常
- 空格跳跃正常

---

## Task 12: 推送到 GitHub

```bash
git add .
git commit -m "feat: complete character control module implementation"
git push origin master
```

---

## 完成检查点

| 任务 | 状态 |
|------|------|
| 目录结构创建 | [ ] |
| MovementComponent | [ ] |
| CameraComponent | [ ] |
| ShootingComponent | [ ] |
| InputHandler 基类 | [ ] |
| KeyboardInputHandler | [ ] |
| BaseCharacter | [ ] |
| TPSCharacter | [ ] |
| nepyinit 更新 | [ ] |
| 输入映射配置 | [ ] |
| 测试验证 | [ ] |
| GitHub 推送 | [ ] |

---

> 计划创建时间：2026年4月5日
