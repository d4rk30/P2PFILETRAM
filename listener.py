import socket
import threading
import sys
import time
from protocol import Protocol, MessageType


class BroadcastListener:
    """统一监听器 - 同时处理广播发现和业务通信"""

    def __init__(self, neighbor_manager, local_ip, local_port, broadcast_port=23333, file_receiver=None, file_sender=None):
        self.neighbor_manager = neighbor_manager
        self.local_ip = local_ip
        self.local_port = local_port
        self.broadcast_port = broadcast_port
        self.running = False

        # 广播监听
        self.broadcast_thread = None
        self.broadcast_socket = None

        # 业务监听
        self.business_thread = None
        self.business_socket = None

        # 文件传输组件
        self.file_receiver = file_receiver
        self.file_sender = file_sender

        # 在初始化时检测local_port是否可用（用于端口检测）
        if neighbor_manager is None:  # 这是端口检测调用
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.bind(('', self.local_port))
                test_socket.close()
            except socket.error as e:
                raise Exception(f"端口 {self.local_port} 已被占用")

    def start(self, show_message=True):
        """启动监听线程"""
        if self.running:
            return False

        self.running = True

        # 启动广播监听
        if not self._start_broadcast_listener(show_message):
            return False

        # 启动业务监听
        if not self._start_business_listener(show_message):
            self._stop_broadcast_listener()
            return False

        return True

    def _start_broadcast_listener(self, show_message=True):
        """启动广播监听"""
        try:
            # 创建UDP socket
            self.broadcast_socket = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM)
            self.broadcast_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 在支持的平台上设置SO_REUSEPORT，允许多个程序监听同一端口
            try:
                self.broadcast_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass  # 某些平台不支持SO_REUSEPORT

            # 绑定到广播端口，所有节点都监听这个端口
            self.broadcast_socket.bind(('', self.broadcast_port))
            self.broadcast_socket.settimeout(1)  # 设置1秒超时

            if show_message:
                print(f"[信息] 广播监听器已启动，监听端口: {self.broadcast_port}")

            self.broadcast_thread = threading.Thread(
                target=self._broadcast_listen_loop, daemon=True)
            self.broadcast_thread.start()
            return True

        except Exception as e:
            print(f"[错误] 启动广播监听器失败: {e}")
            return False

    def _start_business_listener(self, show_message=True):
        """启动业务监听"""
        try:
            # 创建UDP socket监听业务端口
            self.business_socket = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM)
            self.business_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # 在支持的平台上设置SO_REUSEPORT
            try:
                self.business_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass

            # 绑定到业务端口
            self.business_socket.bind((self.local_ip, self.local_port))
            self.business_socket.settimeout(1)  # 设置1秒超时

            if show_message:
                print(f"[信息] 业务监听器已启动，监听端口: {self.local_port}")

            self.business_thread = threading.Thread(
                target=self._business_listen_loop, daemon=True)
            self.business_thread.start()
            return True

        except Exception as e:
            print(f"[错误] 启动业务监听器失败: {e}")
            return False

    def stop(self, show_message=True):
        """停止所有监听"""
        if not self.running:
            return  # 如果没有运行，直接返回，不显示消息

        if show_message:
            print("[信息] 监听器已停止")
        self.running = False

        self._stop_broadcast_listener()
        self._stop_business_listener()

    def _stop_broadcast_listener(self):
        """停止广播监听"""
        if self.broadcast_socket:
            try:
                self.broadcast_socket.close()
            except:
                pass

        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=2)

    def _stop_business_listener(self):
        """停止业务监听"""
        if self.business_socket:
            try:
                self.business_socket.close()
            except:
                pass

        if self.business_thread and self.business_thread.is_alive():
            self.business_thread.join(timeout=2)

    def _broadcast_listen_loop(self):
        """广播监听循环"""
        while self.running:
            try:
                data, addr = self.broadcast_socket.recvfrom(1024)
                # 处理接收到的数据
                self._handle_broadcast_message(data, addr)
            except socket.timeout:
                continue  # 超时继续等待
            except Exception as e:
                if not self.running:  # 如果是因为停止而导致的错误，忽略它
                    break
                print(f"[错误] 接收广播时出错: {e}")
                time.sleep(1)  # 出错后等待一秒再继续

    def _business_listen_loop(self):
        """业务监听循环"""
        while self.running:
            try:
                data, addr = self.business_socket.recvfrom(4096)
                # 处理接收到的数据
                self._handle_business_message(data, addr)
            except socket.timeout:
                continue  # 超时继续等待
            except Exception as e:
                if not self.running:  # 如果是因为停止而导致的错误，忽略它
                    break
                print(f"[错误] 业务监听时出错: {e}")
                time.sleep(1)  # 出错后等待一秒再继续

    def _handle_broadcast_message(self, data, addr):
        """处理接收到的广播消息"""
        try:
            # 解析消息
            message = Protocol.parse_message(data)
            if not message:
                return

            message_type = message.get('type')

            # 处理节点发现消息
            if message_type == MessageType.NODE_DISCOVERY:
                self._handle_node_discovery(message, addr)

            # 处理文件传输请求
            elif message_type == MessageType.SEND_OFFER:
                self._handle_file_offer(message, addr)

        except Exception as e:
            print(f"[错误] 处理广播消息时出错: {e}")

    def _handle_node_discovery(self, message, addr):
        """处理节点发现消息"""
        node_ip = message.get('ip')
        node_port = message.get('port')
        node_name = message.get('name', 'Unknown')

        if not node_ip or not node_port:
            return

        # 防止自发现 - 忽略来自本机IP且端口相同的广播
        if node_ip == self.local_ip and node_port == self.local_port:
            return

        # 构造节点信息
        node_info = {
            'name': node_name,
            'ip': node_ip,
            'port': node_port,
            'timestamp': int(float(message.get('timestamp', time.time()))),
            'platform': message.get('platform', 'Unknown')  # 从消息中获取平台信息
        }

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

    def _handle_file_offer(self, message, addr):
        """处理文件传输请求"""
        if self.file_receiver:
            self.file_receiver.handle_file_offer(
                message, addr, self.broadcast_port)

    def _handle_business_message(self, data, addr):
        """处理业务消息"""
        try:
            # 解析消息
            message = Protocol.parse_message(data)
            if not message:
                return

            message_type = message.get('type')

            # 处理文件传输请求
            if message_type == MessageType.SEND_OFFER:
                self._handle_business_file_offer(message, addr)
            # 处理文件传输响应
            elif message_type in [MessageType.RECEIVE_CONFIRM, MessageType.RECEIVE_REJECT]:
                self._handle_file_response(message, addr)

        except Exception as e:
            print(f"[错误] 处理业务消息时出错: {e}")

    def _handle_business_file_offer(self, message, addr):
        """处理业务端口的文件传输请求"""
        if self.file_receiver:
            # 注意：这里我们需要传递sender的UDP地址，而不是broadcast_port
            # 因为响应需要发送到发送方的监听端口
            self.file_receiver.handle_file_offer(message, addr, addr[1])

    def _handle_file_response(self, message, addr):
        """处理文件传输响应"""
        if self.file_sender:
            self.file_sender.handle_response(message, addr)

    def set_file_receiver(self, file_receiver):
        """设置文件接收器"""
        self.file_receiver = file_receiver

    def set_file_sender(self, file_sender):
        """设置文件发送器"""
        self.file_sender = file_sender

    def is_running(self):
        """检查是否正在运行"""
        return self.running
