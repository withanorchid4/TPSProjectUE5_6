# 性能分级模块 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 TPS 游戏添加零耦合的性能分级模块，用户在主菜单手动选择 Low/Med/High 画质，引擎 Scalability 参数即时生效并持久化。

**Architecture:** `GraphicsQualityManager` 单例调 UE `GameUserSettings.ScalabilityQuality` API 控制全局画质；`GraphicsSettingsPanel` Python UI 控制器创建 WBP_GraphicsSettings Widget 绑定按钮回调。不修改任何现有游戏逻辑。

**Tech Stack:** UE5.6 + NePy (Python), UE GameUserSettings Scalability API

---

### Task 1: GraphicsQualityManager 核心

**Files:**
- Create: `Content/Scripts/system/graphics_quality_manager.py`

**Step 1: 创建 graphics_quality_manager.py**

```python
# -*- encoding: utf-8 -*-
"""性能分级管理器 — 零耦合方案

通过 UE GameUserSettings.ScalabilityQuality API 控制全局画质。
三档: Low(0) / Med(1) / High(2)
切换后立即生效，SaveConfig() 持久化到 GameUserSettings.ini。
"""

import ue


class GraphicsQualityManager:
    """性能分级管理器（单例）

    用法:
        gqm = GraphicsQualityManager.get_instance()
        gqm.set_quality(0)  # Low
        gqm.set_quality(1)  # Med
        gqm.set_quality(2)  # High
    """

    QUALITY_LOW = 0
    QUALITY_MED = 1
    QUALITY_HIGH = 2

    QUALITY_NAMES = {0: "Low", 1: "Med", 2: "High"}

    # 各档位 Scalability 参数值 (0-4 对应 Engine Scalability Level)
    # 我们用 0/1/2 三档，分别映射到引擎的 0/1/2
    QUALITY_PRESETS = {
        # level: (Resolution, ViewDist, AA, Shadow, GI, Reflection, PostProcess, Texture, Effects, Foliage)
        0: (0.7, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        1: (0.9, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        2: (1.0, 2, 2, 2, 2, 2, 2, 2, 2, 2),
    }

    _instance = None

    def __init__(self):
        self._current_quality = self.QUALITY_HIGH  # 默认 High
        self._settings = None  # UGameUserSettings 引用

    @staticmethod
    def get_instance():
        if GraphicsQualityManager._instance is None:
            GraphicsQualityManager._instance = GraphicsQualityManager()
        return GraphicsQualityManager._instance

    @staticmethod
    def reset_instance():
        GraphicsQualityManager._instance = None

    @property
    def current_quality(self):
        return self._current_quality

    @property
    def current_quality_name(self):
        return self.QUALITY_NAMES.get(self._current_quality, "Unknown")

    def initialize(self):
        """初始化：获取 GameUserSettings，读取当前档位"""
        try:
            self._settings = ue.GameUserSettings.GetGameUserSettings()
            if self._settings:
                # 从已保存的配置读取当前档位
                self._settings.LoadConfig()
                sq = self._settings.ScalabilityQuality
                # 用 ShadowQuality 作为档位指示器（所有组理论上应一致）
                self._current_quality = getattr(sq, 'ShadowQuality', 2)
                ue.LogWarning(f"GraphicsQualityManager: Initialized, current={self.QUALITY_NAMES.get(self._current_quality, '?')}")
            else:
                ue.LogWarning("GraphicsQualityManager: GameUserSettings not found, using default High")
        except Exception as e:
            ue.LogError(f"GraphicsQualityManager: Init failed: {e}")

    def set_quality(self, level: int):
        """设置画质等级（立即生效 + 持久化）

        Args:
            level: 0=Low, 1=Med, 2=High
        """
        if level not in self.QUALITY_PRESETS:
            ue.LogWarning(f"GraphicsQualityManager: Invalid quality level {level}")
            return False

        if level == self._current_quality:
            ue.Log(f"GraphicsQualityManager: Already at {self.QUALITY_NAMES[level]}")
            return True

        preset = self.QUALITY_PRESETS[level]
        (
            res_quality, view_dist, aa, shadow, gi,
            reflection, post_process, texture, effects, foliage
        ) = preset

        try:
            if not self._settings:
                self._settings = ue.GameUserSettings.GetGameUserSettings()

            if not self._settings:
                ue.LogError("GraphicsQualityManager: No GameUserSettings!")
                return False

            sq = self._settings.ScalabilityQuality

            # 分辨率缩放（0.0~1.0）
            sq.ResolutionQuality = res_quality

            # 各质量组（0-4 整数）
            sq.ViewDistanceQuality = view_dist
            sq.AntiAliasingQuality = aa
            sq.ShadowQuality = shadow
            sq.GlobalIlluminationQuality = gi
            sq.ReflectionQuality = reflection
            sq.PostProcessQuality = post_process
            sq.TextureQuality = texture
            sq.EffectsQuality = effects
            sq.FoliageQuality = foliage

            # 应用 + 持久化
            self._settings.ApplySettings(True)
            self._settings.SaveConfig()

            self._current_quality = level
            ue.LogWarning(f"GraphicsQualityManager: Set to {self.QUALITY_NAMES[level]}, applied & saved")
            return True

        except Exception as e:
            ue.LogError(f"GraphicsQualityManager: set_quality failed: {e}")
            return False
```

