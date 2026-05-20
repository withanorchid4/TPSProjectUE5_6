# TPS Demo — 游戏操作与实现说明

> 项目：网易2026初入江湖培训作业 — 第三人称射击游戏 Demo  
> 引擎：Unreal Engine 5.6 + NePy（Python 绑定插件）  
> 脚本：Python 3.12（游戏逻辑）+ 蓝图（动画/材质/Widget）

---

## 第一部分：操作说明

### 1.1 启动与登录

1. 使用 Epic Games Launcher 安装 UE 5.6.0，打开 `Newbie.uproject`
2. 启动服务端：运行 `server/main.py`（Python 3，需安装 protobuf）
3. 在 UE 编辑器中点击 Play，进入主菜单
4. 在登录界面输入账号密码（预置账号：`netease1`/`netease2`/`netease3`，密码均为 `123`），点击登录
5. 选择或创建角色后点击"开始游戏"，进入 Level1

### 1.2 按键操作

| 按键 | 功能 | 说明 |
|------|------|------|
| **W/S** | 前后移动 | 基于摄像机方向的8向移动 |
| **A/D** | 左右移动 | 同上 |
| **Space** | 跳跃 | 仅地面时生效 |
| **LeftShift** | 冲刺 | 按住时速度翻倍（600），射击/瞄准时不可冲刺 |
| **鼠标移动** | 视角旋转 | 控制摄像机朝向 |
| **鼠标左键** | 射击 | 按住连射，需持枪状态 |
| **鼠标右键** | 瞄准（ADS） | 摄像机拉近，移动降速，需持枪状态 |
| **C** | 切换射击模式 | 点射（0.15s间隔）/ 连射（0.1s间隔） |
| **E** | 切换持枪/收枪 | 收枪后不可射击和瞄准 |
| **R** | 手动换弹 | 2秒换弹动画，弹药打空时自动触发 |
| **Q** | 发射魔法箭 | 飞行轨迹 + 命中范围晕眩3秒，10秒CD |
| **F** | 自我增益Buff | 增加攻击力 +0.3/层，持续10秒 |

### 1.3 游戏流程

1. **Level1**：5个敌人（近战+远程混编），消灭所有敌人后自动进入 Level2
2. **Level2**：8个敌人（更多远程敌人），消灭后显示胜利结算界面
3. 玩家死亡则显示失败界面，可选择重试或返回主菜单

### 1.4 HUD 信息

| 位置 | 内容 |
|------|------|
| 屏幕中央 | 十字准星（持枪时） |
| 左下角 | 血条 + HP数值 |
| 血条上方 | Buff状态（ATK↑/ATK↓ + 层数 + 剩余时间） |
| 右下角 | 弹药数（当前/储备）+ 射击模式 + 魔法箭CD |
| 左上角 | 关卡编号 + 剩余敌人数 |
| 敌人头顶 | 伤害跳字（黄色浮动数字） |

### 1.5 道具拾取

敌人死亡后掉落道具，走近自动拾取：

| 道具 | 效果 | 概率 |
|------|------|------|
| 弹药箱 | +30 储备弹药 | 50% |
| 急救包 | +50 HP | 50% |

### 1.6 画质设置

主菜单 → "画质设置" → 选择 Low / Med / High 三档，即时生效，下次启动自动恢复。

---

## 第二部分：实现说明

### 2.1 架构概览

项目采用 **组件组合模式**：所有游戏逻辑由 Python 组件实现，蓝图仅用于动画、材质和 UI Widget。

