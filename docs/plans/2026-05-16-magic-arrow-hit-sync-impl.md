# 魔法箭命中同步 实现计划

> **For Codely:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 本地魔法箭命中后，广播命中事件到其他客户端，接收方销毁对应视觉箭并在 AOE 位置播放特效+音效。

**Architecture:** 新增一对 Proto 消息 (CsMagicArrowHit / ScMagicArrowHitResult)，在现有 CsShoot/ScShootResult 中增加 arrow_id 字段用于箭矢追踪。每支魔法箭分配 `player_id * 1000 + 递增序号` 作为唯一 ID。RemotePlayer 维护 `_active_arrows` 字典按 arrow_id 追踪视觉箭。

**Tech Stack:** UE5.6 NePy (Python), protobuf, TCP socket

---

### Task 1: Proto 文件变更（客户端+服务端同步修改）

**Files:**
- Modify: `Content/Scripts/network/proto/tps.proto`
- Modify: `server/proto/tps.proto`

**Step 1: 在两个 proto 文件中添加 MsgId 枚举值**

在 MsgId 枚举的 `CS_GAME_RESULT = 230` 和 `SC_GAME_RESULT = 231` 之后添加：

```protobuf
  CS_MAGIC_ARROW_HIT  = 232;
  SC_MAGIC_ARROW_HIT  = 233;
```

**Step 2: 在 CsShoot 消息中增加 arrow_id 字段**

```protobuf
message CsShoot {
  int32   weapon_type    = 1;  // 0=普通, 1=魔法箭
  Vector3 hit_location   = 2;  // 命中点世界坐标
  int32   arrow_id       = 3;  // 魔法箭专用ID（枪械为0）
}
```

**Step 3: 在 ScShootResult 消息中增加 arrow_id 字段**

```protobuf
message ScShootResult {
  int32   player_id      = 1;
  int32   weapon_type    = 2;
  Vector3 hit_location   = 3;  // 命中点世界坐标
  int32   arrow_id       = 4;  // 魔法箭专用ID
}
```

**Step 4: 在文件末尾添加新消息定义**

```protobuf
// ============ 魔法箭命中 ============
message CsMagicArrowHit {
  int32   arrow_id     = 1;
  Vector3 aoe_location  = 2;
}

message ScMagicArrowHitResult {
  int32   player_id    = 1;
  int32   arrow_id     = 2;
  Vector3 aoe_location  = 3;
}
```

**Step 5: 重新生成两个 pb2 文件**

客户端：
```bash
cd C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\nepy_mini_NoSC\nepy_mini\Newbie\Content\Scripts\network\proto
protoc --python_out=. tps.proto
```

服务端：
```bash
cd C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\nepy_mini_NoSC\nepy_mini\Newbie\server\proto
protoc --python_out=. tps.proto
```

**Step 6: 验证 pb2 文件包含新增字段**

```bash
python -c "from proto import tps_pb2; print(dir(tps_pb2))"
```

预期：输出中包含 `CS_MAGIC_ARROW_HIT`, `SC_MAGIC_ARROW_HIT`, `CsMagicArrowHit`, `ScMagicArrowHitResult`

---

### Task 2: shooting.py — 添加 arrow_id 计数器并在发射时分配

**Files:**
- Modify: `Content/Scripts/character/shooting.py`

**Step 1: 在 ShootingComponent.__init__ 中添加计数器**

在 `self._reload_timer = 0.0` 之后添加：

```python
        # 魔法箭ID计数器
        self._next_arrow_id = 0
```

**Step 2: 修改 fire_magic_arrow 方法，分配 arrow_id 并传给 arrow + CsShoot**

在 `if arrow:` 块内，`arrow.SetOwner(self.owner)` 之后添加 arrow_id 逻辑：

原代码（约 L249-259）：
```python
        if arrow:
            arrow.SetOwner(self.owner)
            ue.LogWarning("ShootingComponent: Magic arrow fired!")
            
            # 网络同步：发送魔法箭射击事件（含命中点）
            self._send_shoot_to_server(hit_location=target_location, weapon_type=1)
```

