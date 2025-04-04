from tkinter import Tk, Label, Button, StringVar
import serial
import time
from utils.serial_communication import open_serial_port, read_from_serial, send_to_serial

class RelayControlApp:
    def __init__(self, master):
        self.master = master
        master.title("Relay Control")

        self.data_var = StringVar()
        self.data_label = Label(master, textvariable=self.data_var)
        self.data_label.pack()

        self.relay_button = Button(master, text="Toggle Relay", command=self.toggle_relay)
        self.relay_button.pack()

        self.serial_port = open_serial_port('/dev/ttyUSB0', 9600)  # Adjust port as necessary
        self.update_data()

    def update_data(self):
        while True:
            data = read_from_serial(self.serial_port)
            if data:
                self.data_var.set(data)
            self.master.update()
            time.sleep(1)

    def toggle_relay(self):
        send_to_serial(self.serial_port, 'TOGGLE_RELAY')

if __name__ == "__main__":
    root = Tk()
    app = RelayControlApp(root)
    root.mainloop()