```
ue.Character
  └── BaseCharacter (@ue.uclass, 组件组合)
        └── TPSCharacter (@ue.uclass, 主角色)
              ├── MovementComponent      移动/跳跃/冲刺
              ├── CameraComponent        TPS越肩摄像机/瞄准
              ├── ShootingComponent      HitScan射击/弹药/魔法箭
              ├── HealthComponent         血量管理
              ├── BuffComponent           Buff/Debuff管理
              ├── AudioManager            音效+粒子播放
              ├── DitherOcclusion         相机遮挡Dither效果
              ├── KeyboardInputHandler    UE InputComponent绑定
              └── NetworkManager(单例)    网络同步

ue.Character
  └── BaseEnemy (@ue.uclass, _is_enemy=True)
        ├── HealthComponent              血量/受伤/死亡
        ├── EnemyAIComponent             AI状态机
        ├── MeleeEnemy                   近战敌人(15伤害, 150范围)
        └── RangedEnemy                  远程敌人(10伤害子弹, 800范围)

ue.HUD
  └── CrosshairHUD (@ue.uclass)          准星+血条+弹药+Buff+伤害跳字

ue.Actor
  ├── TracerRound     弹道轨迹弹丸(纯视觉)
  ├── MagicArrow      魔法箭(晕眩投射物)
  ├── EnemyProjectile 远程敌人子弹
  └── PickupItem       掉落道具(弹药/血包)
```

**NePy 特殊约束**：NePy 子类化不支持 `ReceiveTick`（UE 优化：蓝图中无 Tick 节点则 C++ 层不注册 Ticker）。解决方案是使用 `TickableMixin` + `ue.AddTicker` 替代，见 `system/tickable.py`。

### 2.2 角色移动系统

**文件**：`character/movement.py`

- 基于 `AddMovementInput` + Controller Yaw 方向的8向移动
- W/S → `MoveForward`（Controller Yaw 前向向量），A/D → `MoveRight`（Controller Yaw 右向向量）
- 步行速度 300，冲刺速度 600（LeftShift 按住）
- 跳跃使用 `Character.Jump()`，仅在地面时生效（`IsFalling()` 判断）
- 射击时强制降速到步行（300），确保持枪步行动画生效

### 2.3 TPS 摄像机系统

**文件**：`character/camera.py` + 详细设计文档 `docs/tps_shooting_design.md`

**越肩摄像机**：

| 参数 | 值 | 说明 |
|------|----|------|
| TargetArmLength | 300 | 摄像机到角色距离 |
| SocketOffset Y | 50 | 右偏（越肩） |
| SocketOffset Z | 100 | 上偏（俯视感） |
| CameraLagSpeed | 6.0 | 摄像机跟随延迟（平滑感） |
| ProbeSize | 12.0 | 碰撞探测球 |

**瞄准模式（ADS）**：右键按住 → ArmLength 从 300→50，Y偏移 50→30，Z偏移 100→80；角色自动转向摄像机 Yaw；移动速度降至 300。

**俯仰角限制**：在输入层直接 Clamp ControlRotation 的 Pitch 到 [-80°, +80°]，避免万向锁和摄像机翻转。不用 PlayerCameraManager 的 ViewPitchMin/Max（在 SpringArm + CameraLag 组合下不可靠）。

### 2.4 射击系统（HitScan 双射线）

**文件**：`character/shooting.py` + 详细设计文档 `docs/tps_shooting_design.md`

#### 2.4.1 双射线检测（核心设计）

每次射击执行两次 LineTrace：

```
第一次（cam_trace）：  摄像机 ──→ 命中点P     ← 只提供瞄准方向
第二次（muzzle_trace）：枪口 ──→ P           ← 决定实际命中
```

**为什么需要双射线？** TPS 中摄像机在角色后上方，近距离敌人可能不在摄像机射线路径上但确实在准星和枪口之间（"盲区"问题）。用双射线可修正：cam_trace 确定瞄准方向，muzzle_trace 从枪口出发确定实际命中。

- 射线通道：`TraceTypeQuery2`（Camera 通道）
- 忽略自身：`Actors to Ignore = [self.owner]`
- 命中提取：`HitResult.Component (WeakPtr) → .Get() → Component → .GetOwner() → Actor`
- 敌人判定：`hasattr(actor, 'take_damage')`（NePy 的 isinstance 不可靠）

#### 2.4.2 弹药系统

- 弹夹容量 30，总弹药上限 90（3个弹夹）
- 换弹：2秒动画，从总弹药补充弹夹
- 弹药打空自动触发换弹
- 点射模式（0.15s间隔）/ 连射模式（0.1s间隔），C键切换

#### 2.4.3 弹道视觉

