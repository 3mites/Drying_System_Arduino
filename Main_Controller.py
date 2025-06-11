import sys
import time
import json
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot, QTimer, QIODevice
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo

from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow
from calculate_emc import MoistureEstimator


class SecondWindow(QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_SecondWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton_2.clicked.connect(self.go_to_third)
        self.ui.pushButton.clicked.connect(self.go_to_first)

    def go_to_third(self):
        self.first_window.temp_drying_window.show()
        self.close()

    def go_to_first(self):
        self.first_window.show()
        self.close()

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t1, t2, t3, t4, t_ave_first):
        self.ui.label.setText(f"{t1} °C")
        self.ui.label_6.setText(f"{t2} °C")
        self.ui.label_12.setText(f"{t3} °C")
        self.ui.label_11.setText(f"{t4} °C")
        self.ui.label_8.setText(f"Average: {t_ave_first} °C")


class ThirdWindow(QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_temp_drying)

    def go_to_temp_drying(self):
        self.first_window.temp_drying_window.show()
        self.close()

    @pyqtSlot(str, str, str)
    def update_humidity_labels(self, h1, h2, h_ave):
        self.ui.label_6.setText(f"{h1} %")
        self.ui.label_12.setText(f"{h2} %")
        self.ui.label_8.setText(f"Average: {h_ave} %")


class TempDryingWindow(QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_TempDryingWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_second)
        self.ui.pushButton_2.clicked.connect(self.go_to_third)

    def go_to_second(self):
        self.first_window.second_window.show()
        self.close()

    def go_to_third(self):
        self.first_window.third_window.show()
        self.close()

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        self.ui.label.setText(f"{t5} °C")
        self.ui.label_6.setText(f"{t6} °C")
        self.ui.label_12.setText(f"{t7} °C")
        self.ui.label_11.setText(f"{t8} °C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")


class FirstWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)

        self.fuzzy_timer = QTimer(self)
        self.fuzzy_timer.timeout.connect(self.run_fuzzy_controller)
        self.fuzzy_timer.start(300000)

        self.last_valid_drying_seconds = None

        self.serial = QSerialPort(self)
        self.serial.setPortName("/dev/ttyUSB0")
        self.serial.setBaudRate(QSerialPort.Baud9600)
        self.serial.readyRead.connect(self.read_serial_data)
        self.serial.open(QIODevice.ReadOnly)
        self.buffer = b""

        self.ui.pushButton_2.clicked.connect(self.go_to_second)

    def run_fuzzy_controller(self):
        try:
            fuzzy = TemperatureFuzzyController()
            adj = fuzzy.temperature_adjustment(self.t_ave_first, self.h_ave)
            if self.serial.isOpen():
                self.serial.write(f"ADJ:{adj}\n".encode())
        except Exception as e:
            print("Fuzzy error:", e)

    def read_serial_data(self):
        self.buffer += self.serial.readAll().data()
        if b"pwm_2:" in self.buffer:
            line = self.buffer.decode(errors='ignore')
            self.buffer = b""
            parts = line.strip().split()
            parsed = {}
            for part in parts:
                if ":" in part:
                    k, v = part.split(":", 1)
                    parsed[k] = v

            try:
                data = {
                    'T': parsed.get("t_ave_2nd", "0"),
                    'H': parsed.get("h_ave", "0"),
                    'pwm2': parsed.get("pwm_2", "0"),
                    'pwm1': parsed.get("pwm_1", "0"),
                    'temps': [parsed.get(f"T{i+1}", "0") for i in range(4)],
                    'dry_temps': [parsed.get(f"T{i+5}", "0") for i in range(4)],
                    'hum': [parsed.get("H1", "0"), parsed.get("H2", "0")],
                    't_ave_first': parsed.get("t_ave_first", "0"),
                }
                self.on_packet(data)
            except Exception as e:
                print("Parsing error:", e)

    def on_packet(self, data):
        self.h_ave = data['H']
        self.t_ave_first = data['t_ave_first']

        QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", Qt.QueuedConnection,
            Q_ARG(str, data['temps'][0]), Q_ARG(str, data['temps'][1]),
            Q_ARG(str, data['temps'][2]), Q_ARG(str, data['temps'][3]),
            Q_ARG(str, self.t_ave_first))

        QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", Qt.QueuedConnection,
            Q_ARG(str, data['dry_temps'][0]), Q_ARG(str, data['dry_temps'][1]),
            Q_ARG(str, data['dry_temps'][2]), Q_ARG(str, data['dry_temps'][3]),
            Q_ARG(str, data['T']))

        QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", Qt.QueuedConnection,
            Q_ARG(str, data['hum'][0]), Q_ARG(str, data['hum'][1]), Q_ARG(str, self.h_ave))

        QMetaObject.invokeMethod(self, "update_labels", Qt.QueuedConnection,
            Q_ARG(str, data['T']), Q_ARG(str, self.h_ave),
            Q_ARG(str, data['pwm2']), Q_ARG(str, data['pwm1']))

    @pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        self.ui.label.setText(f"{t_ave_2nd} °C")
        self.ui.label_6.setText(f"{h_ave} %")
        self.ui.label_12.setText(pwm_2)
        self.ui.label_11.setText(pwm_1)
        try:
            estimator = MoistureEstimator(float(t_ave_2nd), float(h_ave))
            sec = estimator.get_drying_time_seconds()
            self.last_valid_drying_seconds = sec
            self.ui.label_8.setText(f"Dry Time: {sec} s")
        except:
            self.ui.label_8.setText(f"Dry Time: {self.last_valid_drying_seconds or 'Error'} s")

    def go_to_second(self):
        self.second_window.show()
        self.hide()

    def closeEvent(self, event):
        if self.serial.isOpen():
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = FirstWindow()
    main.show()
    sys.exit(app.exec_())
