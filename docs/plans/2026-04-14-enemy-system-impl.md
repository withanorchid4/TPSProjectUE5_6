# Enemy System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a minimum viable enemy system with melee and ranged enemies that have simple AI and can be killed by the player.

**Architecture:** Component composition pattern (consistent with existing BaseCharacter). HealthComponent and EnemyAIComponent are plain Python classes owned by BaseEnemy. Two enemy subclasses override attack behavior. NavMesh for pathfinding.

**Tech Stack:** UE 5.6 + NePy (Python), NavMesh for pathfinding, Mannequin skeleton for enemy visuals

**Design doc:** `docs/plans/2026-04-14-enemy-system-design.md`

---

## Task 1: HealthComponent

**Files:**
- Create: `Content/Scripts/system/__init__.py`
- Create: `Content/Scripts/system/health_component.py`

**Step 1: Create system package**

Create `Content/Scripts/system/__init__.py`:
```python
from .health_component import HealthComponent

__all__ = ['HealthComponent']
```

**Step 2: Implement HealthComponent**

Create `Content/Scripts/system/health_component.py`:
```python
# -*- encoding: utf-8 -*-
"""血量组件 - 敌人/玩家共用"""

import ue


class HealthComponent:
    """
    血量管理组件
    
    Usage:
        health = HealthComponent(owner, max_hp=100.0)
        health.on_death = lambda: owner.handle_death()
        health.on_damage = lambda amount, attacker: owner.handle_damage(amount, attacker)
    """
    
    def __init__(self, owner, max_hp=100.0):
        self.owner = owner
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.on_death = None
        self.on_damage = None
    
    def take_damage(self, amount: float, attacker=None) -> float:
        if self.current_hp <= 0:
            return 0.0
        actual = min(amount, self.current_hp)
        self.current_hp -= actual
        self.current_hp = max(0.0, self.current_hp)
        
        if self.on_damage:
            self.on_damage(actual, attacker)
        
        if self.current_hp <= 0 and self.on_death:
            self.on_death()
        
        return actual
    
    def heal(self, amount: float) -> float:
        if self.current_hp <= 0:
            return 0.0
        old = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - old
    
    def is_dead(self) -> bool:
        return self.current_hp <= 0
    
    def get_hp_ratio(self) -> float:
        if self.max_hp <= 0:
            return 0.0
        return self.current_hp / self.max_hp
```

**Step 3: Verify in editor**

Run game, check Output Log for import errors. No runtime effect yet — just ensure no import errors.

**Step 4: Commit**

```bash
git add Content/Scripts/system/
git commit -m "feat: add HealthComponent for enemy/player HP management"
```

---

## Task 2: EnemyAIComponent

**Files:**
- Create: `Content/Scripts/system/enemy_ai_component.py`
- Modify: `Content/Scripts/system/__init__.py`

**Step 1: Implement EnemyAIComponent**