**Step 2: 在编辑器中验证**

1. 启动 UE 编辑器，PIE 运行
2. 在 Output Log 中搜索 `GraphicsQualityManager` 确认无 import 错误
3. 在 GM 命令行或 Python 控制台手动测试：
   ```python
   from system.graphics_quality_manager import GraphicsQualityManager
   gqm = GraphicsQualityManager.get_instance()
   gqm.initialize()
   gqm.set_quality(0)  # 画面应立刻变差
   gqm.set_quality(2)  # 画面应立刻恢复
   ```

**Step 3: Commit**

```bash
git add Content/Scripts/system/graphics_quality_manager.py
git commit -m "feat: add GraphicsQualityManager with Scalability API"
```

---

### Task 2: GraphicsSettingsPanel UI 控制器

**Files:**
- Create: `Content/Scripts/ui/graphics_settings_ui.py`

**Step 1: 创建 graphics_settings_ui.py**

```python
# -*- encoding: utf-8 -*-
"""画质设置界面控制器

WBP_GraphicsSettings 需要的命名控件：
- btn_low     — Button，Low 画质
- btn_med     — Button，Med 画质
- btn_high    — Button，High 画质
- txt_current — TextBlock，当前画质状态
- btn_back    — Button，返回主菜单
"""

import ue
from system.graphics_quality_manager import GraphicsQualityManager


class GraphicsSettingsPanel:
    """画质设置面板控制器"""

    WBP_PATH = "/Game/BluePrint/WBP_GraphicsSettings.WBP_GraphicsSettings_C"

    def __init__(self, parent, pc):
        self._parent = parent
        self._pc = pc
        self._widget = None
        self._gqm = GraphicsQualityManager.get_instance()
        self._destroyed = False
        self._on_back_callback = None

        # 创建 Widget
        widget_class = ue.LoadObject(ue.Class, self.WBP_PATH)
        if not widget_class:
            ue.LogError("GraphicsSettingsPanel: Failed to load WBP_GraphicsSettings_C!")
            return

        self._widget = ue.WidgetBlueprintLibrary.Create(parent, widget_class, pc)
        if not self._widget:
            ue.LogError("GraphicsSettingsPanel: CreateWidget returned None!")
            return

        # 绑定按钮事件
        try:
            self._widget.btn_low.OnClicked.Add(self._on_low)
            self._widget.btn_med.OnClicked.Add(self._on_med)
            self._widget.btn_high.OnClicked.Add(self._on_high)
            self._widget.btn_back.OnClicked.Add(self._on_back)
        except Exception as e:
            ue.LogWarning(f"GraphicsSettingsPanel: Delegate binding failed ({e})")

        # 初始化显示
        self._update_display()

        # 显示到视口
        self._widget.bIsFocusable = True
        self._widget.AddToViewport(0)
        pc.bShowMouseCursor = True
        self._widget.SetKeyboardFocus()

        ue.LogWarning("GraphicsSettingsPanel: Shown")

    # ─── 按钮回调 ───

    def _on_low(self):
        if self._destroyed:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_LOW)
        self._update_display()

    def _on_med(self):
        if self._destroyed:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_MED)
        self._update_display()

    def _on_high(self):
        if self._destroyed:
            return
        self._gqm.set_quality(GraphicsQualityManager.QUALITY_HIGH)
        self._update_display()

    def _on_back(self):
        if self._destroyed:
            return
        if self._on_back_callback:
            try:
                self._on_back_callback()
            except Exception as e:
                ue.LogError(f"GraphicsSettingsPanel: back callback error: {e}")

    # ─── 公开接口 ───

    def set_back_callback(self, callback):
        """设置返回按钮回调（由 TPSGameMode 注册）"""
        self._on_back_callback = callback

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        if self._widget:
            try:
                self._widget.RemoveFromParent()
            except Exception:
                pass
            self._widget = None
        ue.LogWarning("GraphicsSettingsPanel: Destroyed")

    # ─── 内部工具 ───

    def _update_display(self):
        """更新当前画质状态文本和按钮高亮"""
        current = self._gqm.current_quality
        name = self._gqm.current_quality_name

        # 状态文本
        try:
            txt = self._find_widget("txt_current")
            if txt:
                txt.SetText(f"Current: {name}")
        except Exception:
            pass

        # 按钮高亮：选中项加 [ ] 标记
        btn_names = {
            GraphicsQualityManager.QUALITY_LOW: "btn_low",
            GraphicsQualityManager.QUALITY_MED: "btn_med",
            GraphicsQualityManager.QUALITY_HIGH: "btn_high",
        }
        for level, btn_name in btn_names.items():
            try:
                btn = self._find_widget(btn_name)
                if btn:
                    # 选中项用 [Low] / [Med] / [High]，未选中用 Low / Med / High
                    label = self._gqm.QUALITY_NAMES[level]
                    if level == current:
                        label = f"[ {label} ]"
                    # 尝试设置按钮文本（部分 Widget 类型可能不支持）
                    if hasattr(btn, 'SetText'):
                        btn.SetText(label)
            except Exception:
                pass

    def _find_widget(self, name):
        if not self._widget:
            return None
        try:
            w = getattr(self._widget, name, None)
            if w:
                return w
        except Exception:
            pass
        try:
            w = self._widget.GetWidgetFromName(name)
            if w:
                return w
        except Exception:
            pass
        return None
```