**文件**：`character/tracer_round.py`

TracerRound 是纯视觉弹丸：SceneComponent 做根（`bRotationFollowsVelocity` 控制朝向），Cylinder 子组件做弹道线（-90° pitch 沿 X 轴），速度 30000，0.2秒自动销毁。通过行程距离判断是否到达目标点后立即销毁。

### 2.5 魔法箭系统

**文件**：`character/magic_arrow.py`

- 投射物（ProjectileMovementComponent），速度 3000，无重力
- 冰霜拖尾 Niagara 特效（`NS_ArrowTrail_Magic`）
- 命中/Overlap 后：播放 AOE Niagara 特效 + 爆炸音效 + 晕眩半径 500 内敌人 3 秒
- CD 10 秒，HUD 显示倒计时
- 碰撞延迟 0.05 秒开启（避免出生时撞到玩家自身）
- 使用 `TickableMixin` 替代 `ReceiveTick`

**Shader 预热**：`BaseCharacter.ReceiveBeginPlay` 中 Spawn 一根 `_visual_only=True` 的魔法箭并立即销毁，强制 UE 编译 Cylinder+LightArrow 的 Shader 和触发纹理 Streaming，避免首帧黑箭问题。

### 2.6 敌人 AI 系统

**文件**：`system/enemy_ai_component.py` + `enemy/base_enemy.py` + `enemy/melee_enemy.py` + `enemy/ranged_enemy.py`

#### 2.6.1 AI 状态机

```
IDLE(巡逻) ──detect_range──→ CHASE ──attack_range──→ ATTACK
  ↑                            │                       │
  └── lose_range ──────────────┘                       │
  ↑                            │←── out of range ──────┘
  │                            │
  └──── stun end (距离>lose) ──┘
  ↓                            ↓
  STUNNED ←── 魔法箭命中 ─── (任何状态)
  DEAD    ←── 血量归零 ──── (任何状态)
```

| 状态 | 行为 |
|------|------|
| IDLE | 在出生点附近 NavMesh 巡逻（移动→等待→移动） |
| CHASE | `AddMovementInput` 直线追击玩家 |
| ATTACK | 每次冷却结束后执行攻击（近战/远程） |
| STUNNED | `GlobalAnimRateScale=0.0` 冻结动画，恢复时按距离判断：在 `lose_range` 内→CHASE，否则→IDLE |
| DEAD | 播放死亡 Montage → 70%进度时开始溶解 → 销毁+掉落道具 |

#### 2.6.2 两种敌人

| | 近战敌人 (MeleeEnemy) | 远程敌人 (RangedEnemy) |
|---|---|---|
| HP | 80 | 60 |
| 伤害 | 15（延迟0.5s到出拳帧扣血） | 10（EnemyProjectile） |
| detect_range | 800 | 1500 |
| attack_range | 150 | 800 |
| attack_cooldown | 1.5s | 2.0s |
| move_speed | 300 | 200 |
| 武器 | 无（空手动画） | SM_AR4（持枪动画） |

**近战攻击**：播放 ComboAttack Montage，延迟 0.5s 到出拳帧时检测玩家距离并扣血（避免动画还没出拳就扣血）。

**远程攻击**：在身体前方 80cm 生成 EnemyProjectile，速度 1500，SphereCollision 检测 Overlap 碰撞玩家。

#### 2.6.3 平滑旋转

敌人不使用 `bOrientRotationToMovement`（因为 `AddMovementInput` 不触发该属性），而是手动实现：`_face_target()` 设置 `_target_yaw`，`ReceiveTick` 中用 `rotation_speed=15` 做插值旋转。

#### 2.6.4 巡逻逻辑

IDLE 状态下在出生点 `patrol_radius=500` 范围内的 NavMesh 上取随机可达点，`AddMovementInput` 直线走向目标。到达后等待 `patrol_wait_time=2.5` 秒，再取下一个点。任何时刻检测到玩家进入 `detect_range` 立即切换到 CHASE。

### 2.7 血量系统

**文件**：`system/health_component.py`

