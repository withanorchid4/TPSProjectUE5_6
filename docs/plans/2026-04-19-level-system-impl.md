# 关卡系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现主菜单→Level1→Level2的游戏流程，杀完敌人自动进入下一关

**Architecture:** 创建 TPSGameMode（Python @ue.uclass）管理关卡状态和敌人数统计，敌人死亡通知 GameMode，击杀完毕触发关卡切换。主菜单用 UMG Widget 蓝图实现。关卡用 OpenLevel 整体切换。

**Tech Stack:** NePy Python, UMG Blueprint, UE5.6 OpenLevel

---

## 现有关键文件

- `Content/Scripts/enemy/base_enemy.py` — `_on_death()` 里需通知 GameMode
- `Content/Scripts/system/crosshair_hud.py` — 需增加"关卡完成"/"胜利"文字绘制
- `Content/Scripts/nepyinit.py` — 需注册新类
- `Content/BluePrint/TPSGameMode.uasset` — 已有蓝图，当前是空 GameModeBase 子类
- `Config/DefaultEngine.ini` — `GlobalDefaultGameMode=/Game/BluePrint/TPSGameMode.TPSGameMode_C`
- `Content/NewMap.umap` — 当前唯一关卡

---

### Task 1: 创建 TPSGameMode Python 类

**Files:**
- Create: `Content/Scripts/system/game_mode.py`

**Step 1: 创建 game_mode.py**

```python
# -*- encoding: utf-8 -*-
"""关卡游戏模式 — 管理敌人数、关卡切换"""

import ue


@ue.uclass()
class TPSGameMode(ue.GameModeBase):
    """TPS 游戏模式
    
    职责：
    - 统计本关敌人数
    - 敌人死亡时递减，为0触发关卡完成
    - 管理关卡切换（OpenLevel）
    """

    LEVEL_COMPLETE_DELAY = 3.0  # 关卡完成后延迟秒数再切关

    def __init_pyobj__(self):
        self.alive_enemies = 0
        self.current_level = 0
        self._level_complete = False
        self._transition_timer = 0.0
        self._is_main_menu = False

    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        # 判断当前关卡
        level_name = self.GetWorld().GetOuter().GetName()
        if level_name == "MainMenu":
            self._is_main_menu = True
            self._show_main_menu()
            return
        
        # 游戏关卡：统计敌人
        self._is_main_menu = False
        self._count_enemies()
        
        if level_name == "Level1":
            self.current_level = 1
        elif level_name == "Level2":
            self.current_level = 2
        else:
            self.current_level = 1
        
        ue.LogWarning(f"TPSGameMode: Level {self.current_level} started, enemies={self.alive_enemies}")

    def _count_enemies(self):
        """统计场景中所有敌人"""
        from enemy.base_enemy import BaseEnemy
        actors = ue.GameplayStatics.GetAllActorsOfClass(self, BaseEnemy)
        if actors:
            self.alive_enemies = len(actors)
        else:
            self.alive_enemies = 0

    def on_enemy_killed(self):
        """敌人死亡时调用"""
        self.alive_enemies -= 1
        ue.LogWarning(f"TPSGameMode: Enemy killed, remaining={self.alive_enemies}")
        
        if self.alive_enemies <= 0 and not self._level_complete:
            self._on_level_complete()

    def _on_level_complete(self):
        """关卡完成"""
        self._level_complete = True
        self._transition_timer = self.LEVEL_COMPLETE_DELAY
        ue.LogWarning(f"TPSGameMode: Level {self.current_level} complete!")

    def _show_main_menu(self):
        """显示主菜单 Widget"""
        widget_class = ue.LoadObject(ue.Class, "/Game/BluePrint/WBP_MainMenu.WBP_MainMenu_C")
        if not widget_class:
            ue.LogWarning("TPSGameMode: WBP_MainMenu not found, using HUD fallback")
            return
        pc = ue.GameplayStatics.GetPlayerController(self, 0)
        if pc:
            widget = ue.WidgetBlueprintLibrary.CreateWidget(pc, widget_class)
            if widget:
                widget.AddToViewport(0)
                ue.LogWarning("TPSGameMode: Main menu shown")

    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if not self._level_complete:
            return
        
        self._transition_timer -= delta_time
        if self._transition_timer <= 0.0:
            self._transition_to_next_level()

    def _transition_to_next_level(self):
        """切换到下一关"""
        if self.current_level == 1:
            ue.GameplayStatics.OpenLevel(self, "Level2")
        elif self.current_level == 2:
            # 胜利，回到主菜单
            ue.GameplayStatics.OpenLevel(self, "MainMenu")
```