Create `Content/Scripts/system/enemy_ai_component.py`:
```python
# -*- encoding: utf-8 -*-
"""敌人AI组件 - Python状态机 + NavMesh寻路"""

import ue
from enum import Enum


class EnemyState(Enum):
    IDLE = "idle"
    CHASE = "chase"
    ATTACK = "attack"
    STUNNED = "stunned"
    DEAD = "dead"


class EnemyAIComponent:
    """
    敌人AI状态机组件
    
    状态: IDLE → CHASE → ATTACK → STUNNED → DEAD
    
    用法:
        ai = EnemyAIComponent(owner, detect_range=800, attack_range=150, ...)
        ai.on_chase = lambda: owner.move_to_player()
        ai.on_attack = lambda: owner.attack()
        ai.tick(delta_time)
    """
    
    def __init__(self, owner, detect_range=800.0, attack_range=150.0,
                 lose_range=1500.0, attack_cooldown=1.5, move_speed=300.0):
        self.owner = owner
        self.state = EnemyState.IDLE
        
        # 参数
        self.detect_range = detect_range
        self.attack_range = attack_range
        self.lose_range = lose_range
        self.attack_cooldown = attack_cooldown
        self.move_speed = move_speed
        
        # 计时器
        self._attack_cooldown_timer = 0.0
        self._stun_timer = 0.0
        
        # 回调
        self.on_chase = None       # 追击时每帧调用
        self.on_attack = None       # 攻击时调用
        self.on_stop = None         # 停止移动时调用
        self.on_stunned = None      # 进入晕眩时调用
        
        # 缓存
        self._player = None
    
    def _find_player(self):
        """查找玩家角色"""
        if self._player:
            return self._player
        # 遍历所有 TPSCharacterBP 实例
        all_actors = ue.GameplayStatics.GetAllActorsOfClass(
            self.owner.GetWorld(),
            ue.Character
        )
        for actor in all_actors:
            if hasattr(actor, 'movement') and hasattr(actor, 'shooting'):
                self._player = actor
                return actor
        return None
    
    def _get_distance_to_player(self) -> float:
        """获取到玩家的距离"""
        player = self._find_player()
        if not player:
            return 99999.0
        return self.owner.GetDistanceTo(player)
    
    def tick(self, delta_time: float):
        """每帧更新状态机"""
        if self.state == EnemyState.DEAD:
            return
        
        # 更新冷却
        if self._attack_cooldown_timer > 0:
            self._attack_cooldown_timer -= delta_time
        if self._stun_timer > 0:
            self._stun_timer -= delta_time
        
        # 状态机
        if self.state == EnemyState.IDLE:
            self._tick_idle()
        elif self.state == EnemyState.CHASE:
            self._tick_chase(delta_time)
        elif self.state == EnemyState.ATTACK:
            self._tick_attack()
        elif self.state == EnemyState.STUNNED:
            self._tick_stunned()
    
    def _tick_idle(self):
        dist = self._get_distance_to_player()
        if dist < self.detect_range:
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: IDLE → CHASE (dist={dist:.0f})")
    
    def _tick_chase(self, delta_time: float):
        dist = self._get_distance_to_player()
        
        if dist > self.lose_range:
            self.state = EnemyState.IDLE
            if self.on_stop:
                self.on_stop()
            ue.Log(f"EnemyAI: CHASE → IDLE (lost player)")
            return
        
        if dist < self.attack_range:
            self.state = EnemyState.ATTACK
            if self.on_stop:
                self.on_stop()
            ue.Log(f"EnemyAI: CHASE → ATTACK (in range)")
            return
        
        # 追击：使用 NavMesh 移动
        if self.on_chase:
            self.on_chase()
    
    def _tick_attack(self):
        dist = self._get_distance_to_player()
        
        if dist > self.attack_range * 1.2:  # 留点容差
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: ATTACK → CHASE (out of range)")
            return
        
        if self._attack_cooldown_timer <= 0:
            if self.on_attack:
                self.on_attack()
            self._attack_cooldown_timer = self.attack_cooldown
    
    def _tick_stunned(self):
        if self._stun_timer <= 0:
            self.state = EnemyState.IDLE
            ue.Log(f"EnemyAI: STUNNED → IDLE")
    
    def set_stunned(self, duration: float):
        """进入晕眩状态"""
        self.state = EnemyState.STUNNED
        self._stun_timer = duration
        if self.on_stop:
            self.on_stop()
        if self.on_stunned:
            self.on_stunned()
        ue.Log(f"EnemyAI: → STUNNED ({duration}s)")
    
    def set_dead(self):
        """进入死亡状态"""
        self.state = EnemyState.DEAD
        if self.on_stop:
            self.on_stop()
    
    def is_in_state(self, state: EnemyState) -> bool:
        return self.state == state
```

**Step 2: Update system/__init__.py**

Add `EnemyAIComponent` to exports.

**Step 3: Verify in editor**

Run game, check no import errors.

**Step 4: Commit**

```bash
git add Content/Scripts/system/
git commit -m "feat: add EnemyAIComponent with state machine"
```

