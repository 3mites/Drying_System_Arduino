import sys
import serial
import threading
from PyQt5 import QtWidgets, QtCore
from FLC_MaizeDry import TemperatureFuzzyController
from lcd_display import Ui_MainWindow as Ui_FirstWindow
from lcd_display_temperature import Ui_MainWindow as Ui_SecondWindow
from lcd_display_temperature_drying import Ui_MainWindow as Ui_TempDryingWindow
from lcd_display_humidity import Ui_MainWindow as Ui_ThirdWindow

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

        self.second_window = None
        self.third_window = None
        self.temp_drying_window = None

        self.ui.pushButton_2.setEnabled(True)
        self.ui.pushButton.setEnabled(False)

        self.ui.pushButton_2.clicked.connect(self.go_to_second)

        self.serial_thread = threading.Thread(target=self.read_serial_data)
        self.serial_thread.daemon = True
        self.serial_thread.start()

    def read_serial_data(self):
        try:
            ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            buffer = ""
            while True:
                line = ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue

                buffer += line + " "  # Accumulate incoming data

                # Check if the line ends with the last expected field
                if "pwm_2:" in buffer:
                    print("Received full line:", repr(buffer))  # Debug print

                    parts = buffer.strip().split()
                    buffer = ""  # Clear buffer for next line

                    if len(parts) < 15:
                        print("Incomplete serial data:", parts)
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

                        # Update FirstWindow
                        QtCore.QMetaObject.invokeMethod(
                            self,
                            "update_labels",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, t_ave_2nd),
                            QtCore.Q_ARG(str, h_ave),
                            QtCore.Q_ARG(str, pwm_2),
                            QtCore.Q_ARG(str, pwm_1)
                        )

                        # Update SecondWindow
                        if hasattr(self, 'second_window') and self.second_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(
                                self.second_window,
                                "update_temperature_labels",
                                QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, t1),
                                QtCore.Q_ARG(str, t2),
                                QtCore.Q_ARG(str, t3),
                                QtCore.Q_ARG(str, t4),
                                QtCore.Q_ARG(str, t_ave_first)
                            )

                        # Update TempDryingWindow
                        if hasattr(self, 'temp_drying_window') and self.temp_drying_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(
                                self.temp_drying_window,
                                "update_temperature_labels",
                                QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, t5),
                                QtCore.Q_ARG(str, t6),
                                QtCore.Q_ARG(str, t7),
                                QtCore.Q_ARG(str, t8),
                                QtCore.Q_ARG(str, t_ave_2nd)
                            )

                        # Update ThirdWindow
                        if hasattr(self, 'third_window') and self.third_window.isVisible():
                            QtCore.QMetaObject.invokeMethod(
                                self.third_window,
                                "update_humidity_labels",
                                QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, h1),
                                QtCore.Q_ARG(str, h2),
                                QtCore.Q_ARG(str, h_ave)
                            )

                    except Exception as e:
                        print("Temperature parsing error (T1->T8):", e)
        except serial.SerialException as e:
            print("Serial error:", e)


                

    @QtCore.pyqtSlot(str, str, str, str)
    def update_labels(self, t_ave_2nd, h_ave, pwm_2, pwm_1):
        self.ui.label.setText(f"{t_ave_2nd} °C")
        self.ui.label_6.setText(f"{h_ave} %")
        self.ui.label_12.setText(f"{pwm_2}")
        self.ui.label_11.setText(f"{pwm_1}")

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

        self.ui.pushButton.clicked.connect(self.go_to_second)   # Previous
        self.ui.pushButton_2.clicked.connect(self.go_to_third)  # Next

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
        self.ui.label.setText(f"{t5} \u00B0C")
        self.ui.label_6.setText(f"{t6} \u00B0C")
        self.ui.label_12.setText(f"{t7} \u00B0C")
        self.ui.label_11.setText(f"{t8} \u00B0C")
        self.ui.label_8.setText(f"Average: {t_ave_2nd} \u00B0C")




app = QtWidgets.QApplication(sys.argv)
main_window = FirstWindow()
main_window.show()
sys.exit(app.exec_())
