#!/usr/bin/env python3
"""
文件传输协议定义模块
定义各种消息类型和序列化方法
"""

import json
import hashlib
import os
from typing import Dict, Any, Optional


class MessageType:
    """消息类型常量"""
    # 节点发现相关
    NODE_DISCOVERY = "NODE_DISCOVERY"

    # 文件传输相关
    SEND_OFFER = "SEND_OFFER"           # 发送文件请求
    RECEIVE_CONFIRM = "RECEIVE_CONFIRM"  # 接受文件
    RECEIVE_REJECT = "RECEIVE_REJECT"    # 拒绝文件
    FILE_META = "FILE_META"             # 文件元信息
    FILE_BLOCK = "FILE_BLOCK"           # 文件分块数据
    ACK = "ACK"                         # 确认消息
    ERR = "ERR"                         # 错误消息
    TRANSFER_COMPLETE = "TRANSFER_COMPLETE"  # 传输完成


class Protocol:
    """协议处理类"""

    BLOCK_SIZE = 64 * 1024  # 64KB 分块大小

    @staticmethod
    def create_discovery_message(node_name: str, node_ip: str, node_port: int) -> bytes:
        """创建节点发现消息"""
        import platform as platform_module
        message = {
            "type": MessageType.NODE_DISCOVERY,
            "name": node_name,
            "ip": node_ip,
            "port": node_port,
            "platform": platform_module.system(),
            "timestamp": str(int(__import__('time').time()))
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_send_offer(sender_ip: str, sender_port: int, file_path: str,
                          file_size: int, file_md5: str) -> bytes:
        """创建文件发送请求消息"""
        message = {
            "type": MessageType.SEND_OFFER,
            "sender_ip": sender_ip,
            "sender_port": sender_port,
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "file_md5": file_md5,
            "timestamp": str(int(__import__('time').time()))
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_receive_response(accepted: bool, receiver_port: Optional[int] = None) -> bytes:
        """创建接收响应消息"""
        message_type = MessageType.RECEIVE_CONFIRM if accepted else MessageType.RECEIVE_REJECT
        message = {
            "type": message_type,
            "timestamp": str(int(__import__('time').time()))
        }
        if accepted and receiver_port:
            message["tcp_port"] = receiver_port
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_file_meta(file_name: str, total_blocks: int) -> bytes:
        """创建文件元信息消息"""
        message = {
            "type": MessageType.FILE_META,
            "file_name": file_name,
            "total_blocks": total_blocks,
            "block_size": Protocol.BLOCK_SIZE
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_ack(block_number: int) -> bytes:
        """创建确认消息"""
        message = {
            "type": MessageType.ACK,
            "block_number": block_number
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_error(error_msg: str) -> bytes:
        """创建错误消息"""
        message = {
            "type": MessageType.ERR,
            "error": error_msg,
            "timestamp": str(int(__import__('time').time()))
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def create_transfer_complete(file_md5: str) -> bytes:
        """创建传输完成消息"""
        message = {
            "type": MessageType.TRANSFER_COMPLETE,
            "file_md5": file_md5,
            "timestamp": str(int(__import__('time').time()))
        }
        return json.dumps(message, ensure_ascii=False).encode('utf-8')

    @staticmethod
    def parse_message(data: bytes) -> Optional[Dict[str, Any]]:
        """解析消息"""
        try:
            message_str = data.decode('utf-8')
            return json.loads(message_str)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            print(f"[错误] 消息解析失败: {e}")
            return None

    @staticmethod
    def calculate_file_md5(file_path: str) -> str:
        """计算文件MD5值"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            print(f"[错误] 计算文件MD5失败: {e}")
            return ""

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小显示"""
        if size_bytes == 0:
            return "0B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f}{size_names[i]}"

    @staticmethod
    def validate_message(message: Dict[str, Any], expected_type: str) -> bool:
        """验证消息格式"""
        return (isinstance(message, dict) and
                message.get("type") == expected_type)
