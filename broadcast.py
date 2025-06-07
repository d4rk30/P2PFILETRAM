import socket
import threading
import time
from utils import get_broadcast_address, serialize_message, create_node_info


class BroadcastSender:
    """广播发送器"""

    def __init__(self, local_ip, local_port, broadcast_port=23333, interval=1, node_name=None):
        self.local_ip = local_ip
        self.local_port = local_port
        self.broadcast_port = broadcast_port
        self.interval = interval
        self.running = False
        self.thread = None
        self.socket = None
        self.neighbor_manager = None

        # 节点信息
        self.node_info = create_node_info(local_ip, local_port, node_name)

    def start(self, show_message=True):
        """启动广播发送线程"""
        if self.running:
            return False

        self.running = True
        self.thread = threading.Thread(
            target=self._broadcast_loop, daemon=True)
        self.thread.start()
        if show_message:
            print(f"[信息] 广播发送器已启动，端口: {self.broadcast_port}")
        return True

    def stop(self, show_message=True):
        """停止广播发送"""
        if not self.running:
            return  # 如果没有运行，直接返回，不显示消息

        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        if show_message:
            print("[信息] 广播发送器已停止")

    def _broadcast_loop(self):
        """广播循环"""
        # 启动后立即发送一次广播
        if self.running:
            try:
                self._send_broadcast()
            except Exception as e:
                print(f"[错误] 广播发送出错: {e}")

        while self.running:
            try:
                time.sleep(self.interval)
                if self.running:  # 检查是否还在运行
                    self._send_broadcast()
            except Exception as e:
                print(f"[错误] 广播发送出错: {e}")
                time.sleep(self.interval)

    def _send_broadcast(self):
        """发送一次广播"""
        try:
            # 创建UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # 设置超时，避免阻塞
            sock.settimeout(1)

            # 更新节点信息的时间戳，但保留原有的节点名称
            current_name = self.node_info.get('name')
            self.node_info = create_node_info(
                self.local_ip, self.local_port, current_name)

            # 构造广播消息
            message = {
                "type": "NODE_DISCOVERY",
                "node": self.node_info
            }

            # 序列化并发送到广播端口
            data = serialize_message(message)
            if data:
                broadcast_addr = get_broadcast_address()
                sock.sendto(data, (broadcast_addr, self.broadcast_port))
                # print(f"[调试] 已发送广播: {self.node_info['name']} ({self.local_ip}:{self.local_port}) -> {broadcast_addr}:{self.broadcast_port}")

            sock.close()

        except Exception as e:
            if "Address already in use" not in str(e):  # 忽略端口占用错误的输出
                print(f"[错误] 发送广播失败: {e}")

    def update_node_info(self, **kwargs):
        """更新节点信息"""
        for key, value in kwargs.items():
            if key in self.node_info:
                self.node_info[key] = value

    def get_node_info(self):
        """获取当前节点信息"""
        return self.node_info.copy()

    def set_neighbor_manager(self, neighbor_manager):
        """设置邻居管理器，用于检查名称重复"""
        self.neighbor_manager = neighbor_manager

        # 如果当前名称是自动生成的，重新生成唯一名称
        if self.node_info['name'].startswith('node_'):
            from utils import generate_unique_node_name
            new_name = generate_unique_node_name(neighbor_manager)
            self.node_info['name'] = new_name

    def is_running(self):
        """检查是否正在运行"""
        return self.running
