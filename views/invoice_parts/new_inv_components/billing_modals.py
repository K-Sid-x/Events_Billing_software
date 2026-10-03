import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys

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
from views.invoice_parts.helpers import enable_copy_paste, grab_global_scroll

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

def open_format_cells(state, btn_widget=None):
    theme = state.theme
    format_pop = tk.Toplevel(state.popup)
    format_pop.title("Format Cells")
    format_pop.geometry("450x260")
    format_pop.configure(bg=theme["card"])
    format_pop.grab_set()
    
    format_pop.update_idletasks()
    if btn_widget:
        x = btn_widget.winfo_rootx() - 450 - 5
        y = btn_widget.winfo_rooty()
        if x < 0:
            x = btn_widget.winfo_rootx() + btn_widget.winfo_width() + 5
        format_pop.geometry(f"+{x}+{y}")
        
    tk.Label(format_pop, text="Category:", font=("Arial", 10, "bold"), bg=theme["card"], fg=theme["sec"]).grid(row=0, column=0, padx=10, pady=10, sticky="nw")
    
    cat_frame = tk.Frame(format_pop, bg=theme["card"])
    cat_frame.grid(row=1, column=0, padx=10, sticky="nw")
    
    cat_var = tk.StringVar()
    opts = [
        "Standard (INV-000)",
        "Numeric (00)",
        "Financial Year (<FY>)",
        "Batched 50s (B-<B50>/00)",
        "Custom"
    ]
    
    right_frame = tk.Frame(format_pop, bg=theme["card"])
    right_frame.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nw")
    
    tk.Label(right_frame, text="Type the number format code:", bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0, 2))
    tk.Label(right_frame, text="Hint: Use <FY> for Year, <B50> for Batches", bg=theme["card"], fg=theme["accent_blue"], font=("Arial", 8, "italic")).pack(anchor="w", pady=(0, 2))
    tk.Label(right_frame, text="Use 00, 000, or 0000 to denote the bill number.", bg=theme["card"], fg=theme.get("error", "#ef4444"), font=("Arial", 8, "bold")).pack(anchor="w", pady=(0, 5))
    
    fmt_entry = tk.Entry(right_frame, font=("Arial", 11), width=25, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], readonlybackground=theme["bg"])
    fmt_entry.pack(anchor="w")
    enable_copy_paste(fmt_entry)
    
    preview_lbl = tk.Label(right_frame, text="", font=("Arial", 14, "bold"), bg=theme["card"], fg=theme["text"])
    preview_lbl.pack(anchor="w", pady=(15, 0))
    
    def update_preview(*args):
        fmt = fmt_entry.get()
        temp_count = state.get_format_count(fmt)
        preview_lbl.config(text=state.get_formatted_inv_num(fmt, temp_count))
            
    fmt_entry.bind("<KeyRelease>", update_preview)
    
    custom_cache = state.saved_custom_format
    last_val = "Custom"
    
    def on_cat_select(*args):
        nonlocal custom_cache, last_val
        val = cat_var.get()
        
        if last_val == "Custom":
            v = fmt_entry.get().strip()
            if v: custom_cache = v
        
        fmt_entry.config(state="normal")
        fmt_entry.delete(0, 'end')
        
        if val == "Standard (INV-000)":
            fmt_entry.insert(0, "INV-000")
            fmt_entry.config(state="readonly")
        elif val == "Numeric (00)":
            fmt_entry.insert(0, "00")
            fmt_entry.config(state="readonly")
        elif val == "Financial Year (<FY>)":
            fmt_entry.insert(0, "INV/<FY>/000")
            fmt_entry.config(state="readonly")
        elif val == "Batched 50s (B-<B50>/00)":
            fmt_entry.insert(0, "B-<B50>/00")
            fmt_entry.config(state="readonly")
        else:
            fmt_entry.insert(0, custom_cache)
            fmt_entry.config(state="normal")
            fmt_entry.bind("<Return>", lambda ev: state.focus_next(ev))
        
        last_val = val
        update_preview()

    for opt in opts:
        tk.Radiobutton(cat_frame, text=opt, variable=cat_var, value=opt, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], command=on_cat_select).pack(anchor="w", pady=2)

    if state.inv_format == "INV-000": cat_var.set("Standard (INV-000)")
    elif state.inv_format == "00": cat_var.set("Numeric (00)")
    elif state.inv_format == "INV/<FY>/000": cat_var.set("Financial Year (<FY>)")
    elif state.inv_format == "B-<B50>/00": cat_var.set("Batched 50s (B-<B50>/00)")
    else: cat_var.set("Custom")
    on_cat_select()
    
    def apply_format():
        nonlocal custom_cache
        new_fmt = fmt_entry.get().strip()
        
        if cat_var.get() == "Custom":
            import re
            # --- THE FIX: If they typed a custom format but forgot the zeros, forcefully add '00' so counting doesn't break ---
            if not re.search(r'0+', new_fmt):
                new_fmt += "00"
                fmt_entry.delete(0, 'end')
                fmt_entry.insert(0, new_fmt)
            if new_fmt: custom_cache = new_fmt
            
        if getattr(state, "is_edit_mode", False):
            import re
            curr_txt = state.inv_num_var.get().strip() or getattr(state, "current_inv_val", "")
            digits = re.findall(r'\d+', str(curr_txt))
            target_count = int(digits[-1]) if digits else state.get_format_count(new_fmt)
        else:
            target_count = state.get_format_count(new_fmt)
            state.current_inv_count = target_count

        # Pull from the live generator instead of the label to ensure safety injections apply
        final_inv_str = state.get_formatted_inv_num(new_fmt, target_count)
        state.inv_num_var.set(final_inv_str)
        
        if state.comp:
            try: data = json.loads(state.comp[14]) if len(state.comp)>14 and state.comp[14] else {}
            except: data = {}
            data["invoice_format"] = new_fmt
            data["custom_inv_format"] = custom_cache 
            
            # --- THE FIX: Safely update ONLY the template JSON to prevent global profile corruption! ---
            try:
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("UPDATE company SET template_json=? WHERE id=?", (json.dumps(data), state.comp[0]))
                conn.commit()
                conn.close()
            except Exception as e: print(e)
            # -------------------------------------------------------------------------------------------
        
        state.inv_format = new_fmt
        state.saved_custom_format = custom_cache
        state.inv_number = state.get_formatted_inv_num(new_fmt, state.current_inv_count)
        if state.comp:
            database.log_audit("Invoices", "Format Changed", new_fmt, f"Updated invoice numbering format to '{new_fmt}'", 0.0, company_id=state.comp[0])
        format_pop.destroy()
        
    btn_frame = tk.Frame(format_pop, bg=theme["card"])
    btn_frame.place(relx=1.0, rely=1.0, x=-15, y=-15, anchor="se")
    
    tk.Button(btn_frame, text="Cancel", width=10, bg=theme["border"], fg=theme["text"], relief="flat", command=format_pop.destroy).pack(side="left", padx=10)
    tk.Button(btn_frame, text="OK", width=10, bg=theme["accent_blue"], fg="#ffffff", relief="flat", command=apply_format).pack(side="left")


