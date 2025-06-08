#!/usr/bin/env python3
"""
文件接收模块
负责处理文件接收请求和实际的文件接收
"""

import os
import socket
import threading
import time
import sys
import queue
from typing import Optional, Callable

from protocol import Protocol, MessageType

# 全局输入锁，确保同时只有一个线程可以使用input()
input_lock = threading.Lock()

# 全局文件请求队列，用于在主线程中处理用户交互
file_request_queue = queue.Queue()


class FileReceiver:
    """文件接收类"""

    def __init__(self, local_ip: str, local_port: int):
        self.local_ip = local_ip
        self.local_port = local_port
        self.receive_sessions = {}  # 接收会话管理
        self.download_dir = "./downloads"  # 下载目录

        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)

    def handle_file_offer(self, message: dict, sender_addr: tuple,
                          sender_port: int, callback: Optional[Callable] = None) -> bool:
        """处理文件发送请求 - 将请求放入队列，由主线程处理"""
        try:
            sender_ip = message.get("sender_ip")
            sender_port = message.get("sender_port")
            file_name = message.get("file_name")
            file_size = message.get("file_size")
            file_md5 = message.get("file_md5")

            if not all([sender_ip, sender_port, file_name, file_size, file_md5]):
                print("[错误] 文件请求信息不完整")
                return False

            # 将文件请求放入队列，由主线程处理用户交互
            request_data = {
                'sender_ip': sender_ip,
                'sender_port': sender_port,
                'file_name': file_name,
                'file_size': file_size,
                'file_md5': file_md5,
                'response_port': sender_port,
                'callback': callback,
                'receiver': self  # 传递接收器实例
            }

            # 放入队列并通知主线程
            file_request_queue.put(request_data)

            # 显示通知（不等待用户输入）
            print(f"\n[通知] 收到来自 {sender_ip}:{sender_port} 的文件传输请求")
            print(f"[通知] 请输入回车继续...")

            return True

        except Exception as e:
            print(f"[错误] 处理文件请求失败: {e}")
            return False

    def _accept_file_transfer(self, sender_ip: str, sender_port: int, file_name: str,
                              file_size: int, file_md5: str, response_port: int,
                              callback: Optional[Callable]) -> bool:
        """接受文件传输"""
        try:
            # 创建TCP监听socket
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_sock.bind((self.local_ip, 0))  # 动态分配端口
            tcp_port = tcp_sock.getsockname()[1]
            tcp_sock.listen(1)

            print(f"[信息] 已接受，开始接收...")

            # 发送确认消息
            confirm_message = Protocol.create_receive_response(True, tcp_port)
            response_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            response_sock.sendto(confirm_message, (sender_ip, response_port))
            response_sock.close()

            # 启动接收线程
            receive_thread = threading.Thread(
                target=self._receive_file_data,
                args=(tcp_sock, file_name, file_size, file_md5, callback)
            )
            receive_thread.daemon = True
            receive_thread.start()

            return True

        except Exception as e:
            print(f"[错误] 准备接收文件失败: {e}")
            return False

    def _reject_file_transfer(self, sender_ip: str, response_port: int) -> bool:
        """拒绝文件传输"""
        try:
            reject_message = Protocol.create_receive_response(False)
            response_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            response_sock.sendto(reject_message, (sender_ip, response_port))
            response_sock.close()

            print("[信息] 已拒绝文件传输请求")
            return True

        except Exception as e:
            print(f"[错误] 发送拒绝消息失败: {e}")
            return False

    def _receive_file_data(self, tcp_sock: socket.socket, file_name: str,
                           expected_size: int, expected_md5: str,
                           callback: Optional[Callable]):
        """接收文件数据"""
        client_sock = None
        file_path = None

        try:
            # 等待连接
            tcp_sock.settimeout(30.0)
            client_sock, addr = tcp_sock.accept()
            client_sock.settimeout(10.0)

            print(f"[信息] 开始接收来自 {addr[0]} 的文件...")

            # 准备文件保存路径
            file_path = os.path.join(self.download_dir, file_name)
            # 如果文件已存在，添加数字后缀
            counter = 1
            base_name, ext = os.path.splitext(file_name)
            while os.path.exists(file_path):
                new_name = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(self.download_dir, new_name)
                counter += 1

            # 接收文件元信息
            meta_length = int.from_bytes(client_sock.recv(4), byteorder='big')
            meta_data = client_sock.recv(meta_length)
            meta_message = Protocol.parse_message(meta_data)

            if not meta_message or meta_message.get("type") != MessageType.FILE_META:
                raise Exception("文件元信息无效")

            total_blocks = meta_message.get("total_blocks", 0)
            print(f"[信息] 文件将分为 {total_blocks} 块接收")

            # 接收文件数据
            bytes_received = 0
            with open(file_path, 'wb') as f:
                block_count = 0

                while block_count < total_blocks:
                    # 接收数据块长度
                    length_data = client_sock.recv(4)
                    if len(length_data) < 4:
                        break

                    block_length = int.from_bytes(length_data, byteorder='big')

                    # 接收数据块
                    block_data = b""
                    while len(block_data) < block_length:
                        chunk = client_sock.recv(
                            min(block_length - len(block_data), 8192))
                        if not chunk:
                            break
                        block_data += chunk

                    if len(block_data) != block_length:
                        raise Exception("数据块接收不完整")

                    # 写入文件
                    f.write(block_data)
                    bytes_received += len(block_data)
                    block_count += 1

                    # 显示进度
                    progress = (bytes_received / expected_size) * 100
                    print(
                        f"\r[接收] 进度: {progress:.1f}% ({Protocol.format_file_size(bytes_received)}/{Protocol.format_file_size(expected_size)})", end='', flush=True)

            print()  # 换行

            # 接收传输完成消息
            complete_length = int.from_bytes(
                client_sock.recv(4), byteorder='big')
            complete_data = client_sock.recv(complete_length)
            complete_message = Protocol.parse_message(complete_data)

            if not complete_message or complete_message.get("type") != MessageType.TRANSFER_COMPLETE:
                raise Exception("传输完成消息无效")

            # 校验文件完整性
            print("[信息] 正在校验文件完整性...")
            received_md5 = Protocol.calculate_file_md5(file_path)

            if received_md5 == expected_md5:
                print("[完成] 文件接收成功，MD5校验一致")
                print(f"[信息] 文件已保存到: {file_path}")

                # 发送ACK确认
                ack_message = Protocol.create_ack(0)
                client_sock.send(len(ack_message).to_bytes(4, byteorder='big'))
                client_sock.send(ack_message)

                if callback:
                    callback(True, f"文件已保存到: {file_path}")

                # 重新显示命令提示符
                print("\nP2P> ", end='', flush=True)

            else:
                print("[错误] 文件校验失败，MD5不匹配")
                # 删除损坏的文件
                try:
                    os.remove(file_path)
                except:
                    pass

                # 发送错误消息
                error_message = Protocol.create_error("MD5校验失败")
                client_sock.send(
                    len(error_message).to_bytes(4, byteorder='big'))
                client_sock.send(error_message)

                if callback:
                    callback(False, "文件校验失败")

                # 重新显示命令提示符
                print("\nP2P> ", end='', flush=True)

        except Exception as e:
            print(f"\n[错误] 文件接收失败: {e}")

            # 清理损坏的文件
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

            if callback:
                callback(False, f"接收失败: {e}")

            # 重新显示命令提示符
            print("\nP2P> ", end='', flush=True)

        finally:
            # 清理资源
            if client_sock:
                try:
                    client_sock.close()
                except:
                    pass
            try:
                tcp_sock.close()
            except:
                pass

    def get_receive_status(self) -> dict:
        """获取接收状态"""
        return self.receive_sessions.copy()

    def set_download_directory(self, directory: str):
        """设置下载目录"""
        self.download_dir = directory
        os.makedirs(self.download_dir, exist_ok=True)


