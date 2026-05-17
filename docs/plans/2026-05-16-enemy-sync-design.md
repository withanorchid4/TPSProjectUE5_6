# 敌人主机权威同步设计

## 概述

采用主机权威模式同步敌人状态。先进入游戏的玩家自动成为主机，主机运行敌人 AI 并 60fps 广播全量敌人状态。非主机客户端禁用本地 AI，仅根据网络数据驱动敌人表现。任何客户端都可以对敌人造成伤害（本地即时反馈 + 发 CsEnemyEvent），主机为最终权威。主机掉线时游戏结束。

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 同步模式 | 主机权威 | 工作量适中，无需服务端重写 AI |
| 主机确定 | 第一个进游戏的玩家 | 最简单，无需选举 |
| 同步频率 | 60fps | 敌人数量不多，带宽可接受 |
| 伤害处理 | 客户端本地即时 + CsEnemyEvent 广播 | 保证操作手感 |
| 主机掉线 | 游戏结束 | 简单处理，不做主机迁移 |
| 敌人 ID | 主机按位置排序分配 1,2,3... | 关卡相同+初始位置相同，排序一致 |

## 数据流

### 主机帧循环

```
枚举所有 BaseEnemy
→ 构建 CsEnemyStates(每个: id, type, location, rotation, hp, ai_state, is_attacking)
→ 服务器 → ScEnemyStates → 广播给非主机客户端
```

### 非主机客户端接收

```
按 enemy_id 找到本地 enemy → 设置位置/旋转/HP/AI状态/攻击动画
敌人已死亡但本地还活着 → 强制对齐（播死亡动画+销毁）
```

### 伤害事件

```
任何客户端击中敌人
→ 本地 take_damage (即时反馈)
→ CsEnemyEvent → 服务器广播 ScEnemyEvent
→ 所有客户端(含主机)收到后对本地敌人 take_damage
→ 主机状态为权威：如果冲突（敌人已死但客户端还活着），主机下一帧的状态更新会覆盖
```

## 主机确定

- 服务端记录第一个进入 IN_GAME 状态的 session 为 host
- ScEnterGame 新增 `bool is_host = 5` 字段
- 客户端根据 is_host 决定是否启用 AI + 上报敌人状态

## 敌人 ID 分配

- 主机 ReceiveBeginPlay 时调用 `GetAllActorsOfClass(BaseEnemy)`
- 按 GetActorLocation 排序（先 X 升序，再 Y，再 Z）
- 顺序分配 enemy_id = 1, 2, 3...
- 非主机客户端用同样的排序算法分配 ID，因为关卡相同+初始位置相同，排序结果一致
- 敌人死亡后 ID 不回收，新分配的敌人继续递增

## Proto 变更

### 修改 EnemyState — 扩展 AI 状态字段

```protobuf
message EnemyState {
  int32   enemy_id     = 1;
  int32   enemy_type   = 2;  // 0=近战, 1=远程
  Vector3 location      = 3;
  int32   hp            = 4;
  int32   ai_state      = 5;  // 0=idle, 1=chase, 2=attack, 3=stunned, 4=dead
  bool    is_attacking  = 6;  // 攻击动画状态
  Rotator rotation      = 7;  // 朝向
}
```

### 修改 ScEnterGame — 增加 is_host

```protobuf
message ScEnterGame {
  repeated PlayerState players    = 1;
  repeated EnemyState  enemies    = 2;
  repeated ItemState   items      = 3;
  PlayerState          self_state = 4;
  bool                 is_host   = 5;  // 是否为主机
}
```

### 新增消息 + MsgId

```protobuf
// MsgId
CS_ENEMY_STATES = 240;
SC_ENEMY_STATES = 241;

message CsEnemyStates {
  repeated EnemyState enemies = 1;
}

message ScEnemyStates {
  repeated EnemyState enemies = 1;
}
```

## 关键文件改动

| 文件 | 改动 |
|------|------|
| `tps.proto` (客户端+服务端) | EnemyState 扩展字段；ScEnterGame 加 is_host；新增 CsEnemyStates/ScEnemyStates + MsgId |
| `server/game_world.py` | 记录 host_player_id；提供 is_host() 方法 |
| `server/msg_handler.py` | handle_select_character 设置 host；handle_enemy_states 转发；ScEnterGame 填 is_host + enemies |
| `server/client_session.py` | 无需改动 |
| `base_enemy.py` | 加 enemy_id 属性；is_network_driven 标志；非主机禁用 AI ticker；apply_network_state() |
| `melee_enemy.py` | 适配网络驱动模式 |
| `ranged_enemy.py` | 适配网络驱动模式 |
| `enemy_ai_component.py` | 非主机模式下 ticker 不执行 |
| `base_character.py` | 注册 on_enemy_states 回调；_on_net_enemy_states 驱动本地敌人 |
| `network_manager.py` | send_enemy_states()；_on_enemy_states 解析；注册回调 |
| `game_mode.py` | 记录 is_host 状态 |

## 边界情况

- **主机掉线**：服务端检测到 host session 断开后，通知所有客户端游戏结束
- **新客户端加入**：ScEnterGame.enemies 包含所有敌人当前状态，客户端按位置排序分配 ID 后映射
- **敌人死亡**：主机状态覆盖——如果主机判定敌人已死但客户端还活着，下一帧状态更新中 hp=0 + ai_state=4 强制对齐
- **伤害冲突**：客户端本地即时反馈 + CsEnemyEvent 广播；如果主机判定敌人已死，后续伤害事件忽略（take_damage 检查 is_dead）