- 玩家/敌人共用，`max_hp` 可配置
- `take_damage()` 扣血，`heal()` 回血
- 回调机制：`on_damage(amount, attacker)` / `on_death()`
- 受伤回调推送 `bIsHit` 脉冲到 AnimBP + 触发伤害跳字
- 死亡回调播放死亡 Montage + 溶解效果 + 掉落道具

### 2.8 Buff 系统

**文件**：`system/buff_component.py`

| Buff类型 | 倍率 | 持续时间 | 触发方式 |
|----------|------|----------|----------|
| attack_up | +0.3/层 | 10秒 | F键（自我增益） |
| attack_down | -0.2/层 | 8秒 | 敌人攻击时自动附加 |

**规则**：
- 所有 Buff 合计最多 3 层，满了替换最早的
- 同类 Buff 添加间隔 2 秒（`ADD_INTERVAL`）
- `get_attack_multiplier()` 计算最终攻击倍率（下限 0.1）

**视觉表现**：
- 角色身体 OverlayMaterial 发光：ATK↑ 金色 / ATK↓ 红色，强度与层数正比
- 剩余 ≤3 秒时闪烁（每 0.1s 切换亮/灭）
- HUD 显示 ATK↑/ATK↓ + 层数 + 倒计时
- 受伤时屏幕泛红后处理（PostProcessVolume + M_damageOverlay，0.5秒淡出）

### 2.9 道具掉落与拾取

**文件**：`pickup/pickup_item.py`

- 敌人死亡时 50% 掉落弹药箱（+30 储备弹药）、50% 急救包（+50 HP）
- SphereCollision（半径 80）+ OverlapAllDynamic 检测玩家碰触
- RotatingMovementComponent 自动旋转（90°/s），模型原点偏移补偿避免公转
- SetLifeSpan 15秒后自动消失
- 网络同步：主机击杀时决定道具类型，通过 `ENEMY_KILLED` 事件同步给非主机

### 2.10 HUD 系统

**文件**：`system/crosshair_hud.py`

继承 `ue.HUD`，`ReceiveDrawHUD` 每帧绘制：

| 元素 | 实现方式 |
|------|----------|
| 十字准星 | DrawLine（4条线段，绿色，持枪时显示） |
| 血条 | DrawRect + DrawText（左下角，低血量变红） |
| 弹药 | DrawText（右下角，仅持枪时） |
| Buff状态 | DrawText（ATK↑/ATK↓ + 层数 + 倒计时） |
| 射击模式 | DrawText（AUTO/SEMI） |
| 换弹提示 | DrawText（RELOADING...） |
| 魔法箭CD | DrawText（MAGIC READY / MAGIC X.Xs） |
| 伤害跳字 | 世界坐标→Project→屏幕坐标，1秒上浮+淡出 |
| 关卡信息 | DrawText（左上角 LEVEL + Enemies） |

### 2.11 动画系统

**动画蓝图**：ABP_Rifle，状态机 `GroundLocomotion` → `Slot(DefaultSlot)` → `Output Pose`

**Python → AnimBP 变量推送**：

| 变量 | 类型 | 说明 |
|------|------|------|
| bSwitchWeapon | bool | E键触发，仅1帧True后重置 |
| SwitchWeaponSpeed | float | 持枪→收枪=-1，收枪→持枪=1 |
| bHasWeapon | bool | 当前是否持枪 |
| bIsAiming | bool | 右键瞄准状态 |
| bIsHit | bool | 受击脉冲（延迟一帧还原） |
| bIsReloading | bool | 换弹脉冲（延迟一帧还原） |

**脉冲机制**：`bIsHit`/`bIsReloading` 必须延迟一帧还原。因为 AnimBP 在 Python 赋值后下一帧才读取变量，如果在同一帧内设 True 再设 False，AnimBP 就读不到 True。

**死亡动画**：Montage 播放，播到 70% 时开始溶解销毁（避开末尾 blend-out 过渡回 idle）。

**溶解效果**：`M_Dissolve` 材质 + `CreateDynamicMaterialInstance`，`DissolveAmount` 从 0→1 渐变，2秒完成。

### 2.12 Dither 遮挡效果

