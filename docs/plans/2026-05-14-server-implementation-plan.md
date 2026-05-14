# TPS 服务端实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 TPS 游戏搭建独立 Python 服务端，支持多客户端接入、账号系统、角色创建/选择、游戏状态同步、断线重连。

**Architecture:** 独立 Python 服务端（select 事件循环 + protobuf + sqlite3），客户端通过 TCP 连接。客户端单机逻辑保留不动，只新增网络模块 + 登录/角色选择 UI。服务端只做状态镜像和广播，不做物理校验。

**Tech Stack:** Python 3 + socket/select + protobuf + sqlite3（服务端）；NePy Python + TickableMixin（客户端网络模块）

**设计文档:** `docs/plans/2026-05-14-server-design.md`

---

## Task 1: 环境搭建 — protobuf 编译工具链

**Files:**
- Create: `server/requirements.txt`
- Create: `server/proto/tps.proto`

**Step 1: 创建 server 目录结构**

```
server/
├── main.py
├── game_server.py
├── client_session.py
├── msg_handler.py
├── game_world.py
├── db.py
├── proto/
│   └── tps.proto
└── db_init.sql
```

**Step 2: 创建 requirements.txt**

```
protobuf>=4.21.0
```

**Step 3: 创建 tps.proto**

将设计文档 §3.1 中完整的 proto 定义写入 `server/proto/tps.proto`。

**Step 4: 编译 proto**

```bash
cd server/proto
pip install protobuf grpcio-tools
python -m grpc_tools.protoc -I. --python_out=. tps.proto
```

验证 `tps_pb2.py` 生成成功。

**Step 5: Commit**

```bash
git add server/
git commit -m "feat(server): init server directory with proto definition"
```

---

## Task 2: 数据库层 — db.py + db_init.sql

**Files:**
- Create: `server/db.py`
- Create: `server/db_init.sql`

**Step 3: 创建 db_init.sql**

```sql
CREATE TABLE IF NOT EXISTS accounts (
    account   TEXT PRIMARY KEY,
    password  TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS characters (
    char_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    account   TEXT NOT NULL,
    char_name TEXT NOT NULL UNIQUE,
    level     INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    FOREIGN KEY (account) REFERENCES accounts(account)
);
```

**Step 4: 创建 db.py**

封装 sqlite3 操作：

```python
class Database:
    def __init__(self, db_path="server/game.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        # 执行 db_init.sql

    def register(self, account, password) -> bool:
        # INSERT INTO accounts，重复返回 False

    def login(self, account, password) -> bool:
        # SELECT 验证账号密码

    def get_characters(self, account) -> list[dict]:
        # SELECT * FROM characters WHERE account=?

    def create_character(self, account, char_name) -> dict | None:
        # INSERT INTO characters，重名返回 None

    def close(self):
        self.conn.close()
```

**Step 5: 手动测试**

```bash
cd server
python -c "from db import Database; db = Database(':memory:'); print(db.register('test','123')); print(db.login('test','123')); print(db.create_character('test','Hero')); print(db.get_characters('test'))"
```

预期输出：`True True {'char_id': 1, ...} [{'char_id': 1, 'char_name': 'Hero', ...}]`

**Step 6: Commit**

```bash
git add server/db.py server/db_init.sql
git commit -m "feat(server): add database layer with account and character tables"
```

---

## Task 3: 网络基础 — ClientSession + 包解析

**Files:**
- Create: `server/client_session.py`

**Step 1: 创建 client_session.py**

```python
import struct
from proto import tps_pb2

class ClientSession:
    """单个客户端连接的读写缓冲 + 消息解包"""

    HEADER_SIZE = 4  # 4字节大端长度头

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.recv_buffer = b""
        self.account = None           # 登录后设置
        self.player_state = None      # 进游戏后设置
        self.state = "CONNECTED"      # CONNECTED / LOGGED_IN / IN_GAME

    def try_recv(self) -> bool:
        """尝试从 socket 读取数据到缓冲区。返回 False 表示断线。"""
        try:
            data = self.sock.recv(4096)
            if not data:
                return False
            self.recv_buffer += data
            return True
        except Exception:
            return False

    def extract_messages(self) -> list[tuple[int, bytes]]:
        """从缓冲区提取完整的 protobuf 消息列表 [(msg_id, msg_bytes), ...]"""
        messages = []
        while len(self.recv_buffer) >= self.HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
            total_len = self.HEADER_SIZE + msg_len
            if len(self.recv_buffer) < total_len:
                break  # 数据不完整，等下次
            msg_data = self.recv_buffer[self.HEADER_SIZE:total_len]
            self.recv_buffer = self.recv_buffer[total_len:]
            # msg_data 前2字节 = msg_id，剩余 = protobuf body
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))
        return messages

    def send_msg(self, msg_id: int, msg_bytes: bytes):
        """打包并发送一条 protobuf 消息"""
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        try:
            self.sock.sendall(length + payload)
        except Exception:
            pass  # 发送失败，等 select 检测断线
```

