import sys
import serial
import threading
import pandas as pd
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal
from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display_button import Ui_MainWindow as Ui_StartWindow
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow
from calculate_emc import MoistureEstimator


class StartWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_StartWindow()
        self.ui.setupUi(self)
        self.first_window = None
        self.ui.pushButton.clicked.connect(self.open_first_window)

    def open_first_window(self):
        if self.first_window is None:
            self.first_window = FirstWindow()
        self.first_window.show()
        self.close()


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
        self.first_window.temp_drying_window.show()
        self.close()

    @QtCore.pyqtSlot(str, str, str)
    def update_humidity_labels(self, h1, h2, h_ave):
        print("Updating ThirdWindow labels:", h1, h2, h_ave)
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
        self.first_window.temp_drying_window.show()
        self.close()

    def go_to_first(self):
        self.first_window.show()
        self.close()

    @QtCore.pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t1, t2, t3, t4, t_ave_first):
        print("Updating SecondWindow labels:", t1, t2, t3, t4, t_ave_first)
        self.ui.label.setText(f"{t1} °C")
        self.ui.label_6.setText(f"{t2} °C")
        self.ui.label_12.setText(f"{t3} °C")
        self.ui.label_11.setText(f"{t4} °C")
        self.ui.label_8.setText(f"Average: {t_ave_first} °C")


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
        self.first_window.second_window.show()
        self.close()

    def go_to_third(self):
        self.first_window.third_window.show()
        self.close()

    @QtCore.pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        print("Updating TempDryingWindow labels:", t5, t6, t7, t8, t_ave_2nd)
        self.ui.label.setText(f"{t5} °C")
        self.ui.label_6.setText(f"{t6} °C")
        self.ui.label_12.setText(f"{t7} °C")
        self.ui.label_11.setText(f"{t8} °C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")


class FirstWindow(QtWidgets.QMainWindow):
    update_labels_signal = pyqtSignal(str, str, str, str)
    update_temp_labels_signal = pyqtSignal(str, str, str, str, str)
    update_drying_labels_signal = pyqtSignal(str, str, str, str, str)
    update_humidity_labels_signal = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)

        self.fuzzy_timer = QtCore.QTimer(self)
        self.fuzzy_timer.timeout.connect(self.run_fuzzy_controller)
        self.fuzzy_timer.start(300000)

        self.last_valid_drying_seconds = None
        self.data_log = []
        self.excel_file = "serial_readings.xlsx"

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.update_labels_signal.connect(self.update_labels)
        self.update_temp_labels_signal.connect(self.second_window.update_temperature_labels)
        self.update_drying_labels_signal.connect(self.temp_drying_window.update_temperature_labels)
        self.update_humidity_labels_signal.connect(self.third_window.update_humidity_labels)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def run_fuzzy_controller(self):
        try:
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
            self.ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            buffer = ""
            while True:
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                print("Received line:", line)
                buffer += line + " "
                if "pwm_2:" in buffer:
                    parts = buffer.strip().split()
                    buffer = ""
                    if len(parts) < 16:
                        continue
                    try:
                        t0 = parts[0].split("T0:")[1]
                        t1 = parts[1].split("T1:")[1]
                        t2 = parts[2].split("T2:")[1]
                        t3 = parts[3].split("T3:")[1]
                        t4 = parts[4].split("T4:")[1]
                        t5 = parts[5].split("T5:")[1]
                        t6 = parts[6].split("T6:")[1]
                        t7 = parts[7].split("T7:")[1]
                        t8 = parts[8].split("T8:")[1]
                        h1 = parts[9].split("H1:")[1]
                        h2 = parts[10].split("H2:")[1]
                        t_ave_first = parts[11].split("t_ave_first:")[1]
                        t_ave_2nd = parts[12].split("t_ave_2nd:")[1]
                        h_ave = parts[13].split("h_ave:")[1]
                        pwm_1 = parts[14].split("pwm_1:")[1]
                        pwm_2 = parts[15].split("pwm_2:")[1]

                        self.update_labels_signal.emit(t_ave_2nd, h_ave, pwm_2, pwm_1)
                        self.update_temp_labels_signal.emit(t1, t2, t3, t4, t_ave_first)
                        self.update_drying_labels_signal.emit(t5, t6, t7, t8, t_ave_2nd)
                        self.update_humidity_labels_signal.emit(h1, h2, h_ave)

                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.data_log.append({
                            "Timestamp": timestamp, "T0": t0, "T1": t1, "T2": t2, "T3": t3,
                            "T4": t4, "T5": t5, "T6": t6, "T7": t7, "T8": t8,
                            "H1": h1, "H2": h2, "T_Ave_First": t_ave_first,
                            "T_Ave_Second": t_ave_2nd, "H_Ave": h_ave,
                            "PWM_1": pwm_1, "PWM_2": pwm_2
                        })
                        pd.DataFrame(self.data_log).to_excel(self.excel_file, index=False, engine='openpyxl')

                        QtCore.QThread.sleep(1)
                    except Exception as e:
                        print("Error parsing serial data:", e)
        except serial.SerialException as e:
            print("Serial error:", e)

    @QtCore.pyqtSlot(str, str, str, str)
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


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    start_window = StartWindow()
    start_window.show()
    sys.exit(app.exec_())
