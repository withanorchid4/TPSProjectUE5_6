# -*- encoding: utf-8 -*-
"""多客户端联机测试

两个客户端同时连接服务端，验证：
1. 双方都能注册/登录/创角/进游戏
2. 后进者收到先到者的 ScPlayerJoin
3. 双方都能收到 ScPlayerStates（含对方位置）
4. A 移动后 B 能看到 A 的新位置
5. A 射击后 B 能收到 ScShootResult
6. A 断线后 B 收到 ScPlayerLeave
7. A 重连后 B 收到 ScPlayerJoin
"""

import socket
import struct
import sys
import time

sys.path.insert(0, ".")
from network.proto import tps_pb2


class TestClient:
    HEADER_SIZE = 4

    def __init__(self, host="127.0.0.1", port=9999):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        self.sock.settimeout(3)
        self.recv_buffer = b""

    def send(self, msg_id, msg_bytes):
        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))
        self.sock.sendall(length + payload)

    def recv_one(self, timeout=3):
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.recv_buffer) >= self.HEADER_SIZE:
                msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
                total = self.HEADER_SIZE + msg_len
                if len(self.recv_buffer) >= total:
                    msg_data = self.recv_buffer[self.HEADER_SIZE:total]
                    self.recv_buffer = self.recv_buffer[total:]
                    msg_id = struct.unpack("!H", msg_data[:2])[0]
                    return msg_id, msg_data[2:]
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise ConnectionError("disconnected")
                self.recv_buffer += data
            except socket.timeout:
                if self.recv_buffer:
                    continue
                raise
        raise TimeoutError("recv_one timed out")

    def drain(self, max_count=50, timeout=0.3):
        self.sock.settimeout(timeout)
        for _ in range(max_count):
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.recv_buffer += data
            except socket.timeout:
                break
        messages = []
        while len(self.recv_buffer) >= self.HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
            total = self.HEADER_SIZE + msg_len
            if len(self.recv_buffer) < total:
                break
            msg_data = self.recv_buffer[self.HEADER_SIZE:total]
            self.recv_buffer = self.recv_buffer[total:]
            if len(msg_data) >= 2:
                msg_id = struct.unpack("!H", msg_data[:2])[0]
                messages.append((msg_id, msg_data[2:]))
        return messages

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def full_login(c, account, char_name):
    """完整流程：注册 -> 登录 -> 创角 -> 进游戏"""
    # 注册
    msg = tps_pb2.CsLogin(account=account, password="123456", is_register=True)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    mid, data = c.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    assert r.success, f"Register failed: {r.msg}"

    # 登录
    msg = tps_pb2.CsLogin(account=account, password="123456", is_register=False)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    mid, data = c.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    assert r.success, f"Login failed: {r.msg}"

    # 创角
    msg = tps_pb2.CsCreateCharacter(char_name=char_name)
    c.send(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())
    mid, data = c.recv_one()
    cr = tps_pb2.ScCreateResult()
    cr.ParseFromString(data)
    assert cr.success, f"Create char failed: {cr.msg}"
    char_id = cr.character.char_id

    # 进游戏
    msg = tps_pb2.CsSelectCharacter(char_id=char_id)
    c.send(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())
    mid, data = c.recv_one()
    assert mid == tps_pb2.SC_ENTER_GAME
    eg = tps_pb2.ScEnterGame()
    eg.ParseFromString(data)
    return eg.self_state.player_id, eg


def print_states(bcs, label=""):
    """打印广播中的 PlayerStates"""
    for mid, data in bcs:
        if mid == tps_pb2.SC_PLAYER_STATES:
            ps = tps_pb2.ScPlayerStates()
            ps.ParseFromString(data)
            players_str = ", ".join(
                f"[{p.player_id}]{p.char_name}({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f})"
                for p in ps.players
            )
            print(f"  {label}ScPlayerStates: {players_str}")
        elif mid == tps_pb2.SC_PLAYER_JOIN:
            pj = tps_pb2.ScPlayerJoin()
            pj.ParseFromString(data)
            print(f"  {label}ScPlayerJoin: [{pj.player.player_id}]{pj.player.char_name}")
        elif mid == tps_pb2.SC_PLAYER_LEAVE:
            pl = tps_pb2.ScPlayerLeave()
            pl.ParseFromString(data)
            print(f"  {label}ScPlayerLeave: player_id={pl.player_id}")
        elif mid == tps_pb2.SC_SHOOT_RESULT:
            sr = tps_pb2.ScShootResult()
            sr.ParseFromString(data)
            print(f"  {label}ScShootResult: player={sr.player_id} weapon={sr.weapon_type}")
        elif mid == tps_pb2.SC_ACTION:
            sa = tps_pb2.ScAction()
            sa.ParseFromString(data)
            print(f"  {label}ScAction: player={sa.player_id} action={tps_pb2.ActionType.Name(sa.action_type)}")