**Step 2: 手动测试**

```bash
cd server
python -c "
from client_session import ClientSession
import struct
# 构造一个测试包：msg_id=100, body=b'hello'
body = b'hello'
header = struct.pack('!H', 100)
payload = header + body
length = struct.pack('!I', len(payload))
# 模拟缓冲区
sess = ClientSession.__new__(ClientSession)
sess.recv_buffer = length + payload + length + payload
msgs = sess.extract_messages()
print(msgs)
"
```

预期：`[(100, b'hello'), (100, b'hello')]`

**Step 3: Commit**

```bash
git add server/client_session.py
git commit -m "feat(server): add ClientSession with packet parsing"
```

---

## Task 4: 游戏世界状态 — GameWorld

**Files:**
- Create: `server/game_world.py`

**Step 1: 创建 game_world.py**

```python
class GameWorld:
    """管理所有在线玩家的状态 + 世界快照"""

    def __init__(self):
        self.players = {}       # player_id -> PlayerState dict
        self._next_player_id = 1

    def add_player(self, session) -> int:
        """玩家进入游戏，分配 player_id，返回 id"""
        pid = self._next_player_id
        self._next_player_id += 1
        self.players[pid] = {
            "player_id": pid,
            "char_name": session.player_state.get("char_name", "Unknown"),
            "location": {"x": 0, "y": 0, "z": 200},
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "hp": 100,
            "move_speed": 600,
        }
        session.player_state["player_id"] = pid
        return pid

    def remove_player(self, player_id: int):
        self.players.pop(player_id, None)

    def update_player_move(self, player_id, location, rotation, is_sprinting):
        """更新玩家位置"""
        if player_id in self.players:
            p = self.players[player_id]
            p["location"] = location
            p["rotation"] = rotation
            p["move_speed"] = 900 if is_sprinting else 600

    def get_all_player_states(self) -> list:
        return list(self.players.values())

    def get_snapshot(self) -> dict:
        """返回完整世界快照（进入游戏/重连用）"""
        return {
            "players": list(self.players.values()),
        }
```

**Step 2: Commit**

```bash
git add server/game_world.py
git commit -m "feat(server): add GameWorld for player state management"
```

---

## Task 5: 消息处理器 — msg_handler.py

**Files:**
- Create: `server/msg_handler.py`

**Step 1: 创建 msg_handler.py**

实现所有 CsXxx 消息的处理函数。每个函数签名：

```python
def handle_xxx(server: GameServer, session: ClientSession, data: bytes) -> list:
    """处理消息，返回需要广播给其他玩家的 [(msg_id, msg_bytes), ...]"""
```

处理列表：

| 消息 | 函数 | 核心逻辑 |
|------|------|----------|
| CS_LOGIN | `handle_login` | 调 db.register/login，检查断线重连 |
| CS_GET_CHARACTERS | `handle_get_characters` | 调 db.get_characters |
| CS_CREATE_CHAR | `handle_create_character` | 调 db.create_character |
| CS_SELECT_CHAR | `handle_select_character` | 设 session.player_state，加入 GameWorld |
| CS_RECONNECT_ACK | `handle_reconnect_ack` | 标记重连完成 |
| CS_MOVE | `handle_move` | 更新 GameWorld 中的位置 |
| CS_SKILL | `handle_skill` | 广播技能结果 |
| CS_PICKUP | `handle_pickup` | 广播拾取结果 |
| CS_SHOOT | `handle_shoot` | 广播射击结果 |

**handle_login 关键逻辑（含断线重连）：**

