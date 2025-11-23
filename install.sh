#!/bin/bash
echo "安装币安量化交易平台..."
echo ""

echo "[1/1] 安装Python依赖..."
cd backend

echo "逐个安装依赖包..."
while IFS= read -r package; do
    # 跳过空行和注释
    [[ -z "$package" || "$package" =~ ^# ]] && continue
    
    echo ""
    echo "正在安装: $package"
    
    # 检查是否是 TA-Lib
    if [[ "$package" =~ TA-Lib ]]; then
        echo ""
        echo "========================================"
        echo "检测到 TA-Lib，需要特殊安装流程"
        echo "========================================"
        echo ""
        echo "正在尝试自动安装 TA-Lib C 库..."
        
        # 检测操作系统
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "检测到 Linux 系统，开始安装依赖..."
            sudo apt update
            sudo apt install -y build-essential wget unzip python3-dev python3-pip
            
            echo "下载并编译 TA-Lib C 库..."
            cd /tmp
            wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
            tar -xvzf ta-lib-0.4.0-src.tar.gz
            cd ta-lib/
            ./configure --prefix=/usr
            make
            sudo make install
            cd -
            
            echo "安装 Python TA-Lib 包..."
            pip3 install --upgrade pip
            pip3 install TA-Lib
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            echo "检测到 macOS 系统..."
            if command -v brew &> /dev/null; then
                echo "使用 Homebrew 安装 TA-Lib..."
                brew install ta-lib
                pip3 install TA-Lib
            else
                echo "未检测到 Homebrew，请先安装 Homebrew:"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo "然后运行: brew install ta-lib && pip3 install TA-Lib"
            fi
        else
            echo "未识别的操作系统，请手动安装 TA-Lib"
            echo "参考: https://github.com/mrjbq7/ta-lib#dependencies"
        fi
    else
        pip3 install "$package"
        if [ $? -ne 0 ]; then
            echo "警告: $package 安装失败，继续安装其他依赖..."
        fi
    fi
done < requirements.txt

cd ..

echo ""
echo "安装完成！"
echo "运行 ./start.sh 或 bash start.sh 启动平台"
echo ""
