#!/usr/bin/env python3
"""
文件发送模块
负责发起文件推送请求和实际的文件传输
"""

import os
import socket
import threading
import time
from typing import Optional, Callable

from protocol import Protocol, MessageType


class FileSender:
    """文件发送类"""

    def __init__(self, local_ip: str, local_port: int):
        self.local_ip = local_ip
        self.local_port = local_port
        self.transfer_sessions = {}  # 传输会话管理
        self.response_handlers = {}  # 响应处理器

    def send_file_offer(self, target_ip: str, target_port: int, file_path: str,
                        broadcast_port: int, callback: Optional[Callable] = None) -> bool:
        """发送文件推送请求"""

        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"[错误] 文件不存在: {file_path}")
            return False

        # 获取文件信息
        try:
            file_size = os.path.getsize(file_path)
            file_md5 = Protocol.calculate_file_md5(file_path)
            if not file_md5:
                return False

            print(
                f"[信息] 正在向 {target_ip}:{target_port} 推送文件 {os.path.basename(file_path)} ({Protocol.format_file_size(file_size)})")

        except Exception as e:
            print(f"[错误] 读取文件信息失败: {e}")
            return False

        # 创建发送请求消息
        offer_message = Protocol.create_send_offer(
            self.local_ip, self.local_port, file_path, file_size, file_md5
        )

        # 发送UDP请求到目标节点的业务端口
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(offer_message, (target_ip, target_port))
            sock.close()

            print("[等待] 等待对方确认...")

            # 注册响应处理器
            response_key = f"{target_ip}:{target_port}"
            self.response_handlers[response_key] = {
                'file_path': file_path,
                'file_md5': file_md5,
                'callback': callback,
                'timestamp': time.time()
            }

            # 启动超时检查线程
            timeout_thread = threading.Thread(
                target=self._check_timeout,
                args=(response_key, 30.0)
            )
            timeout_thread.daemon = True
            timeout_thread.start()

            return True

        except Exception as e:
            print(f"[错误] 发送请求失败: {e}")
            return False

    def handle_response(self, message: dict, sender_addr: tuple):
        """处理文件传输响应"""
        sender_ip = sender_addr[0]
        sender_key = None

        # 找到对应的响应处理器
        for key in self.response_handlers:
            if key.startswith(sender_ip + ":"):
                sender_key = key
                break

        if not sender_key:
            return

        handler = self.response_handlers.get(sender_key)
        if not handler:
            return

        try:
            if message.get("type") == MessageType.RECEIVE_CONFIRM:
                print("[成功] 对方已接受，开始传输...")
                tcp_port = message.get("tcp_port")
                if tcp_port:
                    # 开始文件传输
                    target_ip, target_port = sender_key.split(":")
                    self._start_file_transfer(
                        handler['file_path'], handler['file_md5'],
                        target_ip, tcp_port, handler['callback'])
                # 移除响应处理器
                del self.response_handlers[sender_key]

            elif message.get("type") == MessageType.RECEIVE_REJECT:
                print("[信息] 对方拒绝了文件传输请求")
                if handler['callback']:
                    handler['callback'](False, "对方拒绝")
                # 移除响应处理器
                del self.response_handlers[sender_key]

        except Exception as e:
            print(f"[错误] 处理响应失败: {e}")

    def _check_timeout(self, response_key: str, timeout: float):
        """检查响应超时"""
        time.sleep(timeout)

        handler = self.response_handlers.get(response_key)
        if handler:
            print("[超时] 等待响应超时")
            if handler['callback']:
                handler['callback'](False, "响应超时")
            # 移除超时的响应处理器
            if response_key in self.response_handlers:
                del self.response_handlers[response_key]

    def _start_file_transfer(self, file_path: str, file_md5: str, target_ip: str,
                             target_port: int, callback: Optional[Callable]):
        """开始文件传输"""
        try:
            # 建立TCP连接
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.settimeout(10.0)
            tcp_sock.connect((target_ip, target_port))

            # 发送文件元信息
            file_size = os.path.getsize(file_path)
            total_blocks = (file_size + Protocol.BLOCK_SIZE -
                            1) // Protocol.BLOCK_SIZE

            meta_message = Protocol.create_file_meta(
                os.path.basename(file_path), total_blocks)
            tcp_sock.send(len(meta_message).to_bytes(4, byteorder='big'))
            tcp_sock.send(meta_message)

            # 发送文件数据
            with open(file_path, 'rb') as f:
                block_number = 0
                bytes_sent = 0

                while True:
                    block_data = f.read(Protocol.BLOCK_SIZE)
                    if not block_data:
                        break

                    # 发送数据块长度和数据
                    tcp_sock.send(len(block_data).to_bytes(4, byteorder='big'))
                    tcp_sock.send(block_data)

                    bytes_sent += len(block_data)
                    block_number += 1

                    # 显示进度
                    progress = (bytes_sent / file_size) * 100
                    print(
                        f"\r[传输] 进度: {progress:.1f}% ({Protocol.format_file_size(bytes_sent)}/{Protocol.format_file_size(file_size)})", end='', flush=True)

                    # 等待ACK（可选，简化版本先不等待）
                    time.sleep(0.001)  # 小延迟避免发送过快

            print()  # 换行

            # 发送传输完成消息
            complete_message = Protocol.create_transfer_complete(file_md5)
            tcp_sock.send(len(complete_message).to_bytes(4, byteorder='big'))
            tcp_sock.send(complete_message)

            print("[完成] 文件已发送，等待校验...")

            # 等待最终确认
            response_length = int.from_bytes(tcp_sock.recv(4), byteorder='big')
            response_data = tcp_sock.recv(response_length)
            response = Protocol.parse_message(response_data)

            if response and response.get("type") == MessageType.ACK:
                print("[完成] 文件传输成功，MD5校验一致")
                if callback:
                    callback(True, "传输成功")
            else:
                print("[错误] 文件校验失败")
                if callback:
                    callback(False, "校验失败")

        except Exception as e:
            print(f"\n[错误] 文件传输失败: {e}")
            if callback:
                callback(False, f"传输失败: {e}")
        finally:
            try:
                tcp_sock.close()
            except:
                pass

    def get_transfer_status(self) -> dict:
        """获取传输状态"""
        return self.transfer_sessions.copy()