```python
def handle_login(server, session, data):
    msg = tps_pb2.CsLogin()
    msg.ParseFromString(data)

    if msg.is_register:
        success = server.db.register(msg.account, msg.password)
    else:
        success = server.db.login(msg.account, msg.password)

    result = tps_pb2.ScLoginResult()
    result.success = success
    if not success:
        result.msg = "注册失败(账号已存在)" if msg.is_register else "账号或密码错误"

    session.send_msg(MsgId.SC_LOGIN_RESULT, result.SerializeToString())

    if success:
        session.account = msg.account
        session.state = "LOGGED_IN"

        # 检查断线重连
        if msg.account in server.disconnected_sessions:
            saved = server.disconnected_sessions.pop(msg.account)
            del server.disconnect_time[msg.account]
            session.player_state = saved
            session.state = "IN_GAME"
            pid = server.game_world.add_player(session)

            # 发送 ScReconnect
            reconnect = tps_pb2.ScReconnect()
            # ... 填充世界快照
            session.send_msg(MsgId.SC_RECONNECT, reconnect.SerializeToString())

            # 广播 ScPlayerJoin
            ...
```

**Step 2: Commit**

```bash
git add server/msg_handler.py
git commit -m "feat(server): add message handlers for all CsXxx messages"
```

---

## Task 6: 服务端主循环 — GameServer + main.py

**Files:**
- Create: `server/game_server.py`
- Create: `server/main.py`

**Step 1: 创建 game_server.py**

```python
class GameServer:
    def __init__(self, host="0.0.0.0", port=9999):
        self.host = host
        self.port = port
        self.db = Database()
        self.game_world = GameWorld()
        self.active_sessions = {}       # socket -> ClientSession
        self.disconnected_sessions = {}  # account -> player_state dict
        self.disconnect_time = {}       # account -> timestamp
        self.listen_socket = None
        self.running = False

    def start(self):
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((self.host, self.port))
        self.listen_socket.listen(10)
        self.listen_socket.setblocking(False)
        self.running = True
        ue.LogWarning(f"GameServer: Listening on {self.host}:{self.port}")
        self._event_loop()

    def _event_loop(self):
        while self.running:
            all_sockets = [self.listen_socket] + list(self.active_sessions.keys())
            readable, _, _ = select.select(all_sockets, [], [], 0.033)

            for sock in readable:
                if sock is self.listen_socket:
                    conn, addr = sock.accept()
                    conn.setblocking(False)
                    self.active_sessions[conn] = ClientSession(conn, addr)
                else:
                    session = self.active_sessions[sock]
                    if not session.try_recv():
                        self._on_disconnect(sock)
                        continue
                    for msg_id, data in session.extract_messages():
                        self._dispatch(session, msg_id, data)

            self._broadcast_world_state()
            self._check_expired_reconnects()

    def _dispatch(self, session, msg_id, data):
        handler = HANDLERS.get(msg_id)
        if handler:
            handler(self, session, data)

    def _on_disconnect(self, sock):
        session = self.active_sessions.pop(sock)
        sock.close()
        if session.state == "IN_GAME" and session.player_state:
            account = session.account
            self.disconnected_sessions[account] = session.player_state
            self.disconnect_time[account] = time.time()
            pid = session.player_state.get("player_id")
            if pid:
                self.game_world.remove_player(pid)
                # 广播 ScPlayerLeave
                ...

    def _broadcast_world_state(self):
        """每帧广播所有玩家位置"""
        if not self.game_world.players:
            return
        states = tps_pb2.ScPlayerStates()
        for p in self.game_world.get_all_player_states():
            ps = states.players.add()
            ps.player_id = p["player_id"]
            ps.char_name = p["char_name"]
            ps.location.x = p["location"]["x"]
            # ...
        data = states.SerializeToString()
        for session in self.active_sessions.values():
            if session.state == "IN_GAME":
                session.send_msg(MsgId.SC_PLAYER_STATES, data)

    def _check_expired_reconnects(self):
        now = time.time()
        expired = [a for a, t in self.disconnect_time.items() if now - t > 300]
        for account in expired:
            del self.disconnected_sessions[account]
            del self.disconnect_time[account]

    def broadcast(self, msg_id, data, exclude=None):
        for session in self.active_sessions.values():
            if session.state == "IN_GAME" and session is not exclude:
                session.send_msg(msg_id, data)
```

**Step 2: 创建 main.py**

