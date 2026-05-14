# TPS 服务端实现报告

> 日期：2026-05-14
> 状态：服务端核心功能已完成，客户端集成待开发

---

## 一、已完成文件

```
server/
├── main.py                 # 入口，创建 GameServer 监听 0.0.0.0:9999
├── game_server.py           # select 事件循环 + 连接管理 + 广播 + 断线重连
├── client_session.py       # 包解析 + 收发缓冲 + Session 状态机
├── msg_handler.py           # 9 个消息处理函数 + HANDLERS 分发表
├── game_world.py            # 在线玩家位置/血量状态管理
├── db.py                    # sqlite3 账号/角色 CRUD
├── db_init.sql              # 建表语句
├── requirements.txt         # protobuf 依赖
├── game.db                  # 运行时生成（gitignore）
├── proto/
│   ├── __init__.py
│   ├── tps.proto            # 18 种消息定义
│   └── tps_pb2.py           # protoc 编译产物
└── test_reconnect_v2.py     # 断线重连集成测试脚本
```

---

## 二、各模块实现情况

### 1. 网络层 — `client_session.py` ✅

**包格式**：`[4字节大端长度][2字节大端msg_id][protobuf body]`

| 方法 | 功能 | 状态 |
|------|------|------|
| `try_recv()` | 非阻塞 recv，返回 False 表示断线 | ✅ |
| `extract_messages()` | 从缓冲区切出完整消息 `[(msg_id, body), ...]` | ✅ |
| `send_msg(msg_id, msg_bytes)` | 打包 + sendall，失败静默 | ✅ |

**Session 状态**：`CONNECTED → LOGGED_IN → IN_GAME`

**测试**：构造双包缓冲区 `pack(100, b"hello") * 2`，`extract_messages()` 正确返回 `[(100, b"hello"), (100, b"hello")]` ✅

---

### 2. 数据库 — `db.py` ✅

| 操作 | 方法 | 状态 |
|------|------|------|
| 注册 | `register(account, password)` | ✅ 重复返回 False |
| 登录 | `login(account, password)` | ✅ 明文比对 |
| 查角色列表 | `get_characters(account)` | ✅ |
| 创建角色 | `create_character(account, char_name)` | ✅ 重名返回 None |
| 按ID查角色 | `get_character_by_id(char_id)` | ✅ |

**测试**：内存数据库全流程 register→login→create_character→get_characters 均通过 ✅

---

### 3. 游戏世界 — `game_world.py` ✅

| 操作 | 方法 | 状态 |
|------|------|------|
| 玩家进入 | `add_player(session)` | ✅ 分配递增 player_id，初始位置 (0,0,200) |
| 玩家离开 | `remove_player(player_id)` | ✅ |
| 更新位置 | `update_player_move(pid, loc, rot, sprint)` | ✅ sprint时 speed=900 |
| 查询单个 | `get_player_state(pid)` | ✅ |
| 查询全部 | `get_all_player_states()` | ✅ |

---

### 4. 消息处理 — `msg_handler.py` ✅

| MsgId | Handler | 功能 | 回复消息 | 广播消息 | 状态 |
|-------|---------|------|----------|----------|------|
| CS_LOGIN(100) | `handle_login` | 注册/登录 + 断线重连检测 | ScLoginResult | ScPlayerJoin(重连时) | ✅ |
| CS_GET_CHARACTERS(102) | `handle_get_characters` | 查角色列表 | ScCharacterList | — | ✅ |
| CS_CREATE_CHAR(104) | `handle_create_character` | 创建角色 | ScCreateResult | — | ✅ |
| CS_SELECT_CHAR(106) | `handle_select_character` | 选角进游戏 | ScEnterGame | ScPlayerJoin | ✅ |
| CS_RECONNECT_ACK(108) | `handle_reconnect_ack` | 确认重连 | — | — | ✅ |
| CS_MOVE(200) | `handle_move` | 更新位置 | — | —(主循环广播) | ✅ |
| CS_SKILL(202) | `handle_skill` | 技能释放 | — | ScSkillResult | ✅ |
| CS_PICKUP(204) | `handle_pickup` | 道具拾取 | — | ScPickupResult | ✅ |
| CS_SHOOT(206) | `handle_shoot` | 射击 | — | ScShootResult | ✅ |

---

### 5. 主循环 — `game_server.py` ✅

**select 事件循环**（每帧 ~33ms）：

```
select(all_sockets, timeout=0.033)
  ├─ listen_socket 可读 → accept → 创建 ClientSession
  ├─ 客户端 socket 可读 → try_recv → extract_messages → _dispatch
  │                       └─ 返回 False → _on_disconnect
  ├─ _broadcast_world_state()      每帧广播 ScPlayerStates
  └─ _check_expired_reconnects()   每帧检查5分钟超时
```

**广播机制**：
- **位置广播**：每帧序列化一次 ScPlayerStates，发给所有 IN_GAME 客户端
- **事件广播**：handler 返回 `[(msg_id, data)]` 或 `[(msg_id, data, exclude_session)]`，通过 `broadcast()` 分发

