# TPS Demo — Agent 上下文文件

> **新会话开始时读此文件即可恢复完整上下文**
> 项目路径：`C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\nepy_mini_NoSC\nepy_mini\Newbie\`

---

## 一、项目概述

网易2026初入江湖培训作业 — TPS 第三人称射击游戏 demo，使用 **UE 5.6 + NePy 插件**（Python 绑定）开发。游戏逻辑全部用 Python 实现，只有动画蓝图、材质、Widget 用蓝图。

**整体目标文档**：`C:\Users\zilong.luo\Desktop\netease\2026初入江湖-1培训—程序（新人版） 20251226.xlsx` — 其中的 **P5** 是完整作业要求和评分标准。
**作业任务拆解**：`C:\Users\zilong.luo\Desktop\netease\docs\plan\homework_plan.md` — 从 Excel 提取的37项必修+扩展任务清单。

---

## 二、技术栈

- **引擎**: Unreal Engine 5.6
- **脚本**: Python 3.12 + NePy（UE5.6 Python 绑定插件）
- **角色骨骼**: SKM_Quinn_Simple（UE5 标准骨骼，女性）
- **敌人骨骼**: SKM_Manny_Simple（复用 Mannequin，男性）
- **动画资源**: 引擎自带 Mannequin 动画包（Rifle/Pistol/Unarmed）
- **武器模型**: SM_AR4（来自导入的 Weapons 资源包，UE4.27 资产直接复制可用）
- **道具模型**: VV_ammobox_001（弹药箱）、VV_aidbox_001（急救包），来自 supply_crates-Vicevoxel-FBX 包
- **音效资源**: Starter Content 音效包（Fire01_Cue/Explosion_Cue/Light02_Cue/Collapse_Cue/Starter_Music_Cue 等）
- **粒子资源**: Starter Content 粒子包（P_Explosion/P_Sparks/P_Fire 等）

---

## 三、文件结构

```
Content/Scripts/
├── character/
│   ├── __init__.py
│   ├── base_character.py    # 角色基类 @ue.uclass()
│   ├── movement.py           # 移动组件
│   ├── camera.py             # 摄像机组件
│   ├── shooting.py           # 射击组件（HitScan射线+弹药+add_ammo）
│   ├── input_handler.py     # 输入处理器抽象基类
│   ├── bullet.py             # 子弹 Actor（旧Projectile方案，保留未删）
│   ├── hitscan_bullet.py     # 高速隐形子弹 Actor（旧方案，保留未删）
│   ├── tracer_round.py       # 弹道轨迹弹丸（纯视觉，SceneComponent根+Cylinder子组件+ProjectileMovement）
│   └── magic_arrow.py        # 魔法箭 Actor（晕眩，Projectile）
├── enemy/
│   ├── __init__.py
│   ├── base_enemy.py         # 敌人基类（死亡Montage+道具掉落+伤害跳字+_is_enemy标记）
│   ├── melee_enemy.py        # 近战敌人
│   ├── ranged_enemy.py       # 远程敌人
│   └── enemy_projectile.py   # 远程敌人子弹
├── pickup/
│   ├── __init__.py
│   └── pickup_item.py        # 掉落道具（弹药箱/急救包）
├── system/
│   ├── __init__.py
│   ├── health_component.py   # 血量组件
│   ├── enemy_ai_component.py # AI状态机组件
│   ├── buff_component.py    # Buff管理组件
│   ├── audio_manager.py     # 音效+粒子管理器
│   └── crosshair_hud.py      # HUD @ue.uclass(ue.HUD)
├── input_handlers/
│   ├── __init__.py
│   └── keyboard_handler.py   # 键盘/鼠标输入处理
├── input_config.py           # 动态输入映射
├── tps_character.py          # TPS 主角色类
└── nepyinit.py               # NePy 初始化入口

Content/BluePrint/
├── TPSCharacterBP.uasset     # TPS角色蓝图
├── TPSGameMode.uasset        # GameMode蓝图（当前空GameModeBase子类）
├── EnemyBPs/
│   ├── BaseEnemyBP.uasset
│   ├── MeleeEnemyBP.uasset
│   └── RangedEnemyBP.uasset
└── Tools/
    └── PickupItemBP.uasset

Config/DefaultEngine.ini 关键配置：
  GameDefaultMap=/Game/NewMap.NewMap
  GlobalDefaultGameMode=/Game/BluePrint/TPSGameMode.TPSGameMode_C
  GameInstanceClass=/Game/Mygameinstance.Mygameinstance_C
