import threading
import time
import sys
from utils import get_timestamp, format_time


class NeighborManager:
    """邻居节点管理器"""

    def __init__(self, timeout_seconds=10):
        self.neighbors = {}  # {ip:port: node_info}
        self.lock = threading.Lock()
        self.timeout_seconds = timeout_seconds
        self._running = True

        # 启动清理线程
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired_nodes, daemon=True)
        self.cleanup_thread.start()

    def _get_node_key(self, node_info):
        """生成节点的唯一标识符"""
        ip = node_info.get('ip')
        port = node_info.get('port')
        if not ip or not port:
            return None
        return f"{ip}:{port}"

    def add_or_update_neighbor(self, node_info):
        """添加或更新邻居节点"""
        node_key = self._get_node_key(node_info)
        if not node_key:
            return False

        with self.lock:
            # 更新时间戳
            node_info['timestamp'] = get_timestamp()
            self.neighbors[node_key] = node_info
            return True

    def remove_neighbor(self, node_key):
        """移除邻居节点"""
        with self.lock:
            if node_key in self.neighbors:
                del self.neighbors[node_key]
                return True
            return False

    def get_neighbor(self, node_key):
        """获取特定邻居节点信息"""
        with self.lock:
            return self.neighbors.get(node_key, None)

    def get_all_neighbors(self):
        """获取所有邻居节点信息"""
        with self.lock:
            # 返回副本，避免外部修改
            return dict(self.neighbors)

    def get_neighbor_count(self):
        """获取邻居节点数量"""
        with self.lock:
            return len(self.neighbors)

    def is_neighbor_online(self, node_key):
        """检查邻居节点是否在线"""
        with self.lock:
            if node_key not in self.neighbors:
                return False

            node_info = self.neighbors[node_key]
            current_time = get_timestamp()
            last_seen = node_info.get('timestamp', 0)
            return (current_time - last_seen) <= self.timeout_seconds

    def _cleanup_expired_nodes(self):
        """清理过期节点的后台线程"""
        while self._running:
            try:
                current_time = get_timestamp()
                expired_keys = []

                with self.lock:
                    for node_key, node_info in self.neighbors.items():
                        last_seen = node_info.get('timestamp', 0)
                        if (current_time - last_seen) > self.timeout_seconds:
                            expired_keys.append(
                                (node_key, node_info.get('name', node_key)))

                # 在锁外删除过期节点
                for node_key, node_name in expired_keys:
                    with self.lock:
                        if node_key in self.neighbors:
                            del self.neighbors[node_key]

                # 每5秒检查一次
                time.sleep(5)

            except Exception as e:
                print(f"[错误] 清理过期节点时发生错误: {e}")
                time.sleep(5)

    def format_neighbors_list(self):
        """格式化邻居列表为显示字符串"""
        neighbors = self.get_all_neighbors()

        lines = []
        lines.append("在线节点列表:")
        lines.append(
            f"{'节点名称':<15} {'IP地址':<15} {'端口':<8} {'最后心跳':<12} {'平台':<10}")
        lines.append("-" * 62)

        if not neighbors:
            lines.append("当前没有发现其他在线节点")
            lines.append("-" * 62)
            lines.append("总计: 0 个节点在线")
            return "\n".join(lines)

        for node_key, node_info in neighbors.items():
            name = node_info.get('name', 'Unknown')
            ip = node_info.get('ip', 'N/A')
            port = node_info.get('port', 'N/A')
            timestamp = node_info.get('timestamp', 0)
            platform_info = node_info.get('platform', 'Unknown')
            last_seen = format_time(timestamp)

            lines.append(
                f"{name:<15} {ip:<15} {port:<8} {last_seen:<12} {platform_info:<10}")

        lines.append("-" * 62)
        lines.append(f"总计: {len(neighbors)} 个节点在线")

        return "\n".join(lines)

    def stop(self):
        """停止邻居管理器"""
        self._running = False
        if hasattr(self, 'cleanup_thread') and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=1)

    def __del__(self):
        """析构函数"""
        self.stop()
