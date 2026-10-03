import tkinter as tk
import traceback
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import database
# --- THE FIX: Pointing to the new employee_parts folder ---
from views.employee_parts.employee_tab import EmployeeTab

class EmployeesView(tk.Frame):
    def __init__(self, parent):
        is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        bg_color = "#0f172a" if is_dark else "#e0f2fe"
        super().__init__(parent, bg=bg_color)
        
        try:
            tab = EmployeeTab(self)
            tab.pack(fill="both", expand=True)
        except Exception as e:
            tk.Label(self, text=f"FATAL ERROR:\n\n{str(e)}\n\n{traceback.format_exc()}", fg="red", bg=bg_color, justify="left").pack(fill="both", expand=True, padx=20, pady=20)