import sys
import serial
import threading
import pandas as pd
import time
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow
from calculate_emc import MoistureEstimator


class ThirdWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)

        self.first_window = first_window
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton.setEnabled(True)

        self.ui.pushButton.clicked.connect(self.go_to_temp_drying)

    def go_to_temp_drying(self):
        if self.first_window.temp_drying_window is None:
            self.first_window.temp_drying_window = TempDryingWindow(self.first_window)
        self.first_window.temp_drying_window.show()
        self.close()

    @pyqtSlot(str, str, str)
    def update_humidity_labels(self, h1, h2, h_ave):
        self.ui.label_6.setText(f"{h1} %")
        self.ui.label_12.setText(f"{h2} %")
        self.ui.label_8.setText(f"Average: {h_ave} %")


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
        if self.first_window.temp_drying_window is None:
            self.first_window.temp_drying_window = TempDryingWindow(self.first_window)
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


class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        self.fuzzy_timer = QtCore.QTimer(self)
        self.fuzzy_timer.timeout.connect(self.run_fuzzy_controller)
        self.fuzzy_timer.start(300000)

        self.last_valid_drying_seconds = None

        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)

        self.data_log = []
        self.excel_file = "serial_readings.xlsx"

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def run_fuzzy_controller(self):
        try:
            print("Running TemperatureFuzzyController...")
            fuzzy_control = TemperatureFuzzyController()
            adjustment = fuzzy_control.temperature_adjustment(self.t_ave_first, self.h_ave)
            if hasattr(self, 'ser') and self.ser.is_open:
                message = f"ADJ:{adjustment}\n"
                self.ser.write(message.encode())
                print("Sent to Arduino:", message)
        except Exception as e:
            print("Error running TemperatureFuzzyController:", e)

    def read_serial_data(self):
        try:
            ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            self.ser = ser
            buffer = ""
            print("Serial port opened.")
            while True:
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                buffer += line + " "
                if "pwm_2:" in buffer:
                    parts = buffer.strip().split()
                    buffer = ""
                    if len(parts) < 15:
                        continue
                    try:
                        t1 = parts[0].split("T1:")[1]
                        t2 = parts[1].split("T2:")[1]
                        t3 = parts[2].split("T3:")[1]
                        t4 = parts[3].split("T4:")[1]
                        t5 = parts[4].split("T5:")[1]
                        t6 = parts[5].split("T6:")[1]
                        t7 = parts[6].split("T7:")[1]
                        t8 = parts[7].split("T8:")[1]
                        h1 = parts[8].split("H1:")[1]
                        h2 = parts[9].split("H2:")[1]
                        t_ave_first = parts[10].split("t_ave_first:")[1]
                        t_ave_2nd = parts[11].split("t_ave_2nd:")[1]
                        h_ave = parts[12].split("h_ave:")[1]
                        pwm_1 = parts[13].split("pwm_1:")[1]
                        pwm_2 = parts[14].split("pwm_2:")[1]

                        self.t_ave_first = t_ave_first
                        self.h_ave = h_ave

                        print(f"\nUpdating GUI with:\nT1-T4: {t1} {t2} {t3} {t4}\nT5-T8: {t5} {t6} {t7} {t8}\nHumidity: {h1} {h2} Avg: {h_ave}\nPWM: {pwm_1} {pwm_2}\nT avg 1: {t_ave_first} T avg 2: {t_ave_2nd}")

                        QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", Qt.QueuedConnection,
                                                 Q_ARG(str, t1), Q_ARG(str, t2), Q_ARG(str, t3), Q_ARG(str, t4), Q_ARG(str, self.t_ave_first))

                        QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", Qt.QueuedConnection,
                                                 Q_ARG(str, t5), Q_ARG(str, t6), Q_ARG(str, t7), Q_ARG(str, t8), Q_ARG(str, t_ave_2nd))

                        QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", Qt.QueuedConnection,
                                                 Q_ARG(str, h1), Q_ARG(str, h2), Q_ARG(str, self.h_ave))

                        QMetaObject.invokeMethod(self, "update_labels", Qt.QueuedConnection,
                                                 Q_ARG(str, t_ave_2nd), Q_ARG(str, h_ave), Q_ARG(str, pwm_2), Q_ARG(str, pwm_1))

                        time.sleep(0.05)

                    except Exception as e:
                        print("Error parsing values:", e)
        except serial.SerialException as e:
            print("Serial connection failed:", e)

    @pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        self.ui.label.setText(f"{t_ave_2nd} °C")
        self.ui.label_6.setText(f"{h_ave} %")
        self.ui.label_12.setText(f"{pwm_2}")
        self.ui.label_11.setText(f"{pwm_1}")
        try:
            temperature = float(t_ave_2nd)
            humidity = float(h_ave)
            estimator = MoistureEstimator(temperature, humidity)
            drying_seconds = estimator.get_drying_time_seconds()
            self.last_valid_drying_seconds = drying_seconds
            self.ui.label_8.setText(f"Dry Time: {drying_seconds} s")
        except Exception as e:
            print("Error estimating drying time:", e)
            if self.last_valid_drying_seconds is not None:
                self.ui.label_8.setText(f"Dry Time: {self.last_valid_drying_seconds} s")
            else:
                self.ui.label_8.setText("Dry Time: Error")

    def go_to_second(self):
        self.second_window.show()
        self.hide()


class TempDryingWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_TempDryingWindow()
        self.ui.setupUi(self)
        self.first_window = first_window

        self.ui.pushButton.setEnabled(True)
        self.ui.pushButton_2.setEnabled(True)

        self.ui.pushButton.clicked.connect(self.go_to_second)
        self.ui.pushButton_2.clicked.connect(self.go_to_third)

    def go_to_second(self):
        if self.first_window.second_window is None:
            self.first_window.second_window = SecondWindow(self.first_window)
        self.first_window.second_window.show()
        self.close()

    def go_to_third(self):
        if self.first_window.third_window is None:
            self.first_window.third_window = ThirdWindow(self.first_window)
        self.first_window.third_window.show()
        self.close()

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        self.ui.label.setText(f"{t5} °C")
        self.ui.label_6.setText(f"{t6} °C")
        self.ui.label_12.setText(f"{t7} °C")
        self.ui.label_11.setText(f"{t8} °C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    start_window = FirstWindow()
    start_window.show()
    sys.exit(app.exec_())
