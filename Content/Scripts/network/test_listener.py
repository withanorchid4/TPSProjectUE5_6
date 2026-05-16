# -*- encoding: utf-8 -*-
"""监听客户端 — 连接服务器后持续打印收到的广播

用法:
    1. 启动服务端: cd server && python main.py
    2. 在 UE 编辑器里 Play 进游戏（会用 netease1 自动登录）
    3. 运行本脚本: cd Content/Scripts && python network/test_listener.py
    4. 在游戏里移动/射击/换弹/瞄准，观察本脚本输出
"""

import socket
import struct
import sys
import time
import threading

sys.path.insert(0, ".")
from network.proto import tps_pb2


HEADER_SIZE = 4


class ListenerClient:
    def __init__(self, host="127.0.0.1", port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.settimeout(0.5)
        self.recv_buffer = b""
        self.running = True

    def send(self, msg_id, msg_bytes):
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        self.sock.sendall(length + payload)

    def recv_messages(self, timeout=0.5):
        """非阻塞收包，返回所有完整消息"""
        self.sock.settimeout(timeout)
        try:
            data = self.sock.recv(8192)
            if not data:
                return []
            self.recv_buffer += data
        except socket.timeout:
            pass
        except ConnectionResetError:
            print("[DISCONNECTED] Server reset connection")
            self.running = False
            return []

        messages = []
        while len(self.recv_buffer) >= HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:HEADER_SIZE])[0]
            total = HEADER_SIZE + msg_len
            if len(self.recv_buffer) < total:
                break
            msg_data = self.recv_buffer[HEADER_SIZE:total]
            self.recv_buffer = self.recv_buffer[total:]
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))
        return messages

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


def decode_and_print(msg_id, data):
    """解析并打印消息"""
    if msg_id == tps_pb2.SC_PLAYER_STATES:
        ps = tps_pb2.ScPlayerStates()
        ps.ParseFromString(data)
        # 只打印有变化的玩家（避免刷屏）
        parts = []
        for p in ps.players:
            parts.append(f"[{p.player_id}]{p.char_name}({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f}) hp={p.hp} sprint={p.is_sprinting} aim={p.is_aiming} reload={p.is_reloading}")
        print(f"  ScPlayerStates: {', '.join(parts)}")

    elif msg_id == tps_pb2.SC_PLAYER_JOIN:
        pj = tps_pb2.ScPlayerJoin()
        pj.ParseFromString(data)
        p = pj.player
        print(f"  >>> ScPlayerJoin: [{p.player_id}]{p.char_name} at ({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f})")

    elif msg_id == tps_pb2.SC_PLAYER_LEAVE:
        pl = tps_pb2.ScPlayerLeave()
        pl.ParseFromString(data)
        print(f"  >>> ScPlayerLeave: player_id={pl.player_id}")

    elif msg_id == tps_pb2.SC_SHOOT_RESULT:
        sr = tps_pb2.ScShootResult()
        sr.ParseFromString(data)
        wt = "magic_arrow" if sr.weapon_type == 1 else "gun"
        print(f"  >>> ScShootResult: player={sr.player_id} weapon={wt}")

    elif msg_id == tps_pb2.SC_ACTION:
        sa = tps_pb2.ScAction()
        sa.ParseFromString(data)
        action_name = tps_pb2.ActionType.Name(sa.action_type)
        print(f"  >>> ScAction: player={sa.player_id} action={action_name}")

    elif msg_id == tps_pb2.SC_ENEMY_EVENT:
        se = tps_pb2.ScEnemyEvent()
        se.ParseFromString(data)
        print(f"  >>> ScEnemyEvent: enemy={se.enemy_id} type={se.event_type} value={se.value} by={se.player_id}")

    else:
        name = tps_pb2.MsgId.Name(msg_id) if hasattr(tps_pb2.MsgId, 'Name') else str(msg_id)
        print(f"  [{msg_id}] {name} ({len(data)} bytes)")


def main():
    print("=" * 60)
    print("Listener Client — 监听其他玩家的动作")
    print("=" * 60)

    # 用 netease2 账号（UE 客户端会用 netease1）
    ACCOUNT = "netease2"
    PASSWORD = "123"
    CHAR_NAME = "Listener"

    c = ListenerClient()

    # 注册
    print("\n[1] Register...")
    msg = tps_pb2.CsLogin(account=ACCOUNT, password=PASSWORD, is_register=True)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    msgs = c.recv_messages(3)
    for mid, data in msgs:
        if mid == tps_pb2.SC_LOGIN_RESULT:
            r = tps_pb2.ScLoginResult()
            r.ParseFromString(data)
            print(f"  Register: success={r.success} msg={r.msg}")

    # 登录
    print("\n[2] Login...")
    msg = tps_pb2.CsLogin(account=ACCOUNT, password=PASSWORD, is_register=False)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    msgs = c.recv_messages(3)
    for mid, data in msgs:
        if mid == tps_pb2.SC_LOGIN_RESULT:
            r = tps_pb2.ScLoginResult()
            r.ParseFromString(data)
            print(f"  Login: success={r.success}")

    # 获取角色列表
    print("\n[3] Get characters...")
    msg = tps_pb2.CsGetCharacters()
    c.send(tps_pb2.CS_GET_CHARACTERS, msg.SerializeToString())
    msgs = c.recv_messages(3)
    char_id = None
    for mid, data in msgs:
        if mid == tps_pb2.SC_CHARACTER_LIST:
            cl = tps_pb2.ScCharacterList()
            cl.ParseFromString(data)
            if len(cl.characters) > 0:
                char_id = cl.characters[0].char_id
                print(f"  Using existing character: {cl.characters[0].char_name} (id={char_id})")

    if char_id is None:
        # 创建角色
        print("\n[4] Create character...")
        msg = tps_pb2.CsCreateCharacter(char_name=CHAR_NAME)
        c.send(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())
        msgs = c.recv_messages(3)
        for mid, data in msgs:
            if mid == tps_pb2.SC_CREATE_RESULT:
                cr = tps_pb2.ScCreateResult()
                cr.ParseFromString(data)
                char_id = cr.character.char_id
                print(f"  Created: {cr.character.char_name} (id={char_id})")

    # 选择角色进游戏
    print("\n[5] Select character & enter game...")
    msg = tps_pb2.CsSelectCharacter(char_id=char_id)
    c.send(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())
    msgs = c.recv_messages(3)
    my_pid = None
    for mid, data in msgs:
        if mid == tps_pb2.SC_ENTER_GAME:
            eg = tps_pb2.ScEnterGame()
            eg.ParseFromString(data)
            my_pid = eg.self_state.player_id
            print(f"  Entered game! my player_id={my_pid}")
            if len(eg.players) > 0:
                for p in eg.players:
                    print(f"  Other player in world: [{p.player_id}]{p.char_name}")

    if my_pid is None:
        print("ERROR: Failed to enter game!")
        c.close()
        return

    # 排空初始广播
    c.recv_messages(1)

    print("\n" + "=" * 60)
    print(f"Listening... (my player_id={my_pid})")
    print("Now go play in UE! Move, shoot, reload, aim...")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # 持续监听
    last_player_states_time = 0
    try:
        while c.running:
            msgs = c.recv_messages(0.5)
            for mid, data in msgs:
                # ScPlayerStates 太频繁，只每2秒打印一次
                if mid == tps_pb2.SC_PLAYER_STATES:
                    now = time.time()
                    if now - last_player_states_time >= 2.0:
                        decode_and_print(mid, data)
                        last_player_states_time = now
                else:
                    decode_and_print(mid, data)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        c.close()


if __name__ == "__main__":
    main()
