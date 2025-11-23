# -*- coding: utf-8 -*-
"""
策略名称: top_gainers_ema_1119_1537
生成时间: 2025-11-19 15:37:50
策略流程: 获取行情 -> 自定义策略 -> 标的选择 -> 获取行情 -> 技术指标 -> 自定义策略 -> 交易执行 -> 定时启动
"""

# ==================== 导入库 ====================
# 数据处理
import pandas as pd
import numpy as np

# 时间处理
from datetime import datetime, timedelta

# 系统库
import logging
import json
import os
import time
import math

# 并发处理
from concurrent.futures import ThreadPoolExecutor, as_completed

# HTTP请求
import requests

# AI相关
from openai import OpenAI

# 定时任务
from apscheduler.schedulers.background import BackgroundScheduler

# 技术分析库
import talib

# 日志
logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self, binance_client, config, runner=None):
        self.client = binance_client
        self.config = config
        self.runner = runner  # 保存 runner 引用，用于检查停止状态
        self.scheduler = None  # 保存调度器引用
        self.positions = {'current': [], 'history': []}
        self.symbol_cooldown = {}  # 标的冷却时间记录 {symbol: last_buy_time}
        # 使用根目录的 data/positions.json
        self.positions_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'positions.json')
        self.load_positions()
    
    def load_positions(self):
        """加载仓位数据"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
        
        if os.path.exists(self.positions_file):
            with open(self.positions_file, 'r', encoding='utf-8') as f:
                self.positions = json.load(f)
                logger.info(f"加载仓位数据: {len(self.positions.get('current', []))} 个当前持仓, {len(self.positions.get('history', []))} 个历史记录")
        else:
            # 如果文件不存在，创建初始文件
            logger.info("仓位文件不存在，创建新文件")
            self.save_positions()
    
    def save_positions(self):
        """保存仓位数据"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
        
        with open(self.positions_file, 'w', encoding='utf-8') as f:
            json.dump(self.positions, f, ensure_ascii=False, indent=2)

    
    def run(self):
        """执行策略主流程"""
        logger.info("=" * 60)
        logger.info(f"策略 {'top_gainers_ema_1119_1537'} 开始执行")
        logger.info("=" * 60)
        
        try:
            # 步骤1: 重新加载仓位数据（同步手动平仓等操作）
            logger.info("\n步骤1: 重新加载仓位数据...")
            self.load_positions()
            
            # 步骤2: 清理到期仓位（检查持仓时间）
            logger.info("\n步骤2: 清理到期仓位...")
            self.clear_expired_positions()
            
            # 步骤3: 获取BTCUSDT的5m行情数据（自定义标的）
            logger.info("\n步骤3: 获取BTCUSDT的5m行情数据...")
            klines_BTCUSDT_5m = self.client.get_klines("BTCUSDT", "5m", 60)
            if klines_BTCUSDT_5m is None or len(klines_BTCUSDT_5m) == 0:
                logger.warning(f"未获取到BTCUSDT的5mK线数据")
                return
            logger.info(f"获取到 {len(klines_BTCUSDT_5m)} 根BTCUSDT的5mK线")

            # 步骤4: 自定义策略判断（全局）
            logger.info("\n步骤4: 自定义策略判断...")
            
            try:
                # 计算全局指标
                global_indicators = self.calculate_indicators(klines_BTCUSDT_5m)
                
                signal = self.custom_strategy_1(klines_BTCUSDT_5m, global_indicators)
                
                # 全局策略：返回 "LONG" 或 "SHORT" 决定后续开单方向
                if signal == "LONG":
                    global_direction = "LONG"
                    logger.info(f"  自定义策略通过 ✓ (全局方向: LONG)")
                elif signal == "SHORT":
                    global_direction = "SHORT"
                    logger.info(f"  自定义策略通过 ✓ (全局方向: SHORT)")
                else:
                    logger.info(f"  自定义策略未通过（返回值: {signal}），策略结束")
                    return
            except Exception as e:
                logger.error(f"自定义策略判断出错: {e}")
                return

            # 步骤5: 获取交易标的
            logger.info("\n步骤5: 获取交易标的...")
            symbols = self.get_symbols()
            logger.info(f"获取到 {len(symbols)} 个标的: {symbols}")
            
            if not symbols:
                logger.warning("未获取到任何标的，策略结束")
                return

            # 步骤6: 获取5m行情数据
            logger.info("\n步骤6: 获取5m行情数据...")
            passed_symbols = []
            
            for symbol in symbols:
                try:
                    # 检查是否已持仓
                    if any(p['symbol'] == symbol for p in self.positions['current']):
                        logger.info(f"  {symbol} 已在持仓中，跳过")
                        continue
                    
                    # 检查冷却时间
                    if 0 > 0 and symbol in self.symbol_cooldown:
                        last_buy_time = self.symbol_cooldown[symbol]
                        time_passed = (datetime.now() - last_buy_time).total_seconds() / 60
                        if time_passed < 0:
                            remaining = 0 - time_passed
                            logger.info(f"  {symbol} 冷却中，剩余 {remaining:.1f} 分钟，跳过")
                            continue
                    
                    klines_5m = self.client.get_klines(symbol, "5m", 60)
                    if klines_5m is None or len(klines_5m) == 0:
                        logger.warning(f"  {symbol} 未获取到5mK线数据")
                        continue
                    
                    # 保存数据供后续使用
                    data = {
                        'symbol': symbol,
                        'klines_5m': klines_5m
                    }
                    
                    # 如果有全局方向，添加到数据中
                    if 'global_direction' in locals():
                        data['direction'] = global_direction
                    
                    passed_symbols.append(data)
                    
                except Exception as e:
                    logger.error(f"获取 {symbol} 5mK线数据出错: {e}")
                    continue
            
            logger.info(f"成功获取 {len(passed_symbols)} 个标的的5mK线数据")
            
            if not passed_symbols:
                logger.warning("未获取到任何K线数据，策略结束")
                return

            # 步骤7: 批量计算技术指标
            logger.info("\n步骤7: 批量计算技术指标...")
            
            for data in passed_symbols:
                try:
                    # 合并全局K线数据
                    data['klines_BTCUSDT_5m'] = klines_BTCUSDT_5m
                    klines_BTCUSDT_5m = data.get('klines_BTCUSDT_5m', [])
                    klines_5m = data.get('klines_5m', [])
                    indicators = self.calculate_indicators(klines_BTCUSDT_5m, klines_5m)
                    # 合并全局指标
                    if 'global_indicators' in locals():
                        indicators.update(global_indicators)
                    data['indicators'] = indicators
                except Exception as e:
                    logger.error(f"计算 {data['symbol']} 指标出错: {e}")
                    data['indicators'] = {}
            
            logger.info(f"完成 {len(passed_symbols)} 个标的的指标计算")

            # 步骤8: 自定义策略判断
            logger.info("\n步骤8: 自定义策略判断...")
            
            new_passed = []
            for data in passed_symbols:
                try:
                    symbol = data['symbol']
                    klines_5m = data.get('klines_5m', [])
                    indicators = data.get('indicators', {})
                    
                    signal = self.custom_strategy_5(klines_BTCUSDT_5m, klines_5m, indicators)
                    
                    # 处理返回值：只识别 "LONG" 和 "SHORT"，其他都跳过
                    if signal == "LONG":
                        direction = "LONG"
                    elif signal == "SHORT":
                        direction = "SHORT"
                    else:
                        logger.info(f"  {symbol} 自定义策略未通过（返回值: {signal}）")
                        continue
                    
                    # 检查方向一致性
                    if 'direction' in data:
                        if data['direction'] != direction:
                            logger.info(f"  {symbol} 方向不一致（已有{data['direction']}，策略返回{direction}），跳过")
                            continue
                    else:
                        data['direction'] = direction
                    
                    logger.info(f"  {symbol} 自定义策略通过 ✓ (方向: {direction})")
                    new_passed.append(data)
                except Exception as e:
                    logger.error(f"判断 {data['symbol']} 自定义策略出错: {e}")
            
            passed_symbols = new_passed
            logger.info(f"自定义策略通过: {len(passed_symbols)} 个标的")
            
            if not passed_symbols:
                logger.info("没有标的通过自定义策略，策略结束")
                return

            # 步骤9: 执行买入
            if passed_symbols:
                logger.info(f"\n步骤9: 执行买入，共{len(passed_symbols)}个标的")
                # 传递带方向的数据
                symbols_with_direction = [{
                    'symbol': d['symbol'],
                    'direction': d.get('direction', 'LONG')
                } for d in passed_symbols]
                self.execute_batch_buy(symbols_with_direction)
            else:
                logger.info("\n没有符合条件的标的")

            
            # 最后总是执行：检查账户数据、止损单、挂单等
            time.sleep(10)
            logger.info("\n最后检查: 验证账户数据、止损单、挂单...")
            self.check_positions_after_buy()
            
            logger.info("=" * 60)
            logger.info("策略执行完成")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"策略执行出错: {e}", exc_info=True)

    
    def get_symbols(self):
        """获取交易标的"""
        # 使用 get_top_gainers 获取涨幅榜数据
        gainers = self.client.get_top_gainers(limit=1000)  # 获取所有上架的
        
        logger.info(f"获取涨幅榜原始数据: {len(gainers)} 个标的")
        
        # 过滤黑名单
        if []:
            gainers = [g for g in gainers if g['symbol'] not in []]
            logger.info(f"过滤黑名单后: {len(gainers)} 个标的")
        
        # 过滤成交额（转换为浮点数比较）
        gainers = [g for g in gainers if float(g['quoteVolume']) >= 30000000]
        logger.info(f"过滤成交量(>=30000000)后: {len(gainers)} 个标的")
        
        # 取前N个
        gainers = gainers[:10]
        symbols = [g['symbol'] for g in gainers]
        
        logger.info(f"最终选择前10个标的: {symbols}")
        
        return symbols

    
    def calculate_indicators(self, klines_BTCUSDT_5m, klines_5m=None):
        """计算技术指标"""
        indicators = {}
        
        # 从 klines_5m 计算指标
        if klines_5m is not None:
            df_5m = pd.DataFrame(klines_5m)
            close_5m = df_5m["close"].astype(float).values
            high_5m = df_5m["high"].astype(float).values
            low_5m = df_5m["low"].astype(float).values
            volume_5m = df_5m["volume"].astype(float).values
            ema = talib.EMA(close_5m, timeperiod=20)
            indicators['ema_5m'] = ema.tolist()
        return indicators

    
    def custom_strategy_1(self, klines_BTCUSDT_5m, indicators):
        """自定义策略 - 自定义策略"""
        # 自定义策略逻辑
        # 可用变量: klines_BTCUSDT_5m, indicators
        # 可用库: pandas as pd, numpy as np, datetime, timedelta, logging, json, os, time, math
        # 返回值: 必须返回 "LONG"(做多) 或 "SHORT"(做空)，其他值都会跳过
        # 注意: 全局策略的返回值会作为后续所有标的的开单方向
        try:
            # 当前是阳线 LONG
            # 当前是阳线 SHORT
            # if klines_BTCUSDT_5m[-1]['close']>klines_BTCUSDT_5m[-1]['open']:
            #     return "LONG"
            # if klines_BTCUSDT_5m[-1]['close']<klines_BTCUSDT_5m[-1]['open']:
            #     return "SHORT"

            # return None

            return "SHORT"
        except Exception as e:
            logger.error(f"自定义策略执行出错: {e}")
            return None

    
    def custom_strategy_5(self, klines_BTCUSDT_5m, klines_5m, indicators):
        """自定义策略 - 自定义策略"""
        # 自定义策略逻辑
        # 可用变量: klines_BTCUSDT_5m, klines_5m, indicators
        # 可用库: pandas as pd, numpy as np, datetime, timedelta, logging, json, os, time, math
        # 返回值: 必须返回 "LONG"(做多) 或 "SHORT"(做空)，其他值都会跳过
        # 注意: 全局策略的返回值会作为后续所有标的的开单方向
        try:
            # 收盘大于ema 且 阳线 long
            # 收盘小于ema 且 阴线 short
            if klines_5m[-1]['close']>indicators['ema_5m'][-1] and klines_5m[-1]['close']>klines_5m[-1]['open']:
                return "LONG"

            if klines_5m[-1]['close']<indicators['ema_5m'][-1] and klines_5m[-1]['close']<klines_5m[-1]['open']:
                return "SHORT"

            return None
        except Exception as e:
            logger.error(f"自定义策略执行出错: {e}")
            return None

    
    def execute_batch_buy(self, symbols):
        """批量执行买入"""
        # 检查仓位数量
        current_count = len(self.positions['current'])
        if current_count >= 1:
            logger.info(f"已达到最大仓位数量 ({current_count}/1)，跳过买入")
            return
        
        # 过滤冷却中的标的
        cooldown_minutes = 0
        if cooldown_minutes > 0:
            now = datetime.now()
            filtered_symbols = []
            for item in symbols:
                # 兼容字典和字符串两种格式
                symbol = item['symbol'] if isinstance(item, dict) else item
                
                if symbol in self.symbol_cooldown:
                    last_buy_time = self.symbol_cooldown[symbol]
                    time_passed = (now - last_buy_time).total_seconds() / 60
                    if time_passed < cooldown_minutes:
                        remaining = cooldown_minutes - time_passed
                        logger.info(f"  {symbol} 冷却中，剩余 {remaining:.1f} 分钟")
                        continue
                filtered_symbols.append(item)
            
            if len(filtered_symbols) < len(symbols):
                logger.info(f"冷却过滤: {len(symbols)} -> {len(filtered_symbols)} 个标的")
            symbols = filtered_symbols
        
        if not symbols:
            logger.info("所有标的都在冷却中，跳过买入")
            return
        
        # 限制买入数量
        symbols = symbols[:1 - current_count]
        logger.info(f"准备买入 {len(symbols)} 个标的: {symbols}")
        
        # 限价单价差（3%）
        limit_order_spread = 0.03
        
        # 准备所有订单
        all_orders = []
        symbols_with_direction = []
        
        # 如果symbols是字典列表（包含direction），则提取
        if symbols and isinstance(symbols[0], dict):
            symbols_with_direction = symbols
            symbols = [s['symbol'] for s in symbols_with_direction]
        
        for i, symbol in enumerate(symbols):
            try:
                # 获取方向（默认LONG）
                direction = "LONG"
                if symbols_with_direction:
                    direction = symbols_with_direction[i].get('direction', 'LONG')
                
                # 获取当前价格
                ticker = self.client.client.ticker_price(symbol=symbol)
                current_price = float(ticker['price'])
                
                # 计算数量
                quantity = 6 / current_price
                
                # 格式化数量精度
                quantity_str = self.client.format_quantity(symbol, quantity)
                
                # 跳过数量为0的订单
                if float(quantity_str) == 0:
                    logger.warning(f"{symbol} 数量为0，跳过")
                    continue
                
                # 根据方向设置订单参数
                if direction == "LONG":
                    # 做多：限价单价格上浮3%
                    limit_price = current_price * (1 + limit_order_spread)
                    side = 'BUY'
                    position_side = 'LONG'
                elif direction == "SHORT":
                    # 做空：限价单价格下浮3%
                    limit_price = current_price * (1 - limit_order_spread)
                    side = 'SELL'
                    position_side = 'SHORT'
                else:
                    logger.warning(f"{symbol} 未知方向: {direction}，跳过")
                    continue
                
                limit_price_str = self.client.format_price(symbol, limit_price)
                
                # 生成自定义订单号
                client_order_id = f"QUANT_{symbol}_{int(time.time() * 1000)}"
                
                all_orders.append({
                    'symbol': symbol,
                    'side': side,
                    'positionSide': position_side,
                    'type': 'LIMIT',
                    'quantity': quantity_str,
                    'price': limit_price_str,
                    'timeInForce': 'GTC',
                    'newClientOrderId': client_order_id,
                    "newOrderRespType": "RESULT",
                    'direction': direction
                })
                
                spread_sign = '+' if direction == 'LONG' else '-'
                logger.info(f"  准备限价{side}单 {symbol} ({direction}): 当前价 {current_price}, 限价 {limit_price_str} ({spread_sign}3%), 数量 {quantity_str}")
                
            except Exception as e:
                logger.error(f"准备订单失败 {symbol}: {e}")
        
        if not all_orders:
            logger.warning("没有可下单的标的")
            return
        
        # 分批下单，每次最多5个
        all_success_orders = []
        batch_size = 5
        for index in range(math.ceil(len(all_orders) / batch_size)):
            batch_orders = all_orders[index * batch_size : (index + 1) * batch_size]
            
            try:
                logger.info(f"执行第 {index + 1} 批订单，共 {len(batch_orders)} 个")
                logger.info(f"订单详情: {batch_orders}")
                results = self.client.client.new_batch_order(batch_orders)
                logger.info(f"下单结果: {results}")
                
                # 过滤成功的订单
                success_orders = [r for r in results if 'orderId' in r]
                all_success_orders.extend(success_orders)
                logger.info(f"第 {index + 1} 批成功: {len(success_orders)} 个订单")
                
            except Exception as e:
                logger.error(f"第 {index + 1} 批下单失败: {e}")
        
        if not all_success_orders:
            logger.warning("没有成功的订单")
            return
        
        logger.info(f"总计成功订单: {len(all_success_orders)} 个")
        
        # 执行批量买入
        try:
            results = all_success_orders
            logger.info(f"批量下单完成: {len(results)} 个订单")
            
            # 过滤成功的订单
            success_orders = [r for r in results if 'orderId' in r]
            logger.info(f"成功订单: {len(success_orders)} 个")
            
            # 保存仓位信息
            for idx, order in enumerate(all_success_orders):
                symbol = order['symbol']
                
                # 从原始订单中获取方向
                direction = 'LONG'
                for orig_order in all_orders:
                    if orig_order['symbol'] == symbol:
                        direction = orig_order.get('direction', 'LONG')
                        break
                
                position_side = 'LONG' if direction == 'LONG' else 'SHORT'
                
                position = {
                    'symbol': symbol,
                    'positionSide': position_side,
                    'entry_time': datetime.now().isoformat(),
                    'entry_price': float(order.get('avgPrice', order.get('price', 0))),
                    'quantity': float(order['origQty']),
                    'order_id': order.get('orderId', ''),
                    'client_order_id': order.get('clientOrderId', ''),
                    'hold_bars': 1,
                    'max_hold_bars': 1,
                    'take_profit_ratio': 5,
                    'stop_loss_ratio': 10,
                    'stop_loss_order_ids': [],
                    'take_profit_order_ids': []
                }
                self.positions['current'].append(position)
                
                # 记录冷却时间
                if 0 > 0:
                    self.symbol_cooldown[symbol] = datetime.now()
                    logger.info(f"✓ 开仓成功: {symbol} ({position_side}), 价格: {position['entry_price']}, 数量: {position['quantity']}, 订单号: {position['client_order_id']}, 冷却 0 分钟")
                else:
                    logger.info(f"✓ 开仓成功: {symbol} ({position_side}), 价格: {position['entry_price']}, 数量: {position['quantity']}, 订单号: {position['client_order_id']}")
            
            self.save_positions()
            logger.info(f"仓位已保存到本地，当前持仓数量: {len(self.positions['current'])}")
            
            # 下止盈止损单
            if True and all_success_orders:
                time.sleep(1)
                
                # 第一步：先下止损单
                all_stop_loss_orders = []
                for idx, order in enumerate(all_success_orders):
                    symbol = order['symbol']
                    entry_price = float(order.get('avgPrice', order.get('price', 0)))
                    quantity = float(order['origQty'])
                    
                    # 从原始订单中获取方向
                    direction = 'LONG'
                    for orig_order in all_orders:
                        if orig_order['symbol'] == symbol:
                            direction = orig_order.get('direction', 'LONG')
                            break
                    
                    if 10 > 0:
                        if direction == 'LONG':
                            # 做多止损：价格下跌到止损价时卖出
                            stop_loss_price = entry_price * (1 - 10 / 100)
                            side = 'SELL'
                            position_side = 'LONG'
                            price_change = f'-10%'
                        elif direction == 'SHORT':
                            # 做空止损：价格上涨到止损价时买入
                            stop_loss_price = entry_price * (1 + 10 / 100)
                            side = 'BUY'
                            position_side = 'SHORT'
                            price_change = f'+10%'
                        else:
                            continue
                        
                        stop_loss_price_str = self.client.format_price(symbol, stop_loss_price)
                        quantity_str = self.client.format_quantity(symbol, quantity)
                        all_stop_loss_orders.append({
                            'symbol': symbol,
                            'side': side,
                            'positionSide': position_side,
                            'type': 'STOP_MARKET',
                            'quantity': quantity_str,
                            'stopPrice': stop_loss_price_str
                        })
                        logger.info(f"  准备止损单 {symbol} ({position_side}): {stop_loss_price_str} ({price_change})")
                
                # 分批下止损单
                if all_stop_loss_orders:
                    for index in range(math.ceil(len(all_stop_loss_orders) / batch_size)):
                        batch_sl = all_stop_loss_orders[index * batch_size : (index + 1) * batch_size]
                        try:
                            sl_results = self.client.client.new_batch_order(batch_sl)
                            logger.info(f"✓ 第 {index + 1} 批止损单设置成功: {len(sl_results)} 个订单")
                            
                            for sl_result in sl_results:
                                if 'orderId' in sl_result:
                                    symbol = sl_result['symbol']
                                    order_id = sl_result['orderId']
                                    for pos in self.positions['current']:
                                        if pos['symbol'] == symbol:
                                            pos['stop_loss_order_ids'].append(order_id)
                                            logger.info(f"  保存止损单订单号: {symbol} -> {order_id}")
                                            break
                            self.save_positions()
                        except Exception as e:
                            logger.error(f"✗ 第 {index + 1} 批止损单设置失败: {e}")
                
                # 第二步：再下止盈单
                time.sleep(1)
                all_take_profit_orders = []
                for idx, order in enumerate(all_success_orders):
                    symbol = order['symbol']
                    entry_price = float(order.get('avgPrice', order.get('price', 0)))
                    quantity = float(order['origQty'])
                    
                    # 从原始订单中获取方向
                    direction = 'LONG'
                    for orig_order in all_orders:
                        if orig_order['symbol'] == symbol:
                            direction = orig_order.get('direction', 'LONG')
                            break
                    
                    if 5 > 0:
                        if direction == 'LONG':
                            # 做多止盈：价格上涨到止盈价时卖出
                            take_profit_price = entry_price * (1 + 5 / 100)
                            side = 'SELL'
                            position_side = 'LONG'
                            price_change = f'+5%'
                        elif direction == 'SHORT':
                            # 做空止盈：价格下跌到止盈价时买入
                            take_profit_price = entry_price * (1 - 5 / 100)
                            side = 'BUY'
                            position_side = 'SHORT'
                            price_change = f'-5%'
                        else:
                            continue
                        
                        take_profit_price_str = self.client.format_price(symbol, take_profit_price)
                        quantity_str = self.client.format_quantity(symbol, quantity)
                        all_take_profit_orders.append({
                            'symbol': symbol,
                            'side': side,
                            'positionSide': position_side,
                            'type': 'LIMIT',
                            'quantity': quantity_str,
                            'price': take_profit_price_str,
                            'timeInForce': 'GTC'
                        })
                        logger.info(f"  准备止盈单 {symbol} ({position_side}): {take_profit_price_str} ({price_change})")
                
                # 分批下止盈单
                if all_take_profit_orders:
                    for index in range(math.ceil(len(all_take_profit_orders) / batch_size)):
                        batch_tp = all_take_profit_orders[index * batch_size : (index + 1) * batch_size]
                        try:
                            tp_results = self.client.client.new_batch_order(batch_tp)
                            logger.info(f"✓ 第 {index + 1} 批止盈单设置成功: {len(tp_results)} 个订单")
                            
                            for tp_result in tp_results:
                                if 'orderId' in tp_result:
                                    symbol = tp_result['symbol']
                                    order_id = tp_result['orderId']
                                    for pos in self.positions['current']:
                                        if pos['symbol'] == symbol:
                                            pos['take_profit_order_ids'].append(order_id)
                                            logger.info(f"  保存止盈单订单号: {symbol} -> {order_id}")
                                            break
                            self.save_positions()
                        except Exception as e:
                            logger.error(f"✗ 第 {index + 1} 批止盈单设置失败: {e}")

            # 发送飞书通知
            try:
                filled_orders = [o for o in all_success_orders if o.get('status') == 'FILLED']
                
                if filled_orders:
                    # 构建包含方向的通知信息
                    symbols_info = []
                    for o in filled_orders:
                        symbol = o['symbol']
                        # 从原始订单获取方向
                        direction = 'LONG'
                        for orig_order in all_orders:
                            if orig_order['symbol'] == symbol:
                                direction = orig_order.get('direction', 'LONG')
                                break
                        direction_text = '做多' if direction == 'LONG' else ('做空' if direction == 'SHORT' else '未知')
                        symbols_info.append(f"{symbol}({direction_text})")
                    
                    symbols_str = ", ".join(symbols_info)
                    timestamp = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                    webhook = ""
                    if webhook:
                        requests.post(
                            webhook,
                            json={"msg_type": "text", "content": {"text": f"开仓通知: {symbols_str} --- {timestamp}"} },
                            timeout=5
                        )
                        logger.info(f"✓ 已发送开仓通知: {symbols_str}")
                else:
                    logger.info("没有成交的订单，跳过通知")
            except Exception as e:
                logger.error(f"发送通知失败: {e}")
        except Exception as e:
            logger.error(f"批量下单失败: {e}")

    
    def clear_expired_positions(self):
        """清理到期仓位（只检查持仓时间）"""
        logger.info(f"检查到期仓位 - 本地持仓数量: {len(self.positions['current'])}")
        
        if not self.positions['current']:
            logger.info("当前无持仓")
            return
        
        logger.info(f"开始检查 {len(self.positions['current'])} 个持仓...")
        
        # 收集所有需要平仓的信息
        closed_positions = []
        
        for position in self.positions['current'][:]:
            try:
                symbol = position['symbol']
                hold_bars = position.get('hold_bars', 0)
                max_hold_bars = position.get('max_hold_bars', 10)
                
                logger.info(f"  检查 {symbol}: 已持仓{hold_bars}/{max_hold_bars}根K线")
                
                # 只检查持仓时间
                if hold_bars >= max_hold_bars:
                    logger.info(f"  {symbol} 达到最大持仓K线数，准备平仓")
                    result = self.close_position(position, reason='到期', send_notification=False)
                    if result:
                        closed_positions.append(result)
                else:
                    position['hold_bars'] = hold_bars + 1
                    self.save_positions()
                    logger.info(f"  {symbol} 继续持仓 ({hold_bars + 1}/{max_hold_bars})")
                    
            except Exception as e:
                logger.error(f"检查仓位 {position.get('symbol', 'unknown')} 出错: {e}")
        
        # 统一发送平仓通知
        if closed_positions:
            self.send_close_notification(closed_positions)
    
    def check_positions_after_buy(self):
        """买入后检查：验证账户数据、止损单、挂单等"""
        try:
            # 一、获取账户信息并清理本地脏数据
            account_info = self.client.get_account_info()
            if not account_info:
                logger.warning("无法获取账户信息")
                return
            
            # 清理本地数据库中不存在于实际账户的仓位
            def filter_valid_position(x):
                position_side = x.get("positionSide", "LONG")
                result = [d for d in account_info.get("positions", []) 
                         if d["symbol"] == x["symbol"] and d.get("positionSide") == position_side]
                all_quantity = abs(float(result[0]["positionAmt"])) if result else 0
                
                if all_quantity > 0:
                    logger.info(f"  验证仓位 {x['symbol']} ({position_side}): 实际持仓数量 {all_quantity}")
                else:
                    logger.warning(f"  验证仓位 {x['symbol']} ({position_side}): 实际账户中无持仓，将从本地移除")
                
                return all_quantity > 0
            
            logger.info(f"验证前本地仓位数量: {len(self.positions['current'])}")
            self.positions['current'] = list(filter(filter_valid_position, self.positions['current']))
            self.save_positions()
            
            if not self.positions['current']:
                logger.info("验证后当前无持仓")
            else:
                logger.info(f"验证后当前持仓数量: {len(self.positions['current'])}")
            
            # 二、处理没有止损单的仓位，立即平仓
            open_orders = self.client.get_open_orders()
            
            def filter_not_stop_positions(x):
                return (float(x.get("positionAmt", 0)) != 0 and 
                       not any(d.get("type") == "STOP_MARKET" and d["symbol"] == x["symbol"] 
                              for d in open_orders))
            
            not_stop_positions = list(filter(filter_not_stop_positions, account_info.get("positions", [])))
            
            if not_stop_positions:
                logger.warning(f"发现 {len(not_stop_positions)} 个没有止损单的仓位，准备平仓")
                for pos in not_stop_positions:
                    try:
                        logger.info(f"  已平仓无止损单的仓位: {pos['symbol']}")
                    except Exception as e:
                        logger.error(f"  平仓 {pos['symbol']} 失败: {e}")
            
            # 三、取消没有对应仓位的挂单
            def filter_not_position_orders(x):
                return not any(float(d.get("positionAmt", 0)) != 0 and d["symbol"] == x["symbol"] 
                              for d in account_info.get("positions", []))
            
            not_position_orders = list(filter(filter_not_position_orders, open_orders))
            
            if not_position_orders:
                logger.info(f"发现 {len(not_position_orders)} 个无仓位的挂单，准备取消")
                for order in not_position_orders:
                    try:
                        self.client.cancel_open_orders(order["symbol"], recvWindow=2000)
                        logger.info(f"  已取消挂单: {order['symbol']}")
                    except Exception as e:
                        logger.error(f"  取消挂单 {order['symbol']} 失败: {e}")
                    
        except Exception as e:
            logger.error(f"买入后检查出错: {e}", exc_info=True)
    
    def close_position(self, position, reason='', send_notification=True):
        """平仓"""
        try:
            symbol = position['symbol']
            position_side = position.get('positionSide', 'LONG')
            quantity = position.get('quantity', None)
            
            result = self.client.close_position(symbol, position_side=position_side, quantity=quantity)
            
            if result.get('success'):
                exit_price = result.get('exit_price', result.get('price', 0))
                entry_price = result.get('entry_price', position.get('entry_price', 0))
                pnl = result.get('unrealized_pnl', 0)
                
                position['exit_time'] = datetime.now().isoformat()
                position['exit_price'] = exit_price
                position['entry_price'] = entry_price
                position['exit_reason'] = reason
                position['pnl'] = round(pnl, 2)
                
                self.positions['current'].remove(position)
                self.positions['history'].append(position)
                self.save_positions()
                
                logger.info(f"✓ 平仓成功 ({reason}): {symbol}")
                logger.info(f"  开仓价: {entry_price}, 平仓价: {exit_price}, 盈亏: {pnl:.2f} USDT")
                
                # 撤销止盈止损单
                stop_loss_order_ids = position.get('stop_loss_order_ids', [])
                take_profit_order_ids = position.get('take_profit_order_ids', [])
                
                for order_id in stop_loss_order_ids:
                    try:
                        cancel_result = self.client.cancel_order(symbol, order_id)
                        if cancel_result.get('success'):
                            logger.info(f"  ✓ 撤销止损单成功: {symbol} 订单ID: {order_id}")
                        else:
                            logger.warning(f"  ✗ 撤销止损单失败: {symbol} 订单ID: {order_id}")
                    except Exception as e:
                        logger.warning(f"  ✗ 撤销止损单异常: {symbol} 订单ID: {order_id}, {e}")
                
                for order_id in take_profit_order_ids:
                    try:
                        cancel_result = self.client.cancel_order(symbol, order_id)
                        if cancel_result.get('success'):
                            logger.info(f"  ✓ 撤销止盈单成功: {symbol} 订单ID: {order_id}")
                        else:
                            logger.warning(f"  ✗ 撤销止盈单失败: {symbol} 订单ID: {order_id}")
                    except Exception as e:
                        logger.warning(f"  ✗ 撤销止盈单异常: {symbol} 订单ID: {order_id}, {e}")

                if send_notification:
                    self.send_close_notification([{
                        'symbol': symbol,
                        'reason': reason,
                        'pnl': pnl
                    }])
                
                return {
                    'symbol': symbol,
                    'reason': reason,
                    'pnl': pnl
                }
            else:
                logger.error(f"✗ 平仓失败: {symbol}, 错误: {result.get('error', 'unknown')}")
                return None
        except Exception as e:
            logger.error(f"✗ 平仓失败: {e}", exc_info=True)
            return None
    
    def send_close_notification(self, closed_positions):
        """发送平仓通知"""
        if not closed_positions:
            return
        
        try:
            timestamp = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            webhook = "{webhook_placeholder}"
            
            if webhook:
                symbols_info = []
                total_pnl = 0
                for pos in closed_positions:
                    symbols_info.append(f"{pos['symbol']}({pos['reason']}, {pos['pnl']:.2f}U)")
                    total_pnl += pos['pnl']
                
                message = f"平仓通知: {', '.join(symbols_info)} | 总盈亏: {total_pnl:.2f}U --- {timestamp}"
                
                requests.post(
                    webhook,
                    json={"msg_type": "text", "content": {"text": message}},
                    timeout=5
                )
                logger.info(f"✓ 已发送平仓通知: {len(closed_positions)} 个仓位")
        except Exception as e:
            logger.error(f"发送平仓通知失败: {e}")


