# 第三人称射击（TPS）系统设计

## 概述

本文档描述 Newbie 项目中第三人称射击系统的完整设计，包括摄像机、瞄准、射击检测、弹道视觉、命中反馈等环节，以及每个设计决策背后的考量。

---

## 1. 摄像机系统

**文件**: `Content/Scripts/character/camera.py`

### 1.1 越肩摄像机

摄像机挂载在 SpringArmComponent 上，位于角色右后上方：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| TargetArmLength | 300.0 | 摄像机到角色的距离 |
| SocketOffset Y | 50.0 | 右偏（越肩效果） |
| SocketOffset Z | 100.0 | 上偏（俯视感） |
| CameraLagSpeed | 6.0 | 摄像机跟随延迟（平滑感） |
| ProbeSize | 12.0 | 碰撞探测球大小 |

**为什么用越肩而非正后方？** 越肩视角在 TPS 中是经典选择：右偏让玩家能看到角色侧面（增强代入感），同时不遮挡准星方向的视野。

### 1.2 瞄准模式（ADS）

按右键开镜时：

- TargetArmLength 从 300 → 50（摄像机拉近角色）
- SocketOffset Y 从 50 → 30, Z 从 100 → 80
- 角色自动转向摄像机 Yaw 方向
- 移动速度降至 300（瞄准移速惩罚）

**为什么开镜时角色要转向摄像机？** 第三人称下角色朝向和摄像机朝向经常不一致。开镜射击时，如果角色面朝的方向和摄像机不同，子弹会从枪口往摄像机方向飞而不是往角色面朝方向飞，视觉上很不自然。所以开镜瞬间强制角色对齐摄像机 Yaw。

### 1.3 俯仰角限制

在 `update_rotation()` 中手动限制 Pitch 到 **[-80°, +80°]**：

```python
pitch = rot.Pitch
if pitch > 180.0:
    pitch -= 360.0  # UE Rotator Pitch 范围 [0, 360)，转为 [-180, 180)
clamped = max(-80.0, min(80.0, pitch))
```

**为什么限制到 ±80° 而不是 ±90°？**

- 仰头到 90° 时摄像机会翻转到角色背后（万向锁），超过 90° 更是直接看到角色后脑勺
- 低头到 -90° 在 TPS 中没有必要，而且 -80° 已经足够瞄准脚下近处的目标
- 留 10° 余量避免浮点精度导致的翻转问题

**为什么不用 PlayerCameraManager 的 ViewPitchMin/Max？** 

实测发现设置 `ViewPitchMin = -89` 后，仰头会超过垂直面 30°（看到角色后背），说明 PlayerCameraManager 的限制在 SpringArm + CameraLag 组合下不够可靠。改为在输入层直接 Clamp ControlRotation，从源头限制更可控。

---

## 2. 射击检测系统

**文件**: `Content/Scripts/character/shooting.py`

### 2.1 双射线检测（核心设计）

这是本系统最重要的设计决策。每次射击执行两次 LineTrace：

```
第一次（cam_trace）：摄像机 ────→ 命中点P    （只提供瞄准方向，P 是目标点）
第二次（muzzle_trace）：枪口 ──→ P           （决定实际命中什么）
```

**为什么需要两次射线？**

这是 TPS 射击的经典问题——**近距离盲区**：

```
        摄像机（角色后上方）
          \  cam_trace 打到地面，越过敌人头顶
           \
            \   敌人 ← 在准星和枪口之间，但不在 cam_trace 路径上
             X ← 枪口
            /
           /  muzzle_trace 从枪口出发，能命中敌人
          /
        角色
```

当敌人很近时，准星虽然对着敌人方向，但射线从摄像机（角色后上方）出发，会越过敌人头顶打到身后地面。这就是为什么玩家"明明对着敌人开枪却打不到"。

用诊断日志验证了这个分析：

```
[Shoot] cam_trace: hit_loc=(-1182,67,-10) actor=<StaticMeshActor 'SM_road'>     ← 打到地面
[Shoot] muzzle_trace: hit_loc=(-1154,398,49) actor=<MeleeEnemyBP_C>            ← 打到敌人
```

**为什么 cam_trace 只提供方向？**

有人可能想"cam_trace 命中敌人就直接用，只有打偏时才补射"。但这样的问题是：

- cam_trace 命中地面时，`hit_location` 是 cam 射线的地面命中点，不是子弹实际飞到的点
- 子弹从枪口出发，弹道终点应该是枪口射线碰到的第一个东西，而不是摄像机射线碰到的
- 如果只补射敌人检测，地面命中特效会在错误位置播放（cam 的地面命中点 vs muzzle 的地面命中点有偏差）

所以设计为：**cam 只管方向，muzzle 管命中**。逻辑更简单，行为更一致。

### 2.2 射线参数