```python
#!/usr/bin/env python3
"""TPS 服务端入口"""
from game_server import GameServer

if __name__ == "__main__":
    server = GameServer(host="0.0.0.0", port=9999)
    try:
        server.start()
    except KeyboardInterrupt:
        server.running = False
        server.db.close()
```

**Step 3: 启动测试**

```bash
cd server
python main.py
```

预期输出：`GameServer: Listening on 0.0.0.0:9999`

用另一个终端 telnet 连接验证 socket 可连：

```bash
telnet 127.0.0.1 9999
```

服务端日志应显示新连接。Ctrl+C 关闭服务端。

**Step 4: Commit**

```bash
git add server/game_server.py server/main.py
git commit -m "feat(server): add GameServer with select event loop"
```

---

## Task 7: 客户端网络模块 — NetClient

**Files:**
- Create: `Content/Scripts/network/__init__.py`
- Create: `Content/Scripts/network/net_client.py`
- Create: `Content/Scripts/network/proto/tps_pb2.py`（从服务端复制）

**Step 1: 创建 network 模块**

```python
# network/__init__.py
```

**Step 2: 创建 net_client.py**

```python
import ue
import socket
import struct
import threading
from system.tickable import TickableMixin

# 内联导入 proto（避免循环依赖）
from network.proto import tps_pb2

class NetClient(TickableMixin):
    """客户端网络单例，管理 TCP 连接与消息收发"""

    STATE_DISCONNECTED     = 0
    STATE_CONNECTING       = 1
    STATE_LOGIN            = 2
    STATE_CHARACTER_SELECT = 3
    STATE_IN_GAME         = 4

    _instance = None

    @classmethod
    def get(cls):
        return cls._instance

    def __init__(self):
        self.sock = None
        self.state = self.STATE_DISCONNECTED
        self.recv_buffer = b""
        self.account = None
        self._msg_callbacks = {}   # msg_id -> callback
        self._ticker_handle = None
        self._send_lock = threading.Lock()
        NetClient._instance = self

    def connect(self, host="127.0.0.1", port=9999):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.sock.setblocking(False)
            self.state = self.STATE_LOGIN
            self._start_ticker()
            ue.LogWarning(f"NetClient: Connected to {host}:{port}")
        except Exception as e:
            ue.LogError(f"NetClient: Connect failed: {e}")
            self.state = self.STATE_DISCONNECTED

    def disconnect(self):
        self._stop_ticker()
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self.state = self.STATE_DISCONNECTED
        self.recv_buffer = b""

    def send_msg(self, msg_id: int, msg_bytes: bytes):
        if not self.sock:
            return
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        with self._send_lock:
            try:
                self.sock.sendall(length + payload)
            except Exception as e:
                ue.LogError(f"NetClient: Send failed: {e}")

    def register_callback(self, msg_id: int, callback):
        self._msg_callbacks[msg_id] = callback

    def on_tick(self, delta_time):
        """每帧检查收缓冲区"""
        if not self.sock or self.state == self.STATE_DISCONNECTED:
            return
        try:
            data = self.sock.recv(4096)
            if not data:
                ue.LogWarning("NetClient: Server disconnected")
                self.disconnect()
                return
            self.recv_buffer += data
        except BlockingIOError:
            pass  # 无数据，正常
        except Exception as e:
            ue.LogError(f"NetClient: Recv error: {e}")
            self.disconnect()
            return

        # 解包消息
        for msg_id, msg_data in self._extract_messages():
            cb = self._msg_callbacks.get(msg_id)
            if cb:
                try:
                    cb(msg_id, msg_data)
                except Exception as e:
                    ue.LogError(f"NetClient: Callback error for msg {msg_id}: {e}")

    def _extract_messages(self):
        """从缓冲区提取完整消息"""
        HEADER_SIZE = 4
        messages = []
        while len(self.recv_buffer) >= HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
            total = HEADER_SIZE + msg_len
            if len(self.recv_buffer) < total:
                break
            msg_data = self.recv_buffer[HEADER_SIZE:total]
            self.recv_buffer = self.recv_buffer[total:]
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))
        return messages
```

**Step 3: 复制 tps_pb2.py 到客户端**

将 `server/proto/tps_pb2.py` 复制到 `Content/Scripts/network/proto/tps_pb2.py`，同时需要复制 `tps_pb2.py` 同目录下的 `tps_pb2.pyi`（如果有）。

