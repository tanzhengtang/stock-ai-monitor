"""
回测引擎
用于验证策略的历史表现
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import logging


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 1000000      # 初始资金
    commission_rate: float = 0.0003       # 佣金费率
    min_commission: float = 5             # 最低佣金
    tax_rate: float = 0.001               # 印花税（仅卖出）
    slippage: float = 0.001               # 滑点
    max_position_pct: float = 0.2         # 单只股票最大仓位
    stop_loss_pct: float = 0.05           # 止损比例
    take_profit_pct: float = 0.1          # 止盈比例
    max_holding_days: int = 10            # 最大持仓天数


@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str
    stock_code: str
    stock_name: str
    side: str  # 'buy' / 'sell'
    price: float
    quantity: int
    amount: float
    commission: float
    tax: float
    trade_date: str
    signal_reason: str
    pnl: float = 0  # 盈亏
    pnl_pct: float = 0  # 盈亏比例


@dataclass
class PositionRecord:
    """持仓记录"""
    stock_code: str
    stock_name: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    holding_days: int
    entry_date: str


@dataclass
class DailySnapshot:
    """每日快照"""
    date: str
    cash: float
    market_value: float
    total_assets: float
    total_pnl: float
    total_pnl_pct: float
    position_count: int
    daily_return: float


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    start_date: str
    end_date: str
    trading_days: int
    
    # 收益指标
    total_return: float           # 总收益率
    annual_return: float          # 年化收益率
    benchmark_return: float       # 基准收益率（可选）
    excess_return: float          # 超额收益
    
    # 风险指标
    max_drawdown: float           # 最大回撤
    max_drawdown_duration: int    # 最大回撤持续天数
    volatility: float             # 波动率
    sharpe_ratio: float           # 夏普比率
    sortino_ratio: float          # 索提诺比率
    calmar_ratio: float           # 卡玛比率
    
    # 交易指标
    total_trades: int             # 总交易次数
    winning_trades: int           # 盈利交易次数
    losing_trades: int            # 亏损交易次数
    win_rate: float               # 胜率
    profit_factor: float          # 盈亏比
    avg_win: float                # 平均盈利
    avg_loss: float               # 平均亏损
    avg_holding_days: float       # 平均持仓天数
    
    # 详细数据
    trades: List[TradeRecord]     # 交易记录
    daily_snapshots: List[DailySnapshot]  # 每日快照
    
    # 策略信息
    strategy_name: str
    config: BacktestConfig


class BacktestEngine:
    """回测引擎
    
    功能：
    1. 历史数据回测
    2. 绩效评估
    3. 风险控制
    4. 报告生成
    """

    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config or BacktestConfig()
        self.logger = logging.getLogger('BacktestEngine')
        
        # 状态
        self.cash = self.config.initial_capital
        self.positions: Dict[str, PositionRecord] = {}
        self.trades: List[TradeRecord] = []
        self.daily_snapshots: List[DailySnapshot] = []
        
        # 当前日期
        self.current_date = ""
        self.trade_counter = 0

    def reset(self):
        """重置回测状态"""
        self.cash = self.config.initial_capital
        self.positions = {}
        self.trades = []
        self.daily_snapshots = []
        self.current_date = ""
        self.trade_counter = 0

    def buy(
        self,
        stock_code: str,
        stock_name: str,
        price: float,
        quantity: int,
        signal_reason: str = ""
    ) -> Optional[TradeRecord]:
        """
        买入股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            price: 买入价格
            quantity: 买入数量
            signal_reason: 信号原因
            
        Returns:
            交易记录
        """
        # 验证数量
        if quantity <= 0 or quantity % 100 != 0:
            self.logger.warning(f"无效的数量: {quantity}")
            return None
        
        # 计算滑点后的价格
        exec_price = price * (1 + self.config.slippage)
        
        # 计算费用
        amount = exec_price * quantity
        commission = max(amount * self.config.commission_rate, self.config.min_commission)
        total_cost = amount + commission
        
        # 检查资金
        if total_cost > self.cash:
            self.logger.warning(f"资金不足: 需要{total_cost:.2f}, 可用{self.cash:.2f}")
            return None
        
        # 检查仓位
        total_assets = self.cash + sum(p.market_value for p in self.positions.values())
        current_position_value = self.positions[stock_code].market_value if stock_code in self.positions else 0
        new_position_value = current_position_value + amount
        position_pct = new_position_value / total_assets
        
        if position_pct > self.config.max_position_pct:
            self.logger.warning(f"超过最大仓位: {position_pct:.1%} > {self.config.max_position_pct:.1%}")
            return None
        
        # 执行买入
        self.cash -= total_cost
        
        # 更新持仓
        if stock_code in self.positions:
            # 加仓
            pos = self.positions[stock_code]
            total_quantity = pos.quantity + quantity
            total_cost_basis = pos.avg_cost * pos.quantity + exec_price * quantity
            pos.avg_cost = total_cost_basis / total_quantity
            pos.quantity = total_quantity
            pos.current_price = exec_price
            pos.market_value = pos.quantity * exec_price
            pos.unrealized_pnl = (exec_price - pos.avg_cost) * pos.quantity
            pos.unrealized_pnl_pct = (exec_price - pos.avg_cost) / pos.avg_cost * 100
        else:
            # 新建持仓
            self.positions[stock_code] = PositionRecord(
                stock_code=stock_code,
                stock_name=stock_name,
                quantity=quantity,
                avg_cost=exec_price,
                current_price=exec_price,
                market_value=amount,
                unrealized_pnl=0,
                unrealized_pnl_pct=0,
                holding_days=0,
                entry_date=self.current_date
            )
        
        # 记录交易
        self.trade_counter += 1
        trade = TradeRecord(
            trade_id=f"TRD_{self.trade_counter:06d}",
            stock_code=stock_code,
            stock_name=stock_name,
            side='buy',
            price=exec_price,
            quantity=quantity,
            amount=amount,
            commission=commission,
            tax=0,
            trade_date=self.current_date,
            signal_reason=signal_reason
        )
        self.trades.append(trade)
        
        return trade

    def sell(
        self,
        stock_code: str,
        price: float,
        quantity: Optional[int] = None,
        signal_reason: str = ""
    ) -> Optional[TradeRecord]:
        """
        卖出股票
        
        Args:
            stock_code: 股票代码
            price: 卖出价格
            quantity: 卖出数量（None表示全部卖出）
            signal_reason: 信号原因
            
        Returns:
            交易记录
        """
        if stock_code not in self.positions:
            self.logger.warning(f"没有持仓: {stock_code}")
            return None
        
        pos = self.positions[stock_code]
        
        # 默认全部卖出
        if quantity is None:
            quantity = pos.quantity
        
        # 验证数量
        if quantity <= 0 or quantity > pos.quantity:
            self.logger.warning(f"无效的数量: {quantity}, 可卖{pos.quantity}")
            return None
        
        # 计算滑点后的价格
        exec_price = price * (1 - self.config.slippage)
        
        # 计算费用
        amount = exec_price * quantity
        commission = max(amount * self.config.commission_rate, self.config.min_commission)
        tax = amount * self.config.tax_rate
        
        # 计算盈亏
        pnl = (exec_price - pos.avg_cost) * quantity - commission - tax
        pnl_pct = (exec_price - pos.avg_cost) / pos.avg_cost * 100
        
        # 执行卖出
        self.cash += amount - commission - tax
        
        # 更新持仓
        pos.quantity -= quantity
        if pos.quantity <= 0:
            del self.positions[stock_code]
        else:
            pos.market_value = pos.quantity * pos.current_price
        
        # 记录交易
        self.trade_counter += 1
        trade = TradeRecord(
            trade_id=f"TRD_{self.trade_counter:06d}",
            stock_code=stock_code,
            stock_name=pos.stock_name if stock_code in self.positions else "",
            side='sell',
            price=exec_price,
            quantity=quantity,
            amount=amount,
            commission=commission,
            tax=tax,
            trade_date=self.current_date,
            signal_reason=signal_reason,
            pnl=pnl,
            pnl_pct=pnl_pct
        )
        self.trades.append(trade)
        
        return trade

    def update_prices(self, prices: Dict[str, float]):
        """
        更新持仓价格
        
        Args:
            prices: {股票代码: 当前价格}
        """
        for stock_code, price in prices.items():
            if stock_code in self.positions:
                pos = self.positions[stock_code]
                pos.current_price = price
                pos.market_value = pos.quantity * price
                pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity
                pos.unrealized_pnl_pct = (price - pos.avg_cost) / pos.avg_cost * 100

    def update_date(self, date: str):
        """更新当前日期"""
        self.current_date = date
        
        # 更新持仓天数
        for pos in self.positions.values():
            if pos.entry_date:
                try:
                    entry = datetime.strptime(pos.entry_date, '%Y-%m-%d')
                    current = datetime.strptime(date, '%Y-%m-%d')
                    pos.holding_days = (current - entry).days
                except:
                    pos.holding_days += 1

    def take_snapshot(self):
        """记录每日快照"""
        market_value = sum(p.market_value for p in self.positions.values())
        total_assets = self.cash + market_value
        total_pnl = total_assets - self.config.initial_capital
        total_pnl_pct = total_pnl / self.config.initial_capital * 100
        
        # 计算日收益率
        daily_return = 0
        if self.daily_snapshots:
            prev_assets = self.daily_snapshots[-1].total_assets
            if prev_assets > 0:
                daily_return = (total_assets - prev_assets) / prev_assets * 100
        
        snapshot = DailySnapshot(
            date=self.current_date,
            cash=self.cash,
            market_value=market_value,
            total_assets=total_assets,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            position_count=len(self.positions),
            daily_return=daily_return
        )
        self.daily_snapshots.append(snapshot)

    def check_stop_loss(self, prices: Dict[str, float]) -> List[Dict]:
        """
        检查止损
        
        Args:
            prices: 当前价格
            
        Returns:
            需要止损的信号列表
        """
        signals = []
        
        for stock_code, pos in self.positions.items():
            if stock_code in prices:
                price = prices[stock_code]
                loss_pct = (pos.avg_cost - price) / pos.avg_cost
                
                if loss_pct >= self.config.stop_loss_pct:
                    signals.append({
                        'stock_code': stock_code,
                        'stock_name': pos.stock_name,
                        'action': 'sell',
                        'reason': f"触发止损: 亏损{loss_pct:.1%}",
                        'price': price
                    })
        
        return signals

    def check_take_profit(self, prices: Dict[str, float]) -> List[Dict]:
        """
        检查止盈
        
        Args:
            prices: 当前价格
            
        Returns:
            需要止盈的信号列表
        """
        signals = []
        
        for stock_code, pos in self.positions.items():
            if stock_code in prices:
                price = prices[stock_code]
                profit_pct = (price - pos.avg_cost) / pos.avg_cost
                
                if profit_pct >= self.config.take_profit_pct:
                    signals.append({
                        'stock_code': stock_code,
                        'stock_name': pos.stock_name,
                        'action': 'sell',
                        'reason': f"触发止盈: 盈利{profit_pct:.1%}",
                        'price': price
                    })
        
        return signals

    def check_max_holding(self) -> List[Dict]:
        """
        检查最大持仓天数
        
        Returns:
            需要卖出的信号列表
        """
        signals = []
        
        for stock_code, pos in self.positions.items():
            if pos.holding_days >= self.config.max_holding_days:
                signals.append({
                    'stock_code': stock_code,
                    'stock_name': pos.stock_name,
                    'action': 'sell',
                    'reason': f"超过最大持仓天数: {pos.holding_days}天",
                    'price': pos.current_price
                })
        
        return signals

    def get_total_assets(self) -> float:
        """获取总资产"""
        market_value = sum(p.market_value for p in self.positions.values())
        return self.cash + market_value

    def get_positions(self) -> List[PositionRecord]:
        """获取所有持仓"""
        return list(self.positions.values())

    def get_trades(self) -> List[TradeRecord]:
        """获取所有交易记录"""
        return self.trades

    def calculate_result(self, strategy_name: str = "Unknown") -> BacktestResult:
        """
        计算回测结果
        
        Args:
            strategy_name: 策略名称
            
        Returns:
            回测结果
        """
        if not self.daily_snapshots:
            return None
        
        # 基本信息
        start_date = self.daily_snapshots[0].date
        end_date = self.daily_snapshots[-1].date
        trading_days = len(self.daily_snapshots)
        
        # 收益指标
        initial_capital = self.config.initial_capital
        final_assets = self.daily_snapshots[-1].total_assets
        total_return = (final_assets - initial_capital) / initial_capital * 100
        
        # 年化收益率
        years = trading_days / 252  # 假设252个交易日/年
        annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
        
        # 日收益率序列
        daily_returns = [s.daily_return for s in self.daily_snapshots]
        
        # 波动率
        volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0
        
        # 最大回撤
        max_drawdown = 0
        max_drawdown_duration = 0
        peak = initial_capital
        drawdown_start = 0
        
        for i, snapshot in enumerate(self.daily_snapshots):
            if snapshot.total_assets > peak:
                peak = snapshot.total_assets
                drawdown_start = i
            
            drawdown = (peak - snapshot.total_assets) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_duration = i - drawdown_start
        
        # 夏普比率（假设无风险利率3%）
        risk_free_rate = 0.03
        excess_returns = [r / 100 - risk_free_rate / 252 for r in daily_returns]
        sharpe_ratio = (np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)) if np.std(excess_returns) > 0 else 0
        
        # 索提诺比率
        downside_returns = [r for r in excess_returns if r < 0]
        downside_std = np.std(downside_returns) if downside_returns else 0
        sortino_ratio = (np.mean(excess_returns) / downside_std * np.sqrt(252)) if downside_std > 0 else 0
        
        # 卡玛比率
        calmar_ratio = annual_return / max_drawdown if max_drawdown > 0 else 0
        
        # 交易指标
        buy_trades = [t for t in self.trades if t.side == 'buy']
        sell_trades = [t for t in self.trades if t.side == 'sell']
        
        winning_trades = [t for t in sell_trades if t.pnl > 0]
        losing_trades = [t for t in sell_trades if t.pnl <= 0]
        
        total_trades = len(sell_trades)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # 平均持仓天数
        holding_days = [t.quantity for t in sell_trades]  # 简化计算
        avg_holding_days = np.mean([p.holding_days for p in self.positions.values()]) if self.positions else 0
        
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            total_return=total_return,
            annual_return=annual_return,
            benchmark_return=0,  # 需要基准数据
            excess_return=total_return,  # 简化计算
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_holding_days=avg_holding_days,
            trades=self.trades,
            daily_snapshots=self.daily_snapshots,
            strategy_name=strategy_name,
            config=self.config
        )

    def format_report(self, result: BacktestResult) -> str:
        """
        格式化回测报告
        
        Args:
            result: 回测结果
            
        Returns:
            格式化的报告
        """
        report = f"""
{'='*70}
📊 回测报告 - {result.strategy_name}
{'='*70}

