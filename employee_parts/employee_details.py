import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json
import tempfile
import webbrowser
import base64
from datetime import date

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    pass

# --- Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
# --------------------------------------

import database
from views.invoice_parts.helpers import format_currency, enable_copy_paste, fetch_global_settings, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar

# --- THE FIX: Centralized ID Card Generator ---
def get_id_card_css():
    return """
        @media print { @page { margin: 0.5cm; size: auto; } body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
        body { display: flex; flex-wrap: wrap; justify-content: center; padding: 20px; font-family: 'Arial', sans-serif; background: #f1f5f9; gap: 30px; }
        .id-card { width: 270px; height: 410px; background: white; border: 2px solid #cbd5e1; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; padding: 25px 20px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; position: relative; overflow: hidden; page-break-inside: avoid; }
        .header-bar { position: absolute; top: 0; left: 0; width: 100%; height: 10px; background: #3b82f6; }
        .header-bar.red { background: #ef4444; }
        .company { font-size: 19px; font-weight: 900; color: #0f172a; margin-bottom: 30px; text-transform: uppercase; letter-spacing: 0.5px; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; padding: 0 5px; box-sizing: border-box; }
        .photo-container { width: 140px; height: 160px; border: 3px solid #e2e8f0; margin-bottom: 25px; background: #f8fafc; display: flex; justify-content: center; align-items: center; overflow: hidden; border-radius: 8px; }
        .photo-container img { width: 100%; height: 100%; object-fit: cover; }
        .no-photo { font-size: 60px; color: #94a3b8; }
        .name { font-size: 24px; font-weight: bold; color: #1e293b; margin-bottom: 2px; line-height: 1.1; }
        .worker-id { font-size: 13px; font-weight: bold; color: #64748b; margin-bottom: 8px; letter-spacing: 1px; }
        .role { font-size: 16px; font-weight: bold; color: #3b82f6; text-transform: uppercase; letter-spacing: 1px; }
        .sign-box { margin-top: auto; width: 100%; text-align: right; padding-right: 5px; }
        .sign-line { display: inline-block; border-top: 1px dashed #64748b; font-size: 10px; color: #64748b; padding-top: 4px; width: 100px; text-align: center; margin-bottom: -5px; }
        .back-title { margin-top: 25px; font-size: 15px; font-weight: bold; color: #3b82f6; letter-spacing: 1px; text-transform: uppercase; }
        .back-text { font-size: 18px; font-weight: bold; color: #1e293b; margin-top: 5px; }
        .emerg-val { color: #ef4444; font-size: 22px; }
    """

def generate_id_card_html(comp_name, comp_logo_html, comp_phone, emp_name, emp_id_str, img_html, role_html, emerg_html, blood_html):
    return f"""
    <div class="id-card">
        <div class="header-bar"></div>
        <div class="company" style="margin-bottom: 15px;">{comp_logo_html}{comp_name}</div>
        <div class="photo-container" style="margin-bottom: 15px;">{img_html}</div>
        <div class="name">{emp_name}</div>
        <div class="worker-id">ID: {emp_id_str}</div>
        {role_html}
        <div class="sign-box"><div class="sign-line">Auth. Signatory</div></div>
    </div>
    
    <div class="id-card">
        <div class="header-bar red"></div>
        <div class="back-title" style="margin-top: 25px;">EMERGENCY CONTACT</div>
        <div class="back-text emerg-val">{emerg_html}</div>
        <div class="back-title" style="margin-top: 15px;">BLOOD GROUP</div>
        <div class="back-text" style="color: #ef4444; font-size: 24px;">{blood_html}</div>
        
        <div style="margin-top: auto; padding: 15px 10px; background: #f8fafc; border-radius: 8px; width: 100%; box-sizing: border-box; border: 1px solid #e2e8f0;">
            <div style="font-size: 11px; color: #475569; font-weight: bold; margin-bottom: 5px;">TERMS OF USE</div>
            <div style="font-size: 10px; color: #64748b; line-height: 1.3; margin-bottom: 10px;">This card is property of {comp_name}. It is non-transferable and must be presented upon request.</div>
            <div style="font-size: 11px; color: #475569; font-weight: bold; margin-bottom: 3px;">IF FOUND, RETURN TO:</div>
            <div style="font-size: 11px; color: #0f172a; font-weight: bold;">{comp_name}</div>
            <div style="font-size: 10px; color: #64748b; margin-top: 2px;">Phone: {comp_phone}</div>
        </div>
    </div>
    """