改为：
```python
        if arrow:
            arrow.SetOwner(self.owner)
            
            # 分配唯一箭矢ID
            self._next_arrow_id += 1
            player_id = getattr(self.owner, '_player_id', 0)
            arrow_id = player_id * 1000 + self._next_arrow_id
            arrow.arrow_id = arrow_id
            ue.LogWarning(f"ShootingComponent: Magic arrow fired! arrow_id={arrow_id}")
            
            # 网络同步：发送魔法箭射击事件（含命中点+箭矢ID）
            self._send_shoot_to_server(hit_location=target_location, weapon_type=1, arrow_id=arrow_id)
```

**Step 3: 修改 _send_shoot_to_server 方法，支持 arrow_id 参数**

原代码（约 L313-326）：
```python
    def _send_shoot_to_server(self, hit_location=None, weapon_type=0):
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
                nm.send_shoot(hit_location=hit_dict, weapon_type=weapon_type)
        except Exception as e:
            ue.LogError(f"ShootingComponent: send_shoot failed: {e}")
```

改为：
```python
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
```

---

### Task 3: network_manager.py — 支持 arrow_id + 魔法箭命中消息

**Files:**
- Modify: `Content/Scripts/network/network_manager.py`

**Step 1: 在 __init__ 中注册 ScMagicArrowHit 回调 + 添加回调属性**

在 `self._client.register_callback(tps_pb2.SC_ENEMY_EVENT, self._on_enemy_event)` 之后添加：

```python
        self._client.register_callback(tps_pb2.SC_MAGIC_ARROW_HIT, self._on_magic_arrow_hit)
```

在 `self.on_enemy_event = None` 之后添加：

```python
        self.on_magic_arrow_hit = None  # → callback(hit_dict)
```

**Step 2: 修改 send_shoot 方法，支持 arrow_id 参数**

原代码（约 L225-240）：
```python
    def send_shoot(self, hit_location=None, weapon_type=0):
        """发送射击同步 — 传武器类型 + 命中点，接收方自行模拟"""
        if not self.is_in_game:
            return

        msg = tps_pb2.CsShoot()
        msg.weapon_type = weapon_type
        if hit_location:
            if isinstance(hit_location, dict):
                msg.hit_location.x = hit_location.get("x", 0.0)
                msg.hit_location.y = hit_location.get("y", 0.0)
                msg.hit_location.z = hit_location.get("z", 0.0)
            else:
                msg.hit_location.x = float(hit_location.x)
                msg.hit_location.y = float(hit_location.y)
                msg.hit_location.z = float(hit_location.z)

        self._client.send_msg(tps_pb2.CS_SHOOT, msg.SerializeToString())
```

改为：
```python
    def send_shoot(self, hit_location=None, weapon_type=0, arrow_id=0):
        """发送射击同步 — 传武器类型 + 命中点 + 箭矢ID"""
        if not self.is_in_game:
            return

        msg = tps_pb2.CsShoot()
        msg.weapon_type = weapon_type
        msg.arrow_id = arrow_id
        if hit_location:
            if isinstance(hit_location, dict):
                msg.hit_location.x = hit_location.get("x", 0.0)
                msg.hit_location.y = hit_location.get("y", 0.0)
                msg.hit_location.z = hit_location.get("z", 0.0)
            else:
                msg.hit_location.x = float(hit_location.x)
                msg.hit_location.y = float(hit_location.y)
                msg.hit_location.z = float(hit_location.z)

        self._client.send_msg(tps_pb2.CS_SHOOT, msg.SerializeToString())
```

**Step 3: 修改 _on_shoot_result 方法，解析 arrow_id**

原代码（约 L362-384）：
```python
    def _on_shoot_result(self, msg_id, data):
        """处理射击结果广播 — player_id + weapon_type + hit_location"""
        result = tps_pb2.ScShootResult()
        result.ParseFromString(data)

        # 不处理自己的射击（本地已经处理了）
        if result.player_id == self._self_player_id:
            return

        shoot_dict = {
            "player_id": result.player_id,
            "weapon_type": result.weapon_type,
            "hit_location": {
                "x": result.hit_location.x,
                "y": result.hit_location.y,
                "z": result.hit_location.z,
            },
        }

        if self.on_shoot_result:
            try:
                self.on_shoot_result(shoot_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_shoot_result callback error: {e}")
```