def open_invoice_add_party(state, lookup_customer_cb):
    theme = state.theme
    q_pop = tk.Toplevel(state.view.winfo_toplevel())
    q_pop.title("Add Party")
    q_pop.geometry("600x700")
    q_pop.configure(bg=theme["bg"]) 
    q_pop.grab_set()
    q_pop.transient(state.popup)
    
    q_pop.update_idletasks()
    x = state.popup.winfo_rootx() + (state.popup.winfo_width() // 2) - (600 // 2)
    y = state.popup.winfo_rooty() + (state.popup.winfo_height() // 2) - (700 // 2)
    q_pop.geometry(f"+{x}+{y}")
    
    main_c = tk.Canvas(q_pop, bg=theme["bg"], highlightthickness=0)
    scroll = ttk.Scrollbar(q_pop, orient="vertical", command=main_c.yview)
    form_f = tk.Frame(main_c, bg=theme["bg"], padx=30, pady=20)
    
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
            if isinstance(widget, (tk.Listbox, tk.Text)): return
            if event.delta: main_c.yview_scroll(int(-1*(event.delta/120)), "units")
        except: pass
        
    def _restore_scroll(e=None): q_pop.bind_all("<MouseWheel>", _on_mousewheel)
    q_pop.bind("<Enter>", _restore_scroll)
    q_pop.bind("<FocusIn>", _restore_scroll)
    q_pop.bind("<Destroy>", lambda e: [q_pop.unbind_all("<MouseWheel>"), state.popup.event_generate("<FocusIn>")] if e.widget == q_pop else None)

    tk.Label(form_f, text="Party Details", font=("Segoe UI", 18, "bold"), bg=theme["bg"], fg=theme["text"]).pack(anchor="w", pady=(0, 20))
    def lbl(text): tk.Label(form_f, text=text, font=("Segoe UI", 9, "bold"), bg=theme["bg"], fg=theme["sec"]).pack(anchor="w", pady=(10, 2))
    
    lbl("Party Name (Business or Individual) *")
    n_var = tk.StringVar()
    tk.Entry(form_f, textvariable=n_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"]).pack(fill="x", ipady=4)
    
    lbl("Alias Name")
    alias_var = tk.StringVar()
    tk.Entry(form_f, textvariable=alias_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"]).pack(fill="x", ipady=4)

    lbl("Contact Numbers")
    phones_container = tk.Frame(form_f, bg=theme["bg"])
    phones_container.pack(fill="x")
    phone_vars = []
    
    def add_phone_ui(default_type="Mobile"):
        ph_f = tk.Frame(phones_container, bg=theme["bg"])
        ph_f.pack(fill="x", pady=(0, 5))
        
        cb_type = ttk.Combobox(ph_f, values=["Mobile", "Work", "Home", "Main", "Other"], state="readonly", width=10, font=("Segoe UI", 11), cursor="hand2", style="Theme.TCombobox")
        cb_type.pack(side="left", ipady=4)
        cb_type.set(default_type)
        cb_type.bind("<MouseWheel>", _forward_scroll) 
        
        p_var = tk.StringVar()
        ent = tk.Entry(ph_f, textvariable=p_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"])
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
    
    add_lbl = tk.Label(form_f, text="+ Add another phone", font=("Segoe UI", 9, "bold"), bg=theme["bg"], fg=theme["accent_blue"], cursor="hand2")
    add_lbl.pack(anchor="w", pady=(0, 10))
    add_lbl.bind("<Enter>", lambda e: add_lbl.config(font=("Segoe UI", 9, "bold underline")))
    add_lbl.bind("<Leave>", lambda e: add_lbl.config(font=("Segoe UI", 9, "bold")))
    add_lbl.bind("<Button-1>", lambda e: add_phone_ui("Work")) 
    
    lbl("Address")
    addr_text = tk.Text(form_f, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"], height=3)
    addr_text.pack(fill="x", pady=2)
    
    lbl("Email Address")
    e_var = tk.StringVar()
    tk.Entry(form_f, textvariable=e_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"]).pack(fill="x", ipady=4)
    
    lbl("PAN Number")
    pan_var = tk.StringVar()
    ent_pan = tk.Entry(form_f, textvariable=pan_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["error"])
    ent_pan.pack(fill="x", ipady=4)
    
    def validate_pan(*args):
        val = pan_var.get().upper()
        if pan_var.get() != val: pan_var.set(val)
        color = theme["accent_green"] if len(val) == 10 else theme["error"]
        ent_pan.config(highlightbackground=color, highlightcolor=color)
    pan_var.trace_add("write", validate_pan)
    
    g_var = tk.StringVar()
    st_var = tk.StringVar()
    
    if getattr(state, 'has_gst', True):
        lbl("GSTIN Number")
        ent_gstin = tk.Entry(form_f, textvariable=g_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["error"])
        ent_gstin.pack(fill="x", ipady=4)
        
        lbl("State / Province")
        formatted_states = [f"{name}, Code - {code}" for code, name in GST_STATES.items()]
        formatted_states.sort()
        
        cb_state = ttk.Combobox(form_f, textvariable=st_var, values=formatted_states, state="readonly", font=("Segoe UI", 11), cursor="hand2", style="Theme.TCombobox")
        cb_state.pack(fill="x", ipady=4)
        cb_state.bind("<MouseWheel>", _forward_scroll) 
        
        def validate_gstin(*args):
            val = g_var.get().upper()
            if g_var.get() != val: g_var.set(val)
            color = theme["accent_green"] if len(val) == 15 else theme["error"]
            ent_gstin.config(highlightbackground=color, highlightcolor=color)
            
            if len(val) >= 2:
                code = val[:2]
                if code in GST_STATES: st_var.set(f"{GST_STATES[code]}, Code - {code}")
            
            if len(val) >= 12:
                pan_val = val[2:12]
                if pan_var.get() != pan_val: pan_var.set(pan_val)
        g_var.trace_add("write", validate_gstin)

    tk.Frame(form_f, height=1, bg=theme["border"]).pack(fill="x", pady=20)
    
    tk.Label(form_f, text="Accounting & Terms", font=("Segoe UI", 12, "bold"), bg=theme["bg"], fg=theme["sec"]).pack(anchor="w", pady=(0, 10))
    act_f = tk.Frame(form_f, bg=theme["bg"]); act_f.pack(fill="x")
    
    r1_f = tk.Frame(act_f, bg=theme["bg"]); r1_f.pack(fill="x", pady=2)
    tk.Label(r1_f, text="Opening Balance", font=("Segoe UI", 9, "bold"), bg=theme["bg"], fg=theme["sec"], width=15, anchor="w").pack(side="left")
    
    ob_var = tk.StringVar(value="0")
    ent_ob = tk.Entry(r1_f, textvariable=ob_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"], width=15)
    ent_ob.pack(side="left", padx=10, ipady=4)
    ent_ob.bind("<FocusIn>", lambda e: ent_ob.delete('0', 'end') if ob_var.get() == '0' else None)
    ent_ob.bind("<FocusOut>", lambda e: ob_var.set('0') if not ob_var.get().strip() else None)
    
    cb_acc = ttk.Combobox(r1_f, values=["They Owe You (Dr)", "You Owe Them (Cr)"], state="readonly", width=18, font=("Segoe UI", 11), cursor="hand2", style="Theme.TCombobox")
    cb_acc.pack(side="left", ipady=4)
    cb_acc.set("They Owe You (Dr)")
    cb_acc.bind("<MouseWheel>", _forward_scroll) 
    
    r2_f = tk.Frame(act_f, bg=theme["bg"]); r2_f.pack(fill="x", pady=(5, 10))
    
    tk.Label(r2_f, text="Payable Terms (Days)\n(When you buy)", font=("Segoe UI", 8, "bold"), bg=theme["bg"], fg=theme["sec"], justify="left", width=16, anchor="w").pack(side="left")
    pay_days_var = tk.StringVar(value="0")
    ent_pay = tk.Entry(r2_f, textvariable=pay_days_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"], width=6)
    ent_pay.pack(side="left", padx=(0, 15), ipady=4)
    ent_pay.bind("<FocusIn>", lambda e: ent_pay.delete('0', 'end') if pay_days_var.get() == '0' else None)
    ent_pay.bind("<FocusOut>", lambda e: pay_days_var.set('0') if not pay_days_var.get().strip() else None)
    
    tk.Label(r2_f, text="Receivable Terms (Days)\n(When you sell)", font=("Segoe UI", 8, "bold"), bg=theme["bg"], fg=theme["sec"], justify="left", width=18, anchor="w").pack(side="left")
    rec_days_var = tk.StringVar(value="0")
    ent_rec = tk.Entry(r2_f, textvariable=rec_days_var, font=("Segoe UI", 11), bg=theme["card"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightbackground=theme["border"], width=6)
    ent_rec.pack(side="left", padx=(0, 0), ipady=4)
    ent_rec.bind("<FocusIn>", lambda e: ent_rec.delete('0', 'end') if rec_days_var.get() == '0' else None)
    ent_rec.bind("<FocusOut>", lambda e: rec_days_var.set('0') if not rec_days_var.get().strip() else None)
    
    def save_party():
        raw_name = n_var.get().strip()
        alias = alias_var.get().strip()
        if not raw_name: messagebox.showerror("Error", "Party Name is required.", parent=q_pop); return
        
        # --- THE FIX: We no longer merge the alias into the name to keep the entry box clean! ---
        name = raw_name 
        # ----------------------------------------------------------------------------------------
        
        final_gstin = g_var.get().strip() if getattr(state, 'has_gst', True) else ""

        # --- THE FIX: Route through database.py gatekeepers to prevent schema bypass! ---
        existing = database.get_customer_by_name(name)
        if existing:
            existing_gst = str(existing[3]).strip().lower() if existing[3] else ""
            if not final_gstin or existing_gst == final_gstin.lower():
                messagebox.showerror("Duplicate Found", "A party with this exact Name and GSTIN already exists.", parent=q_pop)
                return

        try:
            all_phones = [v.get().strip() for v in phone_vars if v.get().strip()]
            final_phone = ", ".join(all_phones) if all_phones else ""
            raw_addr = addr_text.get("1.0", "end-1c").strip()
            
            try: ob_val = float(ob_var.get().replace(",", ""))
            except: ob_val = 0.0
            
            ob_type = "Dr" if "Dr" in cb_acc.get() else "Cr"
            
            p_days = "".join(filter(str.isdigit, pay_days_var.get())) or "0"
            r_days = "".join(filter(str.isdigit, rec_days_var.get())) or "0"
            
            addr_json = json.dumps({
                "address": raw_addr, 
                "advance_in": 0.0,
                "advance_out": 0.0,
                "opening_balance": ob_val,
                "opening_balance_type": ob_type,
                "payable_days": int(p_days),
                "receivable_days": int(r_days)
            })
            
            # --- THE FIX: Thread-safe SQL insertion bypassing the unsafe helper query! ---
            comp_id = getattr(state.view.winfo_toplevel(), "active_company_id", 1)
            conn_id = database.get_connection()
            cur_id = conn_id.cursor()
            
            cur_id.execute("INSERT INTO customers (company_id, name, alias, phone, gstin, email, address) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                           (comp_id, name, alias, final_phone, final_gstin, e_var.get().strip(), addr_json))
            conn_id.commit()
            new_id = cur_id.lastrowid
            
            state_code = "00"
            state_name = "N/A"
            if st_var.get():
                parts = st_var.get().split(", Code - ")
                if len(parts) == 2:
                    state_name = parts[0].strip()
                    state_code = parts[1].strip()
                    
            cur_id.execute("UPDATE customers SET state=?, state_code=? WHERE id=?", (state_name, state_code, new_id))
            conn_id.commit()
            conn_id.close()
            database.log_audit("Invoices", "Party Created", name, f"Quick-added party '{name}' during billing (Opening Bal: {ob_val} {ob_type})", ob_val, company_id=comp_id)
            database.log_audit("Parties", "Created", name, f"Quick-added party '{name}' from Invoice screen (Opening Bal: {ob_val} {ob_type})", ob_val, company_id=comp_id)
            # -----------------------------------------------------------------------------
            
            state.full_customers = database.get_all_customers()
            state.customers = [str(c[1]).strip() for c in state.full_customers if len(c) > 1 and c[1]]
            state.cust_var.set(name)
            lookup_customer_cb(name)
            
            try: state.view.app.get_module("Customers").load_data()
            except: pass
            
            q_pop.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=q_pop)
            
    btn_modal_save = tk.Button(form_f, text="Save", font=("Segoe UI", 12, "bold"), bg=theme["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save_party)
    btn_modal_save.pack(fill="x", pady=25, ipady=12)