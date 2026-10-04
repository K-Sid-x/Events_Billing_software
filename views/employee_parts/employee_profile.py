import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import tempfile
import webbrowser
import base64
import csv
from datetime import date, datetime
import calendar

try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps
except ImportError:
    pass

current_dir = os.path.dirname(os.path.abspath(__file__))
views_dir = os.path.dirname(current_dir)
parent_dir = os.path.dirname(views_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import database
from views.invoice_parts.helpers import format_currency, enable_copy_paste, fetch_global_settings, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar
from views.employee_parts.employee_dialogs import open_increase_salary_dialog, open_pay_dialog, open_absent_dialog, open_salary_history_dialog, open_leave_allocation_dialog
from views.employee_parts.employee_payment_history import EmployeePaymentHistoryPopup
from views.employee_parts.employee_details import open_status_dialog, view_employee_details

BG_COLOR = "#0f172a"
CARD_BG = "#1e293b"
BORDER_COLOR = "#334155"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_YELLOW = "#f59e0b"
ACCENT_BLUE = "#3b82f6"
HEADER_BG = "#475569"

def bind_table_scroll(tree):
    def _scroll(event):
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    tree.bind("<MouseWheel>", _scroll)

def open_employee_ledger(parent, emp_id, curr_fmt, date_fmt_code, refresh_main_cb, tab_instance=None):
    from views.home_parts.ui_components import get_theme
    t = get_theme()
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    BG_COLOR = t["bg"]
    CARD_BG = t["card"]
    BORDER_COLOR = t["border"]
    TEXT_PRIMARY = t["text"]
    TEXT_SECONDARY = t["sec"]
    ACCENT_GREEN = t["accent_green"]
    ACCENT_RED = t["error"]
    ACCENT_YELLOW = "#f59e0b"
    ACCENT_BLUE = t["accent_blue"]
    HEADER_BG = t["header"]

    pop = tk.Toplevel(parent)
    pop.title("Employee Ledger")
    pop.geometry("1080x800")
    pop.configure(bg=BG_COLOR)
    
    try: pop.state('zoomed')
    except: pop.attributes('-zoomed', True)
    
    style = ttk.Style(pop)
    style.theme_use("default")
    
    pop.option_add("*TCombobox*Listbox.background", CARD_BG)
    pop.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    pop.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)
    pop.option_add("*TCombobox*Listbox.selectForeground", TEXT_PRIMARY)
    
    style.configure("TCombobox", fieldbackground=BG_COLOR, background=CARD_BG, foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR, darkcolor=BORDER_COLOR)
    style.map("TCombobox", fieldbackground=[("readonly", BG_COLOR)], selectbackground=[("readonly", BG_COLOR)], selectforeground=[("readonly", TEXT_PRIMARY)])

    style.configure("Ledger.Vertical.TScrollbar", background=TEXT_SECONDARY, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=TEXT_PRIMARY, relief="flat")
    style.configure("Ledger.Horizontal.TScrollbar", background=TEXT_SECONDARY, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=TEXT_PRIMARY, relief="flat")
    style.map("Ledger.Vertical.TScrollbar", background=[("active", ACCENT_BLUE)])
    style.map("Ledger.Horizontal.TScrollbar", background=[("active", ACCENT_BLUE)])

    main_wrapper = tk.Frame(pop, bg=BG_COLOR)
    main_wrapper.pack(fill="both", expand=True)

    if not hasattr(pop, "local_unmask"): pop.local_unmask = False
    if not hasattr(pop, "month_filter_var"): pop.month_filter_var = tk.StringVar(value=datetime.today().strftime("%B"))
    if not hasattr(pop, "year_filter_var"): pop.year_filter_var = tk.StringVar(value=str(datetime.today().year))
    
    # --- ISOLATED LEDGER UNDO/REDO STACKS ---
    if not hasattr(pop, "undo_stack"): pop.undo_stack = []
    if not hasattr(pop, "redo_stack"): pop.redo_stack = []

    def push_undo(action_type, data):
        pop.undo_stack.append((action_type, data))
        pop.redo_stack.clear()

    def perform_undo():
        if not pop.undo_stack: return
        action, data = pop.undo_stack.pop()
        try:
            if action == "EDIT_EMP":
                old_row, new_row = data
                database.update_employee_record_full(old_row)
                pop.redo_stack.append(("EDIT_EMP", (new_row, old_row)))
            elif action == "ADD_PAY":
                full_row = database.get_employee_payment_record(data)
                if full_row:
                    database.delete_employee_payment_and_rollback(data)
                    pop.redo_stack.append(("ADD_PAY", full_row))
            elif action == "DELETE_PAY":
                database.restore_employee_payment_record(data)
                pop.redo_stack.append(("DELETE_PAY", data))
        except Exception as e:
            messagebox.showerror("Undo Error", str(e), parent=pop)
        refresh_data()

    def perform_redo():
        if not pop.redo_stack: return
        action, data = pop.redo_stack.pop()
        try:
            if action == "EDIT_EMP":
                new_row, old_row = data
                database.update_employee_record_full(new_row)
                pop.undo_stack.append(("EDIT_EMP", (old_row, new_row)))
            elif action == "ADD_PAY":
                database.restore_employee_payment_record(data)
                pop.undo_stack.append(("ADD_PAY", data[0]))
            elif action == "DELETE_PAY":
                database.delete_employee_payment_and_rollback(data[0])
                pop.undo_stack.append(("DELETE_PAY", data))
        except Exception as e:
            messagebox.showerror("Redo Error", str(e), parent=pop)
        refresh_data()

    pop.bind("<Control-z>", lambda e: perform_undo())
    pop.bind("<Control-y>", lambda e: perform_redo())

    def refresh_data():
        if refresh_main_cb: refresh_main_cb()
        build_ui()

    def build_ui():
        # --- THE FIX: Capture BOTH scroll positions before wiping the screen ---
        saved_y = pop.ledger_tree.yview()[0] if hasattr(pop, 'ledger_tree') and pop.ledger_tree.winfo_exists() else None
        saved_x = pop.ledger_tree.xview()[0] if hasattr(pop, 'ledger_tree') and pop.ledger_tree.winfo_exists() else None
        
        for widget in main_wrapper.winfo_children(): widget.destroy()

        # --- THE FIX: Permanently unmask EVERYTHING inside the Ledger! ---
        is_masked = False
        # -----------------------------------------------------------------

        database.sync_employee_status(emp_id)

        emp = database.get_employee_dict(emp_id)
        if not emp: pop.destroy(); return

        emp_name, emp_role, emp_salary, emp_join, emp_photo = emp.get('name'), emp.get('role'), emp.get('salary', 0), emp.get('join_date'), emp.get('photo_path')
        resign_str, rejoin_str = emp.get('resign_date', ""), emp.get('rejoin_date', "")
        sal_hist_str = emp.get('salary_history', "")
        
        formatted_join = smart_date_formatter(emp_join, date_fmt_code) if emp_join else "—"

        # --- THE FIX: MVC Compliant Ledger Fetch ---
        all_pays = database.get_employee_ledger_payments(emp_id)
        # -------------------------------------------

        normalized_pays = []
        for p in all_pays:
            p_id, p_date, p_type, p_amount, p_notes, p_mode, p_attach = p
            d = datetime.min
            for fmt in (date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    d = datetime.strptime(p_date, fmt)
                    break
                except: pass
            normalized_pays.append((d, p))
            
        normalized_pays.sort(key=lambda x: (x[0], x[1][0]))

        status_timeline = []
        for d, p in normalized_pays:
            if p[2] in ("Resigned", "Rejoined"):
                if d != datetime.min: status_timeline.append((d, p[2], p[0]))

        # --- THE FIX: Bulletproof Date Parser (Strips Time to Prevent Midnight Boundary Bugs) ---
        jd = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        if emp_join:
            for fmt in (date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    jd = datetime.strptime(str(emp_join).strip(), fmt).replace(hour=0, minute=0, second=0, microsecond=0)
                    break
                except: pass
        # ----------------------------------------------------------------------------------------
        
        today_dt = datetime.today()
        current = datetime(jd.year, jd.month, 1)
        end = datetime(today_dt.year, today_dt.month, 1)

        hist = []
        if sal_hist_str:
            try: hist = json.loads(sal_hist_str)
            except: pass
        if not hist: hist = [{"date": emp_join, "salary": emp_salary}]

        parsed_hist = []
        for h in hist:
            d = datetime.min
            for fmt in (date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    d = datetime.strptime(str(h["date"]).strip(), fmt)
                    break
                except: pass
            if d != datetime.min:
                parsed_hist.append((d, float(h["salary"])))
        parsed_hist.sort(key=lambda x: x[0])  

        header = tk.Frame(main_wrapper, bg=CARD_BG, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        header.pack(fill="x")
        
        top_right_f = tk.Frame(header, bg=CARD_BG)
        top_right_f.pack(side="right", anchor="ne")

        btn_undo = tk.Button(top_right_f, text="↺ Undo", font=("Arial", 11, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY, relief="solid", highlightbackground=BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=perform_undo)
        btn_undo.pack(side="left", padx=(0, 5))
        
        btn_redo = tk.Button(top_right_f, text="↻ Redo", font=("Arial", 11, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY, relief="solid", highlightbackground=BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=perform_redo)
        btn_redo.pack(side="left", padx=(0, 15))
        
        if pop.undo_stack: btn_undo.config(fg=ACCENT_GREEN, state="normal")
        else: btn_undo.config(fg=TEXT_SECONDARY, state="disabled")
        if pop.redo_stack: btn_redo.config(fg=ACCENT_BLUE, state="normal")
        else: btn_redo.config(fg=TEXT_SECONDARY, state="disabled")

        undo_callback = push_undo

        opts_btn = tk.Button(top_right_f, text="⚙️ Options ▼", font=("Arial", 10, "bold"), fg=TEXT_PRIMARY, bg=BG_COLOR, relief="flat", bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, cursor="hand2", padx=10, pady=3)
        opts_btn.pack(side="left")
        opts_menu = tk.Menu(opts_btn, tearoff=0, font=("Arial", 10), bg=CARD_BG, fg=TEXT_PRIMARY, activebackground=ACCENT_BLUE, activeforeground=TEXT_PRIMARY)
        
        opts_menu.add_command(label="📈 Increase Salary", command=lambda: open_increase_salary_dialog(pop, emp_id, emp_name, emp_salary, curr_fmt, date_fmt_code, refresh_data, undo_callback, anchor_widget=opts_btn))
        opts_menu.add_command(label="📜 Salary History", command=lambda: open_salary_history_dialog(pop, emp_id, emp_name, curr_fmt, date_fmt_code, anchor_widget=opts_btn))
        opts_menu.add_separator()
        
        # --- THE FIX: Hook up the Leave Allocation Dialog ---
        try: cur_yr = int(pop.year_filter_var.get())
        except: cur_yr = datetime.today().year
        opts_menu.add_command(label="📅 Set Yearly Paid Leaves", command=lambda: open_leave_allocation_dialog(pop, emp_id, emp_name, cur_yr, refresh_data, anchor_widget=opts_btn))
        # ----------------------------------------------------
        
        opts_btn.bind("<Button-1>", lambda e: opts_menu.tk_popup(opts_btn.winfo_rootx(), opts_btn.winfo_rooty() + opts_btn.winfo_height()))

        photo_f = tk.Frame(header, bg=CARD_BG)
        photo_f.pack(side="left", padx=(0, 20))
        
        photo_lbl = tk.Label(photo_f, bg=CARD_BG, highlightthickness=0, bd=0)
        photo_lbl.pack()
        if emp_photo and os.path.exists(emp_photo):
            try:
                img = Image.open(emp_photo).convert("RGBA")
                img = ImageOps.fit(img, (80, 80), method=Image.Resampling.LANCZOS)
                mask = Image.new('L', (240, 240), 0); draw = ImageDraw.Draw(mask); draw.ellipse((0, 0, 240, 240), fill=255)
                mask = mask.resize((80, 80), Image.Resampling.LANCZOS)
                img_circle = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
                img_circle.paste(img, (0, 0), mask=mask)
                photo_img = ImageTk.PhotoImage(img_circle)
                photo_lbl.config(image=photo_img, bd=0, highlightthickness=0)
                photo_lbl.image = photo_img
            except:
                photo_lbl.config(text="👤", font=("Arial", 36), fg=TEXT_SECONDARY, width=3, height=1)
        else:
            photo_lbl.config(text="👤", font=("Arial", 36), fg=TEXT_SECONDARY, width=3, height=1)

        details_f = tk.Frame(header, bg=CARD_BG)
        details_f.pack(side="left", fill="both", expand=True)
        tk.Label(details_f, text=emp_name, font=("Arial", 22, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
        
        if resign_str and not rejoin_str: 
            tk.Label(details_f, text=f"✖ Inactive (Resigned on {resign_str})", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY, padx=8, pady=2).pack(anchor="w", pady=(0,4))
        elif rejoin_str: 
            tk.Label(details_f, text=f"✔ Active (Rejoined)", font=("Arial", 9, "bold"), bg="#064e3b" if is_dark else "#dcfce3", fg="#6ee7b7" if is_dark else "#166534", padx=8, pady=2).pack(anchor="w", pady=(0,4))
        else: 
            tk.Label(details_f, text="✔ Active", font=("Arial", 9, "bold"), bg="#064e3b" if is_dark else "#dcfce3", fg="#6ee7b7" if is_dark else "#166534", padx=8, pady=2).pack(anchor="w", pady=(0,4))

        tk.Label(details_f, text=f"Role: {emp_role}  |  Join Date: {formatted_join}", font=("Arial", 11), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w", pady=(2, 4))
        
        fin_f = tk.Frame(details_f, bg=CARD_BG)
        fin_f.pack(anchor="w", pady=(5, 0))

        fin_labels_f = tk.Frame(fin_f, bg=CARD_BG)
        fin_labels_f.pack(side="left")

        lbl_adv_out = tk.Label(fin_labels_f, text="Advance (Out): ₹0.00", font=("Arial", 12, "bold"), bg=CARD_BG, fg=ACCENT_RED)
        lbl_adv_out.pack(anchor="w")
        lbl_payable = tk.Label(fin_labels_f, text="Payable Balance: ₹0.00", font=("Arial", 16, "bold"), bg=CARD_BG, fg=ACCENT_GREEN)
        lbl_payable.pack(anchor="w", pady=(2, 0))
        lbl_paid = tk.Label(fin_labels_f, text="Total Paid: ₹0.00", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY)
        lbl_paid.pack(anchor="w", pady=(2, 4))
        
        # --- THE FIX: Add the UI Tracker Tile ---
        lbl_leaves = tk.Label(fin_labels_f, text="Paid Leaves: --", font=("Arial", 9, "bold"), bg=CARD_BG, fg=ACCENT_BLUE)
        lbl_leaves.pack(anchor="w", pady=(0, 4))
        # ----------------------------------------

        tk.Button(details_f, text="📄 View Full Details", font=("Arial", 9, "underline"), fg=ACCENT_BLUE, bg=CARD_BG, cursor="hand2", relief="flat", command=lambda: view_employee_details(pop, emp_id, curr_fmt)).pack(anchor="w", pady=(5,0))

        actions_f = tk.Frame(main_wrapper, bg=BG_COLOR)
        actions_f.pack(fill="x", padx=25, pady=(20, 5))
        
        tk.Button(actions_f, text="💰 Pay / Advance / Bonus", font=("Arial", 10, "bold"), bg=ACCENT_BLUE, fg="white", relief="flat", cursor="hand2", padx=20, pady=8, command=lambda: open_pay_dialog(pop, emp_id, emp_name, emp_salary, curr_fmt, date_fmt_code, refresh_data, undo_callback, getattr(pop, 'current_payable', 0.0), getattr(pop, 'last_past_dues', 0.0), getattr(pop, 'last_current_due', float(emp_salary)))).pack(side="left", padx=(0,10))
        tk.Button(actions_f, text="📅 Mark Leave", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1, cursor="hand2", padx=15, pady=8, command=lambda: open_absent_dialog(pop, emp_id, emp_name, date_fmt_code, refresh_data, undo_callback)).pack(side="left", padx=(0,10))
        
        if resign_str and not rejoin_str: 
            tk.Button(actions_f, text="✔ Mark Rejoined", font=("Arial", 10, "bold"), bg=ACCENT_GREEN, fg="white", relief="flat", cursor="hand2", padx=15, pady=8, command=lambda: open_status_dialog(pop, emp_id, emp_name, "Rejoined", date_fmt_code, refresh_data, undo_callback)).pack(side="left", padx=(0,10))
        else: 
            tk.Button(actions_f, text="✖ Mark Resigned", font=("Arial", 10, "bold"), bg=ACCENT_RED, fg="white", relief="flat", cursor="hand2", padx=15, pady=8, command=lambda: open_status_dialog(pop, emp_id, emp_name, "Resigned", date_fmt_code, refresh_data, undo_callback)).pack(side="left", padx=(0,10))

        btn_print = tk.Button(actions_f, text="🖨️ Print Ledger", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", padx=15, pady=7)
        btn_print.pack(side="right", padx=(0,0))

        def export_ledger_csv():
            # --- THE FIX: Prevent exporting '***' if Privacy Mode is on ---
            if is_masked:
                messagebox.showwarning("Privacy Mode Active", "Please click 'Show Financials' to unmask the data before exporting.", parent=pop)
                return
            # --------------------------------------------------------------
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv", 
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], 
                title=f"Save Ledger - {emp_name}"
            )
            if not file_path: return
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow(["Salary Slab", "Bonus", "Advance", "Action"]) 
                    for item in tree.get_children():
                        tags = tree.item(item, "tags")
                        vals = tree.item(item, "values")
                        v = list(vals)[:3] 
                        while len(v) < 3: v.append("") 
                        if "month_header" in tags or "info_row" in tags or "deduction_row" in tags or "net_row" in tags:
                            writer.writerow([v[0], "", ""]) 
                        elif "divider" in tags:
                            pass 
                        elif "summary_row" in tags:
                            writer.writerow([v[0], v[1], v[2]])
                        else:
                            writer.writerow([v[0], v[1], v[2]])
                messagebox.showinfo("Export Successful", f"Ledger exported to:\n{file_path}", parent=pop)
            except Exception as e:
                messagebox.showerror("Export Failed", str(e), parent=pop)

        btn_export = tk.Button(actions_f, text="📥 Export CSV", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", padx=15, pady=7, command=export_ledger_csv)
        btn_export.pack(side="right", padx=(0, 10))

        btn_hist = tk.Button(actions_f, text="📜 Payment History", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", padx=15, pady=7, command=lambda: EmployeePaymentHistoryPopup(pop, emp_id, emp_name, curr_fmt, date_fmt_code))
        btn_hist.pack(side="right", padx=(0, 10))

        filter_wrapper = tk.Frame(main_wrapper, bg=BG_COLOR)
        filter_wrapper.pack(fill="x", padx=25, pady=(0, 15))

        tk.Label(filter_wrapper, text="Filter Ledger:", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(side="left", padx=(0, 5))

        available_years = sorted(list(set([str(y) for y in range(jd.year, today_dt.year + 1)])))
        if "All Years" not in available_years: available_years.insert(0, "All Years")
        if pop.year_filter_var.get() not in available_years: pop.year_filter_var.set(str(today_dt.year))

        year_cb = ttk.Combobox(filter_wrapper, textvariable=pop.year_filter_var, state="readonly", width=10, font=("Arial", 10))
        year_cb['values'] = available_years
        year_cb.pack(side="left", padx=(0, 5))
        year_cb.bind("<<ComboboxSelected>>", lambda e: build_ui())

        month_options = ["All Months", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        if pop.month_filter_var.get() not in month_options: pop.month_filter_var.set("All Months")

        month_cb = ttk.Combobox(filter_wrapper, textvariable=pop.month_filter_var, state="readonly", width=14, font=("Arial", 10))
        month_cb['values'] = month_options
        month_cb.pack(side="left", padx=(0, 15))
        month_cb.bind("<<ComboboxSelected>>", lambda e: build_ui())

        table_f = tk.Frame(main_wrapper, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=25, pady=(0, 25))
        
        tk.Label(table_f, text="MONTHLY SALARY SLAB, BONUS & ADVANCE RECORD", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w", padx=15, pady=10)
        
        tree_container = tk.Frame(table_f, bg=CARD_BG)
        tree_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # --- THE FIX: Added ghost column to absorb stretching ---
        cols = ("salary", "bonus", "advance", "action", "ghost")
        
        style.configure("Ledger.Treeview.Heading", font=("Arial", 11, "bold"), background=HEADER_BG, foreground=TEXT_PRIMARY, relief="raised", borderwidth=3)
        style.map("Ledger.Treeview.Heading", background=[('active', '#64748b')])
        
        style.configure("Ledger.Treeview", font=("Arial", 10), rowheight=35, background=BG_COLOR, fieldbackground=BG_COLOR, foreground=TEXT_PRIMARY, borderwidth=0)
        style.map("Ledger.Treeview", background=[("selected", BORDER_COLOR)], foreground=[("selected", "#ffffff")])
        
        tree_scroll_y = ttk.Scrollbar(tree_container, orient="vertical", style="Ledger.Vertical.TScrollbar")
        tree_scroll_y.pack(side="right", fill="y")
        
        tree_scroll_x = ttk.Scrollbar(tree_container, orient="horizontal", style="Ledger.Horizontal.TScrollbar")
        tree_scroll_x.pack(side="bottom", fill="x")
        
        tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=12, style="Ledger.Treeview", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        tree.pack(side="left", fill="both", expand=True)
        
        tree_scroll_y.config(command=tree.yview)
        tree_scroll_x.config(command=tree.xview)
        
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                tree.yview_moveto(tree.yview()[0] + (delta * 0.008))
            else:
                tree.xview_moveto(tree.xview()[0] + (delta * 0.02))
                
        tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        tree.heading("salary", text="SALARY SLAB", anchor="center")
        tree.heading("bonus", text="BONUS", anchor="center")
        tree.heading("advance", text="ADVANCE", anchor="center")
        tree.heading("action", text="ACTION", anchor="center")
        tree.heading("ghost", text="")

        comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
        try:
            l_w = json.loads(database.get_ui_setting(f"emp_ledger_widths_{comp_id}", "{}"))
        except:
            l_w = {}

        # --- THE FIX: Action column locked, Ghost column absorbs all stretching ---
        tree.column("salary", width=l_w.get("salary", 400), minwidth=150, stretch=False, anchor="w")
        tree.column("bonus", width=l_w.get("bonus", 200), minwidth=80, stretch=False, anchor="center")
        tree.column("advance", width=l_w.get("advance", 250), minwidth=80, stretch=False, anchor="center")
        tree.column("action", width=l_w.get("action", 120), minwidth=80, stretch=False, anchor="center") 
        tree.column("ghost", width=10, minwidth=10, stretch=True)
        # ------------------------------------------------------------------------

        def save_l_widths():
            new_w = {c: tree.column(c, "width") for c in ("salary", "bonus", "advance", "action")}
            try:
                current_comp = getattr(parent.winfo_toplevel(), "active_company_id", 1)
                database.save_ui_setting(f"emp_ledger_widths_{current_comp}", json.dumps(new_w))
            except: pass

        def on_l_sep_drag(event):
            if tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_l_widths)
                
        tree.bind("<B1-Motion>", on_l_sep_drag, add="+")
        tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_l_widths) if tree.identify_region(e.x, e.y) == "separator" else None, add="+")

        pop.ledger_tree = tree

        tree.tag_configure('month_header', background=CARD_BG, foreground=TEXT_PRIMARY, font=("Arial", 11, "bold", "underline"))
        tree.tag_configure('summary_row', background=CARD_BG, foreground=TEXT_PRIMARY, font=("Arial", 10, "bold"))
        tree.tag_configure('divider', background=BG_COLOR)
        
        tree.tag_configure('info_row', foreground=TEXT_SECONDARY, font=("Arial", 10))
        tree.tag_configure('deduction_row', foreground=ACCENT_RED, font=("Arial", 10))
        tree.tag_configure('net_row', foreground=ACCENT_GREEN, font=("Arial", 10, "bold"))
        tree.tag_configure('data_row', foreground=TEXT_PRIMARY) 
        tree.tag_configure('absent_row', foreground=ACCENT_RED, font=("Arial", 10)) 
        tree.tag_configure('resign_row', foreground=ACCENT_RED, font=("Arial", 10)) 
        tree.tag_configure('rejoin_row', foreground=ACCENT_GREEN, font=("Arial", 10)) 
        tree.tag_configure('delete_btn', foreground=ACCENT_RED, font=("Arial", 9, "bold"))

        tree.tag_configure("evenrow", background=BG_COLOR)
        tree.tag_configure("oddrow", background=CARD_BG)
        tree.tag_configure("empty", foreground=TEXT_PRIMARY)

        all_month_keys = set()
        for d, p in normalized_pays:
            if d != datetime.min: all_month_keys.add(d.strftime("%Y-%m"))

        curr_y, curr_m = jd.year, jd.month
        end_y, end_m = today_dt.year, today_dt.month
        
        filter_y_str = pop.year_filter_var.get()
        filter_m_str = pop.month_filter_var.get()
        if filter_y_str != "All Years" and filter_m_str != "All Months":
            try:
                f_y = int(filter_y_str)
                f_m = datetime.strptime(filter_m_str, "%B").month
                if f_y > end_y or (f_y == end_y and f_m > end_m):
                    end_y, end_m = f_y, f_m
            except: pass
        
        while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
            all_month_keys.add(f"{curr_y}-{curr_m:02d}")
            curr_m += 1
            if curr_m > 12:
                curr_m = 1
                curr_y += 1

        all_month_keys = sorted(list(all_month_keys))
        monthly_groups = {k: [] for k in all_month_keys}
        for d, p in normalized_pays:
            if d != datetime.min:
                monthly_groups[d.strftime("%Y-%m")].append(p)

        # --- THE FIX: Restoring the missing base variables! ---
        running_advance = 0.0
        running_payable = 0.0
        filtered_paid_total = 0.0
        # ------------------------------------------------------

        snapshot_advance = 0.0
        snapshot_payable = 0.0
        has_snapshot = False
        
        pending_dues = []
        all_prev_due_iids = []
        forward_credit = 0.0

        idx = 0
        surplus_extensions = 0
        
        while idx < len(all_month_keys):
            m_key = all_month_keys[idx]
            m_pays = monthly_groups.get(m_key, [])
            
            items_before_month = set(tree.get_children())
            
            month_name_full = datetime.strptime(m_key, "%Y-%m").strftime("%B %Y")
            m_year_str = m_key.split('-')[0]
            m_month_str = datetime.strptime(m_key, "%Y-%m").strftime("%B")
            
            show_this_month = True
            if pop.year_filter_var.get() != "All Years" and pop.year_filter_var.get() != m_year_str:
                show_this_month = False
            if pop.month_filter_var.get() != "All Months" and pop.month_filter_var.get() != m_month_str:
                show_this_month = False

            active_month_salary = emp_salary 
            for hist_date, hist_sal in parsed_hist:
                if hist_date.strftime("%Y-%m") <= m_key:
                    active_month_salary = hist_sal
            
            m_year_int = int(m_year_str)
            m_month_int = datetime.strptime(m_month_str, "%B").month
            days_in_month = calendar.monthrange(m_year_int, m_month_int)[1]
            daily_wage = active_month_salary / days_in_month if days_in_month else 0
            
            # --- THE FIX: Fast-path calendar math replaces the heavy 31-day lag loop! ---
            status_changes_this_month = [s for s in status_timeline if s[0].year == m_year_int and s[0].month == m_month_int]
            
            if not status_changes_this_month:
                is_active = True
                month_end = datetime(m_year_int, m_month_int, days_in_month)
                if month_end < jd:
                    is_active = False
                else:
                    current_status = "Rejoined"
                    for s_dt, s_type, s_id in status_timeline:
                        if s_dt <= month_end: current_status = s_type
                    if current_status == "Resigned": is_active = False
                
                if not is_active:
                    active_days_count = 0
                elif jd.year == m_year_int and jd.month == m_month_int:
                    active_days_count = days_in_month - jd.day + 1
                else:
                    active_days_count = days_in_month
            else:
                active_days_count = 0
                for day in range(1, days_in_month + 1):
                    current_day_dt = datetime(m_year_int, m_month_int, day)
                    is_active = True
                    if current_day_dt < jd: is_active = False
                    else:
                        current_status = "Rejoined" 
                        for s_dt, s_type, s_id in status_timeline:
                            if s_dt <= current_day_dt: current_status = s_type
                        if current_status == "Resigned": is_active = False
                    if is_active: active_days_count += 1
            # ----------------------------------------------------------------------------

            if active_days_count == days_in_month:
                prorated_base_salary = active_month_salary
            else:
                prorated_base_salary = int((daily_wage * active_days_count) + 0.5)

            unpaid_leaves_count = sum(1 for p in m_pays if p[2] == "Unpaid Leave")
            month_unpaid_deduction = int((daily_wage * unpaid_leaves_count) + 0.5)
            
            adjusted_salary = prorated_base_salary - month_unpaid_deduction
            if adjusted_salary < 0: adjusted_salary = 0.0
            
            applied_rollover = 0.0
            if forward_credit > 0.01:
                applied_rollover = min(forward_credit, adjusted_salary)
                forward_credit -= applied_rollover
                
            current_base_due = max(0.0, adjusted_salary - applied_rollover)
            running_payable += adjusted_salary 

            prev_due_iids = []
            net_row_iid = None
            if show_this_month:
                pop.viewed_past_dues_refs = list(pending_dues) 
                tree.insert("", "end", values=(f"Month of {month_name_full}", "", "", ""), tags=("month_header",))
                
                for due in pending_dues:
                    if due["amount"] > 0.01:
                        due_iid = tree.insert("", "end", values=(f"   ↳ Previous Due ({due['month_name']}): {format_currency(due['amount'], curr_fmt)}", "", "", ""), tags=("info_row",))
                        prev_due_iids.append((due_iid, due, due["amount"], due['month_name']))
                        all_prev_due_iids.append((due_iid, due, due["amount"], due['month_name']))
                        
                if applied_rollover > 0.01:
                    tree.insert("", "end", values=(f"   ↳ Surplus Rollover Applied: −{format_currency(applied_rollover, curr_fmt)}", "", "", ""), tags=("net_row",))
                
                changes_this_month = [h for h in parsed_hist if h[0].strftime("%Y-%m") == m_key]
                base_sal_str = format_currency(prorated_base_salary, curr_fmt)
                
                if active_days_count == 0:
                    base_label = f"   ↳ Base (Inactive Month): {format_currency(0, curr_fmt)}"
                elif active_days_count < days_in_month:
                    base_label = f"   ↳ Base (Prorated for {active_days_count} days): {base_sal_str} (Adjusted)"
                else:
                    base_label = f"   ↳ Base: {base_sal_str}"
                
                if changes_this_month:
                    latest_change = changes_this_month[-1]
                    date_str = latest_change[0].strftime(date_fmt_code)
                    tree.insert("", "end", values=(f"{base_label}  (Eff: {date_str})", "", "", ""), tags=("info_row",))
                else:
                    tree.insert("", "end", values=(base_label, "", "", ""), tags=("info_row",))
                
                if month_unpaid_deduction > 0:
                    tree.insert("", "end", values=(f"   ↳ Unpaid Leaves ({unpaid_leaves_count}): −{format_currency(month_unpaid_deduction, curr_fmt)}", "", "", ""), tags=("deduction_row",))
                
                net_row_iid = tree.insert("", "end", values=(f"   ↳ Net Earned: {format_currency(adjusted_salary, curr_fmt)}", "", "", ""), tags=("net_row",))

                bf_str = f"B/F Advance: {format_currency(running_advance, curr_fmt)}"
                tree.insert("", "end", values=("", "", bf_str, ""), tags=("data_row",))

            month_sal_taken = 0.0
            month_adv_taken = 0.0
            month_bonus_taken = 0.0
            
            for p in m_pays:
                p_id, p_date, p_type, p_amount, p_notes, p_mode, p_attach = p
                amt_val = p_amount if p_type not in ("Absent", "Paid Leave", "Unpaid Leave", "Resigned", "Rejoined", "Status") else 0
                
                # --- THE FIX: Run the raw database date through the global formatter first! ---
                p_date = smart_date_formatter(p_date, date_fmt_code)
                # ----------------------------------------------------------------------------
                
                s_str = b_str = a_str = ""
                clean_notes = str(p_notes).replace('[Target: Dues]', '').replace('[Target: Current]', '').replace('[Target: All]', '').strip()
                note_str = f"   [Note: {clean_notes}]" if clean_notes else ""
                mode_str = f" ({p_mode})" if p_mode else ""
                row_tag = "data_row"
                
                note_lower = str(p_notes).lower()
                is_target_current = "[target: current]" in note_lower
                is_target_dues = "[target: dues]" in note_lower
                
                if p_type == "Salary":
                    month_sal_taken += amt_val
                    running_payable -= amt_val
                    
                    pay_left = amt_val
                    covered_details = []
                    
                    if is_target_current:
                        if pay_left > 0.01 and current_base_due > 0.01:
                            deduct = min(pay_left, current_base_due)
                            current_base_due -= deduct
                            pay_left -= deduct
                        if pay_left > 0.01:
                            forward_credit += pay_left
                            covered_details.append(f"Rolled Forward: {format_currency(pay_left, curr_fmt)}")
                            pay_left = 0.0
                    else: 
                        for due in pending_dues:
                            if pay_left <= 0.01: break
                            if due["amount"] > 0.01:
                                deduct = min(pay_left, due["amount"])
                                due["amount"] -= deduct
                                pay_left -= deduct
                                m_short = due['month_name'].split(' ')[0]
                                covered_details.append(f"{m_short}: {format_currency(deduct, curr_fmt)}")
                                
                                if due.get("iid") and tree.exists(due["iid"]):
                                    new_stat = "   [ Paid in Full ]" if due["amount"] <= 0.01 else f"   [ Remaining: {format_currency(due['amount'], curr_fmt)} ]"
                                    tree.item(due["iid"], values=(f"   ↳ Net Earned: {format_currency(due.get('original_salary', 0), curr_fmt)}{new_stat}", "", "", ""))
                                    
                                    if due.get("summary_iid") and tree.exists(due["summary_iid"]):
                                        insert_idx = tree.index(due["summary_iid"]) # <--- FIXED VARIABLE NAME
                                        late_iid = tree.insert("", insert_idx, values=(f"   ↳ Late Payment: {format_currency(deduct, curr_fmt)} on 📅 {p_date}", "", "", ""), tags=("info_row",))
                                        items_before_month.add(late_iid)

                        if not is_target_dues: 
                            if pay_left > 0.01 and current_base_due > 0.01:
                                deduct = min(pay_left, current_base_due)
                                current_base_due -= deduct
                                pay_left -= deduct
                                
                        if pay_left > 0.01:
                            forward_credit += pay_left
                            covered_details.append(f"Rolled Forward: {format_currency(pay_left, curr_fmt)}")
                            pay_left = 0.0
                                
                    # --- THE FIX: Hide Mode and Notes for Salary ---
                    s_str = f"📅 {p_date}  —  {format_currency(amt_val, curr_fmt) if not is_masked else '***'}"
                    if covered_details:
                        s_str += f"  [Cleared — {', '.join(covered_details)}]"
                        
                    if p_mode and "Wallet Deduction" in str(p_mode):
                        running_advance -= amt_val
                        
                elif p_type == "Bonus":
                    # --- THE FIX: Hide Mode and Notes for Bonus ---
                    b_str = f"📅 {p_date}  —  {format_currency(amt_val, curr_fmt) if not is_masked else '***'}"
                    month_bonus_taken += amt_val
                    # ----------------------------------------------
                elif p_type == "Advance":
                    if amt_val < 0:
                        a_str = f"📅 {p_date}  —  {format_currency(amt_val, curr_fmt) if not is_masked else '***'} (Refunded){note_str}"
                    else:
                        a_str = f"📅 {p_date}  —  {format_currency(amt_val, curr_fmt) if not is_masked else '***'}{mode_str}{note_str}"
                    month_adv_taken += amt_val
                    running_advance += amt_val
                elif p_type == "Unpaid Leave":
                    s_str = f"📅 {p_date}  —  Unpaid Leave ( − {format_currency(int(daily_wage + 0.5), curr_fmt)} ){note_str}"
                    row_tag = "absent_row"
                elif p_type == "Absent":
                    s_str = f"📅 {p_date}  —  Absent{note_str}"
                    row_tag = "absent_row"
                elif p_type == "Paid Leave":
                    s_str = f"📅 {p_date}  —  {p_type}{note_str}"
                elif p_type == "Resigned":
                    s_str = f"📅 {p_date}  —  {p_type}{note_str}"
                    row_tag = "resign_row"
                elif p_type == "Rejoined":
                    s_str = f"📅 {p_date}  —  {p_type}{note_str}"
                    row_tag = "rejoin_row"
                    
                if show_this_month:
                    tree.insert("", "end", iid=f"pay_{p_id}", values=(s_str, b_str, a_str, "❌ Delete"), tags=(row_tag, "delete_btn"))
                
            if current_base_due > 0.01:
                new_due_obj = {
                    "month_name": month_name_full, 
                    "amount": current_base_due,
                    "iid": net_row_iid if show_this_month else None,
                    "original_salary": adjusted_salary
                }
                pending_dues.append(new_due_obj)
                if show_this_month:
                    pop.viewed_current_due_ref = new_due_obj
            else:
                if show_this_month:
                    pop.viewed_current_due_ref = None
            
            if show_this_month:
                filtered_paid_total += month_sal_taken + month_adv_taken + month_bonus_taken
                cf_str = f"C/F Next Month: {format_currency(running_advance, curr_fmt)}"

                snapshot_advance = running_advance
                snapshot_payable = running_payable
                has_snapshot = True
                
                status_txt = "   [ Paid in Full ]" if current_base_due <= 0.01 else f"   [ Remaining: {format_currency(current_base_due, curr_fmt)} ]"
                tree.item(net_row_iid, values=(f"   ↳ Net Earned: {format_currency(adjusted_salary, curr_fmt)}{status_txt}", "", "", ""))

                summary_iid = tree.insert("", "end", values=(
                    f"Total Sal Taken: {format_currency(month_sal_taken, curr_fmt) if not is_masked else '***'}", 
                    f"Total Bonus: {format_currency(month_bonus_taken, curr_fmt) if not is_masked else '***'}", 
                    cf_str, 
                    ""
                ), tags=("summary_row",))
                
                if pending_dues and pending_dues[-1]["month_name"] == month_name_full:
                    pending_dues[-1]["summary_iid"] = summary_iid

                tree.insert("", "end", values=("", "", "", ""), tags=("divider",))

            if forward_credit > 0.01 and idx == len(all_month_keys) - 1 and surplus_extensions < 24:
                next_y, next_m = map(int, m_key.split('-'))
                next_m += 1
                if next_m > 12:
                    next_m = 1
                    next_y += 1
                next_key = f"{next_y}-{next_m:02d}"
                all_month_keys.append(next_key)
                surplus_extensions += 1
            
            new_items = [item for item in tree.get_children() if item not in items_before_month]
            for i, item in enumerate(new_items):
                tree.move(item, "", i)
                
            idx += 1

        for due_iid, due_obj, original_amt, m_name in all_prev_due_iids:
            if tree.exists(due_iid):
                if due_obj["amount"] <= 0.01:
                    tree.item(due_iid, values=(f"   ↳ Previous Due ({m_name}): {format_currency(original_amt, curr_fmt)}   [Paid in Full]", "", "", ""))
                elif due_obj["amount"] < original_amt:
                    tree.item(due_iid, values=(f"   ↳ Previous Due ({m_name}): {format_currency(original_amt, curr_fmt)}   [Remaining: {format_currency(due_obj['amount'], curr_fmt)}]", "", "", ""))
                else:
                    tree.item(due_iid, values=(f"   ↳ Previous Due ({m_name}): {format_currency(original_amt, curr_fmt)}   [Unpaid]", "", "", ""))

        if hasattr(pop, "viewed_past_dues_refs"):
            pop.last_past_dues = sum(d["amount"] for d in pop.viewed_past_dues_refs)
        else:
            pop.last_past_dues = 0.0
            
        if hasattr(pop, "viewed_current_due_ref") and pop.viewed_current_due_ref:
            pop.last_current_due = pop.viewed_current_due_ref["amount"]
        else:
            pop.last_current_due = 0.0

        # --- THE FIX: Clean Zebra Striping ---
        row_counter = 0
        for child in tree.get_children():
            tags = list(tree.item(child, "tags"))
            if "month_header" in tags or "summary_row" in tags or "divider" in tags:
                continue 
            
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            
            if bg_tag not in tags:
                tags = [t for t in tags if t not in ("evenrow", "oddrow")]
                tags.append(bg_tag)
                tree.item(child, tags=tags)
                
            row_counter += 1
            
        while row_counter < 12:
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            tree.insert("", "end", iid=f"empty_pad_{row_counter}", values=("", "", "", ""), tags=(bg_tag, "empty"))
            row_counter += 1
        # -------------------------------------

        if not is_masked:
            if pop.year_filter_var.get() == "All Years" and pop.month_filter_var.get() == "All Months":
                disp_adv = running_advance
                disp_pay = running_payable
            else:
                disp_adv = snapshot_advance if has_snapshot else 0.0
                disp_pay = getattr(pop, 'last_past_dues', 0.0) + getattr(pop, 'last_current_due', 0.0)

            pop.current_payable = max(0, disp_pay)

            lbl_adv_out.config(text=f"Advance (Out): {format_currency(disp_adv, curr_fmt)}")
            lbl_payable.config(text=f"Payable Balance: {format_currency(max(0, disp_pay), curr_fmt)}")
            lbl_paid.config(text=f"Total Paid: {format_currency(filtered_paid_total, curr_fmt)}")
        else:
            lbl_adv_out.config(text="Advance (Out): ***")
            lbl_payable.config(text="Payable Balance: ***")
            lbl_paid.config(text="Total Paid: ***")
            
        # --- THE FIX: Calculate and Display the Leave Tracker Math ---
        try: target_year = int(pop.year_filter_var.get())
        except: target_year = datetime.today().year
        
        alloc_dict = {}
        try: alloc_dict = json.loads(emp.get('docs_json', '{}')).get("leave_allocations", {})
        except: pass
        base_allocated = float(alloc_dict.get(str(target_year), 0.0))
        
        # --- PRO-RATA LEAVE CALCULATION ---
        if jd.year == target_year:
            # If they joined this exact year, calculate active months (e.g., Aug to Dec = 5 months)
            months_active = 12 - jd.month + 1
            allocated_leaves = (base_allocated / 12) * months_active
        elif jd.year > target_year:
            # If they hadn't even joined yet in the target year
            allocated_leaves = 0.0
        else:
            # If they joined in a previous year, they get the full baseline
            allocated_leaves = base_allocated
        # ----------------------------------
        
        used_leaves = sum(1 for d, p in normalized_pays if p[2] == 'Paid Leave' and d != datetime.min and d.year == target_year)
        rem_leaves = allocated_leaves - used_leaves
        
        # Ensure it formats cleanly without crazy decimals (e.g. 15 instead of 15.0)
        if allocated_leaves.is_integer(): allocated_leaves = int(allocated_leaves)
        if rem_leaves.is_integer(): rem_leaves = int(rem_leaves)
        
        lbl_leaves.config(text=f"Paid Leaves ({target_year}): {allocated_leaves} Allotted  |  {used_leaves} Used  |  Remaining: {rem_leaves}")
        if rem_leaves < 0: lbl_leaves.config(fg=ACCENT_RED)
        else: lbl_leaves.config(fg=ACCENT_BLUE)
        # -------------------------------------------------------------

        def print_ledger():
            # --- THE FIX: Prevent printing '***' if Privacy Mode is on ---
            if is_masked:
                messagebox.showwarning("Privacy Mode Active", "Please click 'Show Financials' to unmask the data before printing.", parent=pop)
                return
            # -------------------------------------------------------------
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>Employee Ledger - {emp_name}</title>
                <style>
                    @media print {{
                        @page {{ margin: 0; size: auto; }}
                        body {{ margin: 1.5cm; }}
                    }}
                    body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                    h2 {{ color: #1e293b; margin-bottom: 5px; }}
                    .emp-details {{ font-size: 14px; color: #475569; margin-bottom: 25px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                    th, td {{ padding: 8px 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; border-left: none; border-right: none; }}
                    th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                    .month-header td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; color: #1e293b; border-bottom: 1px solid #cbd5e1; text-decoration: underline; }}
                    .info-row td {{ background-color: #f8fafc; color: #475569; padding-top: 6px; padding-bottom: 6px; border: none; }}
                    .deduction-row td {{ background-color: #f8fafc; color: #dc2626; padding-top: 4px; padding-bottom: 4px; border: none; }}
                    .net-row td {{ background-color: #f8fafc; color: #059669; font-weight: bold; padding-top: 4px; padding-bottom: 10px; border-bottom: 1px solid #e2e8f0; }}
                    .summary-row td {{ background-color: #fffbeb; font-weight: bold; color: #0f172a; border-top: 1px solid #cbd5e1; border-bottom: 2px solid #0f172a; }}
                    .divider td {{ height: 10px; border: none; }}
                    .data-row td {{ color: #000000; }}
                </style>
            </head>
            <body>
                <h2>Employee Ledger: {emp_name}</h2>
                <div class="emp-details">Role: {emp_role} &nbsp;|&nbsp; Joined: {formatted_join} &nbsp;|&nbsp; Current Base Salary: {format_currency(emp_salary, curr_fmt)}</div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 40%;">Salary Slab</th>
                            <th style="width: 30%;">Bonus</th>
                            <th style="width: 30%;">Advance</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for item in tree.get_children():
                tags = tree.item(item, "tags")
                vals = tree.item(item, "values")
                v = list(vals)[:3] 
                while len(v) < 3: v.append("") 
                
                if "month_header" in tags: html_content += f'<tr class="month-header"><td colspan="3">{v[0]}</td></tr>'
                elif "info_row" in tags: html_content += f'<tr class="info-row"><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>'
                elif "deduction_row" in tags: html_content += f'<tr class="deduction-row"><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>'
                elif "net_row" in tags: html_content += f'<tr class="net-row"><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>'
                elif "divider" in tags: html_content += f'<tr class="divider"><td colspan="3"></td></tr>'
                elif "summary_row" in tags: html_content += f'<tr class="summary-row"><td>{v[0]}</td><td>{v[1]}</td><td>{v[2]}</td></tr>'
                elif "empty" not in tags:
                    html_content += f"""
                    <tr class="data-row">
                        <td>{v[0]}</td>
                        <td>{v[1]}</td>
                        <td>{v[2]}</td>
                    </tr>
                    """
            html_content += """
                    </tbody>
                </table>
                <script> window.onload = function() { window.print(); } </script>
            </body>
            </html>
            """
            fd, path = tempfile.mkstemp(suffix=".html", prefix="Emp_Ledger_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
            webbrowser.open('file://' + os.path.realpath(path))

        btn_print.config(command=print_ledger)

        def on_ledger_motion(event):
            region = tree.identify("region", event.x, event.y)
            if region == "separator": return
            item = tree.identify_row(event.y)
            if str(item).startswith("empty"):
                tree.config(cursor="")
                return
            if region == "cell" and tree.identify_column(event.x) == '#4':
                tree.config(cursor="hand2")
            else:
                tree.config(cursor="")
        tree.bind("<Motion>", on_ledger_motion)

        def on_ledger_press(event):
            pop._ledger_press_region = tree.identify("region", event.x, event.y)
        tree.bind("<ButtonPress-1>", on_ledger_press, add="+")

        def on_ledger_del(event):
            if getattr(pop, "_ledger_press_region", "") != "cell": return
            region = tree.identify("region", event.x, event.y)
            item = tree.identify_row(event.y)
            if str(item).startswith("empty"): return
            if region == "cell" and tree.identify_column(event.x) == '#4':
                pay_id = str(item).replace("pay_", "")
                if pay_id:
                    allowed, err_msg = database.check_employee_permission(action="delete", company_id=getattr(parent.winfo_toplevel(), "active_company_id", 1))
                    if not allowed:
                        messagebox.showerror("Access Denied", err_msg, parent=pop)
                        return
                    if messagebox.askyesno("Confirm", "Delete this transaction? Math will be recalculated.", parent=pop):
                        # --- THE FIX: Use secure wrapper for undo cache ---
                        row = database.get_employee_payment_record(int(pay_id))
                        try:
                            database.delete_employee_payment_and_rollback(pay_id)
                            database.log_audit("Employees", "Deleted Payment", record_ref=emp_name, details="Deleted a payment record from the ledger.", company_id=getattr(parent.winfo_toplevel(), "active_company_id", 1))
                            if row: push_undo("DELETE_PAY", row)
                            refresh_data() 
                        except ValueError as e:
                            messagebox.showerror("Database Error", str(e), parent=pop) 

        tree.bind("<ButtonRelease-1>", on_ledger_del, add="+")
        
        # --- THE FIX: Bulletproof Scroll Lock (X and Y Axis) ---
        if saved_y is not None and saved_x is not None:
            def force_scroll():
                try:
                    tree.update_idletasks() # Force UI to finish drawing first
                    tree.yview_moveto(saved_y)
                    tree.xview_moveto(saved_x)
                except: pass
            pop.after(100, force_scroll) # Wait 100ms before jumping

    build_ui()