# -*- encoding: utf-8 -*-
"""敌人AI组件 - Python状态机 + AddMovementInput直线移动 + 巡逻逻辑"""

import ue
from enum import Enum


class EnemyState(Enum):
    IDLE = "idle"
    CHASE = "chase"
    ATTACK = "attack"
    STUNNED = "stunned"
    DEAD = "dead"


class _PatrolPhase(Enum):
    """IDLE状态内部的巡逻子阶段"""
    MOVE = "move"   # 走向巡逻点
    WAIT = "wait"   # 到达后等待


class EnemyAIComponent:
    """
    敌人AI状态机组件
    
    状态: IDLE(巡逻) → CHASE → ATTACK → STUNNED → DEAD
    
    IDLE状态下敌人会在出生点附近巡逻：
    - PATROL_MOVE: NavMesh随机取可达点，AddMovementInput直线走向目标
    - PATROL_WAIT: 到达后等待几秒，再取下一个点
    - 任何时刻检测到玩家进detect_range立刻切CHASE
    
    用法:
        ai = EnemyAIComponent(owner, detect_range=800, attack_range=150, ...)
        ai.on_chase = lambda: owner.move_to_player()
        ai.on_attack = lambda: owner.attack()
        ai.on_patrol_move = lambda target: owner.patrol_move(target)
        ai.on_patrol_stop = lambda: owner.stop_move()
        ai.tick(delta_time)
    """
    
    def __init__(self, owner,                  detect_range=2000.0, attack_range=150.0,
                 lose_range=4000.0, attack_cooldown=1.5, move_speed=300.0,
                 patrol_radius=500.0, patrol_wait_time=2.5):
        self.owner = owner
        self.state = EnemyState.IDLE
        
        # 参数
        self.detect_range = detect_range
        self.attack_range = attack_range
        self.lose_range = lose_range
        self.attack_cooldown = attack_cooldown
        self.move_speed = move_speed
        self.patrol_radius = patrol_radius
        self.patrol_wait_time = patrol_wait_time
        
        # 巡逻状态
        self._patrol_phase = _PatrolPhase.MOVE
        self._patrol_wait_timer = 0.0
        self._patrol_target = None      # 当前巡逻目标点
        self._spawn_location = None     # 出生位置（首次tick时记录）
        
        # 计时器
        self._attack_cooldown_timer = 0.0
        self._stun_timer = 0.0
        
        # 回调
        self.on_chase = None
        self.on_attack = None
        self.on_stop = None
        self.on_stunned = None
        self.on_stun_end = None
        self.on_patrol_move = None      # 巡逻移动回调 (target_location)
        self.on_patrol_stop = None      # 巡逻停止回调
    
    def _find_player(self):
        """查找最近的玩家角色（含 RemotePlayer）"""
        all_actors = ue.GameplayStatics.GetAllActorsOfClass(
            self.owner.GetWorld(),
            ue.Character
        )
        closest = None
        closest_dist = float('inf')
        for actor in all_actors:
            if getattr(actor, '_is_enemy', False):
                continue
            if getattr(actor, '_destroyed', False):
                continue
            dist = self.owner.GetDistanceTo(actor)
            if dist < closest_dist:
                closest = actor
                closest_dist = dist
        return closest
    
    def _get_distance_to_player(self) -> float:
        """获取到玩家的距离"""
        player = self._find_player()
        if not player:
            return 99999.0
        return self.owner.GetDistanceTo(player)
    
    PATROL_MIN_DISTANCE = 100.0  # 巡逻点最小距离，太近则重取
    PATROL_MAX_Z_DELTA = 200.0   # 巡逻点与出生点最大Z差，防止NavMesh返回地下点

    def _get_random_patrol_point(self):
        """在出生点附近patrol_radius内的NavMesh上取随机可达点"""
        if self._spawn_location is None:
            return None
        nav_sys = ue.NavigationSystemV1.GetNavigationSystem(self.owner.GetWorld())
        if not nav_sys:
            return None
        for _ in range(5):
            success, point = nav_sys.GetRandomReachablePointInRadius(
                self.owner, self._spawn_location, self.patrol_radius, None, None)
            if success:
                if abs(point.Z - self._spawn_location.Z) > self.PATROL_MAX_Z_DELTA:
                    continue
                dist = ue.KismetMathLibrary.VSize(point - self.owner.GetActorLocation())
                if dist > self.PATROL_MIN_DISTANCE:
                    return point
        return None
    
    def tick(self, delta_time: float):
        """每帧更新状态机"""
        if self.state == EnemyState.DEAD:
            return
        
        # 记录出生位置（延迟到首帧，此时Actor已有正确位置）
        if self._spawn_location is None:
            self._spawn_location = self.owner.GetActorLocation()
        
        # 更新冷却
        if self._attack_cooldown_timer > 0:
            self._attack_cooldown_timer -= delta_time
        if self._stun_timer > 0:
            self._stun_timer -= delta_time
        
        # 状态机
        if self.state == EnemyState.IDLE:
            self._tick_idle(delta_time)
        elif self.state == EnemyState.CHASE:
            self._tick_chase()
        elif self.state == EnemyState.ATTACK:
            self._tick_attack()
        elif self.state == EnemyState.STUNNED:
            self._tick_stunned()
    
    def _tick_idle(self, delta_time: float):
        # 检测玩家优先级最高
        dist = self._get_distance_to_player()
        if dist < self.detect_range:
            self._stop_patrol()
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: IDLE → CHASE (dist={dist:.0f})")
            return
        
        # 巡逻逻辑
        if self._patrol_phase == _PatrolPhase.MOVE:
            self._tick_patrol_move()
        elif self._patrol_phase == _PatrolPhase.WAIT:
            self._tick_patrol_wait(delta_time)
    
    def _tick_patrol_move(self):
        """巡逻移动 — 每帧通过回调驱动AddMovementInput"""
        # 没有目标点 → 取一个新的
        if self._patrol_target is None:
            self._patrol_target = self._get_random_patrol_point()
            if self._patrol_target is None:
                return
        
        # 检查是否到达巡逻点（2维距离，忽略Z轴）
        my_loc = self.owner.GetActorLocation()
        diff = self._patrol_target - my_loc
        diff2d = ue.Vector(diff.X, diff.Y, 0.0)
        dist = ue.KismetMathLibrary.VSize(diff2d)
        if dist < 80.0:
            self._arrive_patrol_point()
            return
        
        # 每帧驱动移动
        if self.on_patrol_move:
            self.on_patrol_move(self._patrol_target)
    
    def _arrive_patrol_point(self):
        """到达巡逻点 → 切等待"""
        self._patrol_phase = _PatrolPhase.WAIT
        self._patrol_wait_timer = self.patrol_wait_time
        self._patrol_target = None
        if self.on_patrol_stop:
            self.on_patrol_stop()
    
    def _tick_patrol_wait(self, delta_time: float):
        """巡逻等待子阶段"""
        self._patrol_wait_timer -= delta_time
        if self._patrol_wait_timer <= 0:
            self._patrol_phase = _PatrolPhase.MOVE
            # 不在这里设target，让_tick_patrol_move统一处理
    
    def _stop_patrol(self):
        """停止巡逻（切换到CHASE时调用）"""
        self._patrol_phase = _PatrolPhase.MOVE
        self._patrol_target = None
        if self.on_patrol_stop:
            self.on_patrol_stop()
    
    def _tick_chase(self):
        dist = self._get_distance_to_player()
        
        if dist > self.lose_range:
            self.state = EnemyState.IDLE
            self._patrol_phase = _PatrolPhase.WAIT
            self._patrol_wait_timer = self.patrol_wait_time
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
        
        # 追击
        if self.on_chase:
            self.on_chase()
    
    def _tick_attack(self):
        dist = self._get_distance_to_player()
        
        if dist > self.attack_range * 1.2:
            self.state = EnemyState.CHASE
            ue.Log(f"EnemyAI: ATTACK → CHASE (out of range)")
            return
        
        if self._attack_cooldown_timer <= 0:
            if self.on_attack:
                self.on_attack()
            self._attack_cooldown_timer = self.attack_cooldown
    
    def _tick_stunned(self):
        if self._stun_timer <= 0:
            dist = self._get_distance_to_player()
            if dist < self.lose_range:
                self.state = EnemyState.CHASE
                if self.on_stun_end:
                    self.on_stun_end()
                ue.Log(f"EnemyAI: STUNNED → CHASE (dist={dist:.0f})")
            else:
                self.state = EnemyState.IDLE
                self._patrol_phase = _PatrolPhase.WAIT
                self._patrol_wait_timer = self.patrol_wait_time
                if self.on_stun_end:
                    self.on_stun_end()
                ue.Log(f"EnemyAI: STUNNED → IDLE (dist={dist:.0f})")
    
    def set_stunned(self, duration: float):
        """进入晕眩状态"""
        self._stop_patrol()
        self.state = EnemyState.STUNNED
        self._stun_timer = duration
        if self.on_stop:
            self.on_stop()
        if self.on_stunned:
            self.on_stunned()
        ue.Log(f"EnemyAI: → STUNNED ({duration}s)")
    
    def set_dead(self):
        """进入死亡状态"""
        self._stop_patrol()
        self.state = EnemyState.DEAD
        if self.on_stop:
            self.on_stop()
