import sys
import serial
import threading
from PyQt5 import QtWidgets, QtCore

from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow

class ThirdWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)

        self.first_window = first_window

        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton.setEnabled(True)

        self.ui.pushButton.clicked.connect(self.go_to_second)

    def go_to_second(self):
        self.second_window = SecondWindow(self.first_window)
        self.second_window.show()
        self.close()


class SecondWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_SecondWindow()
        self.ui.setupUi(self)

        self.first_window = first_window

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(True)

        self.ui.pushButton_2.clicked.connect(self.go_to_third)
        self.ui.pushButton.clicked.connect(self.go_to_first)

    def go_to_third(self):
        self.third_window = ThirdWindow(self.first_window)
        self.third_window.show()
        self.close()

    def go_to_first(self):
        self.first_window.show()
        self.close()

class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)

        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def read_serial_data(self):
        try:
            ser = serial.Serial('COM5', 9600, timeout=1)
            while True:
                line = ser.readline().decode().strip()
                if line.startswith("T:") and "H:" in line:
                    try:
                        temp = line.split("T:")[1].split(" H:")[0].strip()
                        hum = line.split("H:")[1].strip()
                        QtCore.QMetaObject.invokeMethod(
                            self,
                            "update_labels",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, temp),
                            QtCore.Q_ARG(str, hum)
                        )
                    except Exception as e:
                        print("Parse error:", e)
        except serial.SerialException as e:
            print("Serial error:", e)

    @QtCore.pyqtSlot(str, str)
    def update_labels(self, temperature, humidity):
        self.ui.label.setText(f"{temperature} °C")
        self.ui.label_6.setText(f"{humidity} %")

    def go_to_second(self):
        self.second_window = SecondWindow(self)
        self.second_window.show()
        self.hide()  # Hide instead of close



app = QtWidgets.QApplication(sys.argv)
main_window = FirstWindow()
main_window.show()
sys.exit(app.exec_())
