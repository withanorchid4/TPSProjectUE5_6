# TPS Demo — 游戏操作与作业要求回复

> 项目：网易2026初入江湖培训作业 — 第三人称射击游戏 Demo  
> 引擎：Unreal Engine 5.6 + NePy（Python 绑定插件）  
> 脚本：Python 3.12（游戏逻辑）+ 蓝图（动画/材质/Widget）  
> 入口关卡：MainMenu

---

## 第一部分：操作说明

### 启动与登录

1. 使用 Epic Games Launcher 安装 UE 5.6.0，打开 `Newbie.uproject`
2. 启动服务端：运行 `server/main.py`（Python 3，需安装 protobuf）
3. 在 UE 编辑器中点击 Play，进入主菜单
4. 在登录界面输入账号密码（预置账号：`netease1`/`netease2`/`netease3`，密码均为 `123`），点击登录；也可注册新账号
5. 选择或创建角色后点击"开始游戏"，进入 Level1

**多机联机**：默认连接地址为 `127.0.0.1`（本机），如需多机联机，非主机客户端需修改 `Content/Scripts/network/network_manager.py` 中 `DEFAULT_HOST = "127.0.0.1"` 为服务端的实际 IP 地址。

### 按键操作

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
| **G** | 画质设置 | 游戏中弹出画质面板，释放鼠标，再按G或点返回关闭 |

### 游戏流程

1. **Level1**：4个敌人（近战+远程混编），消灭所有敌人后自动进入 Level2
2. **Level2**：4个敌人（更多远程敌人），消灭后显示胜利结算界面
3. 玩家死亡则显示失败界面，可选择重试或返回主菜单

### HUD 信息

| 位置 | 内容 |
|------|------|
| 屏幕中央 | 十字准星（持枪时显示） |
| 左下角 | 血条 + HP数值 |
| 血条上方 | Buff状态（ATK↑/ATK↓ + 层数 + 剩余时间） |
| 右下角 | 弹药数（当前/储备）+ 射击模式 + 魔法箭CD |
| 左上角 | 关卡编号 + 剩余敌人数 |
| 敌人头顶 | 伤害跳字（黄色浮动数字） |

### 道具拾取

敌人死亡后掉落道具，走近自动拾取：弹药箱（+30储备弹药，50%概率）或急救包（+50HP，50%概率）。道具15秒后自动消失。

### 画质设置

主菜单 → "画质设置" → 选择 Low / Med / High 三档，即时生效，下次启动自动恢复。

---

## 第二部分：作业内容

以下按 P5 中"客户端基础要求"的18条逐一说明实现方式，然后是服务端要求、材质与渲染、性能分析等。

---

### 基础要求1：搭建一个简单的3D场景，供玩家游戏

共 3 个游戏关卡：MainMenu（主菜单）、Level1（5敌人）、Level2（8敌人）。

---

### 基础要求2：可以用键盘、鼠标控制人物在场景中行走、跳跃、射击

**实现**：`MovementComponent` 基于 `AddMovementInput` 实现移动，输入方向以 Controller Yaw 旋转为基准：W/S 调用 `move_forward(±1)` 生成 Controller 前向向量的移动输入，A/D 调用 `move_right(±1)` 生成 Controller 右向向量的移动输入，组合起来支持8向移动。跳跃通过 `Character.Jump()` 实现，先用 `CharacterMovement.IsFalling()` 检测是否在地面，仅在地面时允许起跳。射击见要求4。

所有输入映射由 `InputConfig` 在引擎初始化时动态创建（`on_post_engine_init` 中调用），通过 `ue.InputSettings.AddAxisMapping/AddActionMapping` 注册，无需在编辑器项目设置中手动配置。`KeyboardInputHandler` 通过 `InputComponent.BindAxis/BindAction` 将映射绑定到对应的回调函数。冲刺（LeftShift）按住时将 `MaxWalkSpeed` 设为 600，松开恢复 300；射击和瞄准时禁止冲刺。

---

### 基础要求3：摄像机以TPS视角跟随主角

**实现（越肩摄像机 + ADS瞄准）**：

摄像机挂在 SpringArmComponent 上，位于角色右后上方（TargetArmLength=300, SocketOffset Y=50 右偏/越肩, Z=100 上偏），启用 CameraLag（速度6.0）产生平滑跟随感。SpringArm 的 `bUsePawnControlRotation=True`，摄像机跟随 Controller 旋转。

