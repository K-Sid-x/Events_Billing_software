import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import csv
import traceback
import tempfile
import webbrowser
from datetime import date, datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.gst_parts import gst_drilldown
from views.invoice_parts.helpers import format_currency, fetch_global_settings, smart_date_formatter
from views.home_parts.ui_components import get_theme

def bind_table_scroll(tree):
    def _scroll_y(event):
        import os
        delta = int(-1 * (event.delta / 120)) if os.name == 'nt' else int(-1 * event.delta)
        tree.yview_scroll(delta, "units")
        return "break"
        
    def _scroll_x(event):
        import os
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        # Buttery smooth fractional glide for horizontal panning
        tree.xview_moveto(tree.xview()[0] + (delta * 0.015))
        return "break"
        
    tree.bind("<MouseWheel>", _scroll_y)
    tree.bind("<Shift-MouseWheel>", _scroll_x)

class GSTReportView(tk.Frame):
    def __init__(self, parent):
        self.t = get_theme() # --- THE FIX: Dynamic UI Theme integration ---
        super().__init__(parent, bg=self.t["bg"])
        
        self.is_bulk_mode = tk.BooleanVar(value=False)
        self.selected_iids = set()
        
        try:
            self.app = self.winfo_toplevel()
            self.comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
            self.period_mode = tk.StringVar(value="Monthly") 

            self.build_ui()
            self.load_data()
        except Exception as e:
            tk.Label(self, text=f"ERROR LOADING GST REPORT:\n\n{str(e)}\n\n{traceback.format_exc()}", fg=self.t["error"], bg=self.t["bg"], justify="left").pack(padx=20, pady=20)

    

    def build_ui(self):
        style = ttk.Style(self)
        
        self.app.option_add('*TCombobox*Listbox.background', self.t["card"])
        self.app.option_add('*TCombobox*Listbox.foreground', self.t["text"])
        self.app.option_add('*TCombobox*Listbox.selectBackground', self.t["accent_blue"])
        self.app.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        
        style.configure("GST.TCombobox", fieldbackground=self.t["card"], background=self.t["card"], foreground=self.t["text"], arrowcolor=self.t["text"], bordercolor=self.t["border"])
        style.map("GST.TCombobox", fieldbackground=[("readonly", self.t["card"])], selectbackground=[("readonly", self.t["accent_blue"])], selectforeground=[("readonly", "#ffffff")])
        
        main_container = tk.Frame(self, bg=self.t["bg"], padx=30, pady=30)
        main_container.pack(fill="both", expand=True)

        header_f = tk.Frame(main_container, bg=self.t["bg"])
        header_f.pack(fill="x", pady=(0, 25))
        
        tk.Label(header_f, text="GST Report", font=("Arial", 28, "bold"), bg=self.t["bg"], fg=self.t["text"]).pack(anchor="w")
        tk.Label(header_f, text="Output GST vs Input GST. Double-click any row to view full bill-wise details.", font=("Arial", 11), bg=self.t["bg"], fg=self.t["sec"]).pack(anchor="w", pady=(5, 0))

        summary_f = tk.Frame(main_container, bg=self.t["bg"])
        summary_f.pack(fill="x", pady=(0, 25))

        frame_out, self.lbl_output = self.create_big_tile(summary_f, "OUTPUT GST (SALES)", "0.00", self.t["accent_blue"])
        frame_out.pack(side="left", expand=True, fill="both", padx=(0, 10))

        frame_in, self.lbl_input = self.create_big_tile(summary_f, "INPUT GST (PURCHASES)", "0.00", self.t["accent_green"])
        frame_in.pack(side="left", expand=True, fill="both", padx=10)

        frame_net, self.lbl_net = self.create_big_tile(summary_f, "NET GST PAYABLE", "0.00", self.t["error"])
        frame_net.pack(side="left", expand=True, fill="both", padx=(10, 0))

        action_f = tk.Frame(main_container, bg=self.t["bg"])
        action_f.pack(fill="x", pady=(0, 15))

        tab_container = tk.Frame(action_f, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        tab_container.pack(side="left")

        self.btn_monthly = tk.Button(tab_container, text="Monthly", font=("Arial", 11, "bold"), bg=self.t["border"], fg=self.t["text"], relief="flat", bd=0, padx=25, pady=8, cursor="hand2", command=lambda: self.set_period("Monthly"))
        self.btn_monthly.pack(side="left")
        
        self.btn_quarterly = tk.Button(tab_container, text="Quarterly", font=("Arial", 11), bg=self.t["card"], fg=self.t["sec"], relief="flat", bd=0, padx=25, pady=8, cursor="hand2", command=lambda: self.set_period("Quarterly"))
        self.btn_quarterly.pack(side="left")

        self.btn_annual = tk.Button(tab_container, text="Annual", font=("Arial", 11), bg=self.t["card"], fg=self.t["sec"], relief="flat", bd=0, padx=25, pady=8, cursor="hand2", command=lambda: self.set_period("Annual"))
        self.btn_annual.pack(side="left")

        self.fy_mode_var = tk.StringVar(value="All")
        self.fy_mode_cb = ttk.Combobox(action_f, textvariable=self.fy_mode_var, values=["All", "Custom FY"], state="readonly", width=10, font=("Arial", 11), style="GST.TCombobox", cursor="hand2")
        self.fy_mode_cb.pack(side="left", padx=(15, 5), ipady=5)

        self.fy_var = tk.StringVar()
        curr_year = datetime.now().year
        curr_month = datetime.now().month
        max_year = curr_year if curr_month >= 4 else curr_year - 1
        self.fy_var.set(f"{max_year}-{max_year+1}")
        fy_list = [f"{y}-{y+1}" for y in range(2023, max_year + 1)]

        self.fy_cb = ttk.Combobox(action_f, textvariable=self.fy_var, values=fy_list, state="readonly", width=12, font=("Arial", 11), style="GST.TCombobox", cursor="hand2")
        self.btn_cancel_fy = tk.Button(action_f, text="✖", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["error"], relief="solid", bd=1, cursor="hand2", command=lambda: cancel_custom_fy())

        def clear_cb_selection(*args):
            self.fy_mode_cb.selection_clear()
            self.fy_cb.selection_clear()

        def drop_focus():
            self.app.focus_set()

        def cancel_custom_fy():
            self.fy_mode_var.set("All")
            self.fy_cb.pack_forget()
            self.btn_cancel_fy.pack_forget()
            self.load_data(reset_page=True)
            drop_focus()

        def on_fy_mode_change(e):
            if self.fy_mode_var.get() == "Custom FY":
                self.fy_cb.pack(side="left", padx=(0, 5), ipady=5, after=self.fy_mode_cb)
                self.btn_cancel_fy.pack(side="left", padx=(0, 10), ipady=3, after=self.fy_cb)
            else:
                self.fy_cb.pack_forget()
                self.btn_cancel_fy.pack_forget()
            self.load_data(reset_page=True)
            drop_focus()

        self.fy_mode_cb.bind("<<ComboboxSelected>>", on_fy_mode_change)
        self.fy_cb.bind("<<ComboboxSelected>>", lambda e: [self.load_data(reset_page=True), drop_focus()])
        self.fy_mode_cb.bind("<FocusIn>", lambda e: self.after(10, clear_cb_selection))
        self.fy_cb.bind("<FocusIn>", lambda e: self.after(10, clear_cb_selection))

        self.tools_container = tk.Frame(action_f, bg=self.t["bg"])
        self.tools_container.pack(side="right", fill="y")

        self.std_tools = tk.Frame(self.tools_container, bg=self.t["bg"])
        self.std_tools.pack(side="right", fill="y")

        btn_export_pdf = tk.Button(self.std_tools, text="🖨 Export PDF", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", highlightbackground=self.t["border"], highlightthickness=1, cursor="hand2", padx=20, pady=7, command=self.export_pdf)
        btn_export_pdf.pack(side="right")

        btn_export_csv = tk.Button(self.std_tools, text="📥 Export CSV", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", highlightbackground=self.t["border"], highlightthickness=1, cursor="hand2", padx=20, pady=7, command=self.export_csv)
        btn_export_csv.pack(side="right", padx=(0, 10))

        self.bulk_tools = tk.Frame(self.tools_container, bg=self.t["bg"])

        btn_bulk_pdf = tk.Button(self.bulk_tools, text="🖨 Export PDF", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=7, command=self.export_pdf)
        btn_bulk_pdf.pack(side="right")

        btn_bulk_csv = tk.Button(self.bulk_tools, text="📥 Export CSV", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=7, command=self.export_csv)
        btn_bulk_csv.pack(side="right", padx=(0, 10))

        btn_bulk_cancel = tk.Button(self.bulk_tools, text="✖ Cancel", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["error"], relief="solid", bd=1, cursor="hand2", padx=15, pady=7, command=lambda: self.cancel_bulk_mode())
        btn_bulk_cancel.pack(side="right", padx=(0, 10))

        self.btn_select_all = tk.Button(self.bulk_tools, text="☑ Select All", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=7, command=lambda: self.toggle_select_all())
        self.btn_select_all.pack(side="right", padx=(0, 10))

        self.lbl_bulk_count = tk.Label(self.bulk_tools, text="0 Selected", font=("Arial", 11, "bold"), bg=self.t["bg"], fg=self.t["accent_blue"])
        self.lbl_bulk_count.pack(side="right", padx=(0, 15))

        self.pag_state = {"current": 1, "total": 1, "per_page": 50}
        pag_frame = tk.Frame(main_container, bg=self.t["bg"])
        pag_frame.pack(side="bottom", fill="x", pady=(10, 0))

        center_pag = tk.Frame(pag_frame, bg=self.t["bg"])
        center_pag.pack(anchor="center")

        self.btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="flat", cursor="hand2", padx=12, pady=3, command=lambda: self.go_prev())
        self.btn_prev.pack(side="left", padx=5)

        self.lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=self.t["bg"], fg=self.t["sec"])
        self.lbl_page.pack(side="left", padx=15)

        self.btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="flat", cursor="hand2", padx=12, pady=3, command=lambda: self.go_next())
        self.btn_next.pack(side="left", padx=5)

        self.table_f = tk.Frame(main_container, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        self.table_f.pack(fill="both", expand=True)
        table_f = self.table_f
        
        self.table_header_lbl = tk.Label(table_f, text="Displaying All Data", font=("Arial", 12, "bold"), bg=self.t["card"], fg=self.t["accent_blue"])
        self.table_header_lbl.pack(anchor="w", padx=15, pady=(15, 5))

        style.configure("GST.Treeview.Heading", font=("Arial", 10, "bold"), background=self.t["header"], foreground=self.t["text"], borderwidth=1, relief="raised")
        style.map("GST.Treeview.Heading", background=[('active', self.t["border"])])
        style.configure("GST.Treeview", font=("Arial", 11), rowheight=45, background=self.t["card"], fieldbackground=self.t["card"], foreground=self.t["text"], borderwidth=0)
        style.map("GST.Treeview", background=[("selected", self.t["border"])], foreground=[("selected", "#ffffff")])

        # --- CUSTOM SCROLLBARS FOR GST REPORT ---
        style.configure("GST.Vertical.TScrollbar", background=self.t["sec"], troughcolor=self.t["card"], bordercolor=self.t["card"], arrowcolor=self.t["text"], relief="flat")
        style.configure("GST.Horizontal.TScrollbar", background=self.t["sec"], troughcolor=self.t["card"], bordercolor=self.t["card"], arrowcolor=self.t["text"], relief="flat")
        style.map("GST.Vertical.TScrollbar", background=[("active", self.t["accent_blue"])])
        style.map("GST.Horizontal.TScrollbar", background=[("active", self.t["accent_blue"])])
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="GST.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="GST.Horizontal.TScrollbar")
        
        cols = ("sl", "period", "tax_sales", "out_gst", "tax_purch", "in_gst", "net_pay", "refund", "pending_action", "ghost")
        self.tree = ttk.Treeview(table_f, columns=cols, show="headings", height=10, style="GST.Treeview", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        self.tree.pack(side="left", fill="both", expand=True)
        bind_table_scroll(self.tree)

        self.tree.heading("sl", text="SL. NO.", anchor="center")
        self.tree.heading("period", text="PERIOD", anchor="w")
        self.tree.heading("tax_sales", text="TOTAL TAXABLE SALES", anchor="e")
        self.tree.heading("out_gst", text="OUTPUT GST", anchor="e")
        self.tree.heading("tax_purch", text="TOTAL TAXABLE PURCHASES", anchor="e")
        self.tree.heading("in_gst", text="INPUT GST", anchor="e")
        self.tree.heading("net_pay", text="NET PAYABLE", anchor="e")
        self.tree.heading("refund", text="REFUND", anchor="e")
        self.tree.heading("pending_action", text="STATUS", anchor="center")
        self.tree.heading("ghost", text="")

        self.tree["displaycolumns"] = cols
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"gst_report_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            saved_w = json.loads(res[0]) if res and res[0] else {}
        except:
            saved_w = {}

        self.tree.column("sl", width=saved_w.get("sl", 60), minwidth=60, anchor="center", stretch=False)
        self.tree.column("period", width=saved_w.get("period", 140), minwidth=80, anchor="w", stretch=False)
        self.tree.column("tax_sales", width=saved_w.get("tax_sales", 160), minwidth=80, anchor="e", stretch=False)
        self.tree.column("out_gst", width=saved_w.get("out_gst", 160), minwidth=80, anchor="e", stretch=False)
        self.tree.column("tax_purch", width=saved_w.get("tax_purch", 180), minwidth=80, anchor="e", stretch=False)
        self.tree.column("in_gst", width=saved_w.get("in_gst", 160), minwidth=80, anchor="e", stretch=False)
        self.tree.column("net_pay", width=saved_w.get("net_pay", 160), minwidth=80, anchor="e", stretch=False)
        self.tree.column("refund", width=saved_w.get("refund", 120), minwidth=80, anchor="e", stretch=False)
        self.tree.column("pending_action", width=saved_w.get("pending_action", 160), minwidth=120, anchor="center", stretch=False)
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)

        def save_report_widths():
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c != "ghost"}
            try:
                database.save_ui_setting(f"gst_report_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_report_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_report_widths)

        self.tree.bind("<B1-Motion>", on_report_sep_drag, add="+")

        self.tree.tag_configure("evenrow", background=self.t["bg"]) 
        self.tree.tag_configure("oddrow", background=self.t["card"])  
        # --- THE HIGH CONTRAST FIX ---
        self.tree.tag_configure("header_row", background=self.t["border"], foreground=self.t["text"], font=("Arial", 11, "bold"))  
        # -----------------------------

        def on_tree_click(event):
            region = self.tree.identify("region", event.x, event.y)
            if region == "cell":
                iid = self.tree.identify_row(event.y)
                if iid and 'empty' not in self.tree.item(iid, 'tags') and 'header_row' not in self.tree.item(iid, 'tags'):
                    if self.is_bulk_mode.get():
                        if iid in self.selected_iids: self.selected_iids.remove(iid)
                        else: self.selected_iids.add(iid)
                        vals = list(self.tree.item(iid, "values"))
                        vals[0] = "[✓]" if iid in self.selected_iids else "[  ]"
                        self.tree.item(iid, values=vals)
                        self.update_bulk_count()

        def on_right_click(event):
            iid = self.tree.identify_row(event.y)
            if not iid or 'empty' in self.tree.item(iid, 'tags') or 'header_row' in self.tree.item(iid, 'tags'): return
            
            self.tree.selection_set(iid)
            menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.t["card"], fg=self.t["text"])
            
            if not self.is_bulk_mode.get():
                menu.add_command(label="📄 Export This Period", command=lambda: self.trigger_single_export(iid, event))
                menu.add_separator()
                menu.add_command(label="☑️ Bulk Export", command=self.enable_bulk_mode)
            else:
                menu.add_command(label="❌ Cancel Bulk Selection", command=self.cancel_bulk_mode)
                
            menu.tk_popup(event.x_root, event.y_root)

        self.tree.bind("<ButtonRelease-1>", on_tree_click, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after(50, save_report_widths) if self.tree.identify_region(e.x, e.y) == "separator" else None, add="+")
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", on_right_click)

        def prevent_empty_select(event):
            for iid in self.tree.selection():
                if 'empty' in self.tree.item(iid, 'tags') or 'header_row' in self.tree.item(iid, 'tags'):
                    self.tree.selection_remove(iid)
        self.tree.bind("<<TreeviewSelect>>", prevent_empty_select)

        def on_motion(event):
            region = self.tree.identify("region", event.x, event.y)
            if region == "cell": 
                iid = self.tree.identify_row(event.y)
                if iid and 'empty' not in self.tree.item(iid, 'tags') and 'header_row' not in self.tree.item(iid, 'tags'):
                    self.tree.config(cursor="hand2")
                else: self.tree.config(cursor="")
            else: self.tree.config(cursor="")
        self.tree.bind("<Motion>", on_motion)

    def enable_bulk_mode(self):
        self.is_bulk_mode.set(True)
        self.selected_iids.clear()
        self.std_tools.pack_forget()
        self.bulk_tools.pack(side="right", fill="y")
        self.tree.heading("sl", text="☑ SELECT")
        self.update_bulk_count()
        self.load_data(reset_page=False)

    def cancel_bulk_mode(self):
        self.is_bulk_mode.set(False)
        self.selected_iids.clear()
        self.bulk_tools.pack_forget()
        self.std_tools.pack(side="right", fill="y")
        self.tree.heading("sl", text="SL. NO.")
        self.load_data(reset_page=False)

    def update_bulk_count(self):
        self.lbl_bulk_count.config(text=f"{len(self.selected_iids)} Selected")

    def toggle_select_all(self):
        visible_iids = [child for child in self.tree.get_children() if 'empty' not in self.tree.item(child, 'tags') and 'header_row' not in self.tree.item(child, 'tags')]
        visible_set = set(visible_iids)
        if visible_set.issubset(self.selected_iids) and visible_set:
            self.selected_iids -= visible_set
        else:
            self.selected_iids |= visible_set
        self.update_bulk_count()
        self.load_data(reset_page=False)

    def go_prev(self):
        if self.pag_state["current"] > 1:
            self.pag_state["current"] -= 1
            self.load_data(reset_page=False)

    def go_next(self):
        if self.pag_state["current"] < self.pag_state["total"]:
            self.pag_state["current"] += 1
            self.load_data(reset_page=False)

    def trigger_single_export(self, iid, event):
        self.single_export_iid = iid
        menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.t["card"], fg=self.t["text"])
        menu.add_command(label="🖨 Export as PDF", command=self.export_pdf)
        menu.add_command(label="📥 Export as CSV", command=self.export_csv)
        menu.tk_popup(event.x_root, event.y_root)

    def create_big_tile(self, parent, title, value, color):
        f = tk.Frame(parent, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1, padx=30, pady=25)
        tk.Label(f, text=title, font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["sec"]).pack(anchor="w")
        lbl_val = tk.Label(f, text=value, font=("Arial", 32, "bold"), bg=self.t["card"], fg=color)
        lbl_val.pack(anchor="w", pady=(8,0))
        return f, lbl_val 

    def set_period(self, mode):
        self.period_mode.set(mode)
        for btn in [self.btn_monthly, self.btn_quarterly, self.btn_annual]:
            btn.config(font=("Arial", 11), bg=self.t["card"], fg=self.t["sec"])
            
        if mode == "Monthly": self.btn_monthly.config(font=("Arial", 11, "bold"), bg=self.t["border"], fg=self.t["text"])
        elif mode == "Quarterly": self.btn_quarterly.config(font=("Arial", 11, "bold"), bg=self.t["border"], fg=self.t["text"])
        elif mode == "Annual": self.btn_annual.config(font=("Arial", 11, "bold"), bg=self.t["border"], fg=self.t["text"])
        
        self.load_data(reset_page=True)

    def safe_float(self, val):
        if val is None or str(val).strip() == "": return 0.0
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '').strip())
        except: return 0.0

    def parse_date(self, date_str):
        if not date_str: return None
        date_str = str(date_str).strip()
        formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]
        for fmt in formats:
            try: return datetime.strptime(date_str, fmt).date()
            except: pass
        return None

    def get_period_key(self, dt_obj):
        mode = self.period_mode.get()
        if dt_obj.month >= 4: fy = dt_obj.year
        else: fy = dt_obj.year - 1
        fy_str = f"{fy}-{fy+1}"
        
        if mode == "Monthly": return dt_obj.strftime("%Y-%m"), fy_str
        elif mode == "Quarterly":
            if dt_obj.month in [4, 5, 6]: q = 1
            elif dt_obj.month in [7, 8, 9]: q = 2
            elif dt_obj.month in [10, 11, 12]: q = 3
            else: q = 4
            return f"Q{q}", fy_str
        else: return fy_str, fy_str

    def load_data(self, reset_page=True):
        if reset_page: self.pag_state["current"] = 1
        for item in self.tree.get_children(): self.tree.delete(item)
        
        periods = {}
        
        is_custom = self.fy_mode_var.get() == "Custom FY"
        if is_custom:
            y1, y2 = map(int, self.fy_var.get().split('-'))
            fy_start = date(y1, 4, 1)
            fy_end = date(y2, 3, 31)
            self.table_header_lbl.config(text=f"Displaying Data for Financial Year: {self.fy_var.get()}")
        else:
            self.table_header_lbl.config(text="Displaying All Available Data")
            
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT invoice_date, subtotal, (COALESCE(cgst,0) + COALESCE(sgst,0) + COALESCE(igst,0)) as total_gst, COALESCE(ca_submitted, 0) FROM invoices WHERE company_id=? AND COALESCE(is_deleted, 0) = 0 AND LOWER(COALESCE(status, '')) != 'draft'", (self.comp_id,))
            for row in c.fetchall():
                dt = self.parse_date(row[0])
                if not dt: dt = date.today()
                if is_custom and not (fy_start <= dt <= fy_end): continue
                
                p_key, fy_str = self.get_period_key(dt)
                if p_key not in periods: periods[p_key] = {"tax_sales": 0.0, "out_gst": 0.0, "tax_purch": 0.0, "in_gst": 0.0, "pending": 0, "fy": fy_str}
                periods[p_key]["tax_sales"] += self.safe_float(row[1])
                periods[p_key]["out_gst"] += self.safe_float(row[2])
                if int(row[3]) == 0: periods[p_key]["pending"] += 1

            c.execute("SELECT purchase_date, subtotal, (COALESCE(cgst,0) + COALESCE(sgst,0) + COALESCE(igst,0)) as total_gst, COALESCE(ca_submitted, 0) FROM purchases WHERE company_id=? AND COALESCE(is_deleted, 0) = 0 AND COALESCE(is_draft, 0) = 0 AND LOWER(COALESCE(status, '')) != 'draft'", (self.comp_id,))
            for row in c.fetchall():
                dt = self.parse_date(row[0])
                if not dt: dt = date.today()
                if is_custom and not (fy_start <= dt <= fy_end): continue
                
                p_key, fy_str = self.get_period_key(dt)
                if p_key not in periods: periods[p_key] = {"tax_sales": 0.0, "out_gst": 0.0, "tax_purch": 0.0, "in_gst": 0.0, "pending": 0, "fy": fy_str}
                periods[p_key]["tax_purch"] += self.safe_float(row[1])
                periods[p_key]["in_gst"] += self.safe_float(row[2])
                if int(row[3]) == 0: periods[p_key]["pending"] += 1
                
            conn.close()
        except Exception as e: print("GST Load Error:", e)

        self.master_periods = periods
        sorted_keys = sorted(periods.keys(), key=lambda k: (periods[k]["fy"], k), reverse=True)
        self.master_sorted_keys = sorted_keys

        g_out_gst = g_in_gst = g_net = 0.0
        for p in sorted_keys:
            d = periods[p]
            g_out_gst += d["out_gst"]
            g_in_gst += d["in_gst"]
            g_net += (d["out_gst"] - d["in_gst"])

        self.lbl_output.config(text=format_currency(g_out_gst, self.curr_fmt))
        self.lbl_input.config(text=format_currency(g_in_gst, self.curr_fmt))
        if g_net >= 0: self.lbl_net.config(text=format_currency(g_net, self.curr_fmt), fg=self.t["error"])
        else: self.lbl_net.config(text=format_currency(abs(g_net), self.curr_fmt) + " (Refund)", fg=self.t["accent_green"])

        total_items = len(sorted_keys)
        self.pag_state["total"] = max(1, (total_items + self.pag_state["per_page"] - 1) // self.pag_state["per_page"])
        if self.pag_state["current"] > self.pag_state["total"]: self.pag_state["current"] = max(1, self.pag_state["total"])

        self.lbl_page.config(text=f"Page {self.pag_state['current']} of {self.pag_state['total']}")
        self.btn_prev.config(state="normal" if self.pag_state["current"] > 1 else "disabled", bg=self.t["card"] if self.pag_state["current"] > 1 else self.t["bg"])
        self.btn_next.config(state="normal" if self.pag_state["current"] < self.pag_state["total"] else "disabled", bg=self.t["card"] if self.pag_state["current"] < self.pag_state["total"] else self.t["bg"])

        start_idx = (self.pag_state["current"] - 1) * self.pag_state["per_page"]
        page_keys = sorted_keys[start_idx : start_idx + self.pag_state["per_page"]]

        current_fy = None
        actual_index = start_idx

        for p in page_keys:
            d = periods[p]
            fy = d["fy"]
            
            if self.period_mode.get() != "Annual" and fy != current_fy:
                self.tree.insert("", "end", values=("", f"🗓 FINANCIAL YEAR {fy}", "", "", "", "", "", "", "", ""), tags=("header_row", "empty"))
                current_fy = fy

            net = d["out_gst"] - d["in_gst"]
            payable = net if net > 0 else 0.0
            refund = abs(net) if net < 0 else 0.0
            pend_count = d["pending"]
            ca_text = f"⚠️ {pend_count} Pending" if pend_count > 0 else "✅ All Submitted"

            tag = "evenrow" if actual_index % 2 == 0 else "oddrow"
            sl_val = "[✓]" if p in self.selected_iids else "[  ]" if self.is_bulk_mode.get() else actual_index + 1

            self.tree.insert("", "end", iid=p, values=(sl_val, p, format_currency(d["tax_sales"], self.curr_fmt), format_currency(d["out_gst"], self.curr_fmt), format_currency(d["tax_purch"], self.curr_fmt), format_currency(d["in_gst"], self.curr_fmt), format_currency(payable, self.curr_fmt), format_currency(refund, self.curr_fmt), ca_text, ""), tags=(tag,))
            actual_index += 1

        for i in range(len(page_keys), self.pag_state["per_page"]):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", "end", values=("", "", "", "", "", "", "", "", "", ""), tags=(tag, "empty"))

    def on_double_click(self, event):
        item = self.tree.selection()
        if not item: return
        if 'empty' in self.tree.item(item[0], 'tags') or 'header_row' in self.tree.item(item[0], 'tags'): return
        period_key = item[0]
        
        pending_older = []
        for p in getattr(self, 'master_sorted_keys', []):
            d = getattr(self, 'master_periods', {}).get(p)
            if d and p < period_key and d["pending"] > 0:
                pending_older.append(f"• {p}: {d['pending']} Pending")
                    
        if pending_older:
            msg = f"Wait! You still have unsubmitted bills from previous periods:\n\n" + "\n".join(pending_older) + f"\n\nAre you sure you want to skip ahead and open {period_key}?"
            if not messagebox.askyesno("Past Due Warning", msg, parent=self.winfo_toplevel()): return
        
        gst_drilldown.show_drilldown_window(parent=self, period_key=period_key, comp_id=self.comp_id, curr_fmt=self.curr_fmt, date_fmt_code=self.date_fmt_code, period_mode_val=self.period_mode.get(), on_close_callback=lambda: self.load_data(reset_page=False))

    def get_export_items(self):
        items = []
        actual_index = 0
        keys_to_process = [self.single_export_iid] if getattr(self, 'single_export_iid', None) else getattr(self, 'master_sorted_keys', [])

        for p in keys_to_process:
            d = getattr(self, 'master_periods', {}).get(p)
            if not d: continue

            if self.is_bulk_mode.get() and p not in self.selected_iids and not getattr(self, 'single_export_iid', None):
                continue

            net = d["out_gst"] - d["in_gst"]
            payable = net if net > 0 else 0.0
            refund = abs(net) if net < 0 else 0.0
            pend_count = d["pending"]
            ca_text = f"⚠️ {pend_count} Pending" if pend_count > 0 else "✅ All Submitted"

            items.append([actual_index + 1, p, format_currency(d["tax_sales"], self.curr_fmt), format_currency(d["out_gst"], self.curr_fmt), format_currency(d["tax_purch"], self.curr_fmt), format_currency(d["in_gst"], self.curr_fmt), format_currency(payable, self.curr_fmt), format_currency(refund, self.curr_fmt), ca_text])
            actual_index += 1
            
        self.single_export_iid = None 
        return items

    def export_pdf(self):
        # --- THE FIX: Enforce Export Lock ---
        uid = int(getattr(self.app, 'current_user_id', 1))
        is_admin = str(uid) == "1"
        if not is_admin:
            u_row = database.get_user_by_id(uid)
            if u_row and u_row[3] == "Admin": is_admin = True
            
        if not is_admin:
            perms = database.get_user_permissions(uid)
            if perms.get("gst_rules", {}).get("lock_export", False):
                messagebox.showwarning("Access Restricted", "Exporting GST reports is locked for your account.\n\nPlease contact the Admin.", parent=self.winfo_toplevel())
                return
        # ------------------------------------

        items_to_export = self.get_export_items()
        is_annual = self.period_mode.get() == "Annual"
        
        if not items_to_export and not is_annual:
            msg = "Please explicitly check at least one month." if self.is_bulk_mode.get() else "No data found for the selected period."
            messagebox.showinfo("Empty Export", msg, parent=self.winfo_toplevel())
            return
            
        html = f"<html><head><title>GST Report ({self.period_mode.get().upper()})</title>"
        html += "<style>@page { size: landscape; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-top:20px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space:nowrap;} th{background-color:#f2f2f2;} .summary{width:40%; margin-bottom:20px;} .summary th, .summary td{text-align:left;}</style></head><body>"
        
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_timestamp = smart_date_formatter(current_timestamp, self.date_fmt_code)
        
        html += f"<h2>GST REPORT ({self.period_mode.get().upper()})</h2>"
        html += f"<p><b>Generated on:</b> {formatted_timestamp}</p>"
        
        html += "<table class='summary'>"
        html += "<tr><th colspan='2'>SUMMARY</th></tr>"
        html += f"<tr><td><b>Total Output GST</b></td><td>{self.lbl_output.cget('text')}</td></tr>"
        html += f"<tr><td><b>Total Input GST</b></td><td>{self.lbl_input.cget('text')}</td></tr>"
        html += f"<tr><td><b>Net Payable</b></td><td>{self.lbl_net.cget('text')}</td></tr>"
        html += "</table>"
        
        if not is_annual:
            html += "<table><tr><th>SL. NO.</th><th>PERIOD</th><th>TOTAL TAXABLE SALES</th><th>OUTPUT GST</th><th>TOTAL TAXABLE PURCHASES</th><th>INPUT GST</th><th>NET PAYABLE</th><th>REFUND</th><th>STATUS</th></tr>"
            for vals in items_to_export:
                html += "<tr>"
                for v in vals: html += f"<td>{v}</td>" 
                html += "</tr>"
            html += "</table>"
            
        html += "<script>window.onload=function(){window.print();}</script></body></html>"
        
        fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))
        
        # --- THE FIX: Log PDF Export ---
        database.log_audit("GST Report", "Compliance Export", f"{self.period_mode.get().upper()} Report", "Exported GST Summary as PDF.", 0.0, company_id=self.comp_id)
        # -------------------------------

    def export_csv(self):
        # --- THE FIX: Enforce Export Lock ---
        uid = int(getattr(self.app, 'current_user_id', 1))
        is_admin = str(uid) == "1"
        if not is_admin:
            u_row = database.get_user_by_id(uid)
            if u_row and u_row[3] == "Admin": is_admin = True
            
        if not is_admin:
            perms = database.get_user_permissions(uid)
            if perms.get("gst_rules", {}).get("lock_export", False):
                messagebox.showwarning("Access Restricted", "Exporting GST reports is locked for your account.\n\nPlease contact the Admin.", parent=self.winfo_toplevel())
                return
        # ------------------------------------

        items_to_export = self.get_export_items()
        is_annual = self.period_mode.get() == "Annual"
        
        if not items_to_export and not is_annual:
            msg = "Please explicitly check at least one month." if self.is_bulk_mode.get() else "No data found for the selected period."
            messagebox.showinfo("Empty Export", msg, parent=self.winfo_toplevel())
            return
            
        file_path = filedialog.asksaveasfilename(parent=self.winfo_toplevel(), defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export GST Report")
        if not file_path: return
            
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow([f"GST REPORT ({self.period_mode.get().upper()})"])
                
                current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                formatted_timestamp = smart_date_formatter(current_timestamp, self.date_fmt_code)
                writer.writerow(["Generated on", formatted_timestamp])
                writer.writerow([])
                
                writer.writerow(["SUMMARY"])
                writer.writerow(["Total Output GST", self.lbl_output.cget("text")])
                writer.writerow(["Total Input GST", self.lbl_input.cget("text")])
                writer.writerow(["Net Payable", self.lbl_net.cget("text")])
                writer.writerow([])
                
                if not is_annual:
                    writer.writerow(["SL. NO.", "PERIOD", "TOTAL TAXABLE SALES", "OUTPUT GST", "TOTAL TAXABLE PURCHASES", "INPUT GST", "NET PAYABLE", "REFUND", "STATUS"])
                    for vals in items_to_export:
                        writer.writerow(vals)
                        
            # --- THE FIX: Log CSV Export ---
            database.log_audit("GST Report", "Compliance Export", f"{self.period_mode.get().upper()} Report", "Exported GST Summary as CSV.", 0.0, company_id=self.comp_id)
            # -------------------------------
            messagebox.showinfo("Export Successful", f"GST Report exported to:\n{file_path}", parent=self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred:\n{str(e)}", parent=self.winfo_toplevel())