创建 `Content/Scripts/network/proto/__init__.py`。

**Step 4: Commit**

```bash
git add Content/Scripts/network/
git commit -m "feat(client): add NetClient with TickableMixin-based recv loop"
```

---

## Task 8: 客户端登录 UI — WBP_Login (Python 驱动)

**Files:**
- Create: `Content/Scripts/ui/login_screen.py`
- Modify: `Content/Scripts/system/game_mode.py`（MainMenu 分支中创建 NetClient + LoginScreen）

**Step 1: 创建 login_screen.py**

```python
import ue
from network.net_client import NetClient
from network.proto import tps_pb2

class LoginScreen:
    """管理 WBP_Login 的逻辑（在 Python 侧驱动）"""

    def __init__(self, player_controller):
        self.pc = player_controller
        self.widget = None
        self.net_client = None

    def show(self):
        # 加载蓝图 Widget 并添加到视口
        widget_class = ue.LoadObject(ue.Class, "/Game/BluePrint/WBP_Login.WBP_Login_C")
        if not widget_class:
            ue.LogError("LoginScreen: WBP_Login_C not found!")
            return
        self.widget = ue.WidgetBlueprintLibrary.Create(self.pc, widget_class, self.pc)
        if self.widget:
            self.widget.AddToViewport(0)
            self.pc.bShowMouseCursor = True

        # 创建网络连接
        self.net_client = NetClient()
        self.net_client.connect()

        # 注册回调
        self.net_client.register_callback(tps_pb2.SC_LOGIN_RESULT, self._on_login_result)

    def on_login_clicked(self, account, password):
        msg = tps_pb2.CsLogin()
        msg.account = account
        msg.password = password
        msg.is_register = False
        self.net_client.send_msg(tps_pb2.CS_LOGIN, msg.SerializeToString())

    def on_register_clicked(self, account, password):
        msg = tps_pb2.CsLogin()
        msg.account = account
        msg.password = password
        msg.is_register = True
        self.net_client.send_msg(tps_pb2.CS_LOGIN, msg.SerializeToString())

    def _on_login_result(self, msg_id, data):
        result = tps_pb2.ScLoginResult()
        result.ParseFromString(data)
        if result.success:
            ue.LogWarning(f"LoginScreen: Login success!")
            # 进入角色选择
            from ui.character_select import CharacterSelectScreen
            if self.widget:
                self.widget.RemoveFromParent()
            CharacterSelectScreen(self.pc, self.net_client).show()
        else:
            ue.LogWarning(f"LoginScreen: Login failed - {result.msg}")

    def hide(self):
        if self.widget:
            self.widget.RemoveFromParent()
            self.widget = None
```

**Step 2: 在 GameMode 的 MainMenu 分支中集成**

修改 `game_mode.py` 的 `_show_main_menu`：

```python
def _show_main_menu(self):
    pc = ue.GameplayStatics.GetPlayerController(self, 0)
    if pc:
        from ui.login_screen import LoginScreen
        self._login_screen = LoginScreen(pc)
        self._login_screen.show()
```

**注意：** WBP_Login 蓝图 Widget 需要在 UE 编辑器中手动创建（Python 无法创建 UMG Widget 蓝图）。Python 侧只负责加载和驱动。蓝图中的按钮点击需要调用 Python 函数。

**Step 3: Commit**

```bash
git add Content/Scripts/ui/login_screen.py
git commit -m "feat(client): add LoginScreen Python driver"
```

---

## Task 9: 客户端角色选择 UI — WBP_CharacterSelect (Python 驱动)

**Files:**
- Create: `Content/Scripts/ui/character_select_screen.py`

**Step 1: 创建 character_select_screen.py**