【基本信息】
  回测区间: {result.start_date} 至 {result.end_date}
  交易天数: {result.trading_days} 天
  初始资金: {self.config.initial_capital:,.0f} 元

【收益指标】
  总收益率: {result.total_return:.2f}%
  年化收益率: {result.annual_return:.2f}%
  
【风险指标】
  最大回撤: {result.max_drawdown:.2f}%
  最大回撤持续: {result.max_drawdown_duration} 天
  波动率: {result.volatility:.2f}%
  夏普比率: {result.sharpe_ratio:.2f}
  索提诺比率: {result.sortino_ratio:.2f}
  卡玛比率: {result.calmar_ratio:.2f}

【交易指标】
  总交易次数: {result.total_trades}
  盈利次数: {result.winning_trades}
  亏损次数: {result.losing_trades}
  胜率: {result.win_rate:.1f}%
  盈亏比: {result.profit_factor:.2f}
  平均盈利: {result.avg_win:,.0f} 元
  平均亏损: {result.avg_loss:,.0f} 元

【最终状态】
  总资产: {result.daily_snapshots[-1].total_assets:,.0f} 元
  可用资金: {result.daily_snapshots[-1].cash:,.0f} 元
  持仓市值: {result.daily_snapshots[-1].market_value:,.0f} 元
  持仓数量: {result.daily_snapshots[-1].position_count} 只

{'='*70}
"""
        return report


# 测试代码
if __name__ == '__main__':
    # 创建回测引擎
    config = BacktestConfig(
        initial_capital=1000000,
        stop_loss_pct=0.05,
        take_profit_pct=0.1
    )
    engine = BacktestEngine(config)
    
    # 模拟回测
    engine.update_date('2024-01-02')
    engine.buy('600519', '贵州茅台', 1800, 100, '均线多头')
    engine.take_snapshot()
    
    engine.update_date('2024-01-03')
    engine.update_prices({'600519': 1850})
    engine.take_snapshot()
    
    engine.update_date('2024-01-04')
    engine.sell('600519', 1900, signal_reason='止盈')
    engine.take_snapshot()
    
    # 计算结果
    result = engine.calculate_result('测试策略')
    print(engine.format_report(result))
