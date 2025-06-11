import sys
import signal
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, pyqtSlot, QTimer, QThread, pyqtSignal, QObject
from PyQt5 import QtWidgets
from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow
from calculate_emc import MoistureEstimator
import serial


class SerialReader(QObject):
    packet_ready = pyqtSignal(dict)

    def __init__(self, port='/dev/ttyUSB0', baud=9600):
        super().__init__()
        self.serial = serial.Serial(port, baud, timeout=0.1)
        self.buffer = b""
        self.packet_timer = QTimer()
        self.packet_timer.setSingleShot(True)
        self.packet_timer.setInterval(200)
        self.packet_timer.timeout.connect(self.emit_packet)
        self.last_packet_data = {}
        self.read_timer = QTimer()
        self.read_timer.timeout.connect(self.read_serial_data)

    def start(self):
        if self.serial.is_open:
            print("Serial port opened")
            self.read_timer.start(100)
        else:
            print("Failed to open serial port")

    def read_serial_data(self):
        try:
            data = self.serial.read(self.serial.in_waiting or 1)
            if data:
                self.buffer += data
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    self.process_line(line.decode(errors='ignore').strip())
        except Exception as e:
            print("Serial read error:", e)

    def process_line(self, line):
        if "pwm_2:" not in line:
            return

        parts = line.split()
        parsed = {}
        for part in parts:
            if ':' in part:
                k, v = part.split(':', 1)
                parsed[k.strip()] = v.strip()

        try:
            data = {
                'T': parsed.get("t_ave_2nd", "0"),
                'H': parsed.get("h_ave", "0"),
                'pwm2': parsed.get("pwm_2", "0"),
                'pwm1': parsed.get("pwm_1", "0"),
                'temps': [parsed.get(f"T{i+1}", "0") for i in range(4)],
                'dry_temps': [parsed.get(f"T{i+5}", "0") for i in range(4)],
                'hum': [parsed.get("H1", "0"), parsed.get("H2", "0")],
                't_ave_first': parsed.get("t_ave_first", "0")
            }
            self.last_packet_data = data
            if not self.packet_timer.isActive():
                self.packet_timer.start()
        except Exception as e:
            print("Parsing error:", e)

    def emit_packet(self):
        self.packet_ready.emit(self.last_packet_data)


class ProcessingWorker(QObject):
    result_ready = pyqtSignal(str)

    @pyqtSlot(float, float)
    def process(self, t_ave_2nd, h_ave):
        try:
            estimator = MoistureEstimator(t_ave_2nd, h_ave)
            drying_seconds = estimator.get_drying_time_seconds()

            fuzzy = TemperatureFuzzyController()
            _ = fuzzy.temperature_adjustment(t_ave_2nd, h_ave)

            hours = int(drying_seconds // 3600)
            minutes = int((drying_seconds % 3600) // 60)
            if hours > 0:
                result_text = f"Dry Time: {hours} hr {minutes} min"
            else:
                result_text = f"Dry Time: {minutes} min"

            print("[ProcessingWorker] Calculated:", result_text)
            self.result_ready.emit(result_text)

        except Exception as e:
            print("[ProcessingWorker] Error:", e)
            self.result_ready.emit("Dry Time: Error")


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
        self.second_window = SecondWindow(self)
        self.third_window = ThirdWindow(self)
        self.temp_drying_window = TempDryingWindow(self)
        self.ui.pushButton_2.clicked.connect(self.go_to_second)
        self.ui.pushButton.setEnabled(False)

        self.worker_thread = QThread()
        self.worker = ProcessingWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.result_ready.connect(self.on_drying_result)
        self.worker_thread.start()

        self.reader = SerialReader()
        self.reader.packet_ready.connect(self.on_packet)
        QTimer.singleShot(1000, self.reader.start)

    def on_packet(self, data):
        print("Received:", data)
        self.t_ave_first = data['t_ave_first']
        self.h_ave = data['H']

        QMetaObject.invokeMethod(self.second_window, "update_temperature_labels", Qt.QueuedConnection,
            Q_ARG(str, data['temps'][0]), Q_ARG(str, data['temps'][1]), Q_ARG(str, data['temps'][2]),
            Q_ARG(str, data['temps'][3]), Q_ARG(str, self.t_ave_first))

        QMetaObject.invokeMethod(self.temp_drying_window, "update_temperature_labels", Qt.QueuedConnection,
            Q_ARG(str, data['dry_temps'][0]), Q_ARG(str, data['dry_temps'][1]), Q_ARG(str, data['dry_temps'][2]),
            Q_ARG(str, data['dry_temps'][3]), Q_ARG(str, data['T']))

        QMetaObject.invokeMethod(self.third_window, "update_humidity_labels", Qt.QueuedConnection,
            Q_ARG(str, data['hum'][0]), Q_ARG(str, data['hum'][1]), Q_ARG(str, self.h_ave))

        QMetaObject.invokeMethod(self, "update_labels", Qt.QueuedConnection,
            Q_ARG(str, data['T']), Q_ARG(str, self.h_ave), Q_ARG(str, data['pwm2']), Q_ARG(str, data['pwm1']))

    @pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        self.ui.label.setText(f"{t_ave_2nd} °C")
        self.ui.label_6.setText(f"{h_ave} %")
        self.ui.label_12.setText(pwm_2)
        self.ui.label_11.setText(pwm_1)

        try:
            t_val = float(t_ave_2nd)
            h_val = float(h_ave)
            QMetaObject.invokeMethod(self.worker, "process", Qt.QueuedConnection,
                                     Q_ARG(float, t_val), Q_ARG(float, h_val))
        except Exception as e:
            print("[update_labels] Float conversion failed:", e)

    @pyqtSlot(str)
    def on_drying_result(self, result_text):
        print("[on_drying_result] ETA Result:", result_text)
        self.ui.label_8.setText(result_text)

    def go_to_second(self):
        self.second_window.show()
        self.hide()

    def closeEvent(self, event):
        if self.reader.serial.is_open:
            self.reader.serial.close()
        self.worker_thread.quit()
        self.worker_thread.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    window = FirstWindow()
    window.show()
    sys.exit(app.exec_())
