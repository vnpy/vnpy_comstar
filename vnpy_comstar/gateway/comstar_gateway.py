from datetime import datetime
from typing import List, Optional, Sequence, Dict, Any
from enum import Enum

from vnpy.event import EventEngine
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.constant import (
    Exchange,
    Product,
    Offset,
    OrderType,
    Direction,
    Status
)
from vnpy.trader.object import (
    SubscribeRequest,
    CancelRequest,
    OrderRequest,
    QuoteRequest,
    ContractData,
    TickData,
    OrderData,
    TradeData,
    LogData,
    QuoteData
)
from vnpy.trader.utility import round_to, ZoneInfo

from .comstar_api import TdApi


# 枚举值映射
VN_ENUMS: Dict[str, Any] = {
    "Exchange": Exchange,
    "Product": Product,
    "Offset": Offset,
    "OrderType": OrderType,
    "Direction": Direction,
    "Status": Status
}

# 其他常量
CHINA_TZ = ZoneInfo("Asia/Shanghai")       # 中国时区
SIZE = 10_000_000                               # 合约乘数


class ComstarGateway(BaseGateway):
    """
    VeighNa用于对接ComStar的XBond交易接口。
    """

    default_name: str = "COMSTAR"

    default_setting: Dict[str, str] = {
        "交易服务器": "",
        "用户名": "",
        "密码": "",
        "Key": "",
        "routing_type": "5",
        "valid_until_time": "18:30:00.000"
    }

    exchanges: List[Exchange] = [Exchange.XBOND, Exchange.CFETS]

    def __init__(self, event_engine: EventEngine, gateway_name: str):
        """构造函数"""
        super().__init__(event_engine, gateway_name)

        self.api: "UserApi" = UserApi(self)

        self.quote_infos: Dict[str, QuoteInfo] = {}

    def connect(self, setting: dict) -> None:
        """连接登录"""
        self.address: str = setting["交易服务器"]
        self.username: str = setting["用户名"]
        self.password: str = setting["密码"]
        self.key: str = setting["Key"]
        self.routing_type: str = setting["routing_type"]
        self.valid_untile_time: str = setting["valid_until_time"]

        self.api.connect(self.username, self.password, self.key, self.address)

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情"""
        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return
        symbol, settle_type = result

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "settle_type": settle_type,
            "vt_symbol": req.vt_symbol
        }

        if req.exchange == Exchange.XBOND:
            self.api.subscribe(data, self.gateway_name)
        else:
            self.api.maker_subscribe(data, self.gateway_name)

    def send_order(self, req: OrderRequest) -> str:
        """委托下单"""
        if req.exchange == Exchange.XBOND:
            return self.send_xbond_order(req)
        else:
            return self.send_cfets_order(req)

    def send_xbond_order(self, req: OrderRequest) -> str:
        """XBond委托下单"""
        if req.type not in {OrderType.LIMIT, OrderType.FAK}:
            self.write_log("仅支持限价单和FAK单")
            return ""

        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return ""
        symbol, settle_type = result

        # 乘以合约乘数
        volume = req.volume * SIZE

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "settle_type": settle_type,
            "direction": str(req.direction),
            "type": str(req.type),
            "price": req.price,
            "volume": volume,
            "strategy_name": req.reference,
            "vt_symbol": req.vt_symbol,
            "offset": str(Offset.NONE)
        }
        order_id: str = self.api.send_order(data, self.gateway_name)

        # 推送提交中状态
        order: OrderData = req.create_order_data(order_id, self.gateway_name)
        self.on_order(order)

        # 返回vt_orderid
        return f"{self.gateway_name}.{order_id}"

    def send_cfets_order(self, req: OrderRequest) -> str:
        """双边委托下单"""
        if req.type not in {OrderType.FAK}:
            self.write_log("仅支持FAK单")
            return ""

        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return ""
        symbol, settle_type = result

        # 乘以合约乘数
        volume = req.volume * SIZE

        quote_info: QuoteInfo = self.quote_infos.get(req.vt_symbol, None)
        if not quote_info:
            self.write_log(f"找不到{req.vt_symbol}的双边报价信息")
            return ""

        if req.direction == Direction.LONG:
            info: dict = quote_info.ask_info.get(req.price, None)
        else:
            info: dict = quote_info.bid_info.get(req.price, None)

        if not info:
            self.write_log(f"找不到{req.vt_symbol}指定价格{req.price}的报价信息")
            return ""

        # 委托数量强制转换成整数类型
        volume: int = int(volume)

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "settle_type": settle_type,
            "direction": str(req.direction),
            "type": str(req.type),
            "price": req.price,
            "volume": volume,
            "strategy_name": req.reference,
            "quoteId": info["quoteid"],
            "partyID": info["partyid"],
            "transactTime": info["time"],
            "vt_symbol": req.vt_symbol
        }

        order_id: str = self.api.maker_send_order(data, self.gateway_name)

        # 推送提交中状态
        order: OrderData = req.create_order_data(order_id, self.gateway_name)
        self.on_order(order)

        return f"{self.gateway_name}.{order_id}"

    def cancel_order(self, req: CancelRequest) -> None:
        """委托撤单"""
        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return
        symbol, settle_type = result

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "settle_type": settle_type,
            "orderid": req.orderid,
            "vt_symbol": req.vt_symbol
        }
        self.api.cancel_order(data, self.gateway_name)

    def send_quote(self, req: QuoteRequest) -> str:
        """双边报价下单"""
        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return ""
        symbol, settle_type = result

        # 乘以合约乘数
        bid_volume = req.bid_volume * SIZE
        ask_volume = req.ask_volume * SIZE

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "bid_settle_type": settle_type,
            "bid_price": req.bid_price,
            "bid_volume": bid_volume,
            "ask_price": req.ask_price,
            "ask_volume": ask_volume,
            "ask_settle_type": settle_type,
            "quoteTransType": "N",
            "validUntilTime": self.valid_untile_time,
            "routingType": self.routing_type,
            "strategy_name": req.reference,
            "vt_symbol": req.vt_symbol
        }

        quote_id: str = self.api.maker_send_quote(data, self.gateway_name)

        # 推送提交中状态
        quote: QuoteData = req.create_quote_data(quote_id, self.gateway_name)
        self.on_quote(quote)

        return f"{self.gateway_name}.{quote_id}"

    def cancel_quote(self, req: CancelRequest) -> None:
        """报价撤单"""
        # 拆分合约代码
        result: tuple = self.split_symbol(req.symbol)
        if not result:
            return
        symbol, settle_type = result

        data: dict = {
            "symbol": symbol,
            "exchange": str(req.exchange),
            "settle_type": settle_type,
            "orderid": req.orderid,
            "routingType": self.routing_type,
            "vt_symbol": req.vt_symbol
        }
        self.api.cancel_quote(data, self.gateway_name)

    def query_account(self) -> None:
        """不支持查询资金"""
        pass

    def query_position(self) -> None:
        """不支持查询持仓"""
        pass

    def query_all(self) -> None:
        """初始化查询"""
        self.api.get_all_contracts()
        self.api.get_all_orders()
        self.api.get_all_trades()
        self.api.get_all_quotes()

    def close(self) -> None:
        """关闭"""
        self.api.close()

    def update_quote_info(self, vt_symbol: str, data: dict) -> None:
        """更新报价缓存信息"""
        quote_info: QuoteInfo = self.quote_infos.get(vt_symbol, None)

        if not quote_info:
            quote_info = QuoteInfo(vt_symbol)
            self.quote_infos[vt_symbol] = quote_info

        quote_info.update_info(data)

    def split_symbol(self, symbol: str) -> Optional[tuple]:
        """
        拆分合约代码

        代码格式: 180406_T0 / 180406_T1
        """
        if "_" not in symbol:
            self.write_log("请输入清算速度T0或T1")
            return None

        new_symbol, settle_type = symbol.split("_")
        if settle_type not in {"T0", "T1"}:
            self.write_log("清算速度仅支持T0或T1")
            return None

        return new_symbol, settle_type


class UserApi(TdApi):
    """
    ComStar API的具体实现
    """

    def __init__(self, gateway):
        """构造函数"""
        super().__init__()

        self.gateway: BaseGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.trades: Dict[str, TradeData] = {}
        self.orders: Dict[str, OrderData] = {}

    def on_tick(self, data: dict):
        """行情推送"""
        # 双边行情
        if data["gateway_name"] == "COMSTAR-QUOTE":
            # 将交易中心格式转换为本地格式
            converted_data: dict = convert_quote_tick(data)

            # 生成Tick对象
            tick: TickData = parse_quote_tick(converted_data)

            # 更新报价周边信息
            self.gateway.update_quote_info(tick.vt_symbol, converted_data)

            # 用BID/ASK中间价表示最新价
            if tick.ask_price_1 and tick.bid_price_1:
                tick.last_price = (tick.ask_price_1 + tick.bid_price_1) / 2
                tick.last_price = round_to(tick.last_price, 0.0001)
        # XBOND行情
        else:
            tick: TickData = parse_tick(data)

        # 调整成交量量和挂单量
        tick.volume = tick.volume / SIZE
        tick.bid_volume_1 = tick.bid_volume_1 / SIZE
        tick.bid_volume_2 = tick.bid_volume_2 / SIZE
        tick.bid_volume_3 = tick.bid_volume_3 / SIZE
        tick.bid_volume_4 = tick.bid_volume_4 / SIZE
        tick.bid_volume_5 = tick.bid_volume_5 / SIZE
        tick.ask_volume_1 = tick.ask_volume_1 / SIZE
        tick.ask_volume_2 = tick.ask_volume_2 / SIZE
        tick.ask_volume_3 = tick.ask_volume_3 / SIZE
        tick.ask_volume_4 = tick.ask_volume_4 / SIZE
        tick.ask_volume_5 = tick.ask_volume_5 / SIZE

        if hasattr(tick, "public_bid_volume"):
            tick.public_bid_volume = tick.public_bid_volume / SIZE
            tick.public_ask_volume = tick.public_ask_volume / SIZE

        tick.gateway_name = self.gateway_name
        tick.localtime = datetime.now()

        self.gateway.on_tick(tick)

    def on_quote(self, data: dict):
        """报价状态更新"""
        quote: QuoteData = parse_quote(data)

        # 过滤服务端推送的SUBMITTING提交中状态
        if quote.status == Status.SUBMITTING:
            return

        quote.bid_volume = quote.bid_volume / SIZE
        quote.ask_volume = quote.ask_volume / SIZE

        quote.gateway_name = self.gateway_name

        self.gateway.on_quote(quote)

    def on_order(self, data: dict):
        """委托状态更新"""
        order: OrderData = parse_order(data)

        # 过滤服务端推送的SUBMITTING提交中状态
        if order.status == Status.SUBMITTING:
            return

        # 调整委托的数量和成交量
        order.volume = order.volume / SIZE
        order.traded = order.traded / SIZE

        # 过滤断线重连后的重复推送
        last_order: OrderData = self.orders.get(order.vt_orderid, None)
        if (
            last_order
            and order.traded == last_order.traded
            and order.status == last_order.status
        ):
            return
        self.orders[order.vt_orderid] = order

        # 推送委托
        order.gateway_name = self.gateway_name

        self.gateway.on_order(order)

    def on_trade(self, data: dict):
        """成交推送"""
        trade: TradeData = parse_trade(data)

        # 调整委托的成交量
        trade.volume = trade.volume / SIZE

        # 过滤断线重连后的重复推送
        if trade.vt_tradeid in self.trades:
            return
        self.trades[trade.vt_tradeid] = trade

        # 推送成交
        trade.gateway_name = self.gateway_name

        self.gateway.on_trade(trade)

    def on_log(self, data: dict):
        """日志推送"""
        log: LogData = parse_log(data)

        log.gateway_name = self.gateway_name

        self.gateway.on_log(log)

    def on_login(self, data: dict):
        """登陆回报"""
        if data["status"]:
            if self.gateway_name == "COMSTAR-QUOTE":
                self.gateway.maker_query_all()
            else:
                self.gateway.query_all()
            self.gateway.write_log("服务器登录成功")
        else:
            self.gateway.write_log("服务器登录失败")

    def on_disconnected(self, reason: str):
        """断线回报"""
        self.gateway.write_log(reason)

    def on_all_quotes(self, data: Sequence[dict]):
        """查询报价回报"""
        for d in data:
            self.on_quote(d)

        self.gateway.write_log("做市报价信息查询成功")

    def on_all_contracts(self, data: Sequence[dict]):
        """查询合约回报"""
        for d in data:
            for settle_type in ("T0", "T1"):
                for exchange in (Exchange.XBOND, Exchange.CFETS):
                    contract: ContractData = parse_contract(d, settle_type)

                    contract.size = contract.size * SIZE
                    contract.min_volume = contract.min_volume / SIZE
                    contract.exchange = exchange
                    contract.gateway_name = self.gateway_name

                    contract.__post_init__()
                    self.gateway.on_contract(contract)

        self.gateway.write_log("合约信息查询成功")

    def on_all_orders(self, data: Sequence[dict]):
        """查询委托回报"""
        for d in data:
            self.on_order(d)

        self.gateway.write_log("委托信息查询成功")

    def on_all_trades(self, data: Sequence[dict]):
        """查询成交回报"""
        for d in data:
            self.on_trade(d)

        self.gateway.write_log("成交信息查询成功")

    def on_auth(self, status: bool):
        """授权验证回报"""
        if status:
            self.gateway.write_log("服务器授权验证成功")
        else:
            self.gateway.write_log("服务器授权验证失败")


def parse_tick(data: dict) -> TickData:
    """
    解析行情数据

    XBond深度数据规则:
    1. Bid/Ask1是共有最优行情
    2. Bid/Ask2-6是私有最优行情
    """
    tick: TickData = TickData(
        symbol=f"{data['symbol']}_{data['settle_type']}",
        exchange=enum_decode(data["exchange"]),
        datetime=parse_datetime(data["datetime"]),
        name=data["name"],
        volume=float(data["volume"]),
        last_price=float(data["last_price"]),
        open_price=float(data["open_price"]),
        high_price=float(data["high_price"]),
        low_price=float(data["low_price"]),
        pre_close=float(data["pre_close"]),
        bid_price_1=float(data["bid_price_2"]),
        bid_price_2=float(data["bid_price_3"]),
        bid_price_3=float(data["bid_price_4"]),
        bid_price_4=float(data["bid_price_5"]),
        bid_price_5=float(data["bid_price_6"]),
        ask_price_1=float(data["ask_price_2"]),
        ask_price_2=float(data["ask_price_3"]),
        ask_price_3=float(data["ask_price_4"]),
        ask_price_4=float(data["ask_price_5"]),
        ask_price_5=float(data["ask_price_6"]),
        bid_volume_1=float(data["bid_volume_2"]),
        bid_volume_2=float(data["bid_volume_3"]),
        bid_volume_3=float(data["bid_volume_4"]),
        bid_volume_4=float(data["bid_volume_5"]),
        bid_volume_5=float(data["bid_volume_6"]),
        ask_volume_1=float(data["ask_volume_2"]),
        ask_volume_2=float(data["ask_volume_3"]),
        ask_volume_3=float(data["ask_volume_4"]),
        ask_volume_4=float(data["ask_volume_5"]),
        ask_volume_5=float(data["ask_volume_6"]),
        gateway_name=data["gateway_name"]
    )

    tick.public_bid_price = float(data["bid_price_1"])
    tick.public_ask_price = float(data["ask_price_1"])
    tick.public_bid_volume = float(data["bid_volume_1"])
    tick.public_ask_volume = float(data["ask_volume_1"])

    return tick


def parse_quote(data: dict) -> QuoteData:
    """解析报价数据"""
    quote: QuoteData = QuoteData(
        symbol=f"{data['securityId']}_{data['buySideVO']['settlType']}",
        exchange=enum_decode(data["exchange"]),
        quoteid=data["quoteid"],
        bid_price=data["buySideVO"]["price"],
        bid_volume=data["buySideVO"]["leaveQty"],
        ask_price=data["sellSideVO"]["price"],
        ask_volume=data["sellSideVO"]["leaveQty"],
        bid_offset=Offset.NONE,
        ask_offset=Offset.NONE,
        status=enum_decode(data["status"]),
        datetime=generate_datetime(data["transactTime"]),
        gateway_name=data["gateway_name"]
    )
    return quote


def parse_quote_tick(data: dict) -> TickData:
    """解析双边行情数据"""
    tick: TickData = TickData(
        symbol=f"{data['symbol']}_{data['settle_type']}",
        exchange=enum_decode(data["exchange"]),
        datetime=parse_datetime(data["datetime"]),
        name=data["name"],
        bid_price_1=data.get("bid_price_1", 0),
        ask_price_1=data.get("ask_price_1", 0),
        bid_volume_1=data.get("bid_volume_1", 0),
        ask_volume_1=data.get("ask_volume_1", 0),
        bid_price_2=data.get("bid_price_2", 0),
        ask_price_2=data.get("ask_price_2", 0),
        bid_volume_2=data.get("bid_volume_2", 0),
        ask_volume_2=data.get("ask_volume_2", 0),
        bid_price_3=data.get("bid_price_3", 0),
        ask_price_3=data.get("ask_price_3", 0),
        bid_volume_3=data.get("bid_volume_3", 0),
        ask_volume_3=data.get("ask_volume_3", 0),
        bid_price_4=data.get("bid_price_4", 0),
        ask_price_4=data.get("ask_price_4", 0),
        bid_volume_4=data.get("bid_volume_4", 0),
        ask_volume_4=data.get("ask_volume_4", 0),
        bid_price_5=data.get("bid_price_5", 0),
        ask_price_5=data.get("ask_price_5", 0),
        bid_volume_5=data.get("bid_volume_5", 0),
        ask_volume_5=data.get("ask_volume_5", 0),
        gateway_name=data["gateway_name"]
    )
    return tick


def parse_order(data: dict) -> OrderData:
    """解析委托更新数据"""
    order: OrderData = OrderData(
        symbol=f"{data['symbol']}_{data['settle_type']}",
        exchange=enum_decode(data["exchange"]),
        orderid=data["orderid"],
        type=enum_decode(data["type"]),
        direction=enum_decode(data["direction"]),
        offset=Offset.NONE,
        price=float(data["price"]),
        volume=float(data["volume"]),
        traded=float(data["traded"]),
        status=enum_decode(data["status"]),
        datetime=generate_datetime(data["time"]),
        gateway_name=data["gateway_name"]
    )
    return order


def parse_trade(data: dict) -> TradeData:
    """解析成交推送数据"""
    trade: TradeData = TradeData(
        symbol=f"{data['symbol']}_{data['settle_type']}",
        exchange=enum_decode(data["exchange"]),
        orderid=data["orderid"],
        tradeid=data["tradeid"],
        direction=enum_decode(data["direction"]),
        offset=Offset.NONE,
        price=float(data["price"]),
        volume=float(data["volume"]),
        datetime=generate_datetime(data["time"]),
        gateway_name=data["gateway_name"]
    )
    return trade


def parse_contract(data: dict, settle_type: str) -> ContractData:
    """解析交易合约数据"""
    contract: ContractData = ContractData(
        symbol=f"{data['symbol']}_{settle_type}",
        exchange=enum_decode(data["exchange"]),
        name=data["name"],
        product=enum_decode(data["product"]),
        size=int(data["size"]),
        pricetick=float(data["pricetick"]),
        min_volume=float(data["min_volume"]),
        gateway_name=data["gateway_name"]
    )
    return contract


def parse_log(data: dict) -> LogData:
    """解析日志信息数据"""
    log: LogData = LogData(
        msg=data["msg"],
        level=data["level"],
        gateway_name=data["gateway_name"]
    )
    log.time = parse_datetime(data["time"])
    return log


def parse_datetime(s: str) -> datetime:
    """解析时间戳字符串"""
    if "." in s:
        dt: datetime = datetime.strptime(s, "%Y%m%d %H:%M:%S.%f")
    elif len(s) > 0:
        dt: datetime = datetime.strptime(s, "%Y%m%d %H:%M:%S")
    else:
        dt: datetime = datetime.now()

    dt: datetime = dt.astimezone(CHINA_TZ)
    return dt


def enum_decode(s: str) -> Optional[Enum]:
    """将字符串转换为枚举值"""
    if "." in s:
        name, member = s.split(".")
        return getattr(VN_ENUMS[name], member)
    else:
        return None


def generate_datetime(time: str) -> datetime:
    """生成时间戳"""
    today: str = datetime.now().strftime("%Y%m%d")
    timestamp: str = f"{today} {time}"
    dt: datetime = parse_datetime(timestamp)
    return dt


def convert_quote_tick(data: dict) -> dict:
    """转换双边市场的Tick数据格式"""
    tick_data: dict = {
        "datetime": data["datetime"],
        "gateway_name": data["gateway_name"],
        "symbol": data["securityId"],
        "name": data["symbol"],
        "exchange": "Exchange.CFETS",
        "settle_type": "T0" if data["settlType"] == "1" else "T1"
    }

    level_map: dict = data["qdmEspMarketDataLevelMap"]

    for i in range(1, 11):
        # 获取当前深度数据
        depth = str(i)
        d: dict = level_map.get(depth, None)

        # 如果没有则结束循环
        if not d:
            break

        # 处理Bid
        if "cleanPriceBid" in d:
            tick_data[f"bid_price_{depth}"] = d["cleanPriceBid"]
            tick_data[f"bid_volume_{depth}"] = d["orderQtyBid"]
            tick_data[f"bid_time_{depth}"] = d["mdEntryTimeBid"]
            tick_data[f"bid_quoteid_{depth}"] = d["quoteEntryIdBid"]
            tick_data[f"bid_partyid_{depth}"] = d["partyInfoBid"]["partyID"]

        # 处理Offer
        if "cleanPriceOffer" in d:
            tick_data[f"ask_price_{depth}"] = d["cleanPriceOffer"]
            tick_data[f"ask_volume_{depth}"] = d["orderQtyOffer"]
            tick_data[f"ask_time_{depth}"] = d["mdEntryTimeOffer"]
            tick_data[f"ask_quoteid_{depth}"] = d["quoteEntryIdOffer"]
            tick_data[f"ask_partyid_{depth}"] = d["partyInfoOffer"]["partyID"]

    return tick_data


class QuoteInfo:
    """报价信息"""

    def __init__(self, vt_symbol: str) -> None:
        """"""
        self.vt_symbol: str = vt_symbol
        self.bid_info: Dict[float, Dict[str, str]] = {}
        self.ask_info: Dict[float, Dict[str, str]] = {}

    def update_info(self, data: dict) -> None:
        """更新缓存信息"""
        # Bid信息
        self.bid_info.clear()
        for i in range(1, 6):
            price = data.get(f"bid_price_{i}", None)
            if not price:
                break

            self.bid_info[price] = {
                "time": data[f"bid_time_{i}"],
                "quoteid": data[f"bid_quoteid_{i}"],
                "partyid": data[f"bid_partyid_{i}"],
            }

        # Ask信息
        self.ask_info.clear()
        for i in range(1, 6):
            price = data.get(f"ask_price_{i}", None)
            if not price:
                break

            self.ask_info[price] = {
                "time": data[f"ask_time_{i}"],
                "quoteid": data[f"ask_quoteid_{i}"],
                "partyid": data[f"ask_partyid_{i}"],
            }
