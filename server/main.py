#!/usr/bin/env python3
"""
TPS 服务端入口

启动命令：
    cd server
    python main.py

默认监听在 0.0.0.0:9999
"""

from game_server import GameServer


if __name__ == "__main__":
    server = GameServer(host="0.0.0.0", port=9999)
    try:
        server.start()
    except KeyboardInterrupt:
        pass
