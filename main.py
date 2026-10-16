from src.app.gui import *

# Main app -------------
root=tk.Tk()
root.title("Character Editor")
app = EditorApp(root)
app.pack(fill="both", expand=True)
root.protocol("WM_DELETE_WINDOW", app.on_app_close)

root.mainloop()