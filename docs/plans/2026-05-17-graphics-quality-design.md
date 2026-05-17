# 性能分级模块设计文档

> 日期：2026-05-17
> 需求来源：P5 客户端要求第 15 条

## 1. 概述

为 TPS 游戏添加性能分级模块，用户可在主菜单手动选择 Low/Med/High 三档画质，切换后引擎 Scalability 参数立即生效，选择持久化到 `GameUserSettings.ini`。

零耦合方案：不修改任何现有游戏逻辑代码，仅通过 UE 引擎 Scalability API 控制全局画质。

## 2. 架构

```
WBP_MainMenu
  └─ btn_graphics_settings (OnClicked)
       └─ MainMenuPanel → callback → TPSGameMode
            └─ GraphicsSettingsPanel (Python UI 控制器)
                 └─ WBP_GraphicsSettings Widget
                      ├─ btn_low / btn_med / btn_high
                      │    └─ OnClicked → GraphicsQualityManager.set_quality(level)
                      └─ btn_back → 返回 MainMenu
```

核心类：
- `GraphicsQualityManager` — 单例，调引擎 Scalability API，3 档
- `GraphicsSettingsPanel` — UI 控制器，创建 Widget 绑定按钮

## 3. 三档 Scalability 参数映射

| Scalability 组 | Low (0) | Med (1) | High (2) | 说明 |
|---|---|---|---|---|
| ResolutionQuality | 0.7 | 0.9 | 1.0 | 渲染分辨率缩放 |
| ViewDistanceQuality | 0 | 1 | 2 | 视距/LOD 切换距离 |
| AntiAliasingQuality | 0 | 1 | 2 | 抗锯齿级别 |
| ShadowQuality | 0 | 1 | 2 | 阴影分辨率+级联数 |
| GlobalIlluminationQuality | 0 | 1 | 2 | Lumen/SSGI 质量 |
| ReflectionQuality | 0 | 1 | 2 | SSR/Lumen 反射 |
| PostProcessQuality | 0 | 1 | 2 | Bloom/DOF/色调映射 |
| TextureQuality | 0 | 1 | 2 | 贴图流送最大Mip |
| EffectsQuality | 0 | 1 | 2 | Niagara 粒子 LOD |
| FoliageQuality | 0 | 1 | 2 | 植被密度/距离 |

Low 档预期效果：分辨率降至 70%、关闭阴影/Lumen/SSR/后处理、特效降级、贴图降档。

## 4. UI 交互

WBP_GraphicsSettings 布局：
- 标题"画质设置"
- 三个 Button：Low / Med / High，选中高亮 `[ ]`
- 当前档位状态文本
- 返回按钮

流程：
1. WBP_MainMenu 点击画质设置按钮 → MainMenuPanel 回调通知 TPSGameMode
2. TPSGameMode 销毁 MainMenuPanel，创建 GraphicsSettingsPanel
3. 点档位按钮 → GraphicsQualityManager.set_quality(level)，画面即时变化
4. 点返回 → 销毁 GraphicsSettingsPanel，重新显示 MainMenuPanel

## 5. 文件清单

| 操作 | 文件 | 改动量 |
|---|---|---|
| 新增 | `Content/Scripts/system/graphics_quality_manager.py` | ~80 行 |
| 新增 | `Content/Scripts/ui/graphics_settings_ui.py` | ~100 行 |
| 新增 | `Content/BluePrint/WBP_GraphicsSettings` | 蓝图 |
| 修改 | `Content/Scripts/ui/main_menu_ui.py` | +~10 行 |
| 修改 | `Content/Scripts/system/game_mode.py` | +~10 行 |
| 修改 | `Content/Scripts/nepyinit.py` | +~2 行 |
| 修改 | `Content/BluePrint/WBP_MainMenu` | 加按钮 |

## 6. 后续扩展

当前为零耦合方案（方案 A），后续可无缝扩展为方案 C（混合方案）：
- 在 GraphicsQualityManager 加 `quality_tier` 全局枚举
- 游戏模块按需读取 `quality_tier` 做精细控制（如 Low 档关闭 MagicArrow 拖尾）
