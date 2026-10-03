import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
from views.home_parts.ui_components import get_theme

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path: sys.path.append(root_dir)
# -----------------------------------------------

import database

# Indian GST State Codes Dictionary for Auto-Extraction
GST_STATES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "28": "Andhra Pradesh",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh"
}

def open_add_party_modal(form):
    """
    form: The parent PurchaseForm instance. 
    It expects form to have standard color attributes (BG_COLOR, CARD_BG, etc.)
    and callback methods (load_vendors, on_vendor_select, vendor_var, comp_id).
    """
    t = get_theme()
    c_bg = t["bg"]
    c_card = t["card"]
    c_text = t["text"]
    c_sec = t["sec"]
    c_border = t["border"]
    c_blue = t["accent_blue"]
    c_green = t["accent_green"]
    c_err = t["error"]
    
    q_pop = tk.Toplevel(form.pop)
    q_pop.title("Add Party")
    q_pop.geometry("600x700")
    q_pop.configure(bg=c_bg) 
    q_pop.grab_set()
    q_pop.transient(form.pop)
    
    # Center the modal dynamically
    q_pop.update_idletasks()
    x = form.pop.winfo_rootx() + (form.pop.winfo_width() // 2) - (600 // 2)
    y = form.pop.winfo_rooty() + (form.pop.winfo_height() // 2) - (700 // 2)
    q_pop.geometry(f"+{x}+{y}")
    
    main_c = tk.Canvas(q_pop, bg=c_bg, highlightthickness=0)
    scroll = ttk.Scrollbar(q_pop, orient="vertical", command=main_c.yview)
    form_f = tk.Frame(main_c, bg=c_bg, padx=30, pady=20)
    
    form_f.bind("<Configure>", lambda e: main_c.configure(scrollregion=main_c.bbox("all")))
    main_c.create_window((0, 0), window=form_f, anchor="nw", width=570)
    main_c.configure(yscrollcommand=scroll.set)
    
    main_c.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    def _forward_scroll(e):
        if e.delta: main_c.yview_scroll(int(-1*(e.delta/120)), "units")
        return "break"

    def _on_mousewheel(event):
        try:
            widget = q_pop.winfo_containing(event.x_root, event.y_root)
            if not widget or not str(widget).startswith(str(q_pop)): return
            # Let Text and Listboxes scroll themselves natively
            if isinstance(widget, (tk.Listbox, tk.Text)): return
            if event.delta: main_c.yview_scroll(int(-1*(event.delta/120)), "units")
        except: pass
        
    def _restore_scroll(e=None): q_pop.bind_all("<MouseWheel>", _on_mousewheel)
    q_pop.bind("<Enter>", _restore_scroll)
    q_pop.bind("<FocusIn>", _restore_scroll)
    q_pop.bind("<Destroy>", lambda e: q_pop.unbind_all("<MouseWheel>") if e.widget == q_pop else None)
    
    tk.Label(form_f, text="Party Details", font=("Segoe UI", 18, "bold"), bg=c_bg, fg=c_text).pack(anchor="w", pady=(0, 20))
    def lbl(text): tk.Label(form_f, text=text, font=("Segoe UI", 9, "bold"), bg=c_bg, fg=c_sec).pack(anchor="w", pady=(10, 2))
    
    lbl("Party Name (Business or Individual) *")
    n_var = tk.StringVar()
    tk.Entry(form_f, textvariable=n_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border).pack(fill="x", ipady=4)
    
    lbl("Alias Name")
    alias_var = tk.StringVar()
    tk.Entry(form_f, textvariable=alias_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border).pack(fill="x", ipady=4)

    lbl("Contact Numbers")
    phones_container = tk.Frame(form_f, bg=c_bg)
    phones_container.pack(fill="x")
    phone_vars = []
    
    def add_phone_ui(default_type="Mobile"):
        ph_f = tk.Frame(phones_container, bg=c_bg)
        ph_f.pack(fill="x", pady=(0, 5))
        
        cb_type = ttk.Combobox(ph_f, values=["Mobile", "Work", "Home", "Main", "Other"], state="readonly", width=10, font=("Segoe UI", 11), cursor="hand2")
        cb_type.pack(side="left", ipady=4)
        cb_type.set(default_type)
        cb_type.bind("<MouseWheel>", _forward_scroll)
        
        p_var = tk.StringVar()
        ent = tk.Entry(ph_f, textvariable=p_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border)
        ent.pack(side="left", fill="x", expand=True, padx=(10,0), ipady=4)
        
        def format_phone(*args, v=p_var, e=ent):
            raw = "".join(filter(str.isdigit, v.get()))
            if len(raw) > 5: formatted = f"{raw[:5]}-{raw[5:10]}"
            else: formatted = raw
            if v.get() != formatted: 
                v.set(formatted)
                e.after(1, lambda: e.icursor("end"))
        p_var.trace_add("write", format_phone)
        phone_vars.append(p_var)
            
    add_phone_ui("Mobile") 
    
    add_lbl = tk.Label(form_f, text="+ Add another phone", font=("Segoe UI", 9, "bold"), bg=c_bg, fg=c_blue, cursor="hand2")
    add_lbl.pack(anchor="w", pady=(0, 10))
    add_lbl.bind("<Enter>", lambda e: add_lbl.config(font=("Segoe UI", 9, "bold underline")))
    add_lbl.bind("<Leave>", lambda e: add_lbl.config(font=("Segoe UI", 9, "bold")))
    add_lbl.bind("<Button-1>", lambda e: add_phone_ui("Work")) 
    
    lbl("Address")
    addr_text = tk.Text(form_f, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border, height=3)
    addr_text.pack(fill="x", pady=2)
    
    lbl("Email Address")
    e_var = tk.StringVar()
    tk.Entry(form_f, textvariable=e_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border).pack(fill="x", ipady=4)
    
    lbl("PAN Number")
    pan_var = tk.StringVar()
    ent_pan = tk.Entry(form_f, textvariable=pan_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_err)
    ent_pan.pack(fill="x", ipady=4)
    
    def validate_pan(*args):
        val = pan_var.get().upper()
        if pan_var.get() != val: pan_var.set(val)
        color = c_green if len(val) == 10 else c_err
        ent_pan.config(highlightbackground=color, highlightcolor=color)
    pan_var.trace_add("write", validate_pan)
    
    g_var = tk.StringVar()
    st_var = tk.StringVar()
    
    if getattr(form, 'has_gst', True):
        lbl("GSTIN Number")
        ent_gstin = tk.Entry(form_f, textvariable=g_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_err)
        ent_gstin.pack(fill="x", ipady=4)
        
        lbl("State / Province")
        
        formatted_states = [f"{name}, Code - {code}" for code, name in GST_STATES.items()]
        formatted_states.sort()
        
        cb_state = ttk.Combobox(form_f, textvariable=st_var, values=formatted_states, state="readonly", font=("Segoe UI", 11), cursor="hand2")
        cb_state.pack(fill="x", ipady=4)
        cb_state.bind("<MouseWheel>", _forward_scroll)
        
        def validate_gstin(*args):
            val = g_var.get().upper()
            if g_var.get() != val: g_var.set(val)
            
            color = c_green if len(val) == 15 else c_err
            ent_gstin.config(highlightbackground=color, highlightcolor=color)
            
            if len(val) >= 2:
                code = val[:2]
                if code in GST_STATES:
                    st_var.set(f"{GST_STATES[code]}, Code - {code}")
            
            if len(val) >= 12:
                pan_val = val[2:12]
                if pan_var.get() != pan_val: pan_var.set(pan_val)
        g_var.trace_add("write", validate_gstin)

    tk.Frame(form_f, height=1, bg=c_border).pack(fill="x", pady=20)
    
    tk.Label(form_f, text="Accounting & Terms", font=("Segoe UI", 12, "bold"), bg=c_bg, fg=c_sec).pack(anchor="w", pady=(0, 10))
    act_f = tk.Frame(form_f, bg=c_bg); act_f.pack(fill="x")
    
    r1_f = tk.Frame(act_f, bg=c_bg); r1_f.pack(fill="x", pady=2)
    tk.Label(r1_f, text="Opening Balance", font=("Segoe UI", 9, "bold"), bg=c_bg, fg=c_sec, width=15, anchor="w").pack(side="left")
    
    ob_var = tk.StringVar(value="0")
    ent_ob = tk.Entry(r1_f, textvariable=ob_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border, width=15)
    ent_ob.pack(side="left", padx=10, ipady=4)
    ent_ob.bind("<FocusIn>", lambda e: ent_ob.delete('0', 'end') if ob_var.get() == '0' else None)
    ent_ob.bind("<FocusOut>", lambda e: ob_var.set('0') if not ob_var.get().strip() else None)
    
    cb_acc = ttk.Combobox(r1_f, values=["They Owe You (Dr)", "You Owe Them (Cr)"], state="readonly", width=18, font=("Segoe UI", 11), cursor="hand2")
    cb_acc.pack(side="left", ipady=4)
    cb_acc.set("They Owe You (Dr)")
    cb_acc.bind("<MouseWheel>", _forward_scroll)
    
    r2_f = tk.Frame(act_f, bg=c_bg); r2_f.pack(fill="x", pady=(5, 10))
    
    tk.Label(r2_f, text="Payable Terms (Days)\n(When you buy)", font=("Segoe UI", 8, "bold"), bg=c_bg, fg=c_sec, justify="left", width=16, anchor="w").pack(side="left")
    
    pay_days_var = tk.StringVar(value="0")
    ent_pay = tk.Entry(r2_f, textvariable=pay_days_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border, width=6)
    ent_pay.pack(side="left", padx=(0, 15), ipady=4)
    ent_pay.bind("<FocusIn>", lambda e: ent_pay.delete('0', 'end') if pay_days_var.get() == '0' else None)
    ent_pay.bind("<FocusOut>", lambda e: pay_days_var.set('0') if not pay_days_var.get().strip() else None)
    
    tk.Label(r2_f, text="Receivable Terms (Days)\n(When you sell)", font=("Segoe UI", 8, "bold"), bg=c_bg, fg=c_sec, justify="left", width=18, anchor="w").pack(side="left")
    
    rec_days_var = tk.StringVar(value="0")
    ent_rec = tk.Entry(r2_f, textvariable=rec_days_var, font=("Segoe UI", 11), bg=c_card, fg=c_text, insertbackground=c_text, highlightthickness=1, highlightbackground=c_border, width=6)
    ent_rec.pack(side="left", padx=(0, 0), ipady=4)
    ent_rec.bind("<FocusIn>", lambda e: ent_rec.delete('0', 'end') if rec_days_var.get() == '0' else None)
    ent_rec.bind("<FocusOut>", lambda e: rec_days_var.set('0') if not rec_days_var.get().strip() else None)
    
    def save_party():
        name = n_var.get().strip()
        alias = alias_var.get().strip()
        if not name: messagebox.showerror("Error", "Party Name is required.", parent=q_pop); return
        
        final_gstin = g_var.get().strip() if getattr(form, 'has_gst', True) else ""

        # --- THE BULLETPROOF FIX: Isolated SQL Injection ---
        conn_check = database.get_connection()
        c_check = conn_check.cursor()
        
        c_check.execute("SELECT id FROM customers WHERE LOWER(name)=LOWER(?) AND LOWER(COALESCE(alias, ''))=LOWER(?) AND LOWER(COALESCE(gstin, ''))=LOWER(?) AND company_id=?", (name, alias, final_gstin, form.comp_id))
        if c_check.fetchone():
            conn_check.close()
            messagebox.showerror("Duplicate Found", "A party with this exact Name, Alias, and GSTIN already exists.", parent=q_pop)
            return

        try:
            all_phones = [v.get().strip() for v in phone_vars if v.get().strip()]
            final_phone = ", ".join(all_phones) if all_phones else ""
            raw_addr = addr_text.get("1.0", "end-1c").strip()
            
            try: ob_val = float(ob_var.get().replace(",", ""))
            except: ob_val = 0.0
            
            ob_type_full = cb_acc.get()
            ob_type_short = "Dr" if "Dr" in ob_type_full else "Cr"
            
            p_days = "".join(filter(str.isdigit, pay_days_var.get())) or "0"
            r_days = "".join(filter(str.isdigit, rec_days_var.get())) or "0"
            
            addr_json = json.dumps({
                "address": raw_addr,
                "pan": pan_var.get().strip().upper(),
                "state": st_var.get(),
                "advance_in": 0.0,
                "advance_out": 0.0,
                "opening_balance": ob_val,
                "ob_type": ob_type_full,
                "opening_balance_type": ob_type_short,
                "payable_terms": str(int(p_days)),
                "receivable_terms": str(int(r_days)),
                "payable_days": int(p_days),
                "receivable_days": int(r_days)
            })
            
            # --- THE FIX: Direct secure SQL saving bypassing database.py completely ---
            c_check.execute("INSERT INTO customers (company_id, name, alias, phone, gstin, email, address) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (form.comp_id, name, alias, final_phone, final_gstin, e_var.get().strip(), addr_json))
            conn_check.commit()
            new_id = c_check.lastrowid
            
            state_code = "00"
            state_name = "N/A"
            if st_var.get():
                parts = st_var.get().split(", Code - ")
                if len(parts) == 2:
                    state_name = parts[0].strip()
                    state_code = parts[1].strip()
            
            # Also securing the Tax Profile update
            c_check.execute("UPDATE customers SET state=?, state_code=? WHERE id=?", (state_name, state_code, new_id))
            conn_check.commit()
            conn_check.close()

            disp_party = f"{name} ({alias})" if alias else name
            database.log_audit(
                "Parties", "Created",
                record_ref=disp_party,
                details=f"Added party '{disp_party}' via Purchase Voucher • Phone: {final_phone or 'N/A'} • GSTIN: {final_gstin or 'N/A'} • Opening Bal: @@CURR:{ob_val}@@ ({ob_type_short})",
                amount=ob_val, company_id=form.comp_id
            )
            
            form.load_vendors()
            form.target_vend_id = int(new_id)
            form.vendor_var.set(name)
            form.on_vendor_select()
            q_pop.destroy()
            
        except Exception as e:
            conn_check.close()
            messagebox.showerror("Save Error", str(e), parent=q_pop)
            
    btn_modal_save = tk.Button(form_f, text="Save", font=("Segoe UI", 12, "bold"), bg=c_blue, fg=c_text, relief="flat", cursor="hand2", command=save_party)
    btn_modal_save.pack(fill="x", pady=25, ipady=12)