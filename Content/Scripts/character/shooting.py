# -*- encoding: utf-8 -*-
"""射击组件"""

import ue


class ShootingComponent:
    """处理射击逻辑"""
    
    FIRE_MODE_SINGLE = "single"  # 点射
    FIRE_MODE_AUTO = "auto"      # 连射
    
    SINGLE_FIRE_RATE = 0.15      # 点射间隔（秒）
    AUTO_FIRE_RATE = 0.1         # 连射间隔（秒）
    
    MAX_AMMO = 30                  # 弹夹容量
    TOTAL_AMMO = 90                # 总弹药上限（3个弹夹）
    RELOAD_DURATION = 2.0          # 换弹时长（秒）
    
    def __init__(self, owner):
        self.owner = owner
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
        
        # 魔法箭ID计数器
        self._next_arrow_id = 0
    
    def _get_current_time(self) -> float:
        """获取当前游戏时间"""
        return self.owner.GetGameTimeSinceCreation()
    
    def can_shoot(self) -> bool:
        """检查是否可以射击"""
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
    
    TRACE_DISTANCE = 100000.0     # 射线检测距离
    GUN_DAMAGE = 10.0             # 枪械基础伤害
    MUZZLE_OFFSET_FORWARD = 80.0  # 枪口前方偏移

    def shoot(self):
        """执行射击（HitScan：LineTrace 射线检测）
        
        从摄像机沿准星方向射线，命中后通过 HitResult.Component (WeakPtr).Get()
        解引用拿到 Component，再 GetOwner() 拿到 Actor，直接扣血。
        """
        if not self.can_shoot():
            return False
        
        controller = self.owner.GetController()
        if not controller:
            ue.LogWarning("ShootingComponent: No controller!")
            return False
        
        mesh = self.owner.GetMesh()
        if not mesh:
            ue.LogWarning("ShootingComponent: No mesh!")
            return False
        
        # 射线参数
        cam_location = self.owner.camera.camera.GetWorldLocation() if (self.owner.camera and self.owner.camera.camera) else self.owner.GetActorLocation()
        fire_rotation = controller.GetControlRotation()
        cam_forward = ue.KismetMathLibrary.GetForwardVector(fire_rotation)
        trace_end = cam_location + cam_forward * self.TRACE_DISTANCE
        
        # === LineTrace 射线检测 ===
        hit_result = ue.KismetSystemLibrary.LineTraceSingle(
            self.owner, cam_location, trace_end,
            ue.ETraceTypeQuery.TraceTypeQuery2,
            False, [self.owner],
            0,
            True,
            ue.LinearColor(1.0, 0.0, 0.0, 1.0),
            ue.LinearColor(0.0, 1.0, 0.0, 1.0),
            0.0
        )
        
        b_hit = False
        hit_data = None
        if isinstance(hit_result, tuple) and len(hit_result) == 2:
            b_hit, hit_data = hit_result
        
        # 从 HitResult 提取命中 Actor：Component (WeakPtr) → Get() → GetOwner()
        hit_actor = None
        hit_location = cam_location + cam_forward * 2000.0  # 默认远端点
        
        if b_hit and hit_data and hasattr(hit_data, 'bBlockingHit') and hit_data.bBlockingHit:
            hit_location = hit_data.Location
            comp_ptr = hit_data.Component
            if comp_ptr and hasattr(comp_ptr, 'Get'):
                comp = comp_ptr.Get()
                if comp and hasattr(comp, 'GetOwner'):
                    hit_actor = comp.GetOwner()
        
        # 伤害计算
        damage_multiplier = 1.0
        if hasattr(self.owner, 'buff_component') and self.owner.buff_component:
            damage_multiplier = self.owner.buff_component.get_attack_multiplier()
        
        if hit_actor and hasattr(hit_actor, 'take_damage'):
            final_damage = self.GUN_DAMAGE * damage_multiplier
            hit_actor.take_damage(final_damage, self.owner)
            ue.Log(f"ShootingComponent: HitScan hit {hit_actor} for {final_damage:.1f} damage")
        
        # 视觉效果
        hand_location = mesh.GetSocketLocation(ue.Name("hand_r"))
        muzzle_location = hand_location + cam_forward * self.MUZZLE_OFFSET_FORWARD
        
        # 生成弹道轨迹弹丸（CS 风格：快速飞向命中点）
        from character.tracer_round import TracerRound
        world = self.owner.GetWorld()
        if world:
            # 从枪口指向命中点的方向，而非摄像机朝向
            tracer_dir = hit_location - muzzle_location
            tracer_rotation = ue.KismetMathLibrary.MakeRotFromX(tracer_dir)
            tracer = world.SpawnActor(TracerRound, muzzle_location, tracer_rotation)
            if tracer:
                tracer.set_target(hit_location)
        
        if hasattr(self.owner, 'audio') and self.owner.audio:
            self.owner.audio.play_gunshot(muzzle_location)
            if hit_actor:
                self.owner.audio.play_enemy_hit(hit_location)
        
        self.last_fire_time = self._get_current_time()
        self.current_ammo -= 1
        ue.Log(f"ShootingComponent: Shot fired (ammo={self.current_ammo}/{self.MAX_AMMO})")
        
        # 网络同步：发送射击事件（含命中点）
        self._send_shoot_to_server(hit_location=hit_location)
        
        return True
    
    def is_firing(self) -> bool:
        """检查是否正在射击"""
        return self._is_firing
    
    def fire_magic_arrow(self):
        """发射魔法箭"""
        from character.magic_arrow import MagicArrow
        
        controller = self.owner.GetController()
        if not controller:
            return
        
        # 和子弹一样的 LineTrace：从摄像机沿准星方向找命中点
        fire_rotation = controller.GetControlRotation()
        cam_location = self.owner.camera.camera.GetWorldLocation() if (self.owner.camera and self.owner.camera.camera) else self.owner.GetActorLocation()
        cam_forward = ue.KismetMathLibrary.GetForwardVector(fire_rotation)
        trace_end = cam_location + cam_forward * 100000.0
        
        hit_result = ue.KismetSystemLibrary.LineTraceSingle(
            self.owner, cam_location, trace_end,
            ue.ETraceTypeQuery.TraceTypeQuery2,
            False, [self.owner],
            0, True,
            ue.LinearColor(1.0, 0.0, 0.0, 1.0),
            ue.LinearColor(0.0, 1.0, 0.0, 1.0),
            0.0
        )
        
        # 确定目标点
        b_hit = False
        hit_data = None
        if isinstance(hit_result, tuple) and len(hit_result) == 2:
            b_hit, hit_data = hit_result
        
        if b_hit and hit_data and hasattr(hit_data, 'bBlockingHit') and hit_data.bBlockingHit:
            target_location = hit_data.Location
        else:
            target_location = cam_location + cam_forward * 5000.0
        
        # 从枪口位置生成，和子弹同一出发点
        mesh = self.owner.GetMesh()
        if mesh:
            hand_location = mesh.GetSocketLocation(ue.Name("hand_r"))
            spawn_location = hand_location + cam_forward * self.MUZZLE_OFFSET_FORWARD
        else:
            actor_location = self.owner.GetActorLocation()
            spawn_location = actor_location + cam_forward * 100.0
        
        arrow_dir = target_location - spawn_location
        arrow_rotation = ue.KismetMathLibrary.MakeRotFromX(arrow_dir)
        
        world = self.owner.GetWorld()
        arrow = world.SpawnActor(MagicArrow, spawn_location, arrow_rotation)
        
        if arrow:
            arrow.SetOwner(self.owner)
            
            # 分配唯一箭矢ID（per-player递增，_active_arrows是per-RemotePlayer的，无需全局唯一）
            self._next_arrow_id += 1
            arrow_id = self._next_arrow_id
            arrow.arrow_id = arrow_id
            ue.LogWarning(f"ShootingComponent: Magic arrow fired! arrow_id={arrow_id}")
            
            # 网络同步：发送魔法箭射击事件（含命中点+箭矢ID）
            self._send_shoot_to_server(hit_location=target_location, weapon_type=1, arrow_id=arrow_id)
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
        
        # 网络同步：发送换弹动作
        self._send_action_to_server("reload_start")
        
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
        
        # 网络同步：发送换弹完成动作
        self._send_action_to_server("reload_end")
        
        ue.LogWarning(f"ShootingComponent: Reload complete! ammo={self.current_ammo}, reserve={self.total_ammo}")
    
    def is_reloading(self) -> bool:
        """是否正在换弹"""
        return self._is_reloading
    
    def add_ammo(self, amount: int):
        """补充总弹药"""
        self.total_ammo += amount
        ue.LogWarning(f"ShootingComponent: +{amount} ammo (reserve={self.total_ammo})")
    
    # ─── 网络同步 ───

    def _send_shoot_to_server(self, hit_location=None, weapon_type=0, arrow_id=0):
        """发送射击事件到服务器"""
        try:
            from network.network_manager import NetworkManager
            nm = NetworkManager.get_instance()
            if nm.is_in_game:
                hit_dict = None
                if hit_location:
                    hit_dict = {
                        "x": hit_location.x,
                        "y": hit_location.y,
                        "z": hit_location.z,
                    }
                nm.send_shoot(hit_location=hit_dict, weapon_type=weapon_type, arrow_id=arrow_id)
        except Exception as e:
            ue.LogError(f"ShootingComponent: send_shoot failed: {e}")
    
    def _send_action_to_server(self, action_name):
        """发送动作同步到服务器"""
        try:
            from network.network_manager import NetworkManager
            from network.proto import tps_pb2
            nm = NetworkManager.get_instance()
            if nm.is_in_game:
                action_map = {
                    "reload_start": tps_pb2.ACTION_RELOAD_START,
                    "reload_end": tps_pb2.ACTION_RELOAD_END,
                    "aim_start": tps_pb2.ACTION_AIM_START,
                    "aim_end": tps_pb2.ACTION_AIM_END,
                }
                action_type = action_map.get(action_name)
                if action_type is not None:
                    nm.send_action(action_type)
        except Exception as e:
            ue.LogError(f"ShootingComponent: send_action failed: {e}")
