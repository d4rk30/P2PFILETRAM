import socket
import threading
from utils import deserialize_message
import sys
import time


class BroadcastListener:
    """广播监听器"""

    def __init__(self, neighbor_manager, local_ip, local_port, broadcast_port=23333):
        self.neighbor_manager = neighbor_manager
        self.local_ip = local_ip
        self.local_port = local_port
        self.broadcast_port = broadcast_port
        self.running = False
        self.thread = None
        self.socket = None

        # 在初始化时检测local_port是否可用（用于端口检测）
        if neighbor_manager is None:  # 这是端口检测调用
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.bind(('', self.local_port))
                test_socket.close()
            except socket.error as e:
                raise Exception(f"端口 {self.local_port} 已被占用")

    def start(self, show_message=True):
        """启动广播监听线程"""
        if self.running:
            return False

        try:
            # 创建UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 在支持的平台上设置SO_REUSEPORT，允许多个程序监听同一端口
            try:
                self.socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass  # 某些平台不支持SO_REUSEPORT

            # 绑定到广播端口，所有节点都监听这个端口
            self.socket.bind(('', self.broadcast_port))
            self.socket.settimeout(1)  # 设置1秒超时

            if show_message:
                print(f"[信息] 广播监听器已启动，监听端口: {self.broadcast_port}")

            self.running = True
            self.thread = threading.Thread(
                target=self._listen_loop, daemon=True)
            self.thread.start()
            return True

        except Exception as e:
            print(f"[错误] 启动广播监听器失败: {e}")
            return False

    def stop(self, show_message=True):
        """停止广播监听"""
        if not self.running:
            return  # 如果没有运行，直接返回，不显示消息

        if show_message:
            print("[信息] 广播监听器已停止")
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _listen_loop(self):
        """监听循环"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                # 处理接收到的数据
                self._handle_broadcast_message(data, addr)
            except socket.timeout:
                continue  # 超时继续等待
            except Exception as e:
                if not self.running:  # 如果是因为停止而导致的错误，忽略它
                    break
                print(f"[错误] 接收广播时出错: {e}")
                time.sleep(1)  # 出错后等待一秒再继续

    def _handle_broadcast_message(self, data, addr):
        """处理接收到的广播消息"""
        try:
            # 反序列化消息
            message = deserialize_message(data)
            if not message:
                return

            # 检查消息类型
            if message.get('type') != 'NODE_DISCOVERY':
                return

            node_info = message.get('node')
            if not node_info:
                return

            node_ip = node_info.get('ip')
            node_port = node_info.get('port')
            node_name = node_info.get('name', 'Unknown')

            if not node_ip or not node_port:
                return

            # 防止自发现 - 忽略来自本机IP且端口相同的广播
            if node_ip == self.local_ip and node_port == self.local_port:
                return

            # 生成节点键
            node_key = f"{node_ip}:{node_port}"

            # 检查是否是新节点
            existing_neighbor = self.neighbor_manager.get_neighbor(node_key)
            is_new_node = existing_neighbor is None

            # 添加或更新邻居节点
            success = self.neighbor_manager.add_or_update_neighbor(node_info)

            # 静默更新邻居节点信息，不显示发现消息
            if success and is_new_node:
                pass  # 新节点发现时不显示消息

        except Exception as e:
            print(f"[错误] 处理广播消息时出错: {e}")

    def is_running(self):
        """检查是否正在运行"""
        return self.running
