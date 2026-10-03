import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import csv
import tempfile
import webbrowser
import base64
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)
# -----------------------------------------------

import database

def print_bulk_id_cards(parent_view, selected_items):
    if not selected_items: return
    
    try:
        comp_id = getattr(parent_view.app, "active_company_id", 1)
        comp = database.get_company(comp_id) if comp_id else database.get_company(1)
        comp_name = comp[1] if comp else "COMPANY NAME"
    except:
        comp_name = "COMPANY NAME"
        comp = None

    # --- THE FIX: Fetch Company Logo ONCE for the whole page ---
    comp_logo = comp[10] if comp and len(comp) > 10 else ""
    comp_logo_html = ""
    if comp_logo and os.path.exists(comp_logo):
        try:
            with open(comp_logo, "rb") as l_file:
                comp_logo_html = f'<img src="data:image/png;base64,{base64.b64encode(l_file.read()).decode()}" style="max-height: 35px; max-width: 150px; margin-bottom: 5px; object-fit: contain;"><br>'
        except: pass

    cards_html = ""
    for row_id in selected_items:
        # --- THE FIX: Use safe dict helper instead of PRAGMA loop! ---
        w_dict = database.get_labour_dict(row_id)
        if not w_dict: continue
        # -------------------------------------------------------------
        
        emp_photo = w_dict.get('photo_path', '')
        img_html = '<div class="no-photo">👤</div>'
        if emp_photo and os.path.exists(emp_photo):
            try:
                with open(emp_photo, "rb") as img_file:
                    b64_string = base64.b64encode(img_file.read()).decode()
                import mimetypes
                mime_type, _ = mimetypes.guess_type(emp_photo)
                if not mime_type: mime_type = "image/png"
                img_html = f'<img src="data:{mime_type};base64,{b64_string}" alt="Photo">'
            except: pass

        raw_role = str(w_dict.get('role', '')).strip()
        role_html = f'<div class="role">{raw_role}</div>' if raw_role and raw_role.lower() not in ("none", "unknown") else ''
        
        # --- THE FIX: Stack emergency contacts and auto-shrink font so they fit perfectly! ---
        emerg_raw = w_dict.get('emergency_contact', '')
        if not emerg_raw: emerg_html = "N/A"
        else: 
            e_parts = [p.strip() for p in str(emerg_raw).split(",") if p.strip()]
            emerg_html = "<br>".join(e_parts)
            if len(e_parts) > 1: emerg_html = f"<span style='font-size: 18px; line-height: 1.2;'>{emerg_html}</span>"
        # --------------------------------------------------------------------------------------
        
        blood_html = w_dict.get('blood_type', 'Unknown')
        addr_html = w_dict.get('address', 'N/A')
        
        worker_id_str = str(w_dict.get('worker_id_str', ''))
        if not worker_id_str: worker_id_str = f"LAB-{int(w_dict.get('id', 0)):04d}"
        
        cards_html += f"""
        <!-- FRONT SIDE -->
        <div class="id-card">
            <div class="header-bar"></div>
            <div class="company" style="margin-bottom: 15px;">{comp_logo_html}{comp_name}</div>
            <div class="photo-container" style="margin-bottom: 15px;">{img_html}</div>
            <div class="name">{w_dict.get('name', '')}</div>
            <div class="worker-id">ID: {worker_id_str}</div>
            {role_html}
            <div class="sign-box"><div class="sign-line">Auth. Signatory</div></div>
        </div>
        <!-- BACK SIDE -->
        <div class="id-card">
            <div class="header-bar" style="background: #ef4444;"></div>
            <div class="back-title" style="margin-top: 25px;">EMERGENCY CONTACT</div>
            <div class="back-text emerg-val">{emerg_html}</div>
            <div class="back-title" style="margin-top: 15px;">BLOOD GROUP</div>
            <div class="back-text" style="color: #ef4444; font-size: 24px;">{blood_html}</div>
            
            <div style="margin-top: auto; padding: 15px 10px; background: #f8fafc; border-radius: 8px; width: 100%; box-sizing: border-box; border: 1px solid #e2e8f0;">
                <div style="font-size: 11px; color: #475569; font-weight: bold; margin-bottom: 5px;">TERMS OF USE</div>
                <div style="font-size: 10px; color: #64748b; line-height: 1.3; margin-bottom: 10px;">This card is property of {comp_name}. It is non-transferable and must be presented upon request.</div>
                <div style="font-size: 11px; color: #475569; font-weight: bold; margin-bottom: 3px;">IF FOUND, RETURN TO:</div>
                <div style="font-size: 11px; color: #0f172a; font-weight: bold;">{comp_name}</div>
                <div style="font-size: 10px; color: #64748b; margin-top: 2px;">Phone: {comp[4] if comp and len(comp) > 4 and comp[4] else "Head Office"}</div>
            </div>
        </div>
        """
        
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Bulk ID Cards</title>
        <style>
            @media print {{ @page {{ margin: 10mm; size: A4; }} body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
            body {{ font-family: 'Arial', sans-serif; background: #f1f5f9; padding: 20px; }}
            /* 2 columns means it will auto-arrange Front and Back side-by-side! */
            .grid-container {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; max-width: 700px; margin: 0 auto; }}
            .id-card {{ width: 270px; height: 410px; background: white; border: 2px dashed #cbd5e1; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; padding: 25px 20px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; position: relative; overflow: hidden; margin: auto; page-break-inside: avoid; }}
            .header-bar {{ position: absolute; top: 0; left: 0; width: 100%; height: 10px; background: #3b82f6; }}
            .company {{ font-size: 19px; font-weight: 900; color: #0f172a; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; padding: 0 5px; box-sizing: border-box; }}
            .photo-container {{ width: 140px; height: 160px; border: 3px solid #e2e8f0; margin-bottom: 25px; background: #f8fafc; display: flex; justify-content: center; align-items: center; overflow: hidden; border-radius: 8px; }}
            .photo-container img {{ width: 100%; height: 100%; object-fit: cover; }}
            .no-photo {{ font-size: 60px; color: #94a3b8; }}
            .name {{ font-size: 24px; font-weight: bold; color: #1e293b; margin-bottom: 2px; line-height: 1.1; }}
            .worker-id {{ font-size: 13px; font-weight: bold; color: #64748b; margin-bottom: 8px; letter-spacing: 1px; }}
            .role {{ font-size: 16px; font-weight: bold; color: #3b82f6; text-transform: uppercase; letter-spacing: 1px; }}
            .sign-box {{ margin-top: auto; width: 100%; text-align: right; padding-right: 5px; }}
            .sign-line {{ display: inline-block; border-top: 1px dashed #64748b; font-size: 10px; color: #64748b; padding-top: 4px; width: 100px; text-align: center; margin-bottom: -5px; }}
            
            .back-title {{ margin-top: 25px; font-size: 15px; font-weight: bold; color: #3b82f6; letter-spacing: 1px; text-transform: uppercase; }}
            .back-text {{ font-size: 18px; font-weight: bold; color: #1e293b; margin-top: 5px; }}
            .emerg-val {{ color: #ef4444; font-size: 22px; }}
            .addr-val {{ font-size: 14px; font-weight: normal; padding: 0 10px; line-height: 1.4; }}
        </style>
    </head>
    <body>
        <div class="grid-container">
            {cards_html}
        </div>
        <script>window.onload = function() {{ window.print(); }}</script>
    </body>
    </html>
    """
    
    # --- THE FIX: Tagged prefix for the Sweeper ---
    fd, path = tempfile.mkstemp(suffix=".html", prefix="Bulk_Labour_ID_Cards_")
    with os.fdopen(fd, 'w', encoding='utf-8') as html_file: html_file.write(html_content)
    webbrowser.open('file://' + os.path.realpath(path))
    parent_view.cancel_bulk()

def show_export_menu(parent_view):
    menu = tk.Menu(parent_view, tearoff=0, font=("Segoe UI", 11), bg=parent_view.colors["card"], fg=parent_view.colors["text"])
    menu.add_command(label="📊 Export to CSV", command=lambda: open_export_selector(parent_view, "csv"))
    menu.add_command(label="📄 Export to PDF", command=lambda: open_export_selector(parent_view, "pdf"))
    btn = parent_view.btn_bulk_export_action if parent_view.is_bulk_mode else parent_view.btn_export
    menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

def open_export_selector(parent_view, fmt):
    pop = tk.Toplevel(parent_view)
    pop.title("Export Settings")
    pop.configure(bg=parent_view.colors["bg"])
    
    btn = parent_view.btn_bulk_export_action if parent_view.is_bulk_mode else parent_view.btn_export
    x = btn.winfo_rootx() + btn.winfo_width() - 350
    y = btn.winfo_rooty() + btn.winfo_height() + 5
    pop.geometry(f"350x380+{max(0, x)}+{max(0, y)}")
    
    pop.grab_set()

    tk.Label(pop, text="Select fields to export:", font=("Segoe UI", 12, "bold"), bg=parent_view.colors["bg"], fg=parent_view.colors["text"]).pack(pady=(15, 10))

    fields = ["Photo", "Name", "Address", "Ph No", "Blood Type", "Role"]
    vars_dict = {}

    f_frame = tk.Frame(pop, bg=parent_view.colors["bg"])
    f_frame.pack(fill="both", expand=True, padx=40)

    for f in fields:
        var = tk.BooleanVar(value=True)
        vars_dict[f] = var
        chk = tk.Checkbutton(f_frame, text=f, variable=var, font=("Segoe UI", 11), bg=parent_view.colors["bg"], fg=parent_view.colors["text"], selectcolor=parent_view.colors["card"], activebackground=parent_view.colors["bg"], activeforeground=parent_view.colors["text"])
        chk.pack(anchor="w", pady=4)

    def confirm():
        selected = {k: v.get() for k, v in vars_dict.items()}
        if not any(selected.values()):
            messagebox.showwarning("Warning", "Select at least one field.", parent=pop)
            return
        pop.destroy()
        execute_export(parent_view, fmt, selected)

    tk.Button(pop, text="Confirm & Export", font=("Segoe UI", 11, "bold"), bg=parent_view.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=confirm, pady=8).pack(fill="x", padx=40, pady=(10, 20))

def execute_export(parent_view, fmt, selected_fields):
    # --- THE FIX: Use safe helper to build lookup dictionary without PRAGMA! ---
    labours = database.get_all_labours()
    db_lookup = {}
    for l in labours:
        l_dict = database.get_labour_dict(l[0])
        if l_dict: db_lookup[str(l[0])] = l_dict
    # ---------------------------------------------------------------------------

    try:
        comp_id = getattr(parent_view.app, "active_company_id", 1)
        comp = database.get_company(comp_id) if comp_id else database.get_company(1)
        comp_name = comp[1] if comp else "COMPANY NAME"
    except:
        comp_name = "COMPANY NAME"

    export_data = []
    sno_counter = 1

    for child in parent_view.tree.get_children():
        if str(child).startswith("empty_"): continue
        if parent_view.is_bulk_mode and str(child) not in parent_view.selected_items: continue

        l_dict = db_lookup.get(str(child), {})

        def clean_db(k):
            v = l_dict.get(k, "")
            if not v or str(v).lower() in ("none", "unknown", ""): return ""
            return str(v).strip()

        # --- THE FIX: Extract only the Primary Phone Number for the Export! ---
        raw_phone = clean_db("phone")
        primary_phone = raw_phone.split(",")[0].strip() if raw_phone else ""
        
        row_data = {
            "sno": str(sno_counter),
            "photo_path": clean_db("photo_path"),
            "name": clean_db("name"),
            "address": clean_db("address"),
            "phone": primary_phone, 
            "blood_type": clean_db("blood_type"),
            "role": clean_db("role")
        }
        # ----------------------------------------------------------------------
        export_data.append(row_data)
        sno_counter += 1

    if not export_data:
        messagebox.showinfo("Export", "No data to export.")
        return

    if fmt == "csv":
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if path:
            csv_headers = ["Sl No"]
            if selected_fields["Photo"]: csv_headers.append("Photo")
            if selected_fields["Name"]: csv_headers.append("Name")
            if selected_fields["Address"]: csv_headers.append("Address")
            if selected_fields["Ph No"]: csv_headers.append("Ph No")
            if selected_fields["Blood Type"]: csv_headers.append("Blood Type")
            if selected_fields["Role"]: csv_headers.append("Role")

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                for r in export_data:
                    row = [r["sno"]]
                    if selected_fields["Photo"]:
                        p_path = r["photo_path"]
                        row.append("Attached" if p_path and os.path.exists(p_path) else "None")
                    if selected_fields["Name"]: row.append(r["name"])
                    if selected_fields["Address"]: row.append(r["address"])
                    if selected_fields["Ph No"]: row.append(r["phone"])
                    if selected_fields["Blood Type"]: row.append(r["blood_type"])
                    if selected_fields["Role"]: row.append(r["role"])
                    writer.writerow(row)
            messagebox.showinfo("Success", "Exported successfully!")
    else:
        # --- THE FIX: Tagged prefix for the Sweeper ---
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Labour_Report_")
        
        headers_html = "<th>Sl No</th>"
        if selected_fields["Photo"]: headers_html += "<th>Photo</th>"
        if selected_fields["Name"]: headers_html += "<th>Name</th>"
        if selected_fields["Address"]: headers_html += "<th>Address</th>"
        if selected_fields["Ph No"]: headers_html += "<th>Ph No</th>"
        if selected_fields["Blood Type"]: headers_html += "<th>Blood Type</th>"
        if selected_fields["Role"]: headers_html += "<th>Role</th>"

        rows_html = ""
        for r in export_data:
            rows_html += f"<tr><td>{r['sno']}</td>"
            
            if selected_fields["Photo"]:
                p_path = r["photo_path"]
                img_html = ""
                if p_path and os.path.exists(p_path):
                    try:
                        with open(p_path, "rb") as img_file:
                            b64 = base64.b64encode(img_file.read()).decode()
                        img_html = f'<img src="data:image/png;base64,{b64}" style="width:25mm; height:25mm; border:1px solid #ccc; object-fit: cover; display:block; margin:auto;">'
                    except: pass
                rows_html += f"<td>{img_html}</td>"

            if selected_fields["Name"]: rows_html += f"<td>{r['name']}</td>"
            if selected_fields["Address"]: rows_html += f"<td>{r['address']}</td>"
            if selected_fields["Ph No"]: rows_html += f"<td>{r['phone']}</td>"
            if selected_fields["Blood Type"]: rows_html += f"<td>{r['blood_type']}</td>"
            if selected_fields["Role"]: rows_html += f"<td>{r['role']}</td>"
            rows_html += "</tr>"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1 {{ text-align: center; margin-bottom: 5px; color: #0f172a; text-transform: uppercase; }}
                h3 {{ text-align: center; margin-top: 0; color: #475569; font-weight: normal; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; vertical-align: middle; }}
                th {{ background-color: #f8fafc; color: #1e293b; font-weight: bold; white-space: nowrap; }}
            </style>
        </head>
        <body>
            <h1>{comp_name}</h1>
            <h3>Labours & Workers Report</h3>
            <table>
                <tr>{headers_html}</tr>
                {rows_html}
            </table>
            <script>window.print();</script>
        </body>
        </html>
        """
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))
    parent_view.cancel_bulk()

def open_import_window(parent_view):
    file_path = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
    if not file_path: return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file: {e}")
        return
        
    if not rows:
        messagebox.showinfo("Empty", "The selected CSV is empty.")
        return

    pop = tk.Toplevel(parent_view)
    pop.title("Import Preview & Filter")
    pop.geometry("900x600")
    pop.configure(bg=parent_view.colors["bg"])
    pop.grab_set()

    tk.Label(pop, text="Import Preview (Duplicates skipped automatically)", font=("Segoe UI", 16, "bold"), bg=parent_view.colors["bg"], fg=parent_view.colors["text"]).pack(pady=(15, 5))
    
    info_lbl = tk.Label(pop, text="Checking against existing database...", font=("Segoe UI", 11), bg=parent_view.colors["bg"], fg=parent_view.colors["text_sec"])
    info_lbl.pack(pady=(0, 10))

    style = ttk.Style(pop)
    style.configure("Preview.Treeview", font=("Segoe UI", 10), rowheight=30, background=parent_view.colors["bg"], fieldbackground=parent_view.colors["bg"], foreground=parent_view.colors["text"])
    style.configure("Preview.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=parent_view.colors["header"], foreground=parent_view.colors["text"])

    tree_frame = tk.Frame(pop, bg=parent_view.colors["card"], highlightbackground=parent_view.colors["border"], highlightthickness=1)
    tree_frame.pack(fill="both", expand=True, padx=20, pady=10)

    scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
    tree = ttk.Treeview(tree_frame, columns=("status", "name", "phone", "role", "address"), show="headings", yscrollcommand=scroll_y.set, style="Preview.Treeview")
    scroll_y.config(command=tree.yview)

    tree.heading("status", text="STATUS")
    tree.heading("name", text="NAME")
    tree.heading("phone", text="PHONE")
    tree.heading("role", text="ROLE")
    tree.heading("address", text="ADDRESS")
    
    comp_id_val = getattr(parent_view.app, "active_company_id", 1)
    try:
        import json
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"labour_staging_cols_{comp_id_val}",))
        res = c.fetchone()
        conn.close()
        s_w = json.loads(res[0]) if res and res[0] else {}
    except:
        s_w = {}

    tree.column("status", width=s_w.get("status", 150), anchor="center")
    tree.column("name", width=s_w.get("name", 200))
    tree.column("phone", width=s_w.get("phone", 150))
    tree.column("role", width=s_w.get("role", 120))
    tree.column("address", width=s_w.get("address", 200))

    def save_staging_widths():
        new_w = {c: tree.column(c, "width") for c in tree["columns"]}
        try:
            import json
            # --- THE FIX: Use safe helper to attach ACTIVE_COMPANY_ID and prevent ghost data! ---
            database.save_ui_setting(f"labour_staging_cols_{comp_id_val}", json.dumps(new_w))
            # ------------------------------------------------------------------------------------
        except: pass

    def on_staging_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            pop.after(50, save_staging_widths)

    tree.bind("<B1-Motion>", on_staging_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_staging_widths) if tree.identify_region(e.x, e.y) == "separator" else None, add="+")
    
    scroll_y.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    
    tree.tag_configure("new", background=parent_view.colors["card"], foreground=parent_view.colors["text"])
    
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    if is_dark: tree.tag_configure("dup", background="#450a0a", foreground="#fca5a5") 
    else: tree.tag_configure("dup", background="#fee2e2", foreground="#991b1b") 

    # --- THE FIX: Safe dict extraction without PRAGMA ---
    existing_labours = database.get_all_labours()
    existing_names = set()
    existing_phones = set()
    
    for l in existing_labours:
        l_dict = database.get_labour_dict(l[0])
        if not l_dict: continue
        if l_dict.get('name'): existing_names.add(str(l_dict['name']).strip().lower())
        if l_dict.get('phone'):
            for p in str(l_dict['phone']).split(','):
                if p.strip(): existing_phones.add(p.strip().lower())
    # ----------------------------------------------------

    valid_rows = []
    dup_count = 0
    new_count = 0

    for r in rows:
        r_keys = {k.lower().strip(): k for k in r.keys() if k}
        
        name_key = next((k for k in r_keys if 'name' in k), None)
        name_val = r[r_keys[name_key]].strip() if name_key and r[r_keys[name_key]] else ""
        
        phone_key = next((k for k in r_keys if 'phone' in k or 'ph no' in k or 'contact' in k), None)
        phone_val = r[r_keys[phone_key]].strip() if phone_key and r[r_keys[phone_key]] else ""
        
        role_key = next((k for k in r_keys if 'role' in k or 'designation' in k), None)
        role_val = r[r_keys[role_key]].strip() if role_key and r[r_keys[role_key]] else ""
        
        addr_key = next((k for k in r_keys if 'address' in k), None)
        addr_val = r[r_keys[addr_key]].strip() if addr_key and r[r_keys[addr_key]] else ""
        
        blood_key = next((k for k in r_keys if 'blood' in k), None)
        blood_val = r[r_keys[blood_key]].strip() if blood_key and r[r_keys[blood_key]] else "Unknown"
        
        if phone_val:
            cleaned_phones = []
            for p in phone_val.split(','):
                raw = p.replace("-", "")
                clean = ''.join(c for c in raw if c.isdigit())
                if len(clean) > 10: clean = clean[:10]
                fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
                if fmt: cleaned_phones.append(fmt)
            phone_val = ", ".join(cleaned_phones)

        if not name_val and not phone_val: continue
            
        is_dup = False
        if name_val and name_val.lower() in existing_names:
            is_dup = True
        if phone_val:
            for p in phone_val.split(','):
                if p.strip().lower() in existing_phones:
                    is_dup = True
                    break
                    
        if is_dup:
            status = "Duplicate (Skipping)"
            tag = "dup"
            dup_count += 1
        else:
            status = "New (Will Import)"
            tag = "new"
            new_count += 1
            valid_rows.append((name_val, phone_val, addr_val, blood_val, role_val))
            
            if name_val:
                existing_names.add(name_val.lower())
            if phone_val:
                for p in phone_val.split(','):
                    if p.strip(): existing_phones.add(p.strip().lower())
            
        tree.insert("", "end", values=(status, name_val, phone_val, role_val, addr_val), tags=(tag,))

    info_lbl.config(text=f"Found {new_count} new workers and {dup_count} duplicates.")

    def confirm_import():
        if not valid_rows:
            messagebox.showinfo("Nothing to import", "No new records found to import.", parent=pop)
            pop.destroy()
            return
            
        success = 0
        for r_data in valid_rows:
            name, phone, addr, blood, role = r_data
            try:
                database.add_labour(name, phone, addr, blood, role, "", "[]")
                success += 1
            except: pass
            
        messagebox.showinfo("Success", f"Successfully imported {success} workers!", parent=pop)
        
        if hasattr(parent_view, 'search_entry'):
            parent_view.search_entry.delete('0', 'end')
            parent_view.search_entry.insert(0, 'Search Name/Role/Phone...')
            
        parent_view.load_data()
        pop.destroy()

    btn_f = tk.Frame(pop, bg=parent_view.colors["bg"])
    btn_f.pack(fill="x", pady=(0, 20), padx=20)
    
    tk.Button(btn_f, text="Cancel", font=("Segoe UI", 11, "bold"), bg=parent_view.colors["border"], fg=parent_view.colors["text"], relief="flat", cursor="hand2", padx=20, pady=8, command=pop.destroy).pack(side="left")
    
    tk.Button(btn_f, text=f"Confirm Import ({new_count})", font=("Segoe UI", 11, "bold"), bg=parent_view.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=confirm_import).pack(side="right")