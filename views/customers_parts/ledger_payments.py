import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import shutil
import time
import webbrowser
import database
import re
from datetime import datetime
from views.customers_parts.ledger_core import execute_ledger_load

# --- THE FIX: Import NativeCalendar securely ---
from views.invoice_parts.calendar_widget import NativeCalendar

current_dir = os.path.dirname(os.path.abspath(__file__))
views_dir = os.path.dirname(current_dir)
ROOT_DIR = os.path.dirname(views_dir)
if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)

from views.invoice_parts.portal_popups import compute_proportional_allocations

def open_payment_popup(ledger, pay_type="receive"):
    conn = database.get_connection()
    c = conn.cursor()
    
    if pay_type == "receive":
        c.execute("SELECT id, invoice_number, balance_due, invoice_date, subtotal FROM invoices WHERE customer_name=? AND company_id=? AND balance_due > 0 AND is_deleted=0 AND status != 'Draft' ORDER BY invoice_date ASC", (ledger.party_name, ledger.comp_id))
    else:
        c.execute("SELECT id, bill_number, balance_due, purchase_date, subtotal FROM purchases WHERE vendor_name=? AND company_id=? AND balance_due > 0 AND is_deleted=0 AND is_draft=0 ORDER BY purchase_date ASC", (ledger.party_name, ledger.comp_id))
        
    raw_unpaid_bills = c.fetchall()
    
    unpaid_bills = []
    raw_subtotals = {}
    for r in raw_unpaid_bills:
        unpaid_bills.append(r)
        sub_val = float(r[4] or 0.0) if len(r) > 4 else float(r[2] or 0.0)
        raw_subtotals[str(r[0])] = sub_val
        
    conn.close()

    p_pop = tk.Toplevel(ledger)
    p_pop.title("Receive Payment" if pay_type == "receive" else "Make Payment")
    
    pop_w, pop_h = 510, 380 
    p_pop.configure(bg=ledger.colors["bg"])
    p_pop.grab_set()

    def center_popup(w, h):
        p_pop.update_idletasks()
        x = ledger.winfo_rootx() + (ledger.winfo_width() // 2) - (w // 2)
        y = ledger.winfo_rooty() + (ledger.winfo_height() // 2) - (h // 2)
        screen_h = p_pop.winfo_screenheight()
        
        if y + h > screen_h - 80:
            y = screen_h - h - 80
            
        p_pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    center_popup(pop_w, pop_h)

    top_f = tk.Frame(p_pop, bg=ledger.colors["bg"])
    top_f.pack(fill="x")
    
    table_f = tk.Frame(p_pop, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    
    btn_f = tk.Frame(p_pop, bg=ledger.colors["bg"])
    btn_f.pack(side="bottom", fill="x")

    tk.Label(top_f, text=p_pop.title(), font=("Segoe UI", 16, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["accent_green"] if pay_type == "receive" else ledger.colors["accent_blue"]).pack(pady=(15, 5))

    form_f = tk.Frame(top_f, bg=ledger.colors["bg"])
    form_f.pack(fill="x", padx=30)

    def remove_focus_pop(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
            p_pop.focus_set()
            
    p_pop.bind("<ButtonPress-1>", remove_focus_pop)
    top_f.bind("<ButtonPress-1>", remove_focus_pop)
    form_f.bind("<ButtonPress-1>", remove_focus_pop)
    table_f.bind("<ButtonPress-1>", remove_focus_pop)
    btn_f.bind("<ButtonPress-1>", remove_focus_pop)

    tk.Label(form_f, text="Apply Payment To:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=8)
    
    apply_opts = []
    
    if pay_type == "make" and ledger.advance_in > 0:
        apply_opts.append(f"Refund Advance to Customer ({ledger.fmt(ledger.advance_in)} Available)")
    elif pay_type == "receive" and ledger.advance_out > 0:
        apply_opts.append(f"Receive Refund from Vendor ({ledger.fmt(ledger.advance_out)} Available)")
        
    ob_due = max(0.0, ledger.ob_val - ledger.ob_paid)
    has_ob_target = False
    
    if pay_type == "receive" and "Dr" in ledger.ob_type and ob_due > 0:
        apply_opts.append(f"Opening Balance (Due: {ledger.fmt(ob_due)})")
        has_ob_target = True
    elif pay_type == "make" and "Cr" in ledger.ob_type and ob_due > 0:
        apply_opts.append(f"Opening Balance (Due: {ledger.fmt(ob_due)})")
        has_ob_target = True
        
    if unpaid_bills or has_ob_target:
        apply_opts.append("Selective Bulk Allocation")
        
    for r in unpaid_bills:
        apply_opts.append(f"{r[1]} (Due: {ledger.fmt(r[2])})")
        
    if not apply_opts:
        apply_opts.append("No Pending Actions")
        
    apply_var = tk.StringVar(value=apply_opts[0])
    apply_cb = ttk.Combobox(form_f, textvariable=apply_var, values=apply_opts, state="readonly", width=42, style="Ledger.TCombobox")
    apply_cb.grid(row=0, column=1, sticky="w", pady=8, padx=10)

    tk.Label(form_f, text="Payment Date:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=8)
    p_date_var = tk.StringVar(value=datetime.now().strftime(ledger.date_fmt_code))
    p_date_btn = tk.Button(form_f, textvariable=p_date_var, bg=ledger.colors["card"], fg=ledger.colors["text"], font=("Segoe UI", 10), relief="solid", bd=1, cursor="hand2", width=41)
    # --- THE FIX: Passed anchor_widget cleanly without the unnecessary date_fmt_code ---
    p_date_btn.config(command=lambda: NativeCalendar(ledger, p_date_var, anchor_widget=p_date_btn))
    p_date_btn.grid(row=1, column=1, sticky="w", pady=8, padx=10)

    tk.Label(form_f, text="Payment Mode:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=8)
    
    p_mode_opts = ["Cash", "Bank Transfer", "UPI", "Google Pay", "PhonePe", "Cheque", "Credit Card"]
    
    active_wallet_bal = 0.0
    if pay_type == "receive" and ledger.advance_in > 0:
        active_wallet_bal = ledger.advance_in
    elif pay_type == "make" and ledger.advance_out > 0:
        active_wallet_bal = ledger.advance_out
        
    if active_wallet_bal > 0:
        p_mode_opts.insert(0, f"Wallet Deduction (Bal: {ledger.fmt(active_wallet_bal)})")
        
    p_mode_var = tk.StringVar(value=p_mode_opts[0])
    p_mode_cb = ttk.Combobox(form_f, textvariable=p_mode_var, values=p_mode_opts, state="readonly", width=42, style="Ledger.TCombobox")
    p_mode_cb.grid(row=2, column=1, sticky="w", pady=8, padx=10)

    tk.Label(form_f, text="Amount:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", pady=8)
    p_amt_var = tk.StringVar()
    
    p_amt_ent = tk.Entry(form_f, textvariable=p_amt_var, font=("Segoe UI", 11), width=18, bg=ledger.colors["card"], fg=ledger.colors["text"], insertbackground=ledger.colors["text"], highlightbackground=ledger.colors["border"], highlightcolor=ledger.colors["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    p_amt_ent.grid(row=3, column=1, sticky="w", pady=8, padx=10)

    tk.Label(form_f, text="Notes / Ref:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=4, column=0, sticky="w", pady=8)
    p_notes_var = tk.StringVar()
    
    p_notes_ent = tk.Entry(form_f, textvariable=p_notes_var, font=("Segoe UI", 11), width=30, bg=ledger.colors["card"], fg=ledger.colors["text"], insertbackground=ledger.colors["text"], highlightbackground=ledger.colors["border"], highlightcolor=ledger.colors["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    p_notes_ent.grid(row=4, column=1, sticky="w", pady=8, padx=10)

    tk.Label(form_f, text="Payment Proof:", bg=ledger.colors["bg"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).grid(row=5, column=0, sticky="w", pady=8)
    attach_var = tk.StringVar()
    attach_f = tk.Frame(form_f, bg=ledger.colors["bg"])
    attach_f.grid(row=5, column=1, sticky="w", pady=8, padx=10)
    
    def browse_proof():
        path = filedialog.askopenfilename(parent=p_pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path: attach_var.set(path)
        
    tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=ledger.colors["border"], fg=ledger.colors["text"], relief="flat", cursor="hand2", command=browse_proof).pack(side="left")
    tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=ledger.colors["bg"], fg=ledger.colors["text_sec"]).pack(side="left", padx=5)

    is_waive_blocked = False
    curr_role = getattr(ledger.app, "current_role", "Admin")
    curr_uid = getattr(ledger.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
    if curr_role != "Admin" and str(curr_uid) != "1":
        u_perms = database.get_user_permissions(curr_uid)
        p_rules = u_perms.get("party_rules", {}) if isinstance(u_perms.get("party_rules"), dict) else {}
        if p_rules.get("block_waive_off", False):
            is_waive_blocked = True

    action_var = tk.IntVar(value=0)
    action_chk = tk.Checkbutton(form_f, text="☑ Waive remaining balance", variable=action_var, bg=ledger.colors["bg"], fg=ledger.colors["error"], font=("Segoe UI", 10, "bold"), selectcolor=ledger.colors["bg"], cursor="hand2")
    
    adv_info_var = tk.StringVar()
    adv_info_lbl = tk.Label(form_f, textvariable=adv_info_var, bg=ledger.colors["bg"], fg=ledger.colors["accent_green"], font=("Segoe UI", 10, "bold"))

    # --- THE FIX: SMART TDS UI WITH PERCENTAGE AUTO-FILL FOR LEDGER ---
    tds_f = tk.Frame(form_f, bg=ledger.colors["bg"])
    tds_f.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 5))
    
    tds_var = tk.BooleanVar(value=False)
    tds_label_text = "Customer Deducted TDS" if pay_type == "receive" else "We Deducted TDS"
    tds_chk = tk.Checkbutton(tds_f, text=tds_label_text, variable=tds_var, bg=ledger.colors["bg"], fg=ledger.colors["accent_blue"], selectcolor=ledger.colors["bg"], activebackground=ledger.colors["bg"], activeforeground=ledger.colors["accent_blue"], font=("Segoe UI", 10, "bold"), cursor="hand2")
    tds_chk.pack(side="left")
    
    tds_rate_var = tk.StringVar(value="1%")
    tds_rate_cb = ttk.Combobox(tds_f, textvariable=tds_rate_var, values=["Auto Balance", "1%", "2%", "5%", "10%", "Custom"], state="readonly", width=12, style="Ledger.TCombobox")
    
    tds_amt_var = tk.StringVar(value="0")
    tds_ent = tk.Entry(tds_f, textvariable=tds_amt_var, font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text"], insertbackground=ledger.colors["text"], highlightbackground=ledger.colors["border"], highlightcolor=ledger.colors["accent_blue"], highlightthickness=1, bd=0, relief="flat", width=12)
    
    _is_auto_updating = [False]
    def on_tds_manual_edit(*args):
        if not _is_auto_updating[0] and tds_var.get():
            tds_rate_var.set("Custom")
            
    tds_amt_var.trace_add("write", on_tds_manual_edit)
    tds_rate_var.trace_add("write", lambda *a: check_amount() if apply_var.get() != "Selective Bulk Allocation" else recalculate())
    
    def toggle_tds(*args):
        if tds_var.get():
            tds_rate_cb.pack(side="left", padx=(10, 5), ipady=2)
            tds_ent.pack(side="left", padx=5, ipady=3)
        else:
            tds_rate_cb.pack_forget()
            tds_ent.pack_forget()
            _is_auto_updating[0] = True
            tds_amt_var.set("0")
            _is_auto_updating[0] = False
            tds_rate_var.set("1%")
            
        if apply_var.get() == "Selective Bulk Allocation": recalculate()
        else: check_amount()
        
    tds_var.trace_add("write", toggle_tds)
    tds_amt_var.trace_add("write", lambda *a: check_amount() if apply_var.get() != "Selective Bulk Allocation" else recalculate())
    # ------------------------------------------------------

    bulk_header_f = tk.Frame(table_f, bg=ledger.colors["card"])
    bulk_header_f.pack(fill="x", padx=10, pady=(10, 5))
    
    tk.Label(bulk_header_f, text="Select Items to Pay (Top to Bottom Allocation):", bg=ledger.colors["card"], fg=ledger.colors["text_sec"], font=("Segoe UI", 10, "bold")).pack(side="left")
    
    sel_total_var = tk.StringVar(value=f"Selected Total: {ledger.fmt(0)}")
    tk.Label(bulk_header_f, textvariable=sel_total_var, font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=ledger.colors["accent_blue"]).pack(side="right", padx=(0, 5))
    
    style = ttk.Style(p_pop)
    style.theme_use("default")
    style.configure("LedgerModal.Vertical.TScrollbar", background=ledger.colors["text_sec"], troughcolor=ledger.colors["bg"], bordercolor=ledger.colors["bg"], arrowcolor=ledger.colors["text"], relief="flat")
    style.map("LedgerModal.Vertical.TScrollbar", background=[("active", ledger.colors["accent_blue"])])
    
    tree_container = tk.Frame(table_f, bg=ledger.colors["card"])
    tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    bulk_scroll_y = ttk.Scrollbar(tree_container, orient="vertical", style="LedgerModal.Vertical.TScrollbar")
    bulk_scroll_y.pack(side="right", fill="y")
    
    bulk_tree = ttk.Treeview(tree_container, columns=("check", "bill", "date", "bal", "alloc", "ghost"), show="headings", height=5, style="Ledger.Treeview", yscrollcommand=bulk_scroll_y.set)
    bulk_tree.pack(side="left", fill="both", expand=True)
    bulk_scroll_y.config(command=bulk_tree.yview)
    
    bulk_tree.heading("check", text="[ ]")
    bulk_tree.heading("bill", text="BILL NO. / OB", anchor="w")
    bulk_tree.heading("date", text="DATE", anchor="center")
    bulk_tree.heading("bal", text="DUE", anchor="e")
    bulk_tree.heading("alloc", text="ALLOCATED", anchor="e")
    bulk_tree.heading("ghost", text="")
    
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"ledger_bulk_cols_{ledger.comp_id}",))
        res = c.fetchone()
        conn.close()
        b_w_dict = json.loads(res[0]) if res and res[0] else {}
    except:
        b_w_dict = {}

    bulk_tree.column("check", width=b_w_dict.get("check", 50), anchor="center", stretch=False)
    bulk_tree.column("bill", width=b_w_dict.get("bill", 150), anchor="w", stretch=False)
    bulk_tree.column("date", width=b_w_dict.get("date", 100), anchor="center", stretch=False)
    bulk_tree.column("bal", width=b_w_dict.get("bal", 120), anchor="e", stretch=False)
    bulk_tree.column("alloc", width=b_w_dict.get("alloc", 120), anchor="e", stretch=False)
    bulk_tree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_bulk_widths():
        new_w = {c: max(30, bulk_tree.column(c, "width")) for c in ("check", "bill", "date", "bal", "alloc")}
        try:
            database.save_ui_setting(f"ledger_bulk_cols_{ledger.comp_id}", json.dumps(new_w))
        except: pass

    def on_bulk_sep_drag(event):
        if bulk_tree.identify_region(event.x, event.y) == "separator":
            p_pop.after(50, save_bulk_widths)

    bulk_tree.bind("<B1-Motion>", on_bulk_sep_drag, add="+")
    bulk_tree.bind("<ButtonRelease-1>", lambda e: p_pop.after(50, save_bulk_widths) if bulk_tree.identify_region(e.x, e.y) == "separator" else None, add="+")

    bulk_targets = []
    raw_balances = {}
    if has_ob_target:
        bulk_targets.append(("OB", "Opening Balance", "Opening", ob_due))
        raw_balances["OB"] = ob_due
    for r in unpaid_bills:
        bulk_targets.append((str(r[0]), r[1], ledger.fmt_date(r[3]), r[2]))
        raw_balances[str(r[0])] = r[2]
        
    for idx, t in enumerate(bulk_targets):
        tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
        bulk_tree.insert("", "end", iid=t[0], values=("[ ]", t[1], t[2], ledger.fmt(t[3]), "-", ""), tags=(tag,))
    
    for j in range(len(bulk_targets), 5):
        tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
        bulk_tree.insert("", "end", values=("", "", "", "", "", ""), tags=(tag, "empty"))

    selected_targets = set()
    allocations = {}
    preview_allocs_state = {}

    def recalculate(*args):
        try: amt = float(p_amt_var.get().strip())
        except: amt = 0.0
        
        sel_sum = sum(t[3] for t in bulk_targets if t[0] in selected_targets)
        sel_total_var.set(f"Selected Total: {ledger.fmt(sel_sum)}")
        
        # --- SMART TDS AUTO-FILL ---
        if tds_var.get() and not _is_auto_updating[0]:
            rate_val = tds_rate_var.get()
            calc_tds = None
            if rate_val == "Auto Balance":
                calc_tds = max(0.0, sel_sum - amt)
            elif rate_val.endswith("%"):
                pct = float(rate_val.replace("%", "")) / 100.0
                selected_subtotal = 0.0
                for t_id in selected_targets:
                    if t_id == "OB": selected_subtotal += ob_due
                    else: selected_subtotal += raw_subtotals.get(t_id, 0.0)
                # Standard Rounding: 0.40 drops, 0.50 pushes to next integer
                calc_tds = int((selected_subtotal * pct) + 0.5)
                
            if calc_tds is not None:
                try: current_tds_val = float(tds_amt_var.get().strip() or 0.0)
                except: current_tds_val = 0.0
                if abs(current_tds_val - calc_tds) > 0.001:
                    _is_auto_updating[0] = True
                    tds_amt_var.set(f"{calc_tds:.2f}")
                    # --- THE FIX: Auto-Fill Cash Amount to Balance Perfectly ---
                    if rate_val.endswith("%"):
                        new_amt = max(0.0, sel_sum - calc_tds)
                        p_amt_var.set(f"{new_amt:.2f}")
                        amt = new_amt
                    # -----------------------------------------------------------
                    _is_auto_updating[0] = False
        # ---------------------------
        
        try: tds_amt = float(tds_amt_var.get().strip()) if tds_var.get() else 0.0
        except: tds_amt = 0.0
        
        eff_amt = amt + tds_amt
        remaining_unaccounted = sel_sum - eff_amt
        
        # Clean label (Removed confusing Remaining balance text)
        base_lbl = "Customer Deducted TDS" if pay_type == "receive" else "We Deducted TDS"
        tds_chk.config(text=base_lbl)
            
        action_chk.grid_forget()
        
        preview_allocs = compute_proportional_allocations(selected_targets, raw_balances, amt, tds_amt, action_var.get(), raw_subtotals)
        preview_allocs_state.clear()
        preview_allocs_state.update(preview_allocs)
        
        for child in bulk_tree.get_children():
            if "empty" in bulk_tree.item(child, "tags"): continue 
            t_id = child
            
            alloc_info = preview_allocs.get(str(t_id), {"total": 0.0})
            tot_alloc = alloc_info["total"]
            
            vals = list(bulk_tree.item(t_id, "values"))
            vals[4] = ledger.fmt(tot_alloc) if tot_alloc > 0 else "-"
            bulk_tree.item(t_id, values=vals)
            allocations[t_id] = alloc_info
            
        if apply_var.get() == "Selective Bulk Allocation":
            is_wallet = "Wallet Deduction" in p_mode_var.get()
            
            if is_wallet and amt > active_wallet_bal:
                adv_info_var.set("⚠️ Exceeds Available Wallet Balance!")
                adv_info_lbl.config(fg=ledger.colors["error"])
                adv_info_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 8), padx=5)
            elif remaining_unaccounted < -0.01:
                adv_info_var.set(f"⚠️ Overpayment Blocked: {ledger.fmt(abs(remaining_unaccounted))}")
                adv_info_lbl.config(fg=ledger.colors["error"])
                adv_info_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 8), padx=5)
            else:
                adv_info_lbl.grid_forget()
                if 0 <= remaining_unaccounted <= sel_sum and remaining_unaccounted > 0.01 and not is_waive_blocked:
                    action_chk.config(text=f"☑ Waive remaining {ledger.fmt(remaining_unaccounted)} (Write-Off)")
                    action_chk.grid(row=7, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                else:
                    action_var.set(False)

    def toggle_select_all(e):
        region = bulk_tree.identify("region", e.x, e.y)
        col = bulk_tree.identify_column(e.x)
        if region == "heading" and col == "#1":
            valid_children = [c for c in bulk_tree.get_children() if "empty" not in bulk_tree.item(c, "tags")]
            if len(selected_targets) == len(bulk_targets):
                selected_targets.clear()
                bulk_tree.heading("check", text="[ ]")
                for child in valid_children:
                    v = list(bulk_tree.item(child, "values"))
                    v[0] = "[ ]"
                    bulk_tree.item(child, values=v)
            else:
                for child in valid_children:
                    selected_targets.add(child)
                    v = list(bulk_tree.item(child, "values"))
                    v[0] = "[✓]"
                    bulk_tree.item(child, values=v)
                bulk_tree.heading("check", text="[✓]")
            recalculate()

    def on_row_click(e):
        region = bulk_tree.identify("region", e.x, e.y)
        if region == "cell":
            iid = bulk_tree.identify_row(e.y)
            if iid and "empty" not in bulk_tree.item(iid, "tags"):
                if iid in selected_targets:
                    selected_targets.remove(iid)
                    vals = list(bulk_tree.item(iid, "values"))
                    vals[0] = "[ ]"
                    bulk_tree.item(iid, values=vals)
                else:
                    selected_targets.add(iid)
                    vals = list(bulk_tree.item(iid, "values"))
                    vals[0] = "[✓]"
                    bulk_tree.item(iid, values=vals)
                recalculate()

    bulk_tree.bind("<ButtonRelease-1>", toggle_select_all)
    bulk_tree.bind("<ButtonRelease-1>", on_row_click, add="+")

    def update_ui_layout(*args):
        sel = apply_var.get()
        if "Refund" in sel or "No Pending Actions" in sel:
            filtered_modes = [m for m in p_mode_opts if "Wallet Deduction" not in m]
            p_mode_cb.config(values=filtered_modes)
            if "Wallet Deduction" in p_mode_var.get():
                p_mode_var.set("Cash")
            tds_f.grid_forget()
            tds_var.set(False)
        else:
            p_mode_cb.config(values=p_mode_opts)
            # Move TDS UP to Row 6 (Above Waive)
            tds_f.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 5))
            
        if sel == "Selective Bulk Allocation":
            center_popup(780, 620)
            table_f.pack(fill="both", expand=True, padx=30, pady=(5, 10))
            recalculate()
        else:
            table_f.pack_forget()
            check_amount()

    apply_var.trace_add("write", update_ui_layout)
    p_mode_var.trace_add("write", lambda *a: update_ui_layout() if apply_var.get() == "Selective Bulk Allocation" else check_amount())

    def check_amount(*args):
        try: amt = float(p_amt_var.get().strip())
        except: amt = 0.0
        
        sel = apply_var.get()
        action_chk.grid_forget()
        adv_info_lbl.grid_forget()
        action_var.set(0)
        
        if "Refund" in sel or "No Pending Actions" in sel:
            tds_f.grid_forget()
            tds_var.set(False)
        else:
            # Place TDS ABOVE the Waive box (Row 6)
            tds_f.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 5))

        if "Refund" in sel or "No Pending Actions" in sel:
            center_popup(pop_w, 380)
            return

        if sel == "Selective Bulk Allocation":
            recalculate()
            return

        try:
            if "Opening Balance" in sel:
                due = ob_due
                sel_subtotal = ob_due
            else:
                offset = len(apply_opts) - len(unpaid_bills)
                sel_idx = apply_opts.index(sel) - offset
                due = unpaid_bills[sel_idx][2]
                sel_subtotal = raw_subtotals.get(str(unpaid_bills[sel_idx][0]), due)
                
            # --- SMART TDS AUTO-FILL ---
            if tds_var.get() and not _is_auto_updating[0]:
                rate_val = tds_rate_var.get()
                calc_tds = None
                if rate_val == "Auto Balance":
                    calc_tds = max(0.0, due - amt)
                elif rate_val.endswith("%"):
                    pct = float(rate_val.replace("%", "")) / 100.0
                    # Standard Rounding: 0.40 drops, 0.50 pushes to next integer
                    calc_tds = int((sel_subtotal * pct) + 0.5)
                    
                if calc_tds is not None:
                    try: current_tds_val = float(tds_amt_var.get().strip() or 0.0)
                    except: current_tds_val = 0.0
                    if abs(current_tds_val - calc_tds) > 0.001:
                        _is_auto_updating[0] = True
                        tds_amt_var.set(f"{calc_tds:.2f}")
                        # --- THE FIX: Auto-Fill Cash Amount to Balance Perfectly ---
                        if rate_val.endswith("%"):
                            new_amt = max(0.0, due - calc_tds)
                            p_amt_var.set(f"{new_amt:.2f}")
                            amt = new_amt
                        # -----------------------------------------------------------
                        _is_auto_updating[0] = False
            # ---------------------------
            
            try: tds_amt = float(tds_amt_var.get().strip()) if tds_var.get() else 0.0
            except: tds_amt = 0.0
                
            eff_amt = amt + tds_amt
            
            # Clean label (Removed confusing Remaining balance text)
            base_lbl = "Customer Deducted TDS" if pay_type == "receive" else "We Deducted TDS"
            tds_chk.config(text=base_lbl)
                
            is_wallet = "Wallet Deduction" in p_mode_var.get()
            
            if is_wallet:
                if amt > active_wallet_bal:
                    adv_info_var.set("⚠️ Exceeds Available Wallet Balance!")
                    adv_info_lbl.config(fg=ledger.colors["error"])
                    adv_info_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                    center_popup(pop_w, 440)
                elif eff_amt > due:
                    adv_info_var.set("⚠️ Cannot overpay bill using Wallet/TDS.")
                    adv_info_lbl.config(fg=ledger.colors["error"])
                    adv_info_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                    center_popup(pop_w, 440)
                elif 0 <= eff_amt < due and not is_waive_blocked:
                    diff = due - eff_amt
                    action_chk.config(text=f"☑ Waive remaining {ledger.fmt(diff)} (Write-Off)")
                    action_chk.grid(row=7, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                    center_popup(pop_w, 440)
                else:
                    center_popup(pop_w, 400)
            else:
                if 0 <= eff_amt < due and not is_waive_blocked:
                    diff = due - eff_amt
                    action_chk.config(text=f"☑ Waive remaining {ledger.fmt(diff)} (Write-Off)")
                    action_chk.grid(row=7, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                    center_popup(pop_w, 440) 
                elif eff_amt > due:
                    diff = eff_amt - due
                    adv_info_var.set(f"To Advance Wallet: {ledger.fmt(diff)}")
                    adv_info_lbl.config(fg=ledger.colors["accent_green"])
                    adv_info_lbl.grid(row=8, column=0, columnspan=2, sticky="w", pady=(5, 5), padx=5)
                    center_popup(pop_w, 440)
                else:
                    center_popup(pop_w, 400) 
        except:
            center_popup(pop_w, 400)

    # --- THE MISSING FIX: Force the UI to listen to your keyboard! ---
    p_amt_var.trace_add("write", check_amount)
    update_ui_layout()

    def safe_update_advance(cursor, cust_db_id, amount_change, pocket):
        cursor.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (cust_db_id, ledger.comp_id))
        raw_addr = cursor.fetchone()[0]
        try: j_data = json.loads(raw_addr)
        except Exception: j_data = {"address": raw_addr if raw_addr else ""}
        
        if pocket == "advance_in":
            current = float(j_data.get("advance_in", j_data.get("advance_wallet", 0.0)))
        elif pocket == "advance_out":
            current = float(j_data.get("advance_out", 0.0))
        elif pocket == "ob_paid":
            current = float(j_data.get("ob_paid", 0.0))
            
        j_data[pocket] = current + amount_change
        cursor.execute("UPDATE customers SET address=? WHERE id=? AND company_id=?", (json.dumps(j_data), cust_db_id, ledger.comp_id))

    def save_payment():
        try: pay_amt = float(p_amt_var.get().strip())
        except: 
            messagebox.showerror("Error", "Enter a valid amount.", parent=p_pop)
            return
            
        try: tds_amt = float(tds_amt_var.get().strip()) if tds_var.get() else 0.0
        except: tds_amt = 0.0

        if pay_amt <= 0 and tds_amt <= 0: return

        sel_apply = apply_var.get()
        is_refund = "Refund" in sel_apply
        is_wallet = "Wallet Deduction" in p_mode_var.get()
        
        if "Refund" in sel_apply or "No Pending Actions" in sel_apply:
            tds_amt = 0.0 # Guard against stray TDS data
        
        if is_refund:
            target_bal = ledger.advance_in if pay_type == "make" else ledger.advance_out
        else:
            target_bal = ledger.advance_in if pay_type == "receive" else ledger.advance_out

        if is_wallet and pay_amt > target_bal:
            messagebox.showerror("Error", f"Amount exceeds wallet balance of {ledger.fmt(target_bal)}.", parent=p_pop)
            return
            
        if is_refund and pay_amt > target_bal:
            messagebox.showerror("Error", f"Refund exceeds available advance of {ledger.fmt(target_bal)}.", parent=p_pop)
            return

        total_due_all = 0.0
        single_invoice = False
        
        if "No Pending Actions" not in sel_apply and not is_refund:
            if sel_apply == "Selective Bulk Allocation":
                total_due_all = sum(t[3] for t in bulk_targets if t[0] in selected_targets)
                single_invoice = False
                
                if pay_amt > total_due_all:
                    messagebox.showerror("Invalid Amount", f"Amount cannot exceed the Selected Total.\n\nPlease check more items or enter an amount up to {ledger.fmt(total_due_all)}.", parent=p_pop)
                    return
            else:
                if "Opening Balance" in sel_apply:
                    total_due_all = ob_due
                else:
                    offset = len(apply_opts) - len(unpaid_bills)
                    sel_idx = apply_opts.index(sel_apply) - offset
                    total_due_all = unpaid_bills[sel_idx][2]
                single_invoice = True

            if is_wallet and pay_amt > total_due_all:
                messagebox.showerror("Invalid Amount", f"You cannot overpay items using the wallet.\n\nPlease check more items or enter an amount up to {ledger.fmt(total_due_all)}.", parent=p_pop)
                return

        final_attach = ""
        r_path = attach_var.get()
        if r_path and os.path.exists(r_path):
            from views.invoice_parts.helpers import get_vault_path
            folder_name = "purchase_payment_receipts" if pay_type == "make" else "invoice_payment_receipts"
            safe_dir = get_vault_path(ROOT_DIR, ledger.comp_id, ledger.party_name, folder_name, ledger.cust_db_id)
            
            ext = os.path.splitext(r_path)[1] or ".png"
            
            if "Advance" in sel_apply or is_refund: prefix = "advance"
            elif single_invoice and "Opening Balance" not in sel_apply:
                safe_bill = re.sub(r'[\\/*?:"<>|]', "_", unpaid_bills[sel_idx][1]).strip()
                prefix = f"payment_{safe_bill}"
            else: prefix = "bulk_payment"
                
            final_attach = os.path.join(safe_dir, f"{prefix}_{int(time.time()*1000)}{ext}")
            try: shutil.copy2(r_path, final_attach)
            except: final_attach = r_path

        conn = database.get_connection()
        c = conn.cursor()
        try: c.execute("ALTER TABLE party_payments ADD COLUMN attachment_path TEXT")
        except: pass
        
        table = "invoices" if pay_type == "receive" else "purchases"
        c.execute(f"PRAGMA table_info({table})")
        
        has_woff = "written_off" in [col[1] for col in c.fetchall()]
        notes_text = p_notes_var.get().strip()
        
        action_log = {
            "pay_type": pay_type, "invoices_changed": [], 
            "old_adv_in": ledger.advance_in, "old_adv_out": ledger.advance_out,
            "old_ob_paid": ledger.ob_paid,
            "pay_date": p_date_var.get(), "mode": p_mode_var.get(), "notes": notes_text,
            "pay_ids": [], "history_rows": []
        }

        if is_waive_blocked:
            action_var.set(0)

        clean_mode = "Wallet Deduction" if is_wallet else p_mode_var.get().split(" (")[0].strip()
        audit_act = ""
        audit_det = ""
        audit_amt = pay_amt

        # --- THE FIX: Inject party_id into direct and refund payments ---
        if "No Pending Actions" in sel_apply:
            pocket = "advance_in" if pay_type == "receive" else "advance_out"
            adv_change = pay_amt 
            safe_update_advance(c, ledger.cust_db_id, adv_change, pocket)
            
            adv_lbl = "Advance Wallet"
            amt_sign = 1 if pay_type == "receive" else -1 
            
            action_log["history_rows"].append((pay_amt * amt_sign, clean_mode, adv_lbl, notes_text or "Direct Advance Payment", final_attach))
            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (ledger.comp_id, ledger.party_name, ledger.cust_db_id, pay_type, p_date_var.get(), pay_amt * amt_sign, clean_mode, adv_lbl, notes_text or "Direct Advance Payment", final_attach))
            action_log["pay_ids"].append(c.lastrowid)
            audit_act = "Advance In" if pay_type == "receive" else "Advance Out"
            audit_det = f"Direct Advance ({clean_mode}) on @@DATE:{p_date_var.get()}@@" + (f" • Note: {notes_text}" if notes_text else "")

        elif is_refund:
            pocket = "advance_in" if pay_type == "make" else "advance_out"
            adv_change = -pay_amt
            safe_update_advance(c, ledger.cust_db_id, adv_change, pocket)
            
            adv_lbl = "Refunded to Customer" if pay_type == "make" else "Refunded from Vendor"
            amt_sign = -1 if pay_type == "make" else 1 
            
            action_log["history_rows"].append((pay_amt * amt_sign, clean_mode, adv_lbl, notes_text, final_attach))
            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (ledger.comp_id, ledger.party_name, ledger.cust_db_id, pay_type, p_date_var.get(), pay_amt * amt_sign, clean_mode, adv_lbl, notes_text, final_attach))
            action_log["pay_ids"].append(c.lastrowid)
            audit_act = "Advance Refund"
            audit_det = f"{adv_lbl} ({clean_mode}) on @@DATE:{p_date_var.get()}@@" + (f" • Note: {notes_text}" if notes_text else "")
        # ----------------------------------------------------------------

        else:
            actual_applied = 0.0
            actual_tds = 0.0
            remaining_funds = pay_amt
            breakdown_text = []
            breakdown_tds = []
            breakdown_woff = []
            total_write_off = 0.0
            ob_paid_now = 0.0

            if not single_invoice:
                for t in bulk_targets:
                    t_id = t[0]
                    info = preview_allocs_state.get(str(t_id), {"cash": 0.0, "tds": 0.0, "woff": 0.0})
                    alloc_cash = info["cash"]
                    alloc_tds = info["tds"]
                    alloc_woff = info["woff"]
                    
                    if alloc_cash > 0 or alloc_tds > 0 or alloc_woff > 0:
                        if t_id == "OB":
                            ob_paid_now = alloc_cash + alloc_tds + alloc_woff
                            actual_applied += alloc_cash
                            actual_tds += alloc_tds
                            total_write_off += alloc_woff
                            if alloc_cash > 0: breakdown_text.append(f"Opening Balance ({ledger.fmt(alloc_cash)})")
                            if alloc_tds > 0: breakdown_tds.append(f"Opening Balance ({ledger.fmt(alloc_tds)})")
                            if alloc_woff > 0: breakdown_woff.append(f"Opening Balance ({ledger.fmt(alloc_woff)})")
                        else:
                            inv_id = int(t_id)
                            inv_num = t[1]
                            
                            c.execute(f"SELECT amount_paid, balance_due, status FROM {table} WHERE id=? AND company_id=?", (inv_id, ledger.comp_id))
                            row_data = c.fetchone()
                            curr_paid, curr_due, curr_status = row_data[0], row_data[1], row_data[2]
                            
                            curr_woff = 0.0
                            if has_woff:
                                c.execute(f"SELECT written_off FROM {table} WHERE id=? AND company_id=?", (inv_id, ledger.comp_id))
                                curr_woff = c.fetchone()[0] or 0.0

                            action_log["invoices_changed"].append((inv_id, curr_paid, curr_due, curr_status, curr_woff)) 
                            
                            new_paid = (curr_paid or 0) + alloc_cash + alloc_tds
                            new_woff = curr_woff + alloc_woff
                            new_due = max(0, curr_due - (alloc_cash + alloc_tds + alloc_woff))
                            new_status = "Paid" if new_due <= 0.01 else "Partial"
                            
                            if has_woff: c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, new_woff, inv_id, ledger.comp_id))
                            else: c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, inv_id, ledger.comp_id))
                            
                            actual_applied += alloc_cash
                            actual_tds += alloc_tds
                            total_write_off += alloc_woff
                            
                            if alloc_cash > 0: breakdown_text.append(f"{inv_num} ({ledger.fmt(alloc_cash)})")
                            if alloc_tds > 0: breakdown_tds.append(f"{inv_num} ({ledger.fmt(alloc_tds)})")
                            if alloc_woff > 0: breakdown_woff.append(f"{inv_num} ({ledger.fmt(alloc_woff)})")
                
                remaining_funds = 0.0 # Handled by the helper math
            else:
                actual_applied = min(pay_amt, total_due_all)
                remaining_after_cash = max(0.0, total_due_all - actual_applied)
                actual_tds = min(remaining_after_cash, tds_amt)
                
                remaining_funds = pay_amt - actual_applied if pay_amt > total_due_all else 0.0

                if "Opening Balance" in sel_apply:
                    ob_paid_now = actual_applied + actual_tds
                    if actual_applied > 0:
                        breakdown_text.append(f"Opening Balance ({ledger.fmt(actual_applied)})")
                    
                    if action_var.get() == 1:
                        write_off_amt = ob_due - (actual_applied + actual_tds)
                        ob_paid_now += write_off_amt
                        total_write_off = write_off_amt
                else:
                    inv_id, inv_num, due = unpaid_bills[sel_idx][0], unpaid_bills[sel_idx][1], unpaid_bills[sel_idx][2]
                    pay_this = actual_applied
                    
                    c.execute(f"SELECT amount_paid, balance_due, status FROM {table} WHERE id=? AND company_id=?", (inv_id, ledger.comp_id))
                    row_data = c.fetchone()
                    curr_paid, curr_due, curr_status = row_data[0], row_data[1], row_data[2]
                    
                    curr_woff = 0.0
                    if has_woff:
                        c.execute(f"SELECT written_off FROM {table} WHERE id=? AND company_id=?", (inv_id, ledger.comp_id))
                        curr_woff = c.fetchone()[0] or 0.0
                        
                    action_log["invoices_changed"].append((inv_id, curr_paid, curr_due, curr_status, curr_woff)) 
                    
                    write_off_amt = 0.0
                    if action_var.get() == 1:
                        write_off_amt = due - (pay_this + actual_tds)
                        
                    new_paid = (curr_paid or 0) + pay_this + actual_tds
                    new_due = max(0, curr_due - (pay_this + actual_tds + write_off_amt))
                    new_status = "Paid" if new_due <= 0.01 else "Partial"
                    new_woff = curr_woff + write_off_amt
                    total_write_off = write_off_amt
                    
                    if has_woff: c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, new_woff, inv_id, ledger.comp_id))
                    else: c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, inv_id, ledger.comp_id))
                    
                    if pay_this > 0:
                        ref_entry = f"{inv_num} ({ledger.fmt(pay_this)})"
                        breakdown_text.append(ref_entry)

            pocket = "advance_in" if pay_type == "receive" else "advance_out"

            if is_wallet:
                adv_change = -actual_applied 
                remaining_funds = 0.0
            else:
                adv_change = remaining_funds

            if ob_paid_now > 0:
                safe_update_advance(c, ledger.cust_db_id, ob_paid_now, "ob_paid")

            if adv_change != 0:
                safe_update_advance(c, ledger.cust_db_id, adv_change, pocket)

            final_ref_string = " | ".join(breakdown_text)
            if total_write_off > 0:
                final_ref_string += f" (+ {ledger.fmt(total_write_off)} Write-Off)"

            amt_sign = -1 if pay_type == "make" else 1
                
            # --- THE FIX: Inject party_id and TDS records into the database ---
            if actual_applied > 0:
                action_log["history_rows"].append((actual_applied * amt_sign, clean_mode, final_ref_string, notes_text or "Selected Payment", final_attach))
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (ledger.comp_id, ledger.party_name, ledger.cust_db_id, pay_type, p_date_var.get(), actual_applied * amt_sign, clean_mode, final_ref_string, notes_text or "Selected Payment", final_attach))
                action_log["pay_ids"].append(c.lastrowid)
                
            if actual_tds > 0:
                tds_ref_str = f"Opening Balance ({ledger.fmt(actual_tds)})" if "Opening Balance" in sel_apply else f"{inv_num} ({ledger.fmt(actual_tds)})"
                tds_lbl_note = "TDS Deducted by Customer" if pay_type == "receive" else "TDS Deducted from Vendor"
                action_log["history_rows"].append((actual_tds * amt_sign, "TDS Deduction", tds_ref_str, tds_lbl_note, ""))
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (ledger.comp_id, ledger.party_name, ledger.cust_db_id, pay_type, p_date_var.get(), actual_tds * amt_sign, "TDS Deduction", tds_ref_str, tds_lbl_note, ""))
                action_log["pay_ids"].append(c.lastrowid)
                
            if remaining_funds > 0 and not is_wallet:
                adv_lbl = "Advance Wallet"
                action_log["history_rows"].append((remaining_funds * amt_sign, clean_mode, adv_lbl, "Overpayment added to wallet credit.", final_attach))
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (ledger.comp_id, ledger.party_name, ledger.cust_db_id, pay_type, p_date_var.get(), remaining_funds * amt_sign, clean_mode, adv_lbl, "Overpayment added to wallet credit.", final_attach))
                action_log["pay_ids"].append(c.lastrowid)
            # -------------------------------------------------------------------------

            audit_act = "Payment In" if pay_type == "receive" else "Payment Out"
            det_parts = [f"Mode: {clean_mode}"]
            if final_ref_string:
                det_parts.append(f"Applied: {final_ref_string}")
            if actual_tds > 0:
                det_parts.append(f"TDS: @@CURR:{actual_tds}@@")
            if remaining_funds > 0 and not is_wallet:
                det_parts.append(f"To Advance Wallet: @@CURR:{remaining_funds}@@")
            if notes_text:
                det_parts.append(f"Note: {notes_text}")
            audit_det = " • ".join(det_parts)
            audit_amt = pay_amt + actual_tds

        ledger.undo_stack.append(action_log)
        ledger.redo_stack.clear() 

        conn.commit()
        conn.close()

        if audit_act:
            database.log_audit("Parties", audit_act, record_ref=ledger.party_name, details=audit_det, amount=audit_amt, company_id=ledger.comp_id)
        
        p_pop.destroy()
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data() 

    tk.Button(btn_f, text="Save Payment", font=("Segoe UI", 11, "bold"), bg=ledger.colors["accent_green"] if pay_type == "receive" else ledger.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save_payment).pack(fill="x", padx=30, pady=(15, 15))


