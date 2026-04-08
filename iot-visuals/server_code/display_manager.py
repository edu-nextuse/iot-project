import tkinter as tk
from threading import Thread
# Dit wordt momenteel niet gebruikt
class StatusWindow:
    def __init__(self):
        self.root = None
        self.label = None
        # Start the window in a separate thread so it doesn't freeze Flask
        self.thread = Thread(target=self._setup_window, daemon=True)
        self.thread.start()

    def _setup_window(self):
        self.root = tk.Tk()
        self.root.title("Pico Status")
        self.root.geometry("400x400")
        self.root.attributes("-topmost", True) # Keep it on top
        
        self.label = tk.Label(self.root, text="Setup", font=("Arial", 100))
        self.label.pack(expand=True)
        self.root.mainloop()

    # --- Thread-Safe Triggers ---
    def show_ok(self):
        if self.root and self.label:
            # Schedule the update on the Tkinter main thread
            self.root.after(0, self._update_ok)

    def show_warning(self):
        if self.root and self.label:
            # Schedule the update on the Tkinter main thread
            self.root.after(0, self._update_warning)

    def show_carefull(self):
        if self.root and self.label:
            self.root.after(0, self._update_carefull)

    # --- Actual GUI Updates ---
    def _update_ok(self):
        self.label.config(text="✅", fg="green")
        self.root.configure(bg="green")

    def _update_warning(self):
        self.label.config(text="❌", fg="red")
        self.root.configure(bg="red")

    def _update_carefull(self):
        self.label.config(text="⚠️", fg="orange")
        self.root.configure(bg="orange")
# Create a single instance to be used by the server
visuals = StatusWindow()