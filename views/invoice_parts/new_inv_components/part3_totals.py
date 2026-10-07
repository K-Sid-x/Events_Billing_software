import tkinter as tk
from tkinter import ttk, messagebox
import json
import re
import os
import sys
import ast
from datetime import datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path: 
    sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, enable_copy_paste, smart_date_formatter, get_date_format_str, unpack_place_data

def extract_address(addr_str):
    if not addr_str: return ""
    s_val = str(addr_str).strip()
    if s_val.startswith("{"):
        try:
            d = json.loads(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
        try:
            d = ast.literal_eval(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
        match = re.search(r'(?:"|\')address(?:"|\')\s*:\s*(?:"|\')(.*?)(?:"|\')\s*(?:,|})', s_val)
        if match: return match.group(1)
    return s_val

def build_part_3(parent, state):
    theme = state.theme  
    
    if not hasattr(state, 'page_num_var'):
        state.page_num_var = tk.StringVar(value="1")
    if not hasattr(state, 'selected_sig_var'):
        state.selected_sig_var = tk.StringVar()
    if not hasattr(state, 'inc_terms_var'):
        state.inc_terms_var = tk.IntVar(value=1)

    if not hasattr(state, 'tax_type_var'):
        state.tax_type_var = tk.StringVar()
        def sync_tax(*args):
            if "Local" in state.tax_type_var.get(): state.gst_type.set("GST")
            elif "Inter" in state.tax_type_var.get(): state.gst_type.set("IGST")
            state.calculate_totals()
        state.tax_type_var.trace_add("write", sync_tax)
        
    state.cgst_rate_var.trace_add("write", lambda *a: state.calculate_totals())
    state.sgst_rate_var.trace_add("write", lambda *a: state.calculate_totals())
    state.igst_rate_var.trace_add("write", lambda *a: state.calculate_totals())

    calc_frame = tk.Frame(parent, bg=theme["card"], padx=20, pady=20, highlightbackground=theme["border"], highlightthickness=1)
    calc_frame.pack(fill="x", padx=20, pady=10)

    left_ctrl = tk.Frame(calc_frame, bg=theme["card"])
    left_ctrl.pack(side="left", fill="y")
    
    curr_sym = "₹"
    try:
        if "(" in state.curr_fmt and ")" in state.curr_fmt:
            raw_inside = state.curr_fmt.split("(")[1].split(")")[0]
            curr_sym = raw_inside.strip().split(" ")[0] 
    except: pass
    
    extras_f = tk.Frame(left_ctrl, bg=theme["card"])
    extras_f.pack(anchor="w", pady=(0, 0), fill="x")

    tk.Checkbutton(extras_f, text="Apply Discount", variable=state.inc_discount_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], font=("Arial", 10, "bold"), anchor="w").grid(row=0, column=0, sticky="w", pady=2)
    
    disc_input_f = tk.Frame(extras_f, bg=theme["card"])
    tk.Entry(disc_input_f, textvariable=state.discount_val_var, font=("Arial", 10), width=10, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1).pack(side="left", ipady=2)
    ttk.Combobox(disc_input_f, textvariable=state.discount_type_var, values=["%", f"Flat ({curr_sym})"], state="readonly", width=10, style="Theme.TCombobox").pack(side="left", padx=(5, 0), ipady=2)

    if not hasattr(state, 'adv_date_var'): state.adv_date_var = tk.StringVar(value=datetime.now().strftime(get_date_format_str()))
    if not hasattr(state, 'adv_mode_var'): state.adv_mode_var = tk.StringVar(value="Cash")

    # --- THE FIX: Display Advance safely on Posted Invoices (Unlocked) ---
    if hasattr(state, "clone_id"):
        state.inc_adv_var.set(0)
        state.adv_val_var.set("")

    adv_cb = tk.Checkbutton(extras_f, text="Advance Received", variable=state.inc_adv_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], font=("Arial", 10, "bold"), anchor="w")
    adv_cb.grid(row=1, column=0, sticky="w", pady=2)
    
    adv_input_f = tk.Frame(extras_f, bg=theme["card"])
    tk.Label(adv_input_f, text=curr_sym, bg=theme["card"], fg=theme["sec"], font=("Arial", 10, "bold")).pack(side="left", padx=(0, 5))
    adv_ent = tk.Entry(adv_input_f, textvariable=state.adv_val_var, font=("Arial", 10), width=8, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    adv_ent.pack(side="left", ipady=2)
    
    from views.invoice_parts.calendar_widget import NativeCalendar
    tk.Label(adv_input_f, text=" On: ", bg=theme["card"], fg=theme["sec"], font=("Arial", 9, "bold")).pack(side="left")
    adv_dt_ent = tk.Entry(adv_input_f, textvariable=state.adv_date_var, font=("Arial", 10), width=10, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    adv_dt_ent.pack(side="left", ipady=2)
    btn_adv_cal = tk.Button(adv_input_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
    btn_adv_cal.pack(side="left", padx=2)
    btn_adv_cal.config(command=lambda b=btn_adv_cal: NativeCalendar(state.popup, state.adv_date_var, anchor_widget=b))
    
    tk.Label(adv_input_f, text=" Via: ", bg=theme["card"], fg=theme["sec"], font=("Arial", 9, "bold")).pack(side="left")
    adv_mode_cb = ttk.Combobox(adv_input_f, textvariable=state.adv_mode_var, values=["Cash", "UPI", "Google Pay", "PhonePe", "Bank Transfer", "Cheque", "Advance Wallet"], state="readonly", width=16, style="Theme.TCombobox")
    adv_mode_cb.pack(side="left", padx=(2, 0), ipady=2)
    # ----------------------------------------------------------------------
    
    def update_adv_modes(*args):
        c_name = state.cust_var.get().strip()
        comp_id = getattr(state.view.winfo_toplevel(), "active_company_id", 1)
        wall_bal = 0.0
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT address FROM customers WHERE name=? AND company_id=?", (c_name, comp_id))
            r = c.fetchone()
            conn.close()
            if r and r[0]:
                j = json.loads(r[0])
                wall_bal = float(j.get("advance_in", j.get("advance_wallet", 0.0)))
        except: pass
        
        modes = ["Cash", "UPI", "Google Pay", "PhonePe", "Bank Transfer", "Cheque"]
        
        # --- THE FIX: Only show Wallet if they actually have money ---
        if wall_bal > 0: 
            modes.append(f"Advance Wallet (₹ {wall_bal:.2f})")
            
        adv_mode_cb.config(values=modes)
        
        # Reset to Cash if they switch to a customer with no balance
        if "Wallet" in state.adv_mode_var.get() and wall_bal <= 0:
            state.adv_mode_var.set("Cash")
        # ------------------------------------------------------------
        
    state.cust_var.trace_add("write", update_adv_modes)
    adv_input_f.bind("<Enter>", update_adv_modes)

    def toggle_extras(*args):
        if state.inc_discount_var.get() == 1: disc_input_f.grid(row=0, column=1, sticky="w", padx=(15, 0))
        else: disc_input_f.grid_remove(); state.discount_val_var.set("")
        
        if state.inc_adv_var.get() == 1: adv_input_f.grid(row=1, column=1, sticky="w", padx=(15, 0))
        else: adv_input_f.grid_remove(); state.adv_val_var.set("")
        
        state.calculate_totals()
        
    state.inc_discount_var.trace_add("write", toggle_extras)
    state.inc_adv_var.trace_add("write", toggle_extras)
    state.discount_val_var.trace_add("write", lambda *a: state.calculate_totals())
    state.discount_type_var.trace_add("write", lambda *a: state.calculate_totals())
    state.adv_val_var.trace_add("write", lambda *a: state.calculate_totals())
    toggle_extras()
    
    tk.Frame(left_ctrl, height=1, bg=theme["border"]).pack(fill="x", pady=15)
    
    tk.Checkbutton(left_ctrl, text="Include Bank Details", variable=state.inc_bank_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], font=("Arial", 10, "bold")).pack(anchor="w")
    
    bank_opts = []
    for b in state.company_banks:
        ac_num = str(b.get('ac', ''))
        last4 = ac_num[-4:] if len(ac_num) >= 4 else ac_num
        alias = b.get('alias', b.get('name', 'Bank'))
        bank_opts.append(f"{alias} (**** {last4})")
        
    if not bank_opts: bank_opts = ["No Banks Setup in Settings"]
    
    cb_bank = ttk.Combobox(left_ctrl, textvariable=state.selected_bank_var, values=bank_opts, state="readonly", width=30, style="Theme.TCombobox")
    cb_bank.pack(anchor="w", pady=(5, 0))
    if bank_opts and bank_opts[0] != "No Banks Setup in Settings":
        cb_bank.current(0)
        
    tk.Checkbutton(left_ctrl, text="Include Terms & Conditions", variable=state.inc_terms_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 0))

    right_outer = tk.Frame(calc_frame, bg=theme["card"], width=380, height=200)
    right_outer.pack(side="right", fill="y", padx=5)
    right_outer.pack_propagate(False)

    # --- THE FIX: Apply the thick scrollbar style (inherits from new_invoice_dialog) ---
    right_scroll = ttk.Scrollbar(right_outer, orient="vertical", style="NewInv.Vertical.TScrollbar")
    # -----------------------------------------------------------------------------------
    right_scroll.pack(side="right", fill="y")

    right_canvas = tk.Canvas(right_outer, bg=theme["card"], highlightthickness=0, yscrollcommand=right_scroll.set)
    right_canvas.pack(side="left", fill="both", expand=True)
    right_scroll.config(command=right_canvas.yview)

    right_ctrl = tk.Frame(right_canvas, bg=theme["card"])
    right_canvas_window = right_canvas.create_window((0, 0), window=right_ctrl, anchor="nw")

    def _scroll_right(e):
        if hasattr(e, 'delta') and e.delta:
            right_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        elif hasattr(e, 'num'):
            if e.num == 4: right_canvas.yview_scroll(-1, "units")
            elif e.num == 5: right_canvas.yview_scroll(1, "units")
        return "break"
    
    right_canvas.bind("<MouseWheel>", _scroll_right)
    right_canvas.bind("<Button-4>", _scroll_right)
    right_canvas.bind("<Button-5>", _scroll_right)

    def bind_mousewheel(widget):
        if widget.winfo_class() == 'TCombobox': return
        widget.bind("<MouseWheel>", _scroll_right)
        widget.bind("<Button-4>", _scroll_right)
        widget.bind("<Button-5>", _scroll_right)
        for child in widget.winfo_children():
            bind_mousewheel(child)

    def _configure_canvas(e):
        right_canvas.itemconfig(right_canvas_window, width=e.width)
    right_canvas.bind("<Configure>", _configure_canvas)

    center_ctrl = tk.Frame(calc_frame, bg=theme["card"])
    center_ctrl.pack(side="left", expand=True, fill="both", padx=10)
    
    state.company_sigs = []
    if state.comp and len(state.comp) > 14 and state.comp[14]:
        try: state.company_sigs = json.loads(state.comp[14]).get("signatures", [])
        except: pass

    page_f = tk.Frame(center_ctrl, bg=theme["card"])
    page_f.pack(side="bottom", anchor="se", pady=(0, 5))
    
    tk.Label(page_f, text="Page No :", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)
    page_ent = tk.Entry(page_f, textvariable=state.page_num_var, font=("Segoe UI", 11, "bold"), width=5, justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    page_ent.pack(side="left", ipady=2)
    enable_copy_paste(page_ent)

    def enforce_page_num(e):
        val = state.page_num_var.get().strip()
        if not val:
            state.page_num_var.set("1")
            
    page_ent.bind("<FocusOut>", enforce_page_num)

    sig_f = tk.Frame(center_ctrl, bg=theme["card"])
    sig_f.pack(side="bottom", anchor="se", pady=(0, 10))
    
    tk.Label(sig_f, text="Signature :", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)
    
    sig_opts = ["--Select--"] 
    for s_obj in state.company_sigs:
        r = s_obj.get("role", "Authorized Signatory")
        sig_opts.append(r)
        
    cb_sig = ttk.Combobox(sig_f, textvariable=state.selected_sig_var, values=sig_opts, state="readonly", width=20, style="Theme.TCombobox")
    cb_sig.pack(side="left", ipady=2)
    
    if not state.selected_sig_var.get() or state.selected_sig_var.get() == "":
        state.selected_sig_var.set("--Select--")

    v_sub = tk.StringVar()
    v_disc_lbl = tk.StringVar()
    v_disc_val = tk.StringVar()
    v_taxable = tk.StringVar()
    v_cgst = tk.StringVar()
    v_sgst = tk.StringVar()
    v_igst = tk.StringVar()
    v_round = tk.StringVar()
    v_tot_amt = tk.StringVar()
    v_adv_paid = tk.StringVar()
    v_grand_lbl = tk.StringVar()
    v_grand_val = tk.StringVar()

    font_normal = ("Segoe UI", 12, "bold")
    font_large = ("Segoe UI", 16, "bold")

    tk.Label(right_ctrl, text="Sub Total :", bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 15), pady=4)
    tk.Label(right_ctrl, textvariable=v_sub, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e").grid(row=0, column=1, sticky="e", pady=4)

    lbl_disc = tk.Label(right_ctrl, textvariable=v_disc_lbl, bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e")
    val_disc = tk.Label(right_ctrl, textvariable=v_disc_val, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    lbl_taxable = tk.Label(right_ctrl, text="Taxable Amt :", bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e")
    val_taxable = tk.Label(right_ctrl, textvariable=v_taxable, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    f_cgst = tk.Frame(right_ctrl, bg=theme["card"])
    tk.Label(f_cgst, text="CGST @ ", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    cb_cgst = ttk.Combobox(f_cgst, textvariable=state.cgst_rate_var, values=["0", "2.5", "6", "9", "14"], width=4, font=("Segoe UI", 11, "bold"), state="readonly", style="Theme.TCombobox")
    cb_cgst.pack(side="left")
    # --- THE FIX: Pass scroll events back to the parent instead of paralyzing the screen! ---
    cb_cgst.bind("<MouseWheel>", _scroll_right)
    # ----------------------------------------------------------------------------------------
    tk.Label(f_cgst, text="% :", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    val_cgst = tk.Label(right_ctrl, textvariable=v_cgst, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    f_sgst = tk.Frame(right_ctrl, bg=theme["card"])
    tk.Label(f_sgst, text="SGST @ ", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    cb_sgst = ttk.Combobox(f_sgst, textvariable=state.sgst_rate_var, values=["0", "2.5", "6", "9", "14"], width=4, font=("Segoe UI", 11, "bold"), state="readonly", style="Theme.TCombobox")
    cb_sgst.pack(side="left")
    cb_sgst.bind("<MouseWheel>", _scroll_right)
    tk.Label(f_sgst, text="% :", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    val_sgst = tk.Label(right_ctrl, textvariable=v_sgst, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    f_igst = tk.Frame(right_ctrl, bg=theme["card"])
    tk.Label(f_igst, text="IGST @ ", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    cb_igst = ttk.Combobox(f_igst, textvariable=state.igst_rate_var, values=["0", "5", "12", "18", "28"], width=4, font=("Segoe UI", 11, "bold"), state="readonly", style="Theme.TCombobox")
    cb_igst.pack(side="left")
    cb_igst.bind("<MouseWheel>", _scroll_right)
    tk.Label(f_igst, text="% :", bg=theme["card"], fg=theme["sec"], font=font_normal).pack(side="left")
    val_igst = tk.Label(right_ctrl, textvariable=v_igst, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    tk.Label(right_ctrl, text="Round Off :", bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e").grid(row=6, column=0, sticky="e", padx=(0, 15), pady=4)
    tk.Label(right_ctrl, textvariable=v_round, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e").grid(row=6, column=1, sticky="e", pady=4)

    sep1 = tk.Frame(right_ctrl, height=1, bg=theme["border"])
    sep1.grid(row=7, column=0, columnspan=2, sticky="ew", pady=5)

    lbl_tot_amt = tk.Label(right_ctrl, text="Total Amount :", bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e")
    val_tot_amt = tk.Label(right_ctrl, textvariable=v_tot_amt, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    lbl_adv = tk.Label(right_ctrl, text="Advance Paid :", bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e")
    val_adv = tk.Label(right_ctrl, textvariable=v_adv_paid, bg=theme["card"], fg=theme["text"], font=font_normal, width=16, anchor="e")

    sep2 = tk.Frame(right_ctrl, height=1, bg=theme["border"])

    tk.Label(right_ctrl, textvariable=v_grand_lbl, bg=theme["card"], fg=theme["sec"], font=font_normal, anchor="e").grid(row=11, column=0, sticky="e", padx=(0, 15), pady=4)
    tk.Label(right_ctrl, textvariable=v_grand_val, bg=theme["card"], fg=theme["accent_green"], font=font_large, width=14, anchor="e").grid(row=11, column=1, sticky="e", pady=4)

    bind_mousewheel(right_ctrl)

    def update_totals_display():
        try: sub_f = float(state.subtotal_var.get())
        except: sub_f = 0.0
        try: cgst_f = float(state.cgst_var.get())
        except: cgst_f = 0.0
        try: sgst_f = float(state.sgst_var.get())
        except: sgst_f = 0.0
        try: igst_f = float(state.igst_var.get())
        except: igst_f = 0.0
        try: r_f = float(state.roundoff_var.get())
        except: r_f = 0.0
        try: gt_f = float(state.grand_total_var.get())
        except: gt_f = 0.0
        try: adv_f = float(state.adv_val_var.get() or 0)
        except: adv_f = 0.0
        try: disc_f = float(state.discount_amt_var.get() or 0)
        except: disc_f = 0.0

        v_sub.set(format_currency(sub_f, state.curr_fmt))
        
        if getattr(state, "inc_discount_var", None) and state.inc_discount_var.get() == 1:
            typ = state.discount_type_var.get()
            val = state.discount_val_var.get() or "0"
            v_disc_lbl.set(f"Discount ({val}%) :" if typ == "%" else "Discount :")
            v_disc_val.set(format_currency(-disc_f, state.curr_fmt))
            v_taxable.set(format_currency(sub_f - disc_f, state.curr_fmt))
            
            lbl_disc.grid(row=1, column=0, sticky="e", padx=(0, 15), pady=4)
            val_disc.grid(row=1, column=1, sticky="e", pady=4)
            lbl_taxable.grid(row=2, column=0, sticky="e", padx=(0, 15), pady=4)
            val_taxable.grid(row=2, column=1, sticky="e", pady=4)
        else:
            lbl_disc.grid_remove()
            val_disc.grid_remove()
            lbl_taxable.grid_remove()
            val_taxable.grid_remove()

        f_cgst.grid_remove()
        val_cgst.grid_remove()
        f_sgst.grid_remove()
        val_sgst.grid_remove()
        f_igst.grid_remove()
        val_igst.grid_remove()

        if getattr(state, 'has_gst', True):
            if state.gst_type.get() == "GST":
                f_cgst.grid(row=3, column=0, sticky="e", padx=(0, 15), pady=4)
                v_cgst.set(format_currency(cgst_f, state.curr_fmt))
                val_cgst.grid(row=3, column=1, sticky="e", pady=4)

                f_sgst.grid(row=4, column=0, sticky="e", padx=(0, 15), pady=4)
                v_sgst.set(format_currency(sgst_f, state.curr_fmt))
                val_sgst.grid(row=4, column=1, sticky="e", pady=4)
            elif state.gst_type.get() == "IGST":
                f_igst.grid(row=5, column=0, sticky="e", padx=(0, 15), pady=4)
                v_igst.set(format_currency(igst_f, state.curr_fmt))
                val_igst.grid(row=5, column=1, sticky="e", pady=4)

        v_round.set(format_currency(r_f, state.curr_fmt))
        
        if state.inc_adv_var.get() == 1:
            lbl_tot_amt.grid(row=8, column=0, sticky="e", padx=(0, 15), pady=4)
            v_tot_amt.set(format_currency(gt_f, state.curr_fmt))
            val_tot_amt.grid(row=8, column=1, sticky="e", pady=4)
            
            lbl_adv.grid(row=9, column=0, sticky="e", padx=(0, 15), pady=4)
            v_adv_paid.set(format_currency(-adv_f, state.curr_fmt))
            val_adv.grid(row=9, column=1, sticky="e", pady=4)
            
            sep2.grid(row=10, column=0, columnspan=2, sticky="ew", pady=5)
            
            v_grand_lbl.set("Balance Due :")
            v_grand_val.set(format_currency(gt_f - adv_f, state.curr_fmt))
        else:
            lbl_tot_amt.grid_remove()
            val_tot_amt.grid_remove()
            lbl_adv.grid_remove()
            val_adv.grid_remove()
            sep2.grid_remove()
            
            v_grand_lbl.set("Grand Total :")
            v_grand_val.set(format_currency(gt_f, state.curr_fmt))

        def refresh_scroll():
            right_ctrl.update_idletasks()
            bbox = right_canvas.bbox("all")
            if bbox:
                right_canvas.configure(scrollregion=bbox)
        right_canvas.after(50, refresh_scroll)

    state.update_totals_display_callback = update_totals_display
    state.gst_type.trace_add("write", lambda *a: state.calculate_totals())
    update_totals_display()

    def get_packed_place_val():
        serv_details = f"{state.serv_name_var.get()}||{state.serv_addr_var.get()}||{state.serv_del_var.get()}||{state.serv_bill_from_var.get()}||{state.serv_bill_to_var.get()}||{state.eway_var.get()}"
        
        subj = state.subj_var.get().strip()
        if not subj.replace("@@B@@", "").replace("@@U@@", "").strip():
            subj = ""
            
        align = state.subj_align_var.get() if hasattr(state, 'subj_align_var') else "center"
        if not align: align = "center"
        subj_str = f"@@SUBJ@@{subj}||{align}@@BANK@@" if subj else "@@BANK@@"
        
        bank_str = ""
        if state.inc_bank_var.get() == 1 and state.company_banks:
            chosen = state.selected_bank_var.get()
            for b in state.company_banks:
                ac_num = str(b.get('ac', ''))
                last4 = ac_num[-4:] if len(ac_num) >= 4 else ac_num
                alias = b.get('alias', b.get('name', 'Bank'))
                if f"{alias} (**** {last4})" == chosen:
                    bank_str = json.dumps(b)
                    break
                    
        try: d_val = state.discount_val_var.get()
        except: d_val = "0"
        try: d_typ = state.discount_type_var.get()
        except: d_typ = "%"
        try: d_inc = state.inc_discount_var.get()
        except: d_inc = 0
            
        disc_str = f"@@DISC@@{d_inc}||{d_val}||{d_typ}"
        adv_str = f"@@ADV@@{state.inc_adv_var.get()}||{state.adv_val_var.get()}"
        
        page_str = f"@@PAGE@@{state.page_num_var.get()}"
        sig_str = f"@@SIG@@{state.selected_sig_var.get()}"
        terms_str = f"@@TERMS@@{state.inc_terms_var.get()}"
        return f"@@SERV@@{serv_details}||{subj_str}{bank_str}{disc_str}{adv_str}{page_str}{sig_str}{terms_str}"

    def open_preview():
        subject_val = state.subj_var.get().strip()
        
        if not subject_val.replace("@@B@@", "").replace("@@U@@", "").strip():
            subject_val = ""
            
        eway_val = state.eway_var.get().strip() if state.inc_eway_var.get() == 1 else ""
        
        cgst_val = float(state.cgst_var.get() or 0.0) if state.gst_type.get() == "GST" else 0.0
        sgst_val = float(state.sgst_var.get() or 0.0) if state.gst_type.get() == "GST" else 0.0
        igst_val = float(state.igst_var.get() or 0.0) if state.gst_type.get() == "IGST" else 0.0

        cust_name = state.cust_var.get().strip()
        cust_phone = state.cust_phone_var.get().strip() if hasattr(state, 'cust_phone_var') else ""
        cust_gst = state.cust_gst_var.get().strip() if hasattr(state, 'cust_gst_var') else ""
        
        cust_addr = ""
        if hasattr(state, 'cust_addr_var'): cust_addr = state.cust_addr_var.get().strip()
        elif hasattr(state, 'cust_addr_text'): cust_addr = state.cust_addr_text.get("1.0", "end-1c").strip()
        
        if not cust_addr and cust_name:
            try:
                for c in database.get_all_customers():
                    if c[1] == cust_name:
                        if not cust_phone and len(c) > 2 and c[2]: cust_phone = str(c[2]).strip()
                        if not cust_gst and len(c) > 3 and c[3]: cust_gst = str(c[3]).strip()
                        if len(c) > 5 and c[5]: cust_addr = str(c[5]).strip()
                        break
            except Exception: pass

        cust_addr = extract_address(cust_addr)

        f_dt = state.serv_bill_from_var.get() if hasattr(state, 'serv_bill_from_var') else ""
        t_dt = state.serv_bill_to_var.get() if hasattr(state, 'serv_bill_to_var') else ""
        serv_bill_val = f"{f_dt} to {t_dt}" if f_dt and t_dt else f_dt
        
        subj_align_val = state.subj_align_var.get() if hasattr(state, 'subj_align_var') else "center"
        if not subj_align_val: subj_align_val = "center"

        inv_data = {
            "inv_num": state.inv_num_var.get(),
            "date": state.inv_date_var.get(),
            "inv_date": state.inv_date_var.get(),
            "cust_name": cust_name,
            "cust_addr": cust_addr,
            "cust_phone": cust_phone,
            "cust_gst": cust_gst,
            "serv_name": state.serv_name_var.get() if hasattr(state, 'serv_name_var') else "",
            "serv_addr": state.serv_addr_var.get() if hasattr(state, 'serv_addr_var') else "",
            "serv_del_date": state.serv_del_var.get() if hasattr(state, 'serv_del_var') else "",
            "serv_bill_date": serv_bill_val,
            "eway_bill": eway_val,
            "inc_eway": state.inc_eway_var.get() if hasattr(state, 'inc_eway_var') else 1,
            "subject": subject_val,
            "subject_text": subject_val,
            "show_subject": bool(subject_val),
            "subj_align": subj_align_val,
            "inc_discount": state.inc_discount_var.get() if hasattr(state, 'inc_discount_var') else 0,
            "discount_val": state.discount_val_var.get() if hasattr(state, 'discount_val_var') else "0",
            "discount_type": state.discount_type_var.get() if hasattr(state, 'discount_type_var') else "%",
            "discount_amt": float(state.discount_amt_var.get() or 0.0) if hasattr(state, 'discount_amt_var') else 0.0,
            "inc_advance": state.inc_adv_var.get(),
            "advance_val": state.adv_val_var.get(),
            "subtotal": float(state.subtotal_var.get() or 0.0),
            "cgst": cgst_val,
            "sgst": sgst_val,
            "igst": igst_val,
            "cgst_rate": state.cgst_rate_var.get(),
            "sgst_rate": state.sgst_rate_var.get(),
            "igst_rate": state.igst_rate_var.get(),
            "total": float(state.grand_total_var.get() or 0.0),
            "page_num": state.page_num_var.get(),
            "selected_sig": state.selected_sig_var.get(),
            "inc_terms": state.inc_terms_var.get() 
        }
        
        items_data = []
        for r in state.item_rows:
            raw_name = r["item"].get().strip()
            clean_name = raw_name.replace("@@B@@", "").replace("@@U@@", "")
            
            if clean_name:
                try: rt = float(r["rate"].get())
                except: rt = 0.0
                try: a = float(r["amt"].get())
                except: a = 0.0
                
                # --- THE FIX: Pass a hidden space " " for blanks to bypass Print Studio's '1' fallback ---
                q_val = r["qty"].get().strip() or " "
                d_val = r["days"].get().strip() or " "
                
                items_data.append({
                    "idx": r["sl_var"].get().strip(),
                    "data": {
                        "name": raw_name, 
                        "hsn": r["sac"].get(), 
                        "qty": q_val,
                        "unit": r["unit"].get().strip(),
                        "rate": rt, 
                        "days": d_val, 
                        "amt": a
                    }
                })

        comp_dict = {}
        if state.comp:
            # Combine all 3 phone numbers if they exist
            phones = []
            if state.comp[4]: phones.append(str(state.comp[4]).strip())
            if len(state.comp) > 5 and state.comp[5]: phones.append(str(state.comp[5]).strip())
            if len(state.comp) > 6 and state.comp[6]: phones.append(str(state.comp[6]).strip())
            phone_str = "\n".join([p for p in phones if p])
            
            comp_dict = {"name": state.comp[1], "name_sec": state.comp[2], "addr": state.comp[3], "phone": phone_str, "email": state.comp[7], "gst": state.comp[9]}
        
        banks_data = []
        if state.inc_bank_var.get() == 1 and state.company_banks and state.selected_bank_var.get():
            chosen = state.selected_bank_var.get()
            for b in state.company_banks:
                ac_num = str(b.get('ac', ''))
                last4 = ac_num[-4:] if len(ac_num) >= 4 else ac_num
                alias = b.get('alias', b.get('name', 'Bank'))
                if f"{alias} (**** {last4})" == chosen:
                    banks_data = [b]
                    break

        settings = {}
        if state.comp:
            if len(state.comp) > 14 and state.comp[14]:
                try: settings = json.loads(state.comp[14])
                except: pass
            
            settings["logo_path"] = state.comp[10] if len(state.comp) > 10 and state.comp[10] else ""
            settings["layout"] = state.comp[11] if len(state.comp) > 11 and state.comp[11] else "Classic"
            settings["logo_size"] = state.comp[12] if len(state.comp) > 12 and state.comp[12] else 120
            settings["logo_shape"] = state.comp[13] if len(state.comp) > 13 and state.comp[13] else "Original"
        settings["from_editor"] = True
            
        try:
            from utils.print_studio import PrintStudio
            PrintStudio(state.view.popup, inv_data, items_data, comp_dict, banks_data, settings)
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not launch preview:\n{e}")

    def perform_save(is_draft=False):
        inv_num = state.inv_num_var.get().strip()
        if not inv_num: messagebox.showerror("Error", "Invoice Number cannot be empty.", parent=state.popup); return
        
        current = inv_num.lower()
        if current in state.existing_inv_nums and current != getattr(state, "original_inv_num_lower", ""):
            messagebox.showerror("Duplicate Found", f"Invoice {inv_num} already exists in the active ledger.\n\nPlease use a different number.", parent=state.popup)
            return

        valid_items = []
        for r in state.item_rows:
            raw_name = r["item"].get().strip()
            clean_name = raw_name.replace("@@B@@", "").replace("@@U@@", "")
            
            # --- THE FIX: Save the row as long as it has text, even if voided! ---
            if clean_name:
                rt = r["rate"].get().strip()
                
                q = r["qty"].get().strip()
                d = r["days"].get().strip()
                
                try: a = float(r["amt"].get())
                except: a = 0.0
                
                u = r["unit"].get().strip() if "unit" in r else ""
                
                # --- THE TRICK: Mark voided Sl Nos with an invisible zero-width space! ---
                if "sl_var" in r and r["sl_var"].get().strip() == "":
                    raw_name = "\u200b" + raw_name
                # -------------------------------------------------------------------------
                
                valid_items.append((raw_name, r["sac"].get(), rt, q, d, a, u))
        
        if not valid_items: messagebox.showerror("Error", "Please add at least one valid item.", parent=state.popup); return

        sub = float(state.subtotal_var.get())
        c = float(state.cgst_var.get()) if state.gst_type.get() == "GST" else 0.0
        s = float(state.sgst_var.get()) if state.gst_type.get() == "GST" else 0.0
        i = float(state.igst_var.get()) if state.gst_type.get() == "IGST" else 0.0
        tot = float(state.grand_total_var.get())

        # --- THE BULLETPROOF FIX: Guaranteed Root Window Traversal ---
        if state.comp:
            comp_id = state.comp[0]
        else:
            comp_id = 1
            widget = state.view if hasattr(state, "view") else state.popup
            while widget:
                if hasattr(widget, "active_company_id"):
                    comp_id = getattr(widget, "active_company_id")
                    break
                if hasattr(widget, "comp_id"):
                    comp_id = getattr(widget, "comp_id")
                    break
                widget = widget.master
        
        # Lock the database global to prevent background bleed during this execution block!
        database.ACTIVE_COMPANY_ID = comp_id
        # -------------------------------------------------------------

        # --- THE FIX: Wrap the frontend sweeper so it ignores Drafts! ---
        if not is_draft:
            try:
                conn_sweep = database.get_connection()
                cur_sweep = conn_sweep.cursor()
                cur_sweep.execute("DELETE FROM invoices WHERE invoice_number=? AND company_id=? AND is_deleted=1", (inv_num, comp_id))
                conn_sweep.commit()
                conn_sweep.close()
            except Exception as e:
                print("Sweeper Error:", e)
        # ----------------------------------------------------------------

        if state.is_edit_mode:
            # Capture old invoice snapshot BEFORE updating to detect real changes
            old_inv, _ = database.get_invoice_by_id(state.edit_inv_id)

            # --- THE FIX: Peel off the old advance before running the update math! ---
            if not is_draft:
                database.clear_invoice_generation_advance(inv_num, comp_id)
            # -------------------------------------------------------------------------
            
            pass_status = 'Draft' if is_draft else None
            database.update_invoice_full(
                state.edit_inv_id, state.inv_date_var.get(), state.serv_del_var.get(), inv_num, state.cust_var.get(), 
                get_packed_place_val(), sub, c, s, i, tot, valid_items, status=pass_status, cust_id=getattr(state, 'cust_id', None)
            )

            new_cust = state.cust_var.get().strip()
            new_date = state.inv_date_var.get().strip()
            changes = []

            if old_inv:
                old_date = str(old_inv[1] or "").strip()
                old_del_col = str(old_inv[2] or "").strip()
                old_num = str(old_inv[3] or "").strip()
                old_cust = str(old_inv[4] or "").strip()
                old_place = str(old_inv[5] or "")
                old_sub = float(old_inv[6] or 0.0)
                old_tot = float(old_inv[10] or 0.0)

                def _norm_dt(d_str):
                    s = str(d_str or "").strip()
                    if not s or s.lower() == "none":
                        return ""
                    return smart_date_formatter(s, "%Y-%m-%d")

                def _tok_dt(d_str):
                    s = str(d_str or "").strip()
                    if not s or s.lower() == "none":
                        return "None"
                    return f"@@DATE:{s}@@"

                # Extract old Delivery Date & Bill Period from @@SERV@@ packed string
                old_del_dt = old_del_col
                old_b_from = ""
                old_b_to = ""
                serv_m = re.search(r'@@SERV@@(.*?)@@', old_place + "@@", re.DOTALL)
                if serv_m:
                    s_parts = serv_m.group(1).split('||')
                    if len(s_parts) > 2:
                        old_del_dt = s_parts[2].strip()
                    if len(s_parts) > 3:
                        old_b_from = s_parts[3].strip()
                    if len(s_parts) > 4:
                        old_b_to = s_parts[4].strip()

                new_del_dt = state.serv_del_var.get().strip()
                new_b_from = state.serv_bill_from_var.get().strip()
                new_b_to = state.serv_bill_to_var.get().strip()

                # 1. Check Invoice Number
                if old_num and old_num != inv_num:
                    changes.append(f"Inv#: {old_num} ➔ {inv_num}")

                # 2. Check Invoice Date
                if _norm_dt(old_date) != _norm_dt(new_date):
                    changes.append(f"Inv Date: {_tok_dt(old_date)} ➔ {_tok_dt(new_date)}")

                # 3. Check Delivery Date
                if _norm_dt(old_del_dt) != _norm_dt(new_del_dt):
                    changes.append(f"Delivery Date: {_tok_dt(old_del_dt)} ➔ {_tok_dt(new_del_dt)}")

                # 4. Check Bill Period (Billing Date)
                if (_norm_dt(old_b_from) != _norm_dt(new_b_from)) or (_norm_dt(old_b_to) != _norm_dt(new_b_to)):
                    old_bp = f"{_tok_dt(old_b_from)} to {_tok_dt(old_b_to)}" if (_norm_dt(old_b_from) and _norm_dt(old_b_to)) else _tok_dt(old_b_from)
                    new_bp = f"{_tok_dt(new_b_from)} to {_tok_dt(new_b_to)}" if (_norm_dt(new_b_from) and _norm_dt(new_b_to)) else _tok_dt(new_b_from)
                    changes.append(f"Bill Period: {old_bp} ➔ {new_bp}")

                # 5. Check Party Name
                if old_cust and old_cust != new_cust:
                    changes.append(f"Party: {old_cust} ➔ {new_cust}")

                # 4. Check Discount Applied / Changed
                old_disc_amt = 0.0
                disc_m = re.search(r'@@DISC@@(.*?)@@', old_place + "@@")
                if disc_m:
                    d_parts = disc_m.group(1).split('||')
                    if len(d_parts) > 0 and str(d_parts[0]).strip() == "1":
                        try: d_v = float(d_parts[1] or 0.0)
                        except: d_v = 0.0
                        d_t = d_parts[2] if len(d_parts) > 2 else "%"
                        old_disc_amt = (old_sub * (d_v / 100.0)) if d_t == "%" else d_v

                new_disc_amt = float(state.discount_amt_var.get() or 0.0) if state.inc_discount_var.get() == 1 else 0.0
                if abs(old_disc_amt - new_disc_amt) > 0.009:
                    if old_disc_amt <= 0.009 and new_disc_amt > 0.009:
                        changes.append(f"Discount Applied: @@CURR:{new_disc_amt:.2f}@@")
                    elif old_disc_amt > 0.009 and new_disc_amt <= 0.009:
                        changes.append(f"Discount Removed: @@CURR:{old_disc_amt:.2f}@@")
                    else:
                        changes.append(f"Discount: @@CURR:{old_disc_amt:.2f}@@ ➔ @@CURR:{new_disc_amt:.2f}@@")

                # 5. Check Advance Applied / Changed
                old_adv_amt = 0.0
                adv_m = re.search(r'@@ADV@@(.*?)@@', old_place + "@@")
                if adv_m:
                    a_parts = adv_m.group(1).split('||')
                    if len(a_parts) > 0 and str(a_parts[0]).strip() == "1":
                        try: old_adv_amt = float(a_parts[1] or 0.0)
                        except: old_adv_amt = 0.0

                new_adv_amt = float(state.adv_val_var.get() or 0.0) if state.inc_adv_var.get() == 1 else 0.0
                if abs(old_adv_amt - new_adv_amt) > 0.009:
                    if old_adv_amt <= 0.009 and new_adv_amt > 0.009:
                        changes.append(f"Advance Applied: @@CURR:{new_adv_amt:.2f}@@")
                    elif old_adv_amt > 0.009 and new_adv_amt <= 0.009:
                        changes.append(f"Advance Removed: @@CURR:{old_adv_amt:.2f}@@")
                    else:
                        changes.append(f"Advance: @@CURR:{old_adv_amt:.2f}@@ ➔ @@CURR:{new_adv_amt:.2f}@@")

                # 6. Check Grand Total
                if abs(old_tot - tot) > 0.009:
                    changes.append(f"Total: @@CURR:{old_tot:.2f}@@ ➔ @@CURR:{tot:.2f}@@")

            # Only record in Audit Log if at least one tracked field actually changed!
            if changes:
                act_lbl = "Draft Updated" if is_draft else "Edited"
                database.log_audit(
                    "Invoices", act_lbl, inv_num,
                    f"{new_cust} • " + " | ".join(changes),
                    tot, company_id=comp_id
                )
            
        else:
            pass_status = 'Draft' if is_draft else 'Unpaid'
            database.save_invoice(
                state.inv_date_var.get(), state.serv_del_var.get(), inv_num, state.cust_var.get(), 
                get_packed_place_val(), sub, c, s, i, tot, valid_items, status=pass_status, cust_id=getattr(state, 'cust_id', None)
            )
            act_lbl = "Draft Saved" if is_draft else ("Cloned" if hasattr(state, "clone_id") else "Created")
            database.log_audit(
                "Invoices", act_lbl, inv_num,
                f"{'Draft' if is_draft else 'Invoice'} for {state.cust_var.get().strip()} ({len(valid_items)} items)",
                tot, company_id=comp_id
            )

        # --- THE FIX: Removed the lockdown so Advance Gateway runs during edits! ---
        if not is_draft and state.inc_adv_var.get() == 1:
            try: adv_amt = float(state.adv_val_var.get())
            except: adv_amt = 0.0
            
            if adv_amt > 0:
                try:
                    conn_p = database.get_connection()
                    cur_p = conn_p.cursor()
                    cur_p.execute("SELECT id, amount_paid, total, write_off FROM invoices WHERE invoice_number=? AND company_id=? AND is_deleted=0", (inv_num, comp_id))
                    inv_res = cur_p.fetchone()
                    
                    if inv_res:
                        inv_id, curr_paid, inv_tot, inv_woff = inv_res
                        curr_paid, inv_tot, inv_woff = float(curr_paid or 0.0), float(inv_tot or 0.0), float(inv_woff or 0.0)
                        
                        pay_date = state.adv_date_var.get() if hasattr(state, 'adv_date_var') else state.inv_date_var.get()
                        pay_mode = state.adv_mode_var.get() if hasattr(state, 'adv_mode_var') else "Cash"
                        clean_mode = "Wallet Deduction" if "Wallet" in pay_mode else pay_mode
                        
                        if "Wallet" in pay_mode:
                            database.internal_update_wallet(cur_p, comp_id, state.cust_var.get(), -adv_amt, "advance_in")
                            
                        ref_str = f"{inv_num} ({adv_amt})"
                        
                        cust_id = getattr(state, 'cust_id', None)
                        cur_p.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, ?, ?, ?)", 
                                    (comp_id, state.cust_var.get(), cust_id, pay_date, adv_amt, clean_mode, ref_str, f"Advance received during invoice generation."))
                        
                        new_paid = curr_paid + adv_amt
                        new_bal = max(0.0, inv_tot - new_paid - inv_woff)
                        new_stat = 'Paid' if new_bal <= 0.01 else 'Partial'
                        
                        cur_p.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=? WHERE id=?", (new_paid, new_bal, new_stat, inv_id))
                        conn_p.commit()
                        if not state.is_edit_mode:
                            database.log_audit(
                                "Invoices", "Advance In", inv_num,
                                f"Advance received during billing from {state.cust_var.get().strip()} via {clean_mode}",
                                adv_amt, company_id=comp_id
                            )
                    conn_p.close()
                except Exception as e: print(f"Advance Gateway Error: {e}")
        # ---------------------------------------------------------------------------
            
        b_type = "Service"
        if state.comp and len(state.comp) > 14 and state.comp[14]:
            try: b_type = json.loads(state.comp[14]).get("business_type", "Service")
            except: pass
            
        if b_type == "Sales" and not state.is_edit_mode and not is_draft:
            today_str = datetime.now().strftime("%Y-%m-%d")
            for item in valid_items:
                # --- THE FIX: Unpack all 7 items to prevent inventory crash! ---
                raw_name, sac, rt, q, d, a, u = item
                clean_name = raw_name.replace("@@B@@", "").replace("@@U@@", "")
                
                unit = "Pcs"
                mrp = rt
                if clean_name in state.inventory_data:
                    unit = state.inventory_data[clean_name].get("unit", "Pcs")
                    if not unit: unit = "Pcs"
                    
                database.add_stock(clean_name, q, unit, mrp, f"Auto-deducted for Inv: {inv_num}", today_str, 'LOSS')
        
        # --- THE FIX: Save the GST rates to memory (Routing through Gatekeeper to prevent Ghost Keys) ---
        try:
            database.save_ui_setting("last_cgst", state.cgst_rate_var.get())
            database.save_ui_setting("last_igst", state.igst_rate_var.get())
        except: pass
        # ------------------------------------------------------------------------------------------------
        
        state.view.load_data()
        state.is_saved = True  
        msg = "Invoice saved as Draft!" if is_draft else "Invoice saved successfully!"
        messagebox.showinfo("Success", msg, parent=state.popup)
        
        state.popup.destroy()

    state.perform_save_cb = perform_save
    
    parent.winfo_toplevel().bind("<Control-p>", lambda e: open_preview())

    btn_frame = tk.Frame(parent, bg=theme["bg"])
    btn_frame.pack(fill="x", padx=20, pady=20)

    btn_text = "💾 Update Invoice" if getattr(state, "is_edit_mode", False) else "💾 Save Invoice"

    tk.Button(btn_frame, text=btn_text, bg=theme["accent_green"], fg="#ffffff", font=("Arial", 10, "bold"), relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: state.perform_save_cb(is_draft=False) if state.perform_save_cb else None).pack(side="right")
    
    tk.Button(btn_frame, text="📝 Save as Draft", bg="#f59e0b", fg="#ffffff", font=("Arial", 10, "bold"), relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: state.perform_save_cb(is_draft=True) if state.perform_save_cb else None).pack(side="right", padx=(10, 10))
    
    tk.Button(btn_frame, text="🖨 Print / Export", bg=theme["accent_blue"], fg="#ffffff", font=("Arial", 10, "bold"), relief="flat", cursor="hand2", padx=15, pady=5, command=open_preview).pack(side="right")