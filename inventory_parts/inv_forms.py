import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
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
from views.invoice_parts.helpers import enable_copy_paste

def center_popup(window, w, h):
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    window.geometry(f"{w}x{h}+{x}+{y}")

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def open_form(inv_view, item_id=None, is_duplicate=False):
    comp_id = getattr(inv_view.winfo_toplevel(), "active_company_id", 1)
    allowed, err_msg = database.check_catalog_permission(action="edit", company_id=comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=inv_view)
        return

    popup = tk.Toplevel(inv_view)
    popup.title("Add Item" if not item_id else "Edit Item")
    popup.configure(bg=inv_view.CARD)
    popup.grab_set()

    # --- THE FIX: Universal Focus Drop Logic ---
    def bind_focus_drop(container):
        container.bind("<ButtonPress-1>", lambda e: popup.focus_set() if e.widget.winfo_class() not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button') else None, add="+")
        for child in container.winfo_children():
            if child.winfo_class() in ('Frame', 'Label', 'Canvas'):
                bind_focus_drop(child)

    comp_id = getattr(inv_view.winfo_toplevel(), "active_company_id", 1)
    
    # --- THE FIX: MVC Compliant GST Toggle Fetch ---
    has_gst = database.get_company_gst_toggle(comp_id)
    # -----------------------------------------------

    def focus_next(event):
        event.widget.tk_focusNext().focus()
        return "break"

    def apply_focus_effect(w):
        w.bind("<FocusIn>", lambda e: w.config(bg=inv_view.FOCUS_BG), add="+")
        w.bind("<FocusOut>", lambda e: w.config(bg=inv_view.BG if not isinstance(w, tk.Text) else inv_view.BG), add="+")

    tk.Label(popup, text="Catalog Details", font=("Arial", 16, "bold"), bg=inv_view.CARD, fg=inv_view.FG).pack(pady=(20, 10), anchor="w", padx=30)

    container = tk.Frame(popup, bg=inv_view.CARD)
    container.pack(fill="both", expand=True, padx=(30, 15), pady=(0, 20))

    style = ttk.Style(popup)
    style.configure("Form.Vertical.TScrollbar", background=inv_view.SEC_FG, troughcolor=inv_view.CARD, bordercolor=inv_view.CARD, arrowcolor=inv_view.FG, relief="flat")
    style.map("Form.Vertical.TScrollbar", background=[("active", inv_view.BLUE)])

    canvas = tk.Canvas(container, bg=inv_view.CARD, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Form.Vertical.TScrollbar")
    
    f = tk.Frame(canvas, bg=inv_view.CARD, padx=15)
    
    f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=f, anchor="nw")
    
    def configure_canvas(event):
        canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", configure_canvas)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        try:
            if not canvas.winfo_exists(): return
            
            # Allow the page to scroll even when hovering over the small Notes text box
            w_class = event.widget.winfo_class()
            if w_class == 'Listbox': return
            
            import os
            delta = int(-1 * (event.delta / 120)) if os.name == 'nt' else int(-1 * event.delta)
            canvas.yview_scroll(delta, "units")
        except: pass

    def _combo_scroll(event):
        _on_mousewheel(event)
        return "break"

    def _bind_smooth_scroll(e):
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _unbind_smooth_scroll(e=None):
        try:
            canvas.unbind_all("<MouseWheel>")
            # Safely return scroll control to the main app when popup closes
            app = inv_view.winfo_toplevel()
            if hasattr(app, "_on_mousewheel"):
                app.bind_all("<MouseWheel>", app._on_mousewheel)
        except: pass

    canvas.bind("<Enter>", _bind_smooth_scroll)
    canvas.bind("<Leave>", _unbind_smooth_scroll)
    popup.bind("<Destroy>", _unbind_smooth_scroll, add="+")

    # --- THE FIX: Replaced 'None' with '--Select--' at the top ---
    full_units = ["--Select--", "Numbers (Nos.)", "Kilograms (Kg)", "Pieces (Pcs)", "Packets (Pkts)", "Running Feet (Rft)", "Running Metre (Rmt)", "Square Feet (Sq.ft.)", "Hours (Hours)", "Days (Days)", "Months (Months)", "Trips (Trip)"]
    # -------------------------------------------------------------

    name_var = tk.StringVar()
    cat_var = tk.StringVar(value="General")
    unit_var = tk.StringVar(value="Numbers (Nos.)")
    rate_var = tk.StringVar(value="0.00")
    hsn_var = tk.StringVar()
    current_pics = []
    
    database.set_active_company(comp_id)
    # --- THE FIX: MVC Compliant Inventory Catalog Fetch ---
    all_inv = database.get_all_inventory()
    inv_names = [i[1] if len(i)>1 else "" for i in all_inv]
    # ------------------------------------------------------
    
    # --- THE FIX: Severed the link to the Stock table for autocomplete ---
    existing_names = list(set(inv_names))
    existing_names = [n for n in existing_names if n.strip()]
    # -------------------------------------------------------------------

    old_data_snapshot = None 

    if item_id:
        parsed = inv_view.get_parsed_data()
        for p in parsed:
            if str(p['id']) == str(item_id):
                old_data_snapshot = dict(p)
                name_var.set(p['name'])
                cat_var.set(p['category'])
                
                short_u = p['unit']
                long_u = next((u for u in full_units if f"({short_u})" in u), short_u)
                unit_var.set(long_u)
                
                hsn_var.set(p['hsn'])
                rate_var.set(str(p['rate']))
                if p.get('pics') and not is_duplicate:
                    current_pics.extend(p['pics'])
                
                if is_duplicate:
                    popup.title("Duplicate Item")
                    name_var.set(name_var.get() + " (Copy)")
                    item_id = None 
                break

    def validate_number_typing(*args, var=rate_var):
        val = var.get()
        clean, dec_count = "", 0
        for char in val:
            # --- THE FIX: Stripped negative sign capability for strict positive pricing ---
            if char.isdigit(): clean += char
            elif char == '.' and dec_count == 0:
                clean += char
                dec_count += 1
            # ----------------------------------------------------------------------------
        if val != clean: var.set(clean)
            
    rate_var.trace_add("write", lambda *a: validate_number_typing(var=rate_var))

    tk.Label(f, text="Item Name *", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(5, 2))
    e_name = tk.Entry(f, textvariable=name_var, font=("Arial", 11), bg=inv_view.BG, fg=inv_view.FG, insertbackground=inv_view.FG, highlightbackground=inv_view.BORDER, highlightthickness=1)
    e_name.pack(fill="x", ipady=3); enable_copy_paste(e_name)
    apply_focus_effect(e_name)
    e_name.focus() 

    lb = tk.Listbox(f, font=("Arial", 10), height=4, bg=inv_view.BG, fg=inv_view.FG, selectbackground=inv_view.BLUE, highlightbackground=inv_view.BORDER, highlightthickness=1, cursor="hand2")
    
    def update_list(*args):
        s = name_var.get().lower(); lb.delete(0, tk.END)
        m = [i for i in existing_names if s in i.lower() and s != i.lower()]
        
        # --- THE FIX: Only show suggestions if the user is actively typing in the Name box ---
        if s and m and popup.focus_get() == e_name: 
            popup.update_idletasks()
            lb.place(x=e_name.winfo_x(), y=e_name.winfo_y()+e_name.winfo_height()+2, width=e_name.winfo_width())
            for x in m[:10]: lb.insert(tk.END, x)
            lb.lift()
        else: lb.place_forget()
        
    name_var.trace("w", update_list)
    e_name.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)
    
    # --- THE FIX: Instantly hide the dropdown if you click into any other box! ---
    def hide_dropdown(e=None):
        if popup.focus_get() != lb:
            lb.place_forget()
            
    e_name.bind("<FocusOut>", lambda e: popup.after(150, hide_dropdown), add="+")
    # -----------------------------------------------------------------------------

    def pre_fill_data(selected_name):
        found = False
        for item in all_inv:
            if len(item) > 1 and item[1].lower() == selected_name.lower():
                unit = str(item[2]) if len(item) > 2 else "Nos."
                try: rate = float(item[3]) if len(item) > 3 else 0.0
                except: rate = 0.0
                raw_desc = str(item[4]) if len(item) > 4 else ""

                if len(item) == 4:
                    try: rate, unit, raw_desc = float(item[2]), "Nos.", str(item[3])
                    except: pass

                desc_val, hsn_val, cat_val = raw_desc, "", "General"
                if raw_desc and raw_desc.strip().startswith("{") and '"desc"' in raw_desc:
                    try:
                        j = json.loads(raw_desc)
                        desc_val = j.get("desc", "")
                        unit = j.get("unit", unit)
                        hsn_val = j.get("hsn", "")
                        cat_val = j.get("category", "General")
                    except: pass
                
                cat_var.set(cat_val)
                long_u = next((u for u in full_units if f"({unit})" in u), unit)
                unit_var.set(long_u)
                rate_var.set(str(rate))
                hsn_var.set(hsn_val)
                t_desc.delete("1.0", "end")
                t_desc.insert("end", desc_val)
                found = True
                break
                
        # --- THE FIX: Severed the fallback that pulled pricing from the Stock table ---
    
    row2 = tk.Frame(f, bg=inv_view.CARD)
    row2.pack(fill="x", pady=(10, 5))
    
    c_f = tk.Frame(row2, bg=inv_view.CARD)
    c_f.pack(side="left", fill="x", expand=True, padx=(0, 10))
    tk.Label(c_f, text="Category", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(0, 2))
    e_cat = ttk.Combobox(c_f, textvariable=cat_var, values=["General", "Services", "Electronics", "Furniture", "Hardware", "Clothing", "Food & Bev", "Other"], font=("Arial", 11), state="readonly", style="Theme.TCombobox")
    e_cat.pack(fill="x", ipady=3)
    e_cat.bind("<Return>", focus_next)
    e_cat.bind("<MouseWheel>", _combo_scroll)

    e_name.bind("<Return>", lambda e: e_cat.focus() if not lb.winfo_ismapped() else lb.focus())
    lb.bind("<Return>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), pre_fill_data(name_var.get()), lb.place_forget(), e_cat.focus(), "break"][4] if lb.curselection() else None)
    lb.bind("<Double-Button-1>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), pre_fill_data(name_var.get()), lb.place_forget(), e_cat.focus()])
    lb.bind("<ButtonRelease-1>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), pre_fill_data(name_var.get()), lb.place_forget(), e_cat.focus()] if lb.curselection() else None)
    
    u_f = tk.Frame(row2, bg=inv_view.CARD)
    u_f.pack(side="left", fill="x", expand=True, padx=(10, 0))
    tk.Label(u_f, text="Unit *", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(0, 2))
    e_unit = ttk.Combobox(u_f, textvariable=unit_var, values=full_units, font=("Arial", 11), state="readonly", style="Theme.TCombobox")
    e_unit.pack(fill="x", ipady=3)
    e_unit.bind("<Return>", focus_next)
    e_unit.bind("<MouseWheel>", _combo_scroll)

    row3 = tk.Frame(f, bg=inv_view.CARD)
    row3.pack(fill="x", pady=(5, 5))

    # --- THE FIX: Cleanly extract the single symbol character ---
    raw_fmt = getattr(inv_view, "curr_fmt", "₹")
    try:
        # If string is "US Dollar ($ 1,000.00)", split('(')[1] yields "$ 1,000.00)".
        # Index [0] grabs the very first character: "$"
        curr_symbol = raw_fmt.split('(')[1][0]
    except:
        curr_symbol = "₹"

    r_f = tk.Frame(row3, bg=inv_view.CARD)
    r_f.pack(side="left", fill="x", expand=True, padx=(0, 10) if has_gst else 0)
    tk.Label(r_f, text=f"Rate / Unit ({curr_symbol}) *", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(0, 2))
    e_rate = tk.Entry(r_f, textvariable=rate_var, font=("Arial", 11), bg=inv_view.BG, fg=inv_view.FG, insertbackground=inv_view.FG, highlightbackground=inv_view.BORDER, highlightthickness=1)
    e_rate.pack(fill="x", ipady=3); enable_copy_paste(e_rate); e_rate.bind("<Return>", focus_next)
    e_rate.bind("<FocusIn>", lambda e: e_rate.delete('0', 'end') if e_rate.get() == '0.00' else None, add="+")
    apply_focus_effect(e_rate)

    if has_gst:
        h_f = tk.Frame(row3, bg=inv_view.CARD)
        h_f.pack(side="left", fill="x", expand=True, padx=(10, 0))
        tk.Label(h_f, text="HSN/SAC Code", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(0, 2))
        e_hsn = tk.Entry(h_f, textvariable=hsn_var, font=("Arial", 11), bg=inv_view.BG, fg=inv_view.FG, insertbackground=inv_view.FG, highlightbackground=inv_view.BORDER, highlightthickness=1)
        e_hsn.pack(fill="x", ipady=3); enable_copy_paste(e_hsn); e_hsn.bind("<Return>", focus_next)
        apply_focus_effect(e_hsn)

    tk.Label(f, text="Internal Notes / Description", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(10, 2))
    t_desc = tk.Text(f, font=("Arial", 11), height=2, bg=inv_view.BG, fg=inv_view.FG, insertbackground=inv_view.FG, highlightbackground=inv_view.BORDER, highlightthickness=1)
    t_desc.pack(fill="x"); enable_copy_paste(t_desc)
    t_desc.bind("<Return>", lambda e: save() if not e.state & 1 else None) 
    apply_focus_effect(t_desc)
    
    if item_id and old_data_snapshot:
        t_desc.insert("end", old_data_snapshot['desc'])

    pic_container = tk.Frame(f, bg=inv_view.CARD)
    pic_container.pack(fill="x", pady=(15, 0))
    
    tk.Label(pic_container, text="Attached Pictures", font=("Arial", 9, "bold"), bg=inv_view.CARD, fg=inv_view.SEC_FG).pack(anchor="w", pady=(0, 2))
    pic_list_f = tk.Frame(pic_container, bg=inv_view.CARD)
    pic_list_f.pack(fill="x")

    def refresh_pics():
        for widget in pic_list_f.winfo_children(): widget.destroy()
        for idx, p in enumerate(current_pics):
            row = tk.Frame(pic_list_f, bg=inv_view.BG, highlightbackground=inv_view.BORDER, highlightthickness=1, pady=2, padx=5)
            row.pack(fill="x", pady=2)
            fname = os.path.basename(p["path"])[:35] + "..."
            tk.Label(row, text=f"🖼️ {fname}", font=("Arial", 9), bg=inv_view.BG, fg=inv_view.FG).pack(side="left", padx=5)
            
            def del_pic(i=idx):
                current_pics.pop(i)
                refresh_pics()
                
            tk.Button(row, text="❌", font=("Arial", 8), bg=inv_view.BG, fg=inv_view.DANGER, relief="flat", cursor="hand2", command=del_pic).pack(side="right", padx=5)

    def attach_picture():
        from tkinter import filedialog
        paths = filedialog.askopenfilenames(parent=popup, title="Select Attachments", filetypes=[("Images & PDFs", "*.png *.jpg *.jpeg *.pdf"), ("All Files", "*.*")])
        if paths:
            for p in paths:
                current_pics.append({"path": p, "desc": "Catalog Attachment"})
            refresh_pics()
            popup.lift(); popup.focus_force()
            
    tk.Button(pic_container, text="📎 + Add File/Image", font=("Arial", 9, "bold"), bg=inv_view.BORDER, fg=inv_view.FG, relief="flat", cursor="hand2", command=attach_picture, padx=10, pady=2).pack(anchor="w", pady=(5, 0))
    refresh_pics()

    def save(event=None):
        name = name_var.get().strip()
        unit_str = unit_var.get().strip()
        unit = unit_str.split("(")[-1].replace(")", "").strip() if "(" in unit_str else unit_str
        
        try: rate = float(rate_var.get().strip() or 0)
        except: rate = 0.0
        
        hsn = hsn_var.get().strip()
        cat = cat_var.get().strip()
        desc_text = t_desc.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showerror("Error", "Item Name is required.", parent=popup)
            return
            
        # Securely copy images to Vault before saving JSON
        import shutil, time, random
        from views.invoice_parts.helpers import get_vault_path
        
        safe_item = name.strip() if name.strip() else f"Item_{int(time.time())}"
        safe_dir = get_vault_path(ROOT_DIR, comp_id, safe_item, module_folder="Catalog")
        
        for pic in current_pics:
            path = pic.get("path", "")
            if path and os.path.exists(path) and "Catalog_Images" not in path:
                ext = os.path.splitext(path)[1] or ".png"
                new_name = f"item_{int(time.time()*1000)}_{random.randint(1000,9999)}{ext}"
                new_path = os.path.join(safe_dir, new_name)
                try:
                    shutil.copy2(path, new_path)
                    pic["path"] = new_path
                except: pass
        
        data_dict = {"desc": desc_text, "unit": unit, "hsn": hsn, "category": cat, "pics": current_pics}
        packed_desc = json.dumps(data_dict)

        if not inv_view.safe_db_add(name, unit, rate, packed_desc, item_id):
            messagebox.showerror("Database Error", "Failed to save data.", parent=popup)
            return
            
        # --- THE FIX: Audit Log Camera for Catalog ---
        if item_id and old_data_snapshot:
            diffs = []
            if old_data_snapshot.get('name') != name: diffs.append(f"Name ➔ '{name}'")
            if float(old_data_snapshot.get('rate', 0)) != rate: diffs.append(f"Rate ➔ @@CURR:{rate}@@")
            if old_data_snapshot.get('category') != cat: diffs.append(f"Category ➔ '{cat}'")
            diff_str = " | ".join(diffs) if diffs else "Item details updated"
            database.log_audit("Catalog", "Edited", record_ref=name, details=diff_str, amount=rate, company_id=comp_id)
        else:
            database.log_audit("Catalog", "Created", record_ref=name, details=f"Added new item in category '{cat}'", amount=rate, company_id=comp_id)
        # ---------------------------------------------

        new_data_snapshot = {"name": name, "unit": unit, "rate": rate, "desc": desc_text, "hsn": hsn, "category": cat, "pics": current_pics}
        inv_view.push_undo({"type": "edit_main" if item_id else "add_main", "id": item_id, "old": old_data_snapshot, "new": new_data_snapshot})

        inv_view.load_data()
        popup.destroy()

    btn_save = tk.Button(f, text="Save Item", font=("Arial", 11, "bold"), bg=inv_view.BLUE, fg="#ffffff", cursor="hand2", relief="flat", command=save, pady=8)
    btn_save.pack(fill="x", pady=(20,0))
    btn_save.bind("<Return>", save) 
    add_hover(btn_save, inv_view.BLUE, inv_view.BTN_HOVER)
    
    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.bind("<Control-Return>", save)
    
    # Arm the Universal Focus Drop
    bind_focus_drop(popup)
    
    popup.update_idletasks()
    req_h = popup.winfo_reqheight() + 20
    # Cap the maximum height at 650 pixels so the scrollbar engages!
    final_h = min(req_h, 650) 
    center_popup(popup, 550, final_h)