改为：
```python
    def _on_shoot_result(self, msg_id, data):
        """处理射击结果广播 — player_id + weapon_type + hit_location + arrow_id"""
        result = tps_pb2.ScShootResult()
        result.ParseFromString(data)

        # 不处理自己的射击（本地已经处理了）
        if result.player_id == self._self_player_id:
            return

        shoot_dict = {
            "player_id": result.player_id,
            "weapon_type": result.weapon_type,
            "hit_location": {
                "x": result.hit_location.x,
                "y": result.hit_location.y,
                "z": result.hit_location.z,
            },
            "arrow_id": result.arrow_id,
        }

        if self.on_shoot_result:
            try:
                self.on_shoot_result(shoot_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_shoot_result callback error: {e}")
```

**Step 4: 添加 send_magic_arrow_hit 方法**

在 `send_action` 方法之后添加：

```python
    def send_magic_arrow_hit(self, arrow_id, aoe_location):
        """发送魔法箭命中事件"""
        if not self.is_in_game:
            return

        msg = tps_pb2.CsMagicArrowHit()
        msg.arrow_id = arrow_id
        if isinstance(aoe_location, dict):
            msg.aoe_location.x = aoe_location.get("x", 0.0)
            msg.aoe_location.y = aoe_location.get("y", 0.0)
            msg.aoe_location.z = aoe_location.get("z", 0.0)
        else:
            msg.aoe_location.x = float(aoe_location.x)
            msg.aoe_location.y = float(aoe_location.y)
            msg.aoe_location.z = float(aoe_location.z)

        self._client.send_msg(tps_pb2.CS_MAGIC_ARROW_HIT, msg.SerializeToString())
```

**Step 5: 添加 _on_magic_arrow_hit 回调处理**

在 `_on_enemy_event` 方法之后添加：

```python
    def _on_magic_arrow_hit(self, msg_id, data):
        """处理魔法箭命中广播"""
        result = tps_pb2.ScMagicArrowHitResult()
        result.ParseFromString(data)

        hit_dict = {
            "player_id": result.player_id,
            "arrow_id": result.arrow_id,
            "aoe_location": {
                "x": result.aoe_location.x,
                "y": result.aoe_location.y,
                "z": result.aoe_location.z,
            },
        }

        if self.on_magic_arrow_hit:
            try:
                self.on_magic_arrow_hit(hit_dict)
            except Exception as e:
                ue.LogError(f"NetworkManager: on_magic_arrow_hit callback error: {e}")
```

---

### Task 4: magic_arrow.py — 添加 arrow_id 属性 + 命中时发送网络消息

**Files:**
- Modify: `Content/Scripts/character/magic_arrow.py`

**Step 1: 在 __init_pyobj__ 中添加 arrow_id 属性**

在 `self._visual_only = False` 之后添加：

```python
        self.arrow_id = 0  # 由 ShootingComponent 在发射时分配
```

**Step 2: 修改 _on_overlap 方法，非 visual_only 时发送 CsMagicArrowHit**

原代码（约 L193-209）：
```python
    def _on_overlap(self, overlapped_actor, other_actor):
        if not other_actor or self._visual_only:
            return
        if other_actor == self.GetOwner():
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # 命中任何东西 → 播放AOE特效 + 晕眩范围内敌人
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        self._start_destroy()
```

改为：
```python
    def _on_overlap(self, overlapped_actor, other_actor):
        if not other_actor or self._visual_only:
            return
        if other_actor == self.GetOwner():
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # 命中任何东西 → 播放AOE特效 + 晕眩范围内敌人
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        
        # 网络同步：广播魔法箭命中事件
        self._send_hit_to_server()
        
        self._start_destroy()
```

**Step 3: 修改 _on_hit 方法，同样发送 CsMagicArrowHit**

原代码（约 L211-227）：
```python
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        if not other_actor or self._visual_only:
            return
        if other_actor == self.GetOwner():
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # 命中！→ 播放AOE特效 + 晕眩范围内敌人
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        self._start_destroy()
```

改为：
```python
    def _on_hit(self, self_actor, other_actor, normal_impulse, hit_result):
        if not other_actor or self._visual_only:
            return
        if other_actor == self.GetOwner():
            return
        
        # 播放魔法命中音效
        owner = self.GetOwner()
        if owner and hasattr(owner, 'audio') and owner.audio:
            owner.audio.play_magic_arrow(self.GetActorLocation())
        
        # 命中！→ 播放AOE特效 + 晕眩范围内敌人
        self._spawn_aoe_effect()
        self._stun_nearby_enemies()
        
        # 网络同步：广播魔法箭命中事件
        self._send_hit_to_server()
        
        self._start_destroy()
```

