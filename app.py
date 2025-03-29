import sys
from PyQt5.QtWidgets import QApplication, QStyleFactory
from ui import StockApp
from qt_material import apply_stylesheet
from data import CONFIG_PATH, load_config

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyle(QStyleFactory.create("Fusion"))

    config = load_config(CONFIG_PATH)

    apply_stylesheet(app, theme=config.get("theme", "dark_teal.xml"))

    window = StockApp()
    window.show()

    sys.exit(app.exec_())