from tkinter import Tk, Label, Button, StringVar

# This class defines the GUI application for controlling and displaying relay-related data.
class RelayControlApp:
    def __init__(self, master):
        """
        Initialize the GUI application.

        Args:
            master: The root Tkinter window or parent widget.
        """
        self.master = master
        master.title("Relay Control")  # Set the title of the GUI window.

        # Variable to display data in the GUI.
        self.data_var = StringVar()  # A Tkinter variable to hold dynamic text.
        self.data_var.set("Waiting for data...")  # Default text displayed in the GUI.

        # Label to display the current data (e.g., messages from the Arduino).
        self.data_label = Label(master, textvariable=self.data_var, font=("Arial", 14))
        self.data_label.pack(pady=10)  # Add padding around the label for better layout.

        # Button to simulate a relay action (for testing purposes).
        # This button doesn't control actual hardware but is useful for GUI testing.
        self.relay_button = Button(master, text="Simulate Relay Action", command=self.simulate_relay_action)
        self.relay_button.pack(pady=10)  # Add padding around the button for better layout.

    def update_data(self, new_data):
        """
        Update the displayed data in the GUI.

        Args:
            new_data: The new data to display (e.g., messages from the Arduino).
        """
        self.data_var.set(new_data)  # Update the text displayed in the label.

    def simulate_relay_action(self):
        """
        Simulate a relay action (for testing purposes).
        This method is triggered when the "Simulate Relay Action" button is clicked.
        """
        print("Simulated relay action triggered!")  # Print a message to the console.

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.
    root.mainloop()  # Start the Tkinter event loop to display the GUI.