import tkinter as tk
from tkinter import ttk
import os
import sys
import json
import traceback
from datetime import date, datetime, timedelta
import calendar

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
from views.invoice_parts.helpers import format_currency, fetch_global_settings, on_tree_hover
from views.invoice_parts.calendar_widget import NativeCalendar
from views.home_parts.ui_components import get_theme 

from views.pl_parts.charts import PLChartManager
from views.pl_parts.documents import PLDocumentManager

def bind_table_scroll(tree):
    def _scroll(event):
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    tree.bind("<MouseWheel>", _scroll)

class ProfitLossView(tk.Frame):
    def __init__(self, parent):
        self.t = get_theme() 
        self.is_dark = self.t["bg"] == "#0f172a"
        self.BG_COLOR = self.t["bg"]
        self.CARD_BG = self.t["card"]
        self.BORDER_COLOR = self.t["border"]
        self.TEXT_PRIMARY = self.t["text"]
        self.TEXT_SECONDARY = self.t["sec"]
        self.ACCENT_BLUE = self.t["accent_blue"]
        self.ACCENT_GREEN = self.t["accent_green"]
        self.ACCENT_RED = self.t["error"]
        self.HEADER_BG = self.t["header"]
        self.ACCENT_YELLOW = "#f59e0b"

        super().__init__(parent, bg=self.BG_COLOR)
        
        try:
            self.app = self.winfo_toplevel()
            comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)

            current_year_num = date.today().year
            self.available_years = ["All Years"] + [str(y) for y in range(current_year_num, 2019, -1)]
            self.months = ["All Months", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

            self.filter_year_var = tk.StringVar(value=str(current_year_num))
            self.filter_month_var = tk.StringVar(value=date.today().strftime("%B"))
            self.filter_start_var = tk.StringVar()
            self.filter_end_var = tk.StringVar()
            
            self.accounting_basis = tk.StringVar(value="Accrual") 
            # --- THE FIX: Inject Default Layout Toggle ---
            self.layout_var = tk.StringVar(value="T-Account (CA)")
            # ---------------------------------------------
            self.chart_data = {"COGS": 0.0, "OPEX": {}, "REVENUE": {}, "TREND": {}}

            self.filter_year_var.trace_add("write", lambda *a: self.load_data())
            self.layout_var.trace_add("write", lambda *a: self.load_data())
            self.filter_month_var.trace_add("write", lambda *a: self.load_data())
            self.filter_start_var.trace_add("write", lambda *a: self.load_data())
            self.filter_end_var.trace_add("write", lambda *a: self.load_data())
            self.accounting_basis.trace_add("write", lambda *a: self.load_data())

            # --- THE FIX: Load sequence corrected to prevent PyInstaller crash! ---
            self.build_ui()
            self.load_data()
            # ----------------------------------------------------------------------
            
        except Exception as e:
            tk.Label(self, text=f"ERROR LOADING P&L REPORT:\n\n{str(e)}\n\n{traceback.format_exc()}", fg=self.ACCENT_RED, bg=self.BG_COLOR, justify="left").pack(padx=20, pady=20)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default")
        
        self.app.option_add("*TCombobox*Listbox.background", self.CARD_BG)
        self.app.option_add("*TCombobox*Listbox.foreground", self.TEXT_PRIMARY)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.ACCENT_BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        style.configure("TCombobox", fieldbackground=self.BG_COLOR, background=self.CARD_BG, foreground=self.TEXT_PRIMARY, arrowcolor=self.TEXT_PRIMARY, bordercolor=self.BORDER_COLOR, lightcolor=self.BORDER_COLOR, darkcolor=self.BORDER_COLOR)
        style.map("TCombobox", fieldbackground=[("readonly", self.BG_COLOR)], selectbackground=[("readonly", self.BG_COLOR)], selectforeground=[("readonly", self.TEXT_PRIMARY)])

        # --- THE FIX: Perfectly matched scrollbar styling from stock.py! ---
        style.configure("PL.Vertical.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.configure("PL.Horizontal.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.map("PL.Vertical.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        style.map("PL.Horizontal.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        # -------------------------------------------------------------------

        main_container = tk.Frame(self, bg=self.BG_COLOR, padx=30, pady=30)
        main_container.pack(fill="both", expand=True)

        header_f = tk.Frame(main_container, bg=self.BG_COLOR)
        header_f.pack(fill="x", pady=(0, 15))
        
        title_f = tk.Frame(header_f, bg=self.BG_COLOR)
        title_f.pack(side="left")
        tk.Label(title_f, text="Profit & Loss Statement", font=("Arial", 28, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(anchor="w")
        tk.Label(title_f, text="Review Revenue, Direct Costs, and OPEX. Expand folders to see exact receipts.", font=("Arial", 11), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))

        filter_f = tk.Frame(main_container, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=15, pady=10)
        filter_f.pack(fill="x", pady=(0, 25))

        btn_f = tk.Frame(filter_f, bg=self.CARD_BG)
        btn_f.pack(side="right", padx=(5, 0))
        
        # --- THE FIX: Stripped borders to enforce Dark Mode styling & Swapped Buttons ---
        export_btn = tk.Button(btn_f, text="📥 Export ▼", font=("Arial", 9, "bold"), bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, activebackground=self.BG_COLOR, activeforeground=self.TEXT_PRIMARY, relief="flat", bd=0, highlightthickness=0, cursor="hand2", padx=10, pady=4)
        export_btn.pack(side="right", padx=(0, 0)) 
        exp_menu = tk.Menu(export_btn, tearoff=0, bg=self.CARD_BG, fg=self.TEXT_PRIMARY, activebackground=self.ACCENT_BLUE)
        exp_menu.add_command(label="Export as CSV", command=lambda: PLDocumentManager(self).export_csv())
        exp_menu.add_command(label="Export as PDF", command=lambda: PLDocumentManager(self).print_pdf())
        export_btn.bind("<Button-1>", lambda e: exp_menu.tk_popup(e.x_root, e.y_root))

        tk.Button(btn_f, text="📊 View Charts", font=("Arial", 9, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff", relief="flat", bd=0, highlightthickness=0, cursor="hand2", padx=15, pady=4, command=lambda: PLChartManager(self)).pack(side="right", padx=(0, 10))
        # -------------------------------------------------------------

        filters_left_f = tk.Frame(filter_f, bg=self.CARD_BG)
        filters_left_f.pack(side="left")

        # --- THE FIX: Reclaimed horizontal space by tightening combo boxes ---
        tk.Label(filters_left_f, text="Layout:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(side="left")
        layout_cb = ttk.Combobox(filters_left_f, textvariable=self.layout_var, values=["Modern (Vertical)", "T-Account (CA)"], font=("Arial", 9, "bold"), state="readonly", width=14, cursor="hand2")
        layout_cb.pack(side="left", padx=(2, 5))

        tk.Label(filters_left_f, text="│ Basis:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(side="left")
        basis_cb = ttk.Combobox(filters_left_f, textvariable=self.accounting_basis, values=["Accrual", "Cash"], font=("Arial", 9, "bold"), state="readonly", width=7, cursor="hand2")
        basis_cb.pack(side="left", padx=(2, 5))

        tk.Label(filters_left_f, text="│ 📅 Period:", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(0, 2))
        year_cb = ttk.Combobox(filters_left_f, textvariable=self.filter_year_var, values=self.available_years, font=("Arial", 10), state="readonly", width=5, cursor="hand2")
        year_cb.pack(side="left", padx=(2, 2))
        month_cb = ttk.Combobox(filters_left_f, textvariable=self.filter_month_var, values=self.months, font=("Arial", 10), state="readonly", width=10, cursor="hand2")
        month_cb.pack(side="left", padx=(0, 5))
        
        tk.Label(filters_left_f, text="│ Custom From:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(side="left", padx=(0, 2))
        sf_ent = tk.Entry(filters_left_f, textvariable=self.filter_start_var, font=("Arial", 10), width=10, bg=self.CARD_BG, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        sf_ent.pack(side="left", ipady=3)
        tk.Button(filters_left_f, text="▼", bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", bd=0, highlightthickness=0, cursor="hand2", command=lambda: NativeCalendar(self.app, self.filter_start_var)).pack(side="left", padx=1)
        
        tk.Label(filters_left_f, text="To:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(side="left", padx=(5, 2))
        ef_ent = tk.Entry(filters_left_f, textvariable=self.filter_end_var, font=("Arial", 10), width=10, bg=self.CARD_BG, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        ef_ent.pack(side="left", ipady=3)
        tk.Button(filters_left_f, text="▼", bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", bd=0, highlightthickness=0, cursor="hand2", command=lambda: NativeCalendar(self.app, self.filter_end_var)).pack(side="left", padx=1)
        
        # --- THE FIX: Moved Clear button to strictly follow the Custom Date boxes ---
        tk.Button(filters_left_f, text="✖ Clear", font=("Arial", 9, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_RED, activebackground=self.CARD_BG, activeforeground=self.ACCENT_RED, relief="flat", bd=0, highlightthickness=0, cursor="hand2", padx=10, pady=4, command=self.clear_filters).pack(side="left", padx=(15, 0))
        # -------------------------------------------------------------------

        tiles_f = tk.Frame(main_container, bg=self.BG_COLOR)
        tiles_f.pack(fill="x", pady=(0, 20))

        self.lbl_inc, self.sub_inc = self.create_pl_tile(tiles_f, "TOTAL INCOME (REVENUE)", "0.00", self.ACCENT_BLUE, "vs prior period")
        self.lbl_inc.master.pack(side="left", expand=True, fill="both", padx=(0, 10))

        self.lbl_cogs, self.sub_cogs = self.create_pl_tile(tiles_f, "DIRECT COSTS (PURCHASES)", "0.00", self.ACCENT_YELLOW, "vs prior period")
        self.lbl_cogs.master.pack(side="left", expand=True, fill="both", padx=10)

        self.lbl_opex, self.sub_opex = self.create_pl_tile(tiles_f, "OPERATING EXPENSES (OPEX)", "0.00", self.TEXT_PRIMARY, "vs prior period")
        self.lbl_opex.master.pack(side="left", expand=True, fill="both", padx=10)

        self.lbl_net, self.sub_net = self.create_pl_tile(tiles_f, "NET PROFIT", "0.00", self.ACCENT_GREEN, "0.0% margin")
        self.lbl_net.master.pack(side="left", expand=True, fill="both", padx=(10, 0))

        # --- THE FIX: We stop building hard-coded tables here. load_data builds them dynamically! ---
        self.tables_f = tk.Frame(main_container, bg=self.BG_COLOR)
        self.tables_f.pack(fill="both", expand=True)

    def create_detail_row(self, parent, title, subtitle, amount, amount_color, command=None, is_bold=False):
        cursor_type = "hand2" if command else ""
        row = tk.Frame(parent, bg=self.CARD_BG, cursor=cursor_type)
        row.pack(fill="x", pady=8)

        left = tk.Frame(row, bg=self.CARD_BG, cursor=cursor_type)
        left.pack(side="left")
        
        title_font = ("Arial", 12, "bold") if is_bold else ("Arial", 11)
        lbl_t = tk.Label(left, text=title, font=title_font, bg=self.CARD_BG, fg=self.TEXT_PRIMARY, cursor=cursor_type)
        lbl_t.pack(anchor="w")
        
        if subtitle:
            lbl_s = tk.Label(left, text=subtitle, font=("Arial", 9), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, cursor=cursor_type)
            lbl_s.pack(anchor="w", pady=(2, 0))

        right_container = tk.Frame(row, bg=self.CARD_BG, cursor=cursor_type)
        right_container.pack(side="right")

        amt_font = ("Arial", 12, "bold") if is_bold else ("Arial", 11, "bold")
        lbl_a = tk.Label(right_container, text=format_currency(amount, self.curr_fmt), font=amt_font, bg=self.CARD_BG, fg=amount_color, cursor=cursor_type)
        lbl_a.pack(side="left")

        if command:
            lbl_arrow = tk.Label(right_container, text="›", font=("Arial", 16), bg=self.CARD_BG, fg=self.BORDER_COLOR, cursor=cursor_type)
            lbl_arrow.pack(side="left", padx=(10, 0))
            
            def on_click(e): command()
            row.bind("<Button-1>", on_click)
            left.bind("<Button-1>", on_click)
            lbl_t.bind("<Button-1>", on_click)
            if subtitle: lbl_s.bind("<Button-1>", on_click)
            right_container.bind("<Button-1>", on_click)
            lbl_a.bind("<Button-1>", on_click)
            lbl_arrow.bind("<Button-1>", on_click)

    def open_drilldown(self, title, columns, data):
        pop = tk.Toplevel(self)
        pop.title(title)
        pop.configure(bg=self.BG_COLOR)
        pop.grab_set()
        
        pop.update_idletasks()
        w, h = 850, 550
        sw, sh = pop.winfo_screenwidth(), pop.winfo_screenheight()
        pop.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")

        header_f = tk.Frame(pop, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1, pady=15, padx=20)
        header_f.pack(fill="x")
        tk.Label(header_f, text=title, font=("Arial", 14, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left")

        table_f = tk.Frame(pop, bg=self.BG_COLOR, padx=20, pady=20)
        table_f.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("PL.Drill.Treeview.Heading", font=("Arial", 10, "bold"), background=self.CARD_BG, foreground=self.TEXT_PRIMARY, relief="solid", borderwidth=1)
        style.configure("PL.Drill.Treeview", font=("Arial", 10), rowheight=35, background=self.BG_COLOR, fieldbackground=self.BG_COLOR, foreground=self.TEXT_PRIMARY, borderwidth=0)
        style.map("PL.Drill.Treeview", background=[("selected", self.BORDER_COLOR)], foreground=[("selected", "#ffffff")])
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="PL.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="PL.Horizontal.TScrollbar")
        
        actual_cols = list(columns) + ["ghost"]
        tree = ttk.Treeview(table_f, columns=actual_cols, show="headings", height=10, style="PL.Drill.Treeview", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=tree.yview)
        scroll_x.config(command=tree.xview)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        tree.tag_configure("evenrow", background=self.BG_COLOR, foreground=self.TEXT_PRIMARY) 
        tree.tag_configure("oddrow", background=self.CARD_BG, foreground=self.TEXT_PRIMARY)  
        tree.tag_configure("empty", background=self.BG_COLOR)

        for col in actual_cols:
            if col == "ghost":
                tree.heading(col, text="", anchor="center")
                tree.column(col, width=10, minwidth=10, stretch=True)
            else:
                tree.heading(col, text=col, anchor="e" if "Amount" in col else "w")
                default_w = 150 if "Amount" in col else (120 if "Date" in col else 250)
                tree.column(col, width=default_w, minwidth=100, anchor="e" if "Amount" in col else "w", stretch=False)

        items_count = 0
        has_valid_data = False
        
        for row_data in data:
            has_valid_data = True
            tag = "evenrow" if items_count % 2 == 0 else "oddrow"
            final_row = list(row_data) + [""]
            tree.insert("", "end", values=final_row, tags=(tag,))
            items_count += 1
        
        if not has_valid_data:
            empty_val = ["No records found."] + [""] * (len(columns) - 1) + [""]
            tree.insert("", "end", values=empty_val, tags=("evenrow",))
            items_count = 1

        for i in range(items_count, 12):
            tree.insert("", "end", iid=f"empty_{i}", values=[""] * len(actual_cols), tags=("evenrow" if i % 2 == 0 else "oddrow", "empty"))
            
        def enforce_selection(e):
            for item in tree.selection():
                if str(item).startswith("empty_"): tree.selection_remove(item)
        tree.bind("<<TreeviewSelect>>", enforce_selection)

    def create_pl_tile(self, parent, title, value, val_color, subtitle):
        # --- THE FIX: Extreme deflation to match compact UI reference ---
        f = tk.Frame(parent, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=15, pady=8)
        tk.Label(f, text=title, font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        lbl_val = tk.Label(f, text=value, font=("Arial", 22, "bold"), bg=self.CARD_BG, fg=val_color)
        lbl_val.pack(anchor="w", pady=(0, 0))
        lbl_sub = tk.Label(f, text=subtitle, font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY)
        lbl_sub.pack(anchor="w")
        return lbl_val, lbl_sub

    def clear_filters(self):
        self.filter_start_var.set("")
        self.filter_end_var.set("")
        self.filter_year_var.set(str(date.today().year))
        self.filter_month_var.set("All Months")

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

    def get_active_date_range(self):
        s_str = self.filter_start_var.get().strip()
        e_str = self.filter_end_var.get().strip()
        
        if s_str or e_str:
            start_dt = self.parse_date(s_str) if s_str else datetime(2000, 1, 1).date()
            end_dt = self.parse_date(e_str) if e_str else date.today()
            if not start_dt: start_dt = datetime(2000, 1, 1).date()
            if not end_dt: end_dt = date.today()
            
            duration = (end_dt - start_dt).days + 1
            prev_end = start_dt - timedelta(days=1)
            prev_start = prev_end - timedelta(days=duration - 1)
            return start_dt, end_dt, prev_start, prev_end

        y_val = self.filter_year_var.get()
        m_val = self.filter_month_var.get()
        if y_val == "All Years": return None, None, None, None

        y = int(y_val)
        if m_val != "All Months":
            m = datetime.strptime(m_val, "%B").month
            start_dt = date(y, m, 1)
            last_day = calendar.monthrange(y, m)[1]
            end_dt = date(y, m, last_day)
            
            if m == 1:
                prev_start = date(y-1, 12, 1)
                prev_end = date(y-1, 12, 31)
            else:
                prev_start = date(y, m-1, 1)
                last_day_prev = calendar.monthrange(y, m-1)[1]
                prev_end = date(y, m-1, last_day_prev)
            return start_dt, end_dt, prev_start, prev_end

        start_dt = date(y, 1, 1)
        end_dt = date(y, 12, 31)
        prev_start = date(y-1, 1, 1)
        prev_end = date(y-1, 12, 31)
        return start_dt, end_dt, prev_start, prev_end

    def is_in_range(self, dt, start_bound, end_bound):
        if not dt: return False
        if not start_bound and not end_bound: return True 
        if dt >= start_bound and dt <= end_bound: return True
        return False

    def load_data(self):
        # --- THE FIX: Updated failsafe for dynamic tables ---
        if not hasattr(self, "tables_f"): return
        
        comp_id = getattr(self.app, "active_company_id", 1)
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
        # ---------------------------------------------------------------------

        curr_start, curr_end, prev_start, prev_end = self.get_active_date_range()
        is_cash_basis = self.accounting_basis.get() == "Cash"

        c_inc, c_cogs, c_opex = 0.0, 0.0, 0.0
        p_inc, p_cogs, p_opex = 0.0, 0.0, 0.0

        inc_grouped = {"Sales Revenue": []}
        cogs_grouped = {}
        opex_grouped = {}
        
        self.chart_data = {"COGS": 0.0, "OPEX": {}, "REVENUE": {}, "TREND": {}}

        COGS_CATEGORIES = ["Purchase", "Supplies", "Raw Materials", "Inventory", "Equipment"]

        invoices = database.get_all_invoices()
        for i in invoices:
            dt = self.parse_date(i[1])
            if not dt: continue
            
            # --- THE FIX: Strictly ignore Draft Invoices ---
            status = str(i[7] if len(i) > 7 and i[7] else "").strip()
            if status.lower() == 'draft': continue 
            # -----------------------------------------------
            
            subtotal = self.safe_float(i[4]) 
            amt_to_record = 0.0

            if is_cash_basis:
                if status == "Paid": amt_to_record = subtotal
                else:
                    total_inv = self.safe_float(i[6])
                    bal_due = self.safe_float(i[8]) if len(i)>8 else total_inv
                    if total_inv > 0:
                        collected = total_inv - bal_due
                        paid_ratio = collected / total_inv
                        amt_to_record = subtotal * paid_ratio
            else:
                amt_to_record = subtotal

            if amt_to_record > 0:
                if self.is_in_range(dt, curr_start, curr_end):
                    c_inc += amt_to_record
                    inc_grouped["Sales Revenue"].append((dt, i[3], f"Inv #{i[2]}", amt_to_record))
                    
                    customer = str(i[3]).strip() if i[3] else "Walk-in"
                    if customer not in self.chart_data["REVENUE"]: self.chart_data["REVENUE"][customer] = 0.0
                    self.chart_data["REVENUE"][customer] += amt_to_record
                    
                    m_key = dt.strftime("%Y-%m")
                    if m_key not in self.chart_data["TREND"]: self.chart_data["TREND"][m_key] = {"Inc": 0.0, "Exp": 0.0}
                    self.chart_data["TREND"][m_key]["Inc"] += amt_to_record
                    
                elif self.is_in_range(dt, prev_start, prev_end):
                    p_inc += amt_to_record

        # --- THE FIX: True Accrual Purchase Engine (Matches Balance Sheet Math) ---
        try:
            conn_p = database.get_connection()
            cur_p = conn_p.cursor()
            # --- THE FIX: Added strict status filter to ignore Drafts ---
            cur_p.execute("SELECT purchase_date, bill_number, vendor_name, subtotal, total, amount_paid FROM purchases WHERE company_id=? AND is_deleted=0 AND is_draft=0 AND LOWER(COALESCE(status, '')) != 'draft'", (comp_id,))
            for r in cur_p.fetchall():
                dt = self.parse_date(r[0])
                if not dt: continue
                
                subtotal = self.safe_float(r[3]) # GST Stripped!
                total = self.safe_float(r[4])
                paid = self.safe_float(r[5])
                
                amt_to_record = paid if is_cash_basis else subtotal
                if is_cash_basis and total > 0:
                    paid_ratio = paid / total
                    amt_to_record = subtotal * paid_ratio
                    
                if amt_to_record > 0:
                    if self.is_in_range(dt, curr_start, curr_end):
                        c_cogs += amt_to_record
                        if "Purchases" not in cogs_grouped: cogs_grouped["Purchases"] = []
                        cogs_grouped["Purchases"].append((dt, f"Bill #{r[1]}", f"Vendor: {r[2]}", amt_to_record))
                    elif self.is_in_range(dt, prev_start, prev_end):
                        p_cogs += amt_to_record
            conn_p.close()
        except: pass
        # --------------------------------------------------------------------------

        try:
            gen_exp = database.get_all_general_expenses()
            for e in gen_exp:
                dt = self.parse_date(e[1])
                if not dt: continue
                amt = self.safe_float(e[4])
                cat = e[3] if e[3] else "General"
                
                is_cogs = cat in COGS_CATEGORIES

                if self.is_in_range(dt, curr_start, curr_end):
                    if is_cogs:
                        c_cogs += amt
                        if cat not in cogs_grouped: cogs_grouped[cat] = []
                        cogs_grouped[cat].append((dt, e[2], "Direct Cost", amt))
                    else:
                        c_opex += amt
                        if cat not in opex_grouped: opex_grouped[cat] = []
                        opex_grouped[cat].append((dt, e[2], "Expense", amt))
                        
                        if cat not in self.chart_data["OPEX"]: self.chart_data["OPEX"][cat] = 0.0
                        self.chart_data["OPEX"][cat] += amt
                        
                    m_key = dt.strftime("%Y-%m")
                    if m_key not in self.chart_data["TREND"]: self.chart_data["TREND"][m_key] = {"Inc": 0.0, "Exp": 0.0}
                    self.chart_data["TREND"][m_key]["Exp"] += amt
                        
                elif self.is_in_range(dt, prev_start, prev_end):
                    if is_cogs: p_cogs += amt
                    else: p_opex += amt
        except: pass

        try:
            pays = database.get_all_employee_payments_with_names()
            for p in pays:
                if p[3] in ("Salary", "Bonus"):
                    dt = self.parse_date(p[1])
                    if not dt: continue
                    amt = self.safe_float(p[4])
                    
                    if self.is_in_range(dt, curr_start, curr_end):
                        c_opex += amt
                        # --- THE FIX: Renamed 'Payroll' to 'Salaries Paid' for consistency ---
                        if "Salaries Paid" not in opex_grouped: opex_grouped["Salaries Paid"] = []
                        opex_grouped["Salaries Paid"].append((dt, f"Emp: {p[2]}", p[3], amt))
                        
                        if "Salaries Paid" not in self.chart_data["OPEX"]: self.chart_data["OPEX"]["Salaries Paid"] = 0.0
                        self.chart_data["OPEX"]["Salaries Paid"] += amt
                        # ---------------------------------------------------------------------
                        
                        m_key = dt.strftime("%Y-%m")
                        if m_key not in self.chart_data["TREND"]: self.chart_data["TREND"][m_key] = {"Inc": 0.0, "Exp": 0.0}
                        self.chart_data["TREND"][m_key]["Exp"] += amt
                        
                    elif self.is_in_range(dt, prev_start, prev_end):
                        p_opex += amt
        except: pass

        # --- THE FIX: True Accrual Labour Engine (With Ghost Wipe) ---
        try:
            conn_l = database.get_connection()
            cur_l = conn_l.cursor()
            # --- THE FIX: Fetched the is_deleted flag from the labours table ---
            cur_l.execute("SELECT ll.date, ll.type, ABS(ll.amount), ll.description, l.name, COALESCE(l.is_deleted, 0) FROM labour_ledger ll LEFT JOIN labours l ON ll.labour_id = l.id WHERE ll.type IN ('Payment', 'Wage', 'Bonus') AND l.company_id = ?", (comp_id,))
            labour_pays = cur_l.fetchall()
            conn_l.close()

            for lp in labour_pays:
                dt = self.parse_date(lp[0])
                if not dt: continue
                p_type = lp[1]
                amt = self.safe_float(lp[2])
                l_name = lp[4] if lp[4] else "Unknown Labour"
                is_deleted = int(lp[5]) if len(lp) > 5 else 0
                
                amt_to_record = 0.0
                
                if is_deleted == 1:
                    # GHOST WIPE: If deleted, all unpaid accrued wages vanish. 
                    # Only actual cash handed to them counts as the final true expense.
                    if p_type == 'Payment':
                        amt_to_record = amt
                        l_type = "Settled Wages (Deleted Worker)"
                    elif p_type == 'Bonus':
                        amt_to_record = amt
                        l_type = "Bonus Paid (Deleted Worker)"
                else:
                    if p_type == 'Wage' and not is_cash_basis:
                        amt_to_record = amt
                        l_type = "Wages Accrued"
                    elif p_type == 'Payment' and is_cash_basis:
                        amt_to_record = amt
                        l_type = "Wages Paid"
                    elif p_type == 'Bonus':
                        amt_to_record = amt
                        l_type = "Bonus Paid"

                if amt_to_record > 0:
                    if self.is_in_range(dt, curr_start, curr_end):
                        c_opex += amt_to_record
                        
                        group_key = "Wages Paid" if is_cash_basis else "Wages & Settlements"
                        if group_key not in opex_grouped: opex_grouped[group_key] = []
                        opex_grouped[group_key].append((dt, f"Labour: {l_name}", l_type, amt_to_record))
                        
                        if group_key not in self.chart_data["OPEX"]: self.chart_data["OPEX"][group_key] = 0.0
                        self.chart_data["OPEX"][group_key] += amt_to_record
                        
                        m_key = dt.strftime("%Y-%m")
                        if m_key not in self.chart_data["TREND"]: self.chart_data["TREND"][m_key] = {"Inc": 0.0, "Exp": 0.0}
                        self.chart_data["TREND"][m_key]["Exp"] += amt_to_record
                        
                    elif self.is_in_range(dt, prev_start, prev_end):
                        p_opex += amt_to_record
        except: pass
        # -------------------------------------------------------------------

        # --- THE FIX: Inject Live Asset Depreciation AND Closing Stock Engine ---
        try:
            conn_d = database.get_connection()
            cur_d = conn_d.cursor()
            cur_d.execute("SELECT item_name, quantity, market_price, transaction_type, notes, added_date FROM stock WHERE company_id=? AND COALESCE(is_deleted, 0) = 0", (comp_id,))
            
            inventory = {}
            for r in cur_d.fetchall():
                name, qty, price, t_type, notes_raw, date_str = r[0], float(r[1] or 0), float(r[2] or 0), r[3], r[4], r[5]
                if name not in inventory:
                    inventory[name] = {'net': 0, 'adds': [], 'dep_rate': 0.0}
                
                try: j = json.loads(notes_raw)
                except: j = {}
                
                if "depreciation" in j: inventory[name]['dep_rate'] = float(j["depreciation"])
                
                d_obj = self.parse_date(date_str) if date_str else date.today()
                
                if t_type == 'ADD':
                    inventory[name]['net'] += qty
                    # --- THE FIX: We now attach the specific purchase date to EACH batch! ---
                    inventory[name]['adds'].append({'qty': qty, 'price': price, 'date': d_obj})
                elif t_type in ('LOSS', 'SOLD'):
                    inventory[name]['net'] -= qty
                    rem = qty
                    for a in inventory[name]['adds']:
                        if a['qty'] > 0:
                            if a['qty'] >= rem:
                                a['qty'] -= rem; rem = 0; break
                            else:
                                rem -= a['qty']; a['qty'] = 0

            # --- THE FIX: Dual-Logic Depreciation Engine ---
            is_custom_filter = bool(self.filter_start_var.get().strip() or self.filter_end_var.get().strip())
            if is_custom_filter:
                calc_end_date = curr_end if curr_end else date.today()
            else:
                calc_end_date = curr_end if (curr_end and curr_end <= date.today()) else date.today()
            
            for name, data in inventory.items():
                if data['net'] > 0:
                    total_gross_val = 0.0
                    total_dep_amount = 0.0
                    
                    # --- THE FIX: We calculate depreciation PER BATCH, isolating new purchases from old ones! ---
                    for batch in data['adds']:
                        if batch['qty'] > 0:
                            batch_gross = batch['qty'] * batch['price']
                            total_gross_val += batch_gross
                            
                            if data['dep_rate'] > 0 and batch['date']:
                                days_owned = (calc_end_date - batch['date']).days
                                if days_owned > 0:
                                    dep_factor = (data['dep_rate'] / 100.0) * (days_owned / 365.25)
                                    if dep_factor > 1.0: dep_factor = 1.0
                                    total_dep_amount += (batch_gross * dep_factor)
                                    
                    if total_dep_amount > 0:
                        if "Asset Depreciation" not in opex_grouped: opex_grouped["Asset Depreciation"] = []
                        opex_grouped["Asset Depreciation"].append((calc_end_date, f"Asset: {name}", "Depreciation Loss", total_dep_amount))
                        c_opex += total_dep_amount
                    
                    if total_gross_val > 0:
                        c_inc += total_gross_val
                        if "Closing Stock (Assets)" not in inc_grouped: inc_grouped["Closing Stock (Assets)"] = []
                        inc_grouped["Closing Stock (Assets)"].append((calc_end_date, f"Asset: {name}", "Gross Value (Pre-Depreciation)", total_gross_val))
                            
            conn_d.close()
        except Exception as e:
            print("Depreciation error:", e)
        # ------------------------------------------------------------------------

        self.chart_data["COGS"] = c_cogs
        
        self.inc_grouped = inc_grouped
        self.cogs_grouped = cogs_grouped
        self.opex_grouped = opex_grouped
        
        for w in self.tables_f.winfo_children(): w.destroy()

        gross_profit = c_inc - c_cogs
        c_net = gross_profit - c_opex
        p_net = (p_inc - p_cogs) - p_opex

        # --- THE FIX: Bind the math to the window so the PDF Exporter can 'see' it! ---
        self.gross_profit = gross_profit
        self.c_opex = c_opex
        # -----------------------------------------------------------------------------

        # --- THE FIX: Dynamic Engine with flawless rendering boundaries ---
        if self.layout_var.get() == "Modern (Vertical)":
            wrapper = tk.Frame(self.tables_f, bg=self.BG_COLOR)
            # --- THE FIX: Removed 100px gap so it fills the screen perfectly ---
            wrapper.pack(fill="both", expand=True, padx=0)

            center_f = tk.Frame(wrapper, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
            center_f.pack(fill="both", expand=True)

            head = tk.Frame(center_f, bg=self.CARD_BG, pady=15, padx=20)
            head.pack(side="top", fill="x")
            tk.Label(head, text="📋 Profit & Loss (Vertical)", font=("Arial", 14, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left")
            tk.Frame(center_f, bg=self.BORDER_COLOR, height=1).pack(side="top", fill="x", padx=20)

            footer = tk.Frame(center_f, bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=15, pady=12)
            footer.pack(side="bottom", fill="x")
            lbl_bot = tk.Label(footer, text=format_currency(c_net, self.curr_fmt), font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_GREEN if c_net >= 0 else self.ACCENT_RED)
            lbl_bot.pack(side="right", padx=20)
            tk.Label(footer, text="NET PROFIT / (LOSS)", font=("Arial", 11, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(side="left", padx=20)

            scroll_cont = tk.Frame(center_f, bg=self.CARD_BG)
            scroll_cont.pack(side="top", fill="both", expand=True, pady=5)
            canvas = tk.Canvas(scroll_cont, bg=self.CARD_BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(scroll_cont, orient="vertical", command=canvas.yview, style="PL.Vertical.TScrollbar")
            body = tk.Frame(canvas, bg=self.CARD_BG, padx=20, pady=10)
            body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas_win = canvas.create_window((0, 0), window=body, anchor="nw")
            canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

            tk.Label(body, text="1. REVENUE (INCOME)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in inc_grouped.items():
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_BLUE, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))
            
            tk.Frame(body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)
            tk.Label(body, text="2. DIRECT COSTS (COGS)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in cogs_grouped.items():
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_YELLOW, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))
            
            tk.Frame(body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)
            self.create_detail_row(body, "= GROSS PROFIT", "", gross_profit, self.TEXT_PRIMARY, is_bold=True)
            tk.Frame(body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)

            tk.Label(body, text="3. OPERATING EXPENSES (OPEX)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in sorted(opex_grouped.items(), key=lambda x: sum(i[3] for i in x[1]), reverse=True):
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_RED, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))
            
            tk.Frame(body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)
            self.create_detail_row(body, "= TOTAL OPEX", "", c_opex, self.TEXT_PRIMARY, is_bold=True)

        else:
            # T-ACCOUNT LAYOUT (Left / Right)
            left_f = tk.Frame(self.tables_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
            left_f.pack(side="left", fill="both", expand=True, padx=(0, 10))

            l_head = tk.Frame(left_f, bg=self.CARD_BG, pady=15, padx=20)
            l_head.pack(side="top", fill="x")
            tk.Label(l_head, text="📉 DEBIT (Expenses & Losses)", font=("Arial", 14, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left")
            tk.Frame(left_f, bg=self.BORDER_COLOR, height=1).pack(side="top", fill="x", padx=20)

            l_footer = tk.Frame(left_f, bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=15, pady=12)
            l_footer.pack(side="bottom", fill="x")
            t_total = max(c_inc, c_cogs + c_opex) 
            tk.Label(l_footer, text=format_currency(t_total, self.curr_fmt), font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(side="right", padx=20)
            tk.Label(l_footer, text="TOTAL DEBIT", font=("Arial", 11, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(side="left", padx=20)

            l_scroll_cont = tk.Frame(left_f, bg=self.CARD_BG)
            l_scroll_cont.pack(side="top", fill="both", expand=True, pady=5)
            l_canvas = tk.Canvas(l_scroll_cont, bg=self.CARD_BG, highlightthickness=0)
            l_scrollbar = ttk.Scrollbar(l_scroll_cont, orient="vertical", command=l_canvas.yview, style="PL.Vertical.TScrollbar")
            l_body = tk.Frame(l_canvas, bg=self.CARD_BG, padx=20, pady=10)
            l_body.bind("<Configure>", lambda e: l_canvas.configure(scrollregion=l_canvas.bbox("all")))
            l_canvas_win = l_canvas.create_window((0, 0), window=l_body, anchor="nw")
            l_canvas.bind("<Configure>", lambda e: l_canvas.itemconfig(l_canvas_win, width=e.width))
            l_canvas.configure(yscrollcommand=l_scrollbar.set)
            l_scrollbar.pack(side="right", fill="y")
            l_canvas.pack(side="left", fill="both", expand=True)

            right_f = tk.Frame(self.tables_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
            right_f.pack(side="left", fill="both", expand=True, padx=(10, 0))

            r_head = tk.Frame(right_f, bg=self.CARD_BG, pady=15, padx=20)
            r_head.pack(side="top", fill="x")
            tk.Label(r_head, text="📈 CREDIT (Incomes & Gains)", font=("Arial", 14, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left")
            tk.Frame(right_f, bg=self.BORDER_COLOR, height=1).pack(side="top", fill="x", padx=20)

            r_footer = tk.Frame(right_f, bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=15, pady=12)
            r_footer.pack(side="bottom", fill="x")
            tk.Label(r_footer, text=format_currency(t_total, self.curr_fmt), font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(side="right", padx=20)
            tk.Label(r_footer, text="TOTAL CREDIT", font=("Arial", 11, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(side="left", padx=20)

            r_scroll_cont = tk.Frame(right_f, bg=self.CARD_BG)
            r_scroll_cont.pack(side="top", fill="both", expand=True, pady=5)
            r_canvas = tk.Canvas(r_scroll_cont, bg=self.CARD_BG, highlightthickness=0)
            r_scrollbar = ttk.Scrollbar(r_scroll_cont, orient="vertical", command=r_canvas.yview, style="PL.Vertical.TScrollbar")
            r_body = tk.Frame(r_canvas, bg=self.CARD_BG, padx=20, pady=10)
            r_body.bind("<Configure>", lambda e: r_canvas.configure(scrollregion=r_canvas.bbox("all")))
            r_canvas_win = r_canvas.create_window((0, 0), window=r_body, anchor="nw")
            r_canvas.bind("<Configure>", lambda e: r_canvas.itemconfig(r_canvas_win, width=e.width))
            r_canvas.configure(yscrollcommand=r_scrollbar.set)
            r_scrollbar.pack(side="right", fill="y")
            r_canvas.pack(side="left", fill="both", expand=True)

            l_canvas.bind("<MouseWheel>", lambda e: l_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            r_canvas.bind("<MouseWheel>", lambda e: r_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

            tk.Label(l_body, text="DIRECT COSTS (COGS)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in cogs_grouped.items():
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(l_body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_YELLOW, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))
            tk.Frame(l_body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)

            tk.Label(l_body, text="OPERATING EXPENSES (OPEX)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in sorted(opex_grouped.items(), key=lambda x: sum(i[3] for i in x[1]), reverse=True):
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(l_body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_RED, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))
            
            if c_net > 0:
                tk.Frame(l_body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)
                self.create_detail_row(l_body, "NET PROFIT", "Transferred to Balance Sheet", c_net, self.ACCENT_GREEN, is_bold=True)

            tk.Label(r_body, text="REVENUE (INCOME)", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", pady=(5, 0))
            for cat, items in inc_grouped.items():
                if not items: continue
                drill_data = [(i[0].strftime(self.date_fmt_code), i[1], i[2], format_currency(i[3], self.curr_fmt)) for i in sorted(items, key=lambda x: x[0], reverse=True)]
                self.create_detail_row(r_body, cat, f"{len(items)} items", sum(i[3] for i in items), self.ACCENT_BLUE, command=lambda c=cat, d=drill_data: self.open_drilldown(c, ("Date", "Description", "Type", "Amount"), d))

            if c_net < 0:
                tk.Frame(r_body, bg=self.BORDER_COLOR, height=1).pack(fill="x", pady=10)
                self.create_detail_row(r_body, "NET LOSS", "Transferred to Balance Sheet", abs(c_net), self.ACCENT_RED, is_bold=True)

        def get_trend(curr, prev, invert=False):
            if not curr_start: return "N/A (All Time)", self.TEXT_SECONDARY
            if prev == 0: return "No prior data", self.TEXT_SECONDARY
            pct = ((curr - prev) / prev) * 100
            if invert:
                if pct > 0: return f"↑ {abs(pct):.1f}% vs prior", self.ACCENT_RED
                if pct < 0: return f"↓ {abs(pct):.1f}% vs prior", self.ACCENT_GREEN
            else:
                if pct > 0: return f"↑ {abs(pct):.1f}% vs prior", self.ACCENT_GREEN
                if pct < 0: return f"↓ {abs(pct):.1f}% vs prior", self.ACCENT_RED
            return "0% vs prior", self.TEXT_SECONDARY

        self.lbl_inc.config(text=format_currency(c_inc, self.curr_fmt))
        t_str, t_col = get_trend(c_inc, p_inc)
        self.sub_inc.config(text=t_str, fg=t_col)

        self.lbl_cogs.config(text=format_currency(c_cogs, self.curr_fmt))
        t_str, t_col = get_trend(c_cogs, p_cogs, invert=True)
        self.sub_cogs.config(text=t_str, fg=t_col)

        self.lbl_opex.config(text=format_currency(c_opex, self.curr_fmt))
        t_str, t_col = get_trend(c_opex, p_opex, invert=True)
        self.sub_opex.config(text=t_str, fg=t_col)

        self.lbl_net.config(text=format_currency(c_net, self.curr_fmt))
        margin = (c_net / c_inc * 100) if c_inc > 0 else 0.0
        
        if c_net >= 0:
            self.lbl_net.config(fg=self.ACCENT_GREEN)
            self.sub_net.config(text=f"{margin:.1f}% Profit Margin", fg=self.ACCENT_GREEN)
        else:
            self.lbl_net.config(fg=self.ACCENT_RED)
            self.sub_net.config(text=f"Operating at a Loss", fg=self.ACCENT_RED)