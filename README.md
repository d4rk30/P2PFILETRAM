# P2P 文件传输系统

## 项目简介

这是一个基于局域网的P2P文件传输系统，采用现代化架构设计，支持多节点发现和高效文件传输。系统使用UDP广播进行节点发现，TCP连接进行文件传输，提供完善的CLI交互界面和实时状态反馈。

## 功能特性

### ✅ 节点发现
- **UDP广播发现**: 每3秒自动发送心跳广播，维护节点在线状态
- **智能节点命名**: 自动生成唯一节点名称，支持自定义名称，避免命名冲突
- **实时邻居管理**: 自动维护在线节点列表，60秒超时自动清理离线节点
- **多节点支持**: 支持同机不同端口多节点运行，正确识别和管理
- **平台信息**: 自动检测并显示各节点的操作系统信息

### ✅ 文件传输
- **主动文件推送**: 通过CLI命令向指定节点发送文件
- **用户确认机制**: 接收方可选择接受或拒绝文件传输
- **实时进度显示**: 发送和接收过程中显示传输进度和速度
- **文件完整性校验**: 使用MD5校验确保文件传输完整
- **多并发支持**: 支持多个节点同时进行文件传输
- **自动文件管理**: 自动创建下载目录，处理重名文件
- **分块传输**: 64KB块大小，支持大文件传输

### ✅ 用户界面
- **清晰的启动信息**: 显示节点基本信息（名称、IP、端口、OS等）
- **丰富的CLI命令**: 支持节点管理和文件传输的完整命令集
- **美观的状态显示**: 使用表格和边框展示节点信息和传输状态
- **智能命令解析**: 支持节点名称和IP:端口两种寻址方式

### ✅ 技术特性
- **线程安全**: 使用锁机制和队列保护共享数据结构，确保并发安全
- **防自发现机制**: 正确过滤自身广播，避免将自己加入邻居列表
- **异常处理**: 完善的错误处理和优雅退出机制
- **跨平台支持**: 支持Windows、macOS、Linux等操作系统

## 文件结构

```
p2p/
├── main.py           # 程序入口，CLI循环和节点管理
├── protocol.py       # 协议定义和消息处理
├── listener.py       # 统一监听器（广播+业务）
├── broadcaster.py    # UDP广播发送器
├── neighbors.py      # 线程安全的邻居表管理
├── send_file.py      # 文件发送功能
├── recv_file.py      # 文件接收功能
├── utils.py          # 工具函数（IP获取、命名等）
├── test_p2p.py       # 单元测试套件
├── downloads/        # 接收文件的默认目录
└── README.md         # 项目说明文档
```

## 安装和运行

### 环境要求
- Python 3.6+
- 支持UDP广播的局域网环境
- 足够的磁盘空间用于文件传输

### 运行方式

1. **基本启动**
```bash
python main.py
```

2. **指定参数启动**
```bash
# 指定端口
python main.py -p 12001

# 指定节点名称
python main.py -n "我的节点"

# 指定广播端口
python main.py -b 23334

# 组合参数
python main.py -p 12001 -n "节点A" -b 23334
```

3. **查看帮助**
```bash
python main.py --help
```

## CLI命令

启动后可在节点提示符下输入以下命令：

| 命令    | 简写 | 功能               | 用法                                  |
| ------- | ---- | ------------------ | ------------------------------------- |
| `help`  | `h`  | 显示帮助信息       | `help`                                |
| `info`  | `i`  | 显示本节点详细信息 | `info`                                |
| `peers` | `p`  | 显示在线节点列表   | `peers`                               |
| `send`  | `s`  | 发送文件到指定节点 | `send <IP:端口\|节点名称> <文件路径>` |
| `clear` | `c`  | 清屏               | `clear`                               |
| `quit`  | `q`  | 退出程序           | `quit`                                |

### send命令详细说明

支持两种目标指定方式：

1. **使用节点名称**（推荐）
```bash
send node_2 ./test.txt
send "我的节点" ./文档/重要文件.pdf
```

2. **使用IP:端口**
```bash
send 192.168.1.100:12001 ./test.txt
send 192.168.1.100:12001 ./我的文档/重要文件.pdf
```

## 使用示例

### 1. 启动多个节点

