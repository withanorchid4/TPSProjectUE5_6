# TODO: 视觉表现改善

> 优先级：🔴 高 = 严重影响游戏观感  🟡 中 = 明显的短板  🟢 低 = 锦上添花

---

## 🔴 P0 — 最值得改善

### 1. 魔法箭仍是蓝色圆柱
- **现状**：用 `/Engine/BasicShapes/Cylinder` + 自发光材质，看起来像一个发光的桶
- **目标**：有拖尾粒子特效的箭矢形飞行体
- **方案**：
  - 用锥体(Cone)或自定义Mesh替代圆柱，缩小前端形成箭头感
  - 添加 Niagara 拖尾粒子（发光散射），飞行中持续生成
  - 命中时播放范围晕眩波特效（从命中点向外扩散的圆环）
- **文件**：`Content/Scripts/character/magic_arrow.py` → `_setup_visual()`

### 2. 射击特效全部复用爆炸粒子
- **现状**：枪口火花、命中敌人、敌人死亡 → 全部用 `P_Explosion`
- **目标**：每种场景有专属特效
- **方案**：
  - 枪口火花 → 小型闪光 + 烟雾（MuzzleFlash），不用大爆炸
  - 命中敌人 → 小型血雾/火花溅射（HitImpact），不是爆炸
  - 命中墙壁/地面 → 灰尘飞溅（BulletImpact）
  - 敌人死亡 → 可以保留爆炸但缩小规模
- **文件**：`Content/Scripts/system/audio_manager.py` → `PARTICLE_PATHS` + 拆分播放接口

### 3. 角色转向生硬，无肢体过渡动画
- **现状**：左右移动时角色瞬间转向移动方向（`bUseControllerRotationYaw=False`），没有转身过渡
- **目标**：角色有自然的转向动画，类似 UE 第三人称模板的 blend by direction
- **方案**：
  - 动画蓝图中增加 Blend Space by Direction（Idle→Walk→Run，含左转/右转过渡）
  - 设置 `OrientRotationToMovement=True`，`RotationRate=(0,0,540)` 实现平滑转身
  - 或者利用 AnimBP 中的 `bHasWeapon` 状态切换持枪/非持枪转身动画
- **文件**：动画蓝图（蓝图侧） + `Content/Scripts/character/movement.py`（CharacterMovement 配置）

### 4. 近战敌人持枪状态
- **现状**：`BaseEnemy._setup_weapon()` 给所有敌人挂载步枪 + `anim.bHasWeapon=True`，近战敌人也端着枪跑
- **目标**：近战敌人无武器或持近战武器，有不持枪的奔跑/攻击动画
- **方案**：
  - `MeleeEnemy` 重写 `_setup_weapon()`：不挂载步枪，设 `anim.bHasWeapon=False`
  - 可选：挂载一个近战武器 Mesh（刀/棍）到 `hand_r`
  - 攻击时推送 `bIsAttacking=True` 到 AnimBP 触发近战攻击动画
- **文件**：`Content/Scripts/enemy/melee_enemy.py` + `base_enemy.py`

---

## 🟡 P1 — 明显的短板

### 5. Buff 无视觉反馈
- **现状**：只有 HUD 文字显示 buff 名和层数，角色身上无任何特效
- **目标**：buff 激活时角色有明显视觉变化
- **方案**：
  - 增益buff（attack_up）→ 角色周围发光粒子环（金色/绿色）
  - 减益buff（attack_down）→ 角色周围暗色粒子（红色/紫色）
  - 可用 Niagara 或简单的 Mesh 材质变化实现
- **文件**：`Content/Scripts/system/buff_component.py`（`add_buff()` 时通知角色） + `base_character.py`（接收特效）

### 6. 敌人无攻击动画
- **现状**：近战敌人攻击只是纯逻辑扣血，远程敌人射击也没有开枪动作
- **目标**：攻击时有对应的蒙太奇动画
- **方案**：
  - 近战：播放挥击蒙太奇，在动画特定帧触发伤害（AnimNotify）
  - 远程：播放射击蒙太奇，与子弹生成同步
  - 推送 `bIsAttacking=True` 到 AnimBP，利用状态机自动切换