```python
import ue
from network.net_client import NetClient
from network.proto import tps_pb2

class CharacterSelectScreen:
    """管理 WBP_CharacterSelect 的逻辑"""

    def __init__(self, player_controller, net_client):
        self.pc = player_controller
        self.net_client = net_client
        self.widget = None
        self.characters = []

    def show(self):
        widget_class = ue.LoadObject(ue.Class, "/Game/BluePrint/WBP_CharacterSelect.WBP_CharacterSelect_C")
        if not widget_class:
            ue.LogError("CharacterSelectScreen: Widget not found!")
            return
        self.widget = ue.WidgetBlueprintLibrary.Create(self.pc, widget_class, self.pc)
        if self.widget:
            self.widget.AddToViewport(0)

        # 注册回调
        self.net_client.register_callback(tps_pb2.SC_CHARACTER_LIST, self._on_character_list)
        self.net_client.register_callback(tps_pb2.SC_CREATE_RESULT, self._on_create_result)
        self.net_client.register_callback(tps_pb2.SC_ENTER_GAME, self._on_enter_game)

        # 请求角色列表
        msg = tps_pb2.CsGetCharacters()
        self.net_client.send_msg(tps_pb2.CS_GET_CHARACTERS, msg.SerializeToString())

    def _on_character_list(self, msg_id, data):
        result = tps_pb2.ScCharacterList()
        result.ParseFromString(data)
        self.characters = list(result.characters)
        # 更新 UI 显示角色列表
        ...

    def on_create_character(self, char_name):
        msg = tps_pb2.CsCreateCharacter()
        msg.char_name = char_name
        self.net_client.send_msg(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())

    def _on_create_result(self, msg_id, data):
        result = tps_pb2.ScCreateResult()
        result.ParseFromString(data)
        if result.success:
            self.characters.append(result.character)
            # 刷新 UI
        else:
            ue.LogWarning(f"Create character failed: {result.msg}")

    def on_select_character(self, char_id):
        msg = tps_pb2.CsSelectCharacter()
        msg.char_id = char_id
        self.net_client.send_msg(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())

    def _on_enter_game(self, msg_id, data):
        result = tps_pb2.ScEnterGame()
        result.ParseFromString(data)
        ue.LogWarning("CharacterSelectScreen: Entering game!")
        # 切换到游戏关卡
        if self.widget:
            self.widget.RemoveFromParent()
        self.net_client.state = NetClient.STATE_IN_GAME
        ue.GameplayStatics.OpenLevel(self.pc, "Level1")

    def hide(self):
        if self.widget:
            self.widget.RemoveFromParent()
            self.widget = None
```

**Step 2: Commit**

```bash
git add Content/Scripts/ui/character_select_screen.py
git commit -m "feat(client): add CharacterSelectScreen Python driver"
```

---

## Task 10: 客户端游戏内同步 — 上报位置/技能/射击/拾取

**Files:**
- Modify: `Content/Scripts/character/base_character.py`（在 ReceiveTick 中上报位置）
- Modify: `Content/Scripts/character/shooting.py`（射击时上报）
- Modify: `Content/Scripts/pickup/pickup_item.py`（拾取时上报）

**Step 1: 在 BaseCharacter.ReceiveTick 中添加位置上报**

```python
# 在 ReceiveTick 末尾添加
net = NetClient.get()
if net and net.state == NetClient.STATE_IN_GAME:
    # 每 3 帧上报一次位置（降低带宽）
    if not hasattr(self, '_move_tick'):
        self._move_tick = 0
    self._move_tick += 1
    if self._move_tick >= 3:
        self._move_tick = 0
        loc = self.GetActorLocation()
        rot = self.GetActorRotation()
        msg = tps_pb2.CsMove()
        msg.location.x = loc.X
        msg.location.y = loc.Y
        msg.location.z = loc.Z
        msg.rotation.pitch = rot.Pitch
        msg.rotation.yaw = rot.Yaw
        msg.rotation.roll = rot.Roll
        msg.is_sprinting = getattr(self.movement, '_is_sprinting', False)
        net.send_msg(tps_pb2.CS_MOVE, msg.SerializeToString())
```

**Step 2: 在 ShootingComponent.shoot() 中添加射击上报**

```python
# 在 shoot() 方法末尾（return True 之前）
net = NetClient.get()
if net and net.state == NetClient.STATE_IN_GAME:
    msg = tps_pb2.CsShoot()
    msg.start_location.x = muzzle_location.X
    msg.start_location.y = muzzle_location.Y
    msg.start_location.z = muzzle_location.Z
    msg.direction.pitch = fire_rotation.Pitch
    msg.direction.yaw = fire_rotation.Yaw
    msg.direction.roll = fire_rotation.Roll
    msg.weapon_type = 0  # 普通子弹
    net.send_msg(tps_pb2.CS_SHOOT, msg.SerializeToString())
```