**Step 4: 添加 _send_hit_to_server 方法**

在 `_stun_nearby_enemies` 方法之后添加：

```python
    def _send_hit_to_server(self):
        """发送魔法箭命中事件到服务器"""
        if self._visual_only or self.arrow_id == 0:
            return
        try:
            from network.network_manager import NetworkManager
            nm = NetworkManager.get_instance()
            if nm.is_in_game:
                aoe_loc = self.GetActorLocation()
                nm.send_magic_arrow_hit(
                    arrow_id=self.arrow_id,
                    aoe_location={"x": aoe_loc.x, "y": aoe_loc.y, "z": aoe_loc.z}
                )
        except Exception as e:
            ue.LogError(f"MagicArrow: send_hit failed: {e}")
```

---

### Task 5: remote_player.py — 添加 _active_arrows 追踪 + destroy_arrow 方法

**Files:**
- Modify: `Content/Scripts/character/remote_player.py`

**Step 1: 在 __init_pyobj__ 中添加 _active_arrows 字典**

在 `self._initial_placed = False` 之后添加：

```python
        # 追踪活跃的视觉魔法箭 {arrow_id: MagicArrow}
        self._active_arrows = {}
```

**Step 2: 修改 play_shoot 的 else 分支（weapon_type==1），记录 arrow_id**

原代码（约 L172-193）：
```python
        else:
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            spawn_loc = hand_loc + forward * 30.0

            # 命中点：来自网络广播
            if hit_location:
                target_loc = ue.Vector(hit_location["x"], hit_location["y"], hit_location["z"])
            else:
                target_loc = spawn_loc + forward * 5000.0

            # 方向：枪口 → 命中点
            arrow_dir = target_loc - spawn_loc
            arrow_rot = ue.KismetMathLibrary.MakeRotFromX(arrow_dir)

            from character.magic_arrow import MagicArrow
            arrow = world.SpawnActor(MagicArrow, spawn_loc, arrow_rot)
            if arrow:
                arrow._visual_only = True
                arrow.SetOwner(self)
                # SpawnActor 返回后立刻禁用碰撞，防止 on_tick 0.05s 后重新启用
                if hasattr(arrow, 'collision_sphere') and arrow.collision_sphere:
                    arrow.collision_sphere.SetCollisionEnabled(0)
                    arrow.collision_sphere.SetCollisionProfileName(ue.Name("NoCollision"))
                arrow._collision_activated = True
                if hasattr(arrow, 'set_target'):
                    arrow.set_target(target_loc)
```

改为：
```python
        else:
            hand_loc = mesh.GetSocketLocation(ue.Name("hand_r"))
            spawn_loc = hand_loc + forward * 30.0

            # 命中点：来自网络广播
            if hit_location:
                target_loc = ue.Vector(hit_location["x"], hit_location["y"], hit_location["z"])
            else:
                target_loc = spawn_loc + forward * 5000.0

            # 方向：枪口 → 命中点
            arrow_dir = target_loc - spawn_loc
            arrow_rot = ue.KismetMathLibrary.MakeRotFromX(arrow_dir)

            from character.magic_arrow import MagicArrow
            arrow = world.SpawnActor(MagicArrow, spawn_loc, arrow_rot)
            if arrow:
                arrow._visual_only = True
                arrow.SetOwner(self)
                # SpawnActor 返回后立刻禁用碰撞，防止 on_tick 0.05s 后重新启用
                if hasattr(arrow, 'collision_sphere') and arrow.collision_sphere:
                    arrow.collision_sphere.SetCollisionEnabled(0)
                    arrow.collision_sphere.SetCollisionProfileName(ue.Name("NoCollision"))
                arrow._collision_activated = True
                if hasattr(arrow, 'set_target'):
                    arrow.set_target(target_loc)
                
                # 记录箭矢ID，用于后续命中时销毁
                arrow_id = kwargs.get("arrow_id", 0) if isinstance(kwargs, dict) else 0
                arrow.arrow_id = arrow_id
                if arrow_id > 0:
                    self._active_arrows[arrow_id] = arrow
```

