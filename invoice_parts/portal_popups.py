import tkinter as tk
from tkinter import ttk, messagebox
import json
from datetime import datetime
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing for Attachments ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    views_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# ---------------------------------------------------------------

import database
from views.invoice_parts.calendar_widget import NativeCalendar
from views.invoice_parts.helpers import enable_copy_paste, format_currency, fetch_global_settings, smart_date_formatter

def get_wallet_balance(comp_id, name):
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT address FROM customers WHERE name=? AND company_id=?", (name, comp_id))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            try: 
                j_data = json.loads(row[0])
                return float(j_data.get("advance_in", j_data.get("advance_wallet", 0.0)))
            except: pass
    except: pass
    return 0.0

def update_wallet_balance(c, comp_id, name, amount_change):
    if amount_change == 0: return
    try:
        c.execute("SELECT id, address FROM customers WHERE name=? AND company_id=?", (name, comp_id))
        row = c.fetchone()
        if row:
            c_id = row[0]; raw_addr = row[1]
            try: j_data = json.loads(raw_addr)
            except: j_data = {"address": raw_addr if raw_addr else ""}
            
            curr = float(j_data.get("advance_in", j_data.get("advance_wallet", 0.0)))
            j_data["advance_in"] = curr + amount_change
            
            c.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), c_id))
        else:
            j_data = {"address": "", "advance_in": amount_change}
            c.execute("INSERT INTO customers (company_id, name, address) VALUES (?, ?, ?)", (comp_id, name, json.dumps(j_data)))
    except Exception as e: 
        print("Wallet Update Error:", e)

def parse_eu_num(val_str):
    if not val_str: return 0.0
    val_str = str(val_str).replace(",", "").replace(" ", "")
    try: return float(val_str)
    except: return 0.0