**Step 2: 在编辑器中验证**

1. 确认文件无语法错误（import 可解析）
2. 暂不做 UI 测试（等 Task 3 蓝图创建后一起验证）

**Step 3: Commit**

```bash
git add Content/Scripts/ui/graphics_settings_ui.py
git commit -m "feat: add GraphicsSettingsPanel UI controller"
```

---

### Task 3: UE 蓝图 WBP_GraphicsSettings + WBP_MainMenu 修改

**Files:**
- Create: `Content/BluePrint/WBP_GraphicsSettings` （在 UE 编辑器中手动创建）
- Modify: `Content/BluePrint/WBP_MainMenu` （在 UE 编辑器中手动添加按钮）

**Step 1: 在 UE 编辑器中创建 WBP_GraphicsSettings**

1. Content Browser → 右键 → User Interface → Widget Blueprint
2. 命名为 `WBP_GraphicsSettings`，保存到 `/Game/BluePrint/`
3. 打开蓝图，添加以下控件：
   - **Vertical Box** (根)
     - **TextBlock** "画质设置" (Title)
     - **Horizontal Box**
       - **Button** `btn_low` → 内部 TextBlock 显示 "Low"
       - **Button** `btn_med` → 内部 TextBlock 显示 "Med"
       - **Button** `btn_high` → 内部 TextBlock 显示 "High"
     - **TextBlock** `txt_current` → 默认文本 "Current: High"
     - **Button** `btn_back` → 内部 TextBlock 显示 "返回"
4. 设置 `Is Variable` = True 对所有命名的 Button 和 TextBlock
5. 编译保存

**Step 2: 在 WBP_MainMenu 中添加画质设置按钮**

1. 打开 `WBP_MainMenu`
2. 在现有按钮下方添加 **Button** `btn_graphics_settings`
3. 内部 TextBlock 显示 "画质设置"
4. 设置 `Is Variable` = True
5. 编译保存

**Step 3: 验证**

1. PIE 运行到 MainMenu
2. 确认新按钮可见
3. 点击画质设置按钮（此时回调未绑定，不会报错但也没反应 — 正常）
4. Commit 蓝图文件

```bash
git add Content/BluePrint/WBP_GraphicsSettings.uasset Content/BluePrint/WBP_GraphicsSettings.uasset
git add Content/BluePrint/WBP_MainMenu.uasset
git commit -m "feat: add WBP_GraphicsSettings blueprint + btn_graphics_settings to MainMenu"
```

---

### Task 4: 接入 GameMode 和 MainMenuPanel

**Files:**
- Modify: `Content/Scripts/ui/main_menu_ui.py`
- Modify: `Content/Scripts/system/game_mode.py`
- Modify: `Content/Scripts/nepyinit.py`

**Step 1: 修改 main_menu_ui.py — 绑定画质按钮**

在 `MainMenuPanel.__init__` 的按钮绑定区域添加：

```python
# 在现有 try 块内，btn_delete_char 绑定之后添加：
try:
    self._widget.btn_graphics_settings.OnClicked.Add(self._on_graphics_settings)
except Exception as e:
    ue.LogWarning(f"MainMenuPanel: btn_graphics_settings binding failed ({e})")
```

在 `MainMenuPanel` 类中添加新方法：

```python
def _on_graphics_settings(self):
    """画质设置按钮回调 — 通知 game_mode 切换到画质设置面板"""
    if self._destroyed:
        return
    if self._on_graphics_settings_callback:
        try:
            self._on_graphics_settings_callback()
        except Exception as e:
            ue.LogError(f"MainMenuPanel: graphics_settings callback error: {e}")
```

