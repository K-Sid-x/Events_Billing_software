import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import traceback
import tempfile
import webbrowser
import csv
from datetime import date, datetime

# --- Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings
from views.invoice_parts.calendar_widget import NativeCalendar
from views.home_parts.ui_components import get_theme 

class BalanceSheetView(tk.Frame):
    def __init__(self, parent):
        self.t = get_theme() 
        self.YELLOW = "#f59e0b"
        super().__init__(parent, bg=self.t["bg"])
        
        try:
            self.app = self.winfo_toplevel()
            self.comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)

            # Strict "As Of" Snapshot Date
            self.as_of_var = tk.StringVar(value=date.today().strftime(self.date_fmt_code))
            self.as_of_var.trace_add("write", lambda *a: self.refresh_data())

            self.detail_ar = []
            self.detail_ap = []
            self.detail_stock = []
            self.detail_adv_paid = []
            self.detail_adv_received = []
            self.detail_payables = []
            self.detail_retained_earnings = []
            self.detail_opening_capital = []
            self.detail_cash = []

            self.build_ui_shell()
            self.refresh_data()
            
        except Exception as e:
            err_msg = f"CRITICAL ERROR LOADING BALANCE SHEET:\n\n{str(e)}\n\n{traceback.format_exc()}"
            tk.Label(self, text=err_msg, font=("Arial", 10, "bold"), fg=self.t["error"], bg=self.t["bg"], justify="left").pack(fill="both", expand=True, padx=20, pady=20)

    def build_ui_shell(self):
        style = ttk.Style(self)
        style.theme_use("default")
        
        self.app.option_add("*TCombobox*Listbox.background", self.t["card"])
        self.app.option_add("*TCombobox*Listbox.foreground", self.t["text"])
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.t["accent_blue"])
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("TCombobox", fieldbackground=self.t["bg"], background=self.t["card"], foreground=self.t["text"], arrowcolor=self.t["text"], bordercolor=self.t["border"], lightcolor=self.t["border"], darkcolor=self.t["border"])
        style.map("TCombobox", fieldbackground=[("readonly", self.t["bg"])], selectbackground=[("readonly", self.t["bg"])], selectforeground=[("readonly", self.t["text"])])

        style.configure("Vertical.TScrollbar", background=self.t["card"], troughcolor=self.t["bg"], bordercolor=self.t["border"], arrowcolor=self.t["text"], relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", self.t["border"])])

        self.main_container = tk.Frame(self, bg=self.t["bg"], padx=30, pady=30)
        self.main_container.pack(fill="both", expand=True)

        self.top_row = tk.Frame(self.main_container, bg=self.t["bg"])
        self.top_row.pack(fill="x", pady=(0, 15))

        self.filter_f = tk.Frame(self.main_container, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1, padx=15, pady=10)
        self.filter_f.pack(fill="x", pady=(0, 20))

        tk.Label(self.filter_f, text="📅 Balance Sheet As Of:", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="left", padx=(0, 15))

        as_of_ent = tk.Entry(self.filter_f, textvariable=self.as_of_var, font=("Arial", 10), width=15, bg=self.t["bg"], fg=self.t["text"], insertbackground=self.t["text"], highlightbackground=self.t["border"], highlightthickness=1)
        as_of_ent.pack(side="left", ipady=3)
        tk.Button(self.filter_f, text="📅", bg=self.t["bg"], fg=self.t["text"], relief="flat", cursor="hand2", command=lambda: NativeCalendar(self.app, self.as_of_var)).pack(side="left", padx=2)

        tk.Button(self.filter_f, text="↺ Today", font=("Arial", 9, "bold"), bg=self.t["bg"], fg=self.t["accent_blue"], relief="flat", cursor="hand2", padx=10, pady=3, command=lambda: self.as_of_var.set(date.today().strftime(self.date_fmt_code))).pack(side="left", padx=(15, 0))

        # --- THE FIX: ADD ACCOUNTING METHOD TOGGLE ---
        tk.Label(self.filter_f, text="|   Method:", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["sec"]).pack(side="left", padx=(15, 5))
        self.acc_method_var = tk.StringVar(value="Accrual Basis")
        acc_cb = ttk.Combobox(self.filter_f, textvariable=self.acc_method_var, values=["Cash Basis", "Accrual Basis"], state="readonly", width=15, font=("Arial", 10))
        acc_cb.pack(side="left")
        self.acc_method_var.trace_add("write", lambda *a: self.refresh_data())
        # ---------------------------------------------

        self.dynamic_wrapper = tk.Frame(self.main_container, bg=self.t["bg"])
        self.dynamic_wrapper.pack(fill="both", expand=True)

    def parse_date(self, date_str):
        if not date_str: return None
        date_str = str(date_str).strip()
        
        # --- The Ultimate P&L Date Parser Clone ---
        if " " in date_str:
            date_str = date_str.split(" ")[0] 
            
        formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]
        for fmt in formats:
            try: return datetime.strptime(date_str, fmt).date()
            except: pass
        return None

    def get_end_date(self):
        d_str = self.as_of_var.get().strip()
        if d_str:
            d = self.parse_date(d_str)
            if d: return d
        return date.today()

    def calculate_balance_sheet(self):
        end_date = self.get_end_date()
        is_cash = self.acc_method_var.get() == "Cash Basis"

        def is_valid(d_str):
            if not end_date: return True
            d = self.parse_date(d_str)
            return d <= end_date if d else True

        # --- 1. GET OPENING CAPITAL ---
        comp_row = database.get_company(self.comp_id)
        self.opening_capital = 0.0
        opening_date = None
        if comp_row and len(comp_row) > 14 and comp_row[14]:
            try:
                t_json = json.loads(comp_row[14])
                self.opening_capital = float(t_json.get("opening_capital", 0.0))
                cap_date_str = t_json.get("opening_capital_date", "")
                if cap_date_str:
                    opening_date = self.parse_date(cap_date_str)
            except: pass

        self.active_capital = self.opening_capital
        if opening_date and end_date and opening_date > end_date:
            self.active_capital = 0.0

        raw_data = database.get_balance_sheet_raw_data()

        # --- ASSET BUCKETS ---
        self.accts_receivable = 0.0
        self.closing_stock = 0.0
        self.advances_paid = 0.0

        # --- LIABILITY BUCKETS ---
        self.accts_payable = 0.0
        self.advances_received = 0.0
        self.salaries_payable = 0.0

        # --- P&L ENGINE (For Retained Earnings) ---
        self.total_revenue = 0.0
        self.total_cogs = 0.0
        self.total_expenses = 0.0

        self.detail_ar.clear()
        self.detail_ap.clear()
        self.detail_stock.clear()
        self.detail_adv_paid.clear()
        self.detail_adv_received.clear()
        self.detail_payables.clear()
        self.detail_retained_earnings.clear()
        self.detail_opening_capital.clear()
        self.detail_cash.clear()

        # --- THE FIX: GST Separation & True Subtotal Accrual Math ---
        self.output_gst = 0.0
        self.input_gst = 0.0

        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT invoice_date, invoice_number, customer_name, subtotal, total, balance_due, status, (COALESCE(cgst,0)+COALESCE(sgst,0)+COALESCE(igst,0)) FROM invoices WHERE company_id=? AND is_deleted=0 AND status != 'Draft'", (self.comp_id,))
            for r in c.fetchall():
                if is_valid(r[0]):
                    dt_str = self.parse_date(r[0]).strftime(self.date_fmt_code) if self.parse_date(r[0]) else "Unknown"
                    sub = float(r[3] or 0.0)
                    tot = float(r[4] or 0.0)
                    bal = float(r[5] or 0.0)
                    gst = float(r[7] or 0.0)
                    
                    if is_cash:
                        collected = tot - bal
                        paid_ratio = collected / tot if tot > 0 else 0
                        self.total_revenue += (sub * paid_ratio)
                        self.output_gst += (gst * paid_ratio)
                    else:
                        self.total_revenue += sub
                        self.output_gst += gst
                        self.accts_receivable += bal
                    
                    if bal > 0 and not is_cash:
                        self.detail_ar.append((dt_str, f"Inv #{r[1]} ({r[2]})", format_currency(bal, self.curr_fmt), r[6]))
                        
            c.execute("SELECT purchase_date, bill_number, vendor_name, subtotal, total, balance_due, status, (COALESCE(cgst,0)+COALESCE(sgst,0)+COALESCE(igst,0)) FROM purchases WHERE company_id=? AND is_deleted=0 AND is_draft=0 AND status != 'Draft'", (self.comp_id,))
            for r in c.fetchall():
                if is_valid(r[0]):
                    dt_str = self.parse_date(r[0]).strftime(self.date_fmt_code) if self.parse_date(r[0]) else "Unknown"
                    sub = float(r[3] or 0.0)
                    tot = float(r[4] or 0.0)
                    bal = float(r[5] or 0.0)
                    gst = float(r[7] or 0.0)
                    
                    if is_cash:
                        paid = tot - bal
                        paid_ratio = paid / tot if tot > 0 else 0
                        self.total_cogs += (sub * paid_ratio)
                        self.input_gst += (gst * paid_ratio)
                    else:
                        self.total_cogs += sub
                        self.input_gst += gst
                        self.accts_payable += bal
                    
                    if bal > 0 and not is_cash:
                        self.detail_ap.append((dt_str, f"Bill #{r[1]} ({r[2]})", format_currency(bal, self.curr_fmt), r[6]))
            conn.close()
        except Exception as e: pass
        
        self.net_gst = self.output_gst - self.input_gst
        self.gst_payable = self.net_gst if self.net_gst >= 0 else 0.0
        self.gst_receivable = abs(self.net_gst) if self.net_gst < 0 else 0.0
        # ------------------------------------------------------------

        # 4. CLOSING STOCK (Asset) & FIXED ASSET DEPRECIATION
        self.total_depreciation = 0.0
        
        try:
            conn_d = database.get_connection()
            cur_d = conn_d.cursor()
            cur_d.execute("SELECT item_name, quantity, market_price, transaction_type, notes, added_date FROM stock WHERE company_id=? AND COALESCE(is_deleted, 0) = 0", (self.comp_id,))
            
            inventory = {}
            for r in cur_d.fetchall():
                name, qty, price, t_type, notes_raw, date_str = r[0], float(r[1] or 0), float(r[2] or 0), r[3], r[4], r[5]
                
                d_obj = self.parse_date(date_str)
                if end_date and d_obj and d_obj > end_date:
                    continue
                
                if name not in inventory:
                    inventory[name] = {'net': 0, 'latest_price': price, 'dep_rate': 0.0, 'first_date': None}
                
                try: j = json.loads(notes_raw)
                except: j = {}
                
                if "depreciation" in j: 
                    inventory[name]['dep_rate'] = float(j["depreciation"])
                    
                if t_type == 'ADD':
                    inventory[name]['latest_price'] = price
                    if d_obj:
                        if not inventory[name]['first_date'] or d_obj < inventory[name]['first_date']:
                            inventory[name]['first_date'] = d_obj
                
                if t_type == 'ADD':
                    inventory[name]['net'] += qty
                elif t_type in ('LOSS', 'SOLD'):
                    inventory[name]['net'] -= qty

            for name, data in inventory.items():
                if data['net'] > 0:
                    gross_val = data['net'] * data['latest_price']
                    dep_amount = 0.0
                    
                    if data['dep_rate'] > 0 and data['first_date'] and end_date:
                        days_owned = (end_date - data['first_date']).days
                        if days_owned > 0:
                            dep_factor = (data['dep_rate'] / 100.0) * (days_owned / 365.25)
                            if dep_factor > 1.0: dep_factor = 1.0 
                            dep_amount = gross_val * dep_factor
                    
                    net_val = gross_val - dep_amount
                    self.closing_stock += net_val
                    
                    disp_date = data["first_date"].strftime(self.date_fmt_code) if data["first_date"] else "Unknown"
                    if dep_amount > 0:
                        self.total_depreciation += dep_amount
                        self.detail_stock.append((disp_date, f"⚙️ {name} (Depreciated)", format_currency(net_val, self.curr_fmt), f"Gross: {format_currency(gross_val, self.curr_fmt)} | Loss: -{format_currency(dep_amount, self.curr_fmt)}"))
                    else:
                        self.detail_stock.append((disp_date, name, format_currency(net_val, self.curr_fmt), f"{data['net']} units @ {format_currency(data['latest_price'], self.curr_fmt)}"))
            conn_d.close()
        except Exception as e: pass

        # 5. SALARIES, ADVANCES & GENERAL EXPENSES (WITH GHOST WIPE & EXPLICIT ROLES)
        payables_dict = {}
        advances_dict = {}
        client_advances_dict = {}
        deleted_workers = set()
        
        for r in raw_data.get("salaries", []):
            if is_valid(r[0]):
                p_type = r[1]
                amt = float(r[2] or 0.0)
                notes = r[3] if r[3] else ""
                emp_name = r[4] if len(r) > 4 and r[4] else "Unknown Worker"
                is_deleted = int(r[5]) if len(r) > 5 else 0
                worker_role = r[6] if len(r) > 6 else "Worker"
                
                if is_deleted == 1:
                    deleted_workers.add(emp_name)
                
                note_lower = str(notes).lower()
                is_wallet_deduct = "wallet deduction" in note_lower or "advance out" in note_lower or "(out)" in note_lower
                
                if p_type == 'Wage':
                    if not is_cash:
                        self.salaries_payable += amt
                        self.total_expenses += amt
                        payables_dict[emp_name] = payables_dict.get(emp_name, 0.0) + amt
                elif p_type in ('Salary', 'Bonus'):
                    self.total_expenses += abs(amt)
                    if is_wallet_deduct:
                        if emp_name not in advances_dict: advances_dict[emp_name] = {"bal": 0.0, "role": worker_role}
                        advances_dict[emp_name]["bal"] -= abs(amt)
                elif p_type == 'Payment':
                    if not is_cash:
                        self.salaries_payable -= abs(amt)
                        payables_dict[emp_name] = payables_dict.get(emp_name, 0.0) - abs(amt)
                    else:
                        self.total_expenses += abs(amt)
                    if is_wallet_deduct:
                        if emp_name not in advances_dict: advances_dict[emp_name] = {"bal": 0.0, "role": worker_role}
                        advances_dict[emp_name]["bal"] -= abs(amt)
                elif p_type == 'Advance':
                    if emp_name not in advances_dict: advances_dict[emp_name] = {"bal": 0.0, "role": worker_role}
                    advances_dict[emp_name]["bal"] += amt
                elif p_type == 'Client Advance':
                    if emp_name not in client_advances_dict: client_advances_dict[emp_name] = {"bal": 0.0, "role": worker_role}
                    client_advances_dict[emp_name]["bal"] += amt

        # Automatically cancel unpaid liabilities and reverse the expense for deleted workers
        for emp in deleted_workers:
            bal = payables_dict.get(emp, 0.0)
            if bal > 0.01 and not is_cash:
                self.salaries_payable -= bal
                self.total_expenses -= bal
                payables_dict[emp] = 0.0

        for emp, bal in payables_dict.items():
            if bal > 0.01:
                self.detail_payables.append((self.as_of_var.get(), emp, format_currency(bal, self.curr_fmt), "Unpaid Wages"))
                
        # Append active advances to the Global Asset Bucket
        for emp, adv_data in advances_dict.items():
            if adv_data["bal"] > 0.01:
                self.advances_paid += adv_data["bal"]
                self.detail_adv_paid.append((self.as_of_var.get(), emp, adv_data["role"], format_currency(adv_data["bal"], self.curr_fmt), "Advance Paid"))
                
        for emp, adv_data in client_advances_dict.items():
            if adv_data["bal"] > 0.01:
                self.advances_received += adv_data["bal"]
                self.detail_adv_received.append((self.as_of_var.get(), emp, adv_data["role"], format_currency(adv_data["bal"], self.curr_fmt), "Advance Received"))
        
        for r in raw_data.get("expenses", []):
            if is_valid(r[0]):
                if r[2] != "Inventory/Purchases": 
                    self.total_expenses += float(r[3] or 0.0)

        # ==========================================
        # THE PERFECT ACCOUNTING EQUATION MATH
        # ==========================================
        if self.salaries_payable < 0: self.salaries_payable = 0.0

        self.retained_earnings = self.total_revenue - self.total_cogs + self.closing_stock - self.total_expenses
        self.total_equity = self.active_capital + self.retained_earnings
        
        # --- THE FIX: Insert GST into the Balance Sheet Equation ---
        self.total_liabilities_only = self.accts_payable + self.advances_received + self.salaries_payable + self.gst_payable
        self.total_assets_except_cash = self.accts_receivable + self.advances_paid + self.closing_stock + self.gst_receivable
        # -----------------------------------------------------------
        
        # Cash derived to strictly enforce double-entry balancing
        self.cash_and_bank = (self.total_liabilities_only + self.total_equity) - self.total_assets_except_cash

        self.total_assets = self.cash_and_bank + self.total_assets_except_cash
        self.total_liab_equity = self.total_liabilities_only + self.total_equity
        
        # Prepare remaining Drill-Downs
        self.detail_opening_capital = [
            (opening_date.strftime(self.date_fmt_code) if opening_date else "Day Zero", "Initial Investment", format_currency(self.active_capital, self.curr_fmt), "Permanent Capital")
        ]
        self.detail_cash = [
            (self.as_of_var.get(), "Derived Cash & Bank Balance", format_currency(self.cash_and_bank, self.curr_fmt), "Liquid Asset")
        ]
        
        # --- THE FIX: Dynamic P&L Labels based on method ---
        if is_cash:
            rev_desc = "Total Cash Received from Sales"
            cogs_desc = "Total Cash Paid for Purchases"
            exp_desc = "Total Cash Paid for Expenses & Wages"
        else:
            rev_desc = "Total Invoiced Revenue (Inflows)"
            cogs_desc = "Total Cost of Purchases"
            exp_desc = "Total Expenses, Salaries & Wage Payable"

        self.detail_retained_earnings = [
            ("Revenue", rev_desc, format_currency(self.total_revenue, self.curr_fmt)),
            ("Direct Costs", cogs_desc, format_currency(self.total_cogs, self.curr_fmt)),
            ("Closing Stock & Assets", "Valuation after depreciation", format_currency(self.closing_stock, self.curr_fmt)),
            ("Operating Expenses", exp_desc, format_currency(self.total_expenses, self.curr_fmt))
        ]
        
        if self.total_depreciation > 0:
            self.detail_retained_earnings.insert(3, ("Asset Depreciation", "Calculated wear-and-tear loss", "-" + format_currency(self.total_depreciation, self.curr_fmt)))
            
        self.detail_retained_earnings.append(
            ("Net Result", "Final Retained Earnings (Rev - Purch + Stock - Exp)", format_currency(self.retained_earnings, self.curr_fmt))
        )
        # ---------------------------------------------------

    def refresh_data(self):
        self.calculate_balance_sheet()
        for widget in self.dynamic_wrapper.winfo_children():
            widget.destroy()
        self.build_dynamic_ui()

    def build_dynamic_ui(self):
        # ==========================================
        # 1. LOCK THE BOTTOM ROW FIRST
        # ==========================================
        bottom_row = tk.Frame(self.dynamic_wrapper, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1, padx=25, pady=20)
        bottom_row.pack(side="bottom", fill="x")

        b_left = tk.Frame(bottom_row, bg=self.t["card"])
        b_left.pack(side="left")
        tk.Label(b_left, text="Accounting Equation (Assets = Liabilities + Equity)", font=("Arial", 10), bg=self.t["card"], fg=self.t["sec"]).pack(anchor="w", pady=(0, 2))
        
        # --- THE FIX: Honest UI Labeling ---
        tk.Label(b_left, text="✓ Auto-Balanced via Derived Cash", font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["accent_green"]).pack(anchor="w")
        # -----------------------------------

        b_right = tk.Frame(bottom_row, bg=self.t["card"])
        b_right.pack(side="right")

        btn_export_csv = tk.Button(b_right, text="📥 Export CSV", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", highlightbackground=self.t["border"], highlightthickness=1, cursor="hand2", padx=20, pady=7, command=self.export_csv)
        btn_export_csv.pack(side="left", padx=(0, 10))

        btn_export_pdf = tk.Button(b_right, text="📥 Export PDF", font=("Arial", 10, "bold"), bg=self.t["bg"], fg=self.t["text"], relief="flat", highlightbackground=self.t["border"], highlightthickness=1, cursor="hand2", padx=20, pady=8, command=self.export_pdf)
        btn_export_pdf.pack(side="left")

        # ==========================================
        # 2. BUILD THE MIDDLE COLUMNS 
        # ==========================================
        mid_row = tk.Frame(self.dynamic_wrapper, bg=self.t["bg"])
        mid_row.pack(fill="both", expand=True, pady=(0, 20))

        # ------------------------------------------
        # LEFT COLUMN (LIABILITIES & EQUITY)
        # ------------------------------------------
        col_liabs = tk.Frame(mid_row, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        col_liabs.pack(side="left", fill="both", expand=True, padx=(0, 10))

        l_header = tk.Frame(col_liabs, bg=self.t["card"], pady=15, padx=20)
        l_header.pack(side="top", fill="x")
        tk.Label(l_header, text="📉 Liabilities & Equity", font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="left")
        tk.Label(l_header, text=format_currency(self.total_liab_equity, self.curr_fmt), font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="right")
        tk.Frame(col_liabs, bg=self.t["border"], height=1).pack(side="top", fill="x", padx=20)

        l_footer = tk.Frame(col_liabs, bg=self.t["bg"], highlightbackground=self.t["border"], highlightthickness=1, padx=15, pady=12)
        l_footer.pack(side="bottom", fill="x", padx=20, pady=15)
        tk.Label(l_footer, text=f"Total Liabilities & Equity  {format_currency(self.total_liab_equity, self.curr_fmt)}", font=("Arial", 11, "bold"), bg=self.t["bg"], fg=self.t["text"]).pack()

        l_scroll_container = tk.Frame(col_liabs, bg=self.t["card"])
        l_scroll_container.pack(side="top", fill="both", expand=True, pady=5)
        
        l_canvas = tk.Canvas(l_scroll_container, bg=self.t["card"], highlightthickness=0)
        l_scrollbar = ttk.Scrollbar(l_scroll_container, orient="vertical", command=l_canvas.yview, style="Vertical.TScrollbar")
        
        l_body = tk.Frame(l_canvas, bg=self.t["card"], padx=20, pady=10)
        l_body.bind("<Configure>", lambda e: l_canvas.configure(scrollregion=l_canvas.bbox("all")))
        l_canvas_win = l_canvas.create_window((0, 0), window=l_body, anchor="nw")
        l_canvas.bind("<Configure>", lambda e: l_canvas.itemconfig(l_canvas_win, width=e.width))
        l_canvas.configure(yscrollcommand=l_scrollbar.set)
        
        l_scrollbar.pack(side="right", fill="y")
        l_canvas.pack(side="left", fill="both", expand=True)

        tk.Label(l_body, text="EQUITY", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["sec"]).pack(anchor="w", pady=(5, 0))
        self.create_detail_row(l_body, "Opening Capital", "Initial investment value", self.active_capital, self.t["text"], command=lambda: self.open_drilldown("Opening Capital", ("Date", "Description", "Amount", "Type"), self.detail_opening_capital))
        self.create_detail_row(l_body, "Retained Earnings", "Net Profit / Loss generated", self.retained_earnings, self.t["accent_green"] if self.retained_earnings >= 0 else self.t["error"], command=lambda: self.open_drilldown("Retained Earnings Breakdown", ("Component", "Description", "Amount"), self.detail_retained_earnings))
        
        tk.Frame(l_body, bg=self.t["border"], height=1).pack(fill="x", pady=10)
        
        tk.Label(l_body, text="LIABILITIES", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["sec"]).pack(anchor="w", pady=(5, 0))
        self.create_detail_row(l_body, "Sundry Creditors (Payables)", "Unpaid vendor bills", self.accts_payable, self.t["error"], command=lambda: self.open_drilldown("Sundry Creditors", ("Date", "Bill / Vendor", "Balance Due", "Status"), self.detail_ap))
        self.create_detail_row(l_body, "Advances Received", "Client prepayments", self.advances_received, self.t["text"], command=lambda: self.open_drilldown("Advances Received", ("As Of", "Name", "Role", "Amount", "Details"), self.detail_adv_received))
        self.create_detail_row(l_body, "Salaries Payable", "Earned wages pending payment", self.salaries_payable, self.t["error"], command=lambda: self.open_drilldown("Salaries Payable", ("As Of", "Worker Name", "Net Owed", "Status"), self.detail_payables))
        
        # --- THE FIX: Display GST Payable Liability with Sub-Window ---
        if self.gst_payable > 0.01:
            gst_drill = [
                ("Output GST", "Total Tax collected from Sales", format_currency(self.output_gst, self.curr_fmt)), 
                ("Input GST", "Total Tax claimed from Purchases", "-" + format_currency(self.input_gst, self.curr_fmt))
            ]
            self.create_detail_row(l_body, "Net GST Payable", "Output GST > Input GST", self.gst_payable, self.t["error"], command=lambda: self.open_drilldown("GST Payable Breakdown", ("Component", "Description", "Amount"), gst_drill))
        # --------------------------------------------------------------

        # ------------------------------------------
        # RIGHT COLUMN (ASSETS)
        # ------------------------------------------
        col_assets = tk.Frame(mid_row, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        col_assets.pack(side="left", fill="both", expand=True, padx=(10, 0))

        a_header = tk.Frame(col_assets, bg=self.t["card"], pady=15, padx=20)
        a_header.pack(side="top", fill="x")
        tk.Label(a_header, text="📈 Assets", font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="left")
        tk.Label(a_header, text=format_currency(self.total_assets, self.curr_fmt), font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="right")
        tk.Frame(col_assets, bg=self.t["border"], height=1).pack(side="top", fill="x", padx=20)

        a_footer = tk.Frame(col_assets, bg=self.t["bg"], highlightbackground=self.t["border"], highlightthickness=1, padx=15, pady=12)
        a_footer.pack(side="bottom", fill="x", padx=20, pady=15)
        tk.Label(a_footer, text=f"Total Assets  {format_currency(self.total_assets, self.curr_fmt)}", font=("Arial", 11, "bold"), bg=self.t["bg"], fg=self.t["text"]).pack()

        a_scroll_container = tk.Frame(col_assets, bg=self.t["card"])
        a_scroll_container.pack(side="top", fill="both", expand=True, pady=5)
        
        a_canvas = tk.Canvas(a_scroll_container, bg=self.t["card"], highlightthickness=0)
        a_scrollbar = ttk.Scrollbar(a_scroll_container, orient="vertical", command=a_canvas.yview, style="Vertical.TScrollbar")
        
        a_body = tk.Frame(a_canvas, bg=self.t["card"], padx=20, pady=10)
        a_body.bind("<Configure>", lambda e: a_canvas.configure(scrollregion=a_canvas.bbox("all")))
        a_canvas_win = a_canvas.create_window((0, 0), window=a_body, anchor="nw")
        a_canvas.bind("<Configure>", lambda e: a_canvas.itemconfig(a_canvas_win, width=e.width))
        a_canvas.configure(yscrollcommand=a_scrollbar.set)
        
        a_scrollbar.pack(side="right", fill="y")
        a_canvas.pack(side="left", fill="both", expand=True)

        self.create_detail_row(a_body, "Cash & Bank Balance", "Derived liquid funds", self.cash_and_bank, self.t["accent_green"], command=lambda: self.open_drilldown("Cash & Bank Balance", ("As Of Date", "Description", "Amount", "Type"), self.detail_cash))
        self.create_detail_row(a_body, "Sundry Debtors (Receivables)", "Unpaid client invoices", self.accts_receivable, self.t["text"], command=lambda: self.open_drilldown("Sundry Debtors", ("Date", "Invoice / Client", "Balance Due", "Status"), self.detail_ar))
        self.create_detail_row(a_body, "Advances Paid", "Prepaid to vendors & staff", self.advances_paid, self.t["text"], command=lambda: self.open_drilldown("Advances Paid", ("As Of", "Name", "Role", "Amount", "Details"), self.detail_adv_paid))
        # --- THE FIX: Upgrade Asset Label to encompass Fixed Assets ---
        self.create_detail_row(a_body, "Closing Stock & Fixed Assets", "Net book value & inventory", self.closing_stock, self.t["text"], command=lambda: self.open_drilldown("Closing Stock & Fixed Assets", ("Last Updated", "Item Name", "Net Value", "Calculation Details"), self.detail_stock))
        
        # --- THE FIX: Display GST Receivable Asset with Sub-Window ---
        if self.gst_receivable > 0.01:
            gst_drill = [
                ("Input GST", "Total Tax claimed from Purchases", format_currency(self.input_gst, self.curr_fmt)), 
                ("Output GST", "Total Tax collected from Sales", "-" + format_currency(self.output_gst, self.curr_fmt))
            ]
            self.create_detail_row(a_body, "Net GST Receivable (ITC)", "Input GST > Output GST", self.gst_receivable, self.t["accent_green"], command=lambda: self.open_drilldown("GST Receivable Breakdown", ("Component", "Description", "Amount"), gst_drill))
        # -------------------------------------------------------------

    def create_detail_row(self, parent, title, subtitle, amount, amount_color, command=None):
        cursor_type = "hand2" if command else ""
        row = tk.Frame(parent, bg=self.t["card"], cursor=cursor_type)
        row.pack(fill="x", pady=10) 

        left = tk.Frame(row, bg=self.t["card"], cursor=cursor_type)
        left.pack(side="left")
        lbl_t = tk.Label(left, text=title, font=("Arial", 11), bg=self.t["card"], fg=self.t["text"], cursor=cursor_type)
        lbl_t.pack(anchor="w")
        lbl_s = tk.Label(left, text=subtitle, font=("Arial", 9), bg=self.t["card"], fg=self.t["sec"], cursor=cursor_type)
        lbl_s.pack(anchor="w", pady=(2, 0))

        right_container = tk.Frame(row, bg=self.t["card"], cursor=cursor_type)
        right_container.pack(side="right")

        lbl_a = tk.Label(right_container, text=format_currency(amount, self.curr_fmt), font=("Arial", 11, "bold"), bg=self.t["card"], fg=amount_color, cursor=cursor_type)
        lbl_a.pack(side="left")

        if command:
            lbl_arrow = tk.Label(right_container, text="›", font=("Arial", 16), bg=self.t["card"], fg=self.t["border"], cursor=cursor_type)
            lbl_arrow.pack(side="left", padx=(10, 0))
            
            def on_click(e): command()
            row.bind("<Button-1>", on_click)
            left.bind("<Button-1>", on_click)
            lbl_t.bind("<Button-1>", on_click)
            lbl_s.bind("<Button-1>", on_click)
            right_container.bind("<Button-1>", on_click)
            lbl_a.bind("<Button-1>", on_click)
            lbl_arrow.bind("<Button-1>", on_click)

    def open_drilldown(self, title, columns, data):
        pop = tk.Toplevel(self)
        pop.title(title)
        pop.configure(bg=self.t["bg"])
        pop.grab_set()
        
        pop.update_idletasks()
        w, h = 850, 550
        sw, sh = pop.winfo_screenwidth(), pop.winfo_screenheight()
        pop.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")

        header_f = tk.Frame(pop, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1, pady=15, padx=20)
        header_f.pack(fill="x")
        tk.Label(header_f, text=title, font=("Arial", 14, "bold"), bg=self.t["card"], fg=self.t["text"]).pack(side="left")

        table_f = tk.Frame(pop, bg=self.t["bg"], padx=20, pady=20)
        table_f.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Treeview.Heading", font=("Arial", 10, "bold"), background=self.t["card"], foreground=self.t["text"], relief="solid", borderwidth=1)
        style.configure("Dark.Treeview", font=("Arial", 10), rowheight=35, background=self.t["bg"], fieldbackground=self.t["bg"], foreground=self.t["text"], borderwidth=0)
        style.map("Dark.Treeview", background=[("selected", self.t["border"])], foreground=[("selected", "#ffffff")])

        style.configure("BS.Drill.Vertical.TScrollbar", background=self.t["sec"], troughcolor=self.t["bg"], bordercolor=self.t["bg"], arrowcolor=self.t["text"], relief="flat")
        style.configure("BS.Drill.Horizontal.TScrollbar", background=self.t["sec"], troughcolor=self.t["bg"], bordercolor=self.t["bg"], arrowcolor=self.t["text"], relief="flat")
        style.map("BS.Drill.Vertical.TScrollbar", background=[("active", self.t["accent_blue"])])
        style.map("BS.Drill.Horizontal.TScrollbar", background=[("active", self.t["accent_blue"])])
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="BS.Drill.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="BS.Drill.Horizontal.TScrollbar")
        
        actual_cols = list(columns) + ["ghost"]
        tree = ttk.Treeview(table_f, columns=actual_cols, show="headings", height=10, style="Dark.Treeview", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=tree.yview)
        scroll_x.config(command=tree.xview)
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        def _drill_fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                tree.yview_moveto(tree.yview()[0] + (delta * 0.008))
            else:
                tree.xview_moveto(tree.xview()[0] + (delta * 0.02))

        tree.bind("<MouseWheel>", lambda e: _drill_fast_scroll(e, "y"))
        tree.bind("<Shift-MouseWheel>", lambda e: _drill_fast_scroll(e, "x"))

        tree.tag_configure("evenrow", background=self.t["bg"], foreground=self.t["text"]) 
        tree.tag_configure("oddrow", background=self.t["card"], foreground=self.t["text"])  
        tree.tag_configure("empty", background=self.t["bg"])

        clean_title_key = "".join(e for e in title if e.isalnum())
        try:
            res = database.get_ui_setting(f"bs_drill_{clean_title_key}_cols_{self.comp_id}", "{}")
            w_dict = json.loads(res) if res else {}
        except:
            w_dict = {}

        for col in actual_cols:
            if col == "ghost":
                tree.heading(col, text="", anchor="center")
                tree.column(col, width=10, minwidth=10, stretch=True)
            else:
                tree.heading(col, text=col, anchor="e" if "Amount" in col or "Value" in col or "Balance" in col else "w")
                default_w = 150 if "Amount" in col or "Value" in col or "Balance" in col else (120 if "Date" in col else 250)
                tree.column(col, width=w_dict.get(col, default_w), minwidth=100, anchor="e" if "Amount" in col or "Value" in col or "Balance" in col else "w", stretch=False)

        def save_drill_widths():
            new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "ghost"}
            try:
                database.save_ui_setting(f"bs_drill_{clean_title_key}_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_drill_sep_drag(event):
            if tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_drill_widths)

        tree.bind("<B1-Motion>", on_drill_sep_drag, add="+")
        tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_drill_widths) if tree.identify_region(e.x, e.y) == "separator" else None, add="+")

        def populate_drilldown():
            for item in tree.get_children(): tree.delete(item)
            
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
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                empty_pad = [""] * len(actual_cols)
                tree.insert("", "end", iid=f"empty_{i}", values=empty_pad, tags=(tag, "empty"))
                
        populate_drilldown()
            
        def enforce_selection(e):
            for item in tree.selection():
                if str(item).startswith("empty_"): tree.selection_remove(item)
        tree.bind("<<TreeviewSelect>>", enforce_selection)

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], 
            title="Save Balance Sheet as CSV"
        )
        if not file_path: return
            
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                
                writer.writerow(["BALANCE SHEET REPORT"])
                writer.writerow(["As Of Date", self.as_of_var.get()])
                writer.writerow(["Generated on", datetime.now().strftime(self.date_fmt_code)])
                writer.writerow([])
                
                writer.writerow(["LIABILITIES & EQUITY"])
                writer.writerow(["Opening Capital", format_currency(self.active_capital, self.curr_fmt)])
                writer.writerow(["Retained Earnings", format_currency(self.retained_earnings, self.curr_fmt)])
                writer.writerow(["Sundry Creditors (Payables)", format_currency(self.accts_payable, self.curr_fmt)])
                writer.writerow(["Advances Received", format_currency(self.advances_received, self.curr_fmt)])
                writer.writerow(["Salaries Payable", format_currency(self.salaries_payable, self.curr_fmt)])
                writer.writerow(["TOTAL LIAB & EQUITY", format_currency(self.total_liab_equity, self.curr_fmt)])
                writer.writerow([])

                writer.writerow(["ASSETS"])
                writer.writerow(["Cash & Bank Balance", format_currency(self.cash_and_bank, self.curr_fmt)])
                writer.writerow(["Sundry Debtors (Receivables)", format_currency(self.accts_receivable, self.curr_fmt)])
                writer.writerow(["Advances Paid", format_currency(self.advances_paid, self.curr_fmt)])
                writer.writerow(["Closing Stock & Fixed Assets", format_currency(self.closing_stock, self.curr_fmt)])
                writer.writerow(["TOTAL ASSETS", format_currency(self.total_assets, self.curr_fmt)])
                writer.writerow([])
                        
            messagebox.showinfo("Export Successful", f"Balance Sheet exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while saving the file:\n{str(e)}")

    def export_pdf(self):
        # --- THE FIX: Fetch Company Name ---
        try:
            comp = database.get_company(self.comp_id)
            comp_name = comp[1] if comp else "COMPANY NAME"
        except:
            comp_name = "COMPANY NAME"
        # -----------------------------------

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Balance Sheet Report</title>
            <style>
                @media print {{
                    @page {{ margin: 0; size: A4 portrait; }}
                    body {{ margin: 1.5cm; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                }}
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6; }}
                h1 {{ color: #0f172a; text-align: center; margin-bottom: 5px; font-size: 26px; }}
                .date-stamp {{ text-align: center; color: #64748b; font-size: 14px; margin-bottom: 30px; }}
                
                .details-container {{ display: flex; justify-content: space-between; gap: 20px; align-items: stretch; }}
                .col {{ flex: 1; display: flex; flex-direction: column; }}
                
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 0px; border: 1px solid #cbd5e1; }}
                th {{ text-align: left; background-color: #1e293b; color: white; padding: 12px; font-size: 15px; border: 1px solid #1e293b; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                td {{ padding: 12px; border: 1px solid #e2e8f0; }}
                .amt-col {{ text-align: right; font-weight: bold; border-left: 1px solid #e2e8f0; }}
                
                .footer-total td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; border: 1px solid #cbd5e1; border-top: 2px solid #0f172a; color: #0f172a; -webkit-print-color-adjust: exact; print-color-adjust: exact; padding: 15px; }}
                .sub-header td {{ background-color: #f8fafc; font-weight: bold; font-size: 12px; color: #64748b; letter-spacing: 1px; text-transform: uppercase; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                
                .title-txt {{ font-weight: bold; color: #1e293b; display: block; font-size: 13px; }}
                .sub-txt {{ font-size: 11px; color: #64748b; display: block; margin-top: 4px; font-weight: normal; }}
            </style>
        </head>
        <body>
            <h1>Balance Sheet</h1>
            <div class="date-stamp">
                <b style="font-size: 18px; color: #0f172a;">{comp_name}</b><br>
                As Of Date: {self.as_of_var.get()} &nbsp;|&nbsp; {self.acc_method_var.get()}<br>
                <span style="font-size:11px;">Generated on: {datetime.now().strftime(self.date_fmt_code)}</span>
            </div>
            
            <div class="details-container">
                <!-- LEFT COLUMN -->
                <div class="col">
                    <div style="flex-grow: 1;">
                        <table>
                            <tr><th colspan="2">📉 LIABILITIES & EQUITY</th></tr>
                            <tr class="sub-header"><td colspan="2">EQUITY</td></tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Opening Capital</span>
                                    <span class="sub-txt">Initial investment value</span>
                                </td>
                                <td class="amt-col">{format_currency(self.active_capital, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Retained Earnings</span>
                                    <span class="sub-txt">Net Profit / Loss generated</span>
                                </td>
                                <td class="amt-col">{format_currency(self.retained_earnings, self.curr_fmt)}</td>
                            </tr>
                            <tr class="sub-header"><td colspan="2">LIABILITIES</td></tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Sundry Creditors (Payables)</span>
                                    <span class="sub-txt">Unpaid vendor bills</span>
                                </td>
                                <td class="amt-col" style="color:#ef4444;">{format_currency(self.accts_payable, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Advances Received</span>
                                    <span class="sub-txt">Client prepayments</span>
                                </td>
                                <td class="amt-col">{format_currency(self.advances_received, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Salaries Payable</span>
                                    <span class="sub-txt">Earned wages pending payment</span>
                                </td>
                                <td class="amt-col" style="color:#ef4444;">{format_currency(self.salaries_payable, self.curr_fmt)}</td>
                            </tr>
                        </table>
                    </div>
                    <!-- ANCHORED TOTAL -->
                    <table style="margin-top: auto;">
                        <tr class="footer-total">
                            <td>Total Liabilities & Equity</td>
                            <td class="amt-col">{format_currency(self.total_liab_equity, self.curr_fmt)}</td>
                        </tr>
                    </table>
                </div>

                <!-- RIGHT COLUMN -->
                <div class="col">
                    <div style="flex-grow: 1;">
                        <table>
                            <tr><th colspan="2">📈 ASSETS</th></tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Cash & Bank Balance</span>
                                    <span class="sub-txt">Derived liquid funds</span>
                                </td>
                                <td class="amt-col" style="color:#10b981;">{format_currency(self.cash_and_bank, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Sundry Debtors (Receivables)</span>
                                    <span class="sub-txt">Unpaid client invoices</span>
                                </td>
                                <td class="amt-col">{format_currency(self.accts_receivable, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Advances Paid</span>
                                    <span class="sub-txt">Prepaid to vendors & staff</span>
                                </td>
                                <td class="amt-col">{format_currency(self.advances_paid, self.curr_fmt)}</td>
                            </tr>
                            <tr>
                                <td>
                                    <span class="title-txt">Closing Stock & Fixed Assets</span>
                                    <span class="sub-txt">Net book value & inventory</span>
                                </td>
                                <td class="amt-col">{format_currency(self.closing_stock, self.curr_fmt)}</td>
                            </tr>
                        </table>
                    </div>
                    <!-- ANCHORED TOTAL -->
                    <table style="margin-top: auto;">
                        <tr class="footer-total">
                            <td>Total Assets</td>
                            <td class="amt-col">{format_currency(self.total_assets, self.curr_fmt)}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <script>
                window.onload = function() {{ window.print(); }}
            </script>
        </body>
        </html>
        """
        
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Balance_Sheet_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        webbrowser.open('file://' + os.path.realpath(path))