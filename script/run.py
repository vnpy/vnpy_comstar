# flake8: noqa
from vnpy.event import EventEngine

from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp, QtCore
from vnpy.trader.ui.widget import QuoteMonitor

from vnpy_comstar import ComstarQuoteGateway, ComstarXbondGateway
from vnpy_zheshang.quote_widget import QuotingWidget


def main():
    """"""
    qapp = create_qapp()

    event_engine = EventEngine()

    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(ComstarXbondGateway)
    main_engine.add_gateway(ComstarQuoteGateway)
    
    main_window = MainWindow(main_engine, event_engine)

    quote_widget, quote_dock = main_window.create_dock(
        QuoteMonitor,
        "报价",
        QtCore.Qt.RightDockWidgetArea
    )

    quoting_widget, quoting_dock = main_window.create_dock(
        QuotingWidget,
        "做市",
        QtCore.Qt.LeftDockWidgetArea
    )

    main_window.showMaximized()

    qapp.exec()


if __name__ == "__main__":
    main()
