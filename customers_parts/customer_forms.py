import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import database
from views.invoice_parts.helpers import enable_copy_paste, GST_STATE_CODES



def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def center_popup(window, w, h):
    window.withdraw() 
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    if h > sh - 100: h = sh - 100
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    if y < 20: y = 20 
    window.geometry(f"{w}x{h}+{x}+{y}")
    window.deiconify() 

def open_form(customers_view, cust_id=None):
    try: colors = customers_view.colors
    except: colors = {"bg": "#0f172a", "card": "#1e293b", "border": "#334155", "text": "#f8fafc", "text_sec": "#94a3b8", "accent_blue": "#3b82f6", "accent_green": "#10b981", "error": "#ef4444"}
    
    comp_id = getattr(customers_view.winfo_toplevel(), "active_company_id", 1)
    
    try:
        comp_data = database.get_company(comp_id)
        is_gst_company = (comp_data[8] == 1) if comp_data and len(comp_data) > 8 else False
    except Exception:
        is_gst_company = False

    try: curr_symbol = customers_view.curr_fmt.split('(')[-1].replace(')', '').strip()
    except: curr_symbol = "₹"
    
    if len(curr_symbol) > 3: curr_symbol = ""
    ob_label_text = f"Opening Balance ({curr_symbol})" if curr_symbol else "Opening Balance"

    popup = tk.Toplevel(customers_view.winfo_toplevel())
    popup.withdraw() 
    popup.title("Add Party" if not cust_id else "Edit Party")
    popup.configure(bg=colors["bg"])
    popup.grab_set()

    def focus_next(event):
        event.widget.tk_focusNext().focus()
        return "break"

    main_container = tk.Frame(popup, bg=colors["bg"])
    main_container.pack(fill="both", expand=True)

    # --- THE FIX: Ensure the thick scrollbar style is registered and applied ---
    style = ttk.Style(popup)
    style.configure("CustForm.Vertical.TScrollbar", background=colors.get("text_sec", "#94a3b8"), troughcolor=colors["bg"], bordercolor=colors["bg"], arrowcolor=colors.get("text", "#f8fafc"), relief="flat")
    style.map("CustForm.Vertical.TScrollbar", background=[("active", colors.get("accent_blue", "#3b82f6"))])
    
    canvas = tk.Canvas(main_container, bg=colors["bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview, style="CustForm.Vertical.TScrollbar")
    # -------------------------------------------------------------------------
    
    f = tk.Frame(canvas, bg=colors["bg"], padx=30)
    
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    canvas_window = canvas.create_window((0, 0), window=f, anchor="nw")
    
    def configure_frame(event): canvas.configure(scrollregion=canvas.bbox("all"))
    f.bind("<Configure>", configure_frame)
    
    def configure_canvas(event): canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", configure_canvas)

    def _on_mousewheel(event):
        if canvas.bbox("all")[3] > canvas.winfo_height():
            delta = int(-1 * (event.delta / 120)) if os.name == 'nt' else -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta, "units")
            
    popup.bind("<MouseWheel>", _on_mousewheel)
    popup.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units") if canvas.bbox("all")[3] > canvas.winfo_height() else None)
    popup.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units") if canvas.bbox("all")[3] > canvas.winfo_height() else None)

    def unbind_scroll(combo_widget):
        def prevent_scroll(event):
            _on_mousewheel(event)
            return "break" 
        combo_widget.bind("<MouseWheel>", prevent_scroll)
        combo_widget.bind("<Button-4>", prevent_scroll)
        combo_widget.bind("<Button-5>", prevent_scroll)

    tk.Label(f, text="Party Details", font=("Segoe UI", 16, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(15, 5), anchor="w")

    name_var = tk.StringVar()
    alias_var = tk.StringVar()
    email_var = tk.StringVar()
    pan_var = tk.StringVar()
    gstin_var = tk.StringVar()
    state_var = tk.StringVar()
    
    ob_var = tk.StringVar(value="0.00")
    ob_type_var = tk.StringVar(value="They Owe You (Dr)")
    
    payable_var = tk.StringVar(value="0")
    receivable_var = tk.StringVar(value="0")

    phones_data = [] 

    def make_entry(parent, var, width=45):
        e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 11), width=width, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
        e.pack(anchor="w", ipady=3); enable_copy_paste(e); e.bind("<Return>", focus_next)
        return e

    tk.Label(f, text="Party Name (Business or Individual) *", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
    make_entry(f, name_var)
    
    tk.Label(f, text="Alias Name", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
    make_entry(f, alias_var)

    tk.Label(f, text="Contact Numbers", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(10, 2))
    
    phones_frame = tk.Frame(f, bg=colors["bg"])
    phones_frame.pack(fill="x", anchor="w")

    def add_phone_field(ptype="Mobile", pnum=""):
        if len(phones_data) >= 4:
            messagebox.showinfo("Limit reached", "Maximum of 4 phone numbers allowed.", parent=popup)
            return
        row = tk.Frame(phones_frame, bg=colors["bg"])
        row.pack(fill="x", pady=3)
        t_var = tk.StringVar(value=ptype)
        n_var = tk.StringVar(value=pnum)
        
        cb = ttk.Combobox(row, textvariable=t_var, values=["Mobile", "Work", "Home", "Main", "Other"], font=("Segoe UI", 10), state="readonly", width=8, style="Theme.TCombobox", cursor="hand2")
        cb.pack(side="left", padx=(0, 10), ipady=2)
        unbind_scroll(cb) 
        
        ent = tk.Entry(row, textvariable=n_var, font=("Segoe UI", 11), width=32, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
        ent.pack(side="left", ipady=3)
        enable_copy_paste(ent)

        def format_phone(*args, current_entry=ent, current_var=n_var):
            raw = current_var.get().replace("-", "")
            clean = ''.join(c for c in raw if c.isdigit())
            if len(clean) > 10: clean = clean[:10]
            fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
            if current_var.get() != fmt:
                current_var.set(fmt)
                current_entry.after(1, lambda: current_entry.icursor(tk.END))
                
        n_var.trace_add("write", format_phone)
        phones_data.append((t_var, n_var))

    btn_add_phone = tk.Button(f, text="+ Add another phone", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["accent_blue"], relief="flat", cursor="hand2", command=add_phone_field)
    btn_add_phone.pack(anchor="w", pady=(0, 5))

    tk.Label(f, text="Address", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
    t_addr = tk.Text(f, font=("Segoe UI", 11), height=3, width=45, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
    t_addr.pack(anchor="w"); enable_copy_paste(t_addr)

    tk.Label(f, text="Email Address", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
    make_entry(f, email_var)

    tk.Label(f, text="PAN Number", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
    e_pan = make_entry(f, pan_var)

    def validate_pan(*args):
        val = pan_var.get().upper()
        if pan_var.get() != val: 
            pan_var.set(val)
            e_pan.after(1, lambda: e_pan.icursor(tk.END)) 
        if len(val) == 10: e_pan.config(highlightbackground=colors["accent_green"], highlightcolor=colors["accent_green"])
        elif len(val) > 0: e_pan.config(highlightbackground=colors["error"], highlightcolor=colors["error"])
        else: e_pan.config(highlightbackground=colors["border"], highlightcolor=colors["accent_blue"])
            
    pan_var.trace_add("write", validate_pan)

    if is_gst_company:
        tk.Label(f, text="GSTIN Number", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
        e_gstin = make_entry(f, gstin_var)

        tk.Label(f, text="State / Province", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(5, 2))
        
        state_combo = ttk.Combobox(f, textvariable=state_var, values=sorted(GST_STATE_CODES.values()), font=("Segoe UI", 11), state="readonly", width=43, style="Theme.TCombobox", cursor="hand2")
        state_combo.pack(anchor="w", ipady=2)
        unbind_scroll(state_combo) 

        def validate_gstin(*args):
            val = gstin_var.get().upper()
            if gstin_var.get() != val: 
                gstin_var.set(val)
                e_gstin.after(1, lambda: e_gstin.icursor(tk.END)) 
                
            if len(val) >= 2:
                state_code = val[:2]
                if state_code in GST_STATE_CODES:
                    state_var.set(GST_STATE_CODES[state_code])
                    
            if len(val) == 15: 
                e_gstin.config(highlightbackground=colors["accent_green"], highlightcolor=colors["accent_green"])
                pan_extracted = val[2:12]
                if pan_var.get() != pan_extracted: pan_var.set(pan_extracted)
            elif len(val) > 0: 
                e_gstin.config(highlightbackground=colors["error"], highlightcolor=colors["error"])
            else: 
                e_gstin.config(highlightbackground=colors["border"], highlightcolor=colors["accent_blue"])
                
        gstin_var.trace_add("write", validate_gstin)

    tk.Frame(f, bg=colors["border"], height=1).pack(fill="x", pady=10)
    tk.Label(f, text="Accounting & Terms", font=("Segoe UI", 10, "bold"), bg=colors["bg"], fg=colors["text_sec"]).pack(anchor="w", pady=(0, 5))

    ob_frame = tk.Frame(f, bg=colors["bg"])
    ob_frame.pack(fill="x", anchor="w", pady=2)
    tk.Label(ob_frame, text=ob_label_text, font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"], width=22, anchor="w").pack(side="left")
    
    e_ob = tk.Entry(ob_frame, textvariable=ob_var, font=("Segoe UI", 11), width=15, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
    e_ob.pack(side="left", ipady=3); enable_copy_paste(e_ob)
    e_ob.bind("<FocusIn>", lambda e: e_ob.delete(0, 'end') if ob_var.get() == "0.00" else None)
    
    cb_ob_type = ttk.Combobox(ob_frame, textvariable=ob_type_var, values=["They Owe You (Dr)", "You Owe Them (Cr)"], font=("Segoe UI", 10), state="readonly", width=18, style="Theme.TCombobox", cursor="hand2")
    cb_ob_type.pack(side="left", padx=10, ipady=2)
    unbind_scroll(cb_ob_type)

    terms_frame = tk.Frame(f, bg=colors["bg"])
    terms_frame.pack(fill="x", anchor="w", pady=(10, 0))
    
    pay_f = tk.Frame(terms_frame, bg=colors["bg"])
    pay_f.pack(side="left", padx=(0, 20))
    tk.Label(pay_f, text="Payable Terms (Days)\n(When you buy)", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"], justify="left").pack(side="left", padx=(0, 5))
    e_pay = tk.Entry(pay_f, textvariable=payable_var, font=("Segoe UI", 11), width=8, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
    e_pay.pack(side="left", ipady=3); enable_copy_paste(e_pay)
    e_pay.bind("<FocusIn>", lambda e: e_pay.delete(0, 'end') if payable_var.get() == "0" else None)

    rec_f = tk.Frame(terms_frame, bg=colors["bg"])
    rec_f.pack(side="left")
    tk.Label(rec_f, text="Receivable Terms (Days)\n(When you sell)", font=("Segoe UI", 9, "bold"), bg=colors["bg"], fg=colors["text_sec"], justify="left").pack(side="left", padx=(0, 5))
    e_rec = tk.Entry(rec_f, textvariable=receivable_var, font=("Segoe UI", 11), width=8, bg=colors["card"], fg=colors["text"], insertbackground=colors["text"], highlightbackground=colors["border"], highlightthickness=1)
    e_rec.pack(side="left", ipady=3); enable_copy_paste(e_rec)
    e_rec.bind("<FocusIn>", lambda e: e_rec.delete(0, 'end') if receivable_var.get() == "0" else None)

    if cust_id:
        try:
            c_data = database.get_customer(cust_id)
            if c_data:
                # --- THE FIX: Aligning indexes with our newly secured database query ---
                name_var.set(str(c_data[1]) if c_data[1] else "")
                alias_var.set(str(c_data[8]) if len(c_data) > 8 and c_data[8] else "")
                
                phone_str = str(c_data[2]) if c_data[2] else ""
                
                if str(c_data[3]) and str(c_data[3]) != "None": gstin_var.set(str(c_data[3]))
                if str(c_data[4]) and str(c_data[4]) != "None": email_var.set(str(c_data[4]))
                # -----------------------------------------------------------------------
                
                raw_addr = str(c_data[5]) if len(c_data)>5 and c_data[5] else ""
                if raw_addr and raw_addr.strip().startswith("{") and '"address"' in raw_addr:
                    try:
                        data = json.loads(raw_addr)
                        t_addr.insert("end", data.get("address", ""))
                        state_var.set(data.get("state", ""))
                        pan_var.set(data.get("pan", ""))
                        ob_var.set(str(data.get("opening_balance", "0.00")))
                        ob_type_var.set(data.get("ob_type", "They Owe You (Dr)"))
                        
                        payable_var.set(str(data.get("payable_terms", data.get("credit_period", "0"))))
                        receivable_var.set(str(data.get("receivable_terms", data.get("credit_period", "0"))))
                    except: t_addr.insert("end", raw_addr)
                else: t_addr.insert("end", raw_addr)
                    
                if phone_str and phone_str != "None":
                    parts = [p.strip() for p in phone_str.split(",")]
                    for p in parts:
                        if ":" in p:
                            ptype, pnum = p.split(":", 1)
                            add_phone_field(ptype.strip(), pnum.strip())
                        else:
                            if p: add_phone_field("Mobile", p)
                else: add_phone_field("Mobile", "")
        except: pass
    else: add_phone_field("Mobile", "")

    # --- Enforce "Lock Opening Balance on Existing Parties" Rule for Non-Admins ---
    is_ob_locked = False
    if cust_id:
        app_top = customers_view.winfo_toplevel()
        curr_role = getattr(app_top, "current_role", "Admin")
        curr_uid = getattr(app_top, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
        if curr_role != "Admin" and str(curr_uid) != "1":
            u_perms = database.get_user_permissions(curr_uid)
            p_rules = u_perms.get("party_rules", {}) if isinstance(u_perms.get("party_rules"), dict) else {}
            if p_rules.get("lock_opening_balance", False):
                is_ob_locked = True
                e_ob.unbind("<FocusIn>")
                e_ob.config(state="disabled", disabledbackground=colors["bg"], disabledforeground=colors["text_sec"])
                cb_ob_type.config(state="disabled")

    # Snapshot initial form state right after loading so only real user edits are logged
    def _build_phone_str():
        pts = []
        for t_v, n_v in phones_data:
            raw_n = n_v.get().replace("-", "").strip()
            clean_n = "".join(c for c in raw_n if c.isdigit())[:10]
            fmt_n = f"{clean_n[:5]}-{clean_n[5:]}" if len(clean_n) > 5 else clean_n
            if fmt_n:
                pts.append(f"{t_v.get()}: {fmt_n}")
        return ", ".join(pts)

    try: _init_ob = float(ob_var.get().replace(",", ""))
    except: _init_ob = 0.0
    try: _init_pay = int(payable_var.get())
    except: _init_pay = 0
    try: _init_rec = int(receivable_var.get())
    except: _init_rec = 0

    initial_snapshot = {
        "name": name_var.get().strip(),
        "alias": alias_var.get().strip(),
        "phone": _build_phone_str(),
        "gstin": gstin_var.get().strip() if is_gst_company else "",
        "email": email_var.get().strip(),
        "address": t_addr.get("1.0", "end-1c").strip(),
        "pan": pan_var.get().upper().strip(),
        "state": state_var.get().strip() if is_gst_company else "",
        "ob_val": _init_ob,
        "ob_type": ob_type_var.get(),
        "pay_terms": _init_pay,
        "rec_terms": _init_rec
    }

    def save():
        raw_name = name_var.get().strip()
        alias = alias_var.get().strip()
        
        if not raw_name:
            messagebox.showerror("Error", "Party Name is required.", parent=popup)
            return
            
        # --- THE FIX: We no longer merge the alias into the name to keep the entry box clean! ---
        name = raw_name 
        # ----------------------------------------------------------------------------------------
            
        final_gstin = gstin_var.get().strip() if is_gst_company else ""
        
        conn_check = database.get_connection()
        c_check = conn_check.cursor()
        
        if cust_id:
            c_check.execute("SELECT id FROM customers WHERE LOWER(name)=LOWER(?) AND LOWER(COALESCE(alias, ''))=LOWER(?) AND LOWER(COALESCE(gstin, ''))=LOWER(?) AND company_id=? AND id!=?", (name, alias, final_gstin, comp_id, cust_id))
        else:
            c_check.execute("SELECT id FROM customers WHERE LOWER(name)=LOWER(?) AND LOWER(COALESCE(alias, ''))=LOWER(?) AND LOWER(COALESCE(gstin, ''))=LOWER(?) AND company_id=?", (name, alias, final_gstin, comp_id))
            
        if c_check.fetchone():
            conn_check.close()
            messagebox.showerror("Duplicate Found", "A party with this exact Name, Alias, and GSTIN already exists.", parent=popup)
            return
        conn_check.close()
        
        address_text = t_addr.get("1.0", "end-1c").strip()
        email = email_var.get().strip()
        pan_text = pan_var.get().upper().strip()

        try: ob_val = float(ob_var.get().replace(",", ""))
        except: ob_val = 0.0
        try: pay_val = int(payable_var.get())
        except: pay_val = 0
        try: rec_val = int(receivable_var.get())
        except: rec_val = 0

        combined_phone = _build_phone_str()

        existing_data = {}
        if cust_id:
            c_data = database.get_customer(cust_id)
            if c_data and len(c_data) > 5 and c_data[5]:
                try: existing_data = json.loads(c_data[5])
                except: pass
        else:
            c_data = database.get_customer_by_name(name)
            if c_data and len(c_data) > 5 and c_data[5]:
                try: existing_data = json.loads(c_data[5])
                except: pass

        if cust_id and is_ob_locked:
            ob_val = float(existing_data.get("opening_balance", _init_ob) or 0.0)
            final_ob_type = existing_data.get("ob_type", initial_snapshot["ob_type"])
        else:
            final_ob_type = ob_type_var.get()

        adv_in = float(existing_data.get("advance_in", existing_data.get("advance_wallet", 0.0)))
        adv_out = float(existing_data.get("advance_out", 0.0))
        ob_paid_existing = float(existing_data.get("ob_paid", 0.0) or 0.0)

        updated_address = {
            "address": address_text, 
            "state": state_var.get(), 
            "pan": pan_text, 
            "opening_balance": ob_val, 
            "ob_type": final_ob_type, 
            "ob_paid": ob_paid_existing,
            "payable_terms": pay_val,
            "receivable_terms": rec_val,
            "advance_in": adv_in,
            "advance_out": adv_out
        }
        packed_address = json.dumps(updated_address)

        try:
            disp_ref = f"{name} ({alias})" if alias else name
            if cust_id:
                old_name = initial_snapshot["name"]
                old_alias = initial_snapshot["alias"]
                old_phone = initial_snapshot["phone"]
                old_gstin = initial_snapshot["gstin"]
                old_email = initial_snapshot["email"]
                old_addr = initial_snapshot["address"]
                old_pan = initial_snapshot["pan"]
                old_state = initial_snapshot["state"]
                old_ob = initial_snapshot["ob_val"]
                old_ob_t = initial_snapshot["ob_type"]
                old_pay_t = initial_snapshot["pay_terms"]
                old_rec_t = initial_snapshot["rec_terms"]

                database.update_customer(cust_id, name, alias, combined_phone, final_gstin, email, packed_address)
                target_id = cust_id

                diffs = []
                if old_name != name:
                    diffs.append(f"Name: '{old_name}' ➔ '{name}'")
                if old_alias != alias:
                    diffs.append(f"Alias: '{old_alias or 'None'}' ➔ '{alias or 'None'}'")
                if old_phone != combined_phone:
                    diffs.append(f"Phone: '{old_phone or 'None'}' ➔ '{combined_phone or 'None'}'")
                if is_gst_company and old_gstin != final_gstin:
                    diffs.append(f"GSTIN: '{old_gstin or 'None'}' ➔ '{final_gstin or 'None'}'")
                if old_pan != pan_text:
                    diffs.append(f"PAN: '{old_pan or 'None'}' ➔ '{pan_text or 'None'}'")
                if old_email != email:
                    diffs.append(f"Email: '{old_email or 'None'}' ➔ '{email or 'None'}'")
                if old_addr != address_text:
                    diffs.append(f"Address: '{old_addr or 'None'}' ➔ '{address_text or 'None'}'")
                if is_gst_company and old_state != state_var.get().strip():
                    diffs.append(f"State: '{old_state or 'None'}' ➔ '{state_var.get().strip() or 'None'}'")
                if abs(old_ob - ob_val) > 0.009 or old_ob_t != final_ob_type:
                    old_dr_cr = "Dr" if "Dr" in old_ob_t else "Cr"
                    new_dr_cr = "Dr" if "Dr" in final_ob_type else "Cr"
                    diffs.append(f"Opening Bal: @@CURR:{old_ob}@@ ({old_dr_cr}) ➔ @@CURR:{ob_val}@@ ({new_dr_cr})")
                if old_pay_t != pay_val or old_rec_t != rec_val:
                    diffs.append(f"Terms (Pay/Rec): {old_pay_t}d/{old_rec_t}d ➔ {pay_val}d/{rec_val}d")

                if diffs:
                    database.log_audit("Parties", "Edited", record_ref=disp_ref, details=" | ".join(diffs), amount=ob_val, company_id=comp_id)
            else: 
                # --- THE FIX: Thread-safe SQL insertion bypassing the unsafe helper query! ---
                conn_id = database.get_connection()
                cur_id = conn_id.cursor()
                cur_id.execute("INSERT INTO customers (company_id, name, alias, phone, gstin, email, address) VALUES (?, ?, ?, ?, ?, ?, ?)", (comp_id, name, alias, combined_phone, final_gstin, email, packed_address))
                conn_id.commit()
                target_id = cur_id.lastrowid
                conn_id.close()
                # -----------------------------------------------------------------------------

                info_parts = [f"Created party '{disp_ref}'"]
                if combined_phone:
                    info_parts.append(f"Phone: {combined_phone}")
                if final_gstin:
                    info_parts.append(f"GSTIN: {final_gstin}")
                if ob_val > 0:
                    dr_cr = "Dr" if "Dr" in final_ob_type else "Cr"
                    info_parts.append(f"Opening Bal: @@CURR:{ob_val}@@ ({dr_cr})")
                database.log_audit("Parties", "Created", record_ref=disp_ref, details=" • ".join(info_parts), amount=ob_val, company_id=comp_id)
                
            # --- NEW: Save to dedicated Tax Profile SQL columns ---
            state_val = state_var.get()
            state_code = state_val.split("Code - ")[1].strip() if "Code - " in state_val else ""
            database.update_customer_tax_profile(target_id, state_val, state_code)
            # ------------------------------------------------------
            
            if hasattr(customers_view, 'load_data'):
                customers_view.load_data()
            popup.destroy()
        except Exception as e: messagebox.showerror("Database Error", f"Failed to save party: {e}", parent=popup)

    btn_save = tk.Button(f, text="Save", font=("Segoe UI", 11, "bold"), bg=colors["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", command=save, pady=8)
    btn_save.pack(fill="x", pady=(20, 0))
    add_hover(btn_save, colors["accent_blue"], "#2563eb" if colors["bg"] == "#0f172a" else "#0284c7")
    tk.Frame(f, bg=colors["bg"], height=20).pack()

    popup.update_idletasks()
    center_popup(popup, 560, 620)