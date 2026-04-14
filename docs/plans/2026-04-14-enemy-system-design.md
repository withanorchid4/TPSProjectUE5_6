# 敌人系统设计文档

## 需求范围

最小可玩版本，覆盖需求 #7 #9 #10：
- #7 场景中有可以被攻击的敌人，击杀直至消失
- #9 至少两种不同攻击模式：近战敌人 + 远程敌人
- #10 敌人有简单AI，会攻击玩家

## 约束

- Python 为主编程语言（动画蓝图、材质、行为树可用蓝图）
- 使用 NePy 插件 (@ue.uclass)
- 敌人模型复用 Mannequin 骨骼（SKM_Manny_Simple）
- AI 使用 Python 状态机 + NavMesh 寻路

---

## 文件结构

```
Content/Scripts/
├── enemy/
│   ├── __init__.py
│   ├── base_enemy.py          # 敌人基类 @ue.uclass
│   ├── melee_enemy.py         # 近战敌人 @ue.uclass
│   ├── ranged_enemy.py        # 远程敌人 @ue.uclass
│   └── enemy_projectile.py    # 远程敌人子弹 Actor
├── system/
│   ├── __init__.py
│   ├── health_component.py    # 血量组件（敌人/玩家共用）
│   └── enemy_ai_component.py  # AI状态机组件（NavMesh寻路）
```

## 类关系

```
ue.Character
  └── BaseEnemy (@ue.uclass)
        ├── HealthComponent     — 血量/受伤/死亡回调
        ├── EnemyAIComponent    — 状态机(idle→chase→attack) + NavMesh寻路
        │
        ├── MeleeEnemy  — attack_range小，近身伤害，追到就打
        └── RangedEnemy — attack_range大，远程发射 EnemyProjectile

ue.Actor
  └── EnemyProjectile — 远程敌人子弹，碰到玩家造成伤害
```

---

## HealthComponent

```python
class HealthComponent:
    max_hp: float = 100.0
    current_hp: float
    
    take_damage(amount, attacker)   # 扣血，返回实际伤害
    heal(amount)                    # 回血
    is_dead() -> bool               # current_hp <= 0
    
    on_death = None    # 死亡回调
    on_damage = None   # 受伤回调
```

- 玩家后续也可复用，只需设不同 max_hp 和回调
- take_damage 内部 clamp 到 0，不会出现负血量
- 敌人死亡后设碰撞 NoCollision，播动画，延迟 1-2s 后 Destroy()

---

## EnemyAIComponent — 状态机

```
IDLE → CHASE → ATTACK → STUNNED → DEAD

IDLE:    检测玩家距离 < detect_range → CHASE
CHASE:   NavMesh寻路向玩家移动; < attack_range → ATTACK; > lose_range → IDLE
ATTACK:  停止移动, 面向玩家, 执行攻击; 冷却中 → CHASE
STUNNED: 什么都不做, 持续 stun_duration; 时间到 → IDLE
DEAD:    终态
```

### 默认参数

| 参数 | 近战 | 远程 |
|------|------|------|
| detect_range | 800 | 1500 |
| attack_range | 150 | 800 |
| lose_range | 1500 | 2000 |
| attack_cooldown | 1.5s | 2.0s |
| move_speed | 300 | 200 |

---

## MeleeEnemy

- 继承 BaseEnemy，attack_range=150
- attack() 对范围内玩家直接扣血
- 预留减攻debuff接口（后续 #11）

## RangedEnemy

- 继承 BaseEnemy，attack_range=800
- attack() 生成 EnemyProjectile 向玩家方向发射
- 保持距离，太近时后退

## EnemyProjectile

- 和玩家 Bullet 类似，速度更慢（3000 vs 15000）
- 碰到玩家 → 调用玩家 HealthComponent 扣血 → 销毁
- 碰到其他物体 → 直接销毁
- 视觉：Cylinder 网格，缩放子弹形态，红色/橙色区分

## 碰撞配置

- 玩家子弹 → 碰到敌人 → 敌人 take_damage()
- 敌人子弹 → 碰到玩家 → 玩家 take_damage()
- Bullet._on_actor_hit 中添加伤害调用

---

## 编辑器配置清单

- [ ] NavMeshBoundsVolume 放置到关卡
- [ ] 创建敌人蓝图（MeleeEnemyBP / RangedEnemyBP）基于 Python 类
- [ ] 敌人蓝图设置 SKM_Manny_Simple + AnimBP
- [ ] 碰撞预设配置（子弹 vs 敌人/玩家）
- [ ] 在关卡中放置敌人测试
