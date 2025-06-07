import socket
import time
import json
import platform


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到远程地址（不会实际发送数据）
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # 如果上述方法失败，使用备用方法
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip.startswith("127."):
                # 如果返回回环地址，尝试其他方法
                return "192.168.1.100"  # 默认值
            return local_ip
        except Exception:
            return "192.168.1.100"  # 默认值


def is_port_available(port):
    """检查端口是否可用

    同时检查TCP和UDP端口是否可用
    """
    try:
        # 检查TCP端口
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.bind(('', port))
        tcp_sock.close()

        # 检查UDP端口
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.bind(('', port))
        udp_sock.close()

        return True
    except:
        return False


def find_available_port(start_port, max_attempts=100):
    """查找可用端口

    Args:
        start_port: 起始端口号
        max_attempts: 最大尝试次数

    Returns:
        找到的可用端口号，如果没找到返回None
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None


def get_timestamp():
    """获取当前时间戳"""
    return int(time.time())


def get_broadcast_address():
    """获取广播地址"""
    # 使用全局广播地址，让同一网络内的所有程序都能相互发现
    return "255.255.255.255"


def create_node_info(ip, port, name=None, neighbor_manager=None):
    """创建节点信息字典"""
    if name is None:
        name = generate_unique_node_name(neighbor_manager)

    return {
        "ip": ip,
        "port": port,
        "name": name,
        "timestamp": get_timestamp(),
        "platform": platform.system()
    }


def generate_unique_node_name(neighbor_manager=None):
    """生成唯一的节点名称

    根据已存在的节点数量生成新的节点名称
    """
    if neighbor_manager is None:
        return "node_1"

    # 获取所有已存在的节点名称
    existing_nodes = neighbor_manager.get_all_neighbors()
    existing_names = set()

    # 收集所有node_N格式的名称
    for node_key, node_info in existing_nodes.items():
        name = node_info.get('name', '')
        if name.startswith('node_'):
            try:
                num = int(name.split('_')[1])
                existing_names.add(num)
            except (IndexError, ValueError):
                continue

    # 如果没有任何节点，返回node_1
    if not existing_names:
        return "node_1"

    # 找到最小的未使用编号
    current_num = 1
    while current_num in existing_names:
        current_num += 1

    return f"node_{current_num}"


def serialize_message(data):
    """序列化消息为JSON字符串"""
    try:
        return json.dumps(data).encode('utf-8')
    except Exception as e:
        print(f"序列化错误: {e}")
        return b""


def deserialize_message(data):
    """反序列化JSON消息"""
    try:
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"反序列化错误: {e}")
        return None


def format_time(timestamp):
    """格式化时间戳为可读字符串"""
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