**文件**：`character/dither_occlusion.py`

当相机与角色之间有障碍物时，将障碍物材质替换为半透明 Dither 版本，让玩家能看到被遮挡的角色。

**实现**：
1. 每帧从相机向角色头部（+160Z）和腰部（+90Z）发射 Visibility 通道射线
2. 使用迭代 `LineTraceSingle` 穿透检测：每次命中一个遮挡物后将其加入 ignore 列表，从命中点稍微偏移继续 trace，最多穿透 10 个遮挡物
3. 命中的遮挡物：查 `DITHER_MAT_MAP` 映射表，找到原始材质对应的 Dither 版本
4. 替换材质为 `CreateDynamicMaterialInstance`，设置 `FadeOpacity=0.2`
5. 不再被遮挡的物体自动恢复原始材质

**Dither 材质**：Blend Mode 改为 Masked，添加 `FadeOpacity` 参数 + `DitherTemporalAA` 函数 → Opacity Mask。批量转换脚本见 `Scripts/batch_convert_dither.py`，映射表见 `docs/dither_material_mapping.md`（30+ 材质）。

### 2.13 音效与粒子系统

**文件**：`system/audio_manager.py`

| 事件 | 音效 | 粒子 | 音量 |
|------|------|------|------|
| 射击 | Explosion02 | P_Explosion(0.2x) | 0.6 |
| 命中敌人 | Explosion_Cue | P_Explosion(0.3x) | 0.7 |
| 命中表面 | Explosion02(0.3) | P_Explosion(0.15x) | 0.3 |
| 魔法箭飞行 | Light02_Cue | — | 0.8 |
| 魔法箭爆炸 | Explosion02 | — | 0.7 |
| 敌人死亡 | Explosion01 | P_Explosion(0.5x) | 0.8 |
| 敌人攻击 | Collapse_Cue | — | 0.5 |
| 背景音乐 | Starter_Music_Cue | — | 0.3 |

所有 3D 音效用 `PlaySoundAtLocation`，BGM 用 `PlaySound2D`。资源加载后缓存避免重复 LoadObject。

### 2.14 性能分级模块

**文件**：`system/graphics_quality_manager.py` + `ui/graphics_settings_ui.py` + 详细文档 `docs/graphics-quality.md`

**零耦合设计**：纯引擎 Scalability API，不依赖其他游戏模块。

| Scalability 组 | Low(0) | Med(1) | High(2) |
|---|---|---|---|
| ResolutionQuality | 70% | 90% | 100% |
| ShadowQuality | 0 | 1 | 2 |
| GlobalIlluminationQuality | 0 | 1 | 2 |
| ReflectionQuality | 0 | 1 | 2 |
| PostProcessQuality | 0 | 1 | 2 |
| TextureQuality | 0 | 1 | 2 |
| EffectsQuality | 0 | 1 | 2 |
| FoliageQuality | 0 | 1 | 2 |
| AntiAliasingQuality | 0 | 1 | 2 |
| ViewDistanceQuality | 0 | 1 | 2 |

**实现**：通过 `KismetSystemLibrary.ExecuteConsoleCommand` 执行 `sg.XxxQuality` 控制台命令即时生效（所有组统一 `SetByConsole` 优先级），同时写入 `GameUserSettings.ini` 持久化。

**可观察差异**：Low 关闭动态阴影和 Lumen GI/反射；High 开启 4级 CSM + VSM + Lumen 全功能。静态场景因使用 Lightmass 烘焙光照，不受 Scalability 影响。

### 2.15 材质特效

| 材质 | 用途 | 实现 |
|------|------|------|
| M_Dissolve | 敌人死亡溶解 | DissolveAmount 0→1 渐变，2秒 |
| LightArrow | 魔法箭自发光 | Emissive 材质，Cylinder 网格 |
| M_BuffGlow | Buff 发光效果 | OverlayMaterial，GlowColor + GlowIntensity 参数 |
| M_damageOverlay | 受伤屏幕泛红 | PostProcessVolume + DamageIntensity 参数，0.5秒淡出 |
| Dither材质(x30+) | 遮挡半透明 | BlendMode=Masked + FadeOpacity + DitherTemporalAA |

