# 关卡系统设计文档

## 游戏流程

```
主菜单(UMG) → 按开始游戏 → Level1(杀完敌人) → Level2(杀完敌人) → 胜利界面
```

## 核心组件

### 1. TPSGameMode（Python @ue.uclass，继承 GameModeBase）

- `current_level`: 当前关卡编号
- `alive_enemies`: 剩余敌人数
- `ReceiveBeginPlay()`: 用 `GetAllActorsOfClass(BaseEnemy)` 统计本关敌人总数
- `on_enemy_killed()`: 敌人死亡时调用，`alive_enemies -= 1`，为0时触发关卡完成
- `on_level_complete()`: 显示"关卡完成"→ 延迟3秒 → `OpenLevel` 加载下一关
- `start_game()`: `OpenLevel("Level1")`

### 2. 主菜单 WBP_MainMenu（编辑器蓝图Widget）

- 纯蓝图制作：标题文字 + "开始游戏"按钮
- 按钮OnClick → `OpenLevel("Level1")`
- Python 侧在主菜单关卡 ReceiveBeginPlay 里 `CreateWidget` + `AddToViewport`

### 3. 关卡完成提示（复用 CrosshairHUD）

- 在 HUD 上画"关卡完成"文字 + "进入下一关"提示
- 不需要额外 Widget

### 4. 两关视觉区分

- Level1：户外开阔区域，5个敌人（3近战+2远程），日光照明
- Level2：室内/废墟场景，8个敌人（4近战+4远程），暗色调+点光源，敌人更强

## 敌人死亡通知

- `base_enemy.py` 的 `die()` 方法里，通过 `GetGameMode()` 获取 GameMode，调用 `on_enemy_killed()`

## 关卡过渡

- `ue.GameplayStatics.OpenLevel(world, "Level2")` — 整体切换，PlayerController 自动迁移
- 每个关卡配自己的 `PlayerStart`
