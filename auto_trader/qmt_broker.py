"""
QMT交易接口
对接迅投QMT量化交易终端
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable

from .base_broker import (
    BaseBroker, Order, OrderSide, OrderType, OrderStatus,
    Position, Account
)


class QMTBroker(BaseBroker):
    """QMT交易接口
    
    迅投QMT量化交易终端接口，支持：
    - 股票交易
    - 查询账户和持仓
    - 实时行情
    
    使用前提：
    1. 开通QMT权限（联系券商）
    2. 安装QMT客户端
    3. 启动QMT并登录
    
    QMT提供两种接口：
    1. miniQMT - 简化版，通过xtquant库调用
    2. 完整QMT - 需要运行在QMT环境中
    """

    def __init__(self, account_id: str = ''):
        """
        初始化QMT接口
        
        Args:
            account_id: 资金账号
        """
        super().__init__("QMT")
        self.account_id = account_id
        
        # QMT连接
        self.xt_trader = None
        self.session_id = None
        
        # 订单记录
        self.orders: Dict[str, Order] = {}
        
        # 回调函数
        self.on_order_update: Optional[Callable] = None
        self.on_account_update: Optional[Callable] = None

    def connect(self, **kwargs) -> bool:
        """
        连接QMT
        
        Args:
            **kwargs:
                path: QMT安装路径
                account: 资金账号
        """
        try:
            from xtquant import xttrader, xtdata
            
            # 获取参数
            qmt_path = kwargs.get('path', '')
            self.account_id = kwargs.get('account', self.account_id)
            
            if not qmt_path:
                # 尝试默认路径
                qmt_path = os.environ.get('QMT_PATH', '')
            
            if not qmt_path:
                self.logger.error("QMT路径未指定")
                return False
            
            # 创建交易对象
            self.xt_trader = xttrader.XtQuantTrader(qmt_path, self.session_id)
            
            # 注册回调
            self.xt_trader.register_callback(self._create_callback())
            
            # 启动交易
            self.xt_trader.start()
            
            # 连接
            connect_result = self.xt_trader.connect()
            if connect_result != 0:
                self.logger.error(f"QMT连接失败: {connect_result}")
                return False
            
            # 订阅账号
            subscribe_result = self.xt_trader.subscribe_account(self.account_id)
            if subscribe_result != 0:
                self.logger.warning(f"订阅账号失败: {subscribe_result}")
            
            self.connected = True
            self.logger.info(f"QMT连接成功: {self.account_id}")
            return True
            
        except ImportError:
            self.logger.error("xtquant未安装，请确保QMT环境正确")
            return False
        except Exception as e:
            self.logger.error(f"QMT连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.xt_trader:
            try:
                self.xt_trader.stop()
            except Exception as e:
                self.logger.warning(f"断开连接异常: {e}")
        
        self.connected = False
        self.logger.info("QMT已断开")

    def _create_callback(self):
        """创建回调对象"""
        from xtquant import xttrader
        
        class Callback(xttrader.XtQuantTraderCallback):
            def __init__(self, broker):
                self.broker = broker
            
            def on_disconnected(self):
                self.broker.connected = False
                self.broker.logger.warning("QMT连接断开")
            
            def on_order_error(self, order_error):
                self.broker.logger.error(f"订单错误: {order_error}")
            
            def on_order_response(self, response):
                self.broker.logger.info(f"订单响应: {response}")
            
            def on_stock_position(self, position):
                self.broker.logger.debug(f"持仓更新: {position}")
            
            def on_asset(self, asset):
                self.broker.logger.debug(f"资产更新: {asset}")
        
        return Callback(self)

    def get_account(self) -> Account:
        """获取账户信息"""
        if not self.connected or not self.xt_trader:
            return Account(account_id=self.account_id, cash=0)
        
        try:
            asset = self.xt_trader.query_stock_asset(self.account_id)
            
            return Account(
                account_id=self.account_id,
                cash=asset.cash if asset else 0,
                frozen_cash=asset.frozen_cash if asset else 0,
                market_value=asset.market_value if asset else 0,
                total_assets=asset.total_asset if asset else 0
            )
        except Exception as e:
            self.logger.error(f"获取账户信息失败: {e}")
            return Account(account_id=self.account_id, cash=0)

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        if not self.connected or not self.xt_trader:
            return []
        
        try:
            positions = self.xt_trader.query_stock_positions(self.account_id)
            result = []
            
            for pos in positions:
                if pos.volume > 0:
                    result.append(Position(
                        stock_code=pos.stock_code,
                        stock_name='',
                        quantity=pos.volume,
                        avg_cost=pos.open_price,
                        current_price=pos.market_value / pos.volume if pos.volume > 0 else 0,
                        market_value=pos.market_value
                    ))
            
            return result
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            return []

    def get_current_price(self, stock_code: str) -> float:
        """获取当前价格"""
        if not self.connected:
            return 0
        
        try:
            from xtquant import xtdata
            
            # 获取最新行情
            quote = xtdata.get_market_data([stock_code], ['last_price'])
            if quote and stock_code in quote:
                return quote[stock_code][0]
            
            return 0
        except Exception as e:
            self.logger.error(f"获取价格失败: {e}")
            return 0

    def submit_order(self, order: Order) -> Order:
        """提交订单"""
        if not self.connected or not self.xt_trader:
            order.status = OrderStatus.FAILED
            order.remark = "未连接"
            return order
        
        try:
            from xtquant import xttype
            
            # 构建订单
            stock_code = order.stock_code
            
            # 判断市场
            if stock_code.startswith(('60', '68')):
                market = xttype.MARKET_SHA  # 上海
            else:
                market = xttype.MARKET_SZA  # 深圳
            
            # 下单
            if order.is_buy:
                order_id = self.xt_trader.order_stock(
                    account=self.account_id,
                    stock_code=stock_code,
                    order_type=xttype.STOCK_BUY,
                    order_volume=order.quantity,
                    price_type=xttype.FIX_PRICE if order.order_type == OrderType.LIMIT else xttype.LATEST_PRICE,
                    price=order.price
                )
            else:
                order_id = self.xt_trader.order_stock(
                    account=self.account_id,
                    stock_code=stock_code,
                    order_type=xttype.STOCK_SELL,
                    order_volume=order.quantity,
                    price_type=xttype.FIX_PRICE if order.order_type == OrderType.LIMIT else xttype.LATEST_PRICE,
                    price=order.price
                )
            
            # 更新订单
            order.broker_order_id = str(order_id)
            order.status = OrderStatus.SUBMITTED
            order.updated_time = datetime.now()
            
            self.orders[order.order_id] = order
            self.logger.info(f"订单已提交: {order.side.value} {order.stock_code} {order.quantity}股")
            
            return order
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.remark = str(e)
            self.logger.error(f"下单失败: {e}")
            return order

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        if not self.connected or not self.xt_trader:
            return False
        
        order = self.orders.get(order_id)
        if not order or not order.broker_order_id:
            return False
        
        try:
            from xtquant import xttype
            
            result = self.xt_trader.cancel_order_stock(
                self.account_id,
                int(order.broker_order_id)
            )
            
            if result == 0:
                order.status = OrderStatus.CANCELLED
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return False

    def query_order(self, order_id: str) -> Optional[Order]:
        """查询订单"""
        return self.orders.get(order_id)

    def query_orders(self) -> List[Order]:
        """查询所有订单"""
        if not self.connected or not self.xt_trader:
            return []
        
        try:
            orders = self.xt_trader.query_stock_orders(self.account_id)
            return list(self.orders.values())
        except Exception as e:
            self.logger.error(f"查询订单失败: {e}")
            return []