```

---

## 四、类继承/组合关系

```
ue.Character
  └── BaseCharacter (@ue.uclass, 组件组合模式)
        └── TPSCharacter (@ue.uclass, 主角色)
              ├── MovementComponent    — 移动/跳跃/冲刺
              ├── CameraComponent     — 摄像机/瞄准（收枪禁镜）
              ├── ShootingComponent   — HitScan射击+弹药系统+add_ammo
              ├── HealthComponent     — 玩家血量（heal方法）
              ├── BuffComponent       — Buff管理（纯管理，触发解耦）
              ├── AudioManager        — 音效+粒子播放（纯播放，触发解耦）
              └── KeyboardInputHandler — UE InputComponent 绑定

ue.Character
  └── BaseEnemy (@ue.uclass, 组件组合模式, _is_enemy=True)
        ├── HealthComponent     — 血量/受伤/死亡回调
        ├── EnemyAIComponent    — 状态机(IDLE→CHASE→ATTACK→STUNNED→DEAD)
        ├── 武器网格(SM_AR4)    — 默认持枪 + bHasWeapon=True
        ├── MeleeEnemy  — 近战敌人(15伤害, attack_range=150)
        └── RangedEnemy — 远程敌人(10伤害子弹, attack_range=800)

ue.HUD
  └── CrosshairHUD (@ue.uclass) — 准星+血条+弹药(仅持枪)+Buff状态+伤害飘字

ue.Actor
  ├── Bullet          — [旧] 玩家子弹(SphereCollision+Projectile)
  ├── HitscanBullet   — [旧] 高速隐形子弹(SphereCollision+Projectile)
  ├── TracerRound     — 弹道轨迹弹丸(SceneComponent根+Cylinder子组件-90°pitch+ProjectileMovement)
  ├── EnemyProjectile — 远程敌人子弹(SphereCollision+Projectile, attacker=owner)
  ├── MagicArrow      — 魔法箭(晕眩范围内敌人3秒, Projectile)
  └── PickupItem      — 掉落道具(50%弹药箱+30弹药/50%急救包+50HP, RotatingMovement旋转, SetLifeSpan超时)
