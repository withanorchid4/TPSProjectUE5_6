# 魔法箭命中同步设计

## 概述

本地玩家魔法箭命中后，将命中事件广播给其他客户端。接收方销毁对应的视觉魔法箭，并在 AOE 位置播放特效 + 3D 音效。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 箭矢标识 | 每玩家递增序列号 (`player_id * 1000 + seq`) | 简单、确定、无碰撞 |
| 协议设计 | 新增独立消息 (CsMagicArrowHit / ScMagicArrowHitResult) | "开火"和"命中"是不同事件，语义清晰 |
| 受击敌人动画 | 不处理 | 由敌人受击系统单独处理 |
| AOE 音效 | 接收方在 AOE 位置播放 play_magic_arrow 3D 音效 | 完整的视听体验 |

## Proto 协议变更

### 修改 CsShoot — 增加 arrow_id

```protobuf
message CsShoot {
    int32 weapon_type = 1;  // 0=gun, 1=magic_arrow
    Vector3 hit_location = 2;
    int32 arrow_id = 3;     // 魔法箭专用，枪械为0
}
```

### 修改 ScShootResult — 增加 arrow_id

```protobuf
message ScShootResult {
    int32 player_id = 1;
    int32 weapon_type = 2;
    Vector3 hit_location = 3;
    int32 arrow_id = 4;     // 魔法箭专用
}
```

### 新增 CsMagicArrowHit — 本地箭命中时发送

```protobuf
message CsMagicArrowHit {
    int32 arrow_id = 1;
    Vector3 aoe_location = 2;
}
```

### 新增 ScMagicArrowHitResult — 服务端广播

```protobuf
message ScMagicArrowHitResult {
    int32 player_id = 1;
    int32 arrow_id = 2;
    Vector3 aoe_location = 3;
}
```

## Arrow ID 管理

- `shooting.py` 维护 `_next_arrow_id` 计数器，从 1 递增
- 发射魔法箭时：`arrow_id = player_id * 1000 + _next_arrow_id`
- 将 `arrow_id` 传给 SpawnActor 后的 MagicArrow 实例
- 同步传给 CsShoot

## 数据流

### 发射阶段

```
ShootingComponent.fire_magic_arrow()
  → 分配 arrow_id
  → arrow = SpawnActor(MagicArrow); arrow.arrow_id = arrow_id
  → CsShoot(weapon_type=1, hit_location, arrow_id) → 服务器

服务器 → ScShootResult(player_id, weapon_type=1, hit_location, arrow_id) → 广播

接收方 RemotePlayer.play_shoot()
  → visual_arrow = SpawnActor(MagicArrow, visual_only=True)
  → visual_arrow.arrow_id = arrow_id
  → 记录到 self._active_arrows[arrow_id] = visual_arrow
```

### 命中阶段

```
MagicArrow._on_overlap() / _on_hit()
  → CsMagicArrowHit(arrow_id, aoe_location) → 服务器

服务器 → ScMagicArrowHitResult(player_id, arrow_id, aoe_location) → 广播

接收方 BaseCharacter._on_net_magic_arrow_hit()
  → 从 remote_player._active_arrows 中按 arrow_id 找到 visual_arrow
  → visual_arrow 立即销毁
  → 在 aoe_location 播放 AOE Niagara 特效 + play_magic_arrow 3D 音效
```

## 关键文件改动

| 文件 | 改动 |
|------|------|
| `tps.proto` (客户端+服务端) | CsShoot/ScShootResult 加 arrow_id；新增 CsMagicArrowHit/ScMagicArrowHitResult |
| `shooting.py` | 加 `_next_arrow_id` 计数器；fire_magic_arrow 分配 ID 并传给 arrow + CsShoot |
| `magic_arrow.py` | 加 `arrow_id` 属性；命中时发 CsMagicArrowHit；销毁时从 _active_arrows 移除 |
| `remote_player.py` | 加 `_active_arrows` 字典；play_shoot 时记录；提供 `destroy_arrow(arrow_id)` 方法 |
| `base_character.py` | 加 `_on_net_magic_arrow_hit` 回调 |
| `network_manager.py` | 加 `send_magic_arrow_hit()`；解析 ScMagicArrowHitResult |
| `server/` | 处理 CsMagicArrowHit → 广播 ScMagicArrowHitResult |

## 边界情况

- **箭未命中就超时/超距**：只在本机销毁，不发网络消息；接收方 visual_arrow 也自然超时销毁
- **发射方自己看到的 AOE**：本地箭命中后仍正常播放特效+音效+晕眩，不需要走网络
- **_active_arrows 清理**：visual_arrow 被销毁时（超时/超距/命中）都需从字典移除，避免泄漏