**Step 2: 注册到 nepyinit.py**

在 `Content/Scripts/nepyinit.py` 的 `on_init()` 中添加：

```python
    # 注册 GameMode 类
    try:
        from system.game_mode import TPSGameMode
        ue.LogWarning('TPSGameMode class loaded successfully!')
    except Exception as e:
        ue.LogError(f'Failed to load TPSGameMode: {e}')
        import traceback
        traceback.print_exc()
```

**Step 3: 修改 TPSGameMode 蓝图父类**

在编辑器中：
1. 打开 `Content/BluePrint/TPSGameMode` 蓝图
2. 将父类从 `GameModeBase` 改为 `TPSGameMode`（Python 类）
3. 编译保存

> 如果无法在蓝图里选 Python 类作父类，则保持蓝图为空 GameModeBase 子类，
> 改用纯 Python 方式：在 DefaultEngine.ini 中把 GlobalDefaultGameMode 指向 Python 类的路径。
> 这一步需要在编辑器中试验。

**Step 4: 提交**

```bash
git add Content/Scripts/system/game_mode.py Content/Scripts/nepyinit.py
git commit -m "feat: add TPSGameMode with level tracking and transitions"
```

---

### Task 2: 敌人死亡通知 GameMode

**Files:**
- Modify: `Content/Scripts/enemy/base_enemy.py` — `_on_death()` 方法

**Step 1: 在 _on_death 中通知 GameMode**

在 `base_enemy.py` 的 `_on_death()` 方法开头（`self.ai.set_dead()` 之后）添加：

```python
        # 通知 GameMode 敌人死亡
        game_mode = self.GetWorld().GetAuthGameMode()
        if game_mode and hasattr(game_mode, 'on_enemy_killed'):
            game_mode.on_enemy_killed()
```

**Step 2: 验证**

在编辑器中运行，杀死敌人，检查日志输出 "TPSGameMode: Enemy killed, remaining=X"

**Step 3: 提交**

```bash
git add Content/Scripts/enemy/base_enemy.py
git commit -m "feat: enemy death notifies GameMode"
```

---

### Task 3: HUD 显示关卡信息

**Files:**
- Modify: `Content/Scripts/system/crosshair_hud.py`

**Step 1: 添加关卡状态绘制**

在 `CrosshairHUD.ReceiveDrawHUD` 中，弹药之后添加关卡信息绘制：

```python
        # 6) 关卡信息
        self._draw_level_info(size_x, size_y)
```

添加新方法：

```python
    # ── 关卡信息 ──
    def _draw_level_info(self, size_x, size_y):
        game_mode = self.GetWorld().GetAuthGameMode()
        if not game_mode or not hasattr(game_mode, 'current_level'):
            return
        
        # 关卡标题（左上角）
        level_text = f"LEVEL {game_mode.current_level}"
        level_color = ue.LinearColor(1.0, 1.0, 1.0, 0.7)
        self.DrawText(level_text, level_color, 40.0, 40.0, None, 1.2, False)
        
        # 剩余敌人数
        if hasattr(game_mode, 'alive_enemies'):
            enemy_text = f"Enemies: {game_mode.alive_enemies}"
            enemy_color = ue.LinearColor(1.0, 0.8, 0.3, 0.8)
            self.DrawText(enemy_text, enemy_color, 40.0, 65.0, None, 1.0, False)
        
        # 关卡完成提示
        if hasattr(game_mode, '_level_complete') and game_mode._level_complete:
            center_x = size_x / 2.0
            center_y = size_y / 2.0 - 50.0
            
            if game_mode.current_level == 2:
                title = "VICTORY!"
            else:
                title = "LEVEL COMPLETE!"
            
            title_color = ue.LinearColor(0.2, 1.0, 0.4, 1.0)
            self.DrawText(title, title_color, center_x - 120.0, center_y, None, 2.0, False)
            
            if game_mode.current_level < 2:
                sub = "Entering next level..."
                sub_color = ue.LinearColor(1.0, 1.0, 1.0, 0.7)
                self.DrawText(sub, sub_color, center_x - 100.0, center_y + 40.0, None, 1.0, False)
            else:
                sub = "Returning to menu..."
                sub_color = ue.LinearColor(1.0, 1.0, 1.0, 0.7)
                self.DrawText(sub, sub_color, center_x - 90.0, center_y + 40.0, None, 1.0, False)
```