**瞄准模式（ADS）**：右键按住时，TargetArmLength 从300缩小到50（摄像机贴近角色），SocketOffset Y从50→30/Z从100→80（更居中），角色自动转向摄像机 Yaw 方向，移动速度降至300（瞄准移速惩罚）。


---

### 基础要求4：鼠标左键控制枪械开枪射击，可以在点射和连射模式间切换

**实现（HitScan双射线检测）**：

射击使用 HitScan 方式（射线即时命中），不是投射物。核心设计是**双射线检测**——每次射击执行两次 LineTrace：

第一次 cam_trace 从摄像机位置沿准星方向发射，目的是确定瞄准目标点（只提供方向，不决定命中）。第二次 muzzle_trace 从枪口位置往 cam_trace 的命中点发射，决定实际命中什么。

射线使用 Camera 通道（TraceTypeQuery2），忽略玩家自身。命中 Actor 通过 `HitResult.Component (WeakPtr) → .Get() → Component → .GetOwner()` 提取，使用 `hasattr(actor, 'take_damage')` 判定是否为可受伤目标（NePy 中 isinstance 不可靠）。

**点射/连射切换**：C键切换。点射模式射击间隔0.15秒，连射0.1秒。`ShootingComponent` 维护 `_is_firing` 状态（鼠标按下/松开），`tick()` 每帧检查 `_is_firing` 并调用 `shoot()`，`can_shoot()` 中通过 `fire_rate` 控制射击间隔。射击时强制降速到300（持枪步行动画），停止射击后恢复。

**弹道视觉**：射击时在枪口位置 Spawn `TracerRound`（细长圆柱体 StaticMesh，Scale 0.05×0.05×1.5），速度30000飞向命中点，0.2秒自动销毁。使用 SceneComponent 做根组件（`bRotationFollowsVelocity` 控制朝向），Cylinder 子组件以-90° pitch 相对旋转沿X轴（前方）。因为是子组件的 RelativeRotation，不受根组件朝向覆盖。通过行程距离判断是否越过目标点后立即销毁（高速弹丸每帧移动约500单位，距离判定<50会被跳过，改用已飞行距离平方比较）。

---

### 基础要求5：鼠标右键发射魔法箭，魔法箭有飞行轨迹，有攻击间隔(CD)，击中目标后使一定范围内的敌人晕眩3秒

**实现**：

**魔法箭 Actor**（`MagicArrow`）：使用 ProjectileMovementComponent 的投射物，速度3000，无重力（ProjectileGravityScale=0.0）。箭体挂载自发光材质 `LightArrow`，以及 `NS_ArrowTrail_Magic` 冰霜拖尾 Niagara 特效。

**碰撞**：SphereComponent（半径12）做根组件，碰撞延迟0.05秒后开启（避免出生时撞到玩家自身），使用 `IgnoreActorWhenMoving(owner, True)` 忽略发射者。命中任何物体后触发 AOE 效果。

**晕眩**：命中后在半径500内查找所有 BaseEnemy，对未死亡的敌人调用 `ai.set_stunned(3.0)`，AI 进入 STUNNED 状态，`mesh.GlobalAnimRateScale=0.0` 冻结动画，3秒后根据与玩家距离判断恢复到 CHASE 或 IDLE。

**AOE特效**：命中点播放 `NS_Basic_6` Niagara 特效（`SeekToDesiredAge(0.5)` 跳过前半段），加爆炸音效。

**CD**：10秒冷却，`ShootingComponent._magic_arrow_cd_remaining` 倒计时，HUD 显示 "MAGIC X.Xs" 或 "MAGIC READY"。

**Shader预热**：`BaseCharacter.ReceiveBeginPlay` 中 Spawn 一根 `_visual_only=True` 的魔法箭（禁用碰撞和命中逻辑），下一帧销毁。这强制 UE 编译 Cylinder+LightArrow 的 Shader 和触发纹理 Streaming，避免玩家首次发射魔法箭时箭体黑漆漆的问题（首次使用时 GPU 资源异步加载，Shader 未编译完成）。

---

### 基础要求6：枪械有弹夹设定，有换弹动作表现

**实现**：`ShootingComponent` 管理弹药：弹夹容量30，总弹药上限90（3个弹夹）。换弹时从总弹药补充弹夹，不够则补剩余量。换弹持续2秒，期间不可射击。