---

## Task 3: BaseEnemy

**Files:**
- Create: `Content/Scripts/enemy/__init__.py`
- Create: `Content/Scripts/enemy/base_enemy.py`
- Modify: `Content/Scripts/nepyinit.py` — register enemy classes

**Step 1: Create enemy package**

Create `Content/Scripts/enemy/__init__.py`:
```python
from .base_enemy import BaseEnemy
from .melee_enemy import MeleeEnemy
from .ranged_enemy import RangedEnemy

__all__ = ['BaseEnemy', 'MeleeEnemy', 'RangedEnemy']
```

**Step 2: Implement BaseEnemy**

Create `Content/Scripts/enemy/base_enemy.py`:
```python
# -*- encoding: utf-8 -*-
"""敌人基类"""

import ue
from system.health_component import HealthComponent
from system.enemy_ai_component import EnemyAIComponent, EnemyState


@ue.uclass()
class BaseEnemy(ue.Character):
    """
    敌人基类，使用组件组合模式
    
    子类需重写:
        _create_ai_component() — 配置AI参数
        attack()                — 攻击逻辑
    """
    
    DEFAULT_MAX_HP = 100.0
    DEATH_DESTROY_DELAY = 2.0       # 死亡后延迟销毁时间
    
    def __init_pyobj__(self):
        self.health = None
        self.ai = None
        self._player_ref = None
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        ue.Log(f"{self} ReceiveBeginPlay")
        
        # 初始化组件
        self.health = HealthComponent(self, self.DEFAULT_MAX_HP)
        self.health.on_death = self._on_death
        self.health.on_damage = self._on_damage
        
        self.ai = self._create_ai_component()
        self.ai.on_chase = self._on_chase
        self.ai.on_attack = self._on_attack
        self.ai.on_stop = self._on_stop
        
        # 角色配置
        self.bUseControllerRotationYaw = False
        
        ue.Log(f"BaseEnemy: Initialized ({self.__class__.__name__})")
    
    def _create_ai_component(self) -> EnemyAIComponent:
        """子类重写以配置AI参数"""
        return EnemyAIComponent(self)
    
    def take_damage(self, amount: float, attacker=None):
        """受到伤害"""
        if self.health and not self.health.is_dead():
            self.health.take_damage(amount, attacker)
    
    def attack(self):
        """子类重写以实现攻击逻辑"""
        pass
    
    def _on_death(self):
        """死亡回调"""
        self.ai.set_dead()
        # 禁用碰撞
        self.SetActorEnableCollision(False)
        # 延迟销毁
        ue.KismetSystemLibrary.Delay(
            self,
            self.DEATH_DESTROY_DELAY,
            ue.LatentActionInfo()
        )
        # 备选：在tick中计时销毁
        self._death_timer = self.DEATH_DESTROY_DELAY
        ue.Log(f"BaseEnemy: {self} died")
    
    def _on_damage(self, amount: float, attacker=None):
        """受伤回调 — 预留给受击特效/伤害跳字"""
        ue.Log(f"BaseEnemy: {self} took {amount} damage, HP={self.health.current_hp}")
    
    def _on_chase(self):
        """追击回调 — NavMesh寻路向玩家移动"""
        player = self.ai._find_player()
        if not player:
            return
        # 使用 AI MoveTo（需要 AIController）
        ai_controller = self.GetController()
        if ai_controller:
            ai_controller.MoveToLocation(
                player.GetActorLocation(),
                self.ai.attack_range * 0.8,
                True,
                True,
                False,
                False,
                None,
                False
            )
    
    def _on_attack(self):
        """攻击回调"""
        # 面向玩家
        player = self.ai._find_player()
        if player:
            self._face_target(player)
        self.attack()
    
    def _on_stop(self):
        """停止移动"""
        ai_controller = self.GetController()
        if ai_controller:
            ai_controller.StopMovement()
    
    def _face_target(self, target):
        """面向目标"""
        target_loc = target.GetActorLocation()
        my_loc = self.GetActorLocation()
        direction = target_loc - my_loc
        target_yaw = ue.KismetMathLibrary.DegAtan2(direction.Y, direction.X)
        self.SetActorRotation(ue.Rotator(0.0, target_yaw, 0.0), False)
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        # 更新AI
        if self.ai:
            self.ai.tick(delta_time)
        
        # 死亡延迟销毁
        if self.health and self.health.is_dead():
            if hasattr(self, '_death_timer'):
                self._death_timer -= delta_time
                if self._death_timer <= 0:
                    self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        ue.Log(f"{self} ReceiveEndPlay")
```

