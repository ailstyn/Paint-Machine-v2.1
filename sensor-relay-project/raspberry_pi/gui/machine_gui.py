from tkinter import Tk, Canvas, Frame, StringVar, Label, Button
from tkinter.ttk import Progressbar

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "white", "splash": "red"},
    {"name": "Dark Mode", "bg": "#222", "fg": "#eee", "splash": "#ff9800"},
    {"name": "Light Mode", "bg": "#fafafa", "fg": "#222", "splash": "#1976d2"},
    {"name": "Green Alert", "bg": "#1b5e20", "fg": "#fff", "splash": "#ffeb3b"},
]

class RelayControlApp:
    def __init__(self, master):
        print("Initializing RelayControlApp...")
        self.master = master
        self.weight_fraction_var = StringVar()
        self.time_remaining_var = StringVar()
        self.color_scheme_index = 0
        self.set_color_scheme(COLOR_SCHEMES[self.color_scheme_index])

        master.title("Relay Control")
        master.attributes("-fullscreen", True)
        master.configure(bg=self.bg)

        # Create a container frame for horizontal layout
        self.container = Frame(master, bg=self.bg)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        # Add a vertical progress bar on the left side
        self.progress_bar = Progressbar(self.container, orient="vertical", length=300, mode="determinate")
        self.progress_bar.pack(side="left", padx=20, pady=20)

        # Create a section for the scale in the center
        self.scale_frame = Frame(self.container, borderwidth=2, relief="groove", padx=10, pady=10, bg=self.bg)
        self.scale_frame.pack(side="left", padx=20, pady=20, fill="both", expand=True)

        # Variables to display data for the Arduino
        self.weight_fraction_var.set("N/A / N/A")
        self.time_remaining_var.set("N/A")

        # Labels to display the data
        self.scale_label = Label(self.scale_frame, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg=self.bg, fg=self.fg)
        self.scale_label.pack(pady=5)
        self.weight_label = Label(self.scale_frame, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg=self.bg, fg=self.fg)
        self.weight_label.pack(pady=5)
        self.time_label = Label(self.scale_frame, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg=self.bg, fg=self.fg)
        self.time_label.pack(pady=5)

        # Add a column of icons on the right side
        self.icon_canvas = Canvas(self.container, width=75, height=225, bg=self.bg, highlightthickness=0)
        self.icon_canvas.pack(side="left", padx=20, pady=20)

        # Draw icons (small circles and a dumbbell)
        self.icons = []
        self.icons.append(self.icon_canvas.create_oval(22.5, 22.5, 52.5, 52.5, fill=self.fg))  # First icon (circle)

        # Dumbbell icon
        self.dumbbell_bar = self.icon_canvas.create_rectangle(33.75, 108.75, 41.25, 116.25, fill="black")
        self.left_inner_weight = self.icon_canvas.create_rectangle(22.5, 105, 33.75, 120, fill="gray", outline="black")
        self.left_outer_weight = self.icon_canvas.create_rectangle(18.75, 108.75, 22.5, 116.25, fill="gray", outline="black")
        self.right_inner_weight = self.icon_canvas.create_rectangle(41.25, 105, 52.5, 120, fill="gray", outline="black")
        self.right_outer_weight = self.icon_canvas.create_rectangle(52.5, 108.75, 56.25, 116.25, fill="gray", outline="black")
        self.icons.append(self.dumbbell_bar)

        # Clock icon
        self.clock_icon = self.icon_canvas.create_oval(22.5, 142.5, 52.5, 172.5, fill=self.fg)
        self.icon_canvas.create_line(37.5, 157.5, 37.5, 146.25, width=1.5, fill="black")
        self.icon_canvas.create_line(37.5, 157.5, 45, 157.5, width=0.75, fill="black")
        self.icons.append(self.clock_icon)

        # Add a selection box (rectangle)
        self.selection_box = self.icon_canvas.create_rectangle(18.75, 18.75, 56.25, 56.25, outline="yellow", width=3)
        self.selected_index = 0

        # Add a keybinding to exit fullscreen mode
        master.bind("<Escape>", self.exit_fullscreen)

        # Add color scheme button
        self.color_button = Button(master, text="Change Color Scheme", command=self.cycle_color_scheme, bg=self.bg, fg=self.fg)
        self.color_button.place(relx=1.0, rely=0.0, anchor="ne")

        self.refresh()  # Start the refresh loop

    def move_selection(self, direction):
        if direction == "up" and self.selected_index > 0:
            self.selected_index -= 1
        elif direction == "down" and self.selected_index < len(self.icons) - 1:
            self.selected_index += 1
        x1, y1, x2, y2 = self.icon_canvas.coords(self.icons[self.selected_index])
        padding = 3
        self.icon_canvas.coords(self.selection_box, x1 - padding, y1 - padding, x2 + padding, y2 + padding)

    def update_data(self, arduino_id, data):
        target_weight = data.get("target_weight", "N/A")
        current_weight = data.get("current_weight", "N/A")
