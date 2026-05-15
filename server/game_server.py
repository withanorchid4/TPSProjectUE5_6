import socket
import select
import time
import sys

from db import Database
from game_world import GameWorld
from client_session import ClientSession
from msg_handler import HANDLERS
from proto import tps_pb2
from proto.tps_pb2 import MsgId


class GameServer:
    """游戏服务器主类，管理 select 事件循环和消息分发"""

    def __init__(self, host="0.0.0.0", port=9999):
        self.host = host
        self.port = port
        self.db = Database()
        self.game_world = GameWorld()
        self.active_sessions = {}  # socket -> ClientSession
        self.disconnected_sessions = {}  # account -> player_state dict
        self.disconnect_time = {}  # account -> timestamp
        self.listen_socket = None
        self.running = False

    def start(self):
        """启动服务器"""
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((self.host, self.port))
        self.listen_socket.listen(10)
        self.listen_socket.setblocking(False)
        self.running = True

        print(f"GameServer: Listening on {self.host}:{self.port}")
        print(f"GameServer: Press Ctrl+C to stop")

        self._event_loop()

    def _event_loop(self):
        """select 事件循环"""
        while self.running:
            try:
                all_sockets = [self.listen_socket] + list(self.active_sessions.keys())
                readable, _, _ = select.select(all_sockets, [], [], 0.033)  # ~30fps

                for sock in readable:
                    if sock is self.listen_socket:
                        conn, addr = sock.accept()
                        conn.setblocking(False)
                        self.active_sessions[conn] = ClientSession(conn, addr)
                        print(f"New connection from {addr}")
                    else:
                        session = self.active_sessions[sock]
                        if not session.try_recv():
                            self._on_disconnect(sock)
                            continue

                        for msg_id, data in session.extract_messages():
                            self._dispatch(session, msg_id, data)

                self._broadcast_world_state()
                self._check_expired_reconnects()
                self._check_idle_connections()

            except KeyboardInterrupt:
                print("\nGameServer: Shutting down...")
                self.running = False
            except Exception as e:
                print(f"GameServer: Error in event loop: {e}")

        # 清理
        self._cleanup()

    def _dispatch(self, session, msg_id, data):
        """分发消息到对应的处理器"""
        handler = HANDLERS.get(msg_id)
        if handler:
            broadcasts = handler(self, session, data)
            for bc in broadcasts:
                if len(bc) == 2:
                    self.broadcast(bc[0], bc[1])
                elif len(bc) == 3:
                    self.broadcast(bc[0], bc[1], exclude=bc[2])
        else:
            print(f"GameServer: Unknown message ID: {msg_id}")

    def _on_disconnect(self, sock):
        """处理客户端断线"""
        session = self.active_sessions.pop(sock, None)
        if not session:
            return

        sock.close()
        print(f"Client disconnected: {session.addr}")

        if session.state == "IN_GAME" and session.player_state:
            account = session.account

            # 从 game_world 复制最新的位置/血量到 session.player_state
            pid = session.player_state.get("player_id")
            if pid and pid in self.game_world.players:
                world_state = self.game_world.players[pid]
                session.player_state["location"] = dict(world_state["location"])
                session.player_state["rotation"] = dict(world_state["rotation"])
                session.player_state["hp"] = world_state["hp"]
                session.player_state["move_speed"] = world_state["move_speed"]

            # 保存断线状态（现在包含最新位置）
            self.disconnected_sessions[account] = session.player_state
            self.disconnect_time[account] = time.time()

            # 从游戏世界移除
            pid = session.player_state.get("player_id")
            if pid:
                self.game_world.remove_player(pid)

                # 广播 ScPlayerLeave
                leave_msg = tps_pb2.ScPlayerLeave()
                leave_msg.player_id = pid
                self.broadcast(MsgId.SC_PLAYER_LEAVE, leave_msg.SerializeToString())

                print(f"Player {session.player_state.get('char_name')} disconnected, preserved for 5 minutes")

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
            ps.location.y = p["location"]["y"]
            ps.location.z = p["location"]["z"]
            ps.rotation.pitch = p["rotation"]["pitch"]
            ps.rotation.yaw = p["rotation"]["yaw"]
            ps.rotation.roll = p["rotation"]["roll"]
            ps.hp = p["hp"]
            ps.move_speed = p["move_speed"]
            ps.is_sprinting = p.get("is_sprinting", False)
            ps.is_aiming = p.get("is_aiming", False)
            ps.is_reloading = p.get("is_reloading", False)

        data = states.SerializeToString()
        for session in self.active_sessions.values():
            if session.state == "IN_GAME":
                session.send_msg(MsgId.SC_PLAYER_STATES, data)

    def _check_expired_reconnects(self):
        """检查过期的断线重连记录（5分钟）"""
        now = time.time()
        expired = [a for a, t in self.disconnect_time.items() if now - t > 300]
        for account in expired:
            state = self.disconnected_sessions.pop(account, None)
            del self.disconnect_time[account]
            print(f"Expired reconnect state for account: {account}")

    def _check_idle_connections(self):
        """检测超过30秒无消息的IN_GAME连接，视为断线

        正常客户端每100ms发CsMove，30秒无消息说明已异常断开。
        非IN_GAME状态的连接（如刚连接还没登录）不做检测。
        """
        now = time.time()
        idle_socks = [
            sock for sock, session in self.active_sessions.items()
            if session.state == "IN_GAME" and now - session.last_active > 30
        ]
        for sock in idle_socks:
            print(f"Idle timeout (30s): {self.active_sessions[sock].addr}")
            self._on_disconnect(sock)

    def broadcast(self, msg_id, data, exclude=None):
        """向所有在线玩家广播消息"""
        for session in self.active_sessions.values():
            if session.state == "IN_GAME" and session is not exclude:
                session.send_msg(msg_id, data)

    def _cleanup(self):
        """清理资源"""
        print("GameServer: Cleaning up...")
        for sock in list(self.active_sessions.keys()):
            sock.close()
        if self.listen_socket:
            self.listen_socket.close()
        self.db.close()
        print("GameServer: Shutdown complete")