等等，play_shoot 的参数不包含 arrow_id。需要修改 play_shoot 的签名。

**重新设计 Step 2**: 修改 play_shoot 方法签名，接受 arrow_id 参数

原 play_shoot 签名：
```python
    def play_shoot(self, weapon_type=0, hit_location=None):
```

改为：
```python
    def play_shoot(self, weapon_type=0, hit_location=None, arrow_id=0):
```

然后在 else 分支（weapon_type==1）末尾，`arrow.set_target(target_loc)` 之后添加：

```python
                # 记录箭矢ID，用于后续命中时销毁
                arrow.arrow_id = arrow_id
                if arrow_id > 0:
                    self._active_arrows[arrow_id] = arrow
```

**Step 3: 添加 destroy_arrow 方法**

在 `play_shoot` 方法之后添加：

```python
    def destroy_arrow(self, arrow_id):
        """根据 arrow_id 销毁对应的视觉魔法箭"""
        arrow = self._active_arrows.pop(arrow_id, None)
        if arrow and not arrow._destroyed if hasattr(arrow, '_destroyed') else True:
            try:
                arrow._stop_ticker()
                arrow.Destroy()
            except Exception as e:
                ue.LogWarning(f"RemotePlayer: destroy_arrow error: {e}")
```

注意：MagicArrow 没有 `_destroyed` 标志，但 _stop_ticker + Destroy 应该足够。让我检查一下。

MagicArrow 的销毁是通过 `_stop_ticker()` + `self.Destroy()` 完成的。没有 `_destroyed` 标志。所以简化为：

```python
    def destroy_arrow(self, arrow_id):
        """根据 arrow_id 销毁对应的视觉魔法箭"""
        arrow = self._active_arrows.pop(arrow_id, None)
        if arrow:
            try:
                arrow._stop_ticker()
                arrow.Destroy()
            except Exception as e:
                ue.LogWarning(f"RemotePlayer: destroy_arrow error: {e}")
```

**Step 4: 在 do_cleanup 中清理 _active_arrows**

在 `do_cleanup` 方法的 `self._destroyed = True` 之后添加：

```python
        # 清理所有活跃的视觉箭
        for aid, arrow in list(self._active_arrows.items()):
            try:
                arrow._stop_ticker()
                arrow.Destroy()
            except Exception:
                pass
        self._active_arrows.clear()
```

---

### Task 6: base_character.py — 添加魔法箭命中回调

**Files:**
- Modify: `Content/Scripts/character/base_character.py`

**Step 1: 在 _init_network 中注册 on_magic_arrow_hit 回调**

在 `self._net_manager.on_action = self._on_net_action` 之后添加：

```python
            self._net_manager.on_magic_arrow_hit = self._on_net_magic_arrow_hit
```

**Step 2: 在 ReceiveEndPlay 中清理回调**

在 `self._net_manager.on_action = None` 之后添加：

```python
            self._net_manager.on_magic_arrow_hit = None
```

**Step 3: 在 _on_net_shoot_result 中传递 arrow_id**

原代码（约 L383-390）：
```python
    def _on_net_shoot_result(self, shoot_dict):
        """网络：收到远程玩家射击，在远程玩家位置生成弹道特效"""
        pid = shoot_dict.get("player_id", "?")
        weapon = shoot_dict.get("weapon_type", 0)
        hit_loc = shoot_dict.get("hit_location")
        rp = self._remote_players.get(pid)
        if rp and not rp._destroyed:
            rp.play_shoot(weapon, hit_location=hit_loc)
        else:
            ue.Log(f"BaseCharacter: Remote player {pid} shot but no actor found")
```

改为：
```python
    def _on_net_shoot_result(self, shoot_dict):
        """网络：收到远程玩家射击，在远程玩家位置生成弹道特效"""
        pid = shoot_dict.get("player_id", "?")
        weapon = shoot_dict.get("weapon_type", 0)
        hit_loc = shoot_dict.get("hit_location")
        arrow_id = shoot_dict.get("arrow_id", 0)
        rp = self._remote_players.get(pid)
        if rp and not rp._destroyed:
            rp.play_shoot(weapon, hit_location=hit_loc, arrow_id=arrow_id)
        else:
            ue.Log(f"BaseCharacter: Remote player {pid} shot but no actor found")
```

