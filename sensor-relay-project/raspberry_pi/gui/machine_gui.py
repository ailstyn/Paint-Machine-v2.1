from tkinter import Tk, Label, Frame, StringVar
from tkinter.ttk import Progressbar  # Import Progressbar from ttk

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

        # Make the window fullscreen
        master.attributes("-fullscreen", True)

        # Set the background color of the root window
        master.configure(bg="#2e3192")

        # Create a section for the single Arduino
        frame = Frame(master, borderwidth=2, relief="groove", padx=10, pady=10, bg="#2e3192")
        frame.pack(padx=10, pady=10, fill="both", expand=True)  # Center the frame in the window

        # Variables to display data for the Arduino
        self.weight_fraction_var = StringVar()
        self.weight_fraction_var.set("N/A / N/A")

        self.time_remaining_var = StringVar()
        self.time_remaining_var.set("N/A")

        # Labels to display the data
        Label(frame, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg="#2e3192", fg="white").pack(pady=5)
        Label(frame, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        # Add a progress bar
        self.progress_bar = Progressbar(frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=10)

        Label(frame, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        # Add a keybinding to exit fullscreen mode
        master.bind("<Escape>", self.exit_fullscreen)

    def update_data(self, data):
        """
        Update the displayed data for the Arduino.

        Args:
            data: A dictionary containing the new data to display.
                  Expected keys: 'target_weight', 'current_weight', 'time_remaining'.
        """
        target_weight = data.get("target_weight", "N/A")
        current_weight = data.get("current_weight", "N/A")

        # Update the weight fraction
        if target_weight != "N/A" and current_weight != "N/A":
            self.weight_fraction_var.set(f"{current_weight} / {target_weight}")

            # Update the progress bar
            try:
                target_weight = float(target_weight)
                current_weight = float(current_weight)
                progress = (current_weight / target_weight) * 100 if target_weight > 0 else 0
                self.progress_bar["value"] = progress
            except ValueError:
                self.progress_bar["value"] = 0
        else:
            self.weight_fraction_var.set("N/A / N/A")
            self.progress_bar["value"] = 0

        # Update the time remaining
        if "time_remaining" in data:
            self.time_remaining_var.set(f"{data['time_remaining']}")
        else:
            self.time_remaining_var.set("N/A")

    def exit_fullscreen(self, event=None):
        """
        Exit fullscreen mode when the Escape key is pressed.
        """
        self.master.attributes("-fullscreen", False)

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.
    root.mainloop()  # Start the Tkinter event loop to display the GUI.