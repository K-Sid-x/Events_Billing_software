import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import os
import sys
import math
import re
import shutil
import time
import tempfile
import webbrowser

# --- Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)

import database
from views.labour_parts.labour_details import view_labour_details
from views.invoice_parts import helpers
from views.labour_parts.labour_payment_history import LabourPaymentHistoryPopup

# --- THE FIX: Eradicated Calendar Silencer for strict UI enforcement ---
from views.invoice_parts.calendar_widget import NativeCalendar
# -----------------------------------------------------------------------

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def open_labour_ledger(parent_view, labour_id):
    worker = database.get_labour(labour_id)
    if not worker: return
    
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("PRAGMA table_info(labours)")
    cols = [col[1] for col in c.fetchall()]
    conn.close()
    
    w_dict = dict(zip(cols, worker))
    worker_name = w_dict.get('name', 'Worker')
    emp_photo = w_dict.get('photo_path', '')
    
    comp_id = getattr(parent_view.app, "active_company_id", 1)
    curr_fmt, date_fmt_code = helpers.fetch_global_settings(comp_id)
    current_date_str = datetime.date.today().strftime(date_fmt_code)

    t = parent_view.colors
    pop = tk.Toplevel(parent_view)
    pop.title(f"Financial Ledger: {worker_name}")
    
    pop.geometry("980x680")
    pop.configure(bg=t["bg"])
    pop.grab_set()

    try: pop.state('zoomed')
    except tk.TclError: pop.attributes('-zoomed', True)
    
    pop.current_wallet = 0.0
    pop.current_payable = 0.0
    pop.current_page = 1
    pop.items_per_page = 50
    pop.total_pages = 1

    pop.undo_stack = []
    pop.redo_stack = []

    def browse_proof_cmd(attach_var, popup_win):
        path = filedialog.askopenfilename(parent=popup_win, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path: attach_var.set(path)
        popup_win.lift()

    def save_proof_cmd(r_path):
        if not r_path or not os.path.exists(r_path): return ""
        comp_id = getattr(parent_view.app, "active_company_id", 1)
        
        from views.invoice_parts.helpers import get_vault_path
        safe_dir = get_vault_path(ROOT_DIR, comp_id, worker_name, "Labours", labour_id)
        proof_dir = os.path.join(safe_dir, "payment_proofs")
        os.makedirs(proof_dir, exist_ok=True)
        
        ext = os.path.splitext(r_path)[1] or ".png"
        final_attach = os.path.join(proof_dir, f"proof_{int(time.time()*1000)}{ext}")
        try:
            import shutil
            shutil.copy2(r_path, final_attach)
            return final_attach
        except:
            return r_path

    def update_ur_buttons():
        if pop.undo_stack: btn_undo.config(state="normal", bg=t["accent_blue"], fg="#ffffff", cursor="hand2")
        else: btn_undo.config(state="disabled", bg=t["card"], fg=t["border"], cursor="arrow")

        if pop.redo_stack: btn_redo.config(state="normal", bg=t["accent_blue"], fg="#ffffff", cursor="hand2")
        else: btn_redo.config(state="disabled", bg=t["card"], fg=t["border"], cursor="arrow")

    def log_action(action_dict):
        pop.undo_stack.append(action_dict)
        pop.redo_stack.clear()
        update_ur_buttons()

    # --- THE FIX: Expanded Undo/Redo Engine to support Single & Bulk Edits! ---
    def perform_undo():
        if not pop.undo_stack: return
        action = pop.undo_stack.pop()
        
        if action["action"] == "add":
            database.delete_labour_ledger_and_attendance_rollback(action["ledg_id"])
            pop.redo_stack.append(action)
        elif action["action"] == "delete":
            new_ledg_id = database.add_labour_ledger_entry(labour_id, action["d"], action["type"], action["wage_amt"], action["ledger_desc"], action.get("mode", "Cash"), action.get("attachment_path", ""))
            action["new_ledg_id"] = new_ledg_id
            if action["type"] == "Wage":
                new_att_id = database.add_labour_attendance(labour_id, action["d"], action.get("h_val", 1.0), 0.0, 0.0, action.get("base_desc", action["ledger_desc"]))
                action["att_id"] = new_att_id
            pop.redo_stack.append(action)
        elif action["action"] == "bulk_edit_wage":
            for item in action["changes"]:
                database.update_labour_wage_entry(item["ledg_id"], labour_id, item["new_date"], item["old_date"], item["old_amt"], item["old_desc"], item["old_base"], item["old_h_val"])
            pop.redo_stack.append(action)
        elif action["action"] == "edit_other":
            database.update_labour_ledger_entry_details(action["ledg_id"], labour_id, action["e_date"], action["old_desc"], action["old_attach"], False)
            pop.redo_stack.append(action)
            
        update_ur_buttons(); load_ledger(); parent_view.load_data()

    def perform_redo():
        if not pop.redo_stack: return
        action = pop.redo_stack.pop()
        
        if action["action"] == "add":
            new_ledg_id = database.add_labour_ledger_entry(labour_id, action["d"], action["type"], action["wage_amt"], action["ledger_desc"], action.get("mode", "Cash"), action.get("attachment_path", ""))
            action["ledg_id"] = new_ledg_id
            if action["type"] == "Wage":
                new_att_id = database.add_labour_attendance(labour_id, action["d"], action.get("h_val", 1.0), 0.0, 0.0, action.get("base_desc", action["ledger_desc"]))
                action["att_id"] = new_att_id
            pop.undo_stack.append(action)
        elif action["action"] == "delete":
            target_id = action.get("new_ledg_id", action["ledg_id"])
            database.delete_labour_ledger_and_attendance_rollback(target_id)
            pop.undo_stack.append(action)
        elif action["action"] == "bulk_edit_wage":
            for item in action["changes"]:
                database.update_labour_wage_entry(item["ledg_id"], labour_id, item["old_date"], item["new_date"], item["new_amt"], item["new_desc"], item["new_base"], item["new_h_val"])
            pop.undo_stack.append(action)
        elif action["action"] == "edit_other":
            database.update_labour_ledger_entry_details(action["ledg_id"], labour_id, action["e_date"], action["new_desc"], action["new_attach"], False)
            pop.undo_stack.append(action)
            
        update_ur_buttons(); load_ledger(); parent_view.load_data()
    # ----------------------------------------------------------------------------------------

    def show_export_options():
        if not hasattr(pop, 'filtered_rows') or not pop.filtered_rows:
            messagebox.showinfo("Export", "No data to export for this period.", parent=pop)
            return

        opt_pop = tk.Toplevel(pop)
        opt_pop.title("Select Columns to Print")
        opt_pop.geometry("350x380")
        opt_pop.configure(bg=t["bg"])

        opt_pop.update_idletasks()
        x = pop.winfo_rootx() + (pop.winfo_width()//2) - (350//2)
        y = pop.winfo_rooty() + (pop.winfo_height()//2) - (380//2)
        opt_pop.geometry(f"+{max(0, x)}+{max(0, y)}")
        opt_pop.grab_set()

        tk.Label(opt_pop, text="Select columns to export:", font=("Segoe UI", 12, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(15, 10))

        cols_def = [
            ("Date", True),
            ("Particulars", True),
            ("Rate", False),               # Unchecked by default
            ("Earned (+)", True),
            ("Paid / Advance (-)", True),
            ("Payable Bal.", False)        # Unchecked by default
        ]

        vars_dict = {}
        f_frame = tk.Frame(opt_pop, bg=t["bg"])
        f_frame.pack(fill="both", expand=True, padx=40)

        for col_name, default_state in cols_def:
            var = tk.BooleanVar(value=default_state)
            vars_dict[col_name] = var
            chk = tk.Checkbutton(f_frame, text=col_name, variable=var, font=("Segoe UI", 11), bg=t["bg"], fg=t["text"], selectcolor=t["card"], activebackground=t["bg"], activeforeground=t["text"])
            chk.pack(anchor="w", pady=4)

        def confirm():
            selected = {k: v.get() for k, v in vars_dict.items()}
            if not any(selected.values()):
                messagebox.showwarning("Warning", "Select at least one column.", parent=opt_pop)
                return
            opt_pop.destroy()
            export_ledger(selected)

        tk.Button(opt_pop, text="Confirm & Print", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=confirm, pady=8).pack(fill="x", padx=40, pady=(10, 20))

    def export_ledger(selected_cols):
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Labour_Ledger_Print_")
        
        headers_html = ""
        if selected_cols.get("Date"): headers_html += "<th>Date</th>"
        if selected_cols.get("Particulars"): headers_html += "<th>Particulars</th>"
        if selected_cols.get("Rate"): headers_html += "<th style='text-align:center;'>Rate</th>"
        if selected_cols.get("Earned (+)"): headers_html += "<th>Earned (+)</th>"
        if selected_cols.get("Paid / Advance (-)"): headers_html += "<th>Paid / Advance (-)</th>"
        if selected_cols.get("Payable Bal."): headers_html += "<th>Payable Bal.</th>"

        rows_html = ""
        for r in pop.filtered_rows:
            e_id, e_date, e_desc, rate_str, earned, paid, bal_str, val_tag = r
            c_earned = "#0f172a" if earned != "-" else "#475569"
            if val_tag == "bonus": c_paid = "#10b981"
            elif val_tag == "neg": c_paid = "#ef4444"
            else: c_paid = "#475569"
            
            row_html = "<tr>"
            if selected_cols.get("Date"): row_html += f"<td>{e_date}</td>"
            if selected_cols.get("Particulars"): row_html += f"<td>{e_desc}</td>"
            # --- THE FIX: Added white-space: nowrap so it never wraps to two lines! ---
            if selected_cols.get("Rate"): row_html += f"<td style='text-align:center; white-space: nowrap;'>{rate_str}</td>"
            # --------------------------------------------------------------------------
            if selected_cols.get("Earned (+)"): row_html += f"<td style='color:{c_earned};'><b>{earned}</b></td>"
            if selected_cols.get("Paid / Advance (-)"): row_html += f"<td style='color:{c_paid};'><b>{paid}</b></td>"
            if selected_cols.get("Payable Bal."): row_html += f"<td>{bal_str}</td>"
            row_html += "</tr>"
            
            rows_html += row_html

        html = f"""
        <html><head><style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }}
            h2 {{ color: #0f172a; text-transform: uppercase; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; margin-bottom: 5px; }}
            h4 {{ color: #475569; margin-top: 0px; margin-bottom: 20px; font-weight: normal; }}
            .summary-box {{ display: flex; justify-content: space-between; background: #f8fafc; padding: 15px 20px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 15px; margin-bottom: 20px; }}
            .summary-box div {{ line-height: 1.6; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 10px; text-align: left; }}
            th {{ background-color: #f1f5f9; color: #0f172a; font-weight: bold; white-space: nowrap; }}
            td:first-child {{ white-space: nowrap; }}
            tr:nth-child(even) {{ background-color: #f8fafc; }}
        </style></head><body>
        <h2>Financial Statement: {worker_name}</h2>
        <h4>Report Date: {current_date_str} | Filter: {date_filter_var.get()}</h4>
        <div class="summary-box">
            <div>
                <strong>Total Work Logged:</strong> {getattr(pop, 'filtered_hajiras', 0.0)} Shifts<br>
                <strong>Total Earned:</strong> {helpers.format_currency(getattr(pop, 'filtered_earned', 0.0))}<br>
                <strong>Total Paid:</strong> {helpers.format_currency(getattr(pop, 'filtered_paid', 0.0))}
            </div>
            <div style="text-align: right;">
                <!-- THE FIX: Wrapped the amount inside the red strong tag! -->
                <strong style="color: #ef4444;">Advance (Out): {helpers.format_currency(pop.current_wallet)}</strong><br>
                <strong style="color: #10b981; font-size: 18px;">Payable Balance:</strong> <span style="color: #10b981; font-size: 18px; font-weight: bold;">{helpers.format_currency(pop.current_payable)}</span>
            </div>
        </div>
        <table>
            <tr>{headers_html}</tr>
            {rows_html}
        </table>
        <script>window.onload = function() {{ window.print(); }}</script>
        </body></html>
        """
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))


    style = ttk.Style(pop)
    style.theme_use("default")
    
    style.configure("LabourLedger.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.configure("LabourLedger.Horizontal.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("LabourLedger.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    style.map("LabourLedger.Horizontal.TScrollbar", background=[("active", t["accent_blue"])])

    style.configure("Ledger.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], bordercolor=t["border"])
    style.map("Ledger.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
    pop.option_add("*TCombobox*Listbox.background", t["card"])
    pop.option_add("*TCombobox*Listbox.foreground", t["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    header_f = tk.Frame(pop, bg=t["bg"])
    header_f.pack(fill="x", padx=20, pady=(20, 10))
    
    profile_f = tk.Frame(header_f, bg=t["bg"])
    profile_f.pack(side="left")

    photo_lbl = tk.Label(profile_f, bg=t["bg"])
    photo_lbl.pack(side="left", padx=(0, 15))
    
    if emp_photo and os.path.exists(emp_photo) and HAS_PIL:
        try:
            img = Image.open(emp_photo).convert("RGBA")
            img = ImageOps.fit(img, (70, 70), method=Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            bordered = ImageOps.expand(img, border=2, fill=t["accent_blue"])
            photo_img = ImageTk.PhotoImage(bordered)
            photo_lbl.config(image=photo_img)
            photo_lbl.image = photo_img
        except: photo_lbl.config(text="👤", font=("Arial", 36), fg=t["text_sec"])
    else: photo_lbl.config(text="👤", font=("Arial", 36), fg=t["text_sec"])

    info_f = tk.Frame(profile_f, bg=t["bg"])
    info_f.pack(side="left", fill="y", pady=2)
    tk.Label(info_f, text=worker_name, font=("Segoe UI", 16, "bold"), bg=t["bg"], fg=t["text"]).pack(anchor="w")
    work_text_lbl = tk.Label(info_f, text="✅ Total Work Logged: 0.0 Shifts", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["accent_blue"])
    work_text_lbl.pack(anchor="w", pady=(0, 5))
    tk.Button(info_f, text="👁️ View Full Details & Docs", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text_sec"], relief="solid", bd=1, cursor="hand2", padx=10, pady=2, command=lambda: view_labour_details(parent_view, labour_id)).pack(anchor="w")

    balance_f = tk.Frame(header_f, bg=t["bg"])
    balance_f.pack(side="right", fill="y")
    wallet_lbl = tk.Label(balance_f, text="Advance (Out): ₹0.00", font=("Segoe UI", 12, "bold"), bg=t["bg"], fg=t["error"])
    wallet_lbl.pack(anchor="e")
    balance_lbl = tk.Label(balance_f, text="Payable Balance: ₹0.00", font=("Segoe UI", 16, "bold"), bg=t["bg"], fg=t["accent_green"])
    balance_lbl.pack(anchor="e", pady=(2, 0))
    history_lbl = tk.Label(balance_f, text="Total Earned: ₹0.00  |  Total Paid: ₹0.00", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"])
    history_lbl.pack(anchor="e", pady=(5, 0))

    action_f = tk.Frame(pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1, padx=15, pady=10)
    action_f.pack(fill="x", padx=20, pady=(0, 15))
    
    def log_work(btn_widget):
        att_pop = tk.Toplevel(pop)
        att_pop.title("Log Work / Shifts")
        pop_x = btn_widget.winfo_rootx()
        pop_y = btn_widget.winfo_rooty() + btn_widget.winfo_height() + 5
        max_x = pop.winfo_screenwidth() - 360
        att_pop.geometry(f"360x420+{min(pop_x, max_x)}+{pop_y}")
        att_pop.configure(bg=t["bg"])
        att_pop.grab_set()
        
        shifts_f = tk.Frame(att_pop, bg=t["bg"])
        shifts_f.pack(fill="x", padx=20, pady=(15, 5))
        day_var = tk.DoubleVar(value=1.0)
        night_var = tk.DoubleVar(value=0.0)
        
        day_f = tk.Frame(shifts_f, bg=t["bg"])
        day_f.pack(fill="x", pady=2)
        tk.Label(day_f, text="Day Shift:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"], width=12, anchor="w").pack(side="left")
        tk.Button(day_f, text="➖", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: day_var.set(max(0.0, float(day_var.get()) - 0.5)), width=2, relief="solid", bd=1).pack(side="left")
        tk.Entry(day_f, textvariable=day_var, font=("Arial", 13, "bold"), width=5, justify="center", bg=t["card"], fg=t["accent_blue"], bd=0).pack(side="left", padx=8, ipady=3)
        tk.Button(day_f, text="➕", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: day_var.set(float(day_var.get()) + 0.5), width=2, relief="solid", bd=1).pack(side="left")

        night_f = tk.Frame(shifts_f, bg=t["bg"])
        night_f.pack(fill="x", pady=8)
        tk.Label(night_f, text="Night Shift:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"], width=12, anchor="w").pack(side="left")
        tk.Button(night_f, text="➖", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: night_var.set(max(0.0, float(night_var.get()) - 0.5)), width=2, relief="solid", bd=1).pack(side="left")
        tk.Entry(night_f, textvariable=night_var, font=("Arial", 13, "bold"), width=5, justify="center", bg=t["card"], fg=t["accent_blue"], bd=0).pack(side="left", padx=8, ipady=3)
        tk.Button(night_f, text="➕", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: night_var.set(float(night_var.get()) + 0.5), width=2, relief="solid", bd=1).pack(side="left")

        tk.Label(att_pop, text="Date:", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        date_f = tk.Frame(att_pop, bg=t["bg"])
        date_f.pack(fill="x", padx=20)
        date_var = tk.StringVar(value=current_date_str)
        tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(side="left", fill="x", expand=True, ipady=4)
        cal_btn = tk.Button(date_f, text="📅", font=("Segoe UI", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
        cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
        if NativeCalendar: cal_btn.config(command=lambda: NativeCalendar(att_pop, date_var, cal_btn))

        # --- THE FIX: MVC Compliant Daily Rate Fetch ---
        saved_rate = database.get_labour_daily_rate(labour_id)
        # -----------------------------------------------

        tk.Label(att_pop, text="Wage / Rate (Per Shift):", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        rate_var = tk.StringVar(value=f"{saved_rate:.2f}")
        tk.Entry(att_pop, textvariable=rate_var, font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["accent_green"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(att_pop, text="Description / Location (Optional):", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar(value="")
        tk.Entry(att_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        def save():
            try:
                d_val = float(day_var.get())
                n_val = float(night_var.get())
                h_val = d_val + n_val
            except: messagebox.showerror("Error", "Invalid Shift count", parent=att_pop); return
            try: r_val = float(re.sub(r'[^\d\.]', '', rate_var.get()))
            except: messagebox.showerror("Error", "Invalid Rate", parent=att_pop); return
            if h_val <= 0: return
            
            # --- THE FIX: Use safe returning helpers to lock in IDs perfectly! ---
            database.update_labour_daily_rate(labour_id, r_val)
            
            d = date_var.get()
            n = note_var.get().strip()
            
            # --- THE FIX: Updated Shift Formatting ---
            shift_tags = []
            if d_val > 0: shift_tags.append(f"{d_val} Nos. Day Shift")
            if n_val > 0: shift_tags.append(f"{n_val} Nos. Night Shift")
            shift_str = " + ".join(shift_tags)
            base_desc = n if n else "Daily Work Log"
            # ----------------------------------------
            
            att_id = database.add_labour_attendance(labour_id, d, h_val, 0.0, 0.0, base_desc)
            
            wage_amt = h_val * r_val
            ledger_desc = f"{base_desc} ({shift_str} @ {helpers.format_currency(r_val)})"
            ledg_id = database.add_labour_ledger_entry(labour_id, d, 'Wage', wage_amt, ledger_desc, "Cash", "")
            
            database.log_audit("Labours", "Logged Work", record_ref=worker_name, details=f"Logged {h_val} shifts @ @@CURR:{r_val}@@ • {base_desc}", amount=wage_amt, company_id=getattr(parent_view.app, "active_company_id", 1))
            log_action({"action": "add", "type": "Wage", "ledg_id": ledg_id, "att_id": att_id, "d": d, "h_val": h_val, "wage_amt": wage_amt, "ledger_desc": ledger_desc, "base_desc": base_desc})
            # ---------------------------------------------------------------------
            
            att_pop.destroy(); load_ledger(); parent_view.load_data() 
            
        tk.Button(att_pop, text="Save Attendance", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(20, 10), ipady=3)

    def give_bonus(btn_widget):
        b_pop = tk.Toplevel(pop)
        b_pop.title("Give Bonus")
        pop_x = btn_widget.winfo_rootx()
        pop_y = btn_widget.winfo_rooty() + btn_widget.winfo_height() + 5
        b_pop.geometry(f"360x420+{min(pop_x, pop.winfo_screenwidth() - 360)}+{pop_y}")
        b_pop.configure(bg=t["bg"])
        b_pop.grab_set()
        
        tk.Label(b_pop, text="Bonus Amount (₹):", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(20, 2))
        amt_var = tk.StringVar()
        tk.Entry(b_pop, textvariable=amt_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["accent_green"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(b_pop, text="Payment Mode:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        mode_var = tk.StringVar(value="Cash")
        modes = ["Cash", "Bank Transfer", "UPI", "Cheque", "Google Pay", "PhonePe"]
        ttk.Combobox(b_pop, textvariable=mode_var, values=modes, state="readonly", font=("Segoe UI", 11), style="Ledger.TCombobox").pack(fill="x", padx=20, ipady=4)

        tk.Label(b_pop, text="Date:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        date_f = tk.Frame(b_pop, bg=t["bg"])
        date_f.pack(fill="x", padx=20)
        date_var = tk.StringVar(value=current_date_str)
        tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(side="left", fill="x", expand=True, ipady=4)
        cal_btn = tk.Button(date_f, text="📅", font=("Arial", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
        cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
        if NativeCalendar: cal_btn.config(command=lambda: NativeCalendar(b_pop, date_var, cal_btn))

        tk.Label(b_pop, text="Notes:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar(value="Festival / Performance Bonus")
        tk.Entry(b_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(b_pop, text="Payment Proof:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        attach_var = tk.StringVar()
        attach_f = tk.Frame(b_pop, bg=t["bg"])
        attach_f.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=lambda: browse_proof_cmd(attach_var, b_pop)).pack(side="left")
        tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

        def save():
            try: amt = float(re.sub(r'[^\d\.]', '', amt_var.get()))
            except: messagebox.showerror("Error", "Invalid amount", parent=b_pop); return
            if amt <= 0: return
            
            # --- THE FIX: Eliminate MAX(id) Race Condition ---
            final_attach = save_proof_cmd(attach_var.get())
            desc = f"Bonus ({mode_var.get()}) - {note_var.get()}"
            
            ledg_id = database.add_labour_ledger_entry(labour_id, date_var.get(), 'Bonus', -abs(amt), desc, mode_var.get(), final_attach)
            
            database.log_audit("Labours", "Recorded Bonus", record_ref=worker_name, details=f"Amount: @@CURR:{abs(amt)}@@ via {mode_var.get()} • Notes: {note_var.get()}", amount=abs(amt), company_id=getattr(parent_view.app, "active_company_id", 1))
            log_action({"action": "add", "type": "Bonus", "ledg_id": ledg_id, "d": date_var.get(), "wage_amt": -abs(amt), "ledger_desc": desc, "mode": mode_var.get(), "attachment_path": final_attach})
            b_pop.destroy(); load_ledger(); parent_view.load_data() 
            # ------------------------------------------------- 
            
        tk.Button(b_pop, text="Confirm Bonus", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(5, 20), ipady=3)

    def give_advance(btn_widget):
        a_pop = tk.Toplevel(pop)
        a_pop.title("Give Advance")
        pop_x = btn_widget.winfo_rootx()
        pop_y = btn_widget.winfo_rooty() + btn_widget.winfo_height() + 5
        a_pop.geometry(f"360x520+{min(pop_x, pop.winfo_screenwidth() - 360)}+{pop_y}")
        a_pop.configure(bg=t["bg"])
        a_pop.grab_set()
        
        tk.Label(a_pop, text="Advance Amount (₹):", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(20, 2))
        amt_var = tk.StringVar()
        tk.Entry(a_pop, textvariable=amt_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["error"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        adv_toggle_f = tk.Frame(a_pop, bg=t["bg"])
        adv_dir_var = tk.StringVar(value="Given")
        def toggle_adv_note():
            if adv_dir_var.get() == "Refund" and note_var.get() == "Cash Advance":
                note_var.set("Advance Refunded")
                amt_var.set(amt_var.get()) 
            elif adv_dir_var.get() == "Given" and note_var.get() == "Advance Refunded":
                note_var.set("Cash Advance")
                
        rb1 = tk.Radiobutton(adv_toggle_f, text="Advance Given (Out)", variable=adv_dir_var, value="Given", bg=t["bg"], fg=t["text"], selectcolor=t["card"], activebackground=t["bg"], activeforeground=t["text"], cursor="hand2", font=("Segoe UI", 9, "bold"), command=toggle_adv_note)
        rb2 = tk.Radiobutton(adv_toggle_f, text="Advance Refund (In)", variable=adv_dir_var, value="Refund", bg=t["bg"], fg=t["accent_green"], selectcolor=t["card"], activebackground=t["bg"], activeforeground=t["accent_green"], cursor="hand2", font=("Segoe UI", 9, "bold"), command=toggle_adv_note)
        rb1.pack(side="left", padx=(0, 10))
        rb2.pack(side="left")
        adv_toggle_f.pack(fill="x", padx=20, pady=(10, 0))

        tk.Label(a_pop, text="Payment Mode:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        mode_var = tk.StringVar(value="Cash")
        modes = ["Cash", "Bank Transfer", "UPI", "Cheque", "Google Pay", "PhonePe"]
        ttk.Combobox(a_pop, textvariable=mode_var, values=modes, state="readonly", font=("Segoe UI", 11), style="Ledger.TCombobox").pack(fill="x", padx=20, ipady=4)

        tk.Label(a_pop, text="Date:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        date_f = tk.Frame(a_pop, bg=t["bg"])
        date_f.pack(fill="x", padx=20)
        date_var = tk.StringVar(value=current_date_str)
        tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(side="left", fill="x", expand=True, ipady=4)
        cal_btn = tk.Button(date_f, text="📅", font=("Arial", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
        cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
        if NativeCalendar: cal_btn.config(command=lambda: NativeCalendar(a_pop, date_var, cal_btn))

        tk.Label(a_pop, text="Notes:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar(value="Cash Advance")
        tk.Entry(a_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(a_pop, text="Payment Proof:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        attach_var = tk.StringVar()
        attach_f = tk.Frame(a_pop, bg=t["bg"])
        attach_f.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=lambda: browse_proof_cmd(attach_var, a_pop)).pack(side="left")
        tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

        def save():
            try: amt = float(re.sub(r'[^\d\.]', '', amt_var.get()))
            except: messagebox.showerror("Error", "Invalid amount", parent=a_pop); return
            if amt <= 0: return
            
            # --- THE FIX: Eliminate MAX(id) Race Condition ---
            final_amt = -abs(amt) if adv_dir_var.get() == "Given" else abs(amt)
            final_attach = save_proof_cmd(attach_var.get())
            desc = f"Advance ({mode_var.get()}) - {note_var.get()}"
            
            ledg_id = database.add_labour_ledger_entry(labour_id, date_var.get(), 'Advance', final_amt, desc, mode_var.get(), final_attach)
            
            database.log_audit("Labours", "Recorded Advance", record_ref=worker_name, details=f"Amount: @@CURR:{abs(amt)}@@ via {mode_var.get()} • Notes: {note_var.get()}", amount=abs(amt), company_id=getattr(parent_view.app, "active_company_id", 1))
            log_action({"action": "add", "type": "Advance", "ledg_id": ledg_id, "d": date_var.get(), "wage_amt": final_amt, "ledger_desc": desc, "mode": mode_var.get(), "attachment_path": final_attach})
            a_pop.destroy(); load_ledger(); parent_view.load_data() 
            # ------------------------------------------------- 
            
        tk.Button(a_pop, text="Confirm Advance", font=("Segoe UI", 11, "bold"), bg=t["error"], fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(5, 20), ipady=3)

    def make_payment(btn_widget):
        pay_pop = tk.Toplevel(pop)
        pay_pop.title("Make Payment")
        pop_x = btn_widget.winfo_rootx() - 100
        pop_y = btn_widget.winfo_rooty() + btn_widget.winfo_height() + 5
        pay_pop.geometry(f"360x520+{min(pop_x, pop.winfo_screenwidth() - 370)}+{pop_y}")
        pay_pop.configure(bg=t["bg"])
        pay_pop.grab_set()
        
        tk.Label(pay_pop, text="Current Payable Balance:", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(15, 2))
        bal_var = tk.StringVar(value=helpers.format_currency(pop.current_payable))
        tk.Entry(pay_pop, textvariable=bal_var, font=("Segoe UI", 14, "bold"), bg=t["bg"], fg=t["accent_blue"], bd=0, state="readonly", readonlybackground=t["bg"]).pack(fill="x", padx=20, ipady=2)
        
        tk.Label(pay_pop, text="Payment Amount (₹):", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        amt_var = tk.StringVar()
        tk.Entry(pay_pop, textvariable=amt_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["accent_green"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(pay_pop, text="Payment Mode:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        modes = ["Cash", "Bank Transfer", "UPI", "Cheque", "Google Pay", "PhonePe"]
        if pop.current_wallet > 0:
            wallet_str = f"Advance (Out) (Available: {helpers.format_currency(pop.current_wallet)})"
            modes.insert(0, wallet_str) # --- THE FIX: Insert at the very top! ---
            
        # --- THE FIX: Hardcoded to ALWAYS default to Cash ---
        mode_var = tk.StringVar(value="Cash")
        mode_cb = ttk.Combobox(pay_pop, textvariable=mode_var, values=modes, state="readonly", font=("Segoe UI", 11), style="Ledger.TCombobox")
        mode_cb.pack(fill="x", padx=20, ipady=4)

        tk.Label(pay_pop, text="Date:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        date_f = tk.Frame(pay_pop, bg=t["bg"])
        date_f.pack(fill="x", padx=20)
        date_var = tk.StringVar(value=current_date_str)
        tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(side="left", fill="x", expand=True, ipady=4)
        cal_btn = tk.Button(date_f, text="📅", font=("Arial", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
        cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
        if NativeCalendar: cal_btn.config(command=lambda: NativeCalendar(pay_pop, date_var, cal_btn))

        tk.Label(pay_pop, text="Notes:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar(value="Wage Settlement")
        tk.Entry(pay_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

        tk.Label(pay_pop, text="Payment Proof:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        attach_var = tk.StringVar()
        attach_f = tk.Frame(pay_pop, bg=t["bg"])
        attach_f.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=lambda: browse_proof_cmd(attach_var, pay_pop)).pack(side="left")
        tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

        def save():
            try: 
                clean_amt = re.sub(r'[^\d\.\-]', '', amt_var.get())
                amt = float(clean_amt) if clean_amt and clean_amt != '-' else 0.0
            except: messagebox.showerror("Error", "Invalid amount", parent=pay_pop); return
            
            # --- THE FIX: Allow Negative amounts (Refunds) but block strict zero! ---
            if amt == 0: return
            # ------------------------------------------------------------------------
            
            sel_mode = mode_var.get()
            d = date_var.get()
            n = note_var.get()
            
            if "Advance (Out)" in sel_mode:
                if amt > pop.current_wallet:
                    messagebox.showerror("Insufficient Wallet", f"You only have {helpers.format_currency(pop.current_wallet)} available.\n\nYou cannot pay more than the wallet balance.", parent=pay_pop)
                    return
                desc = f"Payment (Advance (Out)) - {n}"
            else:
                desc = f"Payment ({sel_mode}) - {n}"
                
            final_attach = save_proof_cmd(attach_var.get())
            
            # --- THE FIX: Removed abs() trap so negative numbers invert the Database value! ---
            ledg_id = database.add_labour_ledger_entry(labour_id, d, 'Payment', -amt, desc, sel_mode, final_attach)
            
            database.log_audit("Labours", "Recorded Payment", record_ref=worker_name, details=f"Amount: @@CURR:{abs(amt)}@@ via {sel_mode} • Notes: {n}", amount=abs(amt), company_id=getattr(parent_view.app, "active_company_id", 1))
            log_action({"action": "add", "type": "Payment", "ledg_id": ledg_id, "d": d, "wage_amt": -amt, "ledger_desc": desc, "mode": sel_mode, "attachment_path": final_attach})
            pay_pop.destroy(); load_ledger(); parent_view.load_data() 
            # ------------------------------------------------- 
            
        tk.Button(pay_pop, text="Confirm Payment", font=("Segoe UI", 11, "bold"), bg=t["accent_green"], fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(5, 20), ipady=3)

    btn_log = tk.Button(action_f, text="📅 Log Work", font=("Segoe UI", 10, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5)
    btn_log.pack(side="left")
    btn_log.config(command=lambda: log_work(btn_log))

    btn_bonus = tk.Button(action_f, text="🎁 Give Bonus", font=("Segoe UI", 10, "bold"), bg="#f59e0b", fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5)
    btn_bonus.pack(side="left", padx=10)
    btn_bonus.config(command=lambda: give_bonus(btn_bonus))

    btn_adv = tk.Button(action_f, text="💸 Give Advance", font=("Segoe UI", 10, "bold"), bg=t["error"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5)
    btn_adv.pack(side="left")
    btn_adv.config(command=lambda: give_advance(btn_adv))
    
    btn_pay = tk.Button(action_f, text="💵 Make Payment", font=("Segoe UI", 10, "bold"), bg=t["accent_green"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5)
    btn_pay.pack(side="left", padx=10)
    btn_pay.config(command=lambda: make_payment(btn_pay))

    comp_id = getattr(parent_view.app, "active_company_id", 1)
    curr_f, date_f = helpers.fetch_global_settings(comp_id)

    btn_hist = tk.Button(action_f, text="📜 Payment History", font=("Segoe UI", 10, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, highlightbackground=t["border"], cursor="hand2", padx=15, pady=4, command=lambda: LabourPaymentHistoryPopup(pop, labour_id, worker_name, curr_f, date_f, t))
    btn_hist.pack(side="right", padx=(10, 0))

    tk.Button(action_f, text="📤 Print / Export", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=4, command=show_export_options).pack(side="right")

    btn_group = tk.Frame(action_f, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
    btn_group.pack(side="right", padx=(0, 10))

    btn_undo = tk.Button(btn_group, text="↺ Undo", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["border"], relief="flat", padx=10, pady=2, command=lambda: perform_undo(), state="disabled")
    btn_undo.pack(side="left")
    tk.Frame(btn_group, width=1, bg=t["border"]).pack(side="left", fill="y")
    btn_redo = tk.Button(btn_group, text="↻ Redo", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["border"], relief="flat", padx=10, pady=2, command=lambda: perform_redo(), state="disabled")
    btn_redo.pack(side="left")

    toolbar_f = tk.Frame(pop, bg=t["card"])
    toolbar_f.pack(fill="x", padx=20, pady=(0, 5))
    
    filter_f = tk.Frame(toolbar_f, bg=t["card"])
    filter_f.pack(side="left")
    
    tk.Label(filter_f, text="View:", font=("Segoe UI", 10, "bold"), bg=t["card"], fg=t["text_sec"]).pack(side="left")
    
    # --- THE FIX: Default back to All, but reorder the list! ---
    filter_var = tk.StringVar(value="All Transactions")
    
    filter_opts = [
        "All Transactions", 
        "Work Log & Payments (No Advances)",
        "Work Log (Earned)", 
        "Payment History (Paid/Advance)"
    ]
    filter_cb = ttk.Combobox(filter_f, textvariable=filter_var, values=filter_opts, state="readonly", font=("Segoe UI", 10), width=35, style="Ledger.TCombobox")
    # -----------------------------------------------------------
    # -----------------------------------------------------------------------
    
    filter_cb.pack(side="left", padx=(5, 15))
    filter_cb.bind("<<ComboboxSelected>>", lambda e: [setattr(pop, 'current_page', 1), load_ledger()])

    tk.Label(filter_f, text="Date:", font=("Segoe UI", 10, "bold"), bg=t["card"], fg=t["text_sec"]).pack(side="left")
    
    date_filter_var = tk.StringVar(value="All Time")
    date_filter_cb = ttk.Combobox(filter_f, textvariable=date_filter_var, values=["All Time", "This Month", "This Year", "Custom Range"], state="readonly", font=("Segoe UI", 10), width=15, style="Ledger.TCombobox")
    date_filter_cb.pack(side="left", padx=(5, 10))
    
    custom_date_f = tk.Frame(filter_f, bg=t["card"])
    tk.Label(custom_date_f, text="From:", font=("Segoe UI", 9), bg=t["card"], fg=t["text_sec"]).pack(side="left")
    from_date_var = tk.StringVar(value=current_date_str)
    from_ent = tk.Entry(custom_date_f, textvariable=from_date_var, font=("Segoe UI", 10), bg=t["bg"], fg=t["text"], width=10, insertbackground=t["text"])
    from_ent.pack(side="left", padx=(2, 2))
    from_cal = tk.Button(custom_date_f, text="📅", font=("Arial", 9), bg=t["bg"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
    from_cal.pack(side="left", padx=(0, 8))
    if NativeCalendar: from_cal.config(command=lambda: NativeCalendar(pop, from_date_var, from_cal))

    tk.Label(custom_date_f, text="To:", font=("Segoe UI", 9), bg=t["card"], fg=t["text_sec"]).pack(side="left")
    to_date_var = tk.StringVar(value=current_date_str)
    to_ent = tk.Entry(custom_date_f, textvariable=to_date_var, font=("Segoe UI", 10), bg=t["bg"], fg=t["text"], width=10, insertbackground=t["text"])
    to_ent.pack(side="left", padx=(2, 2))
    to_cal = tk.Button(custom_date_f, text="📅", font=("Arial", 9), bg=t["bg"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
    to_cal.pack(side="left")
    if NativeCalendar: to_cal.config(command=lambda: NativeCalendar(pop, to_date_var, to_cal))

    def clear_custom_filter():
        date_filter_var.set("All Time")
        on_date_filter_change()
    tk.Button(custom_date_f, text="✖", font=("Arial", 9, "bold"), bg=t["error"], fg="#ffffff", relief="flat", cursor="hand2", command=clear_custom_filter).pack(side="left", padx=(10, 0))

    def on_date_filter_change(e=None):
        if date_filter_var.get() == "Custom Range": custom_date_f.pack(side="left")
        else: custom_date_f.pack_forget()
        pop.current_page = 1
        load_ledger()
        
    date_filter_cb.bind("<<ComboboxSelected>>", on_date_filter_change)
    from_date_var.trace_add("write", lambda *args: load_ledger() if date_filter_var.get() == "Custom Range" else None)
    to_date_var.trace_add("write", lambda *args: load_ledger() if date_filter_var.get() == "Custom Range" else None)

    table_f = tk.Frame(pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
    table_f.pack(fill="both", expand=True, padx=20, pady=(10, 5))

    style.configure("Ledger.Treeview", font=("Segoe UI", 11), rowheight=30, background=t["bg"], fieldbackground=t["bg"], foreground=t["text"])
    # --- THE FIX: Changed selection highlight to vibrant BLUE! ---
    style.map("Ledger.Treeview", background=[("selected", t["accent_blue"])], foreground=[("selected", "#ffffff")])
    # -------------------------------------------------------------
    style.configure("Ledger.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=t["header"], foreground=t["text"])

    scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="LabourLedger.Vertical.TScrollbar")
    scroll_y.pack(side="right", fill="y")
    scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="LabourLedger.Horizontal.TScrollbar")
    scroll_x.pack(side="bottom", fill="x")

    # --- THE FIX: Added Rate Column & Ghost column trick ---
    tree = ttk.Treeview(table_f, columns=("date", "desc", "rate", "earned", "paid", "balance", "ghost"), show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Ledger.Treeview")
    scroll_y.config(command=tree.yview)
    scroll_x.config(command=tree.xview)
    
    tree.heading("date", text="DATE", anchor="center")
    tree.heading("desc", text="PARTICULARS", anchor="w")
    tree.heading("rate", text="RATE", anchor="center")
    tree.heading("earned", text="EARNED (+)", anchor="center")
    tree.heading("paid", text="PAID/ADVANCE (-)", anchor="center")
    tree.heading("balance", text="PAYABLE BAL.", anchor="e")
    tree.heading("ghost", text="")

    try:
        import json
        conn = database.get_connection(); c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"labour_ledger_cols_{comp_id}",))
        res = c.fetchone()
        conn.close()
        l_w = json.loads(res[0]) if res and res[0] else {}
    except: l_w = {}

    tree.column("date", width=l_w.get("date", 120), anchor="center", stretch=False)
    tree.column("desc", width=l_w.get("desc", 250), anchor="w", stretch=False)
    tree.column("rate", width=l_w.get("rate", 90), anchor="center", stretch=False)
    tree.column("earned", width=l_w.get("earned", 120), anchor="center", stretch=False)
    tree.column("paid", width=l_w.get("paid", 120), anchor="center", stretch=False)
    tree.column("balance", width=l_w.get("balance", 150), minwidth=100, anchor="e", stretch=False)
    tree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_ledger_widths():
        new_w = {c: tree.column(c, "width") for c in ("date", "desc", "rate", "earned", "paid", "balance")}
        try:
            # --- THE FIX: Bulletproof Raw SQL to bypass missing database wrapper functions ---
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("REPLACE INTO ui_settings (setting_key, setting_value) VALUES (?, ?)", (f"labour_ledger_cols_{comp_id}", json.dumps(new_w)))
            conn.commit()
            conn.close()
        except: pass
    # -----------------------------------------------------------------------

    def on_ledger_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator": pop.after(50, save_ledger_widths)

    tree.bind("<B1-Motion>", on_ledger_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_ledger_widths) if tree.identify_region(e.x, e.y) == "separator" else None, add="+")

    tree.pack(side="left", fill="both", expand=True)

    def _fast_scroll(event, direction):
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y":
            tree.yview_moveto(tree.yview()[0] + (delta * 0.008))
        else:
            tree.xview_moveto(tree.xview()[0] + (delta * 0.02))
            
    tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
    tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

    # --- THE FIX: Eradicate Raw SQL from Actions! ---
    def edit_entry(entry_id):
        row = database.get_labour_ledger_record(entry_id)
        if not row: return
        
        e_date, e_type, e_amt, e_desc, e_mode, e_attach = row[2], row[3], row[4], row[5], row[6], row[7]
        
        if e_type == 'Wage':
            import re
            
            # --- Auto-Parse previous data from description ---
            m_day = re.search(r'([\d\.]+)\s*Nos\.\s*Day Shift', e_desc)
            m_night = re.search(r'([\d\.]+)\s*Nos\.\s*Night Shift', e_desc)
            d_val_init = float(m_day.group(1)) if m_day else 0.0
            n_val_init = float(m_night.group(1)) if m_night else 0.0
            
            if d_val_init == 0.0 and n_val_init == 0.0:
                m_hajira = re.search(r'Auto-Wage:\s*([\d\.]+)\s*Hajira', e_desc)
                if m_hajira: d_val_init = float(m_hajira.group(1))
                else: d_val_init = 1.0
                
            base_desc_init = re.sub(r'\s*\([^)]*\)$', '', e_desc).strip()
            if base_desc_init == "Daily Work Log": base_desc_init = ""
            
            total_shifts = d_val_init + n_val_init
            r_val_init = e_amt / total_shifts if total_shifts > 0 else 0.0
            
            edit_pop = tk.Toplevel(pop)
            edit_pop.title("Edit Work Log / Shifts")
            
            pop_x = pop.winfo_pointerx() - 150
            pop_y = pop.winfo_pointery() - 50
            max_x = pop.winfo_screenwidth() - 360
            max_y = pop.winfo_screenheight() - 420
            edit_pop.geometry(f"360x420+{min(max(0, pop_x), max_x)}+{min(max(0, pop_y), max_y)}")
            edit_pop.configure(bg=t["bg"])
            edit_pop.grab_set()
            
            shifts_f = tk.Frame(edit_pop, bg=t["bg"])
            shifts_f.pack(fill="x", padx=20, pady=(15, 5))
            day_var = tk.DoubleVar(value=d_val_init)
            night_var = tk.DoubleVar(value=n_val_init)
            
            day_f = tk.Frame(shifts_f, bg=t["bg"])
            day_f.pack(fill="x", pady=2)
            tk.Label(day_f, text="Day Shift:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"], width=12, anchor="w").pack(side="left")
            tk.Button(day_f, text="➖", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: day_var.set(max(0.0, float(day_var.get()) - 0.5)), width=2, relief="solid", bd=1).pack(side="left")
            tk.Entry(day_f, textvariable=day_var, font=("Arial", 13, "bold"), width=5, justify="center", bg=t["card"], fg=t["accent_blue"], bd=0).pack(side="left", padx=8, ipady=3)
            tk.Button(day_f, text="➕", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: day_var.set(float(day_var.get()) + 0.5), width=2, relief="solid", bd=1).pack(side="left")

            night_f = tk.Frame(shifts_f, bg=t["bg"])
            night_f.pack(fill="x", pady=8)
            tk.Label(night_f, text="Night Shift:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"], width=12, anchor="w").pack(side="left")
            tk.Button(night_f, text="➖", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: night_var.set(max(0.0, float(night_var.get()) - 0.5)), width=2, relief="solid", bd=1).pack(side="left")
            tk.Entry(night_f, textvariable=night_var, font=("Arial", 13, "bold"), width=5, justify="center", bg=t["card"], fg=t["accent_blue"], bd=0).pack(side="left", padx=8, ipady=3)
            tk.Button(night_f, text="➕", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"], command=lambda: night_var.set(float(night_var.get()) + 0.5), width=2, relief="solid", bd=1).pack(side="left")

            tk.Label(edit_pop, text="Date:", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
            date_f = tk.Frame(edit_pop, bg=t["bg"])
            date_f.pack(fill="x", padx=20)
            
            # --- THE FIX: Pass raw DB date through the Smart Formatter ---
            fmt_e_date = helpers.smart_date_formatter(e_date, date_fmt_code)
            date_var = tk.StringVar(value=fmt_e_date)
            # -------------------------------------------------------------
            
            tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(side="left", fill="x", expand=True, ipady=4)
            cal_btn = tk.Button(date_f, text="📅", font=("Segoe UI", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2")
            cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
            if NativeCalendar: cal_btn.config(command=lambda: NativeCalendar(edit_pop, date_var, cal_btn))

            tk.Label(edit_pop, text="Wage / Rate (Per Shift):", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
            rate_var = tk.StringVar(value=f"{r_val_init:.2f}")
            tk.Entry(edit_pop, textvariable=rate_var, font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["accent_green"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

            tk.Label(edit_pop, text="Description / Location (Optional):", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
            note_var = tk.StringVar(value=base_desc_init)
            tk.Entry(edit_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)
            
            def save_wage_edit():
                try:
                    d_val = float(day_var.get())
                    n_val = float(night_var.get())
                    h_val = d_val + n_val
                except: messagebox.showerror("Error", "Invalid Shift count", parent=edit_pop); return
                try: r_val = float(re.sub(r'[^\d\.]', '', rate_var.get()))
                except: messagebox.showerror("Error", "Invalid Rate", parent=edit_pop); return
                if h_val <= 0: return
                
                database.update_labour_daily_rate(labour_id, r_val)
                
                new_d = date_var.get()
                new_n = note_var.get().strip()
                
                shift_tags = []
                if d_val > 0: shift_tags.append(f"{d_val} Nos. Day Shift")
                if n_val > 0: shift_tags.append(f"{n_val} Nos. Night Shift")
                shift_str = " + ".join(shift_tags)
                base_desc = new_n if new_n else "Daily Work Log"
                
                new_wage_amt = h_val * r_val
                new_ledger_desc = f"{base_desc} ({shift_str} @ {helpers.format_currency(r_val)})"
                
                database.update_labour_wage_entry(entry_id, labour_id, e_date, new_d, new_wage_amt, new_ledger_desc, base_desc, h_val)
                
                # --- THE FIX: Make Single Edits Undoable ---
                database.log_audit("Labours", "Edited Work Log", record_ref=worker_name, details=f"Updated wage entry to {h_val} shifts @ @@CURR:{r_val}@@", company_id=getattr(parent_view.app, "active_company_id", 1))
                log_action({
                    "action": "bulk_edit_wage",
                    "changes": [{
                        "ledg_id": entry_id, "old_date": e_date, "new_date": new_d,
                        "old_amt": e_amt, "old_desc": e_desc, "old_base": base_desc_init if base_desc_init else "Daily Work Log", "old_h_val": total_shifts,
                        "new_amt": new_wage_amt, "new_desc": new_ledger_desc, "new_base": base_desc, "new_h_val": h_val
                    }]
                })
                # -------------------------------------------
                edit_pop.destroy(); load_ledger(); parent_view.load_data()
                
            tk.Button(edit_pop, text="💾 Save Changes", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save_wage_edit).pack(fill="x", padx=20, pady=(20, 10), ipady=3)
            return

        # --- Regular Edit Popup for Advance/Bonus/Payment ---
        edit_pop = tk.Toplevel(pop)
        edit_pop.title(f"Edit {e_type} Notes")
        
        pop_x = pop.winfo_pointerx() - 100
        pop_y = pop.winfo_pointery() + 15
        max_x = pop.winfo_screenwidth() - 360
        max_y = pop.winfo_screenheight() - 310
        edit_pop.geometry(f"360x310+{max(0, min(pop_x, max_x))}+{max(0, min(pop_y, max_y))}")
        edit_pop.configure(bg=t["bg"])
        edit_pop.grab_set()

        tk.Label(edit_pop, text=f"Update {e_type} Particulars", font=("Segoe UI", 12, "bold"), bg=t["bg"], fg=t["text"]).pack(anchor="w", padx=20, pady=(15, 10))

        tk.Label(edit_pop, text="Notes / Particulars:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar(value=e_desc)
        tk.Entry(edit_pop, textvariable=note_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"]).pack(fill="x", padx=20, ipady=4)

        attach_var = tk.StringVar(value=e_attach if e_attach else "")
        
        tk.Label(edit_pop, text="Attachment / Proof:", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=20, pady=(15, 2))
        attach_f = tk.Frame(edit_pop, bg=t["bg"])
        attach_f.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(attach_f, text="📎 Attach File", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=lambda: browse_proof_cmd(attach_var, edit_pop)).pack(side="left")
        tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

        def save_edit():
            new_desc = note_var.get().strip()
            final_attach = save_proof_cmd(attach_var.get())
            
            database.update_labour_ledger_entry_details(entry_id, labour_id, e_date, new_desc, final_attach, False)
            
            # --- THE FIX: Make Regular Edits Undoable ---
            database.log_audit("Labours", "Edited Ledger Entry", record_ref=worker_name, details=f"Updated particulars/proof for entry.", company_id=getattr(parent_view.app, "active_company_id", 1))
            log_action({
                "action": "edit_other", "ledg_id": entry_id, "e_date": e_date,
                "old_desc": e_desc, "old_attach": e_attach, "new_desc": new_desc, "new_attach": final_attach
            })
            # --------------------------------------------
            edit_pop.destroy(); load_ledger(); parent_view.load_data()

        tk.Button(edit_pop, text="💾 Save Changes", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save_edit).pack(fill="x", padx=20, pady=(20, 10), ipady=3)

    # --- THE FIX: Advanced Multi-Select Right Click & Bulk Edit Engines ---
    def bulk_edit_rate(selected_items):
        wage_ids = []
        for iid in selected_items:
            row = database.get_labour_ledger_record(int(iid))
            if row and row[3] == 'Wage': wage_ids.append(int(iid))
                
        if not wage_ids:
            messagebox.showwarning("Warning", "None of the selected items are Wage logs.", parent=pop)
            return
            
        rate_pop = tk.Toplevel(pop)
        rate_pop.title("Bulk Edit Rate")
        rate_pop.configure(bg=t["bg"])
        rate_pop.grab_set()
        
        pop_x = pop.winfo_pointerx() - 175
        pop_y = pop.winfo_pointery() - 125
        rate_pop.geometry(f"350x250+{max(0, pop_x)}+{max(0, pop_y)}")
        
        tk.Label(rate_pop, text=f"Update Rate for {len(wage_ids)} Logs", font=("Segoe UI", 12, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(20, 10))
        
        tk.Label(rate_pop, text="New Rate / Wage (₹):", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(anchor="w", padx=30, pady=(10, 2))
        rate_var = tk.StringVar()
        tk.Entry(rate_pop, textvariable=rate_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["accent_green"], insertbackground=t["text"]).pack(fill="x", padx=30, ipady=4)
        
        def apply_bulk_rate():
            try: new_rate = float(re.sub(r'[^\d\.]', '', rate_var.get()))
            except: messagebox.showerror("Error", "Invalid Rate", parent=rate_pop); return
            if new_rate < 0: return
            
            import re
            changes = [] # <--- Track changes
            for w_id in wage_ids:
                row = database.get_labour_ledger_record(w_id)
                if not row: continue
                e_date, e_amt, e_desc = row[2], row[4], row[5]
                
                m_day = re.search(r'([\d\.]+)\s*Nos\.\s*Day Shift', e_desc)
                m_night = re.search(r'([\d\.]+)\s*Nos\.\s*Night Shift', e_desc)
                d_val = float(m_day.group(1)) if m_day else 0.0
                n_val = float(m_night.group(1)) if m_night else 0.0
                
                if d_val == 0.0 and n_val == 0.0:
                    m_hajira = re.search(r'Auto-Wage:\s*([\d\.]+)\s*Hajira', e_desc)
                    if m_hajira: d_val = float(m_hajira.group(1))
                    else: d_val = 1.0
                    
                base_desc = re.sub(r'\s*\([^)]*\)$', '', e_desc).strip()
                if base_desc == "Daily Work Log": base_desc = ""
                
                h_val = d_val + n_val
                new_amt = h_val * new_rate
                
                shift_tags = []
                if d_val > 0: shift_tags.append(f"{d_val} Nos. Day Shift")
                if n_val > 0: shift_tags.append(f"{n_val} Nos. Night Shift")
                shift_str = " + ".join(shift_tags)
                
                final_base = base_desc if base_desc else "Daily Work Log"
                new_ledger_desc = f"{final_base} ({shift_str} @ {helpers.format_currency(new_rate)})"
                
                # --- THE FIX: Store state for Undo Engine ---
                changes.append({
                    "ledg_id": w_id, "old_date": e_date, "new_date": e_date,
                    "old_amt": e_amt, "old_desc": e_desc, "old_base": base_desc if base_desc else "Daily Work Log", "old_h_val": h_val,
                    "new_amt": new_amt, "new_desc": new_ledger_desc, "new_base": final_base, "new_h_val": h_val
                })
                # --------------------------------------------
                database.update_labour_wage_entry(w_id, labour_id, e_date, e_date, new_amt, new_ledger_desc, final_base, h_val)
                
            # --- THE FIX: Push to stack instead of wiping! ---
            if changes: 
                database.log_audit("Labours", "Bulk Edited Rates", record_ref=worker_name, details=f"Updated rate to @@CURR:{new_rate}@@ for {len(wage_ids)} logs.", company_id=getattr(parent_view.app, "active_company_id", 1))
                log_action({"action": "bulk_edit_wage", "changes": changes})
            rate_pop.destroy(); load_ledger(); parent_view.load_data()
            
        tk.Button(rate_pop, text="💾 Apply to All", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=apply_bulk_rate).pack(fill="x", padx=30, pady=(20, 10), ipady=3)

    def bulk_delete_entries(selected_items):
        allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(parent_view.app, "active_company_id", 1))
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=pop)
            return
        if messagebox.askyesno("Confirm", f"Delete {len(selected_items)} selected entries? Math will be recalculated.", parent=pop):
            saved_y = tree.yview()[0]; saved_x = tree.xview()[0]
            try:
                for iid in selected_items: database.delete_labour_ledger_and_attendance_rollback(int(iid))
                database.log_audit("Labours", "Bulk Deleted Ledger Entries", record_ref=worker_name, details=f"Deleted {len(selected_items)} ledger entries.", company_id=getattr(parent_view.app, "active_company_id", 1))
                pop.undo_stack.clear(); pop.redo_stack.clear(); update_ur_buttons()
                load_ledger(); parent_view.load_data()
                def force_scroll():
                    try:
                        tree.update_idletasks()
                        tree.yview_moveto(saved_y); tree.xview_moveto(saved_x)
                    except: pass
                pop.after(100, force_scroll)
            except ValueError as e: messagebox.showerror("Database Error", str(e), parent=pop)

    def on_right_click(event):
        row_id = tree.identify_row(event.y)
        if row_id and not str(row_id).startswith("empty"):
            # Preserve multi-selection if clicking on an already selected item
            if row_id not in tree.selection():
                tree.selection_set(row_id)
            
            selected_ids = tree.selection()
            menu = tk.Menu(pop, tearoff=0, font=("Segoe UI", 10), bg=t["card"], fg=t["text"])
            
            if len(selected_ids) > 1:
                menu.add_command(label=f"✏️ Bulk Edit Rate ({len(selected_ids)} items)", command=lambda: bulk_edit_rate(selected_ids))
                menu.add_command(label=f"❌ Bulk Delete ({len(selected_ids)} items)", command=lambda: bulk_delete_entries(selected_ids), foreground=t["error"])
            else:
                menu.add_command(label="✏️ Edit Entry", command=lambda: edit_entry(row_id))
                menu.add_command(label="❌ Delete Entry", command=lambda: delete_entry(row_id), foreground=t["error"])
                
            menu.tk_popup(event.x_root, event.y_root)

    tree.bind("<Button-3>", on_right_click)

    def delete_entry(entry_id):
    # -------------------------------------------------------------------------
        allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(parent_view.app, "active_company_id", 1))
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=pop)
            return
        if messagebox.askyesno("Confirm", "Delete this ledger entry?", parent=pop):
            row = database.get_labour_ledger_record(entry_id)
            if row:
                # --- THE FIX: Capture Scroll & Rollback Both Ledger + Attendance ---
                saved_y = tree.yview()[0]
                saved_x = tree.xview()[0]
                
                try:
                    database.delete_labour_ledger_and_attendance_rollback(entry_id)
                    database.log_audit("Labours", "Deleted Ledger Entry", record_ref=worker_name, details=f"Deleted {row[3]} of @@CURR:{abs(row[4])}@@.", amount=abs(row[4]), company_id=getattr(parent_view.app, "active_company_id", 1))
                    log_action({"action": "delete", "ledg_id": entry_id, "d": row[2], "type": row[3], "wage_amt": row[4], "ledger_desc": row[5], "mode": row[6], "attachment_path": row[7]})
                    
                    load_ledger(); parent_view.load_data()
                    
                    def force_scroll():
                        try:
                            tree.update_idletasks()
                            tree.yview_moveto(saved_y)
                            tree.xview_moveto(saved_x)
                        except: pass
                    pop.after(100, force_scroll)
                except ValueError as e:
                    messagebox.showerror("Database Error", str(e), parent=pop)
                # ------------------------------------------------------------------
    # --------------------------------------------------------

    pop.pagination_frame = tk.Frame(pop, bg=t["bg"])
    pop.pagination_frame.pack(side="bottom", fill="x", pady=(0, 10))
    def change_page(delta):
        new_page = pop.current_page + delta
        if 1 <= new_page <= pop.total_pages:
            pop.current_page = new_page
            load_ledger()
    btn_prev = tk.Button(pop.pagination_frame, text="< Previous", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["text_sec"], relief="flat", cursor="hand2", command=lambda: change_page(-1))
    btn_prev.pack(side="left", expand=True, anchor="e", padx=10)
    lbl_page = tk.Label(pop.pagination_frame, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["text"])
    lbl_page.pack(side="left", expand=False, anchor="center")
    btn_next = tk.Button(pop.pagination_frame, text="Next >", font=("Arial", 10, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", command=lambda: change_page(1), padx=10, pady=3)
    btn_next.pack(side="left", expand=True, anchor="w", padx=10)

    def load_ledger():
        for item in tree.get_children(): tree.delete(item)
        entries = database.get_labour_ledger(labour_id)
        
        comp_id = getattr(parent_view.app, "active_company_id", 1)
        curr_fmt, date_fmt_code = helpers.fetch_global_settings(comp_id)
        
        global_wallet, global_payable = 0.0, 0.0
        filtered_earned, filtered_paid, filtered_payable = 0.0, 0.0, 0.0
        
        current_filter = filter_var.get()
        opt_date = date_filter_var.get()
        today = datetime.date.today()
        
        def safe_parse_date(d_str, default_val):
            if not d_str: return default_val
            for fmt in (date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try: return datetime.datetime.strptime(str(d_str).strip()[:10], fmt).date()
                except: pass
            return default_val
            
        start_dt = safe_parse_date(from_date_var.get(), datetime.date.min)
        end_dt = safe_parse_date(to_date_var.get(), datetime.date.max)
        
        filtered_rows = []
        
        # --- THE FIX: Sort entries chronologically using helpers.py date formats BEFORE calculating math ---
        sorted_entries = []
        for e in entries:
            sorted_entries.append((safe_parse_date(e[1], datetime.date.min), e))
            
        sorted_entries.sort(key=lambda x: (x[0], int(x[1][0]) if str(x[1][0]).isdigit() else 0))

        for p_dt, e in sorted_entries:
            e_id, e_date, e_type, e_amt, e_desc = e[0], e[1], e[2], e[3], e[4]
            if e_type == 'Wage': global_payable += e_amt
            elif e_type == 'Advance':
                if e_amt < 0: global_wallet += abs(e_amt) 
                else: 
                    global_wallet -= abs(e_amt) 
                    if global_wallet < 0: global_wallet = 0.0
            elif e_type == 'Payment':
                if "Wallet" in e_desc or "(Out)" in e_desc or "Advance Out" in e_desc:
                    global_wallet += e_amt
                    global_payable += e_amt
                    if global_wallet < 0: 
                        global_wallet = 0.0
                else:
                    global_payable += e_amt
                # -------------------------------------------------------------------------------
            
            e_dt = p_dt
            passes_date = True
            if opt_date == "This Month" and (e_dt.year != today.year or e_dt.month != today.month): passes_date = False
            if opt_date == "This Year" and e_dt.year != today.year: passes_date = False
            if opt_date == "Custom Range" and not (start_dt <= e_dt <= end_dt): passes_date = False
            
            if passes_date:
                passes_view = True
                if current_filter == "Work Log (Earned)" and e_type != 'Wage': passes_view = False
                elif current_filter == "Payment History (Paid/Advance)" and e_type not in ('Advance', 'Payment', 'Bonus'): passes_view = False
                elif current_filter == "Work Log & Payments (No Advances)" and e_type == 'Advance': passes_view = False
                
                # --- THE FIX: Tie 'Total Paid' and 'Total Earned' directly to the visual filter! ---
                if e_type == 'Wage': 
                    filtered_payable += e_amt
                    if passes_view: filtered_earned += e_amt
                elif e_type == 'Advance':
                    if e_amt < 0 and passes_view: filtered_paid += abs(e_amt)
                elif e_type == 'Payment':
                    if passes_view: filtered_paid -= e_amt
                    if "Wallet" in e_desc or "(Out)" in e_desc or "Advance Out" in e_desc:
                        filtered_payable += e_amt
                    else:
                        filtered_payable += e_amt
                elif e_type == 'Bonus': 
                    if passes_view: filtered_paid += abs(e_amt)
                # -----------------------------------------------------------------------------------
                
                if passes_view:
                    rate_str = "-"
                    if e_type == 'Wage':
                        import re
                        m = re.search(r'\s*@\s*([^)]*)\)$', str(e_desc))
                        if m:
                            # --- THE FIX: Pass extracted rate through global formatting ---
                            raw_rate = m.group(1).replace('₹', '').replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip()
                            try:
                                parsed_rate = float(raw_rate)
                                rate_str = helpers.format_currency(parsed_rate, curr_fmt)
                            except:
                                rate_str = m.group(1).strip()
                            e_desc = re.sub(r'\s*@\s*[^)]*\)$', ')', str(e_desc))
                    
                    if e_type == 'Bonus':
                        earned, paid, val_tag = "-", f"{helpers.format_currency(abs(e_amt), curr_fmt)} (Gift)", "bonus" 
                    elif e_type == 'Advance' and e_amt > 0:
                        earned, paid, val_tag = f"{helpers.format_currency(abs(e_amt), curr_fmt)} (Refund)", "-", "norm"
                    elif e_type == 'Payment':
                        # --- THE FIX: Render refunds gracefully on the grid! ---
                        if e_amt < 0:
                            earned, paid = "-", helpers.format_currency(abs(e_amt), curr_fmt)
                        else:
                            earned, paid = "-", f"- {helpers.format_currency(e_amt, curr_fmt)} (Refund)"
                            
                        if "Advance Out" in e_desc or "Wallet" in e_desc:
                            val_tag = "neg"
                        else:
                            val_tag = "norm"
                        # -------------------------------------------------------
                    else:
                        if e_amt > 0: earned, paid, val_tag = helpers.format_currency(e_amt, curr_fmt), "-", "norm"
                        elif e_amt < 0: earned, paid, val_tag = "-", helpers.format_currency(abs(e_amt), curr_fmt), "neg"
                        else: earned, paid, val_tag = helpers.format_currency(0, curr_fmt), "-", "norm"

                    bal_str = "-" if e_type in ('Advance', 'Bonus') else helpers.format_currency(global_payable, curr_fmt)
                    
                    # --- THE FIX: Store actual datetime object for perfect sorting! ---
                    filtered_rows.append((e_dt, str(e_id), e_date, e_desc, rate_str, earned, paid, bal_str, val_tag))
                    # ------------------------------------------------------------------
                    
        # --- THE FIX: Chronological sorting (Date first, then ID) ---
        filtered_rows.sort(key=lambda x: (x[0], int(x[1]) if x[1].isdigit() else 0), reverse=True)
        # ------------------------------------------------------------
        
        pop.total_pages = math.ceil(len(filtered_rows) / pop.items_per_page)
        if pop.total_pages < 1: pop.total_pages = 1
        if pop.current_page > pop.total_pages: pop.current_page = pop.total_pages

        start_idx = (pop.current_page - 1) * pop.items_per_page
        page_rows = filtered_rows[start_idx:start_idx + pop.items_per_page]

        lbl_page.config(text=f"Page {pop.current_page} of {pop.total_pages}")
        btn_prev.config(state="normal" if pop.current_page > 1 else "disabled", fg=t["text_sec"] if pop.current_page > 1 else t["border"], cursor="hand2" if pop.current_page > 1 else "arrow")
        btn_next.config(state="normal" if pop.current_page < pop.total_pages else "disabled", fg=t["text"] if pop.current_page < pop.total_pages else t["border"], cursor="hand2" if pop.current_page < pop.total_pages else "arrow")

        idx = 1
        last_month_str = ""
        for r in page_rows:
            e_dt, e_id, e_date, e_desc, rate_str, earned, paid, bal_str, val_tag = r
            
            # --- THE FIX: Apply Global Date Format ---
            fmt_date = helpers.smart_date_formatter(e_date, date_fmt_code)
            # -----------------------------------------
            
            current_month_str = e_dt.strftime("%B, %Y").upper() if e_dt != datetime.date.min else "UNKNOWN DATE"
            if current_month_str != last_month_str:
                tree.insert("", "end", iid=f"empty_header_{current_month_str}_{idx}", values=(f"📅  {current_month_str}", "", "", "", "", "", ""), tags=("month_header", "empty"))
                last_month_str = current_month_str
            
            row_tag = "even" if idx % 2 == 0 else "odd"
            tree.insert("", "end", iid=e_id, values=(fmt_date, e_desc, rate_str, earned, paid, bal_str, ""), tags=(f"{row_tag}_{val_tag}",))
            idx += 1
            
        while idx <= 15:
            tree.insert("", "end", iid=f"empty_{idx}", values=("", "", "", "", "", "", ""), tags=(f"{'even' if idx % 2 == 0 else 'odd'}_norm", "empty"))
            idx += 1
            
        tree.tag_configure("even_norm", background=t["bg"], foreground=t["text"])
        tree.tag_configure("odd_norm", background=t["card"], foreground=t["text"])
        tree.tag_configure("even_bonus", background=t["bg"], foreground=t["accent_green"])
        tree.tag_configure("odd_bonus", background=t["card"], foreground=t["accent_green"])
        tree.tag_configure("even_neg", background=t["bg"], foreground=t["error"])
        tree.tag_configure("odd_neg", background=t["card"], foreground=t["error"])
        
        tree.tag_configure("month_header", background=t["border"], foreground=t["text"], font=("Segoe UI", 12, "bold"))
        
        # --- THE FIX: Removed the heavy Healer scan from the visual refresh loop! ---
        att_rows = database.get_labour_attendance_history(labour_id)
        # ----------------------------------------------------------------------------
        
        filtered_hajiras = 0.0
        for r in att_rows:
            r_dt = safe_parse_date(r[0], datetime.date.min)
            p_date = True
            if opt_date == "This Month" and (r_dt.year != today.year or r_dt.month != today.month): p_date = False
            if opt_date == "This Year" and r_dt.year != today.year: p_date = False
            if opt_date == "Custom Range" and not (start_dt <= r_dt <= end_dt): p_date = False
            if p_date: filtered_hajiras += float(r[1])
            
        pop.current_wallet = global_wallet
        pop.current_payable = global_payable
        
        # --- THE FIX: Clean up Export Cache ---
        pop.filtered_rows = [(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]) for r in filtered_rows]
        
        pop.filtered_hajiras = filtered_hajiras
        pop.filtered_earned = filtered_earned
        pop.filtered_paid = filtered_paid
        
        work_text_lbl.config(text=f"✅ Total Work Logged: {filtered_hajiras} Shifts")
        wallet_lbl.config(text=f"Advance (Out): {helpers.format_currency(global_wallet, curr_fmt)}")
        balance_lbl.config(text=f"Payable Balance: {helpers.format_currency(filtered_payable, curr_fmt)}")
        history_lbl.config(text=f"Total Earned: {helpers.format_currency(filtered_earned, curr_fmt)}  |  Total Paid: {helpers.format_currency(filtered_paid, curr_fmt)}")

    # --- THE FIX: Run the healer exactly ONCE when the window boots up! ---
    database.clean_orphan_attendances(labour_id)
    load_ledger()
    # ----------------------------------------------------------------------