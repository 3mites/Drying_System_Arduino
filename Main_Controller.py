import sys
import serial
import threading
import pandas as pd
import serial.tools.list_ports
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

    def resize_to_fit_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size()
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))

    def center_window(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    @QtCore.pyqtSlot(str, str, str)
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

    def resize_to_fit_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size()
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))

    def center_window(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def go_to_third(self):
        if self.first_window.temp_drying_window is None:
            self.first_window.temp_drying_window = TempDryingWindow(self.first_window)
        self.first_window.temp_drying_window.show()
        self.close()

    def go_to_first(self):
        self.first_window.show()
        self.close()

    @QtCore.pyqtSlot(str, str, str, str, str)
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
        self.last_valid_drying_seconds = None

        self.second_window = None
        self.third_window = None
        self.temp_drying_window = None
        self.data_log = []
        self.excel_file = "serial_readings.xlsx"

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def resize_to_fit_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size()
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))

    def center_window(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def find_arduino_port(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if ('Arduino' in port.description) or ('ttyACM' in port.device) or ('ttyUSB' in port.device):
                return port.device
        return None

    def read_serial_data(self):
        retries = 0
        arduino_port = self.find_arduino_port()
        self.arduino_port = arduino_port

        QtCore.QMetaObject.invokeMethod(self, "show_waiting_message", QtCore.Qt.QueuedConnection)

        while self.arduino_port is None and retries < 30:
            QtCore.QThread.sleep(2)
            retries += 1
            self.arduino_port = self.find_arduino_port()

        QtCore.QMetaObject.invokeMethod(self, "handle_connection_result", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def show_waiting_message(self):
        self.msg_box = QtWidgets.QMessageBox(self)
        self.msg_box.setWindowTitle("Connecting")
        self.msg_box.setText("Waiting for Arduino connection...")
        self.msg_box.setStandardButtons(QtWidgets.QMessageBox.NoButton)
        self.msg_box.show()

    @QtCore.pyqtSlot()
    def handle_connection_result(self):
        if hasattr(self, 'msg_box'):
            self.msg_box.close()

        if self.arduino_port is None:
            QtWidgets.QMessageBox.critical(self, "Error", "Arduino not found after 60 seconds.")
        else:
            self.start_serial_reading(self.arduino_port)

    def start_serial_reading(self, port):
        try:
            ser = serial.Serial(port, 9600, timeout=1)
            buffer = ""
            while True:
                line = ser.readline().decode(errors='ignore').strip()
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

                        QtCore.QMetaObject.invokeMethod(self, "update_labels", QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, t_ave_2nd), QtCore.Q_ARG(str, h_ave),
                            QtCore.Q_ARG(str, pwm_2), QtCore.Q_ARG(str, pwm_1))

                        if self.second_window and self.second_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, t1), QtCore.Q_ARG(str, t2),
                                QtCore.Q_ARG(str, t3), QtCore.Q_ARG(str, t4),
                                QtCore.Q_ARG(str, t_ave_first))

                        if self.temp_drying_window and self.temp_drying_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, t5), QtCore.Q_ARG(str, t6),
                                QtCore.Q_ARG(str, t7), QtCore.Q_ARG(str, t8),
                                QtCore.Q_ARG(str, t_ave_2nd))

                        if self.third_window and self.third_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, h1), QtCore.Q_ARG(str, h2),
                                QtCore.Q_ARG(str, h_ave))

                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.data_log.append({
                            "Timestamp": timestamp, "T1": t1, "T2": t2, "T3": t3, "T4": t4,
                            "T5": t5, "T6": t6, "T7": t7, "T8": t8, "H1": h1, "H2": h2,
                            "T_Ave_First": t_ave_first, "T_Ave_Second": t_ave_2nd,
                            "H_Ave": h_ave, "PWM_1": pwm_1, "PWM_2": pwm_2
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
            if self.last_valid_drying_seconds:
                self.ui.label_8.setText(f"Dry Time: {self.last_valid_drying_seconds} s")
            else:
                self.ui.label_8.setText("Dry Time: Error")

    def go_to_second(self):
        if self.second_window is None:
            self.second_window = SecondWindow(self)
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

    def resize_to_fit_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.availableGeometry().size()
        self.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))

    def center_window(self):
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

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

    @QtCore.pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        self.ui.label.setText(f"{t5} °C")
        self.ui.label_6.setText(f"{t6} °C")
        self.ui.label_12.setText(f"{t7} °C")
        self.ui.label_11.setText(f"{t8} °C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} °C")


app = QtWidgets.QApplication(sys.argv)
main_window = FirstWindow()
main_window.show()
sys.exit(app.exec_())