**Step 4: 添加 _on_net_magic_arrow_hit 回调方法**

在 `_on_net_action` 方法之后添加：

```python
    def _on_net_magic_arrow_hit(self, hit_dict):
        """网络：收到魔法箭命中广播 — 销毁视觉箭 + 播放 AOE 特效+音效"""
        pid = hit_dict.get("player_id", "?")
        arrow_id = hit_dict.get("arrow_id", 0)
        aoe_loc = hit_dict.get("aoe_location")

        # 销毁远程玩家的视觉箭
        rp = self._remote_players.get(pid)
        if rp and not rp._destroyed and arrow_id > 0:
            rp.destroy_arrow(arrow_id)

        # 在 AOE 位置播放特效 + 音效
        if aoe_loc:
            aoe_location = ue.Vector(aoe_loc["x"], aoe_loc["y"], aoe_loc["z"])
            self._play_remote_magic_aoe(aoe_location)

    def _play_remote_magic_aoe(self, location):
        """在指定位置播放远程魔法箭 AOE 特效 + 音效"""
        world = self.GetWorld()
        if not world:
            return

        # AOE Niagara 特效
        aoe_system = ue.LoadObject(
            ue.NiagaraSystem,
            "/Game/Basic_VFX/Niagara/NS_Basic_6.NS_Basic_6"
        )
        if aoe_system:
            aoe_comp = ue.NewObject(ue.NiagaraComponent, self, "RemoteAOE")
            aoe_comp.RegisterComponent()
            aoe_comp.SetAsset(aoe_system)
            aoe_comp.SetWorldLocationAndRotation(location, ue.Rotator(0, 0, 0), False, False)
            aoe_comp.bAutoDestroy = True
            aoe_comp.Activate(True)
            aoe_comp.SeekToDesiredAge(0.5)

        # 3D 音效
        if hasattr(self, 'audio') and self.audio:
            self.audio.play_magic_arrow(location)
```

---

### Task 7: 服务端 — 添加魔法箭命中消息处理

**Files:**
- Modify: `server/msg_handler.py`

**Step 1: 添加 handle_magic_arrow_hit 函数**

在 `handle_game_result` 函数之后添加：

```python
def handle_magic_arrow_hit(server, session, data):
    """处理魔法箭命中 — 广播给其他玩家"""
    msg = tps_pb2.CsMagicArrowHit()
    msg.ParseFromString(data)

    pid = session.player_state.get("player_id") if session.player_state else 0

    result = tps_pb2.ScMagicArrowHitResult()
    result.player_id = pid
    result.arrow_id = msg.arrow_id
    result.aoe_location.x = msg.aoe_location.x
    result.aoe_location.y = msg.aoe_location.y
    result.aoe_location.z = msg.aoe_location.z

    return [(MsgId.SC_MAGIC_ARROW_HIT, result.SerializeToString(), None)]
```

**Step 2: 在 HANDLERS 分发表中注册**

在 `MsgId.CS_GAME_RESULT: handle_game_result,` 之后添加：

```python
    MsgId.CS_MAGIC_ARROW_HIT: handle_magic_arrow_hit,
```

---

### Task 8: 集成测试

**Step 1: 启动服务端**

```bash
cd C:\Users\zilong.luo\Desktop\netease\NeteaseDocs\nepy_mini_NoSC\nepy_mini\Newbie\server
python main.py
```

**Step 2: 启动两个客户端 PIE，测试以下场景**

1. 客户端A 发射魔法箭 → 客户端B 看到视觉箭飞出
2. 魔法箭命中 → 客户端B 看到视觉箭消失 + AOE 特效 + 音效
3. 连续发射多支箭 → 每支独立命中，互不影响
4. 箭飞出未命中（超时） → 双方各自自然销毁，无额外网络消息

**Step 3: 检查日志确认 arrow_id 正确传递**

日志中应出现：
- `ShootingComponent: Magic arrow fired! arrow_id=XXXX`
- 无异常堆栈

**Step 4: 提交**

```bash
git add -A
git commit -m "联机：魔法箭命中同步（arrow_id追踪+AOE特效+音效广播）"
```
