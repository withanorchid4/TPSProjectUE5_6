# -*- encoding: utf-8 -*-
"""射击同步测试

场景：A 射击 → 验证 B 能收到 ScShootResult（player_id + weapon_type 一致）
射击只传事件，接收方自行用本地位置/朝向模拟特效。
"""

import socket
import struct
import sys
import time

sys.path.insert(0, ".")
from network.proto import tps_pb2


HEADER_SIZE = 4


class TestClient:
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
            if len(self.recv_buffer) >= HEADER_SIZE:
                msg_len = struct.unpack("!I", self.recv_buffer[:4])[0]
                total = HEADER_SIZE + msg_len
                if len(self.recv_buffer) >= total:
                    msg_data = self.recv_buffer[HEADER_SIZE:total]
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

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def full_login(c, account, char_name):
    """注册→登录→创角→进游戏，返回 (player_id, ScEnterGame)"""
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


def test_shoot_sync():
    print("=" * 60)
    print("射击同步测试：A 射击 → B 能否收到开火事件")
    print("=" * 60)

    ts = str(int(time.time() * 1000))[-6:]

    # ─── 双方登录 ───
    print("\n[1] A & B 登录进游戏")
    cA = TestClient()
    pidA, _ = full_login(cA, f"archer_A_{ts}", f"ArcherA_{ts}")
    cA.drain()

    cB = TestClient()
    pidB, egB = full_login(cB, f"archer_B_{ts}", f"ArcherB_{ts}")
    print(f"  A player_id={pidA}, B player_id={pidB}")
    cB.drain()
    cA.drain()

    # ─── A 射击（普通枪）───
    print("\n[2] A 射击 weapon_type=0")
    shoot = tps_pb2.CsShoot()
    shoot.weapon_type = 0
    cA.send(tps_pb2.CS_SHOOT, shoot.SerializeToString())

    time.sleep(0.15)
    bcsB = cB.drain()
    cA.drain()

    # 找 B 收到的 ScShootResult
    shoot_results_B = []
    for mid, data in bcsB:
        if mid == tps_pb2.SC_SHOOT_RESULT:
            sr = tps_pb2.ScShootResult()
            sr.ParseFromString(data)
            shoot_results_B.append(sr)

    assert len(shoot_results_B) >= 1, f"B should receive ScShootResult, got {len(shoot_results_B)}"
    sr = shoot_results_B[0]

    print(f"  B 收到 ScShootResult:")
    print(f"    player_id   = {sr.player_id}  (expect {pidA})")
    print(f"    weapon_type = {sr.weapon_type}  (0=普通枪)")

    assert sr.player_id == pidA, f"Shooter should be A({pidA}), got {sr.player_id}"
    assert sr.weapon_type == 0, f"weapon_type should be 0, got {sr.weapon_type}"
    print("  ✅ B 正确收到 A 的射击事件")

    # ─── A 射魔法箭 ───
    print("\n[3] A 射出魔法箭 weapon_type=1")
    shoot2 = tps_pb2.CsShoot()
    shoot2.weapon_type = 1
    cA.send(tps_pb2.CS_SHOOT, shoot2.SerializeToString())

    time.sleep(0.15)
    bcsB = cB.drain()

    magic_results = []
    for mid, data in bcsB:
        if mid == tps_pb2.SC_SHOOT_RESULT:
            sr2 = tps_pb2.ScShootResult()
            sr2.ParseFromString(data)
            magic_results.append(sr2)

    assert len(magic_results) >= 1, f"B should receive magic arrow ScShootResult"
    sr2 = magic_results[0]
    print(f"  B 收到魔法箭 ScShootResult:")
    print(f"    player_id   = {sr2.player_id}")
    print(f"    weapon_type = {sr2.weapon_type}  (1=魔法箭)")

    assert sr2.weapon_type == 1, f"weapon_type should be 1(魔法箭), got {sr2.weapon_type}"
    print("  ✅ B 正确收到 A 的魔法箭射击事件")

    # ─── A 连射3发 ───
    print("\n[4] A 连射 3 发，验证 B 全部收到")
    for i in range(3):
        shoot3 = tps_pb2.CsShoot()
        shoot3.weapon_type = 0
        cA.send(tps_pb2.CS_SHOOT, shoot3.SerializeToString())

    time.sleep(0.3)
    bcsB = cB.drain()

    rapid_results = []
    for mid, data in bcsB:
        if mid == tps_pb2.SC_SHOOT_RESULT:
            sr3 = tps_pb2.ScShootResult()
            sr3.ParseFromString(data)
            rapid_results.append(sr3)

    print(f"  B 收到 {len(rapid_results)} 个 ScShootResult")
    for i, sr3 in enumerate(rapid_results):
        print(f"    [{i}] player={sr3.player_id} weapon={sr3.weapon_type}")

    assert len(rapid_results) == 3, f"B should receive 3 shoot results, got {len(rapid_results)}"
    for i, sr3 in enumerate(rapid_results):
        assert sr3.player_id == pidA, f"Shot {i}: player should be A({pidA})"
        assert sr3.weapon_type == 0, f"Shot {i}: weapon_type should be 0"
    print("  ✅ B 正确收到 A 的 3 连射事件")

    # ─── Cleanup ───
    cA.drain()
    cB.drain()
    cA.close()
    cB.close()

    print("\n" + "=" * 60)
    print("射击同步测试全部通过！✅")
    print("=" * 60)


if __name__ == "__main__":
    test_shoot_sync()
