# -*- encoding: utf-8 -*-
"""远程敌人"""

import ue
from .base_enemy import BaseEnemy
from system.enemy_ai_component import EnemyAIComponent, EnemyState


@ue.uclass()
class RangedEnemy(BaseEnemy):
    """
    远程敌人 — 保持距离，向玩家发射子弹并侧移
    
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
    
    def _on_chase(self):
        """追击时恢复移动速度"""
        movement = self.CharacterMovement
        if movement:
            movement.MaxWalkSpeed = 600.0
        super()._on_chase()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        """每帧更新 — ATTACK状态时持续侧移"""
        # ATTACK 状态下持续侧移
        # if self.ai and self.ai.state == EnemyState.ATTACK and not self._is_stunned:
        #     self._strafe()
        
        # 调用父类 Tick
        super().ReceiveTick(delta_time)
    
    def _strafe(self):
        """横向侧移"""
        player = self.ai._find_player()
        if not player:
            return
        
        my_loc = self.GetActorLocation()
        player_loc = player.GetActorLocation()
        to_player = player_loc - my_loc
        to_player.Z = 0.0
        length = ue.KismetMathLibrary.VSize(to_player)
        if length > 0.0:
            right = ue.KismetMathLibrary.GetRightVector(
                ue.Rotator(0, ue.KismetMathLibrary.MakeRotFromX(to_player).Yaw, 0)
            )
            time_val = self.GetGameTimeSinceCreation()
            side_dir = right if int(time_val) % 2 == 0 else right * -1.0
            self.AddMovementInput(side_dir, 0.5)
            # 横移速度
            movement = self.CharacterMovement
            if movement:
                movement.MaxWalkSpeed = 300.0
    
    def attack(self):
        """远程攻击：面向玩家发射子弹"""
        player = self.ai._find_player()
        if not player:
            return
        
        # 面向玩家
        self._face_target(player)
        
        # 枪口位置：身体前方80cm
        my_loc = self.GetActorLocation()
        forward = ue.KismetMathLibrary.GetForwardVector(self.GetActorRotation())
        spawn_loc = my_loc + forward * 80.0
        target_rotation = self.GetActorRotation()
        
        # 生成子弹
        from enemy.enemy_projectile import EnemyProjectile
        projectile = self.GetWorld().SpawnActor(EnemyProjectile, spawn_loc, target_rotation)
        
        if projectile:
            projectile.SetOwner(self)
            ue.Log("RangedEnemy: Fired projectile at player")
        else:
            ue.LogWarning("RangedEnemy: Failed to spawn projectile")
