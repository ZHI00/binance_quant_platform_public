# 币安量化交易平台

## 版本信息
- 打包时间: 2025-11-23 15:37:14

## 环境
推荐 Ubuntu 22

1. sudo apt update      更新一下
2. python3 --version    若无运行 sudo apt install python3
3. pip3 --version       若无运行 sudo apt install python3-pip
4. sudo apt install tmux -y
5. cd /var
6. 拉取代码 git clone https://github.com/ZHI00/binance_quant_platform_public.git
7. cd ./binance_quant_platform_public
8. 新建会话 tmux new -s trade （重新进入会话：tmux attach -t trade  退出后台运行：Ctrl+B D ）
9. 接着快速开始安装即可

## 快速开始
### Windows
1. 安装依赖: install.bat
2. 检查依赖：check_dependencies.bat
3. 启动平台: start.bat

### Linux/Mac
1. 权限 chmod +x ./*.sh
2. pip3 install --ignore-installed blinker==1.9.0
3. 安装依赖:  ./install.sh
4. 检查依赖:  ./check_dependencies.sh
5. 启动平台:  ./start.sh


访问: http://你的ip:5000