**Step 3: Register in nepyinit.py**

In `on_init()`, add:
```python
try:
    from enemy import MeleeEnemy, RangedEnemy
    ue.LogWarning('Enemy classes loaded successfully!')
except Exception as e:
    ue.LogError(f'Failed to load enemy classes: {e}')
```

**Step 4: Verify in editor**

- Run game, check no import errors in Output Log
- Enemy won't spawn yet (no blueprint), but imports must be clean

**Step 5: Commit**

```bash
git add Content/Scripts/enemy/ Content/Scripts/nepyinit.py
git commit -m "feat: add BaseEnemy with health and AI components"
```

---

## Task 4: MeleeEnemy

**Files:**
- Create: `Content/Scripts/enemy/melee_enemy.py`

**Step 1: Implement MeleeEnemy**

Create `Content/Scripts/enemy/melee_enemy.py`:
```python
# -*- encoding: utf-8 -*-
"""近战敌人"""

import ue
from .base_enemy import BaseEnemy
from system.enemy_ai_component import EnemyAIComponent


@ue.uclass()
class MeleeEnemy(BaseEnemy):
    """
    近战敌人 — 追到身边攻击玩家
    
    参数: detect_range=800, attack_range=150, move_speed=300
    """
    
    DEFAULT_MAX_HP = 80.0
    MELEE_DAMAGE = 15.0
    
    def _create_ai_component(self) -> EnemyAIComponent:
        return EnemyAIComponent(
            self,
            detect_range=800.0,
            attack_range=150.0,
            lose_range=1500.0,
            attack_cooldown=1.5,
            move_speed=300.0
        )
    
    def attack(self):
        """近战攻击：对范围内玩家造成伤害"""
        player = self.ai._find_player()
        if not player:
            return
        
        dist = self.GetDistanceTo(player)
        if dist > self.attack_range * 1.5:
            return
        
        # 对玩家造成伤害
        if hasattr(player, 'take_damage'):
            player.take_damage(self.MELEE_DAMAGE, self)
            ue.Log(f"MeleeEnemy: Hit player for {self.MELEE_DAMAGE} damage")
```

**Step 2: Verify in editor**

Check no import errors.

**Step 3: Commit**

```bash
git add Content/Scripts/enemy/melee_enemy.py
git commit -m "feat: add MeleeEnemy with close-range attack"
```

---

## Task 5: EnemyProjectile

**Files:**
- Create: `Content/Scripts/enemy/enemy_projectile.py`

**Step 1: Implement EnemyProjectile**

