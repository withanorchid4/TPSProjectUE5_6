# -*- encoding: utf-8 -*-
"""角色基类"""

import ue
from .movement import MovementComponent
from .camera import CameraComponent
from .shooting import ShootingComponent
from system.health_component import HealthComponent
from system.buff_component import BuffComponent
from system.audio_manager import AudioManager


@ue.uclass()
class BaseCharacter(ue.Character):
    
    DEFAULT_MAX_HP = 100.0
    """
    角色基类，使用组件组合模式
    
    子类可以继承并重写各方法来自定义行为
    """
    
    def __init_pyobj__(self):
        """初始化 Python 变量（NePy 要求用 __init_pyobj__ 代替 __init__）"""
        # 组件实例
        self.movement = None
        self.camera = None
        self.shooting = None
        self.input_handler = None
        self.health = None
        self.buff_component = None
        self.audio = None
        # 受击脉冲（延迟一帧还原）
        self._pending_hit_reset = False
        # 换弹脉冲（延迟一帧还原）
        self._pending_reload_reset = False
        self._death_timer = -1.0
        # 受伤泛红后处理
        self._damage_overlay_mpc = None
        self._damage_mat = None
        self._damage_ppv = None
        self._damage_intensity = 0.0
    
    @ue.ufunction(override=True)
    def ReceiveBeginPlay(self):
        """角色开始播放时调用"""
        ue.Log(f"{self} ReceiveBeginPlay")
        
        # 初始化组件
        self._init_components()
        
        # 初始化武器状态
        self._is_weapon_drawn = False
        self._b_switch_weapon = False
        self._switch_weapon_speed = 1.0
        self._pending_has_weapon = None  # 下一帧更新 bHasWeapon 的缓存
        self._weapon_hide_timer = 0.0   # 收枪延迟隐藏计时器
        
        # 挂载武器网格
        self._setup_weapon_mesh()
        
        # 初始化受伤泛红后处理材质
        self._init_damage_overlay()
        
        # 标记初始化完成（防止Tick在BeginPlay之前执行）
        self._initialized = True
    
    def _init_components(self):
        """初始化所有组件"""
        # 创建血量组件
        self.health = HealthComponent(self, self.DEFAULT_MAX_HP)
        self.health.on_death = self._on_death
        self.health.on_damage = self._on_damage
        
        # 创建移动组件
        self.movement = MovementComponent(self)
        
        # 创建摄像机组件
        self.camera = CameraComponent(self)
        self.camera.setup()
        
        # 创建射击组件
        self.shooting = ShootingComponent(self)
        
        # 创建Buff组件
        self.buff_component = BuffComponent(self)
        
        # 创建音效管理器
        self.audio = AudioManager(self)
        self.audio.play_bgm()
        
        ue.Log(f"BaseCharacter: Components initialized for {self}")
    
    def set_input_handler(self, handler):
        """
        设置输入处理器
        
        Args:
            handler: InputHandler 实例
        """
        self.input_handler = handler
        handler.set_components(self.movement, self.camera, self.shooting)
        handler.bind()
        ue.Log(f"BaseCharacter: Input handler set to {handler.__class__.__name__}")
    
    def take_damage(self, amount: float, attacker=None):
        """受到伤害"""
        if self.health and not self.health.is_dead():
            self.health.take_damage(amount, attacker)
    
    def _trigger_damage_overlay(self):
        """受伤时触发屏幕泛红后处理"""
        self._damage_intensity = 0.5
        if self._damage_overlay_mpc:
            self._damage_overlay_mpc.SetScalarParameterValue(ue.Name("DamageIntensity"), self._damage_intensity)
    
    def _init_damage_overlay(self):
        """初始化受伤泛红后处理材质（找到场景中的 PostProcessVolume 并添加材质）"""
        try:
            # 加载后处理材质
            mat = ue.LoadObject(ue.Material,
                "/Game/Materials/PostProcess/M_damageOverlay.M_damageOverlay")
            if not mat:
                ue.LogWarning("BaseCharacter: M_damageOverlay not found, damage overlay disabled")
                return

            # 创建 MID 并设置父材质
            mid = ue.NewObject(ue.MaterialInstanceDynamic, self, "DamageOverlayMID")
            if not mid:
                ue.LogWarning("BaseCharacter: Failed to create MID")
                return
            mid.Parent = mat
            mid.SetScalarParameterValue(ue.Name("DamageIntensity"), 0.0)

            # 查找场景中已有的 PostProcessVolume
            ppv_list = ue.GameplayStatics.GetAllActorsOfClass(self, ue.PostProcessVolume)
            ppv = None
            if ppv_list and len(ppv_list) > 0:
                ppv = ppv_list[0]
                ue.Log(f"BaseCharacter: Found existing PostProcessVolume '{ppv}'")
            else:
                ppv = self.GetWorld().SpawnActor(ue.PostProcessVolume,
                    ue.Vector(0, 0, 0), ue.Rotator(0, 0, 0))
                if ppv:
                    ppv.bEnabled = True
                    ppv.bUnbound = True
                    ppv.Priority = 100.0
                    ue.Log("BaseCharacter: Spawned new PostProcessVolume")

            if not ppv:
                ue.LogWarning("BaseCharacter: No PostProcessVolume available, overlay disabled")
                return

            ppv.bEnabled = True
            ppv.bUnbound = True

            # 将 MID 添加到 PPV
            ppv.AddOrUpdateBlendable(mid, 1.0)

            self._damage_overlay_mpc = mid
            self._damage_ppv = ppv
            ue.Log("BaseCharacter: Damage overlay initialized")
        except Exception as e:
            ue.LogWarning(f"BaseCharacter: Damage overlay init failed: {e}")
            self._damage_overlay_mpc = None
            self._damage_ppv = None
    
    def self_buff(self):
        """给自己添加增攻Buff（外部触发入口，按键等调用）"""
        if self.buff_component:
            success = self.buff_component.add_buff("attack_up")
            if success:
                stacks = self.buff_component.get_buff_stacks("attack_up")
                ue.LogWarning(f"BaseCharacter: ATK↑ applied (stacks={stacks})")
            return success
        return False
    
    def _on_damage(self, amount: float, attacker=None):
        """受伤回调 — 推送 bIsHit 脉冲"""
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                anim.bIsHit = True
        
        # 敌人攻击附带减攻debuff
        if attacker and getattr(attacker, '_is_enemy', False):
            if self.buff_component:
                self.buff_component.add_buff("attack_down")
        
        # 受伤泛红：设置后处理材质参数
        self._trigger_damage_overlay()
        
        ue.Log(f"BaseCharacter: took {amount} damage, HP={self.health.current_hp:.0f}")
    
    def _on_death(self):
        """死亡回调"""
        ue.LogWarning(f"BaseCharacter: {self} died!")
        # 禁用输入
        if self.input_handler:
            self.input_handler.unbind()
        self.SetActorEnableCollision(False)

        # 播放死亡 Montage
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                death_montage = ue.LoadObject(ue.AnimMontage,
                    "/Game/Characters/Mannequins/Anims/Death/MM_Death_Front_03_Montage.MM_Death_Front_03_Montage")
                if death_montage:
                    result = anim.Montage_Play(death_montage, 1.0)
                    if result > 0:
                        self._death_timer = result * 0.7

        # 停止移动
        movement = self.CharacterMovement
        if movement:
            movement.StopMovementImmediately()

        # 通知 GameMode 玩家死亡
        from system.game_mode import _instance as game_mode
        if game_mode and hasattr(game_mode, 'on_player_died'):
            game_mode.on_player_died()
    
    @ue.ufunction(override=True)
    def ReceiveTick(self, delta_time: float):
        """
        每帧更新
        
        Args:
            delta_time: 帧间隔时间
        """
        # 防护：ReceiveTick 可能在 ReceiveBeginPlay 之前执行
        if not getattr(self, '_initialized', False):
            return
        
        # 检查 GameMode 延迟标记，在玩家tick中创建结算Widget
        from system.game_mode import _instance as game_mode
        if game_mode and game_mode._pending_result_widget is not None:
            is_victory = game_mode._pending_result_widget
            game_mode._pending_result_widget = None
            game_mode._show_result_widget(is_victory)
        
        # 受伤泛红淡出
        if self._damage_intensity > 0:
            self._damage_intensity -= delta_time * 2.0  # 0.5秒淡出
            if self._damage_intensity <= 0:
                self._damage_intensity = 0.0
            if self._damage_overlay_mpc:
                self._damage_overlay_mpc.SetScalarParameterValue(ue.Name("DamageIntensity"), self._damage_intensity)
        
        # 死亡倒计时销毁
        if self._death_timer > 0:
            self._death_timer -= delta_time
            if self._death_timer <= 0:
                self._death_timer = -1.0
                self.Destroy()
                return
        
        # 更新摄像机组件（平滑过渡）
        if self.camera:
            self.camera.tick(delta_time)
        
        # 更新输入处理器（移动、射击等）
        if self.input_handler:
            self.input_handler.tick(delta_time)
        
        # 更新Buff组件（倒计时+过期移除）
        if self.buff_component:
            self.buff_component.tick(delta_time)
        
        # 推送武器切换状态到动画蓝图
        self._update_weapon_anim_state()
        
        # 下一帧还原 bIsHit（延迟一帧，确保 AnimBP 能读到 True）
        mesh = self.GetMesh()
        if mesh:
            anim = mesh.GetAnimInstance()
            if anim:
                if self._pending_hit_reset:
                    anim.bIsHit = False
                    self._pending_hit_reset = False
                elif anim.bIsHit:
                    self._pending_hit_reset = True
                
                # 还原 bIsReloading（延迟一帧，确保 AnimBP 能读到 True）
                if self._pending_reload_reset:
                    anim.bIsReloading = False
                    self._pending_reload_reset = False
                elif anim.bIsReloading:
                    self._pending_reload_reset = True
        
        # 收枪延迟隐藏计时
        if self._weapon_hide_timer > 0.0:
            self._weapon_hide_timer -= delta_time
            if self._weapon_hide_timer <= 0.0:
                self._weapon_hide_timer = 0.0
                if hasattr(self, '_weapon_mesh') and self._weapon_mesh:
                    self._weapon_mesh.SetVisibility(False)
    
    def switch_weapon(self):
        """切换持枪/收枪状态（E键调用）"""
        # 基于切换前的状态设置动画速度
        if self._is_weapon_drawn:
            self._switch_weapon_speed = -1.0  # 持枪→收枪
        else:
            self._switch_weapon_speed = 1.0   # 收枪→持枪
        
        # 切换持枪状态
        self._is_weapon_drawn = not self._is_weapon_drawn
        
        # 触发切换脉冲
        self._b_switch_weapon = True
        
        # 缓存：下一帧再更新 bHasWeapon
        self._pending_has_weapon = self._is_weapon_drawn
        
        # 切换武器可见性
        if hasattr(self, '_weapon_mesh') and self._weapon_mesh:
            if self._is_weapon_drawn:
                # 拿枪：立即显示
                self._weapon_mesh.SetVisibility(True)
            else:
                # 收枪：延迟0.8s后隐藏
                self._weapon_hide_timer = 1.8
        
        state = "持枪" if self._is_weapon_drawn else "收枪"
        ue.Log(f"BaseCharacter: 切换武器 → {state}, Speed={self._switch_weapon_speed}")
    
    def _update_weapon_anim_state(self):
        """将武器状态推送到动画蓝图变量"""
        mesh = self.GetMesh()
        if not mesh:
            return
        
        anim_instance = mesh.GetAnimInstance()
        if not anim_instance:
            return
        
        try:
            anim_instance.bSwitchWeapon = self._b_switch_weapon
            anim_instance.SwitchWeaponSpeed = self._switch_weapon_speed
        except Exception as e:
            ue.LogWarning(f"BaseCharacter: Failed to set AnimBP vars: {e}")
        
        # 下一帧：更新 bHasWeapon
        if self._pending_has_weapon is not None:
            try:
                anim_instance.bHasWeapon = self._pending_has_weapon
            except Exception as e:
                ue.LogWarning(f"BaseCharacter: Failed to set bHasWeapon: {e}")
            self._pending_has_weapon = None
        
        # bSwitchWeapon 仅保持一帧，之后重置
        if self._b_switch_weapon:
            self._b_switch_weapon = False
    
    def _setup_weapon_mesh(self):
        """查找或创建武器网格"""
        # 优先从蓝图找已添加的 WeaponMesh 组件
        self._weapon_mesh = None
        for comp in self.GetComponentsByClass(ue.StaticMeshComponent):
            if comp.GetName() == "WeaponMesh":
                self._weapon_mesh = comp
                break
        
        if self._weapon_mesh:
            self._weapon_mesh.SetVisibility(False)
            ue.Log("BaseCharacter: Found existing WeaponMesh component")
            return
        
        # 蓝图中没有则运行时创建
        mesh = self.GetMesh()
        if not mesh:
            ue.LogWarning("BaseCharacter: No mesh, cannot attach weapon")
            return
        
        self._weapon_mesh = ue.NewObject(ue.StaticMeshComponent, self, "WeaponMesh")
        self._weapon_mesh.RegisterComponent()
        
        rifle_mesh = ue.LoadObject(ue.StaticMesh, "/Game/Weapons/Meshes/AR4/SM_AR4.SM_AR4")
        if rifle_mesh:
            self._weapon_mesh.SetStaticMesh(rifle_mesh)
        else:
            ue.LogWarning("BaseCharacter: AR4 mesh not found at /Game/Weapons/Meshes/AR4/SM_AR4")
        
        self._weapon_mesh.AttachToComponent(
            mesh,
            ue.Name("hand_r"),
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            ue.EAttachmentRule.KeepRelative,
            False
        )
        # 枪口朝向修正：旋转90°使枪指向前方
        self._weapon_mesh.SetRelativeRotation(
            ue.Rotator(0.0, 90.0, 0.0), False
        )
        self._weapon_mesh.SetVisibility(False)
        ue.Log("BaseCharacter: Weapon mesh created and attached to hand_r")
    
    @ue.ufunction(override=True)
    def ReceiveEndPlay(self, end_play_reason):
        """角色结束播放时调用"""
        if self.input_handler:
            self.input_handler.unbind()
        ue.Log(f"{self} ReceiveEndPlay")