换弹触发方式：R键手动换弹，或弹药打空时自动触发（`can_shoot()` 中 current_ammo<=0 且 total_ammo>0 时自动调用 `start_reload()`）。

换弹动画：推送 `bIsReloading=True` 脉冲到 AnimBP，AnimBP 中触发换弹 Montage。使用"延迟一帧还原"机制——帧1设 True，帧2检测到 `_pending_reload_reset` 后还原为 False。

---

### 基础要求7：场景中有一些可以被攻击的敌人，可以控制角色使用武器攻击敌人，击杀直至消失

**实现**：敌人基类 `BaseEnemy` 继承 `ue.Character`，有 `HealthComponent` 管理 HP，`take_damage()` 扣血，死亡回调播放死亡 Montage 并播放溶解效果。溶解使用 `M_Dissolve` 材质 + `CreateDynamicMaterialInstance`，`DissolveAmount` 从0到1渐变2秒。溶解完成后调用 `Destroy()` 销毁 Actor 并在原位 Spawn 掉落道具。

---

### 基础要求8：加入关卡设计，支持两类关卡，能够顺利切换关卡到下一关

**实现**：`TPSGameMode` 管理3个关卡：MainMenu（主菜单+登录）、Level3（4敌人）、Level4（4敌人）。GameMode 在 `ReceiveBeginPlay` 中通过关卡名判断当前关卡编号（"Level3"→1, "Level4"→2），并调用 `GetAllActorsOfClass(BaseEnemy)` 统计场景中的敌人数量。

敌人死亡时 `GameMode.on_enemy_killed()` 递减计数，当 `alive_enemies` 降为0时触发胜利：Level3 胜利后调用 `ue.GameplayStatics.OpenLevel("Level2")` 切换关卡，Level4 胜利后显示胜利结算 Widget。玩家死亡则显示失败结算 Widget。

结算界面（`WBP_GameResult`）在玩家 Tick 中创建（使用 `_pending_result_widget` 标记延迟一帧）结算界面显示胜利/失败，可重试或返回主菜单。

---

### 基础要求9：至少实现两种不同攻击模式的敌人：近战敌人和远程敌人

**实现**：

**近战敌人**（`MeleeEnemy`）：HP=80，detect_range=800，attack_range=150，attack_cooldown=1.5s，move_speed=300。不持枪（AnimBP `bHasWeapon=False`），攻击时播放 ComboAttack Montage，延迟0.5秒到出拳帧时检测玩家距离（attack_range×1.4容差），在范围内造成15伤害。

**远程敌人**（`RangedEnemy`）：HP=60，detect_range=1500，attack_range=800，attack_cooldown=2.0s，move_speed=200。持枪（AnimBP `bHasWeapon=True`，挂载 SM_AR4），攻击时在身体前方80cm Spawn `EnemyProjectile`（SphereComponent 碰撞+ProjectileMovement，速度1500），命中玩家造成10伤害。EnemyProjectile 使用 `IgnoreActorWhenMoving(owner)` 忽略发射者，Overlap 碰撞玩家后扣血并销毁。

---

### 基础要求10：敌人有简单的AI，会攻击玩家

**实现（Python状态机）**：

`EnemyAIComponent` 实现了5状态的有限状态机：IDLE → CHASE → ATTACK → STUNNED → DEAD。

**IDLE状态**：敌人在出生点附近巡逻。使用 NavMesh 的 `GetRandomReachablePointInRadius` 在 patrol_radius=500 内取随机可达点，通过回调 `on_patrol_move` 每帧驱动 `AddMovementInput` 直线走向目标（移动速度降至200），到达后等待2.5秒，再取下一个巡逻点。任何时刻检测到玩家进入 detect_range 立即切换到 CHASE。

**CHASE状态**：每帧通过回调 `on_chase` 调用 `AddMovementInput` 向玩家方向移动。如果玩家距离超过 lose_range（近战1500/远程2000），切换回 IDLE 并进入巡逻等待子阶段；如果距离小于 attack_range（近战150/远程800），切换到 ATTACK。

**ATTACK状态**：每次 attack_cooldown 冷却结束后通过回调 `on_attack` 触发攻击逻辑（近战播放Montage延迟扣血 / 远程发射子弹）。如果玩家距离超过 attack_range×1.2，切换回 CHASE。