**Step 2: 提交**

```bash
git add Content/Scripts/system/crosshair_hud.py
git commit -m "feat: HUD shows level info, enemy count, level complete text"
```

---

### Task 4: 创建主菜单 Widget 蓝图

**Files:**
- 在编辑器中创建：`Content/BluePrint/WBP_MainMenu`（UMG Widget Blueprint）

**Step 1: 创建 Widget 蓝图**

在编辑器中：
1. Content Browser → 右键 → User Interface → Widget Blueprint
2. 命名为 `WBP_MainMenu`，保存到 `Content/BluePrint/`
3. 设计界面：
   - Canvas Panel (根)
   - Text Block: "TPS Demo" (大标题，居中靠上，字号48+)
   - Button: "Start Game" (居中)
   - Text Block (Button内): "Start Game"

**Step 2: 按钮点击事件**

在 WBP_MainMenu 蓝图中：
1. 选中 Button → Details → Events → On Clicked → +
2. 在事件图中连接：On Clicked → Open Level (by Name) → Level Name = "Level1"

**Step 3: 创建 MainMenu 关卡**

1. File → New Level → Empty Level
2. 保存为 `Content/Maps/MainMenu`
3. 添加一个 PlayerStart
4. 添加简单场景（可选：一个平台+天空）

**Step 4: 更新 DefaultEngine.ini**

将 `GameDefaultMap` 改为主菜单：

```ini
GameDefaultMap=/Game/Maps/MainMenu.MainMenu
EditorStartupMap=/Game/NewMap.NewMap
```

> EditorStartupMap 保持 NewMap 方便开发，GameDefaultMap 改为主菜单让游戏从主菜单启动。

**Step 5: 验证**

PIE 运行，应看到主菜单，点击 Start Game 进入 Level1

**Step 6: 提交**

提交 ini 变更和蓝图资源

---

### Task 5: 创建 Level1 和 Level2 关卡

**Files:**
- 在编辑器中创建：`Content/Maps/Level1`、`Content/Maps/Level2`

**Step 1: 将当前 NewMap 另存为 Level1**

1. 打开 NewMap
2. File → Save As → `Content/Maps/Level1`
3. 确认场景中已有敌人（3近战+2远程=5个）
4. 确认有 PlayerStart

**Step 2: 创建 Level2**

1. File → New Level → Empty Level
2. 保存为 `Content/Maps/Level2`
3. 添加场景内容（区别于 Level1）：
   - 更暗的光照（DirectionalLight 强度降低，加 PointLight）
   - 放置 8 个敌人（4近战+4远程）
   - 不同的建筑/遮挡物布局
4. 添加 PlayerStart

**Step 3: 更新 DefaultEngine.ini（如果需要）**

确保关卡名称能被 OpenLevel 正确找到。Level1、Level2、MainMenu 三个地图文件名需与代码中的字符串一致。

**Step 4: 验证完整流程**

1. 运行游戏 → 主菜单
2. 点击 Start Game → Level1
3. 杀完 5 个敌人 → "LEVEL COMPLETE!" → 3秒后自动进入 Level2
4. 杀完 8 个敌人 → "VICTORY!" → 3秒后回到主菜单

**Step 5: 提交**

提交新关卡资源

---

## 实现顺序

1. Task 1（TPSGameMode） → 核心逻辑
2. Task 2（敌人通知） → 依赖 Task 1
3. Task 3（HUD关卡信息） → 依赖 Task 1
4. Task 4（主菜单Widget） → 可与 Task 5 并行
5. Task 5（关卡创建） → 依赖 Task 1-3

## 注意事项

- TPSGameMode 蓝图已有，需确认是否能选 Python 类作父类；如果不能，需在编辑器中把蓝图删掉，直接用 Python 类的路径配到 DefaultEngine.ini
- OpenLevel 的 Level Name 是地图文件名（不含路径和后缀），如 "Level1"、"Level2"、"MainMenu"
- 敌人蓝图的 Tick 问题：确保蓝图中没有 Event Tick 节点（已知问题 #37）
