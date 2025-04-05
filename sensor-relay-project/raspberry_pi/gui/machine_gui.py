from tkinter import Tk, Label, Frame, StringVar

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

        # Create a dictionary to hold the widgets and variables for each Arduino
        self.arduino_frames = {}

        # Create a section for each Arduino
        for i in range(4):  # Assuming 4 Arduinos
            frame = Frame(master, borderwidth=2, relief="groove")
            frame.pack(side="left", padx=10, pady=10, fill="both", expand=True)

            # Variables to display data for this Arduino
            target_weight_var = StringVar()
            target_weight_var.set("Target Weight: N/A")

            current_weight_var = StringVar()
            current_weight_var.set("Current Weight: N/A")

            time_remaining_var = StringVar()
            time_remaining_var.set("Time Remaining: N/A")

            # Labels to display the data
            Label(frame, text=f"Arduino {i + 1}", font=("Arial", 16, "bold")).pack(pady=5)
            Label(frame, textvariable=target_weight_var, font=("Arial", 14)).pack(pady=5)
            Label(frame, textvariable=current_weight_var, font=("Arial", 14)).pack(pady=5)
            Label(frame, textvariable=time_remaining_var, font=("Arial", 14)).pack(pady=5)

            # Store the variables in the dictionary
            self.arduino_frames[i] = {
                "target_weight_var": target_weight_var,
                "current_weight_var": current_weight_var,
                "time_remaining_var": time_remaining_var,
            }

    def update_data(self, arduino_id, data):
        """
        Update the displayed data for a specific Arduino.

        Args:
            arduino_id: The ID of the Arduino (0-3).
            data: A dictionary containing the new data to display.
                  Expected keys: 'target_weight', 'current_weight', 'time_remaining'.
        """
        if arduino_id in self.arduino_frames:
            frame = self.arduino_frames[arduino_id]
            if "target_weight" in data:
                frame["target_weight_var"].set(f"Target Weight: {data['target_weight']}")
            if "current_weight" in data:
                frame["current_weight_var"].set(f"Current Weight: {data['current_weight']}")
            if "time_remaining" in data:
                frame["time_remaining_var"].set(f"Time Remaining: {data['time_remaining']}")

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.
    root.mainloop()  # Start the Tkinter event loop to display the GUI.