**STUNNED状态**：被魔法箭命中后进入，`_stun_timer` 倒计时3秒，同时 `mesh.GlobalAnimRateScale=0.0` 冻结动画。恢复时检测与玩家的距离：在 lose_range 内→CHASE，否则→IDLE。这样晕眩恢复后敌人会根据玩家位置做出合理判断，而不是统一回 IDLE。

**DEAD状态**：血量归零后进入，停止所有 AI 逻辑。

---

### 基础要求11：buff系统

**实现**：

`BuffComponent` 管理 Buff/Debuff，配置表定义两种类型：

- `attack_up`：+0.3倍率/层，持续10秒，F键触发（自我增益）
- `attack_down`：-0.2倍率/层，持续8秒，敌人攻击时自动附加（`_on_damage` 中检测 `attacker._is_enemy`）

**四条规则**：

1. 所有 Buff 合计最多3层（`MAX_STACKS=3`），满了则移除最早的（`buffs.pop(0)`），新 Buff 替换
2. 同类 Buff 添加间隔2秒（`ADD_INTERVAL=2.0`），通过 `_last_add_time` 字典记录上次添加时间
3. Buff 有对应表现：
   - 角色身体 OverlayMaterial 发光：`M_BuffGlow` 材质 + `CreateDynamicMaterialInstance`，ATK↑ 金色（1.0,0.8,0.2）/ ATK↓ 红色（1.0,0.1,0.1），发光强度与层数正比
   - 剩余≤3秒时闪烁（每0.1秒在当前强度和0之间切换）
   - 无 Buff 时移除 OverlayMaterial
4. `get_attack_multiplier()` 计算最终攻击倍率（下限0.1），`ShootingComponent` 在计算伤害时乘以此倍率

---

### 基础要求12：击杀敌人会在场景中掉落弹药、血包等道具，可以拾取以补充弹药和血量

**实现**：`PickupItem` Actor，敌人死亡时在死亡位置生成。50%弹药箱（+30储备弹药）/ 50%急救包（+50HP）。

道具使用 SphereComponent（半径80，OverlapAllDynamic）检测玩家碰触。为避免碰撞球和模型互相干扰，模型组件的碰撞设为 NoCollision。道具使用 RotatingMovementComponent 自动旋转（90°/秒），设定15秒后自动销毁（引擎内部倒计时，不依赖 Tick）。

拾取逻辑在 `_on_overlap` 中：检查碰触者是否有 `shooting` 和 `health` 属性，弹药箱调用 `shooting.add_ammo(30)`，急救包调用 `health.heal(50)`，拾取后立即 `Destroy()`。

---

### 基础要求13：有简单的GUI界面信息，例如血条，剩余弹药数量，伤害跳字等

**实现**：`CrosshairHUD` 继承 `ue.HUD`，在 `ReceiveDrawHUD` 中每帧绘制：

- **十字准星**：4条 DrawLine（绿色，持枪时显示）
- **血条**：DrawRect 背景灰 + 前景绿（低血量变红，阈值0.3），DrawText 显示 HP 数值，位于左下角
- **弹药显示**：DrawText 显示 "当前/储备"，加射击模式（AUTO/SEMI）和换弹提示（RELOADING...），位于右下角，仅持枪时显示
- **魔法箭CD**：DrawText 显示 "MAGIC READY" 或 "MAGIC X.Xs"
- **Buff状态**：DrawText 显示 ATK↑/ATK↓ + 层数 + 倒计时，位于血条上方
- **伤害跳字**：`add_damage_number()` 接收世界坐标和伤害值，使用 `Project()` 转换为屏幕坐标，1秒内上浮80像素并淡出
- **关卡信息**：DrawText 显示关卡编号和剩余敌人数，位于左上角

---

### 基础要求14：有背景音乐、角色和敌人有受击、攻击音效和粒子特效

**实现**：`AudioManager` 管理音效和粒子的加载与播放。所有资源首次使用时通过 `LoadObject` 加载并缓存，避免重复加载。

