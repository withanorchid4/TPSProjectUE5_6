# TODO: 结算界面从 HUD 改为 Widget

## 背景

当前结算界面（VICTORY/DEFEAT）是用 HUD 的 `DrawText` + 键盘按键（R/N/M）实现的，这是错误的方案。用户要求用 **UMG Widget Blueprint**（方案 B）来做结算界面，和主菜单 `WBP_MainMenu` 同样的方式。

## 当前错误实现（需删除/替换）

### 1. `crosshair_hud.py` — `_draw_game_result()` 方法
- 用 `DrawRect` + `DrawText` 画结算界面，需要删掉
- `_draw_level_info()` 中判断 `game_mode._game_result` 后调用 `_draw_game_result()` 的逻辑也需要删

### 2. `keyboard_handler.py` — `tick()` 中的结算按键检测
- 用 `WasInputKeyJustPressed(ue.Key("R/N/M"))` 检测按键，需要删掉
- 结算界面的按钮交互应由 Widget 自身处理

### 3. `game_mode.py` — `retry_level()` / `next_level()` / `back_to_menu()` 方法
- 这些方法本身逻辑是对的，但调用方需要改：由 Widget 按钮回调 → 蓝图调用 Python 函数，而非键盘监听

## 改造目标

创建 `WBP_GameResult` Widget，包含：
- 黑色半透明遮罩背景
- VICTORY / DEFEAT 大标题（根据 GameMode 的 `_game_result` 决定）
- 按钮们：
  - **Retry** — 重新挑战当前关卡
  - **Next Level** — 仅 Level1 胜利时显示
  - **Menu** — 返回主菜单

## 实现步骤

### Step 1: 修改 `game_mode.py`

- 新增 `_pending_show_result = False` 标记
- 在 `_on_victory()` 和 `on_player_died()` 中，设置 `_pending_show_result = True`（替代直接依赖 `_game_result`）
- 删除 `_game_result` 相关的 HUD 渲染逻辑（保留字段本身供 Widget 判断类型）
- `retry_level()` / `next_level()` / `back_to_menu()` 保留，这些会被蓝图按钮调用
- 在 `ReceiveTick` 中处理 `_pending_show_result`：等 PlayerController 就绪后设标记让蓝图知道该显示结算 Widget

### Step 2: 删除 `crosshair_hud.py` 中的结算绘制代码

- 删除 `_draw_game_result()` 方法
- 删除 `_draw_level_info()` 中调用 `_draw_game_result()` 的分支
- HUD 只保留正常游戏时的关卡信息显示（LEVEL X + Enemies 数量）

### Step 3: 删除 `keyboard_handler.py` 中的结算按键检测

- 删除 `tick()` 开头的 `game_mode._game_result` 判断和 R/N/M 按键检测代码
- 结算界面的交互完全由 Widget 按钮处理

### Step 4: 在编辑器中创建 `WBP_GameResult` Widget Blueprint

- 位置：`Content/BluePrint/WBP_GameResult`
- 结构：
  - `CanvasPanel` 根节点
  - `Border` 或 `Image` — 全屏黑色半透明遮罩（Color: Black, Opacity: 0.7）
  - `TextBlock` — 标题（VICTORY / DEFEAT），绑定到变量
  - `Button` + `TextBlock` — Retry
  - `Button` + `TextBlock` — Next Level（Visibility 绑定变量，默认 Hidden）
  - `Button` + `TextBlock` — Menu
- 创建变量：
  - `ResultType` (String) — "victory" / "defeat"
  - `CurrentLevel` (Integer)
- 按钮点击事件：
  - **Retry** → `Set Input Mode Game Only` + `Set Show Mouse Cursor(False)` → `Open Level (current_level_name)`
  - **Next Level** → `Set Input Mode Game Only` + `Set Show Mouse Cursor(False)` → `Open Level "Level2"`
  - **Menu** → `Set Input Mode Game Only` + `Set Show Mouse Cursor(False)` → `Open Level "MainMenu"`

### Step 5: 在 Level Blueprint 中创建/显示结算 Widget

在 **Level1** 和 **Level2** 的 Level Blueprint 中：
- `Event Tick` → 检查 `GameMode._pending_show_result` / `_game_result`
- 当检测到结算标记时：
  1. `Create Widget (WBP_GameResult)` → `Add to Viewport`
  2. `Set Input Mode UI Only`
  3. `Set Show Mouse Cursor(True)`
  4. 设置 Widget 的 `ResultType` 和 `CurrentLevel` 变量
  5. 根据 `CurrentLevel == 1` 且 `ResultType == "victory"` 设置 Next Level 按钮可见

### Step 6: 设置 `Set Input Mode UI Only`

和主菜单一样，结算界面显示时需要：
- `Set Input Mode UI Only`（让按钮可点击）
- `Set Show Mouse Cursor(True)`

按钮点击后先恢复：
- `Set Input Mode Game Only`
- `Set Show Mouse Cursor(False)`
然后再 `Open Level`

## 关键约束（踩坑记录，务必遵守）

| # | 规则 | 原因 |
|---|------|------|
| 1 | **NePy 不暴露 `CreateWidget`** | Widget 创建必须在蓝图（Level Blueprint）中做，Python 只设标记 |
| 2 | **蓝图 Event BeginPlay 会覆盖 Python `ReceiveBeginPlay`** | 蓝图中必须完全删除 Event BeginPlay 节点（断开连线不够） |
| 3 | **蓝图 Event Tick 会覆盖 Python `ReceiveTick`** | 如果 Level Blueprint 需要 Tick，Python 的 GameMode Tick 就不能依赖 |
| 4 | **`Set Input Mode Game Only` 在 BeginPlay 中无效** | PlayerController 尚未初始化，必须在按钮事件或 Tick 延迟后恢复 |
| 5 | **PIE 时 level_name 带前缀** | 用 `"Level1" in level_name` 而非 `==` 比较 |
| 6 | **主菜单按钮先恢复输入再切关** | 否则下一关也是 UI Only 模式 |

## 当前未提交的 diff

以下 4 个文件有未提交的改动（错误的 HUD 结算实现），新 agent 需要在这些文件基础上修改：

- `Content/Scripts/character/base_character.py` — `_on_death()` 通知 GameMode（保留）
- `Content/Scripts/input_handlers/keyboard_handler.py` — 删除结算按键检测
- `Content/Scripts/system/crosshair_hud.py` — 删除结算绘制代码
- `Content/Scripts/system/game_mode.py` — 保留 `_game_result` + `on_player_died()` + `retry_level()` 等，删除 HUD 相关逻辑，新增 Widget 标记

## 文件结构参考

```
Content/
├── BluePrint/
│   ├── TPSGameMode2.uasset     — GameMode 蓝图（必须完全空白）
│   ├── WBP_MainMenu.uasset     — 主菜单 Widget（已有）
│   └── WBP_GameResult.uasset   — 结算界面 Widget（待创建）
├── Maps/
│   ├── MainMenu.umap           — 主菜单关卡
│   ├── Level1.umap             — 第一关
│   └── Level2.umap             — 第二关
└── Scripts/
    ├── system/
    │   ├── game_mode.py         — 需修改
    │   └── crosshair_hud.py     — 需修改
    ├── input_handlers/
    │   └── keyboard_handler.py  — 需修改
    └── character/
        └── base_character.py    — 已OK，不需改
```
