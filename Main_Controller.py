import sys
import serial
import threading
import time
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot, QTimer
from PyQt5 import QtWidgets
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
        QTimer.singleShot(0, self.first_window.temp_drying_window.show)
        QTimer.singleShot(0, self.close)

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
        QTimer.singleShot(0, self.first_window.temp_drying_window.show)
        QTimer.singleShot(0, self.close)

    def go_to_first(self):
        QTimer.singleShot(0, self.first_window.show)
        QTimer.singleShot(0, self.close)

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t1, t2, t3, t4, t_ave_first):
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
        QTimer.singleShot(0, self.first_window.second_window.show)
        QTimer.singleShot(0, self.close)

    def go_to_third(self):
        QTimer.singleShot(0, self.first_window.third_window.show)
        QTimer.singleShot(0, self.close)

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        self.ui.label.setText(f"{t5} °C")
        self.ui.label_6.setText(f"{t6} °C")
        self.ui.label_12.setText(f"{t7} °C")
        self.ui.label_11.setText(f"{t8} °C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")

class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)

        self.fuzzy_timer = QTimer(self)
        self.fuzzy_timer.timeout.connect(self.run_fuzzy_controller)
        self.fuzzy_timer.start(300000)

        self.last_valid_drying_seconds = None
        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.data_lock = threading.Lock()
        self.latest_data = None

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_latest_data)
        self.process_timer.start(1000)

    def go_to_second(self):
        QTimer.singleShot(0, self.second_window.show)
        QTimer.singleShot(0, self.hide)

    def run_fuzzy_controller(self):
        try:
            fuzzy_control = TemperatureFuzzyController()
            adjustment = fuzzy_control.temperature_adjustment(self.t_ave_first, self.h_ave)
            if hasattr(self, 'ser') and self.ser.is_open:
                self.ser.write(f"ADJ:{adjustment}\n".encode())
        except Exception as e:
            print("Fuzzy controller error:", e)

    def read_serial_data(self):
        try:
            self.ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            buffer = ""
            while True:
                line = self.ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                buffer += line + " "
                if "pwm_2:" in buffer:
                    with self.data_lock:
                        self.latest_data = buffer.strip()
                    buffer = ""
        except serial.SerialException as e:
            print("Serial connection failed:", e)

    def process_latest_data(self):
        with self.data_lock:
            data = self.latest_data
            self.latest_data = None

        if not data:
            return

        try:
            parts = data.strip().split()
            if len(parts) < 15:
                return

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
            self.t_ave_first = parts[10].split("t_ave_first:")[1]
            t_ave_2nd = parts[11].split("t_ave_2nd:")[1]
            self.h_ave = parts[12].split("h_ave:")[1]
            pwm_1 = parts[13].split("pwm_1:")[1]
            pwm_2 = parts[14].split("pwm_2:")[1]

            self.second_window.update_temperature_labels(t1, t2, t3, t4, self.t_ave_first)
            self.temp_drying_window.update_temperature_labels(t5, t6, t7, t8, t_ave_2nd)
            self.third_window.update_humidity_labels(h1, h2, self.h_ave)
            self.update_labels(t_ave_2nd, self.h_ave, pwm_2, pwm_1)

        except Exception as e:
            print("Parsing/UI update error:", e)

    @pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        self.ui.label.setText(f"{t_ave_2nd} °C")
        self.ui.label_6.setText(f"{h_ave} %")
        self.ui.label_12.setText(pwm_2)
        self.ui.label_11.setText(pwm_1)
        try:
            estimator = MoistureEstimator(float(t_ave_2nd), float(h_ave))
            drying_seconds = estimator.get_drying_time_seconds()
            self.last_valid_drying_seconds = drying_seconds
            self.ui.label_8.setText(f"Dry Time: {drying_seconds} s")
        except:
            fallback = self.last_valid_drying_seconds or "Error"
            self.ui.label_8.setText(f"Dry Time: {fallback} s")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = FirstWindow()
    main_window.show()
    sys.exit(app.exec_())
