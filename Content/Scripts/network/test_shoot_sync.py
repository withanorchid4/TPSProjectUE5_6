# -*- encoding: utf-8 -*-
"""射箭同步测试

场景：A 射箭 → 验证 B 能收到 ScShootResult（起始位置、方向、武器类型一致）
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
    print("射箭同步测试：A 射箭 → B 能否看到")
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

    # ─── A 移动到射箭位置 ───
    print("\n[2] A 移动到 (100, 200, 50)，面朝 yaw=45°")
    move = tps_pb2.CsMove()
    move.location.x = 100
    move.location.y = 200
    move.location.z = 50
    move.rotation.yaw = 45
    cA.send(tps_pb2.CS_MOVE, move.SerializeToString())
    time.sleep(0.1)
    cB.drain()
    cA.drain()

    # ─── A 射箭（普通箭）───
    print("\n[3] A 射出普通箭 weapon_type=0")
    shoot = tps_pb2.CsShoot()
    shoot.start_location.x = 100
    shoot.start_location.y = 200
    shoot.start_location.z = 50
    shoot.direction.yaw = 45
    shoot.direction.pitch = -5
    shoot.weapon_type = 0
    cA.send(tps_pb2.CS_SHOOT, shoot.SerializeToString())

    time.sleep(0.15)
    bcsB = cB.drain()
    bcsA = cA.drain()

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
    print(f"    player_id     = {sr.player_id}  (expect {pidA})")
    print(f"    start_location= ({sr.start_location.x}, {sr.start_location.y}, {sr.start_location.z})")
    print(f"    direction     = pitch={sr.direction.pitch}, yaw={sr.direction.yaw}, roll={sr.direction.roll}")
    print(f"    weapon_type   = {sr.weapon_type}  (0=普通箭)")

    assert sr.player_id == pidA, f"Shooter should be A({pidA}), got {sr.player_id}"
    assert sr.start_location.x == 100, f"start_location.x should be 100, got {sr.start_location.x}"
    assert sr.start_location.y == 200, f"start_location.y should be 200, got {sr.start_location.y}"
    assert sr.start_location.z == 50, f"start_location.z should be 50, got {sr.start_location.z}"
    assert sr.direction.yaw == 45, f"direction.yaw should be 45, got {sr.direction.yaw}"
    assert sr.direction.pitch == -5, f"direction.pitch should be -5, got {sr.direction.pitch}"
    assert sr.weapon_type == 0, f"weapon_type should be 0, got {sr.weapon_type}"
    print("  ✅ B 正确收到 A 的普通箭射击信息")

    # ─── A 射魔法箭 ───
    print("\n[4] A 射出魔法箭 weapon_type=1")
    shoot2 = tps_pb2.CsShoot()
    shoot2.start_location.x = 100
    shoot2.start_location.y = 200
    shoot2.start_location.z = 50
    shoot2.direction.yaw = 90
    shoot2.direction.pitch = 0
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
    print(f"    direction   = yaw={sr2.direction.yaw}")
    print(f"    weapon_type = {sr2.weapon_type}  (1=魔法箭)")

    assert sr2.weapon_type == 1, f"weapon_type should be 1(魔法箭), got {sr2.weapon_type}"
    assert sr2.direction.yaw == 90, f"direction.yaw should be 90, got {sr2.direction.yaw}"
    print("  ✅ B 正确收到 A 的魔法箭射击信息")

    # ─── A 连射3箭 ───
    print("\n[5] A 连射 3 箭，验证 B 全部收到")
    for i in range(3):
        shoot3 = tps_pb2.CsShoot()
        shoot3.start_location.x = 100 + i * 10
        shoot3.start_location.y = 200
        shoot3.start_location.z = 50
        shoot3.direction.yaw = 30 + i * 15
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
        print(f"    [{i}] player={sr3.player_id} start_x={sr3.start_location.x} yaw={sr3.direction.yaw}")

    assert len(rapid_results) == 3, f"B should receive 3 shoot results, got {len(rapid_results)}"
    for i, sr3 in enumerate(rapid_results):
        assert sr3.start_location.x == 100 + i * 10, f"Arrow {i}: start_x should be {100 + i * 10}"
        assert sr3.direction.yaw == 30 + i * 15, f"Arrow {i}: yaw should be {30 + i * 15}"
    print("  ✅ B 正确收到 A 的 3 连射信息，位置和方向完全一致")

    # ─── Cleanup ───
    cA.drain()
    cB.drain()
    cA.close()
    cB.close()

    print("\n" + "=" * 60)
    print("射箭同步测试全部通过！✅")
    print("=" * 60)


if __name__ == "__main__":
    test_shoot_sync()