<<<<<<< HEAD
=======
        
        # Update the weight fraction
>>>>>>> 1816290e3118932c0e1459231fce3211bb5df652
        if target_weight != "N/A" and current_weight != "N/A":
            self.weight_fraction_var.set(f"{current_weight} / {target_weight}")
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
        if "time_remaining" in data:
            self.time_remaining_var.set(f"{data['time_remaining']}")
        else:
            self.time_remaining_var.set("N/A")

    def set_progress(self, value):
        value = max(0, min(100, value))
        self.progress_bar["value"] = value

    def exit_fullscreen(self, event=None):
        self.master.attributes("-fullscreen", False)

    def reload_main_screen(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        # Recreate widgets with current color scheme
        self.container = Frame(self.master, bg=self.bg)
        self.container.pack(fill="both", expand=True, padx=10, pady=10)
        self.progress_bar = Progressbar(self.container, orient="vertical", length=300, mode="determinate")
        self.progress_bar.pack(side="left", padx=20, pady=20)
        self.scale_frame = Frame(self.container, borderwidth=2, relief="groove", padx=10, pady=10, bg=self.bg)
        self.scale_frame.pack(side="left", padx=20, pady=20, fill="both", expand=True)
        self.scale_label = Label(self.scale_frame, text="SCALE 1", font=('Cascadia Code SemiBold', 24), bg=self.bg, fg=self.fg)
        self.scale_label.pack(pady=5)
        self.weight_label = Label(self.scale_frame, textvariable=self.weight_fraction_var, font=('Cascadia Code SemiBold', 16), bg=self.bg, fg=self.fg)
        self.weight_label.pack(pady=5)
        self.time_label = Label(self.scale_frame, textvariable=self.time_remaining_var, font=('Cascadia Code SemiBold', 16), bg=self.bg, fg=self.fg)
        self.time_label.pack(pady=5)
        self.icon_canvas = Canvas(self.container, width=75, height=225, bg=self.bg, highlightthickness=0)
        self.icon_canvas.pack(side="left", padx=20, pady=20)
        # Redraw icons as before (omitted for brevity)
        self.color_button = Button(self.master, text="Change Color Scheme", command=self.cycle_color_scheme, bg=self.bg, fg=self.fg)
        self.color_button.place(relx=1.0, rely=0.0, anchor="ne")

    def display_e_stop(self):
        for widget in self.master.winfo_children():
            widget.destroy()
        Label(self.master, text="ESTOP ACTIVATED", font=('Cascadia Code SemiBold', 48), bg=self.bg, fg=self.splash).pack(expand=True, fill="both")
        self.color_button = Button(self.master, text="Change Color Scheme", command=self.cycle_color_scheme, bg=self.bg, fg=self.fg)
        self.color_button.place(relx=1.0, rely=0.0, anchor="ne")

    def refresh(self):
        # If you want to update widget colors dynamically, do it here
        self.master.after(33, self.refresh)

    def cycle_color_scheme(self):
        self.color_scheme_index = (self.color_scheme_index + 1) % len(COLOR_SCHEMES)
        self.set_color_scheme(COLOR_SCHEMES[self.color_scheme_index])
        self.reload_main_screen()

    def set_color_scheme(self, scheme):
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]
        self.master.configure(bg=self.bg)

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