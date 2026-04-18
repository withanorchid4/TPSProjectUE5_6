# -*- encoding: utf-8 -*-
"""射击组件"""

import ue


class ShootingComponent:
    """处理射击逻辑"""
    
    FIRE_MODE_SINGLE = "single"  # 点射
    FIRE_MODE_AUTO = "auto"      # 连射
    
    SINGLE_FIRE_RATE = 0.15      # 点射间隔（秒）
    AUTO_FIRE_RATE = 0.1         # 连射间隔（秒）
    MUZZLE_OFFSET_FORWARD = 80.0    # 枪口前方偏移（从武器位置沿枪管方向）
    
    MAX_AMMO = 30                  # 弹夹容量
    TOTAL_AMMO = 90                # 总弹药上限（3个弹夹）
    RELOAD_DURATION = 2.0          # 换弹时长（秒）
    
    def __init__(self, owner):
        self.owner = owner
        self.bullet_class = None
        self.fire_rate = self.SINGLE_FIRE_RATE
        self.last_fire_time = -999.0
        
        # 射击模式
        self._fire_mode = self.FIRE_MODE_SINGLE
        self._is_firing = False
        
        # 弹药
        self.current_ammo = self.MAX_AMMO
        self.total_ammo = self.TOTAL_AMMO
        
        # 换弹
        self._is_reloading = False
        self._reload_timer = 0.0
    
    def set_bullet_class(self, bullet_class):
        """
        设置子弹类
        
        Args:
            bullet_class: 子弹 Actor 类
        """
        self.bullet_class = bullet_class
        ue.Log(f"ShootingComponent: Bullet class set to: {bullet_class}")
    
    def _get_current_time(self) -> float:
        """获取当前游戏时间"""
        return self.owner.GetGameTimeSinceCreation()
    
    def can_shoot(self) -> bool:
        """检查是否可以射击"""
        if not self.bullet_class:
            ue.LogWarning("ShootingComponent: No bullet class set!")
            return False
        
        # 没拿枪不能射击
        if not getattr(self.owner, '_is_weapon_drawn', False):
            return False
        
        if self._is_reloading:
            return False
        
        if self.current_ammo <= 0:
            if self.total_ammo > 0:
                self.start_reload()
            return False
        
        current_time = self._get_current_time()
        return (current_time - self.last_fire_time) >= self.fire_rate
    
    def start_firing(self):
        """开始射击（按住鼠标左键）"""
        self._is_firing = True
        
        # 立即发射第一颗子弹
        self.shoot()
    
    def stop_firing(self):
        """停止射击（松开鼠标左键）"""
        self._is_firing = False
    
    def toggle_fire_mode(self):
        """切换射击模式（点射/连射）"""
        if self._fire_mode == self.FIRE_MODE_SINGLE:
            self._fire_mode = self.FIRE_MODE_AUTO
            self.fire_rate = self.AUTO_FIRE_RATE
        else:
            self._fire_mode = self.FIRE_MODE_SINGLE
            self.fire_rate = self.SINGLE_FIRE_RATE
        
        mode_name = "连射" if self._fire_mode == self.FIRE_MODE_AUTO else "点射"
        ue.LogWarning(f"ShootingComponent: 切换为{mode_name}模式")
    
    def get_fire_mode(self) -> str:
        """获取当前射击模式"""
        return self._fire_mode
    
    def is_auto_mode(self) -> bool:
        """是否为连射模式"""
        return self._fire_mode == self.FIRE_MODE_AUTO
    
    def tick(self, delta_time: float):
        """
        每帧更新（用于连发射击 + 换弹计时）
        """
        # 连发射击
        if self._is_firing:
            self.shoot()
        
        # 换弹计时
        if self._is_reloading:
            self._reload_timer -= delta_time
            if self._reload_timer <= 0.0:
                self._finish_reload()
    
    TRACE_DISTANCE = 100000.0  # 射线检测距离
    FALLBACK_DISTANCE = 2000.0  # 未命中时的目标距离（避免远点导致角度偏差）

    def shoot(self):
        """执行射击"""
        if not self.can_shoot():
            return False
        
        controller = self.owner.GetController()
        if not controller:
            ue.LogWarning("ShootingComponent: No controller!")
            return False
        
        # 起点：手骨世界位置 + 枪口方向偏移
        mesh = self.owner.GetMesh()
        if not mesh:
            ue.LogWarning("ShootingComponent: No mesh!")
            return False
        hand_location = mesh.GetSocketLocation(ue.Name("hand_r"))
        
        # 从摄像机位置沿准星方向射线，找命中点
        cam_location = self.owner.camera.camera.GetWorldLocation() if (self.owner.camera and self.owner.camera.camera) else self.owner.GetActorLocation()
        fire_rotation = controller.GetControlRotation()
        cam_forward = ue.KismetMathLibrary.GetForwardVector(fire_rotation)
        trace_end = cam_location + cam_forward * self.TRACE_DISTANCE
        
        hit_result = ue.KismetSystemLibrary.LineTraceSingle(
            self.owner, cam_location, trace_end,
            ue.ETraceTypeQuery.TraceTypeQuery1,
            False, [self.owner],
            0,  # EDrawDebugTrace::None
            True,  # bIgnoreSelf
            ue.LinearColor(1.0, 0.0, 0.0, 1.0),
            ue.LinearColor(0.0, 1.0, 0.0, 1.0),
            0.0
        )
        
        # 返回值是 (bool, HitResult) 元组
        if isinstance(hit_result, tuple) and len(hit_result) == 2:
            b_hit, hit_data = hit_result
        else:
            b_hit = False
            hit_data = None
        
        # 目标点：命中点或射线上合理距离的点
        if b_hit and hit_data and hasattr(hit_data, 'bBlockingHit') and hit_data.bBlockingHit:
            target_point = hit_data.Location
        else:
            # 未命中时取合理距离，避免10万单位远点导致枪口→目标方向偏差过大
            target_point = cam_location + cam_forward * self.FALLBACK_DISTANCE
        
        # 子弹方向：从枪口指向目标点
        aim_direction = target_point - hand_location
        aim_length = ue.KismetMathLibrary.VSize(aim_direction)
        if aim_length > 0.0:
            aim_direction = aim_direction * (1.0 / aim_length)
        
        fire_rotation = ue.KismetMathLibrary.MakeRotFromX(aim_direction)
        spawn_location = hand_location + aim_direction * self.MUZZLE_OFFSET_FORWARD
        
        # 生成子弹
        world = self.owner.GetWorld()
        bullet = world.SpawnActor(
            self.bullet_class,
            spawn_location,
            fire_rotation
        )
        
        if bullet:
            bullet.SetOwner(self.owner)
            # 将玩家的攻击倍率传递给子弹
            if hasattr(self.owner, 'buff_component') and self.owner.buff_component:
                bullet.damage_multiplier = self.owner.buff_component.get_attack_multiplier()
            self.last_fire_time = self._get_current_time()
            self.current_ammo -= 1
            ue.Log(f"ShootingComponent: Shot fired (ammo={self.current_ammo}/{self.MAX_AMMO})")
            return True
        else:
            ue.LogWarning("ShootingComponent: Failed to spawn bullet!")
            return False
    
    def is_firing(self) -> bool:
        """检查是否正在射击"""
        return self._is_firing
    
    def fire_magic_arrow(self):
        """发射魔法箭"""
        from character.magic_arrow import MagicArrow
        
        controller = self.owner.GetController()
        if not controller:
            return
        
        # 使用摄像机方向
        fire_rotation = controller.GetControlRotation()
        actor_location = self.owner.GetActorLocation()
        
        forward = ue.KismetMathLibrary.GetForwardVector(fire_rotation)
        spawn_location = actor_location + forward * 100.0
        
        world = self.owner.GetWorld()
        arrow = world.SpawnActor(MagicArrow, spawn_location, fire_rotation)
        
        if arrow:
            arrow.SetOwner(self.owner)
            ue.LogWarning("ShootingComponent: Magic arrow fired!")
        else:
            ue.LogWarning("ShootingComponent: Failed to spawn magic arrow!")
    
    def start_reload(self):
        """开始换弹"""
        if self._is_reloading:
            return
        if self.current_ammo >= self.MAX_AMMO:
            return
        if self.total_ammo <= 0:
            return
        
        self._is_reloading = True
        self._reload_timer = self.RELOAD_DURATION
        
        # 推送 bIsReloading 脉冲到 AnimBP
        mesh = self.owner.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                anim.bIsReloading = True
        
        ue.LogWarning(f"ShootingComponent: Reloading... ({self.RELOAD_DURATION}s)")
    
    def _finish_reload(self):
        """换弹完成"""
        self._is_reloading = False
        self._reload_timer = 0.0
        # 从总弹药中补充弹夹，不够则补剩余量
        needed = self.MAX_AMMO - self.current_ammo
        refill = min(needed, self.total_ammo)
        self.current_ammo += refill
        self.total_ammo -= refill
        ue.LogWarning(f"ShootingComponent: Reload complete! ammo={self.current_ammo}, reserve={self.total_ammo}")
    
    def is_reloading(self) -> bool:
        """是否正在换弹"""
        return self._is_reloading
    
    def add_ammo(self, amount: int):
        """补充总弹药"""
        self.total_ammo += amount
        ue.LogWarning(f"ShootingComponent: +{amount} ammo (reserve={self.total_ammo})")
