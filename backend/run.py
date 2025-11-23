#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
启动脚本
"""
import os
import sys
import webbrowser
import time
import signal
import psutil
from threading import Timer

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 保存进程ID到文件
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'server.pid')

def save_pid():
    """保存当前进程ID"""
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def remove_pid():
    """删除进程ID文件"""
    if os.path.exists(PID_FILE):
        try:
            os.remove(PID_FILE)
        except:
            pass

def open_browser():
    """延迟打开浏览器"""
    time.sleep(2)
    try:
        webbrowser.open('http://localhost:5000')
    except Exception as e:
        # 在服务器环境中可能无法打开浏览器，忽略错误
        print(f"无法打开浏览器: {e}")

def signal_handler(sig, frame):
    """处理关闭信号"""
    print("\n正在关闭服务器...")
    remove_pid()
    sys.exit(0)

if __name__ == '__main__':
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 保存进程ID
    save_pid()
    
    print("=" * 50)
    print("币安量化交易平台")
    print("=" * 50)
    print()
    print("正在启动服务器...")
    print("访问地址: http://localhost:5000")
    print()
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    print()
    
    # 延迟打开浏览器（仅在本地环境）
    # 在服务器环境中不打开浏览器
    if os.environ.get('DISPLAY') or sys.platform == 'win32':
        Timer(2, open_browser).start()
    
    # 启动Flask应用
    try:
        from app import app, socketio
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"\n服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        remove_pid()
        sys.exit(0)
