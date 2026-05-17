# 性能分级模块 — 技术文档

## 需求来源

客户端要求第 15 条：性能分级模块，思考如何做分级判定，对高开销模块做性能分级。

---

## 设计方案

### 方案选型

采用**零耦合方案**：纯引擎 Scalability API，不依赖任何其他游戏模块。后续可扩展为低耦合方案（游戏模块按需读取档位做精细控制）。

### 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 触发方式 | 设置菜单手动选择 | 简单直观，避免自动检测误判 |
| 档位数量 | 3 档 | Low / Med / High 覆盖常见硬件区间 |
| 持久化 | GameUserSettings.ini | 引擎原生机制，下次启动自动恢复 |
| 入口 | 主菜单"画质设置"按钮 | 不影响游戏内操作 |

### 三档参数映射

| Scalability 组 | Low(0) | Med(1) | High(2) |
|---|---|---|---|
| ResolutionQuality | 70 | 90 | 100 |
| ViewDistanceQuality | 0 | 1 | 2 |
| AntiAliasingQuality | 0 | 1 | 2 |
| ShadowQuality | 0 | 1 | 2 |
| GlobalIlluminationQuality | 0 | 1 | 2 |
| ReflectionQuality | 0 | 1 | 2 |
| PostProcessQuality | 0 | 1 | 2 |
| TextureQuality | 0 | 1 | 2 |
| EffectsQuality | 0 | 1 | 2 |
| FoliageQuality | 0 | 1 | 2 |

---

## 实现架构

```
WBP_MainMenu (btn_graphics_settings)
    └→ GameMode._show_graphics_settings()
        └→ GraphicsSettingsPanel (WBP_GraphicsSettings)
            ├─ btn_low / btn_med / btn_high → GraphicsQualityManager.set_quality()
            └─ btn_back → 返回主菜单

GraphicsQualityManager (单例)
    ├─ initialize()            — 定位 ini 路径，读取已保存档位
    ├─ set_quality(level)      — 写 ini + sg.XxxQuality 控制台命令即时生效
    └─ current_quality         — 当前档位 (0/1/2)
```

### 关键实现细节

1. **ini 路径定位**：通过 `__file__` 向上推导项目根目录（NePy 不暴露 `ue.ProjectDir()`）
2. **运行时生效**：通过 `KismetSystemLibrary.ExecuteConsoleCommand` 执行 `sg.XxxQuality` 控制台命令，所有 10 组统一使用 `SetByConsole` 优先级，避免优先级冲突
3. **分辨率特殊处理**：`ResolutionQuality` 不支持 `sg.ResolutionQuality` 命令，改用 `r.ScreenPercentage` 直接设置百分比
4. **持久化**：写入 `GameUserSettings.ini` 的 `[/Script/Engine.GameUserSettings]` 段，下次启动自动恢复
5. **自动初始化兜底**：`set_quality()` 中若 `_ini_path` 未设置，自动调用 `initialize()`

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `Content/Scripts/system/graphics_quality_manager.py` | 画质管理器（单例），核心逻辑 |
| `Content/Scripts/ui/graphics_settings_ui.py` | 画质设置 UI 控制器 |
| `Content/BluePrint/WBP_GraphicsSettings` | 画质设置 Widget 蓝图 |
| `Content/Scripts/ui/main_menu_ui.py` | 主菜单（添加画质设置按钮） |
| `Content/Scripts/system/game_mode.py` | GameMode（画质面板创建/销毁/返回） |
| `Content/Scripts/nepyinit.py` | 引擎初始化时创建 GQM 单例 |
| `Content/BluePrint/WBP_MainMenu` | 主菜单（添加画质设置按钮） |

---

## 运行效果

### 操作流程

1. 主菜单点击"画质设置"→ 弹出 WBP_GraphicsSettings 面板
2. 点击 Low / Med / High 按钮 → 即时切换画质
3. 当前选中档位显示 `[ xxx ]` 标记，txt_current 显示"当前画质: xxx"
4. 点击"返回"→ 回到主菜单
5. 画质设置持久化到 ini，下次启动自动恢复

### 各档位可观察差异

场景使用 Lightmass 烘焙光照，因此静态场景的间接光照不受 Scalability 档位影响。**Low/High 的差异主要体现在动态阴影、纹理清晰度、植被密度和抗锯齿上**：

| 可观察差异 | Low(0) | Med(1) | High(2) |
|-----------|--------|--------|---------|
| **动态阴影** | 关闭 | 中等（1级CSM，1024分辨率） | 高质量（4级CSM，2048分辨率，VSM） |
| **Lumen GI** | 关闭 | 关闭 | 开启（影响动态物体间接光照） |
| **Lumen 反射** | 关闭 | 关闭 | 开启 |
| **纹理清晰度** | 低（MipBias=1，Pool=400MB） | 中（MipBias=1，Pool=600MB） | 高（MipBias=0，Pool=800MB） |
| **植被密度** | 最疏（0.4） | 中（0.4） | 密（0.8） |
| **抗锯齿** | 最低 | FXAA Quality=1 | FXAA Quality=3 + TSR 高质量 |
| **视距** | 近（LOD Bias=1） | 中（LOD Bias=1） | 远（LOD Bias=0） |
| **后处理** | 最低 | 中 | 高 |
| **体积雾** | 关闭 | 关闭 | 开启 |

### 关于烘焙光照的说明

本场景使用 Lightmass 烘焙静态光照。烘焙光照存储在 Lightmap 中，不受 Scalability 档位影响，这是引擎的标准行为：

- **静态物体**（Static Mobility）→ 始终使用烘焙的 Lightmap，不随档位变化
- **动态物体**（Movable Mobility）→ 受 Lumen GI / 反射等档位设置影响

这意味着在暗部/遮挡区域，Low 和 High 的差异主要体现在动态物体（角色、敌人）上，场景建筑/地面的静态光照不受影响。

---

## NePy API 踩坑记录

| API | 可用性 | 备注 |
|-----|--------|------|
| `ue.ProjectDir()` | ❌ 不存在 | 用 `__file__` 推导替代 |
| `GameUserSettings.GetGameUserSettings()` | ✅ | 获取单例 |
| `GameUserSettings.LoadConfig()` | ❌ 不暴露 | — |
| `GameUserSettings.ApplySettings(True)` | ✅ | 但仅对已 SetXxx 的组生效 |
| `GameUserSettings.SetShadowQuality()` 等 | ⚠️ 部分 | 7 组有 setter，ResolutionQuality/PostProcessQuality/EffectsQuality 无 setter |
| `GameUserSettings.ResolutionQuality` 等属性 | ❌ 不暴露 | setattr 直接赋值报错 |
| `PlayerController.ConsoleCommand` | ❌ 不暴露 | — |
| `ue.SystemLibrary.ExecuteConsoleCommand` | ❌ 不存在 | — |
| `ue.KismetSystemLibrary.ExecuteConsoleCommand` | ✅ | 最终采用的方案，可执行所有 sg.XxxQuality 命令 |

### 方案演进

1. **方案 A**：`GameUserSettings.SetXxx()` + `ApplySettings()` → 3 组无 setter，无法设置
2. **方案 B**：方案 A + `PlayerController.ConsoleCommand` 补充缺失 3 组 → PC 无 ConsoleCommand
3. **方案 C（最终）**：全部 10 组统一用 `KismetSystemLibrary.ExecuteConsoleCommand` 执行 `sg.XxxQuality` 控制台命令，优先级一致，代码简洁