# -----------------------------------------------

def open_status_dialog(parent, emp_id, emp_name, status, date_fmt_code, refresh_cb, undo_cb=None):
    comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
    allowed, err_msg = database.check_employee_permission(action="pay", company_id=comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=parent)
        return

    from views.home_parts.ui_components import get_theme
    t = get_theme()
    BG_COLOR = t["bg"]
    CARD_BG = t["card"]
    BORDER_COLOR = t["border"]
    TEXT_PRIMARY = t["text"]
    TEXT_SECONDARY = t["sec"]
    ACCENT_BLUE = t["accent_blue"]

    pop = tk.Toplevel(parent); pop.title(f"Mark {status}"); pop.geometry("380x280"); pop.configure(bg=BG_COLOR); pop.grab_set()
    date_var = tk.StringVar(value=date.today().strftime(date_fmt_code))
    tk.Label(pop, text=f"Mark as {status}", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(15,5))
    tk.Label(pop, text=f"Employee: {emp_name}", font=("Arial", 10), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(0, 15))
    f = tk.Frame(pop, bg=BG_COLOR); f.pack(fill="both", expand=True, padx=20)
    tk.Label(f, text="Effective Date", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
    d_f = tk.Frame(f, bg=BG_COLOR); d_f.grid(row=1, column=0, sticky="w", pady=(5, 15))
    d_ent = tk.Entry(d_f, textvariable=date_var, font=("Arial", 11), width=15, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    d_ent.pack(side="left", ipady=4); enable_copy_paste(d_ent)
    tk.Button(d_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, date_var)).pack(side="left", padx=5)

    def save_status():
        try:
            # --- THE FIX: Capture the phantom payment record for Undo! ---
            old_row = database.get_employee_full_record(emp_id)
            database.mark_employee_status(emp_id, status, date_var.get())
            
            # --- THE FIX: MVC Compliant Fetch ---
            last_pay_id = database.get_employee_last_payment_id(emp_id)
            new_row = database.get_employee_full_record(emp_id)
            
            if undo_cb: 
                if last_pay_id: undo_cb("ADD_PAY", last_pay_id) # Queue the log for deletion
            # ------------------------------------
                undo_cb("EDIT_EMP", (old_row, new_row))      # Queue the status revert
                
            database.log_audit("Employees", "Status Changed", record_ref=emp_name, details=f"Employee marked as {status}.", company_id=comp_id)
            messagebox.showinfo("Success", f"Employee marked as {status}!", parent=parent)
            if refresh_cb: refresh_cb()
            pop.destroy()
        except Exception as e: messagebox.showerror("Error", str(e), parent=pop)

    tk.Button(pop, text="💾 Save Status", font=("Arial", 11, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=save_status).pack(side="right", padx=20, pady=20)

def view_employee_details(parent, emp_id, curr_fmt):
    from views.home_parts.ui_components import get_theme
    t = get_theme()
    BG_COLOR = t["bg"]
    CARD_BG = t["card"]
    BORDER_COLOR = t["border"]
    TEXT_PRIMARY = t["text"]
    TEXT_SECONDARY = t["sec"]
    ACCENT_BLUE = t["accent_blue"]

    emp = database.get_employee_dict(emp_id)
    if not emp: return
    
    app = parent.winfo_toplevel()
    try:
        comp_id = getattr(app, "active_company_id", 1)
        comp = database.get_company(comp_id) if comp_id else database.get_company(1)
        comp_name = comp[1] if comp else "COMPANY NAME"
        _, date_fmt_code = fetch_global_settings(comp_id)
    except:
        comp_name = "COMPANY NAME"
        date_fmt_code = "%d.%m.%Y"
        comp = None

    pop = tk.Toplevel(parent)
    pop.title(f"Details: {emp.get('name')}")
    pop.geometry("460x650")
    pop.configure(bg=BG_COLOR)
    
    tk.Label(pop, text="Employee Full Details", font=("Arial", 18, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(20, 10), padx=20, anchor="w")
    
    emp_photo = emp.get('photo_path')

    em_contact = "—"
    address = "—"
    bank_name = "—"
    bank_acct = "—"
    ifsc = "—"
    upi = "—"
    blood_type = "Unknown"
    emp_id_str = f"EMP-{int(emp_id):04d}" 
    
    emp_docs = []
    
    docs_json = emp.get('docs_json')
    if docs_json:
        try:
            parsed = json.loads(docs_json)
            if isinstance(parsed, dict):
                em_contact = parsed.get("emergency_contact", "—")
                address = parsed.get("address", "—")
                bank_name = parsed.get("bank_name", "—")
                bank_acct = parsed.get("bank_account", "—")
                ifsc = parsed.get("ifsc_code", "—")
                upi = parsed.get("upi_id", "—")
                blood_type = parsed.get("blood_type", "Unknown")
                
                raw_docs = parsed.get("docs", [])
                if isinstance(raw_docs, str):
                    try:
                        import ast
                        rec = ast.literal_eval(raw_docs)
                        emp_docs = rec if isinstance(rec, list) else [{"path": raw_docs, "desc": "Doc"}]
                    except: emp_docs = [{"path": raw_docs, "desc": "Doc"}]
                elif isinstance(raw_docs, list):
                    emp_docs = raw_docs
                
                if parsed.get("emp_id_str"):
                    emp_id_str = parsed.get("emp_id_str")
            elif isinstance(parsed, list):
                emp_docs = parsed
        except: pass

    if not emp_docs and emp.get('document_path') and os.path.exists(emp.get('document_path')):
        emp_docs.append({"path": emp.get('document_path'), "desc": "Legacy Attached File"})

    def print_id_card():
        comp_logo = comp[10] if comp and len(comp) > 10 else ""
        comp_logo_html = ""
        if comp_logo and os.path.exists(comp_logo):
            try:
                with open(comp_logo, "rb") as l_file:
                    comp_logo_html = f'<img src="data:image/png;base64,{base64.b64encode(l_file.read()).decode()}" style="max-height: 35px; max-width: 150px; margin-bottom: 5px; object-fit: contain;"><br>'
            except: pass

        img_html = ""
        if emp_photo and os.path.exists(emp_photo):
            try:
                with open(emp_photo, "rb") as img_file:
                    b64_string = base64.b64encode(img_file.read()).decode()
                import mimetypes
                mime_type, _ = mimetypes.guess_type(emp_photo)
                if not mime_type: mime_type = "image/png"
                img_html = f'<img src="data:{mime_type};base64,{b64_string}" alt="Photo">'
            except:
                img_html = '<div class="no-photo">👤</div>'
        else:
            img_html = '<div class="no-photo">👤</div>'

        raw_role = str(emp.get('role', '')).strip()
        role_html = f'<div class="role">{raw_role}</div>' if raw_role and raw_role.lower() not in ("none", "unknown") else ''

        emerg_raw = em_contact
        if not emerg_raw or emerg_raw == "—": emerg_html = "N/A"
        else: 
            e_parts = [p.strip() for p in str(emerg_raw).split(",") if p.strip()]
            emerg_html = "<br>".join(e_parts)
            if len(e_parts) > 1: emerg_html = f"<span style='font-size: 18px; line-height: 1.2;'>{emerg_html}</span>"
            
        blood_html = blood_type

        # --- THE FIX: Route through Centralized Generator ---
        comp_phone = comp[4] if comp and len(comp) > 4 and comp[4] else "Head Office"
        cards = generate_id_card_html(comp_name, comp_logo_html, comp_phone, emp.get('name', 'Unknown'), emp_id_str, img_html, role_html, emerg_html, blood_html)
        
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>ID Card - {emp.get('name', 'Unknown')}</title>
            <style>{get_id_card_css()}</style>
        </head>
        <body>
            {cards}
            <script>window.onload = function() {{ window.print(); }}</script>
        </body>
        </html>
        """
        # ----------------------------------------------------
        
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Emp_ID_Card_")
        with os.fdopen(fd, 'w', encoding='utf-8') as html_file:
            html_file.write(html_content)
        webbrowser.open('file://' + os.path.realpath(path))
        
        # --- THE FIX: Detach the timer from the popup so it fires safely ---
        parent.after(5000, lambda p=path: os.remove(p) if os.path.exists(p) else None)
        # -------------------------------------------------------------------

    btn_print = tk.Button(pop, text="🪪 Print ID Card", font=("Arial", 11, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", pady=10, command=print_id_card)
    btn_print.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

    container = tk.Frame(pop, bg=BG_COLOR)
    container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    style = ttk.Style(pop)
    style.theme_use("default")
    # --- THE FIX: Thick Solid Scrollbar Styles! ---
    style.configure("Details.Vertical.TScrollbar", background=TEXT_SECONDARY, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=TEXT_PRIMARY, relief="flat")
    style.map("Details.Vertical.TScrollbar", background=[("active", ACCENT_BLUE)])
    # ----------------------------------------------

    canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Details.Vertical.TScrollbar")
    
    f = tk.Frame(canvas, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
    
    f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=f, anchor="nw")
    
    def configure_canvas(event):
        canvas.itemconfig(canvas_window, width=event.width)
    canvas.bind("<Configure>", configure_canvas)

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        multiplier = int(-1*(event.delta/120)*2) if os.name == 'nt' else int(-1*event.delta)
        canvas.yview_scroll(multiplier, "units")
        
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    photo_f = tk.Frame(f, bg=CARD_BG)
    photo_f.grid(row=0, column=0, columnspan=2, pady=(0, 20))
    
    photo_lbl = tk.Label(photo_f, bg=CARD_BG, highlightthickness=0, bd=0)
    photo_lbl.pack()
    
    if emp_photo and os.path.exists(emp_photo):
        try:
            img = Image.open(emp_photo).convert("RGBA")
            img = ImageOps.fit(img, (120, 120), method=Image.Resampling.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            photo_lbl.config(image=photo_img, bd=2, relief="solid")
            photo_lbl.image = photo_img
        except:
            photo_lbl.config(text="👤", font=("Arial", 48), fg=TEXT_SECONDARY, width=3, height=1)
    else:
        photo_lbl.config(text="👤", font=("Arial", 48), fg=TEXT_SECONDARY, width=3, height=1)

    dob = smart_date_formatter(emp.get('dob'), date_fmt_code) if emp.get('dob') else "—"
    resign_dt = smart_date_formatter(emp.get('resign_date'), date_fmt_code) if emp.get('resign_date') else "—"
    rejoin_dt = smart_date_formatter(emp.get('rejoin_date'), date_fmt_code) if emp.get('rejoin_date') else "—"
    join_dt = smart_date_formatter(emp.get('join_date'), date_fmt_code) if emp.get('join_date') else "—"

    labels = [
        ("Employee ID:", emp_id_str), 
        ("Name:", emp.get('name')), 
        ("Role:", emp.get('role')), 
        ("Join Date:", join_dt), 
        ("Date of Birth:", dob), 
        ("Resign Date:", resign_dt), 
        ("Rejoin Date:", rejoin_dt), 
        ("Current Salary:", format_currency(emp.get('salary', 0), curr_fmt)), 
        ("Primary Phone:", emp.get('phone')), 
        ("Alternate Phone:", emp.get('alt_phone')),
        ("Emergency Contact:", em_contact),
        ("Home Address:", address),
        ("Bank Name:", bank_name),
        ("Bank A/C No:", bank_acct),
        ("IFSC Code:", ifsc),
        ("UPI ID:", upi)
    ]
    
    for i, (lbl, val) in enumerate(labels, start=1):
        tk.Label(f, text=lbl, font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=i, column=0, sticky="ne", pady=8, padx=(0,15))
        val_str = val if val and str(val).strip() else "—"
        tk.Label(f, text=val_str, font=("Arial", 11), bg=CARD_BG, fg=TEXT_PRIMARY, wraplength=230, justify="left").grid(row=i, column=1, sticky="w", pady=8)

    if emp_docs:
        doc_row = len(labels) + 1
        tk.Label(f, text="Documents:", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=doc_row, column=0, sticky="ne", pady=8, padx=(0,15))
        doc_f = tk.Frame(f, bg=CARD_BG)
        doc_f.grid(row=doc_row, column=1, sticky="w", pady=8)
        
        for d in emp_docs:
            path = d.get("path", "") if isinstance(d, dict) else str(d)
            if isinstance(path, str): path = path.strip("[]'\" ")
            
            if path and os.path.exists(path):
                row_f = tk.Frame(doc_f, bg=BG_COLOR, pady=4, padx=8, highlightbackground=BORDER_COLOR, highlightthickness=1)
                row_f.pack(fill="x", pady=2)
                
                ext = os.path.splitext(path)[1].lower()
                if ext == '.pdf': icon = "📄"
                elif ext in ['.jpg', '.jpeg', '.png']: icon = "🖼️"
                elif ext in ['.doc', '.docx']: icon = "📝"
                elif ext in ['.xls', '.xlsx', '.csv']: icon = "📊"
                else: icon = "📁"
                
                tk.Label(row_f, text=f"{icon} {os.path.basename(path)[:20]}", font=("Arial", 9), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(side="left", padx=5)
                
                def view_doc(p=path):
                    try: os.startfile(p)
                    except: webbrowser.open(p)
                    
                tk.Button(row_f, text="👁️ View", font=("Arial", 8, "bold"), bg=ACCENT_BLUE, fg="white", relief="flat", cursor="hand2", command=view_doc).pack(side="right", padx=5)


def print_bulk_employee_ids(parent, selected_ids):
    if not selected_ids: return

    app = parent.winfo_toplevel()
    try:
        comp_id = getattr(app, "active_company_id", 1)
        comp = database.get_company(comp_id) if comp_id else database.get_company(1)
        comp_name = comp[1] if comp else "COMPANY NAME"
        comp_phone = comp[4] if comp and len(comp) > 4 and comp[4] else "Head Office"
    except:
        comp_name = "COMPANY NAME"
        comp_phone = "Head Office"
        comp = None

    comp_logo = comp[10] if comp and len(comp) > 10 else ""
    comp_logo_html = ""
    if comp_logo and os.path.exists(comp_logo):
        try:
            with open(comp_logo, "rb") as l_file:
                comp_logo_html = f'<img src="data:image/png;base64,{base64.b64encode(l_file.read()).decode()}" style="max-height: 35px; max-width: 150px; margin-bottom: 5px; object-fit: contain;"><br>'
        except: pass

    # --- THE FIX: Route through Centralized Generator ---
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Bulk ID Cards</title>
        <style>{get_id_card_css()}</style>
    </head>
    <body>
    """

    for emp_id in selected_ids:
        emp = database.get_employee_dict(int(emp_id))
        if not emp: continue

        emp_photo = emp.get('photo_path')
        img_html = '<div class="no-photo">👤</div>'
        if emp_photo and os.path.exists(emp_photo):
            try:
                import mimetypes
                with open(emp_photo, "rb") as img_file:
                    b64_string = base64.b64encode(img_file.read()).decode()
                mime_type, _ = mimetypes.guess_type(emp_photo)
                if not mime_type: mime_type = "image/png"
                img_html = f'<img src="data:{mime_type};base64,{b64_string}" alt="Photo">'
            except: pass

        emp_id_str = f"EMP-{int(emp_id):04d}"
        em_contact = "—"
        blood_type = "Unknown"
        
        docs_json = emp.get('docs_json')
        if docs_json:
            try:
                parsed = json.loads(docs_json)
                if isinstance(parsed, dict):
                    em_contact = parsed.get("emergency_contact", "—")
                    blood_type = parsed.get("blood_type", "Unknown")
                    if parsed.get("emp_id_str"):
                        emp_id_str = parsed.get("emp_id_str")
            except: pass

        raw_role = str(emp.get('role', '')).strip()
        role_html = f'<div class="role">{raw_role}</div>' if raw_role and raw_role.lower() not in ("none", "unknown") else ''

        emerg_raw = em_contact
        if not emerg_raw or emerg_raw == "—": emerg_html = "N/A"
        else: 
            e_parts = [p.strip() for p in str(emerg_raw).split(",") if p.strip()]
            emerg_html = "<br>".join(e_parts)
            if len(e_parts) > 1: emerg_html = f"<span style='font-size: 18px; line-height: 1.2;'>{emerg_html}</span>"

        html_content += generate_id_card_html(comp_name, comp_logo_html, comp_phone, emp.get('name', 'Unknown'), emp_id_str, img_html, role_html, emerg_html, blood_type)

    html_content += """
    </body>
    <script>window.onload = function() { window.print(); }</script>
    </html>
    """
    # ----------------------------------------------------
    
    fd, path = tempfile.mkstemp(suffix=".html", prefix="Bulk_Emp_ID_Cards_")
    with os.fdopen(fd, 'w', encoding='utf-8') as html_file:
        html_file.write(html_content)
    webbrowser.open('file://' + os.path.realpath(path))
    
    # --- THE FIX: 5-Second Silent Self-Destruct ---
    parent.after(5000, lambda p=path: os.remove(p) if os.path.exists(p) else None)
    # ----------------------------------------------