def open_receive_advance_dialog(portal, parent_popup, customer_name, refresh_cb, undo_cb=None):
    t = portal.colors
    comp_id = portal.comp_id
    curr_format, date_fmt = fetch_global_settings(comp_id)
    
    current_wallet_bal = get_wallet_balance(comp_id, customer_name)
    
    pop = tk.Toplevel(parent_popup)
    pop.title(f"Manage Advance: {customer_name}")
    pop_w, pop_h = 460, 420
    pop.geometry(f"{pop_w}x{pop_h}")
    pop.configure(bg=t["bg"])
    pop.grab_set()

    style = ttk.Style(pop)
    style.configure("Portal.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], arrowcolor=t["text"], bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"])
    style.map("Portal.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
    pop.option_add("*TCombobox*Listbox.background", t["card"])
    pop.option_add("*TCombobox*Listbox.foreground", t["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    pop.update_idletasks()
    x = parent_popup.winfo_rootx() + (parent_popup.winfo_width()//2) - (pop_w//2)
    y = parent_popup.winfo_rooty() + (parent_popup.winfo_height()//2) - (pop_h//2)
    pop.geometry(f"+{max(0, x)}+{max(0, y)}")

    def remove_focus_pop(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
            pop.focus_set()
            
    pop.bind("<ButtonPress-1>", remove_focus_pop)

    tk.Label(pop, text="Manage Advance Wallet", font=("Segoe UI", 16, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(15, 5))
    tk.Label(pop, text=f"Available Balance: {format_currency(current_wallet_bal, curr_format)}", font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["accent_green"] if current_wallet_bal > 0 else t["text_sec"]).pack(pady=(0, 10))
    
    form_f = tk.Frame(pop, bg=t["bg"])
    form_f.pack(fill="x", padx=30)
    form_f.columnconfigure(1, weight=1)
    form_f.bind("<ButtonPress-1>", remove_focus_pop)
    
    action_var = tk.StringVar(value="Receive")
    toggle_f = tk.Frame(form_f, bg=t["bg"])
    toggle_f.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    
    def on_action_change():
        if action_var.get() == "Refund" and notes_var.get() == "Advance Received":
            notes_var.set("Advance Refunded")
        elif action_var.get() == "Receive" and notes_var.get() == "Advance Refunded":
            notes_var.set("Advance Received")
            
    rb1 = tk.Radiobutton(toggle_f, text="Receive Cash (In)", variable=action_var, value="Receive", bg=t["bg"], fg=t["text"], selectcolor=t["card"], activebackground=t["bg"], activeforeground=t["text"], cursor="hand2", font=("Segoe UI", 9, "bold"), command=on_action_change)
    rb2 = tk.Radiobutton(toggle_f, text="Refund Cash (Out)", variable=action_var, value="Refund", bg=t["bg"], fg=t["error"], selectcolor=t["card"], activebackground=t["bg"], activeforeground=t["error"], cursor="hand2", font=("Segoe UI", 9, "bold"), command=on_action_change)
    rb1.pack(side="left", padx=(0, 15))
    rb2.pack(side="left")
    
    tk.Label(form_f, text="Payment Date:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
    date_var = tk.StringVar(value=datetime.now().strftime(date_fmt))
    d_ent = tk.Entry(form_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    d_ent.grid(row=1, column=1, sticky="ew", pady=5, ipady=3)
    
    btn_cal = tk.Button(form_f, text="📅", bg=t["border"], fg=t["text"], relief="flat", cursor="hand2")
    btn_cal.grid(row=1, column=2, padx=(5,0))
    btn_cal.config(command=lambda b=btn_cal: NativeCalendar(pop, date_var, anchor_widget=b))

    tk.Label(form_f, text="Payment Mode:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=5)
    mode_opts = ["Cash", "Bank Transfer", "UPI", "Google Pay", "PhonePe", "Cheque", "Credit Card"]
    mode_var = tk.StringVar(value="Cash")
    mode_cb = ttk.Combobox(form_f, textvariable=mode_var, values=mode_opts, state="readonly", width=25, style="Portal.TCombobox")
    mode_cb.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)
    mode_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(form_f, text="Amount:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=5)
    pay_var = tk.StringVar(value="0")
    pay_ent = tk.Entry(form_f, textvariable=pay_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    pay_ent.grid(row=3, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)
    pay_ent.bind("<FocusIn>", lambda e: pay_ent.delete('0', 'end') if pay_var.get() == '0' else None)

    tk.Label(form_f, text="Notes:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w", pady=5)
    notes_var = tk.StringVar(value="Advance Received")
    notes_ent = tk.Entry(form_f, textvariable=notes_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    notes_ent.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)
    
    tk.Label(form_f, text="Proof:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w", pady=5)
    attach_var = tk.StringVar()
    attached_file_path = [""]  
    attach_f = tk.Frame(form_f, bg=t["bg"])
    attach_f.grid(row=5, column=1, columnspan=2, sticky="w", pady=5)
    
    def browse_proof():
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path:
            attached_file_path[0] = path
            base_name = os.path.basename(path)
            display_name = base_name if len(base_name) <= 22 else base_name[:19] + "..."
            attach_var.set(display_name)
            
    tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=browse_proof).pack(side="left")
    tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

    adv_warn_var = tk.StringVar()
    adv_warn_lbl = tk.Label(form_f, textvariable=adv_warn_var, bg=t["bg"], fg=t["error"], font=("Segoe UI", 10, "bold"))
    
    btn_save = tk.Button(pop, text="Confirm Transaction", font=("Segoe UI", 12, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2")
    
    def enforce_refund_limit(*args):
        try: amt = float(pay_var.get().replace(",", ""))
        except: amt = 0.0
        if action_var.get() == "Refund" and amt > current_wallet_bal:
            adv_warn_var.set(f"⚠️ Limit Exceeded (Max Refund: {format_currency(current_wallet_bal, curr_format)})")
            adv_warn_lbl.grid(row=6, column=0, columnspan=3, sticky="w", pady=(5,0))
            btn_save.config(state="disabled", bg=t["border"])
        else:
            adv_warn_lbl.grid_forget()
            btn_save.config(state="normal", bg=t["accent_blue"])

    pay_var.trace_add("write", enforce_refund_limit)
    action_var.trace_add("write", enforce_refund_limit)

    def save_advance():
        try: amt = float(pay_var.get().replace(",", ""))
        except: 
            messagebox.showerror("Error", "Invalid amount.", parent=pop)
            return
        if amt <= 0: return
        
        is_refund = (action_var.get() == "Refund")
        if is_refund and amt > current_wallet_bal:
            messagebox.showerror("Error", f"Refund amount cannot exceed available balance of {format_currency(current_wallet_bal, curr_format)}.", parent=pop)
            return

        import shutil
        import time
        import re
        
        final_attach = ""
        r_path = attached_file_path[0]
        if r_path and os.path.exists(r_path):
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Match exact branch using Alias to prevent Vault Leaks! ---
            c.execute("SELECT id FROM customers WHERE (name=? OR name || ' (' || alias || ')' = ?) AND company_id=?", (customer_name, customer_name, comp_id))
            cust_row = c.fetchone()
            cust_id = cust_row[0] if cust_row else "0"
            conn.close()
            
            from views.invoice_parts.helpers import get_vault_path
            base_dir = get_vault_path(ROOT_DIR, comp_id, customer_name, "invoice_payment_receipts", cust_id)
            
            # --- THE FIX: Organize into YYYY/Month folders to prevent Hard Drive Bloat! ---
            try:
                dt = datetime.strptime(date_var.get(), date_fmt)
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            except:
                dt = datetime.now()
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            os.makedirs(safe_dir, exist_ok=True)
            # ------------------------------------------------------------------------------
            
            ext = os.path.splitext(r_path)[1] or ".png"
            prefix = "advance_refund" if is_refund else "advance"
            final_attach = os.path.join(safe_dir, f"{prefix}_{int(time.time()*1000)}{ext}")
            try: shutil.copy2(r_path, final_attach)
            except: final_attach = r_path

        try:
            try: db_date = datetime.strptime(date_var.get(), date_fmt).strftime("%Y-%m-%d")
            except: db_date = datetime.now().strftime("%Y-%m-%d")

            conn = database.get_connection()
            c = conn.cursor()
            
            db_amt = -amt if is_refund else amt
            update_wallet_balance(c, comp_id, customer_name, db_amt)

            ref_label = "Refunded to Customer" if is_refund else "Advance Wallet"
            
            # --- THE FIX: Inject party_id into Advance Payments & Fix Inverted Pay Types ---
            cust_id = getattr(portal, 'cust_id', None)
            actual_pay_type = 'make' if is_refund else 'receive'

            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (comp_id, customer_name, cust_id, actual_pay_type, db_date, db_amt, mode_var.get(), ref_label, notes_var.get() or ("Advance Refunded" if is_refund else "Direct Advance Received"), final_attach))
            
            new_id = c.lastrowid
            c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (new_id,))
            inserted_row = c.fetchone()
            # ------------------------------------------------------
            
            if undo_cb:
                undo_cb({
                    "wallet_change": db_amt,
                    "payment_ids": [new_id],
                    "payment_rows": [inserted_row],
                    "inv_states": [],
                    "new_inv_states": []
                })
            
            conn.commit()
            conn.close()
            database.log_audit(
                "Invoices",
                "Advance Refund" if is_refund else "Advance In",
                "Advance Wallet",
                f"{'Refunded advance to' if is_refund else 'Received advance from'} {customer_name} via {mode_var.get()}",
                amt, company_id=comp_id
            )
            refresh_cb()
            pop.destroy()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=pop)

    btn_save.config(command=save_advance)
    btn_save.pack(fill="x", padx=30, pady=(20, 10), ipady=5)


def open_partial_payment_dialog(portal, parent_popup, bill_data, refresh_cb, customer_name, undo_cb=None):
    t = portal.colors
    b_id, b_date, b_num, tot, paid, bal, woff, stat = bill_data
    woff = woff if woff else 0.0
    
    actual_bal = max(0.0, tot - paid - woff)
    
    comp_id = portal.comp_id
    curr_format, date_fmt = fetch_global_settings(comp_id)

    raw_wallet = get_wallet_balance(comp_id, customer_name)
    available_credit = raw_wallet if raw_wallet > 0 else 0.0

    pay_pop = tk.Toplevel(parent_popup)
    pay_pop.title(f"Receive Payment: {b_num}")
    
    pop_w, pop_h = 510, 460
    pay_pop.geometry(f"{pop_w}x{pop_h}")
    pay_pop.configure(bg=t["bg"])
    pay_pop.grab_set()
    
    style = ttk.Style(pay_pop)
    style.configure("Portal.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], arrowcolor=t["text"], bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"])
    style.map("Portal.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
    pay_pop.option_add("*TCombobox*Listbox.background", t["card"])
    pay_pop.option_add("*TCombobox*Listbox.foreground", t["text"])
    pay_pop.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
    pay_pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    pay_pop.update_idletasks()
    x = parent_popup.winfo_rootx() + (parent_popup.winfo_width()//2) - (pop_w//2)
    y = parent_popup.winfo_rooty() + (parent_popup.winfo_height()//2) - (pop_h//2)
    
    screen_h = parent_popup.winfo_screenheight()
    if y + pop_h > screen_h - 80:
        y = screen_h - pop_h - 80
        
    pay_pop.geometry(f"+{max(0, x)}+{max(0, y)}")
    
    def remove_focus_pop(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
            pay_pop.focus_set()
            
    pay_pop.bind("<ButtonPress-1>", remove_focus_pop)

    tk.Label(pay_pop, text=f"Payment for {b_num}", font=("Segoe UI", 14, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(15, 10))
    
    info = tk.Frame(pay_pop, bg=t["card"], padx=10, pady=10, highlightbackground=t["border"], highlightthickness=1)
    info.pack(fill="x", padx=30, pady=10)
    info.bind("<ButtonPress-1>", remove_focus_pop)
    tk.Label(info, text=f"Invoice Total: {format_currency(tot, curr_format)}", font=("Segoe UI", 11), bg=t["card"], fg=t["text"]).pack(anchor="w", pady=2)
    tk.Label(info, text=f"Balance Due: {format_currency(actual_bal, curr_format)}", font=("Segoe UI", 12, "bold"), fg=t["error"], bg=t["card"]).pack(anchor="w", pady=(5,0))

    form_f = tk.Frame(pay_pop, bg=t["bg"])
    form_f.pack(fill="x", padx=30, pady=10)
    form_f.columnconfigure(1, weight=1)
    form_f.bind("<ButtonPress-1>", remove_focus_pop)

    tk.Label(form_f, text="Payment Date:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
    date_var = tk.StringVar(value=datetime.now().strftime(date_fmt))
    d_ent = tk.Entry(form_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    d_ent.grid(row=0, column=1, sticky="ew", pady=5, ipady=3)
    
    btn_cal = tk.Button(form_f, text="📅", bg=t["border"], fg=t["text"], relief="flat", cursor="hand2")
    btn_cal.grid(row=0, column=2, padx=(5, 0))
    btn_cal.config(command=lambda b=btn_cal: NativeCalendar(pay_pop, date_var, anchor_widget=b))

    tk.Label(form_f, text="Payment Mode:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
    mode_opts = ["Cash", "Bank Transfer", "UPI", "Google Pay", "PhonePe", "Cheque", "Credit Card"]
    
    if available_credit > 0:
        mode_opts.insert(0, f"Wallet Deduction (Bal: {format_currency(available_credit, curr_format)})")
        
    # --- THE FIX: Hardcode the default value to Cash ---
    mode_var = tk.StringVar(value="Cash")
    # ---------------------------------------------------
    mode_cb = ttk.Combobox(form_f, textvariable=mode_var, values=mode_opts, state="readonly", width=42, style="Portal.TCombobox")
    mode_cb.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)
    mode_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(form_f, text="Amount:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=5)
    pay_var = tk.StringVar(value=str(actual_bal))
    pay_ent = tk.Entry(form_f, textvariable=pay_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    pay_ent.grid(row=2, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)
    pay_ent.bind("<FocusIn>", lambda e: pay_ent.delete('0', 'end') if pay_ent.get() == str(actual_bal) else None)

    tk.Label(form_f, text="Notes / Ref:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=5)
    notes_var = tk.StringVar()
    notes_ent = tk.Entry(form_f, textvariable=notes_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    notes_ent.grid(row=3, column=1, columnspan=2, sticky="ew", pady=5, ipady=3)

    tk.Label(form_f, text="Payment Proof:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w", pady=5)
    attach_var = tk.StringVar()
    attached_file_path = [""]  
    attach_f = tk.Frame(form_f, bg=t["bg"])
    attach_f.grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)
    
    def browse_proof():
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=pay_pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path:
            attached_file_path[0] = path
            base_name = os.path.basename(path)
            display_name = base_name if len(base_name) <= 22 else base_name[:19] + "..."
            attach_var.set(display_name)
            
    btn_attach = tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=browse_proof)
    btn_attach.pack(side="left")
    tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

    waive_var = tk.BooleanVar(value=False)
    waive_chk = tk.Checkbutton(form_f, text="", variable=waive_var, bg=t["bg"], fg=t["error"], selectcolor=t["bg"], activebackground=t["bg"], activeforeground=t["error"], font=("Segoe UI", 10, "bold"), cursor="hand2")
    
    adv_info_var = tk.StringVar()
    adv_info_lbl = tk.Label(form_f, textvariable=adv_info_var, bg=t["bg"], font=("Segoe UI", 10, "bold"))

    # --- THE FIX: ADD TDS UI CHECKBOX & ENTRY (WITH SUB-FRAME TO PREVENT GRID COLLAPSE) ---
    tds_f = tk.Frame(form_f, bg=t["bg"])
    tds_f.grid(row=6, column=0, columnspan=3, sticky="w", pady=5)
    
    tds_var = tk.BooleanVar(value=False)
    tds_chk = tk.Checkbutton(tds_f, text="Customer Deducted TDS", variable=tds_var, bg=t["bg"], fg=t["accent_blue"], selectcolor=t["bg"], activebackground=t["bg"], activeforeground=t["accent_blue"], font=("Segoe UI", 10, "bold"), cursor="hand2")
    tds_chk.pack(side="left")
    
    tds_amt_var = tk.StringVar(value="0")
    tds_ent = tk.Entry(tds_f, textvariable=tds_amt_var, font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat", width=12)
    
    def toggle_tds(*args):
        if tds_var.get():
            tds_ent.pack(side="left", padx=10, ipady=3)
            # --- THE FIX: Smart Auto-Fill for TDS! ---
            amt = parse_eu_num(pay_var.get())
            rem = actual_bal - amt
            if rem > 0:
                tds_amt_var.set(f"{rem:.2f}")
            # -----------------------------------------
        else:
            tds_ent.pack_forget()
            tds_amt_var.set("0")
        check_amount()
        
    tds_var.trace_add("write", toggle_tds)
    # --------------------------------------------

    def check_amount(*args):
        amt = parse_eu_num(pay_var.get())
        try: tds_amt = parse_eu_num(tds_amt_var.get()) if tds_var.get() else 0.0
        except: tds_amt = 0.0
        
        # --- THE FIX: Prevent TDS from surviving if Cash covers the whole bill! ---
        rem_for_tds = actual_bal - amt
        if rem_for_tds <= 0 and tds_var.get():
            tds_amt_var.set("0")
            tds_amt = 0.0
            
        eff_amt = amt + tds_amt
        # --------------------------------------------------------------------------
        
        # --- THE FIX: Dynamically show remaining value on the TDS label ---
        if rem_for_tds > 0:
            tds_chk.config(text=f"Customer Deducted TDS (Remaining: {format_currency(rem_for_tds, curr_format)})")
        else:
            tds_chk.config(text="Customer Deducted TDS")
        # ------------------------------------------------------------------
        
        waive_chk.grid_forget()
        adv_info_lbl.grid_forget()
        
        is_wallet = "Wallet Deduction" in mode_var.get()
        
        if is_wallet:
            if amt > available_credit:
                waive_var.set(False)
                adv_info_var.set(f"⚠️ Exceeds Available Wallet Balance!")
                adv_info_lbl.config(fg=t["error"])
                # --- THE FIX: Moved to Row 7 to stop UI collisions! ---
                adv_info_lbl.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))
                pay_pop.geometry(f"{pop_w}x{pop_h + 60}")
            elif eff_amt > actual_bal:
                waive_var.set(False)
                adv_info_var.set(f"⚠️ Cannot overpay bill using Wallet/TDS.")
                adv_info_lbl.config(fg=t["error"])
                adv_info_lbl.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))
                pay_pop.geometry(f"{pop_w}x{pop_h + 60}")
            elif 0 <= eff_amt < actual_bal:
                diff = actual_bal - eff_amt
                waive_chk.config(text=f"Waive remaining {format_currency(diff, curr_format)} (Write-Off)")
                waive_chk.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))
                pay_pop.geometry(f"{pop_w}x{pop_h + 60}")
            else:
                waive_var.set(False)
                pay_pop.geometry(f"{pop_w}x{pop_h + 30}")
        else:
            if 0 <= eff_amt < actual_bal:
                diff = actual_bal - eff_amt
                waive_chk.config(text=f"Waive remaining {format_currency(diff, curr_format)} (Write-Off)")
                # --- THE FIX: Moved to Row 7 to stop UI collisions! ---
                waive_chk.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))
                pay_pop.geometry(f"{pop_w}x{pop_h + 60}")
            elif eff_amt > actual_bal:
                waive_var.set(False)
                diff = eff_amt - actual_bal
                adv_info_var.set(f"To Advance Wallet: {format_currency(diff, curr_format)}")
                adv_info_lbl.config(fg=t["accent_green"])
                adv_info_lbl.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 0))
                pay_pop.geometry(f"{pop_w}x{pop_h + 60}")
            else:
                waive_var.set(False)
                pay_pop.geometry(f"{pop_w}x{pop_h + 30}")

    pay_var.trace_add("write", check_amount)
    mode_var.trace_add("write", check_amount)
    tds_amt_var.trace_add("write", check_amount)
    check_amount()

    def save_payment():
        import shutil
        import time
        import re
        
        amt = parse_eu_num(pay_var.get())
        tds_amt = parse_eu_num(tds_amt_var.get()) if tds_var.get() else 0.0
        
        actual_payment = min(actual_bal, amt)
        remaining_after_cash = max(0.0, actual_bal - actual_payment)
        
        actual_tds = min(remaining_after_cash, tds_amt)
        overpayment = amt - actual_payment if amt > actual_bal else 0.0
        
        is_wallet = "Wallet Deduction" in mode_var.get()
        
        if is_wallet and amt > available_credit:
            messagebox.showerror("Error", f"Amount exceeds wallet balance of {format_currency(available_credit, curr_format)}.", parent=pay_pop)
            return

        if is_wallet and overpayment > 0:
            messagebox.showerror("Invalid Amount", f"You cannot overpay an invoice using the wallet.\n\nPlease enter an amount up to {format_currency(actual_bal, curr_format)}.", parent=pay_pop)
            return
            
        is_waive = waive_var.get()
        woff_amt = max(0.0, actual_bal - actual_payment - actual_tds) if is_waive else 0.0
        
        if actual_payment <= 0 and actual_tds <= 0 and woff_amt <= 0 and overpayment <= 0: return

        clean_mode = "Wallet Deduction" if is_wallet else mode_var.get().split(" (")[0].strip()
        amt_sign = 1 

        new_paid = paid + actual_payment + actual_tds
        new_woff = woff + woff_amt
        new_bal = max(0.0, tot - new_paid - new_woff)
        new_status = 'Paid' if new_bal <= 0.01 else 'Partial'
        
        final_attach = ""
        r_path = attached_file_path[0]
        if r_path and os.path.exists(r_path):
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT id FROM customers WHERE (name=? OR name || ' (' || alias || ')' = ?) AND company_id=?", (customer_name, customer_name, comp_id))
            cust_row = c.fetchone()
            cust_id = cust_row[0] if cust_row else "0"
            conn.close()
            
            from views.invoice_parts.helpers import get_vault_path
            base_dir = get_vault_path(ROOT_DIR, comp_id, customer_name, "invoice_payment_receipts", cust_id)
            safe_bill = re.sub(r'[\\/*?:"<>|]', "_", b_num).strip()
            
            try:
                dt = datetime.strptime(date_var.get(), date_fmt)
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            except:
                dt = datetime.now()
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            os.makedirs(safe_dir, exist_ok=True)
            
            ext = os.path.splitext(r_path)[1] or ".png"
            final_attach = os.path.join(safe_dir, f"payment_{safe_bill}_{int(time.time()*1000)}{ext}")
            try: shutil.copy2(r_path, final_attach)
            except: final_attach = r_path
        
        try:
            try: db_date = datetime.strptime(date_var.get(), date_fmt).strftime("%Y-%m-%d")
            except: db_date = datetime.now().strftime("%Y-%m-%d")

            conn = database.get_connection()
            c = conn.cursor()
            
            old_inv_state = {"id": b_id, "paid": paid, "bal": bal, "woff": woff, "status": stat}
            
            if is_wallet: update_wallet_balance(c, comp_id, customer_name, -actual_payment) 
            elif overpayment > 0: update_wallet_balance(c, comp_id, customer_name, overpayment) 

            c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, write_off=?, status=? WHERE id=? AND company_id=?", (new_paid, new_bal, new_woff, new_status, b_id, comp_id))
            new_inv_state = {"id": b_id, "paid": new_paid, "bal": new_bal, "woff": new_woff, "status": new_status}
            
            inserted_ids = []
            inserted_rows = []
            
            cust_id = getattr(portal, 'cust_id', None)
            
            if actual_payment > 0:
                ref_str = f"{b_num} ({actual_payment})"
                final_notes = notes_var.get().strip() or "Standard Payment"
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (comp_id, customer_name, cust_id, 'receive', db_date, actual_payment * amt_sign, clean_mode, ref_str, final_notes, final_attach))
                nid = c.lastrowid
                inserted_ids.append(nid)
                c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (nid,))
                inserted_rows.append(c.fetchone())
                
            # --- THE FIX: INJECT TDS DATABASE SAVE ---
            if actual_tds > 0:
                tds_ref = f"{b_num} ({actual_tds})"
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (comp_id, customer_name, cust_id, 'receive', db_date, actual_tds * amt_sign, "TDS Deduction", tds_ref, "TDS Deducted by Customer", ""))
                nid = c.lastrowid
                inserted_ids.append(nid)
                c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (nid,))
                inserted_rows.append(c.fetchone())
            # -----------------------------------------
            
            if woff_amt > 0:
                woff_ref = f"{b_num} ({woff_amt})"
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (comp_id, customer_name, cust_id, 'receive', db_date, woff_amt * amt_sign, "Write-Off", woff_ref, "Balance Waived (Write-Off)", ""))
                nid = c.lastrowid
                inserted_ids.append(nid)
                c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (nid,))
                inserted_rows.append(c.fetchone())

            if overpayment > 0 and not is_wallet:
                adv_lbl = "Advance Wallet"
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (comp_id, customer_name, cust_id, 'receive', db_date, overpayment * amt_sign, clean_mode, adv_lbl, f"Invoice #{b_num} overpayment assigned as Advance.", final_attach))
                nid = c.lastrowid
                inserted_ids.append(nid)
                c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (nid,))
                inserted_rows.append(c.fetchone())

            wallet_change = 0.0
            if is_wallet: wallet_change = -actual_payment
            elif overpayment > 0: wallet_change = overpayment
            
            if undo_cb:
                undo_cb({
                    "wallet_change": wallet_change,
                    "payment_ids": inserted_ids,
                    "payment_rows": inserted_rows,
                    "inv_states": [old_inv_state],
                    "new_inv_states": [new_inv_state]
                })

            conn.commit()
            conn.close()
            extras = []
            if actual_tds > 0: extras.append(f"TDS: {actual_tds:.2f}")
            if woff_amt > 0: extras.append(f"Write-Off: {woff_amt:.2f}")
            if overpayment > 0: extras.append(f"Overpaid to Wallet: {overpayment:.2f}")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            database.log_audit(
                "Invoices", "Payment In", b_num,
                f"Received from {customer_name} via {clean_mode}{extra_str} • Status: {new_status}",
                actual_payment if actual_payment > 0 else (actual_tds + woff_amt),
                company_id=comp_id
            )
        except Exception as e: print(f"Payment Save Error: {e}")

        refresh_cb()
        pay_pop.destroy()

    tk.Button(pay_pop, text="Confirm Payment", font=("Segoe UI", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save_payment).pack(fill="x", padx=30, pady=(10, 20))


def open_auto_payment_dialog(portal, parent_popup, customer_name, refresh_cb, undo_cb=None):
    t = portal.colors
    comp_id = portal.comp_id
    curr_format, date_fmt = fetch_global_settings(comp_id)
    
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id, invoice_date, invoice_number, total, amount_paid, balance_due, write_off, status FROM invoices WHERE customer_name=? AND company_id=? AND is_deleted=0 AND status != 'Draft' ORDER BY invoice_date ASC", (customer_name, comp_id))
    raw_unpaid = c.fetchall()
    conn.close()
    
    unpaid = []
    raw_balances = {}
    for r in raw_unpaid:
        b_id, p_date, b_num, tot, paid_so_far, bal_due, woff, stat = r
        woff = woff if woff else 0.0
        actual_due = max(0.0, tot - paid_so_far - woff)
        if actual_due > 0.01:
            unpaid.append(r)
            raw_balances[str(b_id)] = actual_due
            
    if not unpaid:
        messagebox.showinfo("Done", "No unpaid invoices found for this customer.", parent=parent_popup)
        return
        
    total_due = sum(raw_balances.values())
    raw_wallet = get_wallet_balance(comp_id, customer_name)
    available_credit = raw_wallet if raw_wallet > 0 else 0.0
    
    auto_pop = tk.Toplevel(parent_popup)
    auto_pop.title(f"Selective Bulk Allocation: {customer_name}")
    
    pop_w, pop_h = 780, 620
    auto_pop.geometry(f"{pop_w}x{pop_h}")
    auto_pop.configure(bg=t["bg"])
    auto_pop.grab_set()

    style = ttk.Style(auto_pop)
    style.theme_use("default")
    style.configure("AutoPay.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("AutoPay.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    style.configure("Portal.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], arrowcolor=t["text"], bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"])
    style.map("Portal.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
    auto_pop.option_add("*TCombobox*Listbox.background", t["card"])
    auto_pop.option_add("*TCombobox*Listbox.foreground", t["text"])
    auto_pop.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
    auto_pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    auto_pop.update_idletasks()
    x = parent_popup.winfo_rootx() + (parent_popup.winfo_width()//2) - (pop_w//2)
    y = parent_popup.winfo_rooty() + (parent_popup.winfo_height()//2) - (pop_h//2)
    
    screen_h = parent_popup.winfo_screenheight()
    if y + pop_h > screen_h - 130:
        y = screen_h - pop_h - 130
        
    auto_pop.geometry(f"+{max(0, x)}+{max(0, y)}")

    def remove_focus_pop(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
            auto_pop.focus_set()
            
    auto_pop.bind("<ButtonPress-1>", remove_focus_pop)

    tk.Label(auto_pop, text="Selective Bulk Allocation", font=("Segoe UI", 14, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(10, 5))
    
    info = tk.Frame(auto_pop, bg=t["card"], padx=10, pady=5, highlightbackground=t["border"], highlightthickness=1)
    info.pack(fill="x", padx=30, pady=(5, 5))
    info.bind("<ButtonPress-1>", remove_focus_pop)

    left_info = tk.Frame(info, bg=t["card"])
    left_info.pack(side="left", fill="y")
    
    tk.Label(left_info, text=f"Total Unpaid Balance: {format_currency(total_due, curr_format)}", font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["error"]).pack(anchor="w", pady=2)
    
    if available_credit > 0:
        tk.Label(left_info, text=f"Advance Received Available: {format_currency(available_credit, curr_format)}", font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["accent_green"]).pack(anchor="w", pady=2)

    selected_total_var = tk.StringVar(value=f"Selected Total: {format_currency(0, curr_format)}")
    tk.Label(info, textvariable=selected_total_var, font=("Segoe UI", 13, "bold"), bg=t["card"], fg=t["accent_blue"]).pack(side="right", anchor="e", pady=2, padx=(0, 10))

    form_f = tk.Frame(auto_pop, bg=t["bg"])
    form_f.pack(fill="x", padx=30, pady=5)
    form_f.columnconfigure(1, weight=1)
    form_f.columnconfigure(4, weight=1)
    form_f.bind("<ButtonPress-1>", remove_focus_pop)

    unallocated_var = tk.StringVar()

    tk.Label(form_f, text="Payment Date:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
    date_var = tk.StringVar(value=datetime.now().strftime(date_fmt))
    d_ent = tk.Entry(form_f, textvariable=date_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat", width=15)
    d_ent.grid(row=0, column=1, sticky="w", pady=5, ipady=3)
    btn_cal = tk.Button(form_f, text="📅", bg=t["border"], fg=t["text"], relief="flat", cursor="hand2")
    btn_cal.grid(row=0, column=2, sticky="w", padx=(5, 15))
    btn_cal.config(command=lambda b=btn_cal: NativeCalendar(auto_pop, date_var, anchor_widget=b))

    tk.Label(form_f, text="Payment Mode:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=0, column=3, sticky="w", pady=5)
    mode_opts = ["Cash", "Bank Transfer", "UPI", "Google Pay", "PhonePe", "Cheque", "Credit Card"]
    if available_credit > 0: mode_opts.insert(0, f"Wallet Deduction (Bal: {format_currency(available_credit, curr_format)})")
        
    # --- THE FIX: Hardcode the default value to Cash ---
    mode_var = tk.StringVar(value="Cash")
    # ---------------------------------------------------
    mode_cb = ttk.Combobox(form_f, textvariable=mode_var, values=mode_opts, state="readonly", width=35, style="Portal.TCombobox")
    mode_cb.grid(row=0, column=4, sticky="ew", pady=5, ipady=3)
    mode_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(form_f, text="Total Amount:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=5)
    pay_var = tk.StringVar(value="0")
    pay_ent = tk.Entry(form_f, textvariable=pay_var, font=("Segoe UI", 12, "bold"), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat", width=15)
    pay_ent.grid(row=1, column=1, columnspan=2, sticky="w", pady=5, ipady=3)
    pay_ent.bind("<FocusIn>", lambda e: pay_ent.delete('0', 'end') if pay_ent.get() == '0' else None)

    tk.Label(form_f, text="Notes / Ref:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=1, column=3, sticky="w", pady=5)
    notes_var = tk.StringVar()
    notes_ent = tk.Entry(form_f, textvariable=notes_var, font=("Segoe UI", 11), bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent_blue"], highlightthickness=1, bd=0, relief="flat", width=35)
    notes_ent.grid(row=1, column=4, sticky="ew", pady=5, ipady=3)

    tk.Label(form_f, text="Payment Proof:", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=5)
    attach_var = tk.StringVar()
    attached_file_path = [""]  
    attach_f = tk.Frame(form_f, bg=t["bg"])
    attach_f.grid(row=2, column=1, columnspan=2, sticky="w", pady=5)
    
    def browse_proof():
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=auto_pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path:
            attached_file_path[0] = path
            base_name = os.path.basename(path)
            display_name = base_name if len(base_name) <= 22 else base_name[:19] + "..."
            attach_var.set(display_name)
            
    btn_attach = tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=t["border"], fg=t["text"], relief="flat", cursor="hand2", command=browse_proof)
    btn_attach.pack(side="left")
    tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)

    tk.Label(form_f, textvariable=unallocated_var, font=("Segoe UI", 10, "bold"), bg=t["bg"], fg=t["error"]).grid(row=2, column=3, columnspan=2, sticky="w", pady=5)

    tk.Label(auto_pop, text="Select Invoices to Pay (Top to Bottom Allocation):", bg=t["bg"], fg=t["text_sec"], font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=30, pady=(5, 0))

    table_f = tk.Frame(auto_pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
    table_f.pack(fill="both", expand=True, padx=30, pady=(5, 5))
    table_f.bind("<ButtonPress-1>", remove_focus_pop)

    scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="AutoPay.Vertical.TScrollbar")
    scroll_y.pack(side="right", fill="y")
    
    tree = ttk.Treeview(table_f, columns=("check", "bill", "date", "bal", "alloc", "ghost"), show="headings", height=5, style="Portal.Treeview", yscrollcommand=scroll_y.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll_y.config(command=tree.yview)
    
    tree.heading("check", text="[ ]")
    tree.heading("bill", text="INVOICE NO.", anchor="w")
    tree.heading("date", text="DATE", anchor="center")
    tree.heading("bal", text="DUE", anchor="e")
    tree.heading("alloc", text="ALLOCATED", anchor="e")
    tree.heading("ghost", text="")
    
    try:
        raw_setting = database.get_ui_setting("inv_portal_auto_cols", "{}")
        a_w_dict = json.loads(raw_setting) if raw_setting else {}
    except:
        a_w_dict = {}

    tree.column("check", width=a_w_dict.get("check", 50), anchor="center", stretch=False)
    tree.column("bill", width=a_w_dict.get("bill", 130), anchor="w", stretch=False)
    tree.column("date", width=a_w_dict.get("date", 100), anchor="center", stretch=False)
    tree.column("bal", width=a_w_dict.get("bal", 120), anchor="e", stretch=False)
    tree.column("alloc", width=a_w_dict.get("alloc", 120), anchor="e", stretch=False)
    tree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_auto_widths():
        new_w = {c: tree.column(c, "width") for c in ("check", "bill", "date", "bal", "alloc")}
        try:
            # --- THE FIX: Route through database gatekeeper to enforce company_id locks! ---
            database.save_ui_setting("inv_portal_auto_cols", json.dumps(new_w))
            # -------------------------------------------------------------------------------
        except: pass

    def on_auto_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            auto_pop.after(50, save_auto_widths)

    tree.bind("<B1-Motion>", on_auto_sep_drag, add="+")

    selected_bills = set()
    allocations = {}

    def recalculate(*args):
        amt = parse_eu_num(pay_var.get())
        remaining = amt
        
        current_selection_sum = sum(raw_balances.get(b_id, 0.0) for b_id in selected_bills)
        selected_total_var.set(f"Selected Total: {format_currency(current_selection_sum, curr_format)}")
        
        for child in tree.get_children():
            if "empty" in tree.item(child, "tags"): continue 
            b_id = child
            bal = raw_balances.get(b_id, 0.0)
            
            if b_id in selected_bills:
                alloc = min(bal, remaining)
                remaining -= alloc
            else:
                alloc = 0.0
                
            vals = list(tree.item(b_id, "values"))
            vals[4] = format_currency(alloc, curr_format) if alloc > 0 else "-"
            tree.item(b_id, values=vals)
            allocations[b_id] = alloc
            
        if remaining > 0:
            unallocated_var.set(f"⚠️ Overpayment Blocked: {format_currency(remaining, curr_format)}")
        else:
            unallocated_var.set("")

    def toggle_select_all(e):
        region = tree.identify("region", e.x, e.y)
        col = tree.identify_column(e.x)
        if region == "heading" and col == "#1":
            valid_children = [c for c in tree.get_children() if "empty" not in tree.item(c, "tags")]
            if len(selected_bills) == len(unpaid):
                selected_bills.clear()
                tree.heading("check", text="[ ]")
                for child in valid_children:
                    v = list(tree.item(child, "values"))
                    v[0] = "[ ]"
                    tree.item(child, values=v)
            else:
                for child in valid_children:
                    selected_bills.add(child)
                    v = list(tree.item(child, "values"))
                    v[0] = "[✓]"
                    tree.item(child, values=v)
                tree.heading("check", text="[✓]")
            recalculate()

    def on_row_click(e):
        region = tree.identify("region", e.x, e.y)
        if region == "cell":
            iid = tree.identify_row(e.y)
            if iid and "empty" not in tree.item(iid, "tags"):
                if iid in selected_bills:
                    selected_bills.remove(iid)
                    vals = list(tree.item(iid, "values"))
                    vals[0] = "[ ]"
                    tree.item(iid, values=vals)
                else:
                    selected_bills.add(iid)
                    vals = list(tree.item(iid, "values"))
                    vals[0] = "[✓]"
                    tree.item(iid, values=vals)
                recalculate()

    tree.bind("<ButtonRelease-1>", toggle_select_all)
    tree.bind("<ButtonRelease-1>", on_row_click, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: auto_pop.after(50, save_auto_widths), add="+")

    def on_tree_motion(event):
        region = tree.identify("region", event.x, event.y)
        if region == "cell" or (region == "heading" and tree.identify_column(event.x) == "#1"):
            iid = tree.identify_row(event.y)
            if iid and "empty" not in tree.item(iid, "tags"):
                tree.config(cursor="hand2")
            elif region == "heading":
                tree.config(cursor="hand2")
            else:
                tree.config(cursor="")
        else:
            tree.config(cursor="")
            
    tree.bind("<Motion>", on_tree_motion)

    idx = 0
    for p in unpaid:
        b_id, p_date, b_num, tot, paid_so_far, bal_due, woff, stat = p
        actual_due = raw_balances[str(b_id)]
        fmt_date = smart_date_formatter(p_date, date_fmt)
        tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
        tree.insert("", "end", iid=str(b_id), values=("[ ]", b_num, fmt_date, format_currency(actual_due, curr_format), "-", ""), tags=(tag,))
        idx += 1

    for j in range(idx, 5):
        tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
        tree.insert("", "end", values=("", "", "", "", "", ""), tags=(tag, "empty"))

    tree.tag_configure("stripe_even", background=t["stripe_even"])
    tree.tag_configure("stripe_odd", background=t["stripe_odd"])

    pay_var.trace_add("write", recalculate)
    mode_var.trace_add("write", recalculate)

    def process_auto_payment():
        import shutil
        import time
        import re
        
        amt = parse_eu_num(pay_var.get())
        if amt <= 0: return

        is_wallet = "Wallet Deduction" in mode_var.get()
        
        selected_total = sum(raw_balances.get(b_id, 0.0) for b_id in selected_bills)
        
        if is_wallet and amt > available_credit:
            messagebox.showerror("Error", f"Amount exceeds wallet balance of {format_currency(available_credit, curr_format)}.", parent=auto_pop)
            return

        if amt > selected_total:
            messagebox.showerror("Invalid Amount", f"Amount cannot exceed the Selected Total.\n\nPlease check more invoices or enter an amount up to {format_currency(selected_total, curr_format)}.\n\nTo add pure advance credit, use the 'Manage Advance' button.", parent=auto_pop)
            return

        clean_mode = "Wallet Deduction" if is_wallet else mode_var.get().split(" (")[0].strip()
        amt_sign = 1 

        actual_applied = 0.0
        breakdown = []
        
        final_attach = ""
        r_path = attached_file_path[0]
        if r_path and os.path.exists(r_path):
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Match exact branch using Alias to prevent Vault Leaks! ---
            c.execute("SELECT id FROM customers WHERE (name=? OR name || ' (' || alias || ')' = ?) AND company_id=?", (customer_name, customer_name, comp_id))
            cust_row = c.fetchone()
            cust_id = cust_row[0] if cust_row else "0"
            conn.close()
            
            from views.invoice_parts.helpers import get_vault_path
            base_dir = get_vault_path(ROOT_DIR, comp_id, customer_name, "invoice_payment_receipts", cust_id)
            
            # --- THE FIX: Organize into YYYY/Month folders to prevent Hard Drive Bloat! ---
            try:
                dt = datetime.strptime(date_var.get(), date_fmt)
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            except:
                dt = datetime.now()
                safe_dir = os.path.join(base_dir, dt.strftime("%Y"), dt.strftime("%B"))
            os.makedirs(safe_dir, exist_ok=True)
            # ------------------------------------------------------------------------------
            
            ext = os.path.splitext(r_path)[1] or ".png"
            final_attach = os.path.join(safe_dir, f"bulk_payment_{int(time.time()*1000)}{ext}")
            try: shutil.copy2(r_path, final_attach)
            except: final_attach = r_path
        
        try:
            try: db_date = datetime.strptime(date_var.get(), date_fmt).strftime("%Y-%m-%d")
            except: db_date = datetime.now().strftime("%Y-%m-%d")

            conn = database.get_connection()
            c = conn.cursor()
            
            # --- THE FIX: Capture old states for Undo! ---
            old_inv_states = []
            for p in unpaid:
                b_id_str = str(p[0])
                if allocations.get(b_id_str, 0.0) > 0:
                    old_inv_states.append({"id": p[0], "paid": p[4], "bal": p[5], "woff": p[6], "status": p[7]})
            # ---------------------------------------------
            
            for p in unpaid:
                b_id_str = str(p[0])
                alloc = allocations.get(b_id_str, 0.0)
                if alloc > 0:
                    b_id, p_date, b_num, tot, paid_so_far, bal_due, woff, stat = p
                    woff = woff if woff else 0.0
                    
                    new_paid = paid_so_far + alloc
                    new_bal = max(0.0, tot - new_paid - woff)
                    new_status = 'Paid' if new_bal <= 0.01 else 'Partial'
                    
                    c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, write_off=?, status=? WHERE id=? AND company_id=?", (new_paid, new_bal, woff, new_status, b_id, comp_id))
                    breakdown.append((b_num, alloc))
                    actual_applied += alloc

            # --- THE FIX: Capture new states for Redo! ---
            new_inv_states = []
            for inv_dict in old_inv_states:
                c.execute("SELECT amount_paid, balance_due, write_off, status FROM invoices WHERE id=?", (inv_dict["id"],))
                r = c.fetchone()
                new_inv_states.append({"id": inv_dict["id"], "paid": r[0], "bal": r[1], "woff": r[2], "status": r[3]})
            # ---------------------------------------------

            if is_wallet: update_wallet_balance(c, comp_id, customer_name, -actual_applied)

            inserted_ids = []
            inserted_rows = []
            if actual_applied > 0:
                ref_str = " | ".join([f"{inv_no} ({format_currency(chunk_amt, curr_format)})" for inv_no, chunk_amt in breakdown])
                # --- THE FIX: Inject party_id into Auto-Allocated Payments ---
                cust_id = getattr(portal, 'cust_id', None)
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (comp_id, customer_name, cust_id, 'receive', db_date, actual_applied * amt_sign, clean_mode, ref_str, notes_var.get() or "Selected Bulk Payment", final_attach))
                nid = c.lastrowid
                inserted_ids.append(nid)
                c.execute("SELECT id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path FROM party_payments WHERE id=?", (nid,))
                inserted_rows.append(c.fetchone())
                # -------------------------------------------------------------
                          
            wallet_change = -actual_applied if is_wallet else 0.0
            
            if undo_cb:
                undo_cb({
                    "wallet_change": wallet_change,
                    "payment_ids": inserted_ids,
                    "payment_rows": inserted_rows,
                    "inv_states": old_inv_states,
                    "new_inv_states": new_inv_states
                })
                          
            conn.commit()
            conn.close()
            if actual_applied > 0:
                bill_list = ", ".join([b_no for b_no, _ in breakdown])
                database.log_audit(
                    "Invoices", "Bulk Payment", bill_list,
                    f"Auto-allocated payment from {customer_name} via {clean_mode}",
                    actual_applied, company_id=comp_id
                )
        except Exception as e: print(f"Allocation Error: {e}")

        refresh_cb()
        auto_pop.destroy()

    tk.Button(auto_pop, text="Confirm Selected Allocation", font=("Segoe UI", 12, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=process_auto_payment).pack(fill="x", padx=30, pady=(10, 15), ipady=10)