Create `Content/Scripts/enemy/enemy_projectile.py`:
```python
# -*- encoding: utf-8 -*-
"""远程敌人子弹"""

import ue


@ue.uclass()
class EnemyProjectile(ue.Actor):
    """
    远程敌人发射的子弹
    
    速度较慢，碰到玩家造成伤害
    """
    
    PROJECTILE_SPEED = 3000.0
    PROJECTILE_LIFETIME = 3.0
    PROJECTILE_DAMAGE = 10.0
    BULLET_SCALE_XY = 0.03
    BULLET_SCALE_Z = 0.12
    
    def __init_pyobj__(self):
        self.bullet_mesh = None
        self.projectile_movement = None
        self.spawn_time = 0.0
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        self.spawn_time = self.GetGameTimeSinceCreation()
        self._setup_visual()
        self._setup_movement()
        self.OnActorHit.Add(self._on_hit)
    
    def _setup_visual(self):
        self.bullet_mesh = ue.NewObject(ue.StaticMeshComponent, self, "BulletMesh")
        self.bullet_mesh.RegisterComponent()
        
        cylinder = ue.LoadObject(ue.StaticMesh, "/Engine/BasicShapes/Cylinder.Cylinder")
        if cylinder:
            self.bullet_mesh.SetStaticMesh(cylinder)
        
        self.bullet_mesh.SetWorldScale3D(ue.Vector(
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_XY,
            self.BULLET_SCALE_Z
        ))
        self.bullet_mesh.SetRelativeRotation(ue.Rotator(-90.0, 0.0, 0.0))
        
        root = self.GetRootComponent()
        if root:
            self.bullet_mesh.AttachToComponent(
                root, ue.Name("None"),
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                ue.EAttachmentRule.KeepRelative,
                False
            )
    
    def _setup_movement(self):
        self.projectile_movement = self.GetComponentByClass(ue.ProjectileMovementComponent)
        if not self.projectile_movement:
            self.projectile_movement = ue.NewObject(
                ue.ProjectileMovementComponent, self, "ProjectileMovement"
            )
            self.projectile_movement.RegisterComponent()
        
        self.projectile_movement.InitialSpeed = self.PROJECTILE_SPEED
        self.projectile_movement.MaxSpeed = self.PROJECTILE_SPEED
        self.projectile_movement.bRotationFollowsVelocity = True
        self.projectile_movement.bShouldBounce = False
        
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        self.projectile_movement.Velocity = forward * self.PROJECTILE_SPEED
    
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        if not other_actor:
            return
        
        # 碰到玩家 → 造成伤害
        if hasattr(other_actor, 'take_damage'):
            other_actor.take_damage(self.PROJECTILE_DAMAGE, None)
            ue.Log(f"EnemyProjectile: Hit player for {self.PROJECTILE_DAMAGE}")
        
        self.Destroy()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        if self.GetGameTimeSinceCreation() - self.spawn_time > self.PROJECTILE_LIFETIME:
            self.Destroy()
```

**Step 2: Register in nepyinit.py**

Add to `on_init()`:
```python
try:
    from enemy.enemy_projectile import EnemyProjectile
    ue.LogWarning('EnemyProjectile loaded successfully!')
except Exception as e:
    ue.LogError(f'Failed to load EnemyProjectile: {e}')
```

**Step 3: Commit**

```bash
git add Content/Scripts/enemy/enemy_projectile.py Content/Scripts/nepyinit.py
git commit -m "feat: add EnemyProjectile for ranged enemies"
```

---

## Task 6: RangedEnemy

**Files:**
- Create: `Content/Scripts/enemy/ranged_enemy.py`

**Step 1: Implement RangedEnemy**

Create `Content/Scripts/enemy/ranged_enemy.py`:
```python
# -*- encoding: utf-8 -*-
"""远程敌人"""

import ue
from .base_enemy import BaseEnemy
from system.enemy_ai_component import EnemyAIComponent


@ue.uclass()
class RangedEnemy(BaseEnemy):
    """
    远程敌人 — 保持距离，向玩家发射子弹
    
    参数: detect_range=1500, attack_range=800, move_speed=200
    """
    
    DEFAULT_MAX_HP = 60.0
    
    def _create_ai_component(self) -> EnemyAIComponent:
        return EnemyAIComponent(
            self,
            detect_range=1500.0,
            attack_range=800.0,
            lose_range=2000.0,
            attack_cooldown=2.0,
            move_speed=200.0
        )
    
    def attack(self):
        """远程攻击：向玩家方向发射子弹"""
        player = self.ai._find_player()
        if not player:
            return
        
        # 计算朝向玩家的旋转
        my_loc = self.GetActorLocation()
        player_loc = player.GetActorLocation()
        direction = player_loc - my_loc
        target_rotation = ue.KismetMathLibrary.MakeRotFromX(direction)
        
        # 生成子弹
        world = self.GetWorld()
        from enemy.enemy_projectile import EnemyProjectile
        projectile = world.SpawnActor(EnemyProjectile, my_loc, target_rotation)
        
        if projectile:
            ue.Log(f"RangedEnemy: Fired projectile at player")
        else:
            ue.LogWarning("RangedEnemy: Failed to spawn projectile")
```

