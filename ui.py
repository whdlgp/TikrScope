import pytz
from PyQt5.QtWidgets import (
    QWidget, QLabel, QRadioButton, QCheckBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QButtonGroup, QListWidget, QListWidgetItem,
    QSplitter, QLineEdit, QComboBox, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt, QSize
from PyQt5.QtGui import QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
from qt_material import list_themes

from data import fetch_market_data, create_plot_html, create_thumbnail, calculate_price_changes, CONFIG_PATH, load_config, save_config
from tickernews import build_search_queries, fetch_news_for_queries
from subui import NewsDialog

def create_thumbnail_widget(ticker, timezone, force_update=False):
    thumb_path = create_thumbnail(ticker, timezone, force_update)

    widget = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(2, 2, 2, 2)

    label = QLabel(ticker)
    label.setAlignment(Qt.AlignCenter)

    pixmap = QPixmap(thumb_path)
    image_label = QLabel()
    image_label.setPixmap(pixmap)
    image_label.setAlignment(Qt.AlignCenter)

    layout.addWidget(label)
    layout.addWidget(image_label)
    widget.setLayout(layout)

    return widget

class StockApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikrScope")
        self.setGeometry(100, 100, 1200, 750)

        self.config = load_config(CONFIG_PATH)

        self.ticker_input = QLineEdit()
        self.ticker_input.setText(','.join(self.config["tickers"]))

        self.timezone_selector = QComboBox()
        self.timezone_selector.addItems(pytz.all_timezones)
        self.timezone_selector.setCurrentText(self.config["timezone"])
        self.timezone_selector.currentTextChanged.connect(self.change_timezone)

        self.theme_selector = QComboBox()
        self.theme_selector.addItems(list_themes())
        self.theme_selector.setCurrentText(self.config.get("theme", "dark_teal.xml"))
        self.theme_selector.currentTextChanged.connect(self.change_theme)

        self.ticker_update_btn = QPushButton("Apply Tickers")
        self.ticker_update_btn.clicked.connect(self.apply_tickers)

        ticker_input_layout = QHBoxLayout()
        ticker_input_layout.addWidget(QLabel("Tickers (comma-separated):"))
        ticker_input_layout.addWidget(self.ticker_input)
        ticker_input_layout.addWidget(QLabel("Timezone:"))
        ticker_input_layout.addWidget(self.timezone_selector)
        ticker_input_layout.addWidget(QLabel("Theme:"))
        ticker_input_layout.addWidget(self.theme_selector)
        ticker_input_layout.addWidget(self.ticker_update_btn)

        self.ticker_list = QListWidget()
        self.ticker_list.setIconSize(QSize(200, 140))
        self.ticker_list.currentItemChanged.connect(self.update_plot)

        self.thumb_update_btn = QPushButton("Update Thumbnails")
        self.thumb_update_btn.clicked.connect(self.update_all_thumbnails)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.thumb_update_btn)
        left_layout.addWidget(self.ticker_list)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        self.web_view = QWebEngineView()

        self.chart_type_group = QButtonGroup()
        chart_layout = QHBoxLayout()
        chart_layout.setAlignment(Qt.AlignLeft)
        for ctype in ["line", "candlestick"]:
            rb = QRadioButton(ctype.capitalize())
            rb.clicked.connect(self.change_chart_type)
            if self.config["chart_type"] == ctype:
                rb.setChecked(True)
            self.chart_type_group.addButton(rb)
            chart_layout.addWidget(rb)

        self.period_group = QButtonGroup()
        period_layout = QHBoxLayout()
        period_layout.setAlignment(Qt.AlignLeft)
        for period in ["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y"]:
            rb = QRadioButton(period)
            rb.clicked.connect(self.change_period)
            if self.config["period"] == period:
                rb.setChecked(True)
            self.period_group.addButton(rb)
            period_layout.addWidget(rb)

        indicator_layout = QHBoxLayout()
        self.main_indicator_group = {}
        indicator_layout.setAlignment(Qt.AlignLeft)
        main_indicators = ["sma5", "sma20", "sma60", "sma120", "vwap"]
        for indicator in main_indicators:
            cb = QCheckBox(indicator.upper())
            cb.setChecked(indicator in self.config.get("main_indicator", []))
            cb.clicked.connect(self.change_main_indicator)
            self.main_indicator_group[indicator] = cb
            indicator_layout.addWidget(cb)

        sub_indicator_layout = QHBoxLayout()
        sub_indicator_layout.setAlignment(Qt.AlignLeft)
        self.sub_indicator_group = QButtonGroup()
        self.sub_indicators = {
            "williams_r": "Williams %R",
            "mfi": "MFI (Money Flow Index)",
            "stoch_rsi": "Stochastic RSI"
        }
        for key, label in self.sub_indicators.items():
            rb = QRadioButton(label)
            rb.clicked.connect(self.change_sub_indicator)
            self.sub_indicator_group.addButton(rb)
            sub_indicator_layout.addWidget(rb)
            if self.config.get("sub_indicator", "williams_r") == key:
                rb.setChecked(True)

        self.auto_refresh_checkbox = QCheckBox("Auto Refresh (30 sec)")
        self.auto_refresh_checkbox.stateChanged.connect(self.toggle_auto_refresh)

        self.manual_update_btn = QPushButton("Update Plot Now")
        self.manual_update_btn.clicked.connect(self.update_plot)

        self.search_news_btn = QPushButton("Search News")
        self.search_news_btn.clicked.connect(self.search_news)

        self.change_summary = QLabel()
        self.change_summary.setText("")
        self.change_summary.setStyleSheet("padding: 2px; font-weight: bold;")
        self.change_summary.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        options_layout = QVBoxLayout()
        options_layout.addLayout(chart_layout)
        options_layout.addLayout(period_layout)
        options_layout.addLayout(indicator_layout)
        options_layout.addLayout(sub_indicator_layout)
        refresh_layout = QHBoxLayout()
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        refresh_layout.addWidget(self.manual_update_btn)
        refresh_layout.addWidget(self.search_news_btn)
        options_layout.addLayout(refresh_layout)

        chart_layout = QVBoxLayout()
        chart_layout.addWidget(self.change_summary)
        chart_layout.addWidget(self.web_view)

        right_layout = QVBoxLayout()
        right_layout.addLayout(options_layout)
        right_layout.addLayout(chart_layout)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 3)

        main_layout = QVBoxLayout()
        main_layout.addLayout(ticker_input_layout)
        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

        self.timer = QTimer()
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.update_plot)

        self.populate_thumbnails()
        if self.config["tickers"]:
            self.ticker_list.setCurrentRow(0)

    def apply_tickers(self):
        tickers_str = self.ticker_input.text().strip()
        if tickers_str:
            self.config["tickers"] = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]
            save_config(CONFIG_PATH, self.config)
            self.populate_thumbnails(force_update=True)
            if self.config["tickers"]:
                self.ticker_list.setCurrentRow(0)

    def populate_thumbnails(self, force_update=False):
        self.ticker_list.clear()
        for ticker in self.config["tickers"]:
            item_widget = create_thumbnail_widget(ticker, self.config["timezone"], force_update)
            item = QListWidgetItem()
            item.setSizeHint(QSize(210, 160))
            self.ticker_list.addItem(item)
            self.ticker_list.setItemWidget(item, item_widget)

    def update_all_thumbnails(self):
        self.populate_thumbnails(force_update=True)

    def change_chart_type(self):
        self.config["chart_type"] = self.chart_type_group.checkedButton().text().lower()
        save_config(CONFIG_PATH, self.config)
        self.update_plot()

    def change_period(self):
        self.config["period"] = self.period_group.checkedButton().text()
        save_config(CONFIG_PATH, self.config)
        self.update_plot()

    def change_main_indicator(self):
        selected_indicators = [indicator for indicator, cb in self.main_indicator_group.items() if cb.isChecked()]
        self.config["main_indicator"] = selected_indicators
        save_config(CONFIG_PATH, self.config)
        self.update_plot()

    def change_sub_indicator(self):
        checked_button = self.sub_indicator_group.checkedButton()
        if checked_button:
            for key, label in self.sub_indicators.items():
                if checked_button.text() == label:
                    self.config["sub_indicator"] = key
                    save_config(CONFIG_PATH, self.config)
                    self.update_plot()
                    break

    def change_timezone(self, tz):
        self.config["timezone"] = tz
        save_config(CONFIG_PATH, self.config)
        self.populate_thumbnails(force_update=False)
        self.update_plot()

    def change_theme(self, theme):
        self.config["theme"] = theme
        save_config(CONFIG_PATH, self.config)
        QMessageBox.information(self, "Theme Changed", "Theme has been changed.\nPlease restart the application to apply it.")

    def get_selected_ticker(self):
        current_item = self.ticker_list.currentItem()
        if current_item:
            widget = self.ticker_list.itemWidget(current_item)
            return widget.layout().itemAt(0).widget().text()
        return self.config["tickers"][0]

    def format_change_summary(self, changes):
        periods = ["1D", "1W", "1M", "6M", "1Y"]
        parts = []
        for p, c in zip(periods, changes):
            if c is None:
                parts.append(f"{p}: <span style='color:#AAAAAA'>N/A</span>")
            else:
                color = "#FF6B6B" if c > 0 else "#4DA3FF"
                sign = "+" if c > 0 else ""
                parts.append(f"{p}: <span style='color:{color}'>{sign}{c:.2f}%</span>")
        return "   ".join(parts)

    def update_plot(self):
        ticker = self.get_selected_ticker()
        df = fetch_market_data(ticker, self.config["period"], self.config["timezone"])

        changes = calculate_price_changes(df)
        self.change_summary.setTextFormat(Qt.RichText)
        self.change_summary.setText(self.format_change_summary(changes))

        html = create_plot_html(
            df, ticker,
            self.config["chart_type"],
            self.config["theme"],
            self.config["main_indicator"],
            self.config["sub_indicator"]
        )
        self.web_view.setHtml(html)

    def search_news(self):
        ticker = self.get_selected_ticker()
        queries = build_search_queries(ticker)
        news = fetch_news_for_queries(queries, days=5)

        if not news:
            QMessageBox.information(self, "News", "No news found.")
            return

        dialog = NewsDialog(news, None, ticker)
        self.news_dialogs = getattr(self, "news_dialogs", [])
        dialog.destroyed.connect(lambda: self.news_dialogs.remove(dialog))
        self.news_dialogs.append(dialog)
        dialog.show()

    def toggle_auto_refresh(self, state):
        if state == 2:
            self.timer.start()
        else:
            self.timer.stop()