同理 `fire_magic_arrow()` 中 `weapon_type = 1`。

**Step 3: 在 PickupItem._on_overlap 中添加拾取上报**

```python
# 在 Destroy() 之前
net = NetClient.get()
if net and net.state == NetClient.STATE_IN_GAME:
    msg = tps_pb2.CsPickup()
    msg.item_uid = id(self)  # 用 Python id 作为临时 uid
    net.send_msg(tps_pb2.CS_PICKUP, msg.SerializeToString())
```

**Step 4: Commit**

```bash
git add Content/Scripts/character/base_character.py Content/Scripts/character/shooting.py Content/Scripts/pickup/pickup_item.py
git commit -m "feat(client): add position/shoot/pickup reporting to server"
```

---

## Task 11: 客户端接收服务端广播 — 其他玩家显示

**Files:**
- Create: `Content/Scripts/network/remote_player.py`
- Modify: `Content/Scripts/network/net_client.py`（注册 IN_GAME 回调）

**Step 1: 创建 remote_player.py**

```python
import ue
from system.tickable import TickableMixin

class RemotePlayerManager(TickableMixin):
    """管理其他玩家的 Actor 显示"""

    def __init__(self):
        self.remote_actors = {}  # player_id -> Actor
        self._ticker_handle = None

    def start(self):
        self._start_ticker()

    def stop(self):
        for actor in self.remote_actors.values():
            if actor:
                actor.Destroy()
        self.remote_actors.clear()
        self._stop_ticker()

    def update_states(self, player_states_msg):
        """收到 ScPlayerStates 时调用"""
        for ps in player_states_msg.players:
            if ps.player_id in self.remote_actors:
                actor = self.remote_actors[ps.player_id]
                if actor:
                    actor.SetActorLocation(
                        ue.Vector(ps.location.x, ps.location.y, ps.location.z),
                        False, False
                    )
                    actor.SetActorRotation(
                        ue.Rotator(ps.rotation.pitch, ps.rotation.yaw, ps.rotation.roll),
                        False
                    )
            else:
                # 新玩家：生成一个简单的 Mesh Actor 代表
                world = ue.GameplayStatics.GetAllActorsOfClass(
                    # 需要获取 world context，从 TPSCharacter 获取
                )
                ...

    def on_player_join(self, msg):
        pass  # 远程玩家加入，生成 Actor

    def on_player_leave(self, msg):
        pid = msg.player_id
        if pid in self.remote_actors:
            self.remote_actors[pid].Destroy()
            del self.remote_actors[pid]
```

**Step 2: 在 NetClient 中注册 IN_GAME 回调**

```python
# 在登录成功/进入游戏后
self.register_callback(tps_pb2.SC_PLAYER_STATES, self._on_player_states)
self.register_callback(tps_pb2.SC_PLAYER_JOIN, self._on_player_join)
self.register_callback(tps_pb2.SC_PLAYER_LEAVE, self._on_player_leave)
self.register_callback(tps_pb2.SC_SHOOT_RESULT, self._on_shoot_result)
self.register_callback(tps_pb2.SC_RECONNECT, self._on_reconnect)
```

**Step 3: Commit**

```bash
git add Content/Scripts/network/remote_player.py
git commit -m "feat(client): add RemotePlayerManager for other player display"
```

---

## Task 12: 客户端断线重连处理

**Files:**
- Modify: `Content/Scripts/network/net_client.py`（添加重连逻辑）
- Modify: `Content/Scripts/ui/login_screen.py`（登录成功时处理 ScReconnect）

**Step 1: 在 NetClient 中添加重连回调**

```python
def _on_reconnect(self, msg_id, data):
    """收到 ScReconnect，直接进入游戏"""
    reconnect = tps_pb2.ScReconnect()
    reconnect.ParseFromString(data)
    ue.LogWarning(f"NetClient: Reconnected! Restoring game state")
    self.state = self.STATE_IN_GAME

    # 确认重连
    ack = tps_pb2.CsReconnectAck()
    self.send_msg(tps_pb2.CS_RECONNECT_ACK, ack.SerializeToString())

    # 恢复自身位置
    # 切换到游戏关卡
    ...
```

**Step 2: 在 LoginScreen._on_login_result 中处理重连路径**