**Step 2: Commit**

```bash
git add Content/Scripts/enemy/ranged_enemy.py
git commit -m "feat: add RangedEnemy with projectile attack"
```

---

## Task 7: Bullet Damage Integration

**Files:**
- Modify: `Content/Scripts/character/bullet.py` — add damage call on enemy hit

**Step 1: Update Bullet._on_actor_hit**

In `Content/Scripts/character/bullet.py`, modify `_on_actor_hit`:
```python
def _on_actor_hit(self, self_actor, other_actor, normal_impulse, hit_result):
    if not other_actor:
        return
    
    # 碰到敌人 → 造成伤害
    if hasattr(other_actor, 'take_damage'):
        other_actor.take_damage(self.BULLET_DAMAGE, None)
        ue.Log(f"Bullet: Hit {other_actor} for {self.BULLET_DAMAGE} damage")
    
    self.Destroy()
```

**Step 2: Verify in editor**

- Run game with an enemy placed in level
- Shoot the enemy → should see damage logs
- Enemy HP should decrease until death

**Step 3: Commit**

```bash
git add Content/Scripts/character/bullet.py
git commit -m "feat: player bullets now deal damage to enemies"
```

---

## Task 8: Editor Setup & Integration

**This task requires manual editor work. No code to write.**

**Step 1: NavMesh setup**
1. In editor, add **NavMeshBoundsVolume** to the level
2. Scale it to cover the playable area
3. Press P to visualize NavMesh (green = navigable)

**Step 2: Create enemy blueprints**
1. Right-click in Content Browser → Blueprint Class → search for `MeleeEnemy` (Python class should appear)
2. Name it `BP_MeleeEnemy`
3. In the blueprint, set:
   - Mesh → SKM_Manny_Simple (or SKM_Quinn_Simple)
   - AnimBP → (assign an AnimBP or leave None for now)
   - CharacterMovement → Max Walk Speed = 300
4. Repeat for `BP_RangedEnemy` based on `RangedEnemy`

**Step 3: AIController setup**
1. Each enemy needs an AIController to use NavMesh
2. In enemy blueprint → Auto Possess AI = Placed in World or Spawned
3. AI Controller Class = AIController (default)

**Step 4: Collision configuration**
1. Bullet (Projectile) → Collision Preset: Custom
   - Block: WorldStatic, WorldDynamic
   - Overlap: Pawn (to detect hits)
2. Enemy → Collision Preset: Pawn (default should work)

**Step 5: Place enemies in level**
1. Drag BP_MeleeEnemy and BP_RangedEnemy into the level
2. Run the game and verify:
   - Enemies detect player and chase
   - MeleeEnemy runs to player and attacks
   - RangedEnemy stays back and shoots
   - Player can kill enemies with bullets
   - Enemies disappear after death

**Step 6: Commit**

```bash
git add Content/
git commit -m "feat: editor setup - NavMesh, enemy blueprints, collision config"
```

---

## Notes

- **NavMesh MoveTo**: The `_on_chase` callback uses `AIController.MoveToLocation()`. If NePy doesn't expose this, fallback to simple `AddMovementInput()` toward player direction (less accurate but works without NavMesh).
- **Death animation**: Currently just disappears. AnimMontage for death can be added later.
- **Stun**: `set_stunned()` is implemented but not yet triggered (will be used by magic arrow in #5).
- **No unit tests**: UE/NePy projects don't have a test framework. All verification is done by running in editor and checking Output Log.