| 事件 | 音效 | 粒子 | 音量 |
|------|------|------|------|
| 射击 | Explosion02 | P_Explosion(0.2x) 枪口火花 | 0.6 |
| 命中敌人 | Explosion_Cue | P_Explosion(0.3x) 命中爆炸 | 0.7 |
| 命中表面 | Explosion02 | P_Explosion(0.15x) 小火花 | 0.3 |
| 魔法箭飞行 | Light02_Cue | NS_ArrowTrail_Magic 拖尾 | 0.8 |
| 魔法箭爆炸 | Explosion02 | NS_Basic_6 AOE | 0.7 |
| 敌人死亡 | Explosion01 | P_Explosion(0.5x) | 0.8 |
| 敌人攻击 | Collapse_Cue | — | 0.5 |
| 背景音乐 | Starter_Music_Cue | — | 0.3 |

3D 音效用 `PlaySoundAtLocation`，BGM 用 `PlaySound2D`。粒子用 `SpawnEmitterAtLocation`（bAutoDestroy=True）。表面命中和敌人命中的特效强度不同——敌人命中是"重要事件"需要明确感知，地面命中是"辅助信息"不需要太嘈杂。

---

### 基础要求15：性能分级模块

**实现（零耦合 Scalability API）**：

`GraphicsQualityManager`（单例）提供 Low(0)/Med(1)/High(2) 三档画质，通过引擎 Scalability API 控制10个渲染组：

| Scalability 组 | Low | Med | High |
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

**即时生效**：通过 `KismetSystemLibrary.ExecuteConsoleCommand` 执行 `sg.XxxQuality` 控制台命令，所有组统一使用 `SetByConsole` 优先级。

**持久化**：写入 `GameUserSettings.ini` 的 `[/Script/Engine.GameUserSettings]` 段，下次启动时引擎自动读取恢复。

**可观察差异**：Low 关闭动态阴影和 Lumen GI/反射，纹理模糊（MipBias=1，Pool=400MB），植被最疏；High 开启4级 CSM + VSM + Lumen 全功能，纹理最清晰（MipBias=0，Pool=800MB），植被密集。静态场景因使用 Lightmass 烘焙光照，不受 Scalability 影响——Low 和 High 的差异主要体现在动态物体（角色、敌人）和阴影上。

入口为主菜单"画质设置"按钮 → `WBP_GraphicsSettings` Widget → Low/Med/High 三按钮。游戏中也可按 G 键弹出画质面板，释放鼠标并暂停角色输入，再按 G 或点击返回关闭面板恢复游戏。

---

### 基础要求16：灵活应用UE的材质系统，编写特殊的材质效果

**实现**：使用材质系统编写了下面几种材质效果：

1. **M_Dissolve（溶解材质）**：敌人死亡时替换所有材质 slot 为溶解 MID。`DissolveAmount` 从0到1渐变2秒，边缘有发光 Emissive 效果，随溶解进度从脚到头逐渐消失。

2. **M_BuffGlow（Buff发光材质）**：OverlayMaterial 方式挂载到角色 Mesh，`GlowColor` 参数控制颜色（ATK↑ 金色/ATK↓ 红色），`GlowIntensity` 控制强度与层数正比，剩余≤3秒时通过 Python 每0.1秒在0和当前强度之间切换实现闪烁。

3. **Dither材质（30+种）**：遮挡半透明效果，见下文 Dither 详述。批量转换脚本 `Scripts/batch_convert_dither.py` 扫描 `/Game/LowerSector_Mod/Models` 下所有材质，自动生成 Dither 版本：Blend Mode 改为 Masked，添加 `FadeOpacity` 标量参数，连接 `DitherTemporalAA` 函数到 Opacity Mask。

---

### 基础要求17：灵活应用UE各类渲染特性提升画面效果，如光照、后处理等

**实现**：

- **光照**：使用 Lightmass 烘焙静态间接光照。
- **Megalights**：在第二个关卡中，灯光较多，使用Megalights来支持多光源直接光照和阴影。
- **后处理**：PostProcessVolume 中挂载受伤泛红材质（M_damageOverlay），使用 Bloom 等标准后处理效果。

---

### 基础要求18：使用Unreal Insights对游戏性能进行简单分析

**实现**：在开发过程中使用 `stat fps` 和 `stat unit` 控制台命令监控帧率和各线程耗时，使用 Unreal Insights 对 CPU 各线程、GPU 和内存进行简单分析。

主要关注点：
- `stat unit` 观察 Game/Draw/RHI/GPU 各线程时间，确保帧率在60fps以上
- 在使用lumen时，运行时性能瓶颈在GPU端，每帧的GPU时间大约为15ms，关闭lumen换用光照烘焙之后GPU时间大约为9ms，其中3.8ms在处理megalights