在类末尾（`_on_enter_game_callback = None` 旁边）添加：

```python
_on_graphics_settings_callback = None

def set_graphics_settings_callback(self, callback):
    """设置画质设置按钮回调"""
    self._on_graphics_settings_callback = callback
```

**Step 2: 修改 game_mode.py — 接入 GraphicsSettingsPanel**

在 `TPSGameMode.__init__` 中添加实例变量：

```python
self._graphics_settings_panel = None  # 画质设置面板控制器
```

在 `_on_login_success` 方法中，`MainMenuPanel` 创建后添加回调注册：

```python
self._main_menu_panel.set_graphics_settings_callback(self._on_show_graphics_settings)
```

添加新方法：

```python
def _on_show_graphics_settings(self):
    """显示画质设置面板"""
    if self._main_menu_panel:
        self._main_menu_panel.destroy()
        self._main_menu_panel = None

    pc = ue.GameplayStatics.GetPlayerController(self, 0)
    if not pc:
        ue.LogError("TPSGameMode: No PlayerController for graphics settings!")
        return

    from ui.graphics_settings_ui import GraphicsSettingsPanel
    self._graphics_settings_panel = GraphicsSettingsPanel(self, pc)
    self._graphics_settings_panel.set_back_callback(self._on_graphics_settings_back)
    ue.LogWarning("TPSGameMode: Graphics settings panel shown")

def _on_graphics_settings_back(self):
    """从画质设置返回主菜单"""
    if self._graphics_settings_panel:
        self._graphics_settings_panel.destroy()
        self._graphics_settings_panel = None

    pc = ue.GameplayStatics.GetPlayerController(self, 0)
    if not pc:
        return

    from ui.main_menu_ui import MainMenuPanel
    self._main_menu_panel = MainMenuPanel(self, pc)
    self._main_menu_panel.set_enter_game_callback(self._on_login_enter_game)
    self._main_menu_panel.set_graphics_settings_callback(self._on_show_graphics_settings)
    ue.LogWarning("TPSGameMode: Back to main menu")
```

**Step 3: 修改 nepyinit.py — 初始化 GraphicsQualityManager**

在 `on_post_engine_init` 函数中添加：

```python
# 初始化性能分级管理器
try:
    from system.graphics_quality_manager import GraphicsQualityManager
    gqm = GraphicsQualityManager.get_instance()
    gqm.initialize()
except Exception as e:
    ue.LogError(f"Failed to initialize GraphicsQualityManager: {e}")
```

**Step 4: 验证完整流程**

1. PIE 运行到 MainMenu
2. 登录后进入主菜单
3. 点击"画质设置"按钮 → 弹出画质设置面板
4. 点击 Low → 画面立刻变差（分辨率降低、阴影消失、后处理关闭）
5. 点击 High → 画面立刻恢复
6. 点击"返回" → 回到主菜单
7. 退出 PIE 后重新运行 → 画质设置应保留（持久化验证）

**Step 5: Commit**

```bash
git add Content/Scripts/ui/main_menu_ui.py Content/Scripts/system/game_mode.py Content/Scripts/nepyinit.py
git commit -m "feat: integrate GraphicsQualityManager into MainMenu and GameMode"
```

---

### Task 5: 最终验证 + DefaultEngine.ini 清理

**Files:**
- Modify: `Config/DefaultEngine.ini`

**Step 1: 清理 DefaultEngine.ini**

当前硬写了 `DefaultGraphicsPerformance=Maximum`，这会覆盖 Scalability 设置。将其改为让 GameUserSettings 决定：

```ini
# 修改前
DefaultGraphicsPerformance=Maximum
AppliedDefaultGraphicsPerformance=Maximum

# 修改后 — 保持不变，因为这是初始默认值
# GameUserSettings.ScalabilityQuality 会在运行时覆盖
```

实际上，`DefaultGraphicsPerformance=Maximum` 只是首次启动的默认值，`GameUserSettings.SaveConfig()` 后会被用户的覆盖。所以**不需要改** DefaultEngine.ini。

**Step 2: 完整流程测试**

1. 删除 `Saved/Config/Windows/GameUserSettings.ini`（清除旧配置）
2. PIE 运行
3. MainMenu → 登录 → 主菜单 → 画质设置
4. 测试 Low/Med/High 三档切换
5. 退出 PIE，检查 `Saved/Config/Windows/GameUserSettings.ini` 中 ScalabilityQuality 是否保存
6. 重新 PIE，确认画质档位恢复

**Step 3: Commit**

```bash
git commit --allow-empty -m "chore: graphics quality module complete, verified"
```