### 2.16 关卡与游戏模式

**文件**：`system/game_mode.py`

**TPSGameMode** 管理关卡流程：

1. **MainMenu**：显示登录 UI → 登录成功后显示主菜单 → 选角色进游戏
2. **Level1**（5敌人）：全部击杀 → `OpenLevel("Level2")`
3. **Level2**（8敌人）：全部击杀 → 显示胜利结算 Widget
4. 玩家死亡 → 显示失败结算 Widget

**结算界面**（`WBP_GameResult`）：显示胜利/失败，可重试当前关卡或返回主菜单。

**延迟创建 Widget**：使用 `_pending_result_widget` 标记，在玩家 Tick 中创建 Widget，避免在 AI 回调中创建导致时序问题。

### 2.17 网络同步

**文件**：`network/network_manager.py` + `server/`

#### 2.17.1 服务端

- TCP 服务器，Python 3 标准库 + protobuf
- 预置账号：netease1/2/3，密码 123
- 支持多客户端同时接入
- 游戏物体管理：角色、敌人状态同步
- 断线重连：客户端重连后传送到服务端记录的位置

#### 2.17.2 客户端网络

**NetworkManager**（单例）封装 NetClient，状态机：

```
DISCONNECTED → CONNECTING → LOGGING_IN → SELECTING_CHAR → IN_GAME
```

**同步内容**：

| 同步项 | 频率 | 方向 |
|--------|------|------|
| 移动位置/旋转 | ~60fps | 客户端→服务端 |
| 射击事件 | 即时 | 客户端→服务端→广播 |
| 换弹/瞄准动作 | 即时 | 客户端→服务端→广播 |
| 魔法箭命中 | 即时 | 客户端→服务端→广播 |
| 敌人状态 | ~60fps（主机） | 主机→服务端→非主机 |
| 敌人伤害/击杀/晕眩 | 即时 | 主机→服务端→非主机 |
| 远程玩家位置/动画 | ~60fps | 服务端→各客户端 |

**主机-非主机架构**：
- 先进入游戏的客户端为主机（`is_host=True`），负责驱动本地 AI + 上报敌人状态
- 后进入的客户端为非主机，敌人由网络驱动（`_is_network_driven=True`），禁用本地 AI
- 敌人事件（伤害/击杀/晕眩）：只有主机发起，非主机收网络广播后在本地执行（`from_network=True` 避免二次广播）
- 道具类型由击杀者决定并通过 `ENEMY_KILLED` 事件同步

**远程玩家**：`RemotePlayer` Actor 在非本机客户端上代表其他玩家，通过 `apply_network_state()` 更新位置/动画。

### 2.18 输入系统

**文件**：`input_config.py` + `input_handlers/keyboard_handler.py`

- `InputConfig.setup()` 在 `on_post_engine_init` 中调用，动态添加所有 Axis/Action Mappings
- 无需在编辑器中手动配置项目设置的 Input
- `KeyboardInputHandler` 通过 `InputComponent.BindAxis/BindAction` 绑定所有按键
- Tick 中调用 `shooting.tick()` 处理连发射击和换弹计时

### 2.19 NePy 关键踩坑记录

| # | 问题 | 解决方案 |
|---|------|----------|
| 1 | `ReceiveTick` 不被调用 | 使用 `TickableMixin` + `ue.AddTicker` |
| 2 | `__init_pyobj__` 不保证被蓝图子类调用 | 变量初始化放在 `ReceiveBeginPlay` |
| 3 | `@ue.uproperty()` 导致 Cast 失败 | 不使用 `@ue.uproperty()` |
| 4 | AnimBP 变量赋值 | 直接 `anim.var = value`，不用 `set_editor_property` |
| 5 | 资产加载 | `ue.LoadObject(类, "路径.资产名")`，不是 `LoadAsset` |
| 6 | 组件附加 | `AttachToComponent` 6个参数（parent, socket, 3xRule, bWeld） |
| 7 | SetRootComponent 重置 Transform | 保存 spawn_loc/spawn_rot 后恢复 |
| 8 | SetActorLocation 3参数 | `SetActorLocation(loc, False, False)` |
| 9 | Vector 取反报错 | 用 `v * -1.0` 代替 `-v` |
| 10 | HitResult.Component 是 WeakPtr | 需 `.Get()` 解引用再 `.GetOwner()` |
| 11 | GameUserSettings 部分 setter 缺失 | 统一用 `ExecuteConsoleCommand` 执行 `sg.XxxQuality` |
| 12 | 魔法箭首帧黑箭 | Spawn 预热箭（`_visual_only=True`）强制 Shader 编译 |

