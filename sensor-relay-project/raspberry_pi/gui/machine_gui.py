from tkinter import Tk, Canvas, Frame, StringVar, Label
from tkinter.ttk import Progressbar

class RelayControlApp:
    def __init__(self, master):
        print("Initializing RelayControlApp...")
        self.master = master
        self.weight_fraction_var = StringVar()
        self.time_remaining_var = StringVar()
        # Initialize other GUI components here...
        print("RelayControlApp initialized.")
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

        # Create a container frame for horizontal layout
        container = Frame(master, bg="#2e3192")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Add a vertical progress bar on the left side
        self.progress_bar = Progressbar(container, orient="vertical", length=300, mode="determinate")
        self.progress_bar.pack(side="left", padx=20, pady=20)

        # Create a section for the scale in the center
        scale_frame = Frame(container, borderwidth=2, relief="groove", padx=10, pady=10, bg="#2e3192")
        scale_frame.pack(side="left", padx=20, pady=20, fill="both", expand=True)  # Center the scale

        # Variables to display data for the Arduino
        self.weight_fraction_var = StringVar()
        self.weight_fraction_var.set("N/A / N/A")

        self.time_remaining_var = StringVar()
        self.time_remaining_var.set("N/A")

        # Labels to display the data
        Label(scale_frame, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg="#2e3192", fg="white").pack(pady=5)
        Label(scale_frame, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        Label(scale_frame, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        # Add a column of icons on the right side
        self.icon_canvas = Canvas(container, width=75, height=225, bg="#2e3192", highlightthickness=0)
        self.icon_canvas.pack(side="left", padx=20, pady=20)  # Align to the right

        # Draw icons (small circles and a dumbbell)
        self.icons = []
        self.icons.append(self.icon_canvas.create_oval(22.5, 22.5, 52.5, 52.5, fill="white"))  # First icon (circle, scaled down)

        # Add a dumbbell icon
        self.dumbbell_bar = self.icon_canvas.create_rectangle(33.75, 108.75, 41.25, 116.25, fill="black")  # Center bar (scaled down)

        # Left weights (two vertically oriented rectangles)
        self.left_inner_weight = self.icon_canvas.create_rectangle(22.5, 105, 33.75, 120, fill="gray", outline="black")  # Inner rectangle (scaled down)
        self.left_outer_weight = self.icon_canvas.create_rectangle(18.75, 108.75, 22.5, 116.25, fill="gray", outline="black")  # Outer rectangle (scaled down)

        # Right weights (two vertically oriented rectangles)
        self.right_inner_weight = self.icon_canvas.create_rectangle(41.25, 105, 52.5, 120, fill="gray", outline="black")  # Inner rectangle (scaled down)
        self.right_outer_weight = self.icon_canvas.create_rectangle(52.5, 108.75, 56.25, 116.25, fill="gray", outline="black")  # Outer rectangle (scaled down)

        # Add the dumbbell components to the icons list
        self.icons.append(self.dumbbell_bar)

        # Add a clock icon
        self.clock_icon = self.icon_canvas.create_oval(22.5, 142.5, 52.5, 172.5, fill="white")  # Clock face (scaled down)
        self.icon_canvas.create_line(37.5, 157.5, 37.5, 146.25, width=1.5, fill="black")  # Clock hour hand (scaled down)
        self.icon_canvas.create_line(37.5, 157.5, 45, 157.5, width=0.75, fill="black")  # Clock minute hand (scaled down)
        self.icons.append(self.clock_icon)  # Add the clock icon to the icons list

        # Add a selection box (rectangle)
        self.selection_box = self.icon_canvas.create_rectangle(18.75, 18.75, 56.25, 56.25, outline="yellow", width=3)  # Adjusted for smaller buttons
        self.selected_index = 0  # Start with the first icon selected

        # Add a keybinding to exit fullscreen mode
        master.bind("<Escape>", self.exit_fullscreen)

        self.refresh()  # Start the refresh loop

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

        # Get the coordinates of the currently selected icon
        x1, y1, x2, y2 = self.icon_canvas.coords(self.icons[self.selected_index])

        # Adjust the selection box to be slightly larger than the icon
        padding = 3  # Add padding around the icon
        self.icon_canvas.coords(self.selection_box, x1 - padding, y1 - padding, x2 + padding, y2 + padding)

    def update_data(self, arduino_id, data):
        """
        Update the displayed data for the Arduino.

        Args:
            arduino_id: The ID of the Arduino sending the data.
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
                self.set_progress(progress)
            except ValueError:
                self.set_progress(0)
        else:
            self.weight_fraction_var.set("N/A / N/A")
            self.set_progress(0)

        # Update the time remaining
        if "time_remaining" in data:
            self.time_remaining_var.set(f"{data['time_remaining']}")
        else:
            self.time_remaining_var.set("N/A")

    def set_progress(self, value):
        """
        Update the vertical progress bar to the specified value.

        Args:
            value: The progress percentage (0 to 100).
        """
        value = max(0, min(100, value))  # Clamp value between 0 and 100
        self.progress_bar["value"] = value  # Update the progress bar value

    def exit_fullscreen(self, event=None):
        # Exit fullscreen mode when the Escape key is pressed.
        self.master.attributes("-fullscreen", False)

    def reload_main_screen(self):
        #Reload the main GUI screen with the current weight, target weight, and other elements.
        for widget in self.master.winfo_children():
            widget.destroy()

        # Add the main screen elements
        Label(self.master, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg="#2e3192", fg="white").pack(pady=5)
        Label(self.master, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

        # Add a progress bar
        self.progress_bar = Progressbar(self.master, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=10)

        Label(self.master, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg="#2e3192", fg="white").pack(pady=5)

    def display_e_stop(self):
        """
        Display a full-screen message indicating that the E-Stop is activated.
        """
        # Clear the GUI
        for widget in self.master.winfo_children():
            widget.destroy()

        # Display the E-Stop message
        Label(self.master, text="ESTOP ACTIVATED", font=('Cascadia Code SemiBold', 48), bg="black", fg="red").pack(expand=True, fill="both")

    def refresh(self):
        # Update GUI elements here
        self.master.after(33, self.refresh)  # Schedule next refresh (30 FPS)

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.

    # Simulate progress
    def simulate_progress():
        current_weight = getattr(app, "current_weight", 0)  # Start with 0 weight
        target_weight = 300  # Set a target weight for simulation

        if current_weight < target_weight:
            # Increment current weight smoothly
            app.current_weight = current_weight + 1.5  # Increment weight
            current_weight = app.current_weight

            # Update weight fraction display
            app.weight_fraction_var.set(f"{current_weight:.1f} / {target_weight}")

            # Calculate and update progress bar
            progress = (current_weight / target_weight) * 100 if target_weight > 0 else 0
            app.set_progress(progress)

            # Schedule the next update
            root.after(33, simulate_progress)  # Update every 33ms (30 frames per second)

    # Initialize simulation variables
    app.progress = 0
    app.time_remaining = 100
    app.current_weight = 0

    simulate_progress()

    root.mainloop()  # Start the Tkinter event loop to display the GUI.