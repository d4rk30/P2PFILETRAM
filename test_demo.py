#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
P2P系统测试演示脚本
用于快速测试节点发现功能
"""

import subprocess
import time
import sys
import os

def run_node(port, name, log_file=None):
    """启动一个P2P节点"""
    cmd = [sys.executable, "main.py", "-p", str(port), "-n", name]
    
    if log_file:
        # 将输出重定向到文件
        with open(log_file, "w") as f:
            return subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
    else:
        return subprocess.Popen(cmd)

def main():
    """主测试函数"""
    print("P2P节点发现功能测试演示")
    print("=" * 50)
    
    # 清理之前的日志文件
    for i in range(1, 4):
        log_file = f"node{i}.log"
        if os.path.exists(log_file):
            os.remove(log_file)
    
    processes = []
    
    try:
        print("正在启动3个测试节点...")
        
        # 启动节点1（前台运行，可交互）
        print(f"启动节点1: 端口12000, 名称'测试节点1'")
        p1 = run_node(12000, "测试节点1")
        processes.append(p1)
        time.sleep(2)
        
        # 启动节点2（后台运行）
        print(f"启动节点2: 端口12001, 名称'测试节点2' (后台)")
        p2 = run_node(12001, "测试节点2", "node2.log")
        processes.append(p2)
        time.sleep(2)
        
        # 启动节点3（后台运行）
        print(f"启动节点3: 端口12002, 名称'测试节点3' (后台)")  
        p3 = run_node(12002, "测试节点3", "node3.log")
        processes.append(p3)
        
        print("\n测试说明:")
        print("- 节点1在前台运行，你可以输入命令与它交互")
        print("- 节点2和节点3在后台运行，日志输出到 node2.log 和 node3.log")
        print("- 等待几秒钟后，在节点1中输入 'peers' 查看发现的节点")
        print("- 输入 'exit' 退出节点1，程序会自动清理所有节点")
        print("=" * 50)
        
        # 等待节点1退出
        p1.wait()
        
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试过程中出错: {e}")
    finally:
        # 清理所有进程
        print("\n正在清理测试节点...")
        for i, p in enumerate(processes, 1):
            try:
                if p.poll() is None:  # 进程还在运行
                    print(f"正在停止节点{i}...")
                    p.terminate()
                    p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"强制终止节点{i}")
                p.kill()
            except Exception as e:
                print(f"清理节点{i}时出错: {e}")
        
        print("测试完成")

if __name__ == "__main__":
    main() 