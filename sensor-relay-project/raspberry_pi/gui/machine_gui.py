from tkinter import Tk, Label, Frame, StringVar, Canvas
from tkinter.ttk import Progressbar

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
        frame.pack(padx=10, pady=10, fill="both", expand=True, side="left")  # Center the frame in the window

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

        # Add a column of icons on the right side
        self.icon_canvas = Canvas(master, width=100, height=300, bg="#2e3192", highlightthickness=0)
        self.icon_canvas.pack(side="right", padx=20, pady=20)

        # Draw icons (small circles and a dumbbell)
        self.icons = []
        self.icons.append(self.icon_canvas.create_oval(30, 30, 70, 70, fill="white"))  # First icon (circle)

        # Add a dumbbell icon
        self.dumbbell_bar = self.icon_canvas.create_rectangle(45, 145, 55, 155, fill="black")  # Center bar (half as thick)

        # Left weights (two vertically oriented rectangles)
        self.left_inner_weight = self.icon_canvas.create_rectangle(30, 140, 45, 160, fill="gray", outline="black")  # Inner rectangle (larger)
        self.left_outer_weight = self.icon_canvas.create_rectangle(25, 145, 30, 155, fill="gray", outline="black")  # Outer rectangle (smaller)

        # Right weights (two vertically oriented rectangles)
        self.right_inner_weight = self.icon_canvas.create_rectangle(55, 140, 70, 160, fill="gray", outline="black")  # Inner rectangle (larger)
        self.right_outer_weight = self.icon_canvas.create_rectangle(70, 145, 75, 155, fill="gray", outline="black")  # Outer rectangle (smaller)

        # Add the dumbbell components to the icons list
        self.icons.append(self.dumbbell_bar)

        # Add a clock icon
        self.clock_icon = self.icon_canvas.create_oval(30, 190, 70, 230, fill="white")  # Clock face
        self.icon_canvas.create_line(50, 210, 50, 195, width=2, fill="black")  # Clock hour hand
        self.icon_canvas.create_line(50, 210, 60, 210, width=1, fill="black")  # Clock minute hand
        self.icons.append(self.clock_icon)  # Add the clock icon to the icons list

        # Add a selection box (rectangle)
        self.selection_box = self.icon_canvas.create_rectangle(25, 25, 75, 75, outline="yellow", width=3)
        self.selected_index = 0  # Start with the first icon selected

        # Add a keybinding to exit fullscreen mode
        master.bind("<Escape>", self.exit_fullscreen)

    def move_selection(self, direction):
        """
        Move the selection box up or down.

        Args:
            direction: "up" or "down" to move the selection.
        """
        if direction == "up" and self.selected_index > 0:
            self.selected_index -= 1
        elif direction == "down" and self.selected_index < len(self.icons) - 1:
            self.selected_index += 1

        # Update the position of the selection box
        x1, y1, x2, y2 = self.icon_canvas.coords(self.icons[self.selected_index])
        self.icon_canvas.coords(self.selection_box, x1 - 5, y1 - 5, x2 + 5, y2 + 5)

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

    def reload_main_screen(self):
        """
        Reload the main GUI screen with the current weight, target weight, and other elements.
        """
        # Clear the GUI
        for widget in self.master.winfo_children():
            widget.destroy()

        # Add the main screen elements
        Label(self.master, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg="#2e3192", fg="white").pack(pady=5)
        Label(self.master, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        # Add a progress bar
        self.progress_bar = Progressbar(self.master, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=10)

        Label(self.master, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.
    root.mainloop()  # Start the Tkinter event loop to display the GUI.