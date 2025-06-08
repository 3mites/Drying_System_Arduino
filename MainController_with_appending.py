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


def center_and_resize(window):
    screen = QtWidgets.QApplication.primaryScreen()
    screen_size = screen.availableGeometry()
    window.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))
    frame_geom = window.frameGeometry()
    frame_geom.moveCenter(screen_size.center())
    window.move(frame_geom.topLeft())


class ThirdWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_ThirdWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton_2.setEnabled(False)
        self.ui.pushButton.clicked.connect(self.go_to_temp_drying)
        center_and_resize(self)

    def go_to_temp_drying(self):
        if self.first_window.temp_drying_window is None:
            self.first_window.temp_drying_window = TempDryingWindow(self.first_window)
        self.first_window.temp_drying_window.show()
        self.close()

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
        self.ui.pushButton_2.clicked.connect(self.go_to_third)
        self.ui.pushButton.clicked.connect(self.go_to_first)
        center_and_resize(self)

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


class TempDryingWindow(QtWidgets.QMainWindow):
    def __init__(self, first_window):
        super().__init__()
        self.ui = Ui_TempDryingWindow()
        self.ui.setupUi(self)
        self.first_window = first_window
        self.ui.pushButton.clicked.connect(self.go_to_second)
        self.ui.pushButton_2.clicked.connect(self.go_to_third)
        center_and_resize(self)

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


class FirstWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_FirstWindow()
        self.ui.setupUi(self)
        self.last_valid_drying_seconds = None
        self.data_log = []
        self.excel_file = "serial_readings.xlsx"

        self.second_window = None
        self.third_window = None
        self.temp_drying_window = None

        self.ui.pushButton.clicked.connect(self.do_nothing)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)
        center_and_resize(self)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def do_nothing(self):
        pass

    def go_to_second(self):
        if self.second_window is None:
            self.second_window = SecondWindow(self)
        self.second_window.show()
        self.hide()

    def find_arduino_port(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if 'Arduino' in port.description or 'ttyACM' in port.device or 'ttyUSB' in port.device:
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
                        # Extract sensor values
                        readings = {k: v.split(":")[1] for k, v in zip(
                            ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "H1", "H2", "T_Ave_First", "T_Ave_Second", "H_Ave", "PWM_1", "PWM_2"],
                            parts[:15]
                        )}
                        # Update GUI
                        QtCore.QMetaObject.invokeMethod(self, "update_labels", QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, readings["T_Ave_Second"]),
                            QtCore.Q_ARG(str, readings["H_Ave"]),
                            QtCore.Q_ARG(str, readings["PWM_2"]),
                            QtCore.Q_ARG(str, readings["PWM_1"]))

                        if self.second_window and self.second_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, readings["T1"]), QtCore.Q_ARG(str, readings["T2"]),
                                QtCore.Q_ARG(str, readings["T3"]), QtCore.Q_ARG(str, readings["T4"]),
                                QtCore.Q_ARG(str, readings["T_Ave_First"]))

                        if self.temp_drying_window and self.temp_drying_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, readings["T5"]), QtCore.Q_ARG(str, readings["T6"]),
                                QtCore.Q_ARG(str, readings["T7"]), QtCore.Q_ARG(str, readings["T8"]),
                                QtCore.Q_ARG(str, readings["T_Ave_Second"]))

                        if self.third_window and self.third_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, readings["H1"]), QtCore.Q_ARG(str, readings["H2"]),
                                QtCore.Q_ARG(str, readings["H_Ave"]))

                        # Save data
                        readings["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        self.data_log.append(readings)
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
        self.ui.label_12.setText(pwm_2)
        self.ui.label_11.setText(pwm_1)

        try:
            temp = float(t_ave_2nd)
            hum = float(h_ave)
            estimator = MoistureEstimator(temp, hum)
            drying_time = estimator.get_drying_time_seconds()
            self.last_valid_drying_seconds = drying_time
            self.ui.label_8.setText(f"Dry Time: {drying_time} s")
        except Exception as e:
            print("Error estimating drying time:", e)
            fallback = self.last_valid_drying_seconds or "Error"
            self.ui.label_8.setText(f"Dry Time: {fallback}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = FirstWindow()
    window.show()
    sys.exit(app.exec_())