- **文件**：`Content/Scripts/enemy/melee_enemy.py` → `attack()` + `ranged_enemy.py` → `attack()`

### 7. 弹道轨迹弹丸是圆柱
- **现状**：TracerRound 也用 `/Engine/BasicShapes/Cylinder`，缩成细条
- **目标**：流线型弹道，有发光拖尾
- **方案**：
  - 用更细长的比例或自定义 Mesh
  - 或者改为纯粒子拖尾（用 Niagara trail emitter），不用 Mesh
- **文件**：`Content/Scripts/character/tracer_round.py` → `ReceiveBeginPlay()`

### 8. 敌人受击无击退/硬直表现
- **现状**：敌人被打只推送 `bIsHit` 到 AnimBP，但没有明显的受击反馈
- **目标**：敌人被打时有短暂的硬直或后退
- **方案**：
  - 确认 AnimBP 中 `bIsHit` 是否正确触发了受击动画
  - 可选：受击时短暂降低移动速度或停顿 0.2s
- **文件**：`Content/Scripts/enemy/base_enemy.py` → `_on_damage()`

### 9. 换弹动画可能不同步
- **现状**：`start_reload()` 设置 `anim.bIsReloading=True`，但2秒后自动完成，没有从动画端获取实际时长
- **目标**：换弹动作和逻辑时长同步
- **方案**：
  - 使用 AnimMontage 的时长作为换弹时间，而非硬编码 2.0s
  - 或在 Montage 的 AnimNotify 中触发 `_finish_reload()`
- **文件**：`Content/Scripts/character/shooting.py` → `start_reload()` / `_finish_reload()`

---

## 🟢 P2 — 锦上添花

### 10. 晕眩状态视觉表现
- **现状**：晕眩时 `GlobalAnimRateScale=0.0`（冻结动画），头顶无任何标识
- **目标**：晕眩敌人有明显的视觉反馈
- **方案**：
  - 头顶生成旋转的星星/晕眩环粒子特效
  - 或者角色材质闪烁
- **文件**：`Content/Scripts/enemy/base_enemy.py` → `_on_stunned()`

### 11. 主菜单/结算界面视觉简陋
- **现状**：主菜单和结算都是纯文字按钮，无背景装饰
- **目标**：有游戏标题、背景图/场景、按钮样式美化
- **方案**：
  - Widget 中添加背景图片或渐变色
  - 按钮添加 hover/pressed 状态样式
  - 标题文字加大加粗 + 阴影效果
- **文件**：`WBP_MainMenu` / `WBP_GameResult`（蓝图侧）

### 12. 音效全部是 StarterContent 占位
- **现状**：射击=Fire01，魔法=Light02，敌人受击=Explosion，明显不匹配
- **目标**：每种音效更贴合场景
- **方案**：
  - 从免费音效库（freesound.org 等）获取合适的音效
  - 或从 Marketplace 的免费音效包中选
  - 替换 `SOUND_PATHS` 中的路径
- **文件**：`Content/Scripts/system/audio_manager.py` → `SOUND_PATHS`

### 13. 场景缺少环境氛围
- **现状**：场景是基本的白盒 + StarterContent，缺乏氛围
- **目标**：场景有基本的氛围感
- **方案**：
  - 添加雾效（Exponential Height Fog）
  - 后处理体积（Bloom、Color Grading、Vignette）
  - 简单的光照调整
- **文件**：Level 关卡中手动添加 Actor

---

## 实施建议顺序

1. **先做 P0 的 3 和 4**（角色转向 + 近战敌人不持枪）— 改动小，效果明显
2. **再做 P0 的 2**（射击特效拆分）— 主要是素材替换
3. **然后 P0 的 1**（魔法箭视觉升级）— 需要一定工作量
4. **接着 P1 逐项**（buff特效 → 攻击动画 → 弹道 → 受击反馈 → 换弹同步）
5. **最后 P2**（晕眩表现 → UI美化 → 音效替换 → 场景氛围）
