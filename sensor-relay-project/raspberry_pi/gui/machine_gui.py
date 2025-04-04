from tkinter import Tk, Label, Button, StringVar
import serial
import time

#class RelayControlApp:
#    def __init__(self, master):
#        self.master = master
#        master.title("Relay Control")
#
#        self.data_var = StringVar()
#        self.data_label = Label(master, textvariable=self.data_var)
#        self.data_label.pack()
#
#        self.relay_button = Button(master, text="Toggle Relay", command=self.toggle_relay)
#        self.relay_button.pack()

        # Open the serial port using pyserial
#        self.serial_port = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)  # Adjust port as necessary
#        self.update_data()
#
#    def update_data(self):
#        while True:
#            if self.serial_port.in_waiting > 0:  # Check if data is available
#                data = self.serial_port.readline().decode('utf-8').strip()  # Read and decode the data
#                if data:
#                    self.data_var.set(data)
#            self.master.update()
#            time.sleep(1)
#
#    def toggle_relay(self):
        # Send the toggle command to the serial port
#        self.serial_port.write(b'TOGGLE_RELAY\n')

if __name__ == "__main__":
    root = Tk()
#    app = RelayControlApp(root)
    root.mainloop()