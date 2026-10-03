import tkinter as tk
import calendar
from datetime import datetime
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(parent_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import fetch_global_settings

class NativeCalendar(tk.Toplevel):
    def __init__(self, parent, target_var, anchor_widget=None, ref_date_var=None):
        super().__init__(parent)
        self.target_var = target_var
        self.title("Select Date")
        self.geometry("280x280")
        self.resizable(False, False)
        self.configure(bg="#ffffff")
        
        self.update_idletasks()
        w = 280
        h = 280
        
        if anchor_widget:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
            
            if x + w > self.winfo_screenwidth(): x = self.winfo_screenwidth() - w - 10
            if y + h > self.winfo_screenheight(): y = anchor_widget.winfo_rooty() - h - 2
                
            self.geometry(f"+{x}+{y}")
        else:
            x = (self.winfo_screenwidth() // 2) - (w // 2)
            y = (self.winfo_screenheight() // 2) - (h // 2)
            self.geometry(f"+{x}+{y}")
            
        self.grab_set()

        self.mode = "days"
        self.year_view_start = 0

        # --- THE BULLETPROOF FIX: Guaranteed Root Window Traversal ---
        comp_id = 1
        widget = parent
        while widget:
            if hasattr(widget, "active_company_id"):
                comp_id = getattr(widget, "active_company_id")
                break
            if hasattr(widget, "comp_id"):
                comp_id = getattr(widget, "comp_id")
                break
            widget = widget.master
            
        _, self.date_fmt_code = fetch_global_settings(comp_id)
        # -------------------------------------------------------------

        now = datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        
        self.selected_day = None
        self.selected_month = None
        self.selected_year = None
        
        self.ref_day = None
        self.ref_month = None
        self.ref_year = None
        
        if ref_date_var:
            ref_val = ref_date_var.get().strip()
            if ref_val:
                try:
                    dt = datetime.strptime(ref_val, self.date_fmt_code)
                    self.ref_day = dt.day
                    self.ref_month = dt.month
                    self.ref_year = dt.year
                except: pass
        
        curr_val = target_var.get().strip()
        if curr_val:
            try:
                dt = datetime.strptime(curr_val, self.date_fmt_code)
                self.current_year = dt.year
                self.current_month = dt.month
                self.selected_day = dt.day
                self.selected_month = dt.month
                self.selected_year = dt.year
            except: pass

        self.build_ui()

    def build_ui(self):
        for widget in self.winfo_children(): widget.destroy()

        header = tk.Frame(self, bg="#1a237e", pady=5)
        header.pack(fill="x")

        tk.Button(header, text="◀", bg="#1a237e", fg="#ffffff", relief="flat", borderwidth=0, cursor="hand2", command=self.prev_action).pack(side="left", padx=10)
        
        title_text = f"{calendar.month_name[self.current_month]} {self.current_year}" if self.mode == "days" else f"{self.year_view_start} - {self.year_view_start + 11}"
        
        btn_title = tk.Button(header, text=title_text, bg="#1a237e", fg="#ffffff", font=("Arial", 10, "bold"), relief="flat", borderwidth=0, cursor="hand2", command=self.toggle_mode)
        btn_title.pack(side="left", expand=True)
        
        tk.Button(header, text="▶", bg="#1a237e", fg="#ffffff", relief="flat", borderwidth=0, cursor="hand2", command=self.next_action).pack(side="right", padx=10)

        body = tk.Frame(self, bg="#ffffff")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        if self.mode == "days":
            days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
            for i, d in enumerate(days):
                tk.Label(body, text=d, font=("Arial", 9, "bold"), fg="#757575", bg="#ffffff").grid(row=0, column=i, sticky="nsew")

            cal = calendar.monthcalendar(self.current_year, self.current_month)
            now = datetime.now()
            
            for row_idx, week in enumerate(cal):
                for col_idx, day in enumerate(week):
                    if day != 0:
                        bg_c = "#ffffff"
                        fg_c = "#000000"
                        
                        is_selected = (day == self.selected_day and self.current_month == self.selected_month and self.current_year == self.selected_year)
                        is_ref = (day == self.ref_day and self.current_month == self.ref_month and self.current_year == self.ref_year)
                        
                        if is_selected or is_ref:
                            bg_c = "#facc15" 
                            fg_c = "#0f172a"
                        elif day == now.day and self.current_month == now.month and self.current_year == now.year:
                            bg_c = "#1a237e" 
                            fg_c = "#ffffff"
                            
                        btn = tk.Button(body, text=str(day), bg=bg_c, fg=fg_c, relief="flat", borderwidth=0, cursor="hand2", command=lambda d=day: self.select_date(d))
                        btn.grid(row=row_idx+1, column=col_idx, sticky="nsew", padx=1, pady=1)
                        
                        if bg_c == "#ffffff":
                            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#e8eaf6"))
                            btn.bind("<Leave>", lambda e, b=btn, c=bg_c: b.config(bg=c))
            
            for i in range(7): body.columnconfigure(i, weight=1)
            for i in range(7): body.rowconfigure(i, weight=1)

        else:
            for i in range(12):
                y = self.year_view_start + i
                r, c = divmod(i, 3)
                btn = tk.Button(body, text=str(y), bg="#ffffff", fg="#000000", font=("Arial", 10), relief="flat", borderwidth=0, cursor="hand2", command=lambda yr=y: self.select_year(yr))
                btn.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#e8eaf6"))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#ffffff"))
                
            for i in range(3): body.columnconfigure(i, weight=1)
            for i in range(4): body.rowconfigure(i, weight=1)

    def toggle_mode(self):
        if self.mode == "days":
            self.mode = "years"
            self.year_view_start = self.current_year - (self.current_year % 10)
        else:
            self.mode = "days"
        self.build_ui()

    def prev_action(self):
        if self.mode == "days":
            self.current_month -= 1
            if self.current_month < 1:
                self.current_month = 12
                self.current_year -= 1
        else:
            self.year_view_start -= 12
        self.build_ui()

    def next_action(self):
        if self.mode == "days":
            self.current_month += 1
            if self.current_month > 12:
                self.current_month = 1
                self.current_year += 1
        else:
            self.year_view_start += 12
        self.build_ui()

    def select_year(self, y):
        self.current_year = y
        self.mode = "days"
        self.build_ui()

    def select_date(self, day):
        dt = datetime(self.current_year, self.current_month, day)
        final_str = dt.strftime(self.date_fmt_code)
            
        self.target_var.set(final_str)
        self.destroy()