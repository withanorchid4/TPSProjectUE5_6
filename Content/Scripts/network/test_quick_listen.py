# -*- encoding: utf-8 -*-
import socket, struct, sys, select, time
sys.path.insert(0, ".")
from network.proto import tps_pb2

H = 4

def send_msg(s, mid, data):
    p = struct.pack("!H", mid) + data
    s.sendall(struct.pack("!I", len(p)) + p)

def recv_until(s, buf, expected_mids, timeout=5.0):
    """Keep receiving until we find a message with one of expected_mids, or timeout."""
    found = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        ready = select.select([s], [], [], min(remaining, 0.5))
        if not ready[0]:
            continue
        d = s.recv(65536)
        if not d:
            return found, buf, False
        buf += d
        # Drain immediately available
        while True:
            r2 = select.select([s], [], [], 0)
            if not r2[0]:
                break
            d2 = s.recv(65536)
            if not d2:
                break
            buf += d2
        # Parse
        while len(buf) >= H:
            ml = struct.unpack("!I", buf[:H])[0]
            if len(buf) < H + ml:
                break
            p = buf[H:H+ml]
            buf = buf[H+ml:]
            if len(p) >= 2:
                mid = struct.unpack("!H", p[:2])[0]
                item = (mid, p[2:])
                found.append(item)
                if mid in expected_mids:
                    return found, buf, True
    return found, buf, True

s = socket.socket()
s.connect(("127.0.0.1", 9999))
buf = b""

# Login
print("1. Login...", flush=True)
send_msg(s, tps_pb2.CS_LOGIN, tps_pb2.CsLogin(account="netease2", password="123", is_register=False).SerializeToString())
ms, buf, _ = recv_until(s, buf, [tps_pb2.SC_LOGIN_RESULT], 5)
for mid, d in ms:
    if mid == tps_pb2.SC_LOGIN_RESULT:
        r = tps_pb2.ScLoginResult(); r.ParseFromString(d)
        print(f"   Login: {r.success}", flush=True)

# Get chars
print("2. Get chars...", flush=True)
send_msg(s, tps_pb2.CS_GET_CHARACTERS, tps_pb2.CsGetCharacters().SerializeToString())
ms, buf, _ = recv_until(s, buf, [tps_pb2.SC_CHARACTER_LIST], 5)
cid = None
for mid, d in ms:
    if mid == tps_pb2.SC_CHARACTER_LIST:
        cl = tps_pb2.ScCharacterList(); cl.ParseFromString(d)
        print(f"   Chars: {len(cl.characters)}", flush=True)
        if cl.characters:
            cid = cl.characters[0].char_id

if cid is None:
    print("3. Create char...", flush=True)
    send_msg(s, tps_pb2.CS_CREATE_CHAR, tps_pb2.CsCreateCharacter(char_name="L2").SerializeToString())
    ms, buf, _ = recv_until(s, buf, [tps_pb2.SC_CREATE_RESULT], 5)
    for mid, d in ms:
        if mid == tps_pb2.SC_CREATE_RESULT:
            cr = tps_pb2.ScCreateResult(); cr.ParseFromString(d)
            print(f"   Create: {cr.success} msg={cr.msg}", flush=True)
            if cr.success:
                cid = cr.character.char_id

print(f"   char_id={cid}", flush=True)

# Enter game
print("4. Enter game...", flush=True)
send_msg(s, tps_pb2.CS_SELECT_CHAR, tps_pb2.CsSelectCharacter(char_id=cid).SerializeToString())
ms, buf, _ = recv_until(s, buf, [tps_pb2.SC_ENTER_GAME], 5)
pid = None
for mid, d in ms:
    if mid == tps_pb2.SC_ENTER_GAME:
        eg = tps_pb2.ScEnterGame(); eg.ParseFromString(d)
        pid = eg.self_state.player_id
        print(f"   ENTERED pid={pid}", flush=True)
        for p in eg.players:
            print(f"   other: [{p.player_id}]{p.char_name}", flush=True)

if pid is None:
    print("FAILED to enter game", flush=True)
    s.close()
    sys.exit(1)

# Listen 10 minutes
print(f"\n5. Listening 600s (pid={pid})... Move/shoot in UE! Ctrl+C to stop", flush=True)
end = time.time() + 600
last = 0
last_keepalive = time.time()
while time.time() < end:
    remaining = end - time.time()
    if remaining <= 0:
        break

    # Send keepalive CsMove every 5s so server doesn't kick us
    now = time.time()
    if now - last_keepalive >= 5:
        move = tps_pb2.CsMove()
        move.location.x = 0; move.location.y = 0; move.location.z = 200
        move.rotation.pitch = 0; move.rotation.yaw = 0; move.rotation.roll = 0
        send_msg(s, tps_pb2.CS_MOVE, move.SerializeToString())
        last_keepalive = now

    ready = select.select([s], [], [], min(remaining, 0.5))
    if not ready[0]:
        continue
    d = s.recv(65536)
    if not d:
        break
    buf += d
    # Drain
    while True:
        r2 = select.select([s], [], [], 0)
        if not r2[0]:
            break
        d2 = s.recv(65536)
        if not d2:
            break
        buf += d2
    # Parse
    while len(buf) >= H:
        ml = struct.unpack("!I", buf[:H])[0]
        if len(buf) < H + ml:
            break
        p = buf[H:H+ml]
        buf = buf[H+ml:]
        if len(p) < 2:
            continue
        mid = struct.unpack("!H", p[:2])[0]
        d = p[2:]
        if mid == tps_pb2.SC_PLAYER_STATES:
            now2 = time.time()
            if now2 - last >= 3:
                ps = tps_pb2.ScPlayerStates(); ps.ParseFromString(d)
                for p2 in ps.players:
                    print(f"   [{p2.player_id}]{p2.char_name} ({p2.location.x:.0f},{p2.location.y:.0f},{p2.location.z:.0f}) hp={p2.hp}", flush=True)
                last = now2
        elif mid == tps_pb2.SC_SHOOT_RESULT:
            sr = tps_pb2.ScShootResult(); sr.ParseFromString(d)
            print(f"   SHOOT: pid={sr.player_id} type={sr.weapon_type}", flush=True)
        elif mid == tps_pb2.SC_ACTION:
            sa = tps_pb2.ScAction(); sa.ParseFromString(d)
            print(f"   ACTION: pid={sa.player_id} {tps_pb2.ActionType.Name(sa.action_type)}", flush=True)
        elif mid == tps_pb2.SC_PLAYER_JOIN:
            pj = tps_pb2.ScPlayerJoin(); pj.ParseFromString(d)
            print(f"   JOIN: [{pj.player.player_id}]{pj.player.char_name}", flush=True)
        elif mid == tps_pb2.SC_PLAYER_LEAVE:
            pl = tps_pb2.ScPlayerLeave(); pl.ParseFromString(d)
            print(f"   LEAVE: pid={pl.player_id}", flush=True)

s.close()
print("Done", flush=True)