**断线处理** (`_on_disconnect`)：
1. 从 `game_world.players[pid]` 复制最新位置/血量到 `session.player_state`
2. 存入 `disconnected_sessions[account]`
3. 记录 `disconnect_time[account]`
4. 从 GameWorld 移除 + 广播 ScPlayerLeave

**重连处理** (`handle_login` 内)：
1. 登录成功后检查 `disconnected_sessions` 是否有该账号
2. 有 → 跳过角色选择，直接 IN_GAME + ScReconnect + 广播 ScPlayerJoin
3. 没有 → 正常走角色选择

---

### 6. 协议 — `proto/tps.proto` ✅

18 种消息，3 个阶段：

| 范围 | 阶段 | 消息 |
|------|------|------|
| 100-109 | 登录/角色 | CsLogin, ScLoginResult, CsGetCharacters, ScCharacterList, CsCreateChar, ScCreateResult, CsSelectChar, ScEnterGame, CsReconnectAck, ScReconnect |
| 200-207 | 游戏内 | CsMove, ScPlayerStates, CsSkill, ScSkillResult, CsPickup, ScPickupResult, CsShoot, ScShootResult |
| 300-302 | 系统 | ScDisconnect, ScPlayerJoin, ScPlayerLeave |

通用类型：Vector3, Rotator, PlayerState, EnemyState, ItemState, CharacterInfo

---

## 三、测试结果

### 单元测试

| 测试项 | 方法 | 结果 |
|--------|------|------|
| 数据库 CRUD | `python -c "from db import Database; ..."` | ✅ PASS |
| 包解析 | 构造双包缓冲区，extract_messages | ✅ PASS |
| 服务端启动 | `python main.py` → `netstat` 确认 9999 监听 | ✅ PASS |

### 集成测试（Python 模拟客户端）

使用 `test_reconnect_v2.py` 脚本模拟完整客户端流程：

| 测试步骤 | 结果 |
|----------|------|
| TCP 连接服务端 | ✅ |
| CsLogin(注册) → ScLoginResult(success=True) | ✅ |
| CsGetCharacters → ScCharacterList | ✅ |
| CsCreateCharacter → ScCreateResult(success=True) | ✅ |
| CsSelectCharacter → ScEnterGame | ✅ |
| CsMove(500,600,100) → 服务端收到并更新位置 | ✅ |
| 断线（关闭 socket） | ✅ |
| 重新连接 + CsLogin(登录) → ScLoginResult(success=True) | ✅ |
| **ScReconnect（位置恢复 loc=(500,600,100), yaw=90, hp=100）** | ✅ |

**完整测试日志**：
```
[13:04:42] Phase 1: Register + Login + CreateChar + SelectChar + EnterGame
[13:04:42] 1. Connected to server
[13:04:42] 2. Register result: success=True
[13:04:42] 3. Got character list, msg_id=103
[13:04:42] 4. Create char: success=True
[13:04:42] 5. Enter game: msg_id=107, pid=3, loc=(0,0,200)
[13:04:42] 6. Sent CsMove to (500,600,100)
[13:04:42] Phase 2: Disconnect
[13:04:42] 7. Socket closed
[13:04:42] Phase 3: Reconnect with same account
[13:04:42] 8. Reconnected to server
[13:04:42] 9. Login: success=True
[13:04:42] 10. *** RECONNECT SUCCESS! ***
           pid=4, loc=(500,600,100), yaw=90, hp=100
[13:04:42] === POSITION PRESERVED - ALL TESTS PASSED ===
```

---

## 四、已修复的 Bug

| Bug | 问题 | 修复 |
|-----|------|------|
| `_on_disconnect` 保存不完整状态 | `session.player_state` 没有 `location`/`rotation` 键（实时位置在 `game_world.players[pid]` 中），断线重连会 KeyError | 断线时先从 `game_world.players[pid]` 复制最新位置/血量到 `session.player_state`，再保存 |
| `handle_login` 重连分支直接取下标 | `saved["location"].get("x", 0)` 在 `location` key 不存在时 KeyError | 改为 `saved.get("location", {}).get("x", 0)` 防御式访问 |
| `game_server.py` 引用错误 | 第117行 `server.game_world.get_all_player_states()` 应为 `self.game_world` | 修正为 `self.game_world.get_all_player_states()` |

---

## 五、已知不足

| 问题 | 影响 | 严重度 | 备注 |
|------|------|--------|------|
| Enemy/Item 状态未实现 | ScEnterGame/ScReconnect 的 enemies/items 字段为空，多客户端看不到敌人 | 🔴 高 | 需要在 GameWorld 中添加敌人/道具同步 |
| 没有心跳机制 | 静止客户端断线无法检测（只能靠 TCP RST） | 🟡 中 | Demo 场景下可接受 |
| 每帧全量广播位置 | 带宽浪费，人数多时性能下降 | 🟡 中 | 可优化为增量广播，Demo 先用 |
| 没有重复登录踢出 | 同一账号可多开 | 🟢 低 | Demo 无所谓 |
| 密码明文存储 | 安全问题 | 🟢 低 | Demo 无所谓 |
| 数据库路径为相对路径 | 非项目根目录启动时 db 路径错误 | 🟢 低 | 可改为绝对路径 |