### 2.20 文件清单

| 目录 | 文件 | 说明 |
|------|------|------|
| `Content/Scripts/character/` | `base_character.py` | 角色基类（组件组合） |
| | `movement.py` | 移动组件 |
| | `camera.py` | TPS 摄像机组件 |
| | `shooting.py` | 射击组件（双射线 + 弹药） |
| | `magic_arrow.py` | 魔法箭 Actor |
| | `tracer_round.py` | 弹道轨迹弹丸 |
| | `dither_occlusion.py` | Dither 遮挡检测 |
| | `input_handler.py` | 输入处理器抽象基类 |
| `Content/Scripts/enemy/` | `base_enemy.py` | 敌人基类 |
| | `melee_enemy.py` | 近战敌人 |
| | `ranged_enemy.py` | 远程敌人 |
| | `enemy_projectile.py` | 远程敌人子弹 |
| `Content/Scripts/pickup/` | `pickup_item.py` | 掉落道具 |
| `Content/Scripts/system/` | `health_component.py` | 血量组件 |
| | `enemy_ai_component.py` | AI 状态机 |
| | `buff_component.py` | Buff 管理 |
| | `audio_manager.py` | 音效+粒子管理 |
| | `crosshair_hud.py` | HUD 绘制 |
| | `game_mode.py` | 关卡游戏模式 |
| | `graphics_quality_manager.py` | 画质管理器（单例） |
| | `tickable.py` | TickableMixin |
| `Content/Scripts/input_handlers/` | `keyboard_handler.py` | 键盘输入绑定 |
| `Content/Scripts/ui/` | `login_ui.py` | 登录界面控制器 |
| | `main_menu_ui.py` | 主菜单控制器 |
| | `graphics_settings_ui.py` | 画质设置界面 |
| `Content/Scripts/network/` | `network_manager.py` | 网络管理器（单例） |
| | `net_client.py` | TCP 客户端 |
| | `proto/tps_pb2.py` | Protobuf 协议 |
| `Content/Scripts/` | `tps_character.py` | TPS 主角色 |
| | `input_config.py` | 动态输入映射 |
| | `nepyinit.py` | NePy 初始化入口 |
| `Scripts/` | `batch_convert_dither.py` | 批量 Dither 材质转换 |
| | `convert_to_dither_material.py` | 单材质 Dither 转换 |
| `server/` | `main.py` | 服务端入口 |
| | `game_server.py` | 游戏服务器逻辑 |
| | `game_world.py` | 游戏世界状态 |
| | `client_session.py` | 客户端会话 |
| | `msg_handler.py` | 消息处理 |
| | `db.py` | 数据库（sqlite3） |

### 2.21 第三方库与插件

| 名称 | 用途 | 来源 |
|------|------|------|
| NePy (NePythonBinding) | UE5.6 Python 绑定 | 内部插件（Sunshine下载） |
| protobuf | 网络通信序列化 | Google Protocol Buffers |
| Starter Content | 音效/粒子/基础资源 | UE 引擎自带 |
| Mannequin 动画包 | 角色/敌人动画 | UE 引擎自带 |
| SM_AR4 | 武器模型 | Weapons 资源包 |
| LowerSector_Mod | 场景建筑模型 | Marketplace 免费资源 |
| supply_crates | 弹药箱/急救包模型 | Vicevoxel FBX 包 |
| NS_ArrowTrail_Magic | 魔法箭拖尾特效 | ArrowTrail 特效包 |
| Variant_Combat | 近战攻击动画 | 动画资源包 |