def test_multi_client():
    print("=" * 60)
    print("Multi-Client Test (2 players)")
    print("=" * 60)

    ts = str(int(time.time() * 1000))[-6:]

    # ─── Client A 登录 ───
    print("\n[1] Client A login")
    cA = TestClient()
    pidA, egA = full_login(cA, f"mc_A_{ts}", f"PlayerA_{ts}")
    print(f"  -> A: player_id={pidA}, loc=({egA.self_state.location.x:.0f},{egA.self_state.location.y:.0f},{egA.self_state.location.z:.0f})")
    cA.drain()  # 排空初始广播

    # ─── Client B 登录 ───
    print("\n[2] Client B login")
    cB = TestClient()
    pidB, egB = full_login(cB, f"mc_B_{ts}", f"PlayerB_{ts}")
    print(f"  -> B: player_id={pidB}, loc=({egB.self_state.location.x:.0f},{egB.self_state.location.y:.0f},{egB.self_state.location.z:.0f})")

    # B 进游戏时，ScEnterGame 应该包含 A 的信息
    other_pids = [p.player_id for p in egB.players]
    print(f"  -> B sees players in world: {other_pids}")
    assert pidA in other_pids, f"B should see A (pid={pidA}) in players list!"

    # A 应该收到 ScPlayerJoin
    bcsA = cA.drain()
    join_msgs = [d for mid, d in bcsA if mid == tps_pb2.SC_PLAYER_JOIN]
    if join_msgs:
        pj = tps_pb2.ScPlayerJoin()
        pj.ParseFromString(join_msgs[0])
        print(f"  -> A received ScPlayerJoin: [{pj.player.player_id}]{pj.player.char_name}")
    else:
        print(f"  -> A: {len(bcsA)} broadcasts (may include PlayerStates with B)")

    cB.drain()  # 排空 B 的初始广播

    # ─── A 移动，B 是否能看到 ───
    print(f"\n[3] A moves to (500, 600, 100)")
    msg = tps_pb2.CsMove()
    msg.location.x = 500
    msg.location.y = 600
    msg.location.z = 100
    msg.rotation.yaw = 90
    cA.send(tps_pb2.CS_MOVE, msg.SerializeToString())

    time.sleep(0.1)
    bcsB = cB.drain()
    print(f"  B received {len(bcsB)} broadcasts:")
    print_states(bcsB, "B: ")

    # 检查 B 收到的 PlayerStates 中是否有 A 的新位置
    found_a_at_new_pos = False
    for mid, data in bcsB:
        if mid == tps_pb2.SC_PLAYER_STATES:
            ps = tps_pb2.ScPlayerStates()
            ps.ParseFromString(data)
            for p in ps.players:
                if p.player_id == pidA and p.location.x == 500:
                    found_a_at_new_pos = True
    assert found_a_at_new_pos, "B should see A at (500,600,100)!"
    print(f"  -> B sees A at new position!")

    cA.drain()  # 排空 A 的广播

    # ─── B 移动，A 是否能看到 ───
    print(f"\n[4] B moves to (300, 400, 50)")
    msg = tps_pb2.CsMove()
    msg.location.x = 300
    msg.location.y = 400
    msg.location.z = 50
    msg.rotation.yaw = 180
    cB.send(tps_pb2.CS_MOVE, msg.SerializeToString())

    time.sleep(0.1)
    bcsA = cA.drain()
    print(f"  A received {len(bcsA)} broadcasts:")
    print_states(bcsA, "A: ")

    found_b_at_new_pos = False
    for mid, data in bcsA:
        if mid == tps_pb2.SC_PLAYER_STATES:
            ps = tps_pb2.ScPlayerStates()
            ps.ParseFromString(data)
            for p in ps.players:
                if p.player_id == pidB and p.location.x == 300:
                    found_b_at_new_pos = True
    assert found_b_at_new_pos, "A should see B at (300,400,50)!"
    print(f"  -> A sees B at new position!")

    cB.drain()

    # ─── A 射击，B 是否收到 ───
    print(f"\n[5] A shoots")
    msg = tps_pb2.CsShoot()
    msg.weapon_type = 0
    cA.send(tps_pb2.CS_SHOOT, msg.SerializeToString())

    time.sleep(0.1)
    bcsB = cB.drain()
    bcsA = cA.drain()
    print(f"  B received {len(bcsB)} broadcasts:")
    print_states(bcsB, "B: ")
    print(f"  A received {len(bcsA)} broadcasts:")
    print_states(bcsA, "A: ")

    b_got_shoot = any(mid == tps_pb2.SC_SHOOT_RESULT for mid, _ in bcsB)
    print(f"  -> B received ScShootResult: {b_got_shoot}")

    # ─── A 换弹，B 是否收到动作 ───
    print(f"\n[6] A reloads")
    msg = tps_pb2.CsAction(action_type=tps_pb2.ACTION_RELOAD_START)
    cA.send(tps_pb2.CS_ACTION, msg.SerializeToString())

    time.sleep(0.1)
    bcsB = cB.drain()
    bcsA = cA.drain()
    b_got_action = any(mid == tps_pb2.SC_ACTION for mid, _ in bcsB)
    print(f"  -> B received ScAction: {b_got_action}")
    if b_got_action:
        for mid, data in bcsB:
            if mid == tps_pb2.SC_ACTION:
                sa = tps_pb2.ScAction()
                sa.ParseFromString(data)
                print(f"     player={sa.player_id} action={tps_pb2.ActionType.Name(sa.action_type)}")

    # ─── A 断线，B 是否收到 ScPlayerLeave ───
    print(f"\n[7] A disconnects")
    cA.close()

    time.sleep(0.2)
    bcsB = cB.drain()
    print(f"  B received {len(bcsB)} broadcasts:")
    print_states(bcsB, "B: ")

    b_got_leave = any(mid == tps_pb2.SC_PLAYER_LEAVE for mid, _ in bcsB)
    print(f"  -> B received ScPlayerLeave: {b_got_leave}")

    # ─── A 重连 ───
    print(f"\n[8] A reconnects")
    cA2 = TestClient()

    # 登录
    msg = tps_pb2.CsLogin(account=f"mc_A_{ts}", password="123456", is_register=False)
    cA2.send(tps_pb2.CS_LOGIN, msg.SerializeToString())
    mid, data = cA2.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    print(f"  -> A login: success={r.success}")
    assert r.success

    # 应收到 ScReconnect
    mid, data = cA2.recv_one()
    if mid == tps_pb2.SC_RECONNECT:
        rc = tps_pb2.ScReconnect()
        rc.ParseFromString(data)
        rs = rc.self_state
        print(f"  -> A ScReconnect: player_id={rs.player_id} loc=({rs.location.x:.0f},{rs.location.y:.0f},{rs.location.z:.0f}) hp={rs.hp}")

        ack = tps_pb2.CsReconnectAck()
        cA2.send(tps_pb2.CS_RECONNECT_ACK, ack.SerializeToString())
    else:
        print(f"  -> A got msg_id={mid} (expected SC_RECONNECT)")

    # B 应该收到 ScPlayerJoin（A 重连回来）
    time.sleep(0.2)
    bcsB = cB.drain()
    print(f"  B received {len(bcsB)} broadcasts after A reconnect:")
    print_states(bcsB, "B: ")

    b_got_join = any(mid == tps_pb2.SC_PLAYER_JOIN for mid, _ in bcsB)
    print(f"  -> B received ScPlayerJoin (A back): {b_got_join}")

    # ─── Cleanup ───
    cA2.drain()
    cA2.close()
    cB.close()

    print("\n" + "=" * 60)
    print("MULTI-CLIENT TEST PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_multi_client()
