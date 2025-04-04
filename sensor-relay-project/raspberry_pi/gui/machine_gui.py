from tkinter import Tk, Label, Button, StringVar

class RelayControlApp:
    def __init__(self, master):
        self.master = master
        master.title("Relay Control")

        # Variable to display data
        self.data_var = StringVar()
        self.data_var.set("Waiting for data...")

        # Label to display data
        self.data_label = Label(master, textvariable=self.data_var, font=("Arial", 14))
        self.data_label.pack(pady=10)

        # Button to simulate relay control (optional, for GUI testing)
        self.relay_button = Button(master, text="Simulate Relay Action", command=self.simulate_relay_action)
        self.relay_button.pack(pady=10)

    def update_data(self, new_data):
        """Update the displayed data."""
        self.data_var.set(new_data)

    def simulate_relay_action(self):
        """Simulate a relay action (for testing purposes)."""
        print("Simulated relay action triggered!")

if __name__ == "__main__":
    root = Tk()
    app = RelayControlApp(root)
    root.mainloop()