```python
def _on_login_result(self, msg_id, data):
    result = tps_pb2.ScLoginResult()
    result.ParseFromString(data)
    if result.success:
        # 注册 ScReconnect 回调，如果收到则走重连路径
        self.net_client.register_callback(tps_pb2.SC_RECONNECT, self._on_reconnect)
        # 如果没收到 ScReconnect，说明是新连接，走角色选择
        # ...
```

**Step 3: Commit**

```bash
git add Content/Scripts/network/net_client.py Content/Scripts/ui/login_screen.py
git commit -m "feat(client): add reconnect handling in NetClient and LoginScreen"
```

---

## Task 13: UE 编辑器中创建蓝图 Widget

**Files:**
- Create (UE 编辑器): `Content/BluePrint/WBP_Login.uasset`
- Create (UE 编辑器): `Content/BluePrint/WBP_CharacterSelect.uasset`

**这一步必须在 UE 编辑器中手动完成，Python 无法创建 UMG Widget 蓝图。**

### WBP_Login 需要的元素：
- `TextBox_Account` — 账号输入框 (EditBox)
- `TextBox_Password` — 密码输入框 (EditBox)
- `Button_Login` — 登录按钮
- `Button_Register` — 注册按钮
- `TextBlock_Status` — 状态提示文本

按钮点击事件需要调用 Python：
```
Button_Login → On Clicked → Execute Python → login_screen.on_login_clicked(account, password)
Button_Register → On Clicked → Execute Python → login_screen.on_register_clicked(account, password)
```

### WBP_CharacterSelect 需要的元素：
- `ListView_Characters` — 角色列表 (ListView 或 VerticalBox)
- `TextBox_CharName` — 创建角色名称输入框
- `Button_Create` — 创建角色按钮
- `Button_Select` — 选择角色进入游戏按钮
- `TextBlock_Status` — 状态提示文本

按钮点击事件调用 Python：
```
Button_Create → On Clicked → Execute Python → character_select_screen.on_create_character(char_name)
Button_Select → On Clicked → Execute Python → character_select_screen.on_select_character(char_id)
```

### NePy 中 Python 与蓝图 Widget 交互方式：
1. 在蓝图中用 `Call Python Function` 节点调用 Python 模块函数
2. 或在 Python 中通过 `widget.Button_Login.OnClicked.Add(callback)` 绑定

**Step 4: 在编辑器中测试**

1. 启动服务端 `python server/main.py`
2. 在 UE 编辑器中 Play
3. 验证登录界面出现、可以连接服务端
4. 测试注册/登录流程

---

## Task 14: 端到端联调测试

**Files:** 无新文件

**Step 1: 启动服务端**

```bash
cd server
python main.py
```

**Step 2: 启动客户端 1（UE 编辑器 Play）**

- 验证：登录界面出现
- 操作：注册账号 test1/123 → 登录 → 角色选择界面
- 操作：创建角色 "Hero1" → 选择进入 → 进入 Level1

**Step 3: 启动客户端 2（另一个 UE 实例或 Standalone Game）**

- 验证：注册账号 test2/123 → 登录 → 创建角色 → 进入游戏
- 验证：客户端 1 能看到客户端 2 的角色

**Step 4: 断线重连测试**

- 客户端 2 强制关闭
- 验证：客户端 1 看到客户端 2 消失
- 客户端 2 重新启动，用同一账号登录
- 验证：直接回到战场，不需要重新选角色

**Step 5: 修复联调中发现的问题**

---

## Task 依赖关系

```
Task 1 (proto) → Task 5 (msg_handler) → Task 6 (GameServer + main)
                ↘ Task 7 (NetClient) → Task 8 (LoginScreen) → Task 9 (CharSelect)
                                    → Task 10 (游戏内同步) → Task 11 (远程玩家)
                                    → Task 12 (断线重连)

Task 2 (db)    → Task 5
Task 3 (session) → Task 6
Task 4 (game_world) → Task 5

Task 13 (蓝图Widget) → Task 14 (联调)
Task 1-12 全部完成 → Task 14
```

**推荐执行顺序：** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

Task 1-6 是服务端（纯 Python，与 UE 无关），可独立开发测试。
Task 7-12 是客户端（NePy Python），需在 UE 环境中测试。
Task 13 是 UE 编辑器手动操作。
Task 14 是最终联调。
