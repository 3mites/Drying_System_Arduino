import sys
from PyQt5 import QtWidgets

from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow

class ThirdWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)

        # Disable NEXT (last window)
        self.ui.pushButton_2.setEnabled(False)

        # Enable PREV to go to SecondWindow
        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton.clicked.connect(self.go_to_second)

    def go_to_second(self):
        self.second_window = SecondWindow()
        self.second_window.show()
        self.close()

class SecondWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_SecondWindow()
        self.ui.setupUi(self)

        # Enable both buttons
        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(True)

        self.ui.pushButton_2.clicked.connect(self.go_to_third)
        self.ui.pushButton.clicked.connect(self.go_to_first)

    def go_to_third(self):
        self.third_window = ThirdWindow()
        self.third_window.show()
        self.close()

    def go_to_first(self):
        self.first_window = FirstWindow()
        self.first_window.show()
        self.close()

class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        # Enable NEXT, Disable PREV (first window)
        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)

        self.ui.pushButton_2.clicked.connect(self.go_to_second)

    def go_to_second(self):
        self.second_window = SecondWindow()
        self.second_window.show()
        self.close()

app = QtWidgets.QApplication(sys.argv)
main_window = FirstWindow()
main_window.show()
sys.exit(app.exec_())
