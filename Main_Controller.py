import sys
import serial
import threading
import pandas as pd
import platform
import time
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
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
        self.first_window = FirstWindow()
        self.ui.pushButton.clicked.connect(self.open_first_window)

    def open_first_window(self):
        self.first_window.show()
        self.close()


class ThirdWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_temp_drying)

    def go_to_temp_drying(self):
        self.close()
        self.first_window.temp_drying_window.show()

    @QtCore.pyqtSlot(str, str, str)
    def update_humidity_labels(self, h1, h2, h_ave):
        try:
            self.ui.label_6.setText(f"{h1} %")
            self.ui.label_12.setText(f"{h2} %")
            self.ui.label_8.setText(f"Average: {h_ave} %")
        except Exception as e:
            print("Humidity label update error:", e)


class SecondWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_SecondWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_first)
        self.ui.pushButton_2.clicked.connect(self.go_to_third)

    def go_to_third(self):
        self.close()
        self.first_window.third_window.show()

    def go_to_first(self):
        self.close()
        self.first_window.show()

    @QtCore.pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t1, t2, t3, t4, t_ave_first):
        try:
            self.ui.label.setText(f"{t1} °C")
            self.ui.label_6.setText(f"{t2} °C")
            self.ui.label_12.setText(f"{t3} °C")
            self.ui.label_11.setText(f"{t4} °C")
            self.ui.label_8.setText(f"Average: {t_ave_first} °C")
        except Exception as e:
            print("Second window temperature update error:", e)


class TempDryingWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_TempDryingWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_second)
        self.ui.pushButton_2.clicked.connect(self.go_to_third)

    def go_to_second(self):
        self.close()
        self.first_window.second_window.show()

    def go_to_third(self):
        self.close()
        self.first_window.third_window.show()

    @QtCore.pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        try:
            self.ui.label.setText(f"{t5} °C")
            self.ui.label_6.setText(f"{t6} °C")
            self.ui.label_12.setText(f"{t7} °C")
            self.ui.label_11.setText(f"{t8} °C")
            self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")
        except Exception as e:
            print("Drying window temperature update error:", e)


class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)
        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)
        self.fuzzy_timer = QtCore.QTimer(self)
        self.fuzzy_timer.timeout.connect(self.run_fuzzy_controller)
        self.fuzzy_timer.start(300000)
        self.last_valid_drying_seconds = None
        self.data_log = []
        self.excel_file = "serial_readings.xlsx"
        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def closeEvent(self, event):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
        event.accept()

    def run_fuzzy_controller(self):
        try:
            fuzzy_control = TemperatureFuzzyController()
            adjustment = fuzzy_control.temperature_adjustment(self.t_ave_first, self.h_ave)
            if hasattr(self, 'ser') and self.ser.is_open:
                self.ser.write(f"ADJ:{adjustment}\n".encode())
        except Exception as e:
            print("Error running fuzzy controller:", e)

    def read_serial_data(self):
        try:
            port = 'COM3' if platform.system() == 'Windows' else '/dev/ttyUSB0'
            self.ser = serial.Serial(port, 9600, timeout=1)
            buffer = ""
            while True:
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                buffer += line + " "
                if "pwm_2:" in buffer:
                    parts = buffer.strip().split()
                    buffer = ""
                    data = {k: v for k, v in (part.split(":", 1) for part in parts if ":" in part)}
                    required = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
                                "H1", "H2", "t_ave_first", "t_ave_2nd", "h_ave", "pwm_1", "pwm_2"]
                    if not all(k in data for k in required):
                        continue
                    t0, t1, t2, t3, t4 = data["T0"], data["T1"], data["T2"], data["T3"], data["T4"]
                    t5, t6, t7, t8 = data["T5"], data["T6"], data["T7"], data["T8"]
                    h1, h2 = data["H1"], data["H2"]
                    self.t_ave_first = data["t_ave_first"]
                    t_ave_2nd = data["t_ave_2nd"]
                    self.h_ave = data["h_ave"]
                    pwm_1, pwm_2 = data["pwm_1"], data["pwm_2"]

                    QtCore.QMetaObject.invokeMethod(self, "update_labels", QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, t_ave_2nd), QtCore.Q_ARG(str, self.h_ave),
                        QtCore.Q_ARG(str, pwm_2), QtCore.Q_ARG(str, pwm_1))

                    if self.second_window.isVisible():
                        QtCore.QMetaObject.invokeMethod(self.second_window, "update_temperature_labels",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, t1), QtCore.Q_ARG(str, t2),
                            QtCore.Q_ARG(str, t3), QtCore.Q_ARG(str, t4),
                            QtCore.Q_ARG(str, self.t_ave_first))

                    if self.temp_drying_window.isVisible():
                        QtCore.QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, t5), QtCore.Q_ARG(str, t6),
                            QtCore.Q_ARG(str, t7), QtCore.Q_ARG(str, t8),
                            QtCore.Q_ARG(str, t_ave_2nd))

                    if self.third_window.isVisible():
                        QtCore.QMetaObject.invokeMethod(self.third_window, "update_humidity_labels",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, h1), QtCore.Q_ARG(str, h2),
                            QtCore.Q_ARG(str, self.h_ave))

                    self.data_log.append({
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "T0": t0, "T1": t1, "T2": t2, "T3": t3, "T4": t4,
                        "T5": t5, "T6": t6, "T7": t7, "T8": t8,
                        "H1": h1, "H2": h2, "T_Ave_First": self.t_ave_first,
                        "T_Ave_Second": t_ave_2nd, "H_Ave": self.h_ave,
                        "PWM_1": pwm_1, "PWM_2": pwm_2
                    })

                    if len(self.data_log) % 10 == 0:
                        pd.DataFrame(self.data_log).to_excel(self.excel_file, index=False, engine='openpyxl')
                        self.data_log.clear()

                    time.sleep(1)
        except serial.SerialException as e:
            print("Serial error:", e)

    @QtCore.pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        try:
            self.ui.label.setText(f"{t_ave_2nd} °C")
            self.ui.label_6.setText(f"{h_ave} %")
            self.ui.label_12.setText(f"{pwm_2}")
            self.ui.label_11.setText(f"{pwm_1}")
            estimator = MoistureEstimator(float(t_ave_2nd), float(h_ave))
            drying_seconds = estimator.get_drying_time_seconds()
            self.last_valid_drying_seconds = drying_seconds
            self.ui.label_8.setText(f"Dry Time: {drying_seconds} s")
        except Exception as e:
            print("Dry time error:", e)
            if self.last_valid_drying_seconds is not None:
                self.ui.label_8.setText(f"Dry Time: {self.last_valid_drying_seconds} s")
            else:
                self.ui.label_8.setText("Dry Time: Error")

    def go_to_second(self):
        self.hide()
        self.second_window.show()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    start_window = StartWindow()
    start_window.show()
    sys.exit(app.exec_())