---

## 六、下一步：客户端集成（Tasks 7-14）

| Task | 内容 | 依赖 | 状态 |
|------|------|------|------|
| 7 | 客户端网络模块 NetClient | 服务端 | ⏳ 待开发 |
| 8 | 登录 UI (WBP_Login) | Task 7 | ⏳ 待开发 |
| 9 | 角色选择 UI (WBP_CharacterSelect) | Task 8 | ⏳ 待开发 |
| 10 | 游戏内同步（位置/射击/拾取上报） | Task 7 | ⏳ 待开发 |
| 11 | 远程玩家显示 | Task 10 | ⏳ 待开发 |
| 12 | 断线重连客户端处理 | Task 7 | ⏳ 待开发 |
| 13 | UE 编辑器创建蓝图 Widget | Task 8-9 | ⏳ 待开发 |
| 14 | 端到端联调 | 全部 | ⏳ 待开发 |

---

## 七、增量更新（2026-05-14 补充）

### 对照 P5 服务端 7 项要求补全

| # | 要求 | 补充前 | 补充后 |
|---|------|--------|--------|
| 1 | 多客户端接入 | ✅ | ✅ |
| 2 | protobuf 交互 | ✅ | ✅ |
| 3 | 创建账号设置密码 | ✅ | ✅ |
| 4 | 建立/选择角色进入游戏 | ✅ | ✅ |
| 5 | 管理游戏内物体 | ⚠️ 只有玩家位置 | ✅ 新增敌人事件广播 |
| 6 | 退出重连进入战场 | ✅ | ✅ |
| 7 | 同步其他角色 | ⚠️ 只有移动/技能 | ✅ 新增动作同步（换弹/瞄准） |

### 对照技术要求补全

| 要求 | 补充前 | 补充后 |
|------|--------|--------|
| 内建 netease1/2/3 账号 | ❌ | ✅ DB 初始化时自动插入 |
| server.bat 启动脚本 | ❌ | ✅ 已创建 |
| 操作说明文档 | ❌ | ✅ OPERATION_GUIDE.md |

### 新增消息

| MsgId | 消息 | 用途 |
|-------|------|------|
| CS_ENEMY_EVENT(210) | CsEnemyEvent | 客户端上报敌人事件（受伤/击杀/晕眩） |
| SC_ENEMY_EVENT(211) | ScEnemyEvent | 广播敌人事件给其他客户端 |
| CS_ACTION(220) | CsAction | 客户端上报动作状态变化（换弹/瞄准） |
| SC_ACTION(221) | ScAction | 广播动作状态变化 |
| CS_GAME_RESULT(230) | CsGameResult | 客户端上报游戏结果（胜利/失败） |
| SC_GAME_RESULT(231) | ScGameResult | 广播游戏结果 + 升级通知 |

### PlayerState 新增字段

```protobuf
message PlayerState {
  ...
  bool is_sprinting = 7;   // 冲刺状态
  bool is_aiming    = 8;   // 瞄准状态
  bool is_reloading = 9;   // 换弹状态
}
```

### 新增枚举类型

```protobuf
enum EnemyEventType { ENEMY_DAMAGE=0; ENEMY_KILLED=1; ENEMY_STUNNED=2; }
enum ActionType { ACTION_RELOAD_START=0; ACTION_RELOAD_END=1; ACTION_AIM_START=2; ACTION_AIM_END=3; }
enum GameResultType { GAME_VICTORY=0; GAME_DEFEAT=1; }
```

### 升级机制

- 客户端胜利时发送 `CsGameResult(GAME_VICTORY)`
- 服务端收到后调用 `db.update_character_level(char_name, level+1)`
- 广播 `ScGameResult` 含 `level_up=True`

### Handler 从 9 个增至 12 个

| 新增 Handler | 功能 |
|--------------|------|
| `handle_enemy_event` | 纯广播转发敌人事件（服务端不追踪敌人状态） |
| `handle_action` | 更新 GameWorld 动作状态 + 广播 |
| `handle_game_result` | 处理胜利/失败，胜利时升级 |

### 文件清单更新

```
server/
├── main.py
├── game_server.py
├── client_session.py
├── msg_handler.py           # 12 个 handler
├── game_world.py             # +动作状态字段 +update_player_action()
├── db.py                     # +内建账号 +update_character_level()
├── db_init.sql
├── requirements.txt
├── server.bat                # 新增：启动脚本
├── OPERATION_GUIDE.md        # 新增：操作说明
├── game.db
├── proto/
│   ├── __init__.py
│   ├── tps.proto             # 24 种消息（+6）
│   └── tps_pb2.py
└── test_reconnect_v2.py
```
