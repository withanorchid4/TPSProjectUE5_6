# -*- encoding: utf-8 -*-
"""Simple listener - connect as netease2, print broadcasts"""
import socket, struct, sys, time
sys.path.insert(0, "network")
from proto import tps_pb2

HEADER = 4

def send_msg(sock, msg_id, data):
    payload = struct.pack("!H", msg_id) + data
    sock.sendall(struct.pack("!I", len(payload)) + payload)

def recv_all(sock, buf, timeout=2.0):
    sock.settimeout(timeout)
    msgs = []
    try:
        while True:
            data = sock.recv(8192)
            if not data:
                return msgs, buf, False
            buf += data
    except socket.timeout:
        pass
    while len(buf) >= HEADER:
        ml = struct.unpack("!I", buf[:HEADER])[0]
        total = HEADER + ml
        if len(buf) < total:
            break
        payload = buf[HEADER:total]
        buf = buf[total:]
        if len(payload) >= 2:
            mid = struct.unpack("!H", payload[:2])[0]
            msgs.append((mid, payload[2:]))
    return msgs, buf, True

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 9999))
buf = b""

# Register netease2
send_msg(sock, tps_pb2.CS_LOGIN, tps_pb2.CsLogin(account="netease2", password="123", is_register=True).SerializeToString())
msgs, buf, ok = recv_all(sock, buf, 2)
for mid, data in msgs:
    if mid == tps_pb2.SC_LOGIN_RESULT:
        r = tps_pb2.ScLoginResult(); r.ParseFromString(data)
        print(f"Register: {r.success} {r.msg}")

# Login
send_msg(sock, tps_pb2.CS_LOGIN, tps_pb2.CsLogin(account="netease2", password="123", is_register=False).SerializeToString())
msgs, buf, ok = recv_all(sock, buf, 2)
for mid, data in msgs:
    if mid == tps_pb2.SC_LOGIN_RESULT:
        r = tps_pb2.ScLoginResult(); r.ParseFromString(data)
        print(f"Login: {r.success}")

# Get characters
send_msg(sock, tps_pb2.CS_GET_CHARACTERS, tps_pb2.CsGetCharacters().SerializeToString())
msgs, buf, ok = recv_all(sock, buf, 2)
char_id = None
for mid, data in msgs:
    if mid == tps_pb2.SC_CHARACTER_LIST:
        cl = tps_pb2.ScCharacterList(); cl.ParseFromString(data)
        print(f"Characters: {len(cl.characters)}")
        if cl.characters:
            char_id = cl.characters[0].char_id
            print(f"  Using char id={char_id}")

if char_id is None:
    # Create
    send_msg(sock, tps_pb2.CS_CREATE_CHAR, tps_pb2.CsCreateCharacter(char_name="Listener2").SerializeToString())
    msgs, buf, ok = recv_all(sock, buf, 3)
    for mid, data in msgs:
        if mid == tps_pb2.SC_CREATE_RESULT:
            cr = tps_pb2.ScCreateResult(); cr.ParseFromString(data)
            print(f"Create: {cr.success} {cr.msg}")
            if cr.success:
                char_id = cr.character.char_id
                print(f"  char_id={char_id}")

if char_id is None:
    print("FAIL: no character")
    sock.close()
    sys.exit(1)

# Select & enter
send_msg(sock, tps_pb2.CS_SELECT_CHAR, tps_pb2.CsSelectCharacter(char_id=char_id).SerializeToString())
msgs, buf, ok = recv_all(sock, buf, 3)
my_pid = None
for mid, data in msgs:
    if mid == tps_pb2.SC_ENTER_GAME:
        eg = tps_pb2.ScEnterGame(); eg.ParseFromString(data)
        my_pid = eg.self_state.player_id
        print(f"Entered game! pid={my_pid}")
        for p in eg.players:
            print(f"  Other: [{p.player_id}]{p.char_name} ({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f})")

if my_pid is None:
    print("FAIL: didn't enter game")
    # Print whatever we got
    for mid, data in msgs:
        print(f"  msg_id={mid} len={len(data)}")
    sock.close()
    sys.exit(1)

# Drain
msgs, buf, ok = recv_all(sock, buf, 0.5)

print("\n=== LISTENING (Ctrl+C to stop) ===")
last_ps = 0
try:
    while True:
        msgs, buf, ok = recv_all(sock, buf, 0.5)
        if not ok:
            print("Disconnected")
            break
        for mid, data in msgs:
            if mid == tps_pb2.SC_PLAYER_STATES:
                now = time.time()
                if now - last_ps >= 2.0:
                    ps = tps_pb2.ScPlayerStates(); ps.ParseFromString(data)
                    parts = []
                    for p in ps.players:
                        parts.append(f"[{p.player_id}]{p.char_name}({p.location.x:.0f},{p.location.y:.0f},{p.location.z:.0f}) hp={p.hp}")
                    print(f"  ScPlayerStates: {', '.join(parts)}")
                    last_ps = now
            elif mid == tps_pb2.SC_SHOOT_RESULT:
                sr = tps_pb2.ScShootResult(); sr.ParseFromString(data)
                wt = "magic" if sr.weapon_type == 1 else "normal"
                print(f"  >>> ScShootResult: pid={sr.player_id} {wt}")
            elif mid == tps_pb2.SC_ACTION:
                sa = tps_pb2.ScAction(); sa.ParseFromString(data)
                print(f"  >>> ScAction: pid={sa.player_id} {tps_pb2.ActionType.Name(sa.action_type)}")
            elif mid == tps_pb2.SC_PLAYER_JOIN:
                pj = tps_pb2.ScPlayerJoin(); pj.ParseFromString(data)
                print(f"  >>> ScPlayerJoin: [{pj.player.player_id}]{pj.player.char_name}")
            elif mid == tps_pb2.SC_PLAYER_LEAVE:
                pl = tps_pb2.ScPlayerLeave(); pl.ParseFromString(data)
                print(f"  >>> ScPlayerLeave: pid={pl.player_id}")
            else:
                print(f"  msg_id={mid} len={len(data)}")
except KeyboardInterrupt:
    print("\nStopped")
sock.close()
