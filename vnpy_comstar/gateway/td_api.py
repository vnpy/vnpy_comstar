from typing import List


class TdApi:
    """ComStar API"""

    def connect(self, username: str, password: str, key: str, address: str) -> None:
        """连接登录"""
        pass

    def close(self) -> None:
        """关闭接口"""
        pass

    def subscribe(self, data: dict) -> None:
        """
        订阅行情

        数据字段：
        symbol
        exchange
        settle_type
        """
        pass

    def send_order(self, data: dict) -> str:
        """
        发送委托

        数据字段：
        symbol
        exchange
        settle_type
        direction
        type
        price
        volume
        strategy_name
        quoteId         仅双边
        partyID         仅双边
        transactTime    仅双边
        """
        pass

    def cancel_order(self, data: dict) -> None:
        """
        撤销委托

        数据字段：
        symbol
        exchange
        settle_type
        orderid
        """
        pass

    def send_quote(self, data: dict) -> str:
        """
        发送报价

        数据字段：
        symbol
        exchange
        bid_settle_type
        bid_price
        bid_volume
        ask_price
        ask_volume
        ask_settle_type
        quoteTransType
        validUntilTime
        routingType
        strategy_name
        """
        pass

    def cancel_quote(self, data: dict) -> None:
        """
        撤销报价

        数据字段：
        symbol
        exchange
        settle_type
        orderid
        """
        pass

    def get_all_contracts(self) -> None:
        """查询合约信息"""
        pass

    def get_all_orders(self) -> None:
        """查询委托信息"""
        pass

    def get_all_trades(self) -> None:
        """查询成交信息"""
        pass

    def get_all_quotes(self) -> None:
        """查询报价信息"""
        pass

    def on_login(self, data: dict) -> None:
        """
        登陆回报

        数据字段：
        status
        """
        pass

    def on_disconnected(self, reason: str):
        """断线回报"""
        pass

    def on_tick(self, data: dict) -> None:
        """
        行情推送

        数据字段：
        symbol
        settle_type
        exchange
        datetime
        name
        volume
        last_price
        open_price
        high_price
        low_price
        pre_close
        bid_price_1
        bid_price_2
        bid_price_3
        bid_price_4
        bid_price_5
        bid_price_6
        ask_price_1
        ask_price_2
        ask_price_3
        ask_price_4
        ask_price_5
        ask_price_6
        bid_volume_1
        bid_volume_2
        bid_volume_3
        bid_volume_4
        bid_volume_5
        bid_volume_6
        ask_volume_1
        ask_volume_2
        ask_volume_3
        ask_volume_4
        ask_volume_5
        ask_volume_6

        仅双边
        bid_time_1
        bid_time_2
        bid_time_3
        bid_time_4
        bid_time_5
        bid_time_6
        ask_time_1
        ask_time_2
        ask_time_3
        ask_time_4
        ask_time_5
        ask_time_6

        bid_quoteid_1
        bid_quoteid_2
        bid_quoteid_3
        bid_quoteid_4
        bid_quoteid_5
        bid_quoteid_6
        ask_quoteid_1
        ask_quoteid_2
        ask_quoteid_3
        ask_quoteid_4
        ask_quoteid_5
        ask_quoteid_6

        bid_partyid_1
        bid_partyid_2
        bid_partyid_3
        bid_partyid_4
        bid_partyid_5
        bid_partyid_6
        ask_partyid_1
        ask_partyid_2
        ask_partyid_3
        ask_partyid_4
        ask_partyid_5
        ask_partyid_6
        """
        pass

    def on_quote(self, data: dict) -> None:
        """
        报价状态更新

        数据字段：
        symbol
        settle_type
        exchange
        quoteid
        bid_price
        bid_volume
        ask_price
        ask_volume
        status
        time
        """
        pass

    def on_order(self, data: dict) -> None:
        """
        委托状态更新

        数据字段：
        symbol
        settle_type
        exchange
        orderid
        type
        direction
        price
        volume
        traded
        status
        time
        """
        pass

    def on_trade(self, data: dict) -> None:
        """
        成交推送

        数据字段：
        symbol
        settle_type
        exchange
        orderid
        tradeid
        direction
        price
        volume
        time
        """
        pass

    def on_log(self, data: dict) -> None:
        """
        日志推送

        数据字段：
        msg
        """
        pass

    def on_all_quotes(self, data: List[dict]):
        """
        查询报价回报

        数据字段参考on_quote
        """
        pass

    def on_all_contracts(self, data: List[dict]):
        """
        查询合约回报

        数据字段参考on_contract
        """
        pass

    def on_all_orders(self, data: List[dict]):
        """
        查询委托回报

        数据字段参考on_order
        """
        pass

    def on_all_trades(self, data: List[dict]):
        """
        查询成交回报

        数据字段参考on_trade
        """
        pass

    def on_auth(self, status: bool):
        """授权验证回报"""
        pass
