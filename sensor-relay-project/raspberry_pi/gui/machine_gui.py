from tkinter import Tk, Canvas, Frame, StringVar, Label, Button, Toplevel
from tkinter.ttk import Progressbar
from PIL import Image, ImageTk
import os

COLOR_SCHEMES = [
    {"name": "Classic Blue", "bg": "#2e3192", "fg": "white", "splash": "red"},
    {"name": "Dark Mode", "bg": "#333333", "fg": "#FFFFFF", "splash": "#F6EB61"},
    {"name": "Light Mode", "bg": "#F5FFFA", "fg": "#000000", "splash": "#800020"},
    {"name": "Green Alert", "bg": "#1B9E3A", "fg": "#FFFFFF", "splash": "#FF6F61"},
]

class RelayControlApp:
    def __init__(self, master):
        print("Initializing RelayControlApp...")
        self.master = master
        self.weight_fraction_var = StringVar()
        self.time_remaining_var = StringVar()
        self.color_scheme_index = 0
        scheme = COLOR_SCHEMES[self.color_scheme_index]
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]

        master.title("Relay Control")
        master.attributes("-fullscreen", True)
        master.configure(bg=self.bg)

        # Load dumbbell image
        dumbbell_img_path = os.path.join(os.path.dirname(__file__), "dumbell.png")
        self.dumbbell_img = Image.open(dumbbell_img_path)
        self.dumbbell_img = self.dumbbell_img.resize((40, 40), Image.Resampling.LANCZOS)
        self.dumbbell_photo = ImageTk.PhotoImage(self.dumbbell_img)

        # Load stopwatch image
        stopwatch_img_path = os.path.join(os.path.dirname(__file__), "stopwatch.png")
        self.stopwatch_img = Image.open(stopwatch_img_path)
        self.stopwatch_img = self.stopwatch_img.resize((40, 40), Image.Resampling.LANCZOS)
        self.stopwatch_photo = ImageTk.PhotoImage(self.stopwatch_img)

        # Load color scheme image
        color_img_path = os.path.join(os.path.dirname(__file__), "color.png")
        self.color_img = Image.open(color_img_path)
        self.color_img = self.color_img.resize((40, 40), Image.Resampling.LANCZOS)
        self.color_photo = ImageTk.PhotoImage(self.color_img)

        # Keep references to loaded images
        self.loaded_images = {
            "dumbbell": self.dumbbell_photo,
            "stopwatch": self.stopwatch_photo,
            "color": self.color_photo,
        }

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
        self.icon_canvas = Canvas(self.container, width=90, height=225, bg=self.bg, highlightthickness=0)
        self.icon_canvas.pack(side="left", padx=20, pady=20)

        self.icons = []
        icon_x = 52.5  # horizontal center, moved right to allow more space for the dot
        icon_centers = [60, 120, 180]  # 3 icons, spaced 60px apart

        # Dumbell icons created by Vitaly Gorbachev - Flaticon https://www.flaticon.com/free-icons/dumbell
        self.dumbbell_icon = self.icon_canvas.create_image(icon_x, icon_centers[0], image=self.dumbbell_photo)
        self.icons.append(self.dumbbell_icon)

        # Clock icons created by Freepik - Flaticon https://www.flaticon.com/free-icons/clock
        self.clock_icon = self.icon_canvas.create_image(icon_x, icon_centers[1], image=self.stopwatch_photo)
        self.icons.append(self.clock_icon)

        # Color wheel icons created by Hasymi - Flaticon https://www.flaticon.com/free-icons/color-wheel
        self.color_icon = self.icon_canvas.create_image(icon_x, icon_centers[2], image=self.color_photo)
        self.icons.append(self.color_icon)

        # Add a solid dot to the left of the selected icon
        self.selected_index = getattr(self, "selected_index", 0)
        dot_radius = 5
        dot_x = icon_x - 45
        dot_y = icon_centers[self.selected_index]
        self.selection_dot = self.icon_canvas.create_oval(
            dot_x - dot_radius, dot_y - dot_radius,
            dot_x + dot_radius, dot_y + dot_radius,
            fill=self.fg, outline=""
        )

        # Add a keybinding to exit fullscreen mode
        master.bind("<Escape>", self.exit_fullscreen)

        self.refresh()  # Start the refresh loop

    def move_selection(self, direction):
        if direction == "up" and self.selected_index > 0:
            self.selected_index -= 1
        elif direction == "down" and self.selected_index < len(self.icons) - 1:
            self.selected_index += 1
        # Move the selection dot
        dot_radius = 5
        icon_x = 52.5
        dot_x = icon_x - 45
        icon_centers = [60, 120, 180]
        dot_y = icon_centers[self.selected_index]
        self.icon_canvas.coords(
            self.selection_dot,
            dot_x - dot_radius, dot_y - dot_radius,
            dot_x + dot_radius, dot_y + dot_radius
        )
        self.icon_canvas.itemconfig(self.selection_dot, fill=self.fg, outline="")

    def update_data(self, arduino_id, data):
        target_weight = data.get("target_weight", "N/A")
        current_weight = data.get("current_weight", "N/A")
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
            # If time_remaining is in ms, display as seconds with two decimals
            try:
                ms = float(data["time_remaining"])
                self.time_remaining_var.set(f"{ms/1000:.2f}s")
            except (ValueError, TypeError):
                self.time_remaining_var.set(data["time_remaining"])
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
        self.icon_canvas = Canvas(self.container, width=90, height=225, bg=self.bg, highlightthickness=0)
        self.icon_canvas.pack(side="left", padx=20, pady=20)

        self.icons = []
        icon_x = 52.5  # horizontal center, moved right to allow more space for the dot
        icon_centers = [60, 120, 180]  # 3 icons, spaced 60px apart

        # Dumbbell icon
        self.dumbbell_icon = self.icon_canvas.create_image(icon_x, icon_centers[0], image=self.loaded_images["dumbbell"])
        self.icons.append(self.dumbbell_icon)

        # Clock icon
        self.clock_icon = self.icon_canvas.create_image(icon_x, icon_centers[1], image=self.loaded_images["stopwatch"])
        self.icons.append(self.clock_icon)

        # Color wheel icon
        self.color_icon = self.icon_canvas.create_image(icon_x, icon_centers[2], image=self.loaded_images["color"])
        self.icons.append(self.color_icon)

        # Add a small dot to the left of the selected icon
        self.selected_index = getattr(self, "selected_index", 0)
        dot_radius = 5
        dot_x = icon_x - 45
        dot_y = icon_centers[self.selected_index]
        self.selection_dot = self.icon_canvas.create_oval(
            dot_x - dot_radius, dot_y - dot_radius,
            dot_x + dot_radius, dot_y + dot_radius,
            fill=self.fg, outline=""
        )

        # Add a keybinding to exit fullscreen mode
        self.master.bind("<Escape>", self.exit_fullscreen)

        self.apply_color_scheme

    def display_e_stop(self):
        if getattr(self, "e_stop_active", False):
            # Already displaying E-Stop, do nothing
            return
        self.e_stop_active = True
        for widget in self.master.winfo_children():
            widget.destroy()
        Label(self.master, text="ESTOP ACTIVATED", font=('Cascadia Code SemiBold', 48), bg=self.bg, fg=self.splash).pack(expand=True, fill="both")

    def refresh(self):
        # If you want to update widget colors dynamically, do it here
        self.master.after(33, self.refresh)

    def cycle_color_scheme(self):
        self.color_scheme_index = (self.color_scheme_index + 1) % len(COLOR_SCHEMES)
        self.set_color_scheme(COLOR_SCHEMES[self.color_scheme_index])
        # self.reload_main_screen()

    def apply_color_scheme(self):
        # Update main window and container backgrounds
        self.master.configure(bg=self.bg)
        self.container.configure(bg=self.bg)
        self.scale_frame.configure(bg=self.bg)
        self.icon_canvas.configure(bg=self.bg)

        # Update label foreground/background colors
        self.scale_label.configure(bg=self.bg, fg=self.fg)
        self.weight_label.configure(bg=self.bg, fg=self.fg)
        self.time_label.configure(bg=self.bg, fg=self.fg)

        # Update progress bar style if needed (requires ttk.Style)
        # from tkinter.ttk import Style
        # style = Style()
        # style.configure("TProgressbar", background=self.splash)

        # Update selection dot and box
        icon_x = 52.5
        icon_centers = [60, 120, 180]
        dot_radius = 5
        dot_x = icon_x - 45
        dot_y = icon_centers[self.selected_index]
        self.icon_canvas.itemconfig(self.selection_dot, fill=self.fg)

        # If you have other widgets that need color updates, add them here

    def set_color_scheme(self, scheme):
        self.bg = scheme["bg"]
        self.fg = scheme["fg"]
        self.splash = scheme["splash"]
        self.apply_color_scheme()  # Apply the new colors

    def show_overlay(self, main_message, sub_message=""):
        # Destroy any existing overlay
        if hasattr(self, "overlay") and self.overlay.winfo_exists():
            self.overlay.destroy()

        self.overlay = Toplevel(self.master)
        self.overlay.transient(self.master)
        self.overlay.grab_set()
        self.overlay.attributes("-topmost", True)
        self.overlay.overrideredirect(True)

        w, h = 400, 200
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (w // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (h // 2)
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")
        self.overlay.lift()

        # Add outline using fg color
        outline_frame = Frame(self.overlay, bg=self.fg, bd=0)
        outline_frame.pack(expand=True, fill="both", padx=6, pady=6)

        frame = Frame(outline_frame, bg=self.bg)
        frame.pack(expand=True, fill="both", padx=2, pady=2)

        label = Label(frame, text=main_message, font=('Cascadia Code SemiBold', 28), bg=self.bg, fg=self.fg)
        label.pack(pady=10)

        sublabel = Label(frame, text=sub_message, font=('Cascadia Code SemiBold', 24), bg=self.bg, fg=self.fg)
        sublabel.pack(pady=10)

    def close_overlay(self):
        if hasattr(self, "overlay") and self.overlay.winfo_exists():
            self.overlay.destroy()

# This block runs the GUI application if the script is executed directly.
if __name__ == "__main__":
    root = Tk()  # Create the root Tkinter window.
    app = RelayControlApp(root)  # Create an instance of the RelayControlApp class.

    # Demo messages to cycle through
    demo_messages = [
        ("SET TARGET WEIGHT", "500g"),
        ("SET TIME LIMIT", "3.00s"),
        ("ESTOP ACTIVATED", ""),
    ]
    demo_index = [0]  # Use a list for mutability in nested function

    def auto_cycle_demo():
        # Cycle color scheme
        app.color_scheme_index = (app.color_scheme_index + 1) % len(COLOR_SCHEMES)
        app.set_color_scheme(COLOR_SCHEMES[app.color_scheme_index])
        app.reload_main_screen()

        # Cycle message
        msg, submsg = demo_messages[demo_index[0]]
        app.show_overlay(msg, submsg)
        demo_index[0] = (demo_index[0] + 1) % len(demo_messages)

        root.after(3000, auto_cycle_demo)

    # Simulate progress as before (optional, or you can comment it out if not needed)
    def simulate_progress():
        current_weight = getattr(app, "current_weight", 0)
        target_weight = 300
        if current_weight < target_weight:
            app.current_weight = current_weight + 1.5
            current_weight = app.current_weight
            app.weight_fraction_var.set(f"{current_weight:.1f} / {target_weight}")
            progress = (current_weight / target_weight) * 100 if target_weight > 0 else 0
            app.set_progress(progress)
            root.after(33, simulate_progress)

    app.progress = 0
    app.time_remaining = 100
    app.current_weight = 0

    auto_cycle_demo()
    # simulate_progress()  # Uncomment if you want to see the progress bar as well

    root.mainloop()  # Start the Tkinter event loop to display the GUI.