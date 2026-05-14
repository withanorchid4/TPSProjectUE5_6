# TPS 服务端设计文档

> 日期：2026-05-14
> 状态：已确认

---

## 设计决策总览

| 决策 | 选择 | 理由 |
|------|------|------|
| 架构 | `select` 单线程事件循环 | 零基础友好，代码最少（~400行），无并发 bug |
| 客户端策略 | 最小改动，单机逻辑保留 | 不动现有代码，只加网络层 |
| 协议 | protobuf + 4字节长度头 | P5 要求 |
| 存储 | sqlite3 | Python 标准库，题目允许 |
| 移动同步 | 客户端上报位置，服务端广播 | 不验证，降低复杂度 |
| 断线重连 | 5分钟内重连恢复战场 | P5 要求断线后可重新进入 |

---

## §1 项目结构与协议

### 1.1 目录结构

```
server/
├── main.py              # 入口，启动 select 事件循环
├── game_server.py       # GameServer 类：select 循环 + 消息分发
├── client_session.py    # ClientSession 类：单个连接的读写缓冲
├── msg_handler.py       # 消息处理：按 msg_id 分发到各函数
├── game_world.py        # GameWorld 类：玩家/敌人/道具状态
├── db.py                # sqlite3 封装：账号、角色存储
├── proto/
│   ├── tps.proto        # 消息定义
│   └── tps_pb2.py       # 编译产物
└── db_init.sql           # 建表语句
```

### 1.2 包格式

```
[4字节大端长度][protobuf 消息体]
```

- 长度字段 = protobuf 消息体的字节数（不含长度字段本身）
- 消息体前2字节为 `msg_id`，剩余为具体消息内容

### 1.3 命名约定

- 客户端→服务端：`CsXxx`，MsgId 范围 100-299
- 服务端→客户端：`ScXxx`，MsgId 范围 101-399

### 1.4 核心原则

**客户端单机逻辑不动，服务端只做状态镜像+广播。** 客户端自行计算移动/伤害，上报结果，服务端不做校验。

---

## §2 核心流程

### 2.1 完整连接生命周期

```
客户端                              服务端
  │                                   │
  │──── TCP connect ────────────────→│
  │                                   │
  │──── CsLogin ────────────────────→│  查DB验证账号
  │←──── ScLoginResult ─────────────│  成功/失败
  │                                   │  ┌─ 有断线记录 → ScReconnect → IN_GAME
  │                                   │  └─ 无断线记录 ↓
  │──── CsGetCharacters ───────────→│  查DB获取角色列表
  │←──── ScCharacterList ───────────│  [角色1, 角色2, ...]
  │                                   │
  │  ┌─ 如果无角色 ─────────────────┐│
  │  │  CsCreateCharacter ────────→││  创建角色写DB
  │  │  ← ScCreateCharacterResult ─││  成功/失败
  │  └─────────────────────────────┘│
  │                                   │
  │──── CsSelectCharacter ──────────→│  选择角色进入游戏
  │←──── ScEnterGame ──────────────│  世界状态快照
  │                                   │
  │═════════ 游戏循环 ═══════════════│
  │──── CsMove ────────────────────→│  上报位置
  │←──── ScPlayerStates ───────────│  广播所有人位置
  │──── CsSkill ───────────────────→│  释放技能
  │←──── ScSkillResult ────────────│  广播技能结果
  │──── CsPickup ───────────────────→│  拾取道具
  │←──── ScPickupResult ───────────│  广播道具消失
  │──── CsShoot ───────────────────→│  射击
  │←──── ScShootResult ────────────│  广播射击结果
  │═════════════════════════════════│
  │                                   │
  │──── 断线 ──────────────────────→│  保存状态，5分钟倒计时
```

### 2.2 客户端新增 UI

| Widget | 功能 | 时机 |
|--------|------|------|
| `WBP_Login` | 账号/密码输入 + 登录/注册按钮 | 启动后第一个界面 |
| `WBP_CharacterSelect` | 角色列表 + 创建角色按钮 + 选择进入按钮 | 登录成功后（仅新连接） |

### 2.3 客户端状态机

```
DISCONNECTED → CONNECTING → LOGIN ─┬→ CHARACTER_SELECT → IN_GAME
                                    └→ IN_GAME (重连，跳过角色选择)
```

### 2.4 select 主循环伪代码

```python
while running:
    readable, _, _ = select.select(all_sockets, [], [], 0.033)  # ~30fps
    for sock in readable:
        if sock is listen_socket:
            new_conn = sock.accept()
            sessions[new_conn] = ClientSession(new_conn)
        else:
            session = sessions[sock]
            session.try_recv()       # 读入缓冲区
            session.process_msgs()   # 解包并分发消息
    broadcast_world_state()          # 每帧广播
    check_expired_reconnects()      # 检查断线超时
```