| 参数 | 值 | 说明 |
|------|----|------|
| TraceChannel | TraceTypeQuery2 | 可见性通道，对静态网格和角色都生效 |
| Actors to Ignore | [self.owner] | 忽略玩家自身，避免自伤 |
| cam_trace 距离 | 100000 | 足够远，保证能找到瞄准目标 |
| muzzle_trace 终点 | cam 命中点 | 从枪口到 cam 命中点 |

**为什么 muzzle_trace 的终点是 cam 命中点而不是同样 100000 远？**

因为 muzzle_trace 的目的是"从枪口出发，沿着准星方向，看碰到什么"。cam 命中点已经是最远的合理目标——如果 cam 打到了 5000 单位外的墙壁，muzzle 只需要检查枪口到那堵墙之间有没有东西，不需要继续往更远处检测。这也避免了枪口射线命中 cam 射线看不到的物体（比如墙后的敌人），保证视觉一致性。

### 2.3 命中判定

`_extract_hit_actor()` 从 HitResult 提取命中 Actor：

```
HitResult.Component (WeakPtr) → .Get() → Component → .GetOwner() → Actor
```

**为什么用 Component → GetOwner 而不是直接拿 Actor？**

UE 的 LineTrace 返回的 HitResult 中没有直接的 Actor 引用，只有 `Component`（弱引用）。需要通过 `Component.GetOwner()` 间接获取。这在 NePy 插件中也是唯一的路径。

### 2.4 敌人判定

```python
def _is_enemy(self, actor):
    return actor is not None and hasattr(actor, 'take_damage')
```

**为什么不用类型检查（isinstance）？**

- NePy 的 Python 类和 UE 的 UClass 是两套体系，`isinstance` 不可靠
- 用 `hasattr(actor, 'take_damage')` 更通用，任何实现了 `take_damage` 的 Actor 都可被射击命中
- 这也意味着友方 NPC 如果有 `take_damage` 也会被判定为敌人——后续如需区分可加入阵营判断

---

## 3. 弹道视觉

**文件**: `Content/Scripts/character/tracer_round.py`

### 3.1 TracerRound 弹丸

射击时生成一个 `TracerRound` Actor，从枪口高速飞向命中点：

| 参数 | 值 | 说明 |
|------|------|------|
| 速度 | 30000 | 极快，接近瞬移但玩家能看到弹道 |
| 形状 | 细长圆柱体 | Scale (0.05, 0.05, 1.5)，模拟弹道线 |
| 最大存活 | 0.2s | 超时自动销毁 |
| 碰撞 | 关闭 | 纯视觉，不影响游戏逻辑 |

**为什么用弹丸而不是直接画线？**

- UE 的 `DrawDebugLine` 只在开发构建可见，不用于正式游戏
- Niagara 粒子弹道配置复杂，而 StaticMesh 弹丸简单可控
- 高速飞行 + 短存活时间 = 视觉上像一道光线闪过，接近 CS 的弹道效果

**为什么生成方向是从枪口到命中点，而不是摄像机方向？**

子弹视觉上从枪口飞出，应该指向实际命中的位置。如果用摄像机方向生成，弹丸会飞向摄像机方向的远处而非枪口前方的命中点，视觉上子弹轨迹和命中点不匹配。

---

## 4. 命中反馈

**文件**: `Content/Scripts/system/audio_manager.py`

### 4.1 三层反馈

| 事件 | 音效 | 特效 | 触发条件 |
|------|------|------|----------|
| 射击 | gunshot（0.6音量） | muzzle_flash（0.2缩放） | 每次射击 |
| 命中敌人 | enemy_hit（0.7音量） | hit_explosion（0.3缩放） | muzzle_trace 命中敌人 |
| 命中表面 | gunshot（0.3音量） | hit_explosion（0.15缩放） | muzzle_trace 命中地面/墙壁 |

**为什么表面命中的特效比敌人命中小？**

- 命中敌人是"重要事件"（确认击中、获得反馈），需要明确感知
- 命中地面是"辅助信息"（知道打偏了），不需要太显眼，否则频繁射击地面时满屏爆炸会很嘈杂
- 音量也做了区分：敌人 0.7 vs 表面 0.3

### 4.2 特效位置

所有命中特效都在 `hit_location`（muzzle_trace 的命中点）播放，保证视觉和逻辑一致。

---

## 5. 魔法箭

`fire_magic_arrow()` 目前仍使用旧的单射线逻辑（cam_trace 直接决定目标点），因为它是一个投射物系统（SpawnActor + ProjectileMovement），不是 HitScan。投射物的碰撞由 UE 物理引擎在飞行过程中检测，不需要双射线修正。

---

## 6. 未解决的问题

| 问题 | 说明 |
|------|------|
| 准星无法瞄准脚前很近的地面 | Pitch 限制到 -80° 后，低头看脚前约 2m 以内的地面仍无法瞄准。这是 SpringArm + 越肩偏移导致的几何限制，非俯仰角问题 |
| 魔法箭未使用双射线 | 魔法箭是投射物，飞行碰撞由物理引擎处理，暂未适配双射线 |