---

### Dither遮挡效果（详细说明）

**文件**：`character/dither_occlusion.py`

**问题**：TPS 游戏中摄像机在角色后上方，当摄像机和角色之间有墙壁、建筑等障碍物时，玩家看不到自己的角色。

**解决方案**：当检测到摄像机和角色之间有遮挡物时，将遮挡物的材质替换为半透明的 Dither 版本，让玩家能透过遮挡物看到角色。

**检测方式**：每帧从相机向角色的头部（+160Z）和腰部（+90Z）两个端点分别发射 Visibility 通道射线。使用**迭代 LineTraceSingle 穿透检测**：每次命中一个遮挡物后将其加入 ignore 列表，从命中点稍微偏移（0.01比例）继续 trace，最多穿透10个遮挡物。这解决了之前使用 LineTraceMulti 只能检测一个遮挡物的问题——LineTraceMulti 的 bBlockingHit 在第一个阻挡处就为 True，射线不再继续。

**材质替换**：命中的遮挡物通过 `DITHER_MAT_MAP`（30+条目）查找原始材质路径对应的 Dither 版本。使用 `CreateDynamicMaterialInstance` 创建 Dither MID，设置 `FadeOpacity=0.2`（20%透明度），替换遮挡物的材质 slot。遮挡物不再被遮挡时自动恢复原始材质。

**材质映射**：批量转换脚本 `Scripts/batch_convert_dither.py` 在编辑器中运行，扫描 LowerSector_Mod 资源包下所有材质，为每个材质生成 Dither 版本（Blend Mode→Masked + FadeOpacity 参数 + DitherTemporalAA 函数→Opacity Mask）。映射表保存在 `docs/dither_material_mapping.md`。

---

### 服务端基础要求

#### 1. 服务器可以同时接入多个客户端，通过protobuf跟多个客户端进行交互

**实现**：服务端使用 Python `select` 实现非阻塞事件循环（约125fps），支持同时接入多个客户端。通信协议为 TCP + Google Protocol Buffers：消息格式为 `[4字节大端长度][2字节大端msg_id][protobuf body]`。

`ClientSession` 为每个连接维护接收缓冲区和发送队列，`try_recv()` 非阻塞读取数据并解析消息，`extract_messages()` 提取完整的消息。`GameServer._event_loop()` 中 select 检测可读 socket，新连接创建 ClientSession，已有连接读取并分发消息到 `msg_handler.py` 中的处理函数。

客户端使用 `NetClient`（基于 `ue.AddTicker` 驱动非阻塞 socket）连接服务器，`NetworkManager`（单例）封装 NetClient 提供游戏级 API。

#### 2. 可以创建账号设置密码，建立/选择角色进入游戏

**实现**：`Database` 使用 sqlite3 存储，自动创建 accounts 和 characters 表，内建3个账号（netease1/2/3，密码123）。支持注册（账号不可重复）、登录（验证密码）、创建角色（名称不可重复）、删除角色、查询角色列表。

客户端登录流程：`LoginPanel` → 输入账号密码 → `NetworkManager.login/register` → 服务端验证 → 返回 `SC_LOGIN_RESULT` → 成功后获取角色列表 `SC_CHARACTER_LIST` → `MainMenuPanel` 显示角色槽位 → 选择角色进游戏 `SC_ENTER_GAME`。

每个账号最多4个角色槽位，角色有名称和等级属性，关卡胜利时角色自动升级（+1 level）。

#### 3. 服务器能够简单管理游戏内必须的物体，能够实现客户端退出重连后重新进入战场

**实现**：`GameWorld` 管理所有在线玩家状态，包括位置、旋转、HP、移动速度、冲刺/瞄准/换弹/持枪/空中等状态。

**断线重连**：客户端断线时，服务端将玩家状态（包括最新位置/旋转/HP）保存到 `disconnected_sessions` 字典中（保留5分钟）。同一账号重新连接后，服务端在 `handle_select_character` 中检测到断线记录，复用旧的 player_id 并将保存的位置/旋转发送给客户端。客户端收到 `SC_ENTER_GAME` 后在 `_on_net_enter_game` 中使用 `K2_SetActorLocation` 传送到服务端记录的位置。

