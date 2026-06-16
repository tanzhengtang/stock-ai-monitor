"""
easytrader交易接口
支持同花顺、通达信等客户端
"""

import time
from datetime import datetime
from typing import Dict, List, Optional

from .base_broker import (
    BaseBroker, Order, OrderSide, OrderType, OrderStatus,
    Position, Account
)


class EasyTraderBroker(BaseBroker):
    """easytrader交易接口
    
    通过模拟操作实现自动交易，支持：
    - 同花顺客户端
    - 通达信客户端
    - 雪球模拟盘
    
    使用前提：
    1. 安装 easytrader: pip install easytrader
    2. 打开对应的交易客户端
    3. 登录交易账号
    
    注意：
    - 需要客户端在前台运行
    - 操作有延迟，不适合高频交易
    - 可能被券商检测，谨慎使用
    """

    def __init__(self, client_type: str = 'ths'):
        """
        初始化
        
        Args:
            client_type: 客户端类型
                - 'ths': 同花顺
                - 'tdx': 通达信
                - 'xq': 雪球模拟盘
        """
        super().__init__("EasyTrader")
        self.client_type = client_type
        self.user = None
        
        # 订单记录
        self.orders: Dict[str, Order] = {}

    def connect(self, **kwargs) -> bool:
        """
        连接交易客户端
        
        Args:
            **kwargs:
                exe_path: 客户端可执行文件路径（可选）
        """
        try:
            import easytrader
            
            if self.client_type == 'ths':
                self.user = easytrader.use('ths')
            elif self.client_type == 'tdx':
                self.user = easytrader.use('tdx')
            elif self.client_type == 'xq':
                self.user = easytrader.use('xq')
            else:
                self.logger.error(f"不支持的客户端类型: {self.client_type}")
                return False
            
            # 连接客户端
            exe_path = kwargs.get('exe_path')
            if exe_path:
                self.user.connect(exe_path)
            else:
                self.user.connect()
            
            self.connected = True
            self.logger.info(f"连接成功: {self.client_type}")
            return True
            
        except ImportError:
            self.logger.error("easytrader未安装，请运行: pip install easytrader")
            return False
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.user = None
        self.connected = False
        self.logger.info("已断开连接")

    def get_account(self) -> Account:
        """获取账户信息"""
        if not self.connected or not self.user:
            return Account(account_id="EASY_001", cash=0)
        
        try:
            balance = self.user.balance
            return Account(
                account_id="EASY_001",
                cash=balance.get('可用余额', 0),
                frozen_cash=balance.get('冻结金额', 0),
                market_value=balance.get('证券市值', 0),
                total_assets=balance.get('总资产', 0)
            )
        except Exception as e:
            self.logger.error(f"获取账户信息失败: {e}")
            return Account(account_id="EASY_001", cash=0)

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        if not self.connected or not self.user:
            return []
        
        try:
            positions = self.user.position
            result = []
            
            for pos in positions:
                result.append(Position(
                    stock_code=pos.get('证券代码', ''),
                    stock_name=pos.get('证券名称', ''),
                    quantity=pos.get('股票余额', 0),
                    avg_cost=pos.get('成本价', 0),
                    current_price=pos.get('市价', 0),
                    market_value=pos.get('市值', 0),
                    unrealized_pnl=pos.get('盈亏', 0)
                ))
            
            return result
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            return []

    def get_current_price(self, stock_code: str) -> float:
        """获取当前价格"""
        if not self.connected or not self.user:
            return 0
        
        try:
            # 尝试从持仓获取
            positions = self.get_positions()
            for pos in positions:
                if pos.stock_code == stock_code:
                    return pos.current_price
            
            # TODO: 从行情接口获取
            return 0
        except Exception as e:
            self.logger.error(f"获取价格失败: {e}")
            return 0

    def submit_order(self, order: Order) -> Order:
        """提交订单"""
        if not self.connected or not self.user:
            order.status = OrderStatus.FAILED
            order.remark = "未连接"
            return order
        
        try:
            if order.is_buy:
                result = self.user.buy(
                    stock_code=order.stock_code,
                    price=order.price,
                    amount=order.quantity
                )
            else:
                result = self.user.sell(
                    stock_code=order.stock_code,
                    price=order.price,
                    amount=order.quantity
                )
            
            # 更新订单状态
            order.status = OrderStatus.SUBMITTED
            order.broker_order_id = result.get('order_id', '')
            order.updated_time = datetime.now()
            
            self.orders[order.order_id] = order
            self.logger.info(f"订单已提交: {order.side.value} {order.stock_code} {order.quantity}股")
            
            # 等待成交
            time.sleep(1)
            self._check_order_status(order)
            
            return order
            
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.remark = str(e)
            self.logger.error(f"下单失败: {e}")
            return order

    def _check_order_status(self, order: Order):
        """检查订单状态"""
        try:
            # 查询委托
            entrusts = self.user.entrust
            for entrust in entrusts:
                if entrust.get('合同编号') == order.broker_order_id:
                    status = entrust.get('状态说明', '')
                    if '已成' in status:
                        order.status = OrderStatus.FILLED
                        order.filled_quantity = order.quantity
                        order.filled_price = order.price
                    elif '部成' in status:
                        order.status = OrderStatus.PARTIAL
                    elif '已撤' in status:
                        order.status = OrderStatus.CANCELLED
                    break
        except Exception as e:
            self.logger.warning(f"查询订单状态失败: {e}")

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        if not self.connected or not self.user:
            return False
        
        order = self.orders.get(order_id)
        if not order or not order.broker_order_id:
            return False
        
        try:
            self.user.cancel_entrust(order.broker_order_id)
            order.status = OrderStatus.CANCELLED
            return True
        except Exception as e:
            self.logger.error(f"取消订单失败: {e}")
            return False

    def query_order(self, order_id: str) -> Optional[Order]:
        """查询订单"""
        return self.orders.get(order_id)

    def refresh_balance(self):
        """刷新余额"""
        if self.connected and self.user:
            try:
                self.user.refresh()
            except Exception as e:
                self.logger.warning(f"刷新余额失败: {e}")
