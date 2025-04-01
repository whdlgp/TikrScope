
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QDialog, QFrame
)
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices, QFont

class NewsItemWidget(QWidget):
    def __init__(self, published, title, link):
        super().__init__()

        time_label = QLabel(published)
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setFont(QFont("", weight=QFont.Bold))

        open_button = QPushButton("Open")
        open_button.setMinimumWidth(60)
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link)))

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(open_button)

        inner_layout = QVBoxLayout()
        inner_layout.addWidget(time_label)
        inner_layout.addWidget(title_label)
        inner_layout.addLayout(button_layout)
        inner_layout.setSpacing(6)
        inner_layout.setContentsMargins(12, 12, 12, 12)

        frame = QFrame()
        frame.setLayout(inner_layout)
        frame.setFrameShape(QFrame.StyledPanel)

        outer_layout = QVBoxLayout()
        outer_layout.addWidget(frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer_layout)

class NewsDialog(QDialog):
    def __init__(self, news_items, parent=None, ticker=""):
        super().__init__(parent)
        self.setWindowTitle(f"News: {ticker}")
        self.setMinimumSize(750, 600)

        self.list_widget = QListWidget()
        self.list_widget.setSpacing(8)

        for item in news_items:
            published = item["published"].strftime("%Y-%m-%d %H:%M")
            title = item["title"]
            link = item["link"]

            widget = NewsItemWidget(published, title, link)
            list_item = QListWidgetItem()
            list_item.setSizeHint(widget.sizeHint())

            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, widget)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)
