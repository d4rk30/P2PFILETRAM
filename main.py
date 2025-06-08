#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import signal
import argparse
import time
import platform
import socket
import os
from utils import get_local_ip, generate_unique_node_name, find_available_port, is_port_available
from neighbors import NeighborManager
from broadcast import BroadcastSender
from listener import BroadcastListener
from send_file import FileSender
from recv_file import FileReceiver, input_lock, file_request_queue, process_file_request


class P2PNode:
    """P2P节点主类"""

    def __init__(self, port=12000, broadcast_port=23333, node_name=None):
        # 首先显示启动横幅
        self._print_banner()

        self.local_ip = get_local_ip()
        self.broadcast_port = broadcast_port

        # 检查端口是否可用，如果不可用则自动寻找下一个可用端口
        while True:
            try:
                # 创建一个实际的监听socket来测试端口
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                test_socket.bind(('', port))
                test_socket.close()
                break  # 如果成功绑定，说明端口可用
            except socket.error as e:
                # 尝试下一个端口
                port = port + 1

        self.port = port

        # 初始化组件
        self.neighbor_manager = NeighborManager()

        # 创建并启动临时监听器来发现现有节点
        print("[信息] 正在扫描网络中的节点...")
        temp_listener = BroadcastListener(
            self.neighbor_manager,
            self.local_ip,
            self.port,
            self.broadcast_port
        )
        temp_listener.start(show_message=False)

        # 等待足够的时间来发现节点（只监听，不发送广播）
        print("[信息] 正在等待发现其他节点...")
        time.sleep(3)  # 3秒确保能收到多次广播（间隔1秒）

        # 停止临时监听器（不显示停止消息）
        temp_listener.stop(show_message=False)
        print("[信息] 节点扫描完成")

        # 如果没有指定节点名称，根据已发现的节点生成唯一名称
        if node_name is None:
            self.node_name = generate_unique_node_name(self.neighbor_manager)
            print(f"[信息] 自动分配节点名称: {self.node_name}")
        else:
            self.node_name = node_name

        # 初始化网络组件（但不启动）
        self._init_network_components()

        # 运行状态
        self.running = False
        self._start_time = time.time()

        # 创建并绑定业务端口socket，让其他程序能检测到端口占用
        self.business_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.business_socket.bind(('', self.port))

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_network_components(self):
        """初始化网络组件"""
        # 初始化文件传输组件
        self.file_sender = FileSender(self.local_ip, self.port)
        self.file_receiver = FileReceiver(self.local_ip, self.port)

        # 初始化广播组件
        self.broadcaster = BroadcastSender(
            self.local_ip,
            self.port,
            self.broadcast_port,
            node_name=self.node_name
        )
        self.listener = BroadcastListener(
            self.neighbor_manager,
            self.local_ip,
            self.port,
            self.broadcast_port,
            file_receiver=self.file_receiver,
            file_sender=self.file_sender
        )

    def start(self):
        """启动P2P节点"""
        if self.running:
            print("[错误] 节点已经在运行")
            return False

        # 启动组件
        print("[信息] 正在启动节点...")

        # 启动广播发送器
        if not self.broadcaster.start():
            print("[错误] 启动广播发送器失败")
            return False

        # 启动统一监听器
        if not self.listener.start():
            print("[错误] 启动监听器失败")
            self.broadcaster.stop()
            return False

        self.running = True

        # 等待一小段时间，让可能的节点发现消息显示出来
        time.sleep(1)

        # 显示提示信息和分隔符
        print("[提示] 输入 'help' 查看可用命令")
        print("=" * 62)

        # 启动命令行界面
        self._start_cli()
        return True

    def stop(self):
        """停止P2P节点"""
        if not self.running:
            return

        print("[信息] 正在停止节点...")
        self.running = False
        self.broadcaster.stop()
        self.listener.stop()
        self.neighbor_manager.stop()

        # 关闭业务端口socket
        if hasattr(self, 'business_socket'):
            try:
                self.business_socket.close()
            except:
                pass

        print("[信息] 节点已停止")

    def _signal_handler(self, signum, frame):
        """处理系统信号"""
        print("\n[信息] 收到停止信号，正在关闭...")
        self.stop()
        sys.exit(0)

    def _show_node_info(self):
        """显示本节点信息"""
        print("节点信息")
        print(f"名称: {self.node_name}")
        print(f"本机地址: {self.local_ip}:{self.port}")
        print(f"广播端口: {self.broadcast_port}")
        print(f"操作系统: {platform.system()}")
        print(f"运行时长: {self._get_uptime()}")
        print()
        print(f"[组件状态]")
        print(
            f"├─ 广播发送: {'✓ 运行中' if self.broadcaster.is_running() else '✗ 已停止'}")
        print(f"├─ 广播监听: {'✓ 运行中' if self.listener.is_running() else '✗ 已停止'}")
        print(f"└─ 在线邻居: {self.neighbor_manager.get_neighbor_count()} 个")

    def _get_uptime(self):
        """获取运行时长"""
        uptime = int(time.time() - self._start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        if hours > 0:
            return f"{hours}小时 {minutes}分钟"
        elif minutes > 0:
            return f"{minutes}分钟 {seconds}秒"
        else:
            return f"{seconds}秒"

    def _start_cli(self):
        """启动命令行界面"""
        while self.running:
            try:
                # 检查是否有待处理的文件请求
                try:
                    request_data = file_request_queue.get_nowait()
                    # 处理文件请求
                    process_file_request(request_data)
                    continue
                except:
                    pass  # 队列为空，继续正常命令处理

                print()  # 添加空行分隔
                with input_lock:  # 使用输入锁确保独占性
                    cmd_input = input("P2P> ").strip()

                if not cmd_input:
                    continue

                # 解析命令和参数
                cmd_parts = cmd_input.split()
                cmd = cmd_parts[0].lower()

                # 执行命令
                if cmd == 'help' or cmd == 'h':
                    self._show_help()
                elif cmd == 'info' or cmd == 'i':
                    self._show_node_info()
                elif cmd == 'peers' or cmd == 'p':
                    print(self.neighbor_manager.format_neighbors_list())
                elif cmd == 'clear' or cmd == 'c':
                    self._clear_screen()
                elif cmd == 'send' or cmd == 's':
                    self._handle_send_command(cmd_parts)
                elif cmd == 'quit' or cmd == 'q':
                    self.stop()
                    break
                else:
                    print(f"[错误] 未知命令: {cmd}")
                    print("[提示] 输入 'help' 查看可用命令")

            except KeyboardInterrupt:
                print("\n[信息] 收到中断信号，正在退出...")
                self.stop()
                break
            except Exception as e:
                print(f"[错误] 命令执行出错: {e}")

    def _handle_send_command(self, cmd_parts):
        """处理send命令"""
        if len(cmd_parts) < 3:
            print("[错误] 用法: send <目标节点IP:端口|节点名称> <文件路径>")
            print("       示例: send 192.168.1.100:12001 ./example.txt")
            print("             send node_2 ./example.txt")
            return

        target = cmd_parts[1]
        file_path = ' '.join(cmd_parts[2:])  # 支持文件路径中的空格

        # 解析目标节点 - 支持IP:端口和节点名称两种格式
        target_ip = None
        target_port = None

        if ':' in target:
            # IP:端口格式
            try:
                target_ip, target_port_str = target.split(':', 1)
                target_port = int(target_port_str)
            except ValueError:
                print("[错误] 端口号必须是数字")
                return
        else:
            # 节点名称格式 - 从在线节点中查找
            found_node = None
            for node_key, node_info in self.neighbor_manager.neighbors.items():
                if node_info.get('name') == target:
                    found_node = node_info
                    target_ip, target_port = node_key.split(':')
                    target_port = int(target_port)
                    break

            if not found_node:
                print(f"[错误] 未找到节点 '{target}'")
                print("[提示] 使用 'peers' 命令查看在线节点列表")
                return

        # 检查目标节点是否在线
        node_key = f"{target_ip}:{target_port}"
        if not self.neighbor_manager.get_neighbor(node_key):
            print(f"[警告] 目标节点 {target} 不在在线节点列表中")
            with input_lock:  # 使用输入锁
                response = input("是否继续发送？(y/n): ").strip().lower()
            if response not in ['y', 'yes', '是']:
                print("[信息] 已取消发送")
                return

        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"[错误] 文件不存在: {file_path}")
            return

        # 发送文件
        self.file_sender.send_file_offer(
            target_ip, target_port, file_path,
            self.broadcast_port, self._send_callback
        )

    def _send_callback(self, success, message):
        """文件发送回调函数"""
        if success:
            print(f"[完成] {message}")
        else:
            print(f"[失败] {message}")

        # 重新显示命令提示符
        print("\nP2P> ", end='', flush=True)

    def _show_help(self):
        """显示帮助信息"""
        print("可用命令:")
        print("info    (i) - 显示节点信息和运行状态")
        print("peers   (p) - 显示在线节点列表")
        print("send    (s) - 发送文件到指定节点")
        print("              用法: send <IP:端口|节点名称> <文件路径>")
        print("clear   (c) - 清屏")
        print("help    (h) - 显示本帮助信息")
        print("quit    (q) - 退出程序")
        sys.stdout.flush()  # 强制刷新输出缓冲区

    def _clear_screen(self):
        """清屏"""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')

    def _print_banner(self):
        """打印程序启动横幅"""
        banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ██████╗ ██████╗ ██████╗     ███████╗██╗██╗     ███████╗    ║