**终端1 - 节点A**：
```bash
python main.py -p 12000 -n "发送节点"
```

**终端2 - 节点B**：
```bash
python main.py -p 12001 -n "接收节点"
```

### 2. 查看在线节点

在任意节点执行：
```
P2P> peers
```

输出示例：
```
在线节点列表:
节点名称            IP地址            端口       最后心跳         平台        
--------------------------------------------------------------
发送节点            192.168.1.100     12000      刚刚            macOS      
接收节点            192.168.1.100     12001      刚刚            macOS      
--------------------------------------------------------------
总计: 2 个节点在线
```

### 3. 发送文件

在发送节点执行：
```
P2P> send 接收节点 ./test.txt
```

或使用IP:端口方式：
```
P2P> send 192.168.1.100:12001 ./test.txt
```

### 4. 接收文件

接收节点会自动收到请求提示：
```
==================================================
[收到文件推送请求]
来自: 192.168.1.100:12000
文件: test.txt (1.2KB)
==================================================
是否接受？(y/n): y
```

### 5. 传输过程

**发送方显示**：
```
[信息] 正在向 192.168.1.100:12001 推送文件 test.txt (1.2KB)
[等待] 等待对方确认...
[成功] 对方已接受，开始传输...
[传输] 进度: 100.0% (1.2KB/1.2KB)
[完成] 文件已发送，等待校验...
[完成] 文件传输成功，MD5校验一致
```

**接收方显示**：
```
[信息] 已接受，开始接收...
[信息] 开始接收来自 192.168.1.100 的文件...
[信息] 文件将分为 1 块接收
[接收] 进度: 100.0% (1.2KB/1.2KB)
[信息] 正在校验文件完整性...
[完成] 文件接收成功，MD5校验一致
[信息] 文件已保存到: ./downloads/test.txt
```

## 测试

### 运行单元测试

执行完整的单元测试套件：

```bash
python test_p2p.py
```

测试套件包含以下模块：

- **协议测试**: 消息类型定义、文件大小格式化、消息解析
- **邻居管理测试**: 初始化、添加/更新邻居、邻居生命周期
- **监听器测试**: 广播监听器和业务监听器初始化
- **文件传输测试**: 发送器和接收器基本功能
- **文件操作测试**: 基本文件操作和下载目录管理
- **集成测试**: 邻居生命周期和系统组件集成

## 故障排除

### 常见问题

**Q: 发现不了其他节点？**
A: 
- 检查防火墙设置，确保UDP端口23333未被阻塞
- 确认各节点在同一局域网内
- 检查网络是否支持UDP广播

**Q: 文件传输失败？**
A:
- 检查文件是否存在且有读取权限
- 确认目标节点在线且响应正常
- 检查网络连接稳定性
- 确认磁盘空间充足

**Q: 程序启动失败？**  
A:
- 检查端口是否被占用，尝试使用 `-p` 参数指定不同端口
- 确认Python版本满足要求（3.6+）
- 检查是否有必要的网络权限

**Q: MD5校验失败？**
A:
- 重新传输文件
- 检查网络稳定性
- 确认文件在传输过程中未被修改

**Q: 同机多节点无法互相发现？**
A:
- 确保使用不同的端口号启动各节点
- 检查是否正确配置了SO_REUSEPORT选项
- 确认防自发现机制工作正常

## 开发说明

### 已解决的关键问题
1. **端口冲突**: 通过SO_REUSEPORT选项解决同机多节点监听冲突
2. **文件传输路由**: 修复文件请求路由到正确目标节点
3. **多线程输入冲突**: 使用队列机制解决并发输入问题
4. **Shell提示符恢复**: 确保所有操作后提示符正确显示
5. **节点名称支持**: 增强send命令支持节点名称寻址
6. **平台信息回归**: 修复平台信息显示问题

### 架构优化
- 合并listener文件，统一处理广播和业务通信
- 完善单元测试覆盖，提高代码质量
- 优化用户交互流程，提升使用体验

## 注意事项

1. 建议在局域网环境中使用，广域网需要额外配置
2. 确保网络环境支持UDP广播通信
3. 大规模部署时注意广播风暴问题
4. 生产环境使用时建议添加认证和加密机制
5. 文件传输完成后会自动清理TCP连接和临时资源
