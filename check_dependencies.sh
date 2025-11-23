#!/bin/bash

echo "========================================"
echo "后端依赖检查工具"
echo "========================================"
echo ""

python3 check_dependencies.py

if [ $? -ne 0 ]; then
    echo ""
    echo "按回车键退出..."
    read
    exit 1
fi

echo ""
echo "按回车键退出..."
read