---

## §3 消息定义与处理

### 3.1 Proto 消息定义

```protobuf
syntax = "proto3";
package tps;

// ============ 消息ID ============
enum MsgId {
  MSG_NONE          = 0;

  // 登录阶段 100-199
  CS_LOGIN          = 100;
  SC_LOGIN_RESULT   = 101;
  CS_GET_CHARACTERS = 102;
  SC_CHARACTER_LIST = 103;
  CS_CREATE_CHAR    = 104;
  SC_CREATE_RESULT  = 105;
  CS_SELECT_CHAR    = 106;
  SC_ENTER_GAME     = 107;
  CS_RECONNECT_ACK  = 108;
  SC_RECONNECT      = 109;

  // 游戏阶段 200-299
  CS_MOVE           = 200;
  SC_PLAYER_STATES  = 201;
  CS_SKILL          = 202;
  SC_SKILL_RESULT   = 203;
  CS_PICKUP         = 204;
  SC_PICKUP_RESULT  = 205;
  CS_SHOOT          = 206;
  SC_SHOOT_RESULT   = 207;

  // 系统 300+
  SC_DISCONNECT     = 300;
  SC_PLAYER_JOIN    = 301;
  SC_PLAYER_LEAVE   = 302;
}

// ============ 通用类型 ============
message Vector3 {
  float x = 1;
  float y = 2;
  float z = 3;
}

message Rotator {
  float pitch = 1;
  float yaw   = 2;
  float roll  = 3;
}

message PlayerState {
  int32    player_id   = 1;
  string   char_name   = 2;
  Vector3  location    = 3;
  Rotator  rotation    = 4;
  int32    hp          = 5;
  float    move_speed  = 6;
}

message EnemyState {
  int32   enemy_id   = 1;
  int32   enemy_type = 2;  // 0=近战, 1=远程
  Vector3 location   = 3;
  int32   hp         = 4;
}

message ItemState {
  int32   item_uid   = 1;
  int32   item_type  = 2;  // 0=血包, 1=弹药, 2=Buff
  Vector3 location   = 3;
  bool    active     = 4;
}

message CharacterInfo {
  int32  char_id   = 1;
  string char_name = 2;
  int32  level     = 3;
}

// ============ 登录/角色 ============
message CsLogin {
  string account     = 1;
  string password    = 2;
  bool   is_register = 3;  // true=注册, false=登录
}

message ScLoginResult {
  bool   success = 1;
  string msg     = 2;  // 失败原因
  string token   = 3;  // 成功时返回
}

message CsGetCharacters {}

message ScCharacterList {
  repeated CharacterInfo characters = 1;
}

message CsCreateCharacter {
  string char_name = 1;
}

message ScCreateResult {
  bool         success   = 1;
  string       msg       = 2;
  CharacterInfo character = 3;  // 成功时返回新角色
}

message CsSelectCharacter {
  int32 char_id = 1;
}

message ScEnterGame {
  repeated PlayerState players    = 1;
  repeated EnemyState  enemies    = 2;
  repeated ItemState   items      = 3;
  PlayerState          self_state = 4;
}

// ============ 重连 ============
message ScReconnect {
  PlayerState          self_state = 1;
  repeated PlayerState players    = 2;
  repeated EnemyState  enemies    = 3;
  repeated ItemState   items      = 4;
}

message CsReconnectAck {}

// ============ 游戏内 ============
message CsMove {
  Vector3 location     = 1;
  Rotator rotation    = 2;
  bool    is_sprinting = 3;
}

message ScPlayerStates {
  repeated PlayerState players = 1;
}

message CsSkill {
  int32   skill_id        = 1;
  Vector3 target_location  = 2;
}

message ScSkillResult {
  int32   player_id       = 1;
  int32   skill_id        = 2;
  Vector3 location        = 3;
  Vector3 target_location = 4;
}

message CsPickup {
  int32 item_uid = 1;
}

message ScPickupResult {
  bool   success   = 1;
  int32  player_id = 2;
  int32  item_uid   = 3;
}

message CsShoot {
  Vector3 start_location = 1;
  Rotator direction      = 2;
  int32   weapon_type    = 3;  // 0=普通, 1=魔法箭
}

message ScShootResult {
  int32   player_id      = 1;
  Vector3 start_location = 2;
  Rotator direction      = 3;
  int32   weapon_type    = 4;
}

// ============ 系统 ============
message ScDisconnect {
  string reason = 1;
}

message ScPlayerJoin {
  PlayerState player = 1;
}

message ScPlayerLeave {
  int32 player_id = 1;
}
```

