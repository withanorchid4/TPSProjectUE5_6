# -*- encoding: utf-8 -*-
"""NetClient — 客户端网络模块

纯 Python 类，使用 ue.AddTicker 驱动非阻塞 socket 收包。
协议与服务端一致：[4字节大端长度][2字节大端msg_id][protobuf body]

用法:
    from network.net_client import NetClient
    from network.proto import tps_pb2

    client = NetClient()
    client.connect("127.0.0.1", 9999)
    client.register_callback(tps_pb2.SC_LOGIN_RESULT, on_login_result)

    # 发送消息
    msg = tps_pb2.CsLogin()
    msg.account = "test"
    msg.password = "123"
    client.send_msg(tps_pb2.CS_LOGIN, msg.SerializeToString())

    # 断开
    client.disconnect()
"""

import socket
import struct
import select

import ue


class NetClient:
    """客户端网络连接管理器

    状态机: DISCONNECTED → CONNECTING → CONNECTED → LOGGED_IN → IN_GAME
    """

    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2
    STATE_LOGGED_IN = 3
    STATE_IN_GAME = 4

    HEADER_SIZE = 4  # 4字节大端长度头
    MSG_ID_SIZE = 2  # 2字节大端消息ID

    def __init__(self):
        self.sock = None
        self.recv_buffer = b""
        self.state = self.STATE_DISCONNECTED
        self._ticker_handle = None
        self._msg_callbacks = {}      # msg_id -> callback
        self._on_disconnect_cb = None  # 断线回调
        self._account = None          # 当前登录账号

    # ─── 连接 / 断开 ───

    def connect(self, host="127.0.0.1", port=9999):
        """建立非阻塞 TCP 连接，并启动 AddTicker 收包循环"""
        if self.sock:
            self.disconnect()

        self.state = self.STATE_CONNECTING
        self.recv_buffer = b""

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)

            # 非阻塞 connect 会抛 BlockingIOError，属正常
            try:
                self.sock.connect((host, port))
            except BlockingIOError:
                pass  # 连接进行中，需等待完成
            except ConnectionRefusedError:
                ue.LogError(f"NetClient: Connection refused {host}:{port}")
                self.state = self.STATE_DISCONNECTED
                self.sock = None
                return False

            # 等待非阻塞连接完成（跨网络有延迟）
            _, writable, _ = select.select([], [self.sock], [], 5.0)
            if not writable:
                ue.LogError(f"NetClient: Connect timeout {host}:{port}")
                self.state = self.STATE_DISCONNECTED
                self.sock.close()
                self.sock = None
                return False

            # 检查连接是否真的成功
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err != 0:
                ue.LogError(f"NetClient: Connect failed, error={err}")
                self.state = self.STATE_DISCONNECTED
                self.sock.close()
                self.sock = None
                return False

            self.state = self.STATE_CONNECTED
            ue.LogWarning(f"NetClient: Connected to {host}:{port}")

            # 启动 ticker
            if not self._ticker_handle:
                self._ticker_handle = ue.AddTicker(self._on_ticker)

            return True

        except Exception as e:
            ue.LogError(f"NetClient: Connect failed: {e}")
            self.state = self.STATE_DISCONNECTED
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def disconnect(self):
        """断开连接，停止 ticker，清空缓冲"""
        if self._ticker_handle:
            ue.RemoveTicker(self._ticker_handle)
            self._ticker_handle = None

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        self.state = self.STATE_DISCONNECTED
        self.recv_buffer = b""

        if self._on_disconnect_cb:
            try:
                self._on_disconnect_cb()
            except Exception as e:
                ue.LogError(f"NetClient: Disconnect callback error: {e}")

    # ─── 发送 ───

    def send_msg(self, msg_id, msg_bytes):
        """打包并发送一条 protobuf 消息

        协议: [4字节长度][2字节msg_id][protobuf body]
        """
        if not self.sock or self.state == self.STATE_DISCONNECTED:
            return False

        header = struct.pack("!H", msg_id)
        payload = header + msg_bytes
        length = struct.pack("!I", len(payload))

        try:
            self.sock.sendall(length + payload)
            return True
        except Exception as e:
            ue.LogError(f"NetClient: Send failed: {e}")
            self.disconnect()
            return False

    # ─── 回调注册 ───

    def register_callback(self, msg_id, callback):
        """注册消息回调: callback(msg_id, msg_data_bytes)"""
        self._msg_callbacks[msg_id] = callback

    def unregister_callback(self, msg_id):
        """取消某个消息的回调"""
        self._msg_callbacks.pop(msg_id, None)

    def set_disconnect_callback(self, callback):
        """注册断线回调: callback()"""
        self._on_disconnect_cb = callback

    # ─── Ticker 驱动收包 ───

    def _on_ticker(self, delta_time):
        """每帧由 AddTicker 调用，循环 recv 直到掏空 socket 缓冲区"""
        if not self.sock or self.state == self.STATE_DISCONNECTED:
            return False

        # 循环 recv：一次 ticker 可能把多帧积压的消息全收上来
        while True:
            try:
                data = self.sock.recv(8192)
                if not data:
                    ue.LogWarning("NetClient: Server disconnected")
                    self.disconnect()
                    return False
                self.recv_buffer += data
            except BlockingIOError:
                break  # 无更多数据
            except ConnectionResetError:
                ue.LogWarning("NetClient: Connection reset by server")
                self.disconnect()
                return False
            except Exception as e:
                ue.LogError(f"NetClient: Recv error: {e}")
                self.disconnect()
                return False

        # 解包所有完整消息
        msg_count = 0
        for msg_id, msg_data in self._extract_messages():
            msg_count += 1
            cb = self._msg_callbacks.get(msg_id)
            if cb:
                try:
                    cb(msg_id, msg_data)
                except Exception as e:
                    ue.LogError(f"NetClient: Callback error for msg {msg_id}: {e}")

        # 调试：统计收包频率


        return True  # 继续 ticker

    def _extract_messages(self):
        """从 recv_buffer 提取完整消息列表 [(msg_id, protobuf_bytes), ...]"""
        messages = []
        while len(self.recv_buffer) >= self.HEADER_SIZE:
            msg_len = struct.unpack("!I", self.recv_buffer[:self.HEADER_SIZE])[0]
            total = self.HEADER_SIZE + msg_len

            if len(self.recv_buffer) < total:
                break  # 数据不完整，等下次

            msg_data = self.recv_buffer[self.HEADER_SIZE:total]
            self.recv_buffer = self.recv_buffer[total:]

            if len(msg_data) >= self.MSG_ID_SIZE:
                msg_id = struct.unpack("!H", msg_data[:self.MSG_ID_SIZE])[0]
                messages.append((msg_id, msg_data[self.MSG_ID_SIZE:]))

        return messages