服务端还会检测30秒无消息的 IN_GAME 连接（正常客户端每100ms发 CsMove），视为异常断开并触发断线保存流程。

主机掉线时，服务端向其他客户端广播 `SC_DISCONNECT`（"主机掉线，游戏结束"）。

#### 4. 服务器端能够正常同步其他角色，包括移动，技能，动作以及其他有用的信息

**实现（主机-非主机架构 + 速度驱动 + 位置纠偏）**：

**主机机制**：第一个进入游戏的客户端自动成为主机（`is_host=True`），负责驱动本地敌人 AI 并上报敌人状态。后进入的客户端为非主机，敌人由网络驱动（`_is_network_driven=True`），禁用本地 AI。

**玩家同步**：

客户端每帧（约60fps）上报位置、旋转、冲刺/持枪/空中状态到服务端。服务端收到后更新 GameWorld 并立即广播 `SC_PLAYER_STATES` 给其他客户端。服务端还每0.1秒做一次兜底广播。

非主机客户端收到 `SC_PLAYERStates` 后，在 `RemotePlayer` 上使用**速度驱动 + 位置纠偏**方案：
- 服务端从位置差计算速度（vel_x/vel_z），广播给客户端
- 客户端 `RemotePlayer` 直接设置 `CharacterMovement.Velocity`，Walking 模式下角色自然移动，动画/重力/碰撞全部正常工作
- 位置纠偏：小偏差（<50单位）不纠正让移动自然；中等偏差（50-500）以 INTERP_SPEED=10 插值趋近服务端位置；大偏差（>500）直接传送

旋转以720°/s 速度追踪服务端旋转，避免瞬间跳变。

**敌人同步**：

主机每帧上报所有敌人状态（位置/旋转/HP/AI状态/是否攻击），非主机收到后在本地敌人上 `apply_network_state()`：直接设置位置和旋转，通过位置差计算速度设置 CharacterMovement.Velocity 驱动移动动画，同步血量和 AI 状态。

**敌人事件同步**（伤害/击杀/晕眩）：只有主机发起（本地射击命中敌人时），通过 `CsEnemyEvent` 发送到服务端广播给非主机。非主机收到后在本地执行（`from_network=True` 参数避免二次广播）。击杀时道具类型也通过事件同步，由主机决定并附带在 `ENEMY_KILLED` 事件中。

**射击同步**：客户端射击时发送 `CsShoot`（命中点+武器类型+箭矢ID），服务端广播 `SC_SHOOT_RESULT`。非主机客户端在远程玩家位置生成弹道视觉特效（TracerRound 从远程玩家枪口飞向网络命中点）。

**魔法箭同步**：发射时同步箭矢ID，命中时发送 `CsMagicArrowHit`（AOE位置），非主机销毁对应箭矢并在AOE位置播放特效。

**动作同步**：换弹/瞄准通过 `CsAction` 同步，非主机在远程玩家的 AnimBP 上设置 `bIsReloading`/`bIsAiming`。

**道具拾取同步**：拾取时通过 `CsPickup{item_uid}` 发送服务端广播 `ScPickupResult`，非发起者客户端收到后按 `item_uid` 查找并销毁本地对应道具，防止不同步导致同一道具被多人重复拾取。

---

### AI部分

#### AI使用技巧

AI 编写代码时经常虚构不存在的 API，因此在生成代码后必须查阅相关文档确认 API 确实存在后再使用。

#### 使用AI提高开发效率的实例

##### 实例1：AI辅助批量生成Dither材质资产

在实现 Dither 遮挡效果时，两个场景中使用了资源包的30多种不同材质。如果手动为每种材质创建 Dither 版本比较繁琐。

使用 AI 生成了一个编辑器批处理脚本 `Scripts/batch_convert_dither.py`，该脚本在 UE 编辑器中通过 Python 命令执行，自动完成以下流程：

1. 使用 `unreal.EditorAssetLibrary.list_assets()` 递归扫描 `/Game/LowerSector_Mod/Models` 下所有材质
2. 过滤掉已有的 `_Dither` 后缀材质和 MaterialInstance（只处理母材质）
3. 对每个材质调用 `convert_to_dither_material.create_dither_material()` 生成 Dither 版本：
   - 复制原始材质到新路径（后缀加 `_Dither`）
   - 将 Blend Mode 从 Opaque 改为 Masked
   - 添加 `FadeOpacity` 标量参数（默认值1.0）
   - 在材质图表中连接 `DitherTemporalAA` 函数到 Opacity Mask 输入