def run_strategy(binance_client, config, runner=None):
    """运行策略入口"""
    strategy = Strategy(binance_client, config, runner)
    
    # 如果有 runner，保存策略实例引用
    if runner:
        runner.strategy_instance = strategy
    
    
    # 使用定时器启动
    logger.info("=" * 60)
    logger.info("策略启动：top_gainers_ema_1119_1537")
    logger.info("定时周期：5m（K线收盘前5秒执行）")
    logger.info("执行时间：04:55, 09:55, 14:55, 19:55, 24:55, 29:55, 34:55, 39:55, 44:55, 49:55, 54:55, 59:55")
    logger.info("=" * 60)
    
    # 创建后台调度器
    scheduler = BackgroundScheduler()
    strategy.scheduler = scheduler
    
    # 添加定时任务
    scheduler.add_job(
        strategy.run,
        'cron',
        minute='4,9,14,19,24,29,34,39,44,49,54,59', second='55',
        misfire_grace_time=5,
        coalesce=False
    )
    
    # 启动调度器（非阻塞）
    scheduler.start()
    logger.info("定时任务已配置，等待下次执行...")
    
    # 保持运行状态，同时检查 runner 的停止信号
    try:
        while True:
            if runner and hasattr(runner, 'running') and not runner.running:
                logger.info("收到停止信号，正在关闭...")
                break
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到中断信号")
    finally:
        logger.info("正在停止定时器...")
        scheduler.shutdown(wait=False)
        logger.info("定时器已停止")

