#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
调试测试脚本：验证UDP广播是否正常工作
"""

import socket
import json
import time
import threading
import sys


def test_broadcast_send(port, name):
    """测试广播发送"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        message = {
            "type": "NODE_DISCOVERY",
            "node": {
                "ip": "192.168.31.139",  # 替换为你的实际IP
                "port": port,
                "name": name,
                "timestamp": int(time.time())
            }
        }

        data = json.dumps(message).encode('utf-8')
        sock.sendto(data, ("255.255.255.255", 23333))
        sock.close()
        print(f"[{name}] 发送广播成功")

    except Exception as e:
        print(f"[{name}] 发送广播失败: {e}")


def test_broadcast_listen():
    """测试广播监听"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass

        sock.bind(('', 23333))
        sock.settimeout(1)

        print("[监听器] 开始监听广播...")

        count = 0
        while count < 20:  # 监听20秒
            try:
                data, addr = sock.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                node = message.get('node', {})
                print(
                    f"[监听器] 收到广播: {node.get('name')} - {node.get('ip')}:{node.get('port')}")
                count += 1
            except socket.timeout:
                count += 1
                continue
            except Exception as e:
                print(f"[监听器] 接收错误: {e}")
                break

        sock.close()

    except Exception as e:
        print(f"[监听器] 启动失败: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python debug_test.py listen    # 启动监听器")
        print("  python debug_test.py send <port> <name>  # 发送广播")
        return

    if sys.argv[1] == "listen":
        test_broadcast_listen()
    elif sys.argv[1] == "send" and len(sys.argv) >= 4:
        port = int(sys.argv[2])
        name = sys.argv[3]

        for i in range(10):
            test_broadcast_send(port, name)
            time.sleep(2)
    else:
        print("参数错误")


if __name__ == "__main__":
    main()
