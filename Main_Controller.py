import sys
import serial
import time
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot, QTimer, QThread, pyqtSignal
from PyQt5 import QtWidgets
from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow
from calculate_emc import MoistureEstimator


class SerialWorker(QThread):
    packet_ready = pyqtSignal(dict)

    def __init__(self, port, baud, parent=None):
        super().__init__(parent)
        self.port, self.baud = port, baud
        self.running = True

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1)
        except Exception as e:
            print("Serial init failed:", e)
            return

        buffer = ""
        last_emit = time.time()

        while self.running:
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
                    data = {
                        'T': parts[11].split("t_ave_2nd:")[1],
                        'H': parts[12].split("h_ave:")[1],
                        'pwm2': parts[14].split("pwm_2:")[1],
                        'pwm1': parts[13].split("pwm_1:")[1],
                        'temps': [parts[i].split(f"T{i+1}:")[1] for i in range(4)],
                        'dry_temps': [parts[i].split(f"T{i+5}:")[1] for i in range(4)],
                        'hum': [parts[8].split("H1:")[1], parts[9].split("H2:")[1]],
                        't_ave_first': parts[10].split("t_ave_first:")[1],
                    }
                    print("[DEBUG] Emitting parsed data...", data)
                except Exception as e:
                    continue

                now = time.time()
                if now - last_emit >= 1.0:
                    self.packet_ready.emit(data)
                    last_emit = now

    def stop(self):
        self.running = False
        self.wait()


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

    @pyqtSlot(str, str, str)
    def update_humidity_labels(self, h1, h2, h_ave):
        print("[DEBUG] Updating ThirdWindow:", h1, h2, h_ave)
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

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t1, t2, t3, t4, t_ave_first):
        print("[DEBUG] Updating SecondWindow:", t1, t2, t3, t4, t_ave_first)
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

    @pyqtSlot(str, str, str, str, str)
    def update_temperature_labels(self, t5, t6, t7, t8, t_ave_2nd):
        print("[DEBUG] Updating TempDryingWindow:", t5, t6, t7, t8, t_ave_2nd)
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

        self.serial_worker = SerialWorker('COM6', 9600)
        self.serial_worker.packet_ready.connect(self.on_packet)
        self.serial_worker.start()

    def run_fuzzy_controller(self):
        try:
            fuzzy_control = TemperatureFuzzyController()
            adjustment = fuzzy_control.temperature_adjustment(self.t_ave_first, self.h_ave)
            if hasattr(self, 'ser') and self.ser.is_open:
                self.ser.write(f"ADJ:{adjustment}\n".encode())
        except Exception as e:
            print("Fuzzy controller error:", e)

    def on_packet(self, data):
        print("[DEBUG] Packet received:", data)

        t_ave_2nd = data['T']
        self.h_ave = data['H']
        self.t_ave_first = data['t_ave_first']

        QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", Qt.QueuedConnection,
                                 Q_ARG(str, data['temps'][0]), Q_ARG(str, data['temps'][1]),
                                 Q_ARG(str, data['temps'][2]), Q_ARG(str, data['temps'][3]),
                                 Q_ARG(str, self.t_ave_first))

        QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", Qt.QueuedConnection,
                                 Q_ARG(str, data['dry_temps'][0]), Q_ARG(str, data['dry_temps'][1]),
                                 Q_ARG(str, data['dry_temps'][2]), Q_ARG(str, data['dry_temps'][3]),
                                 Q_ARG(str, t_ave_2nd))

        QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", Qt.QueuedConnection,
                                 Q_ARG(str, data['hum'][0]), Q_ARG(str, data['hum'][1]),
                                 Q_ARG(str, self.h_ave))

        self.update_labels(t_ave_2nd, self.h_ave, data['pwm2'], data['pwm1'])

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

    def go_to_second(self):
        self.second_window.show()
        self.hide()

    def closeEvent(self, event):
        self.serial_worker.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = FirstWindow()
    main_window.show()
    sys.exit(app.exec_())
