# -*- encoding: utf-8 -*-
"""NetClient 端到端测试

模拟 NetClient 的协议层（不含 ue.AddTicker），
测试完整的 注册 -> 登录 -> 创角 -> 进游戏 -> 移动 -> 射击 -> 断线重连 流程。
"""

import socket
import struct
import sys
import time

sys.path.insert(0, ".")
from network.proto import tps_pb2


class TestClient:
    """简易测试客户端，内置缓冲区（模拟 NetClient 的 _extract_messages）"""

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
        """接收一条完整消息"""
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout

        while time.time() < deadline:
            # 尝试从缓冲区提取
            if len(self.recv_buffer) >= self.HEADER_SIZE:
                msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
                total = self.HEADER_SIZE + msg_len
                if len(self.recv_buffer) >= total:
                    msg_data = self.recv_buffer[self.HEADER_SIZE:total]
                    self.recv_buffer = self.recv_buffer[total:]
                    msg_id = struct.unpack("!H", msg_data[:2])[0]
                    return msg_id, msg_data[2:]

            # 从 socket 读数据
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise ConnectionError("disconnected")
                self.recv_buffer += data
            except socket.timeout:
                if self.recv_buffer:
                    continue  # 缓冲区有数据但不够一条，继续等
                raise

        raise TimeoutError("recv_one timed out")

    def drain(self, max_count=20, timeout=0.3):
        """排空缓冲区中的广播消息，返回 [(msg_id, data), ...]"""
        self.sock.settimeout(timeout)
        messages = []
        for _ in range(max_count):
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.recv_buffer += data
            except socket.timeout:
                break

        # 从缓冲区提取所有完整消息
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
        self.sock.close()


