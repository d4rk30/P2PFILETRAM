#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import signal
import argparse
import time
import platform
import socket
from utils import get_local_ip, generate_unique_node_name, find_available_port, is_port_available
from neighbors import NeighborManager
from broadcast import BroadcastSender
from listener import BroadcastListener


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
                new_port = port + 1
                print(f"[提示] 端口 {port} 已被占用，尝试使用端口 {new_port}")
                port = new_port

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

        # 初始化广播发送器和监听器（但不启动）
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
            self.broadcast_port
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

        # 启动广播监听器
        if not self.listener.start():
            print("[错误] 启动广播监听器失败")
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
        print("[信息] 程序已退出")
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
                # 保存当前光标位置
                sys.stdout.write("\033[s")  # 保存光标位置
                sys.stdout.write("\033[A")  # 向上移动一行
                sys.stdout.write("\033[2K")  # 清除该行
                sys.stdout.write("\033[u")  # 恢复光标位置
                sys.stdout.flush()

                cmd = input("P2P> ").strip().lower()

                if not cmd:
                    continue

                # 执行命令
                if cmd == 'help':
                    self._show_help()
                elif cmd == 'info' or cmd == 'i':
                    self._show_node_info()
                elif cmd == 'peers' or cmd == 'p':
                    print(self.neighbor_manager.format_neighbors_list())
                elif cmd == 'clear' or cmd == 'c':
                    self._clear_screen()
                    # 清屏后重新显示分隔符
                    print("=" * 62)
                elif cmd == 'quit' or cmd == 'q':
                    self.stop()
                    print("[信息] 程序已退出")
                    break
                else:
                    print(f"[错误] 未知命令: {cmd}")
                    print("[提示] 输入 'help' 查看可用命令")

            except KeyboardInterrupt:
                print("\n[信息] 使用 'quit' 命令退出程序")
            except Exception as e:
                print(f"[错误] 命令执行出错: {e}")

    def _show_help(self):
        """显示帮助信息"""
        print("可用命令:")
        print("info    (i) - 显示节点信息和运行状态")
        print("peers   (p) - 显示在线节点列表")
        print("clear   (c) - 清屏")
        print("help    (h) - 显示本帮助信息")
        print("quit    (q) - 退出程序")

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
        description='P2P文件传输系统 - 第一阶段节点发现',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py                    # 使用默认设置启动
  python main.py -p 12001          # 指定端口
  python main.py -n "我的节点"      # 指定节点名称
  python main.py -b 23334          # 指定广播端口
        """
    )

    parser.add_argument('-p', '--port',
                        type=int,
                        default=12000,
                        help='节点监听端口 (默认: 12000)')

    parser.add_argument('-b', '--broadcast-port',
                        type=int,
                        default=23333,
                        help='广播端口 (默认: 23333)')

    parser.add_argument('-n', '--name',
                        type=str,
                        help='节点名称')

    parser.add_argument('--version',
                        action='version',
                        version='P2P文件传输系统 v1.0 - 第一阶段')

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
        print("\n[信息] 程序被用户中断")
    except Exception as e:
        print(f"[错误] 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("[信息] 程序已退出")


if __name__ == '__main__':
    main()