```

---

## 五、按键映射

| 按键 | 动作 |
|------|------|
| W/S | MoveForward (±1) |
| A/D | MoveRight (±1) |
| Space | Jump |
| LeftShift | Sprint (冲刺) |
| C | ToggleFireMode (点射/连射) |
| E | SwitchWeapon (持枪/收枪) |
| Q | MagicArrow (魔法箭晕眩) |
| R | Reload (换弹) |
| F | SelfBuff (增攻Buff) |
| MouseX/Y | Turn/LookUp |
| LeftMouseButton | Fire |
| RightMouseButton | Aim (收枪时无效) |

---

## 六、动画系统

### ABP_Rifle 动画蓝图
- **Event Graph**: 计算 velocity/Direction
- **AnimGraph**: GroundLocomotion 状态机 → Slot(DefaultSlot) → Output Pose
- **功能状态机**: 包含受击状态(MM_HitReact_Back_Med_01，Full Body非Additive)

### AnimBP 变量（Python推送）
| 变量 | 类型 | 说明 |
|------|------|------|
| bSwitchWeapon | bool | E键触发，仅保持1帧True后重置 |
| SwitchWeaponSpeed | float | 持枪→收枪=-1，收枪→持枪=1 |
| bHasWeapon | bool | 下一帧更新，当前是否持枪 |
| bIsAiming | bool | 右键瞄准状态 |
| bIsHit | bool | 受击脉冲，延迟一帧还原 |
| bIsReloading | bool | 换弹脉冲，延迟一帧还原 |

### 动画命名
- **MF** = In-Place（原地动画），用于 BlendSpace 驱动移动
- **MM** = Root Motion（根运动），用于 Montage 播放（射击/换弹/死亡等）

### 延迟一帧还原机制
bIsHit/bIsReloading 脉冲模式：帧1设True，帧2检测 `_pending_xxx_reset` 还原为False。

### 死亡动画
- Montage 方式播放，路径：`/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_03_Montage`
- 播到70%时销毁，避免blend-out过渡回idle

---

## 七、NePy 技术决策（踩坑记录）

1. **`@ue.uclass()` 必须加**，用 `__init_pyobj__` 代替 `__init__`，类必须在 `on_init` 中导入
2. **`__init_pyobj__` 不保证被蓝图子类调用**：实例变量初始化应在 `ReceiveBeginPlay`
3. **`@ue.uproperty()` 会破坏类注册**：导致 Cast 失败，不要用
4. **AnimBP 变量赋值**：`set_editor_property` 运行时不可用；直接属性赋值 `anim.var = value` 可用
5. **资产加载**：`ue.LoadObject(类, "路径。资产名")`，不是 `ue.LoadAsset()`
6. **组件附加**：`AttachToComponent` 6个参数（parent, socket_name, LocationRule, RotationRule, ScaleRule, bWeld）
7. **SetRootComponent 重置Transform**：必须保存 spawn_loc/spawn_rot 后恢复
8. **SetActorLocation 3参数**：`SetActorLocation(loc, False, False)`
9. **NePy Vector 不支持取反**：`-right` 报错，用 `right * -1.0`
10. **bIsHit/bIsReloading 脉冲**：必须延迟一帧还原，否则 AnimBP 读不到 True
11. **受击动画用 Full Body 非 Additive**：Additive 需 Base Pose 易坍缩
12. **敌人平滑旋转**：`_face_target()` 设 `_target_yaw`，Tick 插值(rotation_speed=15)
13. **敌人晕眩**：`mesh.GlobalAnimRateScale = 0.0` 冻结动画，恢复时设回 1.0
14. **EnemyProjectile 必须忽略 owner**：`IgnoreActorWhenMoving(owner)` + overlap 跳过 owner
15. **shooting.tick() 必须每帧调用**：否则换弹计时器不倒数，卡死射击
16. **GetComponentRotation 不跟踪动画骨骼旋转**：返回静态变换，不含动画帧
17. **射击方向**：业界标准 = LineTrace 准星对齐 — 摄像机射线找命中点，子弹从枪口飞向命中点
18. **LineTraceSingle**：8必选+3可选=11参数，返回(bool, HitResult)元组；DrawDebugType 用整数0
19. **LinearColor**：`ue.LinearColor(1.0, 0.0, 0.0, 1.0)` float参数构造
20. **EDrawDebugTrace**：不支持 `None_` 属性，用整数 `0`
21. **死亡动画用 Montage**：从任何状态可触发，播完停最后一帧
22. **死亡后 Tick 直接 return**：不再执行 AI/旋转，只做销毁倒计时
23. **MM动画需先创建 Montage**：AnimSequence 需右键→Create AnimMontage 生成 _Montage 资产
24. **弹药系统**：total_ammo=90, current_ammo=30，换弹从总弹药补充
25. **收枪禁射/禁镜**：can_shoot() 检查 `_is_weapon_drawn`；set_aiming() 也检查
26. **Montage必须通过Slot节点**：连线：状态机→Slot(DefaultSlot)→Output Pose
27. **BP Event Tick 干扰 Python ReceiveTick**：删除BP中Event Tick节点，让Python直接覆盖C++函数
28. **BP修改后需保存编译**：蓝图改了不保存/编译则运行时不生效
29. **SetActorRotation 对部分 Actor 不生效**：PickupItem 用 RotatingMovementComponent 替代
30. **RotatingMovementComponent 公转问题**：模型pivot偏移导致，用 BoundingBox 中心偏移补偿
31. **HUD DrawRect 参数顺序**：`DrawRect(Color, X, Y, W, H)` 颜色在前
32. **SetLifeSpan 替代 Tick 超时**：引擎内部倒计时销毁，不依赖Tick
33. **FBX导入UE**：需手动拖入Content Browser，UE生成.uasset
34. **HitResult.Component 是 WeakPtr**：需 `.Get()` 解引用拿 Component，再 `.GetOwner()` 拿 Actor
35. **TraceTypeQuery1=Visibility, TraceTypeQuery2=Camera**：射击用 Camera 通道
36. **Actor 和 RootComponent 旋转是同一个东西**：Actor没有独立Transform，只是RootComponent的快捷访问器
37. **RootComponent的RelativeRotation = ActorRotation**：无法叠加局部旋转，需要子组件才能保留mesh局部偏移
38. **SceneComponent做根+Mesh做子组件**：bRotationFollowsVelocity控制根朝向，mesh的-90°相对旋转不被覆盖

---

## 八、作业完成状态

### ✅ 已完成（任务编号对应 homework_plan.md）

| # | 任务 | 说明 |
|---|------|------|
| 1 | 场景搭建 | NewMap 关卡（需扩展为 Level1/Level2） |
| 2 | WASD移动 | 8向移动 |
| 3 | 空格跳跃 | |
| 4 | 鼠标左键射击 | |
| 5 | TPS摄像机 | 越肩摄像机 |
| 6 | 枪械射击 | HitScan LineTrace |
| 7 | 点射/连射切换 | C键 |
| 8 | 魔法箭晕眩 | Q键，有轨迹+CD+范围晕眩3秒 |
| 9 | 弹夹设定 | 30发弹夹/90总弹药 |
| 10 | 换弹动作 | R键+弹药打空自动换弹，2秒 |
| 11 | 可被攻击的敌人 | BaseEnemy + 蓝图 |
| 12 | 攻击敌人击杀消失 | 死亡Montage→70%销毁 |
| 13 | 两种敌人 | 近战MeleeEnemy+远程RangedEnemy |
| 14 | 敌人AI | Python状态机(IDLE/CHASE/ATTACK/STUNNED/DEAD) |
| 18 | 增攻Buff | F键，+0.3/层，10秒 |
| 19 | 敌人减攻debuff | -0.2/层，8秒 |
| 20 | Buff最多3层 | 满替换最早 |
| 21 | Buff添加间隔 | 2秒 |
| 22 | Buff表现 | GUI ATK↑/ATK↓ + 层数 + 倒计时 |
| 23 | 击杀掉落道具 | 50%弹药箱+30弹药/50%急救包+50HP |
| 24 | 拾取道具 | 走近自动拾取 |
| 25 | 血条显示 | 左下角 DrawRect |
| 26 | 弹药数量显示 | 右下角，仅持枪时 |
| 27 | 伤害跳字 | 敌头顶浮动黄色数字 |
| 28 | 背景音乐 | Starter_Music_Cue，0.3音量 |
| 29 | 角色受击音效 | 通过AudioManager |
| 30 | 角色攻击音效 | 枪声+枪口火花 |
| 31 | 敌人受击音效 | 命中音效+爆炸粒子 |
| 32 | 敌人攻击音效 | Collapse_Cue |
| 33 | 粒子特效 | P_Explosion 等 |

### ❌ 未完成

| # | 任务 | 说明 |
|---|------|------|
| 15 | 关卡设计 | 需两类关卡 |
| 16 | 两类关卡场景区别 | |
| 17 | 关卡切换 | 杀完敌人→下一关 |
| 34 | 性能分级模块 | 思考分级判定+对高开销模块分级 |
| 35 | 特殊材质效果 | 编写特殊材质 |
| 36 | 渲染特性提升画面 | 光照/后处理等 |
| 37 | Unreal Insights 性能分析 | CPU/GPU/内存分析 |

### 📝 设计/计划已就绪

- **关卡系统**：设计文档 `docs/plans/2026-04-19-level-system-design.md`，实现计划 `docs/plans/2026-04-19-level-system-impl.md`
- 包含：主菜单UMG Widget → Level1(5敌人) → Level2(8敌人) → 胜利，TPSGameMode Python类管理

---

## 九、编辑器配置要点

- **蓝图列表**：TPSCharacterBP, TPSGameMode, BaseEnemyBP, MeleeEnemyBP, RangedEnemyBP, PickupItemBP
- **碰撞通道**：射击用 TraceTypeQuery2（Camera通道）
- **敌人类标记**：`_is_enemy = True`，用于减攻debuff判断
- **AnimBP Slot**：GroundLocomotion → Slot(DefaultSlot) → Output Pose
- **NavMeshBoundsVolume**：需放置到关卡中（当前AI用AddMovementInput直线追击）
- **DefaultEngine.ini**：
  - `GameDefaultMap=/Game/NewMap.NewMap`
  - `GlobalDefaultGameMode=/Game/BluePrint/TPSGameMode.TPSGameMode_C`
  - `GameInstanceClass=/Game/Mygameinstance.Mygameinstance_C`

---

## 十、Git 仓库

- **Remote**: `https://github.com/withanorchid4/TPSProjectUE5_6.git`
- **Branch**: master
- **最近提交**: `f41bd8e HitScan 射击重构 + 音效系统 + 小修复`

---

## 十一、服务端作业（未开始）

作业还要求完成服务端，但客户端专精版只需基础功能：
- Python 3 标准库 + protobuf
- TCP 服务器，多客户端接入
- 内建账号 netease1/2/3，密码 123
- 移动/技能/动作同步
- 详细要求见 `C:\Users\zilong.luo\Desktop\netease\docs\plan\homework_plan.md`