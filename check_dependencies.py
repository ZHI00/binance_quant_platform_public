#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端依赖检查脚本
检查 backend/requirements.txt 中的所有依赖是否已正确安装
"""

import sys
import subprocess
import re
from pathlib import Path


def parse_requirements(requirements_file):
    """解析 requirements.txt 文件"""
    packages = []
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue
                
                # 解析包名和版本
                # 支持格式: package==version, package>=version, package
                match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                if match:
                    package_name = match.group(1)
                    packages.append((package_name, line))
    except FileNotFoundError:
        print(f"❌ 错误: 找不到文件 {requirements_file}")
        return None
    
    return packages


def check_package_installed(package_name):
    """检查单个包是否已安装"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', package_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️  检查 {package_name} 时出错: {e}")
        return False


def get_installed_version(package_name):
    """获取已安装包的版本"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', package_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':', 1)[1].strip()
    except Exception:
        pass
    return None


def main():
    print("=" * 60)
    print("后端依赖检查工具")
    print("=" * 60)
    print()
    
    # 检查 requirements.txt 文件
    requirements_file = Path('backend/requirements.txt')
    if not requirements_file.exists():
        print(f"❌ 错误: 找不到 {requirements_file}")
        return 1
    
    print(f"📋 读取依赖文件: {requirements_file}")
    packages = parse_requirements(requirements_file)
    
    if packages is None:
        return 1
    
    print(f"📦 需要检查 {len(packages)} 个依赖包")
    print()
    
    # 检查每个包
    missing_packages = []
    installed_packages = []
    
    for package_name, requirement_line in packages:
        print(f"检查 {package_name}...", end=' ')
        
        if check_package_installed(package_name):
            version = get_installed_version(package_name)
            print(f"✅ 已安装 (版本: {version})")
            installed_packages.append((package_name, version))
        else:
            print(f"❌ 未安装")
            missing_packages.append((package_name, requirement_line))
    
    # 输出结果
    print()
    print("=" * 60)
    print("检查结果")
    print("=" * 60)
    print(f"✅ 已安装: {len(installed_packages)} 个")
    print(f"❌ 未安装: {len(missing_packages)} 个")
    print()
    
    if missing_packages:
        print("⚠️  以下依赖包未安装:")
        for package_name, requirement_line in missing_packages:
            print(f"   - {requirement_line}")
        print()
        print("💡 请运行以下命令安装缺失的依赖:")
        print(f"   pip install -r {requirements_file}")
        return 1
    else:
        print("🎉 所有依赖包都已正确安装!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
