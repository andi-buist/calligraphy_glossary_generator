from src.app.gui import *

# Main app -------------
root=tk.Tk()
root.title("Character Drawing Tool DEBUG")
drawing_tool = DrawingTool(root)
drawing_tool.pack(fill="both", expand=True)
root.protocol("WM_DELETE_WINDOW", drawing_tool.on_app_close)

root.mainloop()