4. 跳过已存在的 Dither 材质（幂等性，可重复执行）
5. 强制保存并重编译所有生成的材质
6. 输出原始材质→Dither材质的映射关系到 `docs/dither_material_mapping.md`

整个批处理过程不到1分钟，且映射表直接被运行时代码 `dither_occlusion.py` 的 `DITHER_MAT_MAP` 字典引用。当遮挡发生时，系统根据命中物体的材质路径在映射表中查找对应的 Dither 版本，动态创建 MID 并替换，实现遮挡半透明效果。

这种方式的优势：
- **效率**：30+种材质从手动3-4小时缩短到自动化1分钟
- **正确性**：AI生成的脚本逻辑统一，避免手动操作时的遗漏或参数不一致
- **可维护性**：新增场景资源时只需重新运行脚本，映射表自动更新
- **幂等性**：脚本可重复执行，已存在的 Dither 材质会被跳过而非重复创建

##### 实例2：AI驱动的服务端测试自动化

服务端使用 Python 实现了基于 `select` 的非阻塞事件循环 + protobuf 通信协议，逻辑复杂度较高（登录、角色管理、移动同步、断线重连、敌人状态同步等）。手动测试需要启动服务端→启动客户端→操作→观察日志，效率低且容易遗漏边界情况。

使用 AI 编写自动化测试脚本，采用"AI写测试→运行→AI根据失败结果修复→再运行"的迭代循环，直到所有测试用例通过。项目中生成了多个测试脚本：

- `test_client.py`：综合测试客户端，覆盖登录/注册/创建角色/选择角色/移动同步/断线重连等完整流程
- `test_reconnect.py`：断线重连专项测试
- `test_reconnect_v2.py`：重连v2测试
- `test_quick_reconnect.py`：快速重连最小化测试

测试脚本模拟真实客户端行为：建立 TCP 连接→发送 protobuf 消息→接收并验证服务端响应→断开重连→验证状态恢复。每个测试用例有明确的通过/失败判定（如验证返回码、检查位置同步精度、确认断线后状态保留等）。

关键实践：
- **AI编写测试代码**：描述测试场景和期望行为，AI生成完整的测试脚本
- **运行→修复循环**：运行测试发现失败→将失败日志反馈给AI→AI修复代码或测试→再次运行，循环直到全部通过
- **边界用例覆盖**：AI能想到一些容易遗漏的边界情况（如同一账号重复登录、断线后5分钟超时、角色名重复等），自动补充测试用例

这种方式将服务端的验证从手动操作变为自动化回归测试，后续修改服务端代码后只需运行测试脚本即可确认没有引入回归问题。

---

### 扩展部分（附加分项）

未实现下蹲/匍匐、多枪械切换、技能、机关等扩展功能。项目专注于完成基础要求的18项功能，并在材质特效（Dither遮挡）、TPS射击设计（双射线）、网络同步（主机-非主机+速度驱动+位置纠偏）等方面做了深入实现。

---

### 关于NePy插件

本项目使用 NePy（NePythonBinding）插件，这是网易内部的 UE5.6 Python 绑定插件，允许用 Python 编写 UE 的 UClass。核心约束是 NePy 子类化不支持 `ReceiveTick`（UE 优化：蓝图中无 Tick 节点则 C++ 层不注册 Ticker），解决方案是使用 `TickableMixin` + `ue.AddTicker` 替代。其他重要踩坑包括：`__init_pyobj__` 代替 `__init__`、`@ue.uproperty()` 会导致 Cast 失败、AnimBP 变量需直接赋值而非 `set_editor_property`、`HitResult.Component` 是 WeakPtr 需 `.Get()` 解引用、`SetActorLocation` 需3个参数等。

---

### 第三方库与插件

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

---

### 提交说明

- 引擎版本：UE 5.6
- 编程语言：Python（动画蓝图、材质、行为树可用蓝图实现），C++仅作辅助
- 不需要游戏打包（NePy无源码），但压缩提交前需解压到新目录验证工程完整性
- 提交目录：Binaries、Config、Content、Plugins、Source（若有）、Scripts、.uproject
- 不提交：DerivedDataCache、Intermediate