║   ██╔══██╗╚════██╗██╔══██╗    ██╔════╝██║██║     ██╔════╝    ║
║   ██████╔╝ █████╔╝██████╔╝    █████╗  ██║██║     █████╗      ║
║   ██╔═══╝ ██╔═══╝ ██╔═══╝     ██╔══╝  ██║██║     ██╔══╝      ║
║   ██║     ███████╗██║         ██║     ██║███████╗███████╗    ║
║   ╚═╝     ╚══════╝╚═╝         ╚═╝     ╚═╝╚══════╝╚══════╝    ║
║                                                              ║
║             ████████╗██████╗  █████╗ ███╗   ███╗             ║
║             ╚══██╔══╝██╔══██╗██╔══██╗████╗ ████║             ║
║                ██║   ██████╔╝███████║██╔████╔██║             ║
║                ██║   ██╔══██╗██╔══██║██║╚██╔╝██║             ║
║                ██║   ██║  ██║██║  ██║██║ ╚═╝ ██║             ║
║                ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='P2P文件传输系统 - 第二阶段',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,  # 禁用默认的-h选项
        epilog="""
示例用法:
  python main.py                    # 使用默认设置启动
  python main.py -p 12001           # 指定业务端口端口，用来进行文件传输
  python main.py -n "我的节点"      # 指定节点名称
  python main.py -b 23334           # 指定广播端口，用来发现其他节点
        """
    )

    # 手动添加中文帮助选项
    parser.add_argument('-h', '--help',
                        action='help',
                        help='显示此帮助信息并退出')

    parser.add_argument('-p', '--port',
                        type=int,
                        default=12000,
                        help='节点监听端口 (默认: 12000)')

    parser.add_argument('-b', '--broadcast-port',
                        type=int,
                        default=23333,
                        metavar='PORT',
                        help='广播端口 (默认: 23333)')

    parser.add_argument('-n', '--name',
                        type=str,
                        help='节点名称')

    parser.add_argument('--version',
                        action='version',
                        version='P2P文件传输系统 v2.0 - 第二阶段',
                        help='显示程序版本号并退出')

    return parser.parse_args()


def main():
    """主函数"""
    try:
        args = parse_arguments()

        # 创建并启动P2P节点
        node = P2PNode(
            port=args.port,
            broadcast_port=args.broadcast_port,
            node_name=args.name
        )

        node.start()

    except KeyboardInterrupt:
        pass  # Ctrl+C已经在CLI中处理了
    except Exception as e:
        print(f"[错误] 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[信息] 程序已退出")


if __name__ == '__main__':
    main()
