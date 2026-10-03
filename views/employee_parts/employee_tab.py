import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
import sys
import json
import csv
import database
from datetime import date, datetime, timedelta

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
# -----------------------------------------------

from views.invoice_parts.helpers import format_currency, fetch_global_settings, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar

from views.employee_parts.employee_dialogs import open_employee_dialog, open_pay_dialog
from views.employee_parts.employee_profile import open_employee_ledger
from views.employee_parts.employee_payments import EmployeePaymentsDashboard

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class EmployeeTab(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        self.BG_COLOR = "#0f172a" if self.is_dark else "#e0f2fe"
        self.CARD_BG = "#1e293b" if self.is_dark else "#f0f9ff"
        self.BORDER_COLOR = "#334155" if self.is_dark else "#7dd3fc"
        self.TEXT_PRIMARY = "#f8fafc" if self.is_dark else "#0f172a"
        self.TEXT_SECONDARY = "#94a3b8" if self.is_dark else "#0284c7"
        self.ACCENT_GREEN = "#10b981"
        self.ACCENT_RED = "#ef4444"
        self.ACCENT_YELLOW = "#f59e0b"
        self.ACCENT_BLUE = "#3b82f6" if self.is_dark else "#0ea5e9"
        self.HEADER_BG = "#475569" if self.is_dark else "#bae6fd"
        
        super().__init__(parent, bg=self.BG_COLOR)
        
        self.app = self.winfo_toplevel()
        comp_id = getattr(self.app, "active_company_id", 1)
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
        
        self.privacy_mode = True
        self.roster_status_var = tk.StringVar(value="Active")
        self.visible_salaries = set()  
        self.roster_search_var = tk.StringVar()
        
        # --- THE FIX: Add Bulk Mode Trackers ---
        self.is_bulk_mode = False
        self.selected_items = set()
        # ---------------------------------------
        
        self.undo_stack = []
        self.redo_stack = []
        self.photo_cache = []

        self.roster_search_timer = None
        def trigger_roster_search(*args):
            if self.roster_search_timer: self.after_cancel(self.roster_search_timer)
            self.roster_search_timer = self.after(300, self.load_roster)
        self.roster_search_var.trace_add("write", trigger_roster_search)

        self.app.bind("<Control-z>", lambda e: self.perform_undo() if self.winfo_ismapped() else None)
        self.app.bind("<Control-y>", lambda e: self.perform_redo() if self.winfo_ismapped() else None)

        self.build_ui()
        self.load_all_data()

    def enable_bulk(self):
        self.is_bulk_mode = True
        self.selected_items.clear()
        self.toolbar_top.pack_forget()
        self.toolbar_bottom.pack_forget()
        self.bulk_tools_f.pack(fill="x", pady=(0, 5))
        self.tree_roster.heading("sno", text="☑")
        self.load_roster()

    def cancel_bulk(self):
        self.is_bulk_mode = False
        self.selected_items.clear()
        self.bulk_tools_f.pack_forget()
        self.toolbar_top.pack(fill="x", pady=(0, 5))
        self.toolbar_bottom.pack(fill="x")
        self.tree_roster.heading("sno", text="#")
        self.load_roster()

    def select_all_bulk(self):
        all_items = [child for child in self.tree_roster.get_children() if not str(child).startswith("empty")]
        if len(self.selected_items) == len(all_items):
            self.selected_items.clear()
        else:
            for c in all_items: self.selected_items.add(c)
        self.load_roster()

    def print_bulk_ids(self):
        if not self.selected_items:
            messagebox.showinfo("Empty", "No employees selected.", parent=self)
            return
        from views.employee_parts.employee_details import print_bulk_employee_ids
        print_bulk_employee_ids(self, list(self.selected_items))
        self.cancel_bulk()

    def toggle_privacy_mode(self):
        if self.privacy_mode:
            comp_id = getattr(self.winfo_toplevel(), "active_company_id", getattr(self.app, "active_company_id", 1))
            actual_pin = ""
            try:
                # --- THE FIX: MVC Compliant PIN Fetch (No PRAGMA hacks) ---
                comp_data = database.get_company(comp_id)
                if comp_data and len(comp_data) > 15 and comp_data[15]:
                    actual_pin = str(comp_data[15]).strip()
                # ----------------------------------------------------------
            except Exception: pass

            if actual_pin and actual_pin.lower() not in ("none", "null", "false", "0", ""):
                pwd = simpledialog.askstring("Security Verification", "Enter Company PIN to unmask financials:", parent=self, show='*')
                if pwd != actual_pin:
                    if pwd is not None: messagebox.showerror("Access Denied", "Incorrect Security PIN.", parent=self)
                    return

            self.privacy_mode = False
            self.btn_privacy.config(text="👁️ Mask Financials", fg=self.TEXT_SECONDARY)
        else:
            self.privacy_mode = True
            self.btn_privacy.config(text="👁️ Show Financials", fg=self.ACCENT_RED)
            
        self.load_all_data()

    def push_undo(self, action_type, data):
        self.undo_stack.append((action_type, data))
        self.redo_stack.clear()
        self.update_undo_redo_btns()

    def perform_undo(self, event=None):
        if not self.undo_stack: return
        action, data = self.undo_stack.pop()
        
        try:
            if action == "ADD_EMP":
                full_row = database.get_employee_full_record(data)
                if full_row: 
                    # Soft delete the employee to undo the addition safely
                    database.delete_employee(data)
                    self.redo_stack.append(("ADD_EMP", full_row))
                
            elif action == "DELETE_EMP_FULL":
                emp_row, pay_rows = data
                database.restore_deleted_employee(emp_row[0])
                self.redo_stack.append(("DELETE_EMP_FULL", data))
                
            elif action == "EDIT_EMP":
                old_row, new_row = data
                database.update_employee_record_full(old_row)
                self.redo_stack.append(("EDIT_EMP", (new_row, old_row)))
                
            elif action == "ADD_PAY":
                full_row = database.get_employee_payment_record(data)
                if full_row:
                    database.delete_employee_payment_and_rollback(data)
                    self.redo_stack.append(("ADD_PAY", full_row))
                
            elif action == "DELETE_PAY":
                database.restore_employee_payment_record(data)
                self.redo_stack.append(("DELETE_PAY", data))
                
            elif action == "BULK_DELETE_PAY":
                for row in data:
                    database.restore_employee_payment_record(row)
                self.redo_stack.append(("BULK_DELETE_PAY", data))
                
        except Exception as e: messagebox.showerror("Undo Error", str(e), parent=self)
            
        self.update_undo_redo_btns()
        self.load_all_data()

    def perform_redo(self, event=None):
        if not self.redo_stack: return
        action, data = self.redo_stack.pop()
        
        try:
            if action == "ADD_EMP":
                # If we soft-deleted it in undo, restore it now
                database.restore_deleted_employee(data[0])
                self.undo_stack.append(("ADD_EMP", data[0])) 
                
            elif action == "DELETE_EMP_FULL":
                emp_row, pay_rows = data
                database.delete_employee(emp_row[0])
                self.undo_stack.append(("DELETE_EMP_FULL", data))
                
            elif action == "EDIT_EMP":
                new_row, old_row = data
                database.update_employee_record_full(new_row)
                self.undo_stack.append(("EDIT_EMP", (old_row, new_row)))
                
            elif action == "ADD_PAY":
                database.restore_employee_payment_record(data)
                self.undo_stack.append(("ADD_PAY", data[0]))
                
            elif action == "DELETE_PAY":
                database.delete_employee_payment_and_rollback(data[0])
                self.undo_stack.append(("DELETE_PAY", data))
                
            elif action == "BULK_DELETE_PAY":
                for row in data:
                    database.delete_employee_payment_and_rollback(row[0])
                self.undo_stack.append(("BULK_DELETE_PAY", data))
                
        except Exception as e: messagebox.showerror("Redo Error", str(e), parent=self)
            
        self.update_undo_redo_btns()
        self.load_all_data()

    def update_undo_redo_btns(self):
        if hasattr(self, 'btn_undo'):
            if self.undo_stack: self.btn_undo.config(fg=self.ACCENT_GREEN, state="normal")
            else: self.btn_undo.config(fg=self.TEXT_SECONDARY, state="disabled")
            if self.redo_stack: self.btn_redo.config(fg=self.ACCENT_BLUE, state="normal")
            else: self.btn_redo.config(fg=self.TEXT_SECONDARY, state="disabled")

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default")
        
        self.app.option_add("*TCombobox*Listbox.background", self.CARD_BG)
        self.app.option_add("*TCombobox*Listbox.foreground", self.TEXT_PRIMARY)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.ACCENT_BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", self.TEXT_PRIMARY)
        
        style.configure("TCombobox", fieldbackground=self.BG_COLOR, background=self.CARD_BG, foreground=self.TEXT_PRIMARY, arrowcolor=self.TEXT_PRIMARY, bordercolor=self.BORDER_COLOR, lightcolor=self.BORDER_COLOR, darkcolor=self.BORDER_COLOR)
        style.map("TCombobox", fieldbackground=[("readonly", self.BG_COLOR)], selectbackground=[("readonly", self.BG_COLOR)], selectforeground=[("readonly", self.TEXT_PRIMARY)])

        # --- THE FIX: Thick Solid Scrollbar Styles! ---
        style.configure("Emp.Vertical.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.configure("Emp.Horizontal.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.map("Emp.Vertical.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        style.map("Emp.Horizontal.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        # ----------------------------------------------

        top_f = tk.Frame(self, bg=self.BG_COLOR)
        top_f.pack(fill="x", pady=(5, 10))

        tiles_f = tk.Frame(top_f, bg=self.BG_COLOR)
        tiles_f.pack(side="left", fill="x", expand=True)

        def create_tile(parent, title, color, click_cmd=None):
            f = tk.Frame(parent, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
            f.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(f, text=title, font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w", padx=15, pady=(15, 5))
            lbl = tk.Label(f, text="0", font=("Arial", 18, "bold"), bg=self.CARD_BG, fg=color)
            lbl.pack(anchor="w", padx=15, pady=(0, 15))
            if click_cmd:
                f.config(cursor="hand2")
                for w in f.winfo_children(): w.config(cursor="hand2")
                f.bind("<Button-1>", lambda e: click_cmd())
                for w in f.winfo_children(): w.bind("<Button-1>", lambda e: click_cmd())
            return f, lbl

        self.tile_sal_f, self.lbl_tile_sal = create_tile(tiles_f, "TOTAL SALARIES PAID", self.ACCENT_GREEN, lambda: EmployeePaymentsDashboard(self, initial_filter="Salary"))
        self.tile_bon_f, self.lbl_tile_bon = create_tile(tiles_f, "TOTAL BONUSES", self.ACCENT_YELLOW, lambda: EmployeePaymentsDashboard(self, initial_filter="Bonus"))
        self.tile_adv_f, self.lbl_tile_adv = create_tile(tiles_f, "TOTAL ADVANCES", self.ACCENT_BLUE, lambda: EmployeePaymentsDashboard(self, initial_filter="Advance"))
        self.tile_emp_f, self.lbl_tile_emp = create_tile(tiles_f, "ACTIVE EMPLOYEES", self.TEXT_PRIMARY)

        toolbar_right = tk.Frame(top_f, bg=self.BG_COLOR)
        toolbar_right.pack(side="right", anchor="n")

        self.toolbar_top = tk.Frame(toolbar_right, bg=self.BG_COLOR)
        self.toolbar_top.pack(fill="x", pady=(0, 5))
        
        self.toolbar_bottom = tk.Frame(toolbar_right, bg=self.BG_COLOR)
        self.toolbar_bottom.pack(fill="x")
        
        # --- THE FIX: Create the hidden Bulk Tools Toolbar ---
        self.bulk_tools_f = tk.Frame(toolbar_right, bg=self.BG_COLOR)
        
        tk.Label(self.bulk_tools_f, text="Selection Mode Active", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_RED).pack(side="left", padx=(0, 15))
        
        btn_cancel_bulk = tk.Button(self.bulk_tools_f, text="✖ Cancel", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=15, pady=4, command=self.cancel_bulk)
        btn_cancel_bulk.pack(side="right")
        
        btn_select_all = tk.Button(self.bulk_tools_f, text="☑ Select All", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=15, pady=4, command=self.select_all_bulk)
        btn_select_all.pack(side="right", padx=(0, 10))
        
        self.btn_bulk_print = tk.Button(self.bulk_tools_f, text="🪪 Print Selected IDs", font=("Arial", 10, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=4, command=self.print_bulk_ids)
        self.btn_bulk_print.pack(side="right", padx=(0, 10))
        # -----------------------------------------------------

        self.btn_privacy = tk.Button(self.toolbar_top, text="👁️ Show Financials", font=("Arial", 11, "bold"), bg=self.CARD_BG, fg=self.ACCENT_RED, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=self.toggle_privacy_mode)
        self.btn_privacy.pack(side="left", padx=(0, 15))

        self.btn_undo = tk.Button(self.toolbar_top, text="↺ Undo", font=("Arial", 11, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, state="disabled", relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=self.perform_undo)
        self.btn_undo.pack(side="left", padx=(0, 5))
        
        self.btn_redo = tk.Button(self.toolbar_top, text="↻ Redo", font=("Arial", 11, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, state="disabled", relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=self.perform_redo)
        self.btn_redo.pack(side="left", padx=(0, 20))

        btn_add = tk.Button(self.toolbar_top, text="+ Add Employee", font=("Arial", 10, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", width=16, pady=6)
        btn_add.config(command=lambda b=btn_add: open_employee_dialog(self.winfo_toplevel(), refresh_cb=self.load_all_data, undo_cb=self.push_undo, widget=b))
        btn_add.pack(side="left")

        self.btn_payments = tk.Button(self.toolbar_bottom, text="💸 Recent Payments", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=15, pady=4, command=lambda: EmployeePaymentsDashboard(self))
        self.btn_payments.pack(side="left")

        main_container = tk.Frame(self, bg=self.BG_COLOR)
        main_container.pack(fill="both", expand=True, pady=(10, 0))

        def clear_focus(event):
            if str(event.widget).startswith(str(self)):
                if hasattr(event.widget, 'winfo_class'):
                    w_class = event.widget.winfo_class()
                    if w_class not in ('Entry', 'TCombobox', 'Text', 'Treeview'):
                        self.focus_set()
                        if hasattr(self, 'tree_roster') and self.tree_roster.selection():
                            self.tree_roster.selection_remove(self.tree_roster.selection())
        self.bind_all("<ButtonPress-1>", clear_focus, add="+")

        style.configure("Emp.Treeview.Heading", font=("Arial", 10, "bold"), background=self.HEADER_BG, foreground=self.TEXT_PRIMARY, relief="raised", borderwidth=3)
        style.map("Emp.Treeview.Heading", background=[('active', '#64748b' if self.is_dark else self.BORDER_COLOR)])
        style.configure("Emp.Treeview", font=("Arial", 11), rowheight=125, background=self.BG_COLOR, fieldbackground=self.BG_COLOR, foreground=self.TEXT_PRIMARY, borderwidth=0)
        style.map("Emp.Treeview", background=[("selected", self.BORDER_COLOR)], foreground=[("selected", "#ffffff" if self.is_dark else self.TEXT_PRIMARY)])

        # --- THE FIX: Buttery Smooth Horizontal & Vertical Scrolling ---
        def _fast_scroll(event, direction, target_tree):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                target_tree.yview_moveto(target_tree.yview()[0] + (delta * 0.008))
            else:
                target_tree.xview_moveto(target_tree.xview()[0] + (delta * 0.02))
        # ---------------------------------------------------------------

        roster_f = tk.Frame(main_container, bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        roster_f.pack(fill="both", expand=True)

        r_head = tk.Frame(roster_f, bg=self.CARD_BG)
        r_head.pack(fill="x")
        tk.Label(r_head, text="TEAM ROSTER & PAYROLL", font=("Arial", 10, "bold"), fg=self.TEXT_PRIMARY, bg=self.CARD_BG).pack(side="left", padx=(15, 5), pady=10)
        
        tk.Label(r_head, text="🔍 Search:", bg=self.CARD_BG, font=("Arial", 9, "bold"), fg=self.TEXT_SECONDARY).pack(side="left", padx=(10, 5))
        r_ent = tk.Entry(r_head, textvariable=self.roster_search_var, font=("Arial", 10), width=18, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        r_ent.pack(side="left", ipady=3)
        
        # --- THE FIX: Perfectly Sized Red 'X' Clear Button ---
        btn_clear_search = tk.Button(r_head, text="✖", font=("Arial", 9), bg=self.BORDER_COLOR, fg=self.ACCENT_RED, activebackground=self.BORDER_COLOR, activeforeground=self.ACCENT_RED, relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=lambda: self.roster_search_var.set(""))
        btn_clear_search.pack(side="left", padx=(2, 10), ipady=1, ipadx=3)
        # -----------------------------------------------------
        
        roster_cb = ttk.Combobox(r_head, textvariable=self.roster_status_var, values=["Active", "Inactive / Resigned", "All Employees"], state="readonly", width=18, font=("Arial", 10), cursor="hand2")
        roster_cb.pack(side="right", padx=(15, 15), ipady=3)
        roster_cb.bind("<<ComboboxSelected>>", lambda e: self.load_roster())
        tk.Label(r_head, text="Status:", bg=self.CARD_BG, font=("Arial", 9, "bold"), fg=self.TEXT_SECONDARY).pack(side="right", padx=(5, 5))

        # --- THE FIX: Added Sort Dropdown ---
        if not hasattr(self, 'roster_sort_var'):
            self.roster_sort_var = tk.StringVar(value="ID (Ascending)")
            
        sort_cb = ttk.Combobox(r_head, textvariable=self.roster_sort_var, values=["ID (Ascending)", "ID (Descending)", "Name (A to Z)", "Name (Z to A)"], state="readonly", width=16, font=("Arial", 10), cursor="hand2")
        sort_cb.pack(side="right", padx=(15, 5), ipady=3)
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.load_roster())
        tk.Label(r_head, text="Sort By:", bg=self.CARD_BG, font=("Arial", 9, "bold"), fg=self.TEXT_SECONDARY).pack(side="right", padx=(15, 5))
        # ------------------------------------

        tree_container_r = tk.Frame(roster_f, bg=self.CARD_BG)
        tree_container_r.pack(fill="both", expand=True)

        # --- THE FIX: Apply isolated Employee scrollbar styles ---
        scroll_r_y = ttk.Scrollbar(tree_container_r, orient="vertical", style="Emp.Vertical.TScrollbar")
        scroll_r_y.pack(side="right", fill="y")
        scroll_r_x = ttk.Scrollbar(tree_container_r, orient="horizontal", style="Emp.Horizontal.TScrollbar")
        scroll_r_x.pack(side="bottom", fill="x")
        # ---------------------------------------------------------

        # --- THE FIX: Add an invisible 'ghost' column to absorb stretching! ---
        cols_r = ("sno", "emp_id", "name", "role", "join", "salary", "status", "actions", "ghost")
        self.tree_roster = ttk.Treeview(tree_container_r, columns=cols_r, show="tree headings", style="Emp.Treeview", yscrollcommand=scroll_r_y.set, xscrollcommand=scroll_r_x.set)
        # ----------------------------------------------------------------------
        self.tree_roster.pack(side="left", fill="both", expand=True)
        
        scroll_r_y.config(command=self.tree_roster.yview)
        scroll_r_x.config(command=self.tree_roster.xview)
        
        self.tree_roster.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y", self.tree_roster))
        self.tree_roster.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x", self.tree_roster))

        self.tree_roster.heading("#0", text="PHOTO", anchor="center")
        self.tree_roster.heading("sno", text="#", anchor="center")
        self.tree_roster.heading("emp_id", text="ID NO.", anchor="center")
        self.tree_roster.heading("name", text="NAME", anchor="w")
        self.tree_roster.heading("role", text="ROLE", anchor="w")
        self.tree_roster.heading("join", text="JOIN DATE", anchor="center")
        self.tree_roster.heading("salary", text="MONTHLY SALARY", anchor="w")
        self.tree_roster.heading("status", text="STATUS", anchor="w")
        self.tree_roster.heading("actions", text="ACTIONS", anchor="center")

        # --- THE FIX: Excel-Style Widths + Inventory Real-Time Saving Engine ---
        comp_id = getattr(self.winfo_toplevel(), "active_company_id", getattr(self.app, "active_company_id", 1))
        try:
            r_w = json.loads(database.get_ui_setting(f"emp_roster_widths_{comp_id}", "{}"))
        except:
            r_w = {}

        self.tree_roster.column("#0", width=r_w.get("#0", 130), minwidth=80, stretch=False, anchor="center")
        self.tree_roster.column("sno", width=r_w.get("sno", 60), minwidth=40, stretch=False, anchor="center")
        self.tree_roster.column("emp_id", width=r_w.get("emp_id", 120), minwidth=70, stretch=False, anchor="center")
        self.tree_roster.column("name", width=r_w.get("name", 300), minwidth=150, stretch=False, anchor="w")
        self.tree_roster.column("role", width=r_w.get("role", 200), minwidth=100, stretch=False, anchor="w")
        self.tree_roster.column("join", width=r_w.get("join", 120), minwidth=90, stretch=False, anchor="center")
        self.tree_roster.column("salary", width=r_w.get("salary", 160), minwidth=100, stretch=False, anchor="w")
        self.tree_roster.column("status", width=r_w.get("status", 150), minwidth=100, stretch=False, anchor="w")
        
        # --- THE FIX: Actions locks its width, Ghost takes the stretch! ---
        self.tree_roster.column("actions", width=r_w.get("actions", 160), minwidth=100, stretch=False, anchor="center")
        
        self.tree_roster.heading("ghost", text="")
        self.tree_roster.column("ghost", width=10, minwidth=10, stretch=True)
        # ------------------------------------------------------------------

        def save_r_widths():
            new_w = {c: self.tree_roster.column(c, "width") for c in ("sno", "emp_id", "name", "role", "join", "salary", "status", "actions")}
            new_w["#0"] = self.tree_roster.column("#0", "width")
            try:
                current_comp = getattr(self.winfo_toplevel(), "active_company_id", getattr(self.app, "active_company_id", 1))
                # --- THE FIX: Use safe helper to attach ACTIVE_COMPANY_ID and prevent ghost data! ---
                database.save_ui_setting(f"emp_roster_widths_{current_comp}", json.dumps(new_w))
                # ------------------------------------------------------------------------------------
            except: pass

        def on_r_sep_drag(event):
            if self.tree_roster.identify_region(event.x, event.y) == "separator":
                self.after(50, save_r_widths)
                
        self.tree_roster.bind("<B1-Motion>", on_r_sep_drag, add="+")
        self.tree_roster.bind("<ButtonRelease-1>", lambda e: self.after(50, save_r_widths) if self.tree_roster.identify_region(e.x, e.y) == "separator" else None, add="+")
        # -----------------------------------------------------------------------

        self.tree_roster.tag_configure("selected_row", background=self.BORDER_COLOR)
        self.tree_roster.tag_configure("evenrow", background=self.BG_COLOR)
        self.tree_roster.tag_configure("oddrow", background=self.CARD_BG)
        self.tree_roster.tag_configure("active_txt", foreground=self.ACCENT_GREEN if self.is_dark else "#166534")
        self.tree_roster.tag_configure("inactive_txt", foreground=self.ACCENT_RED if self.is_dark else "#991b1b")
        self.tree_roster.tag_configure("empty_row", background=self.CARD_BG)

        self.tree_roster.bind("<Double-1>", self.on_roster_double_click)

        def on_roster_motion(event):
            region = self.tree_roster.identify("region", event.x, event.y)
            if region == "separator": return
            col = self.tree_roster.identify_column(event.x)
            item = self.tree_roster.identify_row(event.y)
            if str(item).startswith("empty"): 
                self.tree_roster.config(cursor="")
                return
            if region == "cell" and col in ('#3', '#6', '#8') and not self.is_bulk_mode:
                self.tree_roster.config(cursor="hand2")
            elif self.is_bulk_mode:
                self.tree_roster.config(cursor="hand2")
            else:
                self.tree_roster.config(cursor="")
        self.tree_roster.bind("<Motion>", on_roster_motion)
        
        # --- THE FIX: Block Actions if Click Started in the Header/Separator ---
        def on_roster_press(event):
            self._roster_press_region = self.tree_roster.identify("region", event.x, event.y)
        self.tree_roster.bind("<ButtonPress-1>", on_roster_press, add="+")

        def safe_roster_click(event):
            if getattr(self, "_roster_press_region", "") != "cell": return
            region = self.tree_roster.identify("region", event.x, event.y)
            if region != "cell": return
            self.on_roster_click(event)
        self.tree_roster.bind("<ButtonRelease-1>", safe_roster_click, add="+")
        self.tree_roster.bind("<Button-3>", self.on_roster_right_click)
        # -----------------------------------------------------------------------

    def load_all_data(self):
        comp_id = getattr(self.winfo_toplevel(), "active_company_id", getattr(self.app, "active_company_id", 1))
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
        self.load_roster()

    def load_roster(self):
        self.photo_cache.clear() 
        for item in self.tree_roster.get_children(): 
            self.tree_roster.delete(item)
            
        database.sync_all_employee_statuses()
        tot_sal, tot_bon, tot_adv, active_count = database.get_employee_dashboard_stats()
        
        comp_id = getattr(self.winfo_toplevel(), "active_company_id", getattr(self.app, "active_company_id", 1))
        allowed_fin, _ = database.check_employee_permission(action="view_financials", company_id=comp_id)
        
        if not allowed_fin:
            self.lbl_tile_sal.config(text="🔒 Hidden")
            self.lbl_tile_bon.config(text="🔒 Hidden")
            self.lbl_tile_adv.config(text="🔒 Hidden")
        elif self.privacy_mode:
            self.lbl_tile_sal.config(text="***")
            self.lbl_tile_bon.config(text="***")
            self.lbl_tile_adv.config(text="***")
        else:
            self.lbl_tile_sal.config(text=format_currency(tot_sal, self.curr_fmt))
            self.lbl_tile_bon.config(text=format_currency(tot_bon, self.curr_fmt))
            self.lbl_tile_adv.config(text=format_currency(tot_adv, self.curr_fmt))
            
        self.lbl_tile_emp.config(text=str(active_count))

        rows = database.get_all_employees(order_by="id ASC")
        search_term = self.roster_search_var.get().lower()
        status_filter = self.roster_status_var.get()
        sort_mode = getattr(self, 'roster_sort_var', tk.StringVar(value="ID (Ascending)")).get()

        import re
        def natural_sort_key(s):
            # Splits letters and digits so emp1 < emp2 < emp10 < wid 1
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

        processed_employees = []
        
        for r in rows:
            emp_id, emp_name, emp_role, emp_salary, emp_join = r[0], r[1], r[4], r[5], r[6]
            
            emp_id_str = f"EMP-{int(emp_id):04d}" 
            d_j = r[10]
            if d_j:
                try:
                    p = json.loads(d_j)
                    if isinstance(p, dict) and p.get("emp_id_str"): emp_id_str = p.get("emp_id_str")
                except: pass
            
            if search_term and search_term not in str(emp_name).lower() and search_term not in str(emp_role).lower() and search_term not in emp_id_str.lower():
                continue

            resign_str = r[11] if len(r)>11 and r[11] else ""
            rejoin_str = r[12] if len(r)>12 and r[12] else ""
            
            is_active = True
            if resign_str and not rejoin_str: is_active = False

            if status_filter == "Active" and not is_active: continue
            if status_filter == "Inactive / Resigned" and is_active: continue
            
            processed_employees.append({
                "raw_data": r,
                "emp_id": emp_id,
                "emp_id_str": emp_id_str,
                "emp_name": emp_name,
                "emp_role": emp_role,
                "emp_salary": emp_salary,
                "emp_join": emp_join,
                "is_active": is_active,
                "resign_str": resign_str,
                "rejoin_str": rejoin_str,
                "is_pinned": int(r[15]) if len(r) > 15 and r[15] else 0
            })

        # --- FIRST PASS: Apply Natural Sorting Filter ---
        if sort_mode == "ID (Descending)":
            processed_employees.sort(key=lambda x: natural_sort_key(x["emp_id_str"]), reverse=True)
        elif sort_mode == "Name (A to Z)":
            processed_employees.sort(key=lambda x: str(x["emp_name"]).lower())
        elif sort_mode == "Name (Z to A)":
            processed_employees.sort(key=lambda x: str(x["emp_name"]).lower(), reverse=True)
        else: 
            processed_employees.sort(key=lambda x: natural_sort_key(x["emp_id_str"]))
            
        # --- SECOND PASS: Force Pinned to Top (Stable Sort) ---
        processed_employees.sort(key=lambda x: x["is_pinned"], reverse=True)

        sno = 1
        row_counter = 0
        
        for emp in processed_employees:
            r = emp["raw_data"]
            emp_id = emp["emp_id"]
            emp_id_str = emp["emp_id_str"]
            
            # --- THE FIX: Visual Indicator ---
            emp_name = f"📌 {emp['emp_name']}" if emp["is_pinned"] else emp["emp_name"]
            emp_role = emp["emp_role"]
            emp_salary = emp["emp_salary"]
            emp_join = emp["emp_join"]
            is_active = emp["is_active"]
            
            if emp["resign_str"] and not emp["rejoin_str"]: status_txt = "✖ Inactive"
            elif emp["rejoin_str"]: status_txt = "✔ Active (Rejoined)"
            else: status_txt = "✔ Active"

            if not self.privacy_mode or emp_id in self.visible_salaries: 
                sal_str = f"{format_currency(emp_salary, self.curr_fmt)}   [ Hide ]"
            else: 
                sal_str = "*** [ Show ]"

            actions_str = "✏️ Edit   ❌ Delete"
            if self.is_bulk_mode: actions_str = ""
            
            formatted_join = smart_date_formatter(emp_join, self.date_fmt_code)

            if self.is_bulk_mode:
                sno_val = f"☑ {sno}" if str(emp_id) in self.selected_items else f"☐ {sno}"
                bg_tag = "selected_row" if str(emp_id) in self.selected_items else ("evenrow" if row_counter % 2 == 0 else "oddrow")
            else:
                sno_val = sno
                bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
                
            fg_tag = "active_txt" if is_active else "inactive_txt"
                
            photo = r[7]
            thumb_img = None
            if photo and os.path.exists(photo) and HAS_PIL:
                try:
                    img = Image.open(photo).convert("RGBA")
                    resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                    img = ImageOps.fit(img, (100, 100), method=resamp)
                    bordered = ImageOps.expand(img, border=1, fill=self.BORDER_COLOR)
                    thumb_img = ImageTk.PhotoImage(bordered)
                    self.photo_cache.append(thumb_img)
                except: pass

            self.tree_roster.insert("", "end", iid=str(emp_id), image=thumb_img if thumb_img else "", values=(sno_val, emp_id_str, emp_name, emp_role, formatted_join, sal_str, status_txt, actions_str, ""), tags=(bg_tag, fg_tag))
            row_counter += 1
            sno += 1
            
        empty_r = ("", "", "", "", "", "", "", "", "")
        for i in range(row_counter, 10):
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            self.tree_roster.insert("", "end", iid=f"empty_r_{i}", values=empty_r, tags=("empty_row", bg_tag))
            row_counter += 1

    def on_roster_double_click(self, event):
        if self.is_bulk_mode: return
        region = self.tree_roster.identify("region", event.x, event.y)
        if region != "cell": return
        
        col = self.tree_roster.identify_column(event.x)
        if col != '#3': return
        
        item = self.tree_roster.identify_row(event.y)
        if not item or str(item).startswith("empty"): return
        
        open_employee_ledger(self.winfo_toplevel(), int(item), self.curr_fmt, self.date_fmt_code, self.load_all_data, tab_instance=self)

    def on_roster_click(self, event):
        region = self.tree_roster.identify("region", event.x, event.y)
        if region != "cell": return
        
        col = self.tree_roster.identify_column(event.x)
        emp_id_str = self.tree_roster.identify_row(event.y)
        if not emp_id_str or str(emp_id_str).startswith("empty"): return
        
        # --- THE FIX: Selection check logic ---
        if self.is_bulk_mode:
            if emp_id_str in self.selected_items:
                self.selected_items.remove(emp_id_str)
            else:
                self.selected_items.add(emp_id_str)
            self.load_roster()
            return
        # --------------------------------------

        emp_id = int(emp_id_str)

        if col == '#6': 
            # --- THE FIX: Allow individual peeking at any time without the global PIN ---
            if not self.privacy_mode: return # If global unmask is active, everything is already shown
            if emp_id in self.visible_salaries: self.visible_salaries.remove(emp_id)
            else: self.visible_salaries.add(emp_id)
            self.load_roster()
            return
            # ----------------------------------------------------------------------------

        if col == '#8': 
            bbox = self.tree_roster.bbox(emp_id_str, '#8')
            if bbox:
                click_x = event.x - bbox[0]
                if click_x < bbox[2] / 2:
                    open_employee_dialog(self.winfo_toplevel(), emp_id=emp_id, date_fmt_code=self.date_fmt_code, refresh_cb=self.load_all_data, undo_cb=self.push_undo)
                else:
                    allowed, err_msg = database.check_employee_permission(action="delete", company_id=getattr(self.app, "active_company_id", 1))
                    if not allowed:
                        messagebox.showerror("Access Denied", err_msg, parent=self)
                        return
                    emp = database.get_employee_dict(emp_id)
                    if emp:
                        emp_name = emp.get('name', 'Unknown')
                        if messagebox.askyesno("Delete Employee", f"Are you sure you want to completely delete {emp_name} and all their records? This cannot be undone."):
                            database.log_audit("Employees", "Deleted Employee", record_ref=emp_name, details="Completely deleted employee and all associated records.", company_id=getattr(self.app, "active_company_id", 1))
                            # --- THE FIX: MVC Compliant Undo Cache Fetch ---
                            emp_row = database.get_employee_full_record(emp_id)
                            pay_rows = database.get_employee_payments(emp_id)
                            
                            database.delete_employee(emp_id)
                            # -----------------------------------------------
                            if emp_row: self.push_undo("DELETE_EMP_FULL", (emp_row, pay_rows))
                            self.load_all_data()

    def on_roster_right_click(self, event):
        row_id = self.tree_roster.identify_row(event.y)
        if row_id and not str(row_id).startswith("empty"):
            self.tree_roster.selection_set(row_id)
            emp_id = int(row_id)
            emp = database.get_employee_dict(emp_id)
            if not emp: return
            
            emp_name = emp.get('name', 'Unknown')
            emp_salary = emp.get('salary', 0)

            menu = tk.Menu(self, tearoff=0, font=("Arial", 11), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, activebackground=self.ACCENT_BLUE, activeforeground=self.TEXT_PRIMARY)
            
            # --- THE FIX: Dynamic Pin/Unpin Logic ---
            is_pinned = int(emp.get('is_pinned', 0)) if emp else 0
            if is_pinned:
                menu.add_command(label="📌 Unpin from Top", command=lambda: [database.toggle_employee_pin_status(emp_id, 0), self.load_all_data()])
            else:
                menu.add_command(label="📌 Pin to Top", command=lambda: [database.toggle_employee_pin_status(emp_id, 1), self.load_all_data()])
            menu.add_separator()
            # ----------------------------------------
            
            menu.add_command(label="📄 Open Full Ledger", command=lambda e_id=emp_id: open_employee_ledger(self.winfo_toplevel(), e_id, self.curr_fmt, self.date_fmt_code, self.load_all_data, tab_instance=self))
            menu.add_separator()
            menu.add_command(label="✏️ Edit Basic Info", command=lambda e_id=emp_id: open_employee_dialog(self.winfo_toplevel(), emp_id=e_id, date_fmt_code=self.date_fmt_code, refresh_cb=self.load_all_data, undo_cb=self.push_undo))
            
            def delete_emp():
                allowed, err_msg = database.check_employee_permission(action="delete", company_id=getattr(self.app, "active_company_id", 1))
                if not allowed:
                    messagebox.showerror("Access Denied", err_msg, parent=self)
                    return
                if messagebox.askyesno("Delete Employee", f"Are you sure you want to completely delete {emp_name} and all their records? This cannot be undone."):
                    database.log_audit("Employees", "Deleted Employee", record_ref=emp_name, details="Completely deleted employee and all associated records.", company_id=getattr(self.app, "active_company_id", 1))
                    # --- THE FIX: MVC Compliant Undo Cache Fetch ---
                    emp_row = database.get_employee_full_record(emp_id)
                    pay_rows = database.get_employee_payments(emp_id)
                    
                    database.delete_employee(emp_id)
                    # -----------------------------------------------
                    if emp_row: self.push_undo("DELETE_EMP_FULL", (emp_row, pay_rows))
                    self.load_all_data()

            menu.add_command(label="❌ Delete Employee", command=delete_emp, foreground=self.ACCENT_RED)
            
            # --- THE FIX: Add to right-click menu! ---
            menu.add_separator()
            menu.add_command(label="🪪 Print Selected IDs", command=self.enable_bulk)
            # -----------------------------------------
            
            menu.tk_popup(event.x_root, event.y_root)