### 3.2 消息分发表

```python
# msg_handler.py
HANDLERS = {
    MsgId.CS_LOGIN:          handle_login,
    MsgId.CS_GET_CHARACTERS: handle_get_characters,
    MsgId.CS_CREATE_CHAR:    handle_create_character,
    MsgId.CS_SELECT_CHAR:    handle_select_character,
    MsgId.CS_RECONNECT_ACK:  handle_reconnect_ack,
    MsgId.CS_MOVE:           handle_move,
    MsgId.CS_SKILL:          handle_skill,
    MsgId.CS_PICKUP:         handle_pickup,
    MsgId.CS_SHOOT:          handle_shoot,
}
```

### 3.3 客户端网络模块

```python
# client/network/NetClient.py
class NetClient:
    """客户端单例，管理 TCP 连接与消息收发"""

    STATE_DISCONNECTED     = 0
    STATE_CONNECTING       = 1
    STATE_LOGIN            = 2
    STATE_CHARACTER_SELECT = 3
    STATE_IN_GAME          = 4

    def connect(self, host, port): ...
    def send_msg(self, msg_id, msg_bytes): ...
    def _recv_tick(self): ...  # 在 TickableMixin.on_tick 里调用
    def _dispatch(self, msg_id, data): ...
```

客户端在 `ReceiveBeginPlay` 时创建 `NetClient`，用 `TickableMixin` 每帧检查收缓冲区，解包后回调到 UI 或游戏逻辑。

---

## §4 断线重连

### 4.1 服务端断线处理流程

```
玩家断线
  │
  ├─ 服务端将 session 从 active 移到 disconnected 池
  ├─ 广播 ScPlayerLeave（其他客户端看到玩家"消失"）
  ├─ 保留状态：位置、HP、背包、角色ID
  └─ 启动 5 分钟倒计时，超时后彻底清除状态
```

### 4.2 重连流程

```
客户端                              服务端
  │──── TCP connect ────────────────→│
  │──── CsLogin(同一账号) ──────────→│  查DB验证
  │                                   │  检查 disconnected 池
  │                                   │  发现有未过期状态!
  │←──── ScLoginResult ─────────────│  success=true
  │←──── ScReconnect ───────────────│  带完整游戏状态快照
  │                                   │
  │  恢复到 IN_GAME 状态               │  移回 active 池
  │                                   │  广播 ScPlayerJoin
```

与正常登录的区别：**登录后不发 `CsGetCharacters`**，服务端检测到断线记录后主动推送 `ScReconnect`。

### 4.3 服务端数据结构

```python
class GameServer:
    active_sessions: dict[socket, ClientSession]       # 在线玩家
    disconnected_sessions: dict[str, PlayerState]      # 断线但未过期 key=account
    disconnect_time: dict[str, float]                   # 断线时间戳

    def on_disconnect(self, session):
        """断线时保存状态"""
        account = session.account
        self.disconnected_sessions[account] = session.player_state
        self.disconnect_time[account] = time.time()
        # 广播 ScPlayerLeave
        ...

    def on_login(self, session, account):
        """登录时检查是否有断线状态"""
        if account in self.disconnected_sessions:
            # 直接恢复，不走角色选择
            session.restore(self.disconnected_sessions.pop(account))
            del self.disconnect_time[account]
            session.send(ScReconnect(...))
            # 广播 ScPlayerJoin
        else:
            # 正常流程：走角色选择
            ...

    def check_expired(self):
        """每帧检查过期断线记录（5分钟）"""
        now = time.time()
        expired = [a for a, t in self.disconnect_time.items() if now - t > 300]
        for account in expired:
            del self.disconnected_sessions[account]
            del self.disconnect_time[account]
```

### 4.4 超时参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 断线保留时间 | 5 分钟 | 超时后状态清除，需重新走角色选择 |
| 心跳间隔 | 30 秒 | 客户端定时发空包维持连接 |
| 读超时 | 60 秒 | 无心跳则踢出 |

---

## 依赖与工具链

| 依赖 | 来源 | 用途 |
|------|------|------|
| Python 3 | 标准库 | 服务端运行时 |
| socket / select | 标准库 | TCP 网络与事件循环 |
| sqlite3 | 标准库 | 账号/角色持久化 |
| protobuf | pip install | 消息序列化 |
| protoc | Google | 编译 .proto → _pb2.py |
