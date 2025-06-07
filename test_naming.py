#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试节点命名功能
"""

from neighbors import NeighborManager
from utils import generate_unique_node_name
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_unique_naming():
    """测试唯一命名功能"""
    print("测试节点命名功能...")

    # 创建模拟的邻居管理器
    neighbor_manager = NeighborManager()

    # 模拟添加一些已存在的节点
    existing_nodes = [
        {"ip": "192.168.1.100", "port": 12000, "name": "node_1"},
        {"ip": "192.168.1.101", "port": 12001, "name": "node_2"},
        {"ip": "192.168.1.102", "port": 12002, "name": "用户自定义名称"},
    ]

    for node in existing_nodes:
        neighbor_manager.add_or_update_neighbor(node)

    print("现有节点:")
    for ip, info in neighbor_manager.get_all_neighbors().items():
        print(f"  {info['name']} ({ip}:{info['port']})")

    print("\n生成新的唯一节点名称:")
    for i in range(5):
        new_name = generate_unique_node_name(neighbor_manager)
        print(f"  新节点 {i+1}: {new_name}")

        # 将新名称添加到邻居表中，模拟实际使用
        new_node = {
            "ip": f"192.168.1.{103+i}",
            "port": 12003+i,
            "name": new_name
        }
        neighbor_manager.add_or_update_neighbor(new_node)

    print("\n最终节点列表:")
    for ip, info in neighbor_manager.get_all_neighbors().items():
        print(f"  {info['name']} ({ip}:{info['port']})")


if __name__ == "__main__":
    test_unique_naming()