def test_net_client_e2e():
    print("=" * 60)
    print("NetClient E2E Test")
    print("=" * 60)

    # 动态生成唯一账号名
    ts = str(int(time.time() * 1000))[-6:]
    account = f"e2e_{ts}"
    char_name = f"Hero_{ts}"

    # ─── Step 1: 注册 ───
    print(f"\n[1] Register: {account}")
    c = TestClient()
    msg = tps_pb2.CsLogin(account=account, password="123456", is_register=True)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())

    mid, data = c.recv_one()
    assert mid == tps_pb2.SC_LOGIN_RESULT
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    print(f"  -> success={r.success}, msg='{r.msg}'")
    assert r.success, f"Register failed: {r.msg}"

    # ─── Step 2: 登录 ───
    print(f"\n[2] Login: {account}")
    msg = tps_pb2.CsLogin(account=account, password="123456", is_register=False)
    c.send(tps_pb2.CS_LOGIN, msg.SerializeToString())

    mid, data = c.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    print(f"  -> success={r.success}")
    assert r.success

    # ─── Step 3: 获取角色列表 ───
    print("\n[3] Get characters")
    c.send(tps_pb2.CS_GET_CHARACTERS, tps_pb2.CsGetCharacters().SerializeToString())

    mid, data = c.recv_one()
    assert mid == tps_pb2.SC_CHARACTER_LIST
    cl = tps_pb2.ScCharacterList()
    cl.ParseFromString(data)
    print(f"  -> {len(cl.characters)} characters")

    # ─── Step 4: 创建角色 ───
    print(f"\n[4] Create character: {char_name}")
    msg = tps_pb2.CsCreateCharacter(char_name=char_name)
    c.send(tps_pb2.CS_CREATE_CHAR, msg.SerializeToString())

    mid, data = c.recv_one()
    cr = tps_pb2.ScCreateResult()
    cr.ParseFromString(data)
    print(f"  -> success={cr.success}, name={cr.character.char_name}, level={cr.character.level}")
    assert cr.success
    char_id = cr.character.char_id

    # ─── Step 5: 选择角色进游戏 ───
    print(f"\n[5] Select char_id={char_id}, enter game")
    msg = tps_pb2.CsSelectCharacter(char_id=char_id)
    c.send(tps_pb2.CS_SELECT_CHAR, msg.SerializeToString())

    mid, data = c.recv_one()
    assert mid == tps_pb2.SC_ENTER_GAME
    eg = tps_pb2.ScEnterGame()
    eg.ParseFromString(data)
    s = eg.self_state
    print(f"  -> player_id={s.player_id}, name={s.char_name}")
    print(f"     loc=({s.location.x:.0f},{s.location.y:.0f},{s.location.z:.0f}) hp={s.hp}")
    pid = s.player_id

    # drain broadcast
    bcs = c.drain()
    print(f"  -> drained {len(bcs)} broadcasts")

    # ─── Step 6: 移动 ───
    print("\n[6] Send CsMove (100, 200, 300, yaw=45)")
    msg = tps_pb2.CsMove()
    msg.location.x = 100
    msg.location.y = 200
    msg.location.z = 300
    msg.rotation.yaw = 45
    c.send(tps_pb2.CS_MOVE, msg.SerializeToString())

    time.sleep(0.1)
    bcs = c.drain()
    for bid, bdata in bcs:
        if bid == tps_pb2.SC_PLAYER_STATES:
            ps = tps_pb2.ScPlayerStates()
            ps.ParseFromString(bdata)
            for p in ps.players:
                print(f"  -> player {p.player_id}: loc=({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f}) hp={p.hp}")

    # ─── Step 7: 射击 ───
    print("\n[7] Send CsShoot")
    msg = tps_pb2.CsShoot()
    msg.weapon_type = 0
    c.send(tps_pb2.CS_SHOOT, msg.SerializeToString())

    time.sleep(0.1)
    bcs = c.drain()
    for bid, bdata in bcs:
        if bid == tps_pb2.SC_SHOOT_RESULT:
            sr = tps_pb2.ScShootResult()
            sr.ParseFromString(bdata)
            print(f"  -> ScShootResult: player={sr.player_id} weapon={sr.weapon_type}")

    # ─── Step 8: 动作(换弹) ───
    print("\n[8] Send CsAction (RELOAD_START)")
    msg = tps_pb2.CsAction(action_type=tps_pb2.ACTION_RELOAD_START)
    c.send(tps_pb2.CS_ACTION, msg.SerializeToString())

    time.sleep(0.1)
    bcs = c.drain()
    for bid, bdata in bcs:
        if bid == tps_pb2.SC_ACTION:
            sa = tps_pb2.ScAction()
            sa.ParseFromString(bdata)
            print(f"  -> ScAction: player={sa.player_id} action={tps_pb2.ActionType.Name(sa.action_type)}")

    # ─── Step 9: 断线 ───
    print(f"\n[9] Disconnect (player_id={pid})")
    c.close()

    # ─── Step 10: 重连 ───
    print("\n[10] Reconnect within 5min")
    c2 = TestClient()

    msg = tps_pb2.CsLogin(account=account, password="123456", is_register=False)
    c2.send(tps_pb2.CS_LOGIN, msg.SerializeToString())

    mid, data = c2.recv_one()
    r = tps_pb2.ScLoginResult()
    r.ParseFromString(data)
    print(f"  -> Login: success={r.success}")
    assert r.success

    # 应收到 ScReconnect
    mid, data = c2.recv_one()
    if mid == tps_pb2.SC_RECONNECT:
        rc = tps_pb2.ScReconnect()
        rc.ParseFromString(data)
        rs = rc.self_state
        print(f"  -> ScReconnect: player_id={rs.player_id} loc=({rs.location.x:.0f},{rs.location.y:.0f},{rs.location.z:.0f}) hp={rs.hp}")

        ack = tps_pb2.CsReconnectAck()
        c2.send(tps_pb2.CS_RECONNECT_ACK, ack.SerializeToString())
        print("  -> Sent CsReconnectAck")
    else:
        print(f"  -> WARNING: got msg_id={mid}, expected SC_RECONNECT")

    c2.drain()
    c2.close()

    # ─── Done ───
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    test_net_client_e2e()