def view_payment_history(ledger):
    h_pop = tk.Toplevel(ledger)
    h_pop.title(f"Payment History: {ledger.party_name}")
    
    # --- THE FIX: Perfect Screen Centering & Taskbar Protection ---
    w, h = 1150, 650
    h_pop.geometry(f"{w}x{h}")
    h_pop.configure(bg=ledger.colors["bg"])
    h_pop.grab_set()
    
    h_pop.update_idletasks()
    sw = h_pop.winfo_screenwidth()
    sh = h_pop.winfo_screenheight()
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    
    if y + h > sh - 80: 
        y = sh - h - 80
        
    h_pop.geometry(f"+{max(0, x)}+{max(0, y)}")
    # --------------------------------------------------------------
    
    try:
        # --- THE FIX: Route settings through Gatekeeper! ---
        raw_widths = database.get_ui_setting(f"hist_grid_cols_{ledger.comp_id}", "{}")
        ledger.app.hist_col_widths = json.loads(raw_widths) if raw_widths else {}
    except:
        if not hasattr(ledger.app, 'hist_col_widths'): ledger.app.hist_col_widths = {}

    def remove_focus(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
            h_pop.focus_set()

    header_f = tk.Frame(h_pop, bg=ledger.colors["bg"])
    header_f.pack(fill="x", padx=20, pady=(15, 5))
    tk.Label(header_f, text=f"📜 Payment History: {ledger.party_name}", font=("Segoe UI", 16, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["text"]).pack(side="left")

    filter_f = tk.Frame(h_pop, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    filter_f.pack(fill="x", padx=20, pady=(0, 15))
    inner_f = tk.Frame(filter_f, bg=ledger.colors["card"], pady=10, padx=10)
    inner_f.pack(fill="x")
    
    table_f = tk.Frame(h_pop, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    table_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    h_pop.bind("<ButtonPress-1>", remove_focus)
    header_f.bind("<ButtonPress-1>", remove_focus)
    filter_f.bind("<ButtonPress-1>", remove_focus)
    table_f.bind("<ButtonPress-1>", remove_focus)

    search_var = tk.StringVar()
    tk.Label(inner_f, text="🔍 Search:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text_sec"]).pack(side="left", padx=(5, 5))
    search_entry = tk.Entry(inner_f, textvariable=search_var, font=("Segoe UI", 10), width=25, bg=ledger.colors["bg"], fg=ledger.colors["text"], insertbackground=ledger.colors["text"], highlightbackground=ledger.colors["border"], highlightcolor=ledger.colors["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    search_entry.pack(side="left", ipady=3)
    
    btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 10, "bold"), bg=ledger.colors["card"], fg=ledger.colors["error"], relief="flat", cursor="hand2", command=lambda: search_var.set(""))
    btn_clear_search.pack(side="left", padx=(5, 10))

    period_container = tk.Frame(inner_f, bg=ledger.colors["card"])
    period_container.pack(side="right")

    type_filter_var = tk.StringVar(value="All Transactions")
    type_filter_cb = ttk.Combobox(period_container, textvariable=type_filter_var, values=["All Transactions", "Received (Cash In)", "Paid (Cash Out)"], state="readonly", width=18, style="Ledger.TCombobox")
    type_filter_cb.pack(side="left", padx=(0, 15))

    normal_period_f = tk.Frame(period_container, bg=ledger.colors["card"])
    
    filter_var = tk.StringVar(value="All Time")
    tk.Label(normal_period_f, text="Period:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text_sec"]).pack(side="left", padx=(0, 5))
    date_cb = ttk.Combobox(normal_period_f, textvariable=filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=12, font=("Segoe UI", 10), style="Ledger.TCombobox", cursor="hand2")
    date_cb.pack(side="left")

    custom_date_f = tk.Frame(period_container, bg=ledger.colors["card"])
    from_var = tk.StringVar(value="")
    to_var = tk.StringVar(value="")

    tk.Label(custom_date_f, text="📅 From:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text_sec"]).pack(side="left", padx=(0, 5))
    from_f = tk.Frame(custom_date_f, bg=ledger.colors["bg"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    from_f.pack(side="left")
    tk.Entry(from_f, textvariable=from_var, font=("Segoe UI", 10), width=10, bg=ledger.colors["bg"], fg=ledger.colors["text"], bd=0, insertbackground=ledger.colors["text"]).pack(side="left", ipady=4, padx=5)
    from_btn = tk.Button(from_f, text="▼", bg=ledger.colors["card"], fg=ledger.colors["text"], relief="flat", cursor="hand2")
    from_btn.pack(side="left", ipadx=4, ipady=3)
    from_btn.config(command=lambda b=from_btn: NativeCalendar(ledger, from_var, anchor_widget=b))

    tk.Label(custom_date_f, text="To:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text_sec"]).pack(side="left", padx=(10, 5))
    to_f = tk.Frame(custom_date_f, bg=ledger.colors["bg"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    to_f.pack(side="left")
    tk.Entry(to_f, textvariable=to_var, font=("Segoe UI", 10), width=10, bg=ledger.colors["bg"], fg=ledger.colors["text"], bd=0, insertbackground=ledger.colors["text"]).pack(side="left", ipady=4, padx=5)
    to_btn = tk.Button(to_f, text="▼", bg=ledger.colors["card"], fg=ledger.colors["text"], relief="flat", cursor="hand2")
    to_btn.pack(side="left", ipadx=4, ipady=3)
    # --- THE FIX: Passed the from_var into the calendar as the ref_date_var to trigger the yellow highlight! ---
    to_btn.config(command=lambda b=to_btn: NativeCalendar(ledger, to_var, anchor_widget=b, ref_date_var=from_var))

    def close_custom():
        filter_var.set("All Time")
        toggle_custom_date()

    tk.Button(custom_date_f, text="✖", font=("Arial", 9, "bold"), bg=ledger.colors["error"], fg="#ffffff", relief="flat", cursor="hand2", command=close_custom).pack(side="left", padx=(10, 0))

    def toggle_custom_date(*args):
        if filter_var.get() == "Custom Range":
            normal_period_f.pack_forget()
            from_var.set("")
            to_var.set("")
            custom_date_f.pack(side="left")
        else:
            custom_date_f.pack_forget()
            normal_period_f.pack(side="left")
        load_history()

    date_cb.bind("<<ComboboxSelected>>", toggle_custom_date)
    
    normal_period_f.pack(side="left")
    custom_date_f.pack_forget()
    
    style = ttk.Style(h_pop)
    style.theme_use("default") 
    def fixed_map(option):
        return [elm for elm in style.map("History.Treeview", query_opt=option) if elm[:2] != ("!disabled", "!selected")]
        
    style.configure("History.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=ledger.colors["header"], foreground=ledger.colors["text"], borderwidth=1, bordercolor=ledger.colors["border"], relief="solid")

    style.configure("Hist.Vertical.TScrollbar", background=ledger.colors["text_sec"], troughcolor=ledger.colors["bg"], bordercolor=ledger.colors["bg"], arrowcolor=ledger.colors["text"], relief="flat")
    style.configure("Hist.Horizontal.TScrollbar", background=ledger.colors["text_sec"], troughcolor=ledger.colors["bg"], bordercolor=ledger.colors["bg"], arrowcolor=ledger.colors["text"], relief="flat")
    style.map("Hist.Vertical.TScrollbar", background=[("active", ledger.colors["accent_blue"])])
    style.map("Hist.Horizontal.TScrollbar", background=[("active", ledger.colors["accent_blue"])])

    h_scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="Hist.Vertical.TScrollbar")
    h_scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="Hist.Horizontal.TScrollbar")
    
    style.configure("History.Treeview", font=("Segoe UI", 10), rowheight=35, background=ledger.colors["bg"], fieldbackground=ledger.colors["bg"], foreground=ledger.colors["text"], borderwidth=0)
    style.map("History.Treeview", background=[("selected", ledger.colors["border"])], foreground=[("selected", ledger.colors["text"])])

    h_tree = ttk.Treeview(table_f, columns=("date", "type", "mode", "ref", "notes", "amount", "action", "ghost"), show="headings", height=12, yscrollcommand=h_scroll_y.set, xscrollcommand=h_scroll_x.set, style="History.Treeview")
    
    h_scroll_y.config(command=h_tree.yview)
    h_scroll_x.config(command=h_tree.xview)
    
    h_scroll_y.pack(side="right", fill="y")
    h_scroll_x.pack(side="bottom", fill="x")
    h_tree.pack(fill="both", expand=True, padx=2, pady=2)

    h_tree.heading("date", text="DATE", anchor="center")
    h_tree.heading("type", text="TYPE", anchor="center")
    h_tree.heading("mode", text="PAYMENT MODE", anchor="center")
    h_tree.heading("ref", text="APPLIED TO", anchor="w")
    h_tree.heading("notes", text="NOTES", anchor="w") 
    h_tree.heading("amount", text="AMOUNT", anchor="e")
    h_tree.heading("action", text="PROOF", anchor="center")
    h_tree.heading("ghost", text="")
    
    h_tree.column("date", width=ledger.app.hist_col_widths.get("date", 100), minwidth=60, anchor="center", stretch=False)
    h_tree.column("type", width=ledger.app.hist_col_widths.get("type", 110), minwidth=70, anchor="center", stretch=False)
    h_tree.column("mode", width=ledger.app.hist_col_widths.get("mode", 140), minwidth=90, anchor="center", stretch=False)
    h_tree.column("ref", width=ledger.app.hist_col_widths.get("ref", 250), minwidth=150, anchor="w", stretch=False) 
    h_tree.column("notes", width=ledger.app.hist_col_widths.get("notes", 200), minwidth=100, anchor="w", stretch=False) 
    h_tree.column("amount", width=ledger.app.hist_col_widths.get("amount", 130), minwidth=80, anchor="e", stretch=False) 
    h_tree.column("action", width=ledger.app.hist_col_widths.get("action", 120), minwidth=80, anchor="center", stretch=False) 
    h_tree.column("ghost", width=10, minwidth=10, stretch=True)

    h_tree.tag_configure("stripe_even", background=ledger.colors["stripe_even"], foreground=ledger.colors["text"])
    h_tree.tag_configure("stripe_odd", background=ledger.colors["stripe_odd"], foreground=ledger.colors["text"])
    
    h_tree.tag_configure("green_text", foreground=ledger.colors["accent_green"], font=("Segoe UI", 10, "bold"))
    h_tree.tag_configure("red_text", foreground=ledger.colors["error"], font=("Segoe UI", 10, "bold"))

    def save_hist_widths():
        for c_name in ("date", "type", "mode", "ref", "notes", "amount", "action"):
            # MATHEMATICAL CLAMP: Prevent 0-width crashes
            ledger.app.hist_col_widths[c_name] = max(30, h_tree.column(c_name, "width"))
        try:
            database.save_ui_setting(f"hist_grid_cols_{ledger.comp_id}", json.dumps(ledger.app.hist_col_widths))
        except: pass

    def on_hist_sep_drag(event):
        if h_tree.identify_region(event.x, event.y) == "separator":
            h_pop.after(50, save_hist_widths)

    h_tree.bind("<B1-Motion>", on_hist_sep_drag, add="+")
    # --- THE FIX: Unconditionally save widths on mouse release! ---
    h_tree.bind("<ButtonRelease-1>", lambda e: h_pop.after(50, save_hist_widths), add="+")
        
    def fast_scroll_hist(event, direction):
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y": 
            h_tree.yview_moveto(h_tree.yview()[0] + (delta * 0.008))
        else: 
            h_tree.xview_moveto(h_tree.xview()[0] + (delta * 0.02))
        
    h_tree.bind("<MouseWheel>", lambda e: fast_scroll_hist(e, "y"))
    h_tree.bind("<Shift-MouseWheel>", lambda e: fast_scroll_hist(e, "x"))

    def on_h_click(event):
        region = h_tree.identify("region", event.x, event.y)
        if region == "cell":
            col = h_tree.identify_column(event.x)
            if col == "#7":
                iid = h_tree.identify_row(event.y)
                if iid and "empty" not in h_tree.item(iid, "tags"):
                    row_vals = h_tree.item(iid, "values")
                    row_tags = h_tree.item(iid, "tags")
                    action_text = row_vals[6]
                    
                    if action_text == "—": return
                    
                    attach_path = row_tags[2] if len(row_tags) > 2 else "NONE"
                    
                    if "View" in action_text:
                        import webbrowser
                        if attach_path != "NONE" and os.path.exists(attach_path):
                            try: os.startfile(attach_path)
                            except: webbrowser.open(attach_path)
                        else:
                            messagebox.showerror("Error", "File could not be located on this device.", parent=h_pop)
                    else:
                        from tkinter import filedialog
                        import shutil
                        import time
                        
                        path = filedialog.askopenfilename(parent=h_pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
                        if path:
                            from views.invoice_parts.helpers import get_vault_path
                            p_type_label = row_vals[1]
                            folder_name = "purchase_payment_receipts" if "Paid" in p_type_label else "invoice_payment_receipts"
                            safe_dir = get_vault_path(ROOT_DIR, ledger.comp_id, ledger.party_name, folder_name, ledger.cust_db_id)
                            
                            import re
                            ext = os.path.splitext(path)[1] or ".png"
                            ref_str = row_vals[3]
                            if "Advance" in ref_str: prefix = "advance"
                            elif "(" in ref_str and " | " not in ref_str:
                                bill_no = ref_str.split("(")[0].strip()
                                prefix = f"payment_{re.sub(r'[\\/*?:\"<>|]', '_', bill_no)}"
                            else: prefix = "bulk_payment"
                            
                            final_attach = os.path.join(safe_dir, f"{prefix}_{int(time.time()*1000)}{ext}")
                            try: shutil.copy2(path, final_attach)
                            except: final_attach = path
                            
                            try:
                                conn = database.get_connection()
                                c = conn.cursor()
                                c.execute("UPDATE party_payments SET attachment_path=? WHERE id=?", (final_attach, iid))
                                conn.commit()
                                conn.close()
                                database.log_audit("Parties", "Proof Attached", record_ref=ledger.party_name, details=f"Attached payment proof for {ref_str} ({row_vals[0]})", amount=0.0, company_id=ledger.comp_id)
                                load_history()
                            except Exception as e:
                                messagebox.showerror("Save Error", str(e), parent=h_pop)

    h_pop.tooltip = None
    h_pop.current_tooltip_id = None

    def hide_tooltip():
        if getattr(h_pop, "tooltip", None):
            h_pop.tooltip.destroy()
            h_pop.tooltip = None
            h_pop.current_tooltip_id = None

    def on_h_motion(e):
        region = h_tree.identify("region", e.x, e.y)
        
        if region == "cell":
            col = h_tree.identify_column(e.x)
            iid = h_tree.identify_row(e.y)
            
            # 1. Action Button Cursor Logic
            if col == "#7" and iid and "empty" not in h_tree.item(iid, "tags"):
                h_tree.config(cursor="hand2")
            else:
                h_tree.config(cursor="")
                
            # 2. Yellow Tooltip Logic for Applied To (#4) and Notes (#5)
            if col in ("#4", "#5") and iid and "empty" not in h_tree.item(iid, "tags"):
                val_idx = 3 if col == "#4" else 4
                text = str(h_tree.item(iid, "values")[val_idx]).strip()
                
                if text and text != "—":
                    if h_pop.current_tooltip_id != f"{iid}_{col}":
                        hide_tooltip()
                        h_pop.current_tooltip_id = f"{iid}_{col}"
                        h_pop.tooltip = tk.Toplevel(h_tree)
                        h_pop.tooltip.wm_overrideredirect(True)
                        h_pop.tooltip.geometry(f"+{e.x_root + 15}+{e.y_root + 15}")
                        
                        lbl = tk.Label(h_pop.tooltip, text=text, bg="#fef08a", fg="#0f172a", font=("Segoe UI", 10), justify="left", relief="solid", borderwidth=1, padx=6, pady=4, wraplength=450)
                        lbl.pack()
                    return
        else:
            h_tree.config(cursor="")

        hide_tooltip()

    h_tree.bind("<Motion>", on_h_motion)
    h_tree.bind("<Leave>", lambda e: hide_tooltip(), add="+")
    h_tree.bind("<MouseWheel>", lambda e: hide_tooltip(), add="+")
    h_tree.bind("<ButtonRelease-1>", lambda e: [h_pop.after(50, save_hist_widths), on_h_click(e)], add="+")

    def load_history(*args):
        for i in h_tree.get_children(): h_tree.delete(i)
        
        from datetime import date, timedelta
        
        q = search_var.get().strip().lower()
        f_type = type_filter_var.get()
        val = filter_var.get()
        
        today = date.today()
        from_dt, to_dt = None, None

        if val == "Today":
            from_dt = datetime.combine(today, datetime.min.time())
            to_dt = datetime.combine(today, datetime.max.time())
        elif val == "This Week":
            start = today - timedelta(days=today.weekday())
            from_dt = datetime.combine(start, datetime.min.time())
            to_dt = datetime.combine(today, datetime.max.time())
        elif val == "This Month":
            start = today.replace(day=1)
            from_dt = datetime.combine(start, datetime.min.time())
            to_dt = datetime.combine(today, datetime.max.time())
        elif val == "Last Month":
            first_this = today.replace(day=1)
            last_month_end = first_this - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            from_dt = datetime.combine(last_month_start, datetime.min.time())
            to_dt = datetime.combine(last_month_end, datetime.max.time())
        elif val == "Custom Range":
            from_str = from_var.get().strip()
            to_str = to_var.get().strip()
            if from_str:
                try: from_dt = datetime.strptime(from_str, ledger.date_fmt_code)
                except: pass
            if to_str:
                try: 
                    to_dt = datetime.strptime(to_str, ledger.date_fmt_code)
                    to_dt = datetime.combine(to_dt, datetime.max.time())
                except: pass

        conn = database.get_connection()
        c = conn.cursor()
        try:
            try: c.execute("ALTER TABLE party_payments ADD COLUMN attachment_path TEXT")
            except: pass
            
            c.execute("SELECT id, pay_date, pay_type, mode, ref, amount, notes, attachment_path FROM party_payments WHERE company_id=? AND party_name=? ORDER BY id DESC", (ledger.comp_id, ledger.party_name))
            idx = 0
            for r in c.fetchall():
                log_id = r[0]
                p_date = r[1]
                p_type = r[2]
                mode = r[3]
                ref = r[4]
                raw_amt = float(r[5] or 0.0)
                notes_str = r[6] if r[6] else ""
                attach_path = r[7] if len(r) > 7 and r[7] else ""

                dt = datetime.min
                for fmt in (ledger.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(str(p_date).strip()[:10], fmt)
                        break
                    except: pass
                
                if dt != datetime.min:
                    if from_dt and dt < from_dt: continue
                    if to_dt and dt > to_dt: continue

                type_lbl = "Received (In)" if p_type == "receive" else "Paid (Out)"
                
                if f_type == "Received (Cash In)" and p_type != "receive": continue
                if f_type == "Paid (Cash Out)" and p_type == "receive": continue
                
                clean_mode = str(mode).replace(" (In)", "").replace(" (Out)", "").strip() if mode else ""
                
                if q and q not in str(raw_amt).lower() and q not in str(p_date).lower() and q not in str(ref).lower() and q not in str(notes_str).lower() and q not in clean_mode.lower(): continue

                tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
                
                if raw_amt < 0:
                    amt_str = f"- {ledger.fmt(abs(raw_amt))}"
                    color_tag = "red_text"
                else:
                    amt_str = f"+ {ledger.fmt(raw_amt)}"
                    color_tag = "green_text"
                    
                if ref:
                    import re
                    def replace_amt(match):
                        try:
                            val = float(match.group(1))
                            return f"({ledger.fmt(val)})"
                        except:
                            return match.group(0)
                    ref = re.sub(r'\(([^)]+)\)', replace_amt, ref)
                
                if attach_path and os.path.exists(attach_path):
                    action_txt = "👁 View Proof"
                elif clean_mode == "System Reversal" or clean_mode == "Write-Off" or clean_mode == "Adjustment" or clean_mode == "System Adjustment":
                    action_txt = "—"
                else:
                    action_txt = "📎 Attach Proof"

                h_tree.insert("", "end", iid=str(log_id), values=(ledger.fmt_date(p_date), type_lbl, clean_mode, ref, notes_str, amt_str, action_txt, ""), tags=(tag, color_tag, attach_path or "NONE"))
                idx += 1
                
            for j in range(idx, 20): 
                tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
                h_tree.insert("", "end", values=("", "", "", "", "", "", "", ""), tags=(tag, "empty"))

        except Exception as e: 
            print("History Load Error:", e)
        conn.close()

    type_filter_var.trace_add("write", lambda *a: load_history())
    search_var.trace_add("write", lambda *a: load_history())
    from_var.trace_add("write", lambda *a: load_history())
    to_var.trace_add("write", lambda *a: load_history())
    
    # --- THE FIX: Expose the refresh function to the parent Ledger ---
    ledger.refresh_history_ui = load_history
    
    def on_close(e):
        if e.widget == h_pop:
            ledger.refresh_history_ui = None
    h_pop.bind("<Destroy>", on_close, add="+")
    # -----------------------------------------------------------------
    
    load_history()

    # --- THE FIX: The Core Settlement / Contra Engine ---
def open_contra_settlement_popup(ledger):
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id, invoice_number, balance_due, invoice_date FROM invoices WHERE customer_name=? AND company_id=? AND balance_due > 0 AND is_deleted=0 AND status != 'Draft' ORDER BY invoice_date ASC", (ledger.party_name, ledger.comp_id))
    unpaid_invs = c.fetchall()
    c.execute("SELECT id, bill_number, balance_due, purchase_date FROM purchases WHERE vendor_name=? AND company_id=? AND balance_due > 0 AND is_deleted=0 AND is_draft=0 ORDER BY purchase_date ASC", (ledger.party_name, ledger.comp_id))
    unpaid_purchs = c.fetchall()
    conn.close()

    if not unpaid_invs or not unpaid_purchs:
        messagebox.showinfo("Not Available", "You need at least one unpaid Invoice and one unpaid Purchase Bill to perform a settlement.", parent=ledger)
        return

    c_pop = tk.Toplevel(ledger)
    c_pop.title("Settle & Offset Bills (Contra Entry)")
    pop_w, pop_h = 1000, 650
    c_pop.geometry(f"{pop_w}x{pop_h}")
    c_pop.configure(bg=ledger.colors["bg"])
    c_pop.grab_set()

    c_pop.update_idletasks()
    x = ledger.winfo_rootx() + (ledger.winfo_width() // 2) - (pop_w // 2)
    y = ledger.winfo_rooty() + (ledger.winfo_height() // 2) - (pop_h // 2)
    c_pop.geometry(f"+{max(0, x)}+{max(0, y)}")

    tk.Label(c_pop, text="⚖️ Settle & Offset Bills", font=("Segoe UI", 16, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["text"]).pack(pady=(15, 5))
    tk.Label(c_pop, text="Select Invoices and Purchases to cancel against each other without moving real cash.", font=("Segoe UI", 10), bg=ledger.colors["bg"], fg=ledger.colors["text_sec"]).pack(pady=(0, 15))

    split_f = tk.Frame(c_pop, bg=ledger.colors["bg"])
    split_f.pack(fill="both", expand=True, padx=20)

    inv_f = tk.Frame(split_f, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    inv_f.pack(side="left", fill="both", expand=True, padx=(0, 5))
    tk.Label(inv_f, text="📦 Invoices (Receivables)", font=("Segoe UI", 11, "bold"), bg=ledger.colors["header"], fg=ledger.colors["text"], pady=8).pack(fill="x")

    purch_f = tk.Frame(split_f, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    purch_f.pack(side="right", fill="both", expand=True, padx=(5, 0))
    tk.Label(purch_f, text="🛒 Purchases (Payables)", font=("Segoe UI", 11, "bold"), bg=ledger.colors["header"], fg=ledger.colors["text"], pady=8).pack(fill="x")

    style = ttk.Style(c_pop)
    style.theme_use("default")
    
    cols = ("check", "bill", "date", "due")
    inv_tree = ttk.Treeview(inv_f, columns=cols, show="headings", height=10, style="Ledger.Treeview")
    purch_tree = ttk.Treeview(purch_f, columns=cols, show="headings", height=10, style="Ledger.Treeview")

    for tree in (inv_tree, purch_tree):
        tree.heading("check", text="[ ]")
        tree.heading("bill", text="BILL NO", anchor="w")
        tree.heading("date", text="DATE", anchor="center")
        tree.heading("due", text="DUE", anchor="e")
        tree.column("check", width=40, anchor="center", stretch=False)
        tree.column("bill", width=120, anchor="w", stretch=True)
        tree.column("date", width=90, anchor="center", stretch=False)
        tree.column("due", width=100, anchor="e", stretch=False)
        tree.pack(fill="both", expand=True, padx=2, pady=2)
        tree.tag_configure("stripe_even", background=ledger.colors["stripe_even"], foreground=ledger.colors["text"])
        tree.tag_configure("stripe_odd", background=ledger.colors["stripe_odd"], foreground=ledger.colors["text"])

    inv_targets = [(str(r[0]), r[1], r[2], ledger.fmt_date(r[3])) for r in unpaid_invs]
    purch_targets = [(str(r[0]), r[1], r[2], ledger.fmt_date(r[3])) for r in unpaid_purchs]

    sel_invs = set()
    sel_purchs = set()

    for idx, t in enumerate(inv_targets):
        tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
        inv_tree.insert("", "end", iid=t[0], values=("[ ]", t[1], t[3], ledger.fmt(t[2])), tags=(tag,))
    for idx, t in enumerate(purch_targets):
        tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
        purch_tree.insert("", "end", iid=t[0], values=("[ ]", t[1], t[3], ledger.fmt(t[2])), tags=(tag,))

    calc_f = tk.Frame(c_pop, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1)
    calc_f.pack(fill="x", padx=20, pady=15)

    lbl_inv_sum = tk.Label(calc_f, text="Selected Invoices: 0.00", font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text"], width=30, anchor="w")
    lbl_inv_sum.grid(row=0, column=0, padx=15, pady=(15, 5))

    lbl_purch_sum = tk.Label(calc_f, text="Selected Purchases: 0.00", font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text"], width=30, anchor="w")
    lbl_purch_sum.grid(row=1, column=0, padx=15, pady=(0, 15))

    tk.Frame(calc_f, width=1, bg=ledger.colors["border"]).grid(row=0, column=1, rowspan=2, sticky="ns", pady=10)

    lbl_offset = tk.Label(calc_f, text="Amount to Cancel Out: 0.00", font=("Segoe UI", 12, "bold"), bg=ledger.colors["card"], fg=ledger.colors["accent_green"], width=35, anchor="e")
    lbl_offset.grid(row=0, column=2, padx=15, pady=(15, 5))

    lbl_rem = tk.Label(calc_f, text="Remaining: 0.00", font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=ledger.colors["text_sec"], width=35, anchor="e")
    lbl_rem.grid(row=1, column=2, padx=15, pady=(0, 15))

    opt_f = tk.Frame(c_pop, bg=ledger.colors["bg"])
    opt_f.pack(fill="x", padx=20, pady=(0, 15))
    tk.Label(opt_f, text="Date:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["text_sec"]).pack(side="left")
    
    d_var = tk.StringVar(value=datetime.now().strftime(ledger.date_fmt_code))
    d_btn = tk.Button(opt_f, textvariable=d_var, bg=ledger.colors["card"], fg=ledger.colors["text"], font=("Segoe UI", 10), relief="solid", bd=1, cursor="hand2", width=12)
    d_btn.pack(side="left", padx=(5, 15))
    d_btn.config(command=lambda: NativeCalendar(ledger, d_var, anchor_widget=d_btn))

    tk.Label(opt_f, text="Notes:", font=("Segoe UI", 9, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["text_sec"]).pack(side="left")
    notes_var = tk.StringVar(value="Offset against Purchases/Invoices")
    tk.Entry(opt_f, textvariable=notes_var, font=("Segoe UI", 10), width=40, bg=ledger.colors["card"], fg=ledger.colors["text"], insertbackground=ledger.colors["text"], highlightbackground=ledger.colors["border"], highlightthickness=1, bd=0, relief="flat").pack(side="left", padx=5, ipady=4)

    btn_confirm = tk.Button(opt_f, text="Confirm Settlement", font=("Segoe UI", 10, "bold"), bg=ledger.colors["border"], fg=ledger.colors["text_sec"], relief="flat", padx=15, pady=5, state="disabled")
    btn_confirm.pack(side="right")

    def recalculate(*args):
        inv_sum = sum(t[2] for t in inv_targets if t[0] in sel_invs)
        purch_sum = sum(t[2] for t in purch_targets if t[0] in sel_purchs)

        offset_amt = min(inv_sum, purch_sum)

        lbl_inv_sum.config(text=f"Selected Invoices: {ledger.fmt(inv_sum)}")
        lbl_purch_sum.config(text=f"Selected Purchases: {ledger.fmt(purch_sum)}")
        lbl_offset.config(text=f"Amount to Cancel Out: {ledger.fmt(offset_amt)}")

        if inv_sum > purch_sum:
            lbl_rem.config(text=f"Remaining Receivable: {ledger.fmt(inv_sum - purch_sum)}", fg=ledger.colors["error"])
        elif purch_sum > inv_sum:
            lbl_rem.config(text=f"Remaining Payable: {ledger.fmt(purch_sum - inv_sum)}", fg=ledger.colors["accent_blue"])
        else:
            lbl_rem.config(text="Perfect Match (Fully Settled)", fg=ledger.colors["accent_green"])
        
        if offset_amt > 0: btn_confirm.config(state="normal", bg=ledger.colors["accent_blue"], fg="#ffffff", cursor="hand2")
        else: btn_confirm.config(state="disabled", bg=ledger.colors["border"], fg=ledger.colors["text_sec"], cursor="arrow")

    def toggle_row(tree, sel_set):
        def handler(e):
            region = tree.identify("region", e.x, e.y)
            if region == "cell":
                iid = tree.identify_row(e.y)
                if iid:
                    if iid in sel_set:
                        sel_set.remove(iid)
                        v = list(tree.item(iid, "values"))
                        v[0] = "[ ]"
                        tree.item(iid, values=v)
                    else:
                        sel_set.add(iid)
                        v = list(tree.item(iid, "values"))
                        v[0] = "[✓]"
                        tree.item(iid, values=v)
                    recalculate()
        return handler

    inv_tree.bind("<ButtonRelease-1>", toggle_row(inv_tree, sel_invs))
    purch_tree.bind("<ButtonRelease-1>", toggle_row(purch_tree, sel_purchs))

    def confirm():
        inv_sum = sum(t[2] for t in inv_targets if t[0] in sel_invs)
        purch_sum = sum(t[2] for t in purch_targets if t[0] in sel_purchs)
        offset_amt = min(inv_sum, purch_sum)

        if offset_amt <= 0: return

        if not messagebox.askyesno("Confirm Settlement", f"This will permanently offset {ledger.fmt(offset_amt)} of selected Invoices against {ledger.fmt(offset_amt)} of Purchases.\n\nNo real cash will be moved. Are you sure?", parent=c_pop):
            return

        conn = database.get_connection()
        c = conn.cursor()

        c.execute("PRAGMA table_info(invoices)")
        has_woff_inv = "written_off" in [col[1] for col in c.fetchall()]
        c.execute("PRAGMA table_info(purchases)")
        has_woff_purch = "written_off" in [col[1] for col in c.fetchall()]

        action_log = {"pay_type": "contra", "inv_changes": [], "purch_changes": [], "pay_ids": [], "history_rows": [], "offset_amt": offset_amt}

        # 1. Process Invoices (Receive side)
        rem_inv_offset = offset_amt
        inv_ref_parts = []
        sel_inv_objs = [t for t in inv_targets if t[0] in sel_invs]
        
        for t in sel_inv_objs:
            if rem_inv_offset <= 0: break
            inv_id_int = int(t[0])
            apply_amt = min(t[2], rem_inv_offset)
            
            c.execute("SELECT amount_paid, balance_due, status FROM invoices WHERE id=? AND company_id=?", (inv_id_int, ledger.comp_id))
            r = c.fetchone()
            curr_paid, curr_due, curr_status = r[0], r[1], r[2]
            curr_woff = 0.0
            
            if has_woff_inv:
                c.execute("SELECT written_off FROM invoices WHERE id=? AND company_id=?", (inv_id_int, ledger.comp_id))
                curr_woff = c.fetchone()[0] or 0.0
            
            action_log["inv_changes"].append((inv_id_int, curr_paid, curr_due, curr_status, curr_woff))

            new_paid = (curr_paid or 0) + apply_amt
            new_due = max(0, curr_due - apply_amt)
            new_status = "Paid" if new_due <= 0.01 else "Partial"

            if has_woff_inv: c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, curr_woff, inv_id_int, ledger.comp_id))
            else: c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, inv_id_int, ledger.comp_id))

            rem_inv_offset -= apply_amt
            inv_ref_parts.append(f"{t[1]} ({ledger.fmt(apply_amt)})")

        # 2. Process Purchases (Make side)
        rem_purch_offset = offset_amt
        purch_ref_parts = []
        sel_purch_objs = [t for t in purch_targets if t[0] in sel_purchs]
        
        for t in sel_purch_objs:
            if rem_purch_offset <= 0: break
            purch_id_int = int(t[0])
            apply_amt = min(t[2], rem_purch_offset)

            c.execute("SELECT amount_paid, balance_due, status FROM purchases WHERE id=? AND company_id=?", (purch_id_int, ledger.comp_id))
            r = c.fetchone()
            curr_paid, curr_due, curr_status = r[0], r[1], r[2]
            curr_woff = 0.0
            
            if has_woff_purch:
                c.execute("SELECT written_off FROM purchases WHERE id=? AND company_id=?", (purch_id_int, ledger.comp_id))
                curr_woff = c.fetchone()[0] or 0.0
            
            action_log["purch_changes"].append((purch_id_int, curr_paid, curr_due, curr_status, curr_woff))

            new_paid = (curr_paid or 0) + apply_amt
            new_due = max(0, curr_due - apply_amt)
            new_status = "Paid" if new_due <= 0.01 else "Partial"

            if has_woff_purch: c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, curr_woff, purch_id_int, ledger.comp_id))
            else: c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (new_paid, new_due, new_status, purch_id_int, ledger.comp_id))

            rem_purch_offset -= apply_amt
            purch_ref_parts.append(f"{t[1]} ({ledger.fmt(apply_amt)})")

        # 3. Create Logs
        pay_date = d_var.get()
        mode = "Contra / Bill Offset"
        notes = notes_var.get().strip()

        # Receive Log (Invoices)
        c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (ledger.comp_id, ledger.party_name, ledger.cust_db_id, "receive", pay_date, offset_amt, mode, " | ".join(inv_ref_parts), notes, ""))
        action_log["pay_ids"].append(c.lastrowid)
        action_log["history_rows"].append(("receive", pay_date, offset_amt, mode, " | ".join(inv_ref_parts), notes))

        # Make Log (Purchases)
        c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (ledger.comp_id, ledger.party_name, ledger.cust_db_id, "make", pay_date, offset_amt, mode, " | ".join(purch_ref_parts), notes, ""))
        action_log["pay_ids"].append(c.lastrowid)
        action_log["history_rows"].append(("make", pay_date, offset_amt, mode, " | ".join(purch_ref_parts), notes))

        conn.commit()
        conn.close()

        ledger.undo_stack.append(action_log)
        ledger.redo_stack.clear()

        database.log_audit("Parties", "Bill Settlement (Contra)", record_ref=ledger.party_name, details=f"Offset @@CURR:{offset_amt}@@ between Invoices and Purchases. Notes: {notes}", amount=offset_amt, company_id=ledger.comp_id)

        c_pop.destroy()
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()

    btn_confirm.config(command=confirm)
# -------------------------------------------------------------