def process_file_request(request_data):
    """在主线程中处理文件请求"""
    receiver = request_data['receiver']
    sender_ip = request_data['sender_ip']
    sender_port = request_data['sender_port']
    file_name = request_data['file_name']
    file_size = request_data['file_size']
    file_md5 = request_data['file_md5']
    response_port = request_data['response_port']
    callback = request_data['callback']

    # 显示文件请求信息
    print(f"\n" + "="*50)
    print(f"[收到文件推送请求]")
    print(f"来自: {sender_ip}:{sender_port}")
    print(f"文件: {file_name} ({Protocol.format_file_size(file_size)})")
    print("="*50)

    # 用户确认 - 在主线程中处理，不需要锁
    try:
        print("是否接受？(y/n): ", end='', flush=True)
        response = input().strip().lower()

        # 处理无效输入
        while response not in ['y', 'yes', '是', 'n', 'no', '否']:
            print("[提示] 请输入 y(是) 或 n(否)")
            print("是否接受？(y/n): ", end='', flush=True)
            response = input().strip().lower()

        if response in ['y', 'yes', '是']:
            # 接受文件
            return receiver._accept_file_transfer(sender_ip, sender_port, file_name,
                                                  file_size, file_md5, response_port, callback)
        else:
            # 拒绝文件
            result = receiver._reject_file_transfer(sender_ip, response_port)
            # 重新显示命令提示符
            print("\nP2P> ", end='', flush=True)
            return result

    except Exception as e:
        print(f"\n[错误] 处理用户输入失败: {e}")
        result = receiver._reject_file_transfer(sender_ip, response_port)
        # 重新显示命令提示符
        print("\nP2P> ", end='', flush=True)
        return result
