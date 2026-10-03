import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import os
import sys
import json
import csv
import shutil
import time
import random
import webbrowser
import re
from datetime import date, datetime, timedelta

try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps
except ImportError:
    pass

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    views_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, enable_copy_paste, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar
from settings_parts.interactive_cropper import InteractiveCropper

# Global fallbacks (Shadowed dynamically inside functions below)
BG_COLOR = "#0f172a"
CARD_BG = "#1e293b"
BORDER_COLOR = "#334155"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_YELLOW = "#f59e0b"
ACCENT_BLUE = "#3b82f6"


def open_employee_dialog(parent, emp_id=None, date_fmt_code="%d.%m.%Y", refresh_cb=None, undo_cb=None, widget=None):
    from views.home_parts.ui_components import get_theme
    t = get_theme()
    BG_COLOR = t["bg"]
    CARD_BG = t["card"]
    BORDER_COLOR = t["border"]
    TEXT_PRIMARY = t["text"]
    TEXT_SECONDARY = t["sec"]
    ACCENT_GREEN = t["accent_green"]
    ACCENT_RED = t["error"]
    ACCENT_BLUE = t["accent_blue"]

    pop = tk.Toplevel(parent)
    pop.title("Add Employee" if not emp_id else "Edit Employee")
    pop.configure(bg=BG_COLOR)
    pop.grab_set()

    pop_w, pop_h = 760, 650
    if widget:
        x = widget.winfo_rootx() - pop_w - 10
        y = widget.winfo_rooty()
        pop.geometry(f"{pop_w}x{pop_h}+{max(0, x)}+{max(0, y)}")
    else:
        pop.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()//2) - (pop_w//2)
        y = parent.winfo_rooty() + (parent.winfo_height()//2) - (pop_h//2)
        pop.geometry(f"{pop_w}x{pop_h}+{max(0, x)}+{max(0, y)}")

    name_var = tk.StringVar(pop); phone_var = tk.StringVar(pop); alt_phone_var = tk.StringVar(pop)
    role_var = tk.StringVar(pop); salary_var = tk.StringVar(pop, value="0"); photo_path_var = tk.StringVar(pop)
    join_date_var = tk.StringVar(pop, value=date.today().strftime(date_fmt_code))
    dob_var = tk.StringVar(pop)
    blood_type_var = tk.StringVar(pop, value="Unknown")
    emergency_contact_var = tk.StringVar(pop)
    emp_id_var = tk.StringVar(pop)
    
    bank_name_var = tk.StringVar(pop)
    bank_var = tk.StringVar(pop)
    ifsc_var = tk.StringVar(pop)
    upi_var = tk.StringVar(pop)
    branch_var = tk.StringVar(pop)
    address_val = ""
    
    current_docs = []

    pop.bind("<ButtonPress-1>", lambda e: pop.focus_set() if e.widget.winfo_class() not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button') else None, add="+")

    comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)

    if emp_id:
        emp = database.get_employee_dict(emp_id)
        if emp:
            name_var.set(emp.get('name', ''))
            phone_var.set(emp.get('phone', ''))
            alt_phone_var.set(emp.get('alt_phone', ''))
            role_var.set(emp.get('role', ''))
            salary_var.set(str(emp.get('salary', 0)))
            join_date_var.set(smart_date_formatter(emp.get('join_date', ''), date_fmt_code))
            photo_path_var.set(emp.get('photo_path', ''))
            dob_var.set(smart_date_formatter(emp.get('dob', ''), date_fmt_code))
            
            docs_json = emp.get('docs_json')
            if docs_json: 
                try: 
                    parsed = json.loads(docs_json)
                    if isinstance(parsed, dict):
                        raw_docs = parsed.get("docs", [])
                        if isinstance(raw_docs, str):
                            try:
                                import ast
                                rec = ast.literal_eval(raw_docs)
                                current_docs = rec if isinstance(rec, list) else [{"path": raw_docs, "desc": "Doc"}]
                            except: current_docs = [{"path": raw_docs, "desc": "Doc"}]
                        elif isinstance(raw_docs, list):
                            current_docs = raw_docs
                            
                        current_docs = [{"path": str(p).strip("[]'\" "), "desc": "Doc"} if not isinstance(p, dict) else p for p in current_docs]
                        
                        blood_type_var.set(parsed.get("blood_type", "Unknown"))
                        emergency_contact_var.set(parsed.get("emergency_contact", ""))
                        address_val = parsed.get("address", "")
                        bank_name_var.set(parsed.get("bank_name", ""))
                        bank_var.set(parsed.get("bank_account", ""))
                        ifsc_var.set(parsed.get("ifsc_code", ""))
                        branch_var.set(parsed.get("branch", ""))
                        upi_var.set(parsed.get("upi_id", ""))
                        emp_id_var.set(parsed.get("emp_id_str", ""))
                    elif isinstance(parsed, list):
                        current_docs = [{"path": str(p).strip("[]'\" "), "desc": "Doc"} if not isinstance(p, dict) else p for p in parsed]
                except: pass
            elif emp.get('document_path') and os.path.exists(emp.get('document_path')):
                current_docs.append({"path": emp.get('document_path'), "desc": "Legacy Attached File"})
                
            if not emp_id_var.get():
                emp_id_var.set(f"EMP-{int(emp_id):04d}")
    else:
        pref = database.get_ui_setting(f"emp_prefix_{comp_id}", "EMP-")
        try: seq = int(database.get_ui_setting(f"emp_seq_{comp_id}", "1"))
        except: seq = 1
        
        # --- THE FIX: Use optimized backend helper for instant scaling ---
        existing = [e[1] for e in database.get_all_employee_id_strings()]
        while f"{pref}{seq:04d}".lower() in existing:
            seq += 1
        # ---------------------------------------------------------------
            
        emp_id_var.set(f"{pref}{seq:04d}")

    tk.Label(pop, text="Add Employee" if not emp_id else "Edit Employee", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=15)
    
    bottom_wrapper = tk.Frame(pop, bg=BG_COLOR)
    bottom_wrapper.pack(side="bottom", fill="x")
    tk.Frame(bottom_wrapper, bg=BORDER_COLOR, height=1).pack(fill="x", padx=20, pady=(15, 10))

    container = tk.Frame(pop, bg=BG_COLOR)
    container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    style = ttk.Style(pop)
    style.theme_use("default")
    style.configure("Dialog.Vertical.TScrollbar", background=TEXT_SECONDARY, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=TEXT_PRIMARY, relief="flat")
    style.map("Dialog.Vertical.TScrollbar", background=[("active", ACCENT_BLUE)])

    canvas = tk.Canvas(container, bg=BG_COLOR, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Dialog.Vertical.TScrollbar")
    
    main_f = tk.Frame(canvas, bg=BG_COLOR)
    
    main_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=main_f, anchor="nw")
    
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

    left_f = tk.Frame(main_f, bg=BG_COLOR, width=180); left_f.pack(side="left", fill="y", padx=(0, 20))
    
    photo_lbl = tk.Label(left_f, bg=CARD_BG, text="Click to\nAdd Photo", font=("Arial", 10), fg=TEXT_SECONDARY, cursor="hand2", highlightbackground=BORDER_COLOR, highlightthickness=1)
    photo_lbl.pack(pady=10); photo_lbl.config(width=18, height=9) 
    
    def update_photo_preview(*args):
        path = photo_path_var.get()
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                img = ImageOps.fit(img, (140, 140), method=Image.Resampling.LANCZOS)
                mask = Image.new('L', (420, 420), 0); draw = ImageDraw.Draw(mask); draw.ellipse((0, 0, 420, 420), fill=255)
                mask = mask.resize((140, 140), Image.Resampling.LANCZOS)
                img_circle = Image.new('RGBA', (140, 140), (0, 0, 0, 0))
                img_circle.paste(img, (0, 0), mask=mask)
                photo_img = ImageTk.PhotoImage(img_circle)
                photo_lbl.config(image=photo_img, text="", width=140, height=140, highlightthickness=0, bd=0)
                photo_lbl.image = photo_img
            except: pass

    def browse_photo(e):
        path = filedialog.askopenfilename(parent=pop, title="Select Employee Photo", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        pop.lift(); pop.focus_force()
        if path: 
            InteractiveCropper(pop, path, lambda final_path: [
                photo_path_var.set(final_path), 
                update_photo_preview(),
                pop.lift(),
                pop.focus_force()
            ])

    photo_lbl.bind("<Button-1>", browse_photo)
    if photo_path_var.get(): update_photo_preview()

    right_f = tk.Frame(main_f, bg=BG_COLOR); right_f.pack(side="left", fill="both", expand=True)
    def focus_next(event): event.widget.tk_focusNext().focus(); return "break"

    # Fetch all existing IDs once for real-time validation
    all_existing_ids = database.get_all_employee_id_strings()

    id_container = tk.Frame(right_f, bg=BG_COLOR)
    id_container.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
    
    id_frame = tk.Frame(id_container, bg=BG_COLOR)
    id_frame.pack(anchor="w")

    tk.Label(id_frame, text="Employee ID NO.", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(side="left", padx=(0, 10))
    
    id_ent = tk.Entry(id_frame, textvariable=emp_id_var, font=("Arial", 11, "bold"), width=15, bg=CARD_BG, fg=ACCENT_BLUE, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    id_ent.pack(side="left", ipady=3)

    # Real-time Warning Label
    warn_lbl = tk.Label(id_container, text="⚠️ Employee ID already exists!", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=ACCENT_RED)

    def check_emp_id(*args):
        eid = emp_id_var.get().strip().lower()
        if not eid:
            warn_lbl.pack_forget()
            return
        is_dup = any((str(r_id) != str(emp_id) and e_str == eid) for r_id, e_str in all_existing_ids)
        if is_dup:
            warn_lbl.pack(anchor="w", padx=115, pady=(2, 0))
        else:
            warn_lbl.pack_forget()

    emp_id_var.trace_add("write", check_emp_id)
    
    def open_id_format():
        f_pop = tk.Toplevel(pop)
        f_pop.title("ID Format")
        f_pop.geometry("300x250")
        f_pop.configure(bg=BG_COLOR)
        f_pop.grab_set()
        
        prefix_key = f"emp_prefix_{comp_id}"
        seq_key = f"emp_seq_{comp_id}"
        
        tk.Label(f_pop, text="Prefix (e.g., EMP-, STF-):", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(15,2))
        pref_var = tk.StringVar(value=database.get_ui_setting(prefix_key, "EMP-"))
        tk.Entry(f_pop, textvariable=pref_var, font=("Arial", 11), bg=CARD_BG, fg=TEXT_PRIMARY).pack(ipady=4)
        
        tk.Label(f_pop, text="Next Sequence Number:", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(15,2))
        seq_var = tk.StringVar(value=database.get_ui_setting(seq_key, "1"))
        tk.Entry(f_pop, textvariable=seq_var, font=("Arial", 11), bg=CARD_BG, fg=TEXT_PRIMARY).pack(ipady=4)
        
        def save_fmt():
            pref = pref_var.get()
            try: seq = int(seq_var.get())
            except: seq = 1
            
            # --- THE FIX: Use optimized backend helper for instant scaling ---
            existing = [e[1] for e in database.get_all_employee_id_strings()]
            while f"{pref}{seq:04d}".lower() in existing:
                seq += 1
            # ---------------------------------------------------------------
            
            database.save_ui_setting(prefix_key, pref)
            database.save_ui_setting(seq_key, str(seq))
            emp_id_var.set(f"{pref}{seq:04d}")
            f_pop.destroy()
            
        tk.Button(f_pop, text="Save Format", bg=ACCENT_BLUE, fg="white", font=("Arial", 10, "bold"), command=save_fmt).pack(pady=20, fill="x", padx=40)

    tk.Button(id_frame, text="⚙️ Format", font=("Arial", 9), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, cursor="hand2", command=open_id_format).pack(side="left", padx=10)

    tk.Label(right_f, text="Name *", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
    n_ent = tk.Entry(right_f, textvariable=name_var, font=("Arial", 11), width=45, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    n_ent.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(n_ent); n_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Phone 1", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=3, column=0, sticky="w", pady=(0, 2))
    p_ent = tk.Entry(right_f, textvariable=phone_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    p_ent.grid(row=4, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=4); enable_copy_paste(p_ent); p_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Phone 2", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=3, column=1, sticky="w", pady=(0, 2))
    ap_ent = tk.Entry(right_f, textvariable=alt_phone_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    ap_ent.grid(row=4, column=1, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(ap_ent); ap_ent.bind("<Return>", focus_next)

    def format_phone(*args, v=None, e=None):
        raw = v.get().replace("-", "")
        clean = ''.join(c for c in raw if c.isdigit())
        if len(clean) > 10: clean = clean[:10]
        fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
        if v.get() != fmt:
            v.set(fmt)
            e.after(1, lambda: e.icursor("end"))
            
    phone_var.trace_add("write", lambda *a: format_phone(v=phone_var, e=p_ent))
    alt_phone_var.trace_add("write", lambda *a: format_phone(v=alt_phone_var, e=ap_ent))
    format_phone(v=phone_var, e=p_ent)
    format_phone(v=alt_phone_var, e=ap_ent)

    tk.Label(right_f, text="Role / Designation", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=5, column=0, sticky="w", pady=(0, 2))
    r_ent = tk.Entry(right_f, textvariable=role_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    r_ent.grid(row=6, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=4); enable_copy_paste(r_ent); r_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Monthly Salary *", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=5, column=1, sticky="w", pady=(0, 2))
    s_ent = tk.Entry(right_f, textvariable=salary_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    s_ent.grid(row=6, column=1, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(s_ent); s_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Join Date", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=7, column=0, sticky="w", pady=(0, 2))
    j_f = tk.Frame(right_f, bg=BG_COLOR); j_f.grid(row=8, column=0, sticky="w", pady=(0, 15))
    j_ent = tk.Entry(j_f, textvariable=join_date_var, font=("Arial", 11), width=14, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    j_ent.pack(side="left", ipady=4); enable_copy_paste(j_ent); j_ent.bind("<Return>", focus_next)
    tk.Button(j_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, join_date_var)).pack(side="left", padx=5)

    tk.Label(right_f, text="Date of Birth", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=7, column=1, sticky="w", pady=(0, 2))
    dob_f = tk.Frame(right_f, bg=BG_COLOR); dob_f.grid(row=8, column=1, sticky="w", pady=(0, 15))
    dob_ent = tk.Entry(dob_f, textvariable=dob_var, font=("Arial", 11), width=14, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    dob_ent.pack(side="left", ipady=4); enable_copy_paste(dob_ent); dob_ent.bind("<Return>", focus_next)
    tk.Button(dob_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, dob_var)).pack(side="left", padx=5)

    tk.Label(right_f, text="Blood Type", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=9, column=0, sticky="w", pady=(0, 2))
    blood_types = ["Unknown", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    blood_cb = ttk.Combobox(right_f, textvariable=blood_type_var, values=blood_types, font=("Arial", 10), state="readonly", width=18)
    blood_cb.grid(row=10, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=3)
    blood_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(right_f, text="Emergency Contacts", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=9, column=1, sticky="w", pady=(0, 2))
    emerg_frame = tk.Frame(right_f, bg=BG_COLOR)
    emerg_frame.grid(row=10, column=1, sticky="w", pady=(0, 5))
    emerg_data = []

    def add_emerg_field(pnum=""):
        if len(emerg_data) >= 3:
            messagebox.showinfo("Limit reached", "Maximum of 3 emergency contacts allowed.", parent=pop); return
        row = tk.Frame(emerg_frame, bg=BG_COLOR)
        row.pack(fill="x", pady=2)
        n_var = tk.StringVar(value=pnum)
        ent = tk.Entry(row, textvariable=n_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
        ent.pack(side="left", fill="x", expand=True, ipady=3); enable_copy_paste(ent)

        def format_emerg(*args, var=n_var, entry=ent):
            raw = var.get().replace("-", "")
            clean = ''.join(c for c in raw if c.isdigit())
            if len(clean) > 10: clean = clean[:10]
            fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
            if var.get() != fmt:
                var.set(fmt)
                entry.after(1, lambda: entry.icursor("end"))
                
        n_var.trace_add("write", format_emerg)
        format_emerg(var=n_var, entry=ent)
        emerg_data.append(n_var)

    btn_add_emerg = tk.Button(right_f, text="+ Add contact", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=ACCENT_RED, relief="flat", cursor="hand2", command=add_emerg_field)
    btn_add_emerg.grid(row=11, column=1, sticky="w", pady=(0, 15))
    
    raw_emerg = emergency_contact_var.get()
    if raw_emerg:
        for p in raw_emerg.split(","):
            if p.strip(): add_emerg_field(p.strip())
    else: add_emerg_field("")

    tk.Label(right_f, text="Physical Address", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=12, column=0, columnspan=2, sticky="w", pady=(0, 2))
    addr_text = tk.Text(right_f, font=("Arial", 11), height=2, width=45, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    addr_text.grid(row=13, column=0, columnspan=2, sticky="w", pady=(0, 15))
    addr_text.insert("1.0", address_val)
    enable_copy_paste(addr_text)

    tk.Label(right_f, text="Bank Name", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=14, column=0, sticky="w", pady=(0, 2))
    bn_ent = tk.Entry(right_f, textvariable=bank_name_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    bn_ent.grid(row=15, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=4); enable_copy_paste(bn_ent); bn_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Bank Account No.", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=14, column=1, sticky="w", pady=(0, 2))
    b_ent = tk.Entry(right_f, textvariable=bank_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    b_ent.grid(row=15, column=1, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(b_ent); b_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="IFSC Code", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=16, column=0, sticky="w", pady=(0, 2))
    ifsc_ent = tk.Entry(right_f, textvariable=ifsc_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    ifsc_ent.grid(row=17, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=4); enable_copy_paste(ifsc_ent); ifsc_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="Bank Branch", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=16, column=1, sticky="w", pady=(0, 2))
    branch_ent = tk.Entry(right_f, textvariable=branch_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    branch_ent.grid(row=17, column=1, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(branch_ent); branch_ent.bind("<Return>", focus_next)

    tk.Label(right_f, text="UPI ID", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=18, column=0, sticky="w", pady=(0, 2))
    u_ent = tk.Entry(right_f, textvariable=upi_var, font=("Arial", 11), width=20, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    u_ent.grid(row=19, column=0, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(u_ent); u_ent.bind("<Return>", focus_next)

    def _capitalize_bank(*args):
        val = bank_name_var.get()
        if val != val.upper(): bank_name_var.set(val.upper())
    def _capitalize_ifsc(*args):
        val = ifsc_var.get()
        if val != val.upper(): ifsc_var.set(val.upper())
    def _numbers_only_ac(*args):
        val = bank_var.get()
        cleaned = ''.join(filter(str.isdigit, val))
        if val != cleaned: bank_var.set(cleaned)

    bank_name_var.trace_add("write", _capitalize_bank)
    ifsc_var.trace_add("write", _capitalize_ifsc)
    bank_var.trace_add("write", _numbers_only_ac)

    tk.Label(right_f, text="Documents & ID Files", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=20, column=0, columnspan=2, sticky="w", pady=(5, 2))
    doc_container = tk.Frame(right_f, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
    doc_container.grid(row=21, column=0, columnspan=2, sticky="ew")
    docs_list_f = tk.Frame(doc_container, bg=CARD_BG)
    docs_list_f.pack(fill="x", padx=10, pady=10)

    def refresh_docs():
        for widget in docs_list_f.winfo_children(): widget.destroy()
        if not current_docs:
            tk.Label(docs_list_f, text="No documents attached yet.", font=("Arial", 9, "italic"), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w")
        for idx, d in enumerate(current_docs):
            row = tk.Frame(docs_list_f, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1, pady=5, padx=5)
            row.pack(fill="x", pady=2)
            
            ext = os.path.splitext(d["path"])[1].lower()
            if ext == '.pdf': icon = "📄"
            elif ext in ['.jpg', '.jpeg', '.png']: icon = "🖼️"
            elif ext in ['.doc', '.docx']: icon = "📝"
            elif ext in ['.xls', '.xlsx', '.csv']: icon = "📊"
            else: icon = "📁"
            
            tk.Label(row, text=f"{icon} {os.path.basename(d['path'])[:30]}", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(side="left", padx=5)
            tk.Button(row, text="❌", font=("Arial", 8), bg=BG_COLOR, fg=ACCENT_RED, relief="flat", cursor="hand2", command=lambda i=idx: [current_docs.pop(i), refresh_docs()]).pack(side="right", padx=5)
            def view_doc(p=d['path']):
                if os.path.exists(p):
                    try: os.startfile(p)
                    except: webbrowser.open(p)
            tk.Button(row, text="👁️", font=("Arial", 8), bg=BG_COLOR, fg=ACCENT_BLUE, relief="flat", cursor="hand2", command=view_doc).pack(side="right", padx=2)

    def browse_document():
        path = filedialog.askopenfilename(parent=pop, title="Select ID/Document", filetypes=[("All Files", "*.*"), ("PDF", "*.pdf"), ("Images", "*.png *.jpg *.jpeg")])
        pop.lift(); pop.focus_force()
        if path:
            current_docs.append({"path": path, "desc": "Document"})
            refresh_docs()

    tk.Button(doc_container, text="📎 + Add Document", font=("Arial", 9, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", command=browse_document).pack(anchor="w", padx=10, pady=(0, 10))
    refresh_docs()

    def flash_red(widget):
        original_bg = BORDER_COLOR
        def toggle(count):
            if not widget.winfo_exists(): return
            if count > 0:
                widget.config(highlightbackground=ACCENT_RED if count % 2 != 0 else original_bg)
                pop.after(150, toggle, count - 1)
            else:
                widget.config(highlightbackground=original_bg)
        toggle(6)

    def save_action():
        valid = True
        name = name_var.get().strip()
        wid = emp_id_var.get().strip()
        
        if not wid:
            flash_red(id_ent)
            valid = False
            
        if not name:
            flash_red(n_ent)
            valid = False
            
        try: 
            sal = float(salary_var.get())
        except ValueError:
            flash_red(s_ent)
            valid = False
            
        if not valid: 
            return
            
        comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
        database.set_active_company(comp_id) # --- THE FIX: Force DB sync to prevent cross-company data leaks! ---
        
        # --- THE FIX: Fast Duplicate Checking & Removed Raw SQL! ---
        all_ids = database.get_all_employee_id_strings()
        is_dup = any((str(r_id) != str(emp_id) and e_str == wid.lower()) for r_id, e_str in all_ids)
                
        if is_dup:
            messagebox.showerror("Duplicate ID", f"The ID '{wid}' is already assigned to another employee.\n\nPlease type a unique ID or use the 'Format' button to auto-generate the next available number.", parent=pop)
            flash_red(id_ent)
            return
        
        # Master Filing Cabinet & ID Predictor
        from views.invoice_parts.helpers import get_vault_path
        
        target_id = emp_id
        if not target_id:
            try:
                con_temp = database.get_connection(); cur_temp = con_temp.cursor()
                cur_temp.execute("SELECT seq FROM sqlite_sequence WHERE name='employees'")
                seq_row = cur_temp.fetchone()
                target_id = (seq_row[0] + 1) if seq_row else 1
                con_temp.close()
            except:
                target_id = 1
                
        safe_dir = get_vault_path(ROOT_DIR, comp_id, name, "Employees", target_id)

        def secure_copy(filepath, prefix):
            if not filepath or not os.path.exists(filepath): return filepath
            try:
                if os.path.abspath(safe_dir) == os.path.dirname(os.path.abspath(filepath)):
                    return filepath
            except: pass
            
            # --- THE FIX: Create the target directory before trying to copy! ---
            os.makedirs(safe_dir, exist_ok=True)
            
            ext = os.path.splitext(filepath)[1]
            if not ext: ext = ".png" if prefix == "photo" else ".pdf"
            
            unique_name = f"{prefix}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}{ext}"
            new_path = os.path.join(safe_dir, unique_name)
            try:
                shutil.copy2(filepath, new_path)
                return new_path
            except:
                return filepath

        final_photo = secure_copy(photo_path_var.get(), "photo")
        
        # --- THE FIX: Instantly delete the temp cropper file from the Desktop! ---
        temp_img = photo_path_var.get()
        if temp_img and os.path.exists(temp_img) and temp_img != final_photo:
            try: os.remove(temp_img)
            except: pass
        # -------------------------------------------------------------------------
        
        for d in current_docs:
            d["path"] = secure_copy(d["path"], "doc")

        payload = {
            "emp_id_str": wid,
            "docs": current_docs,
            "blood_type": blood_type_var.get(),
            "emergency_contact": ", ".join([v.get().strip() for v in emerg_data if v.get().strip()]),
            "address": addr_text.get("1.0", "end-1c").strip(),
            "bank_name": bank_name_var.get().strip(),
            "bank_account": bank_var.get().strip(),
            "ifsc_code": ifsc_var.get().strip(),
            "branch": branch_var.get().strip(),
            "upi_id": upi_var.get().strip()
        }
        docs_json_str = json.dumps(payload)
        
        if emp_id:
            old_row = database.get_employee_full_record(emp_id)
            database.update_employee_full(emp_id, name, phone_var.get(), alt_phone_var.get(), role_var.get(), sal, join_date_var.get(), final_photo, dob_var.get(), docs_json_str)
            database.log_audit("Employees", "Edited Employee", record_ref=name, details="Updated employee profile and basic info.", company_id=comp_id)
            
            emp_data = database.get_employee_dict(emp_id)
            hist_str = emp_data.get("salary_history", "") if emp_data else ""
            try: hist = json.loads(hist_str) if hist_str else []
            except: hist = []
                
            if not hist: hist = [{"date": join_date_var.get(), "salary": sal}]
            elif len(hist) == 1:
                hist[0]["date"] = join_date_var.get()
                hist[0]["salary"] = sal
            else: hist[-1]["salary"] = sal
                
            database.update_employee_salary(emp_id, sal, json.dumps(hist))
            
            new_row = database.get_employee_full_record(emp_id)
            if undo_cb: undo_cb("EDIT_EMP", (old_row, new_row))
        else:
            hist = json.dumps([{"date": join_date_var.get(), "salary": sal}])
            new_id = database.insert_employee_full(name, phone_var.get(), alt_phone_var.get(), role_var.get(), sal, join_date_var.get(), final_photo, '', dob_var.get(), docs_json_str, hist)
            database.log_audit("Employees", "Added Employee", record_ref=name, details=f"Hired as {role_var.get()} at @@CURR:{sal}@@", amount=sal, company_id=comp_id)
            if undo_cb: undo_cb("ADD_EMP", new_id)
            
            # --- THE FIX: Removed destructive auto-increment logic! ---
            # The intelligent 'while' loop at the top of this file will automatically 
            # scan and fill any available gaps without skipping numbers permanently.
            # ----------------------------------------------------------
        
        if refresh_cb: refresh_cb()
        pop.destroy()

    tk.Button(bottom_wrapper, text="Save Employee", font=("Arial", 11, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=save_action).pack(side="right", padx=20, pady=(0, 20))


def open_pay_dialog(parent, emp_id, emp_name, emp_salary, curr_fmt="₹", date_fmt_code="%d.%m.%Y", refresh_cb=None, undo_cb=None, payable_bal=0.0, past_dues_val=None, current_due_val=None):
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
    ACCENT_GREEN = t["accent_green"]
    ACCENT_RED = t["error"]
    ACCENT_BLUE = t["accent_blue"]

    pop = tk.Toplevel(parent)
    pop.title(f"Payments: {emp_name}")
    pop_w, pop_h = 450, 700
    pop.geometry(f"{pop_w}x{pop_h}")
    pop.configure(bg=BG_COLOR)
    pop.grab_set()

    pop.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width()//2) - (pop_w//2)
    y = parent.winfo_rooty() + (parent.winfo_height()//2) - (pop_h//2)
    pop.geometry(f"+{max(0, x)}+{max(0, y)}")
    
    def remove_focus_pop(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox', 'Button']:
            pop.focus_set()
    pop.bind("<ButtonPress-1>", remove_focus_pop)

    pay_records = database.get_employee_wallet_payments(emp_id)
    
    available_adv = 0.0
    for p_t, p_a, p_m in pay_records:
        if p_t == "Advance":
            available_adv += p_a
        elif p_t == "Salary" and p_m and "wallet deduction" in str(p_m).lower():
            available_adv -= p_a
    available_adv = max(0.0, available_adv)

    pay_type_var = tk.StringVar(pop, value="Salary")
    amt_var = tk.StringVar(pop, value=str(emp_salary))
    date_var = tk.StringVar(pop, value=date.today().strftime(date_fmt_code))
    notes_var = tk.StringVar(pop)
    max_allowed = tk.DoubleVar(value=-1.0)

    tk.Label(pop, text="Employee Payment Portal", font=("Segoe UI", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(20, 5))
    tk.Label(pop, text=f"Processing payment for: {emp_name}", font=("Segoe UI", 10), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(0, 20))

    tab_f = tk.Frame(pop, bg=BG_COLOR)
    tab_f.pack(fill="x", padx=20, pady=(0, 20))
    
    btn_map = {}
    base_modes = ["Cash", "Bank Transfer", "UPI", "Cheque", "Google Pay", "PhonePe"]
    
    try: 
        if past_dues_val is not None: past_dues = float(past_dues_val)
        else: past_dues = max(0.0, float(payable_bal) - float(emp_salary))
    except: past_dues = 0.0

    try:
        if current_due_val is not None: curr_due = float(current_due_val)
        else: curr_due = float(emp_salary)
    except: curr_due = float(emp_salary)

    def set_type(t):
        pay_type_var.set(t)
        if t == "Salary":
            amt_var.set(f"{curr_due:.2f}")
            notes_var.set("Salary Payment")
            max_allowed.set(-1.0)
            
            adv_toggle_f.pack_forget()
            
            try:
                if past_dues > 0: smart_btn_f.pack(fill="x", pady=(0, 5), before=amt_ent)
            except: pass
            
            if available_adv > 0:
                opts = [f"Wallet Deduction (Bal: {format_currency(available_adv, curr_fmt)})"] + base_modes
                mode_cb.config(values=opts)
                mode_var.set("Cash")
            else:
                mode_cb.config(values=base_modes)
                mode_var.set("Cash")
        elif t == "Advance":
            amt_var.set("0")
            notes_var.set("Advance Given" if adv_dir_var.get() == "Given" else "Advance Refunded")
            adv_toggle_f.pack(fill="x", pady=(0, 15), after=amt_ent)
            try: smart_btn_f.pack_forget()
            except: pass
            mode_cb.config(values=base_modes)
            if "Wallet" in mode_var.get(): mode_var.set(base_modes[0])
        elif t == "Bonus":
            amt_var.set("0")
            notes_var.set("Bonus Payment")
            adv_toggle_f.pack_forget()
            try: smart_btn_f.pack_forget()
            except: pass
            mode_cb.config(values=base_modes)
            if "Wallet" in mode_var.get(): mode_var.set(base_modes[0])
            
        for b, name in btn_map.items():
            if name == t: 
                b.config(bg=ACCENT_BLUE, fg="#ffffff", highlightbackground=ACCENT_BLUE)
            else: 
                b.config(bg=CARD_BG, fg=TEXT_SECONDARY, highlightbackground=BORDER_COLOR)

    for i, t in enumerate(["Salary", "Advance", "Bonus"]):
        btn = tk.Button(tab_f, text=t, font=("Segoe UI", 10, "bold"), pady=8, cursor="hand2", relief="flat", highlightthickness=1)
        btn.pack(side="left", expand=True, fill="x", padx=(0 if i==0 else 5, 0 if i==2 else 5))
        btn.config(command=lambda x=t, b=btn: set_type(x))
        btn_map[btn] = t
        
    form_f = tk.Frame(pop, bg=BG_COLOR)
    form_f.pack(fill="both", expand=True, padx=20)
    form_f.columnconfigure(0, weight=1)

    tk.Label(form_f, text="Date", font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    d_f = tk.Frame(form_f, bg=BG_COLOR)
    d_f.pack(fill="x", pady=(0, 15))
    
    d_ent = tk.Entry(d_f, textvariable=date_var, font=("Segoe UI", 11), bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE, highlightthickness=1, bd=0, relief="flat")
    d_ent.pack(side="left", fill="x", expand=True, ipady=4)
    enable_copy_paste(d_ent)
    
    btn_cal = tk.Button(d_f, text="📅", bg=BORDER_COLOR, fg=TEXT_PRIMARY, relief="flat", cursor="hand2")
    btn_cal.pack(side="right", padx=(5, 0))
    btn_cal.config(command=lambda b=btn_cal: NativeCalendar(pop, date_var, anchor_widget=b))

    tk.Label(form_f, text="Amount", font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    
    smart_btn_f = tk.Frame(form_f, bg=BG_COLOR)
    
    def enforce_limit(*args):
        lim = max_allowed.get()
        if lim >= 0:
            try:
                val = re.sub(r'[^\d\.]', '', amt_var.get())
                if val and float(val) > lim:
                    amt_var.set(f"{lim:.2f}")
                    amt_ent.icursor("end")
            except: pass
            
    amt_var.trace_add("write", enforce_limit)

    btn_past = tk.Button(smart_btn_f, text=f"Clear Dues ({format_currency(past_dues, curr_fmt)})", font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=ACCENT_RED, relief="solid", bd=1, cursor="hand2")
    btn_curr = tk.Button(smart_btn_f, text=f"Pay Current ({format_currency(curr_due, curr_fmt)})", font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=ACCENT_BLUE, relief="solid", bd=1, cursor="hand2")
    btn_all = tk.Button(smart_btn_f, text=f"Pay All ({format_currency(payable_bal, curr_fmt)})", font=("Segoe UI", 8, "bold"), bg=CARD_BG, fg=ACCENT_GREEN, relief="solid", bd=1, cursor="hand2")

    def set_smart_amount(amt, note, limit, active_btn):
        max_allowed.set(limit)
        amt_var.set(f"{amt:.2f}")
        notes_var.set(note)
        
        btn_past.config(bg=CARD_BG, fg=ACCENT_RED)
        btn_curr.config(bg=CARD_BG, fg=ACCENT_BLUE)
        btn_all.config(bg=CARD_BG, fg=ACCENT_GREEN)
        
        if active_btn == btn_past: active_btn.config(bg=ACCENT_RED, fg="#ffffff")
        elif active_btn == btn_curr: active_btn.config(bg=ACCENT_BLUE, fg="#ffffff")
        elif active_btn == btn_all: active_btn.config(bg=ACCENT_GREEN, fg="#ffffff")

    btn_past.config(command=lambda: set_smart_amount(past_dues, "Clearing Past Dues", past_dues, btn_past))
    btn_curr.config(command=lambda: set_smart_amount(curr_due, "Salary Payment", -1.0, btn_curr))
    btn_all.config(command=lambda: set_smart_amount(payable_bal, "Full Salary & Dues Cleared", -1.0, btn_all))

    btn_past.pack(side="left", fill="x", expand=True, padx=(0, 2))
    btn_curr.pack(side="left", fill="x", expand=True, padx=(2, 2))
    btn_all.pack(side="left", fill="x", expand=True, padx=(2, 0))

    if pay_type_var.get() == "Salary":
        notes_var.set("Salary Payment")
        btn_curr.config(bg=ACCENT_BLUE, fg="#ffffff")

    amt_ent = tk.Entry(form_f, textvariable=amt_var, font=("Segoe UI", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE, highlightthickness=1, bd=0, relief="flat")
    amt_ent.pack(fill="x", ipady=4, pady=(0, 15))
    enable_copy_paste(amt_ent)
    amt_ent.bind("<FocusIn>", lambda e: amt_ent.delete('0', 'end') if amt_var.get() == '0' else None)

    adv_toggle_f = tk.Frame(form_f, bg=BG_COLOR)
    adv_dir_var = tk.StringVar(value="Given")
    
    def toggle_adv_note():
        if adv_dir_var.get() == "Refund" and notes_var.get() == "Advance Given":
            notes_var.set("Advance Refunded")
        elif adv_dir_var.get() == "Given" and notes_var.get() == "Advance Refunded":
            notes_var.set("Advance Given")
            
    rb1 = tk.Radiobutton(adv_toggle_f, text="Advance Given (Out)", variable=adv_dir_var, value="Given", bg=BG_COLOR, fg=TEXT_PRIMARY, selectcolor=CARD_BG, activebackground=BG_COLOR, activeforeground=TEXT_PRIMARY, cursor="hand2", font=("Segoe UI", 9, "bold"), command=toggle_adv_note)
    rb2 = tk.Radiobutton(adv_toggle_f, text="Advance Refund (Returned)", variable=adv_dir_var, value="Refund", bg=BG_COLOR, fg=ACCENT_GREEN, selectcolor=CARD_BG, activebackground=BG_COLOR, activeforeground=ACCENT_GREEN, cursor="hand2", font=("Segoe UI", 9, "bold"), command=toggle_adv_note)
    
    rb1.pack(side="left", padx=(0, 10))
    rb2.pack(side="left")

    tk.Label(form_f, text="Payment Mode", font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    mode_var = tk.StringVar(value="Cash")
    mode_cb = ttk.Combobox(form_f, textvariable=mode_var, values=base_modes, state="readonly", font=("Segoe UI", 11))
    mode_cb.pack(fill="x", ipady=4, pady=(0, 15))
    mode_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(form_f, text="Notes", font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    notes_lbl = tk.Entry(form_f, textvariable=notes_var, font=("Segoe UI", 11), bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE, highlightthickness=1, bd=0, relief="flat")
    notes_lbl.pack(fill="x", ipady=4, pady=(0, 15))
    enable_copy_paste(notes_lbl)
    
    tk.Label(form_f, text="Payment Proof", font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    attach_var = tk.StringVar()
    attach_f = tk.Frame(form_f, bg=BG_COLOR)
    attach_f.pack(fill="x", pady=(0, 20))
    
    def browse_proof():
        path = filedialog.askopenfilename(parent=pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
        if path: attach_var.set(path)
        
    tk.Button(attach_f, text="📎 Attach", font=("Segoe UI", 9, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=browse_proof).pack(side="left")
    tk.Label(attach_f, textvariable=attach_var, font=("Segoe UI", 8), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(side="left", padx=5)
    
    set_type("Salary") 

    def save_pay():
        try:
            comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
            database.set_active_company(comp_id)
            
            amt_str = re.sub(r'[^\d\.\-]', '', amt_var.get())
            if not amt_str or amt_str == '-': return
            amt = float(amt_str)
            
            if amt == 0: return
            
            p_type = pay_type_var.get()
            raw_mode = mode_var.get()
            
            if p_type == "Salary" and "wallet deduction" in str(raw_mode).lower():
                if amt > available_adv:
                    messagebox.showerror("Error", f"Amount exceeds available Advance Wallet Balance ({format_currency(available_adv, curr_fmt)}).", parent=pop)
                    return
                clean_mode = "Wallet Deduction"
            else:
                clean_mode = raw_mode
                
            if p_type == "Advance" and adv_dir_var.get() == "Refund":
                amt = -abs(amt)
                if notes_var.get() == "Advance Given":
                    notes_var.set("Advance Refunded")
            else:
                pass 
                
            final_notes = notes_var.get()
            if final_notes == "Salary Payment": final_notes += " [Target: Current]"
            elif final_notes == "Clearing Past Dues": final_notes += " [Target: Dues]"
            elif final_notes == "Full Salary & Dues Cleared": final_notes += " [Target: All]"
            
            # --- THE FIX: Custom UI Interceptor + Dual Verification ---
            is_split_advance = False
            salary_portion = amt
            advance_portion = 0.0
            
            # Use curr_due as a strict fallback if payable_bal evaluates weirdly due to closures
            strict_limit = min(float(payable_bal), float(curr_due))
            if strict_limit <= 0.01: strict_limit = max(float(payable_bal), float(curr_due))
            
            if p_type == "Salary" and amt > strict_limit + 0.01 and amt > 0:
                excess = amt - max(0.0, strict_limit)
                
                choice = tk.StringVar(value="")
                ask_pop = tk.Toplevel(pop)
                ask_pop.title("Excess Payment Detected")
                ask_pop.geometry("450x220")
                ask_pop.configure(bg=BG_COLOR)
                ask_pop.transient(pop)
                ask_pop.attributes('-topmost', True) 
                ask_pop.grab_set()

                ask_pop.update_idletasks()
                x = pop.winfo_rootx() + (pop.winfo_width()//2) - 225
                y = pop.winfo_rooty() + (pop.winfo_height()//2) - 110
                ask_pop.geometry(f"+{max(0,x)}+{max(0,y)}")

                tk.Label(ask_pop, text=f"You are paying {format_currency(excess, curr_fmt)} extra.", font=("Segoe UI", 12, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(25, 10))
                tk.Label(ask_pop, text="How should we handle this excess amount?", font=("Segoe UI", 10), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(pady=(0, 25))

                btn_f = tk.Frame(ask_pop, bg=BG_COLOR)
                btn_f.pack(fill="x", padx=20)

                def set_choice(c):
                    choice.set(c)
                    ask_pop.destroy()

                tk.Button(btn_f, text="📥 Advance Wallet", font=("Segoe UI", 10, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", bd=0, cursor="hand2", command=lambda: set_choice("advance")).pack(side="left", expand=True, fill="x", padx=(0, 5), ipady=8)
                tk.Button(btn_f, text="▶ Surplus Rollover", font=("Segoe UI", 10, "bold"), bg=ACCENT_GREEN, fg="#ffffff", relief="flat", bd=0, cursor="hand2", command=lambda: set_choice("rollover")).pack(side="left", expand=True, fill="x", padx=(5, 5), ipady=8)
                tk.Button(btn_f, text="✖ Cancel", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, cursor="hand2", command=lambda: set_choice("cancel")).pack(side="left", expand=True, fill="x", padx=(5, 0), ipady=7)

                ask_pop.focus_force()
                ask_pop.wait_window()
                
                decision = choice.get()
                if not decision or decision == "cancel": return # Action cancelled

                if decision == "advance":
                    is_split_advance = True
                    salary_portion = max(0.0, strict_limit)
                    advance_portion = excess
            # ----------------------------------------------------------
            
            import shutil
            import time
            final_attach = ""
            r_path = attach_var.get()
            if r_path and os.path.exists(r_path):
                from views.invoice_parts.helpers import get_vault_path
                safe_dir = get_vault_path(ROOT_DIR, comp_id, emp_name, "Employees", emp_id)
                proof_dir = os.path.join(safe_dir, "payment_proofs")
                os.makedirs(proof_dir, exist_ok=True)
                
                ext = os.path.splitext(r_path)[1] or ".png"
                final_attach = os.path.join(proof_dir, f"proof_{int(time.time()*1000)}{ext}")
                
                try: shutil.copy2(r_path, final_attach)
                except: final_attach = r_path
                
            # --- THE FIX: Execute Split or Single Payment ---
            if is_split_advance:
                if salary_portion > 0:
                    sal_id = database.add_employee_payment(emp_id, "Salary", salary_portion, date_var.get(), final_notes, clean_mode, final_attach)
                    if undo_cb: undo_cb("ADD_PAY", sal_id)
                    database.log_audit("Employees", "Recorded Salary", record_ref=emp_name, details=f"Amount: @@CURR:{salary_portion}@@ via {clean_mode} • Notes: {final_notes}", amount=salary_portion, company_id=comp_id)

                adv_id = database.add_employee_payment(emp_id, "Advance", advance_portion, date_var.get(), "Excess from Salary Payment", clean_mode, final_attach)
                if undo_cb: undo_cb("ADD_PAY", adv_id)
                database.log_audit("Employees", "Recorded Advance", record_ref=emp_name, details=f"Amount: @@CURR:{advance_portion}@@ via {clean_mode} • Notes: Excess from Salary Payment", amount=advance_portion, company_id=comp_id)
            else:
                new_pay_id = database.add_employee_payment(emp_id, p_type, amt, date_var.get(), final_notes, clean_mode, final_attach)
                if undo_cb: undo_cb("ADD_PAY", new_pay_id)
                database.log_audit("Employees", f"Recorded {p_type}", record_ref=emp_name, details=f"Amount: @@CURR:{amt}@@ via {clean_mode} • Notes: {final_notes}", amount=abs(amt), company_id=comp_id)
            # ------------------------------------------------
            
            if refresh_cb: refresh_cb()
            pop.destroy()
        except Exception as e: 
            messagebox.showerror("Error", f"Could not save payment:\n{e}", parent=pop)

    tk.Button(pop, text="Confirm Payment", bg=ACCENT_GREEN, fg="white", font=("Segoe UI", 12, "bold"), pady=8, command=save_pay, cursor="hand2", relief="flat").pack(fill="x", padx=20, pady=(10, 20), ipady=2)


def open_absent_dialog(parent, emp_id, emp_name, date_fmt_code="%d.%m.%Y", refresh_cb=None, undo_cb=None):
    from views.home_parts.ui_components import get_theme
    t = get_theme()
    BG_COLOR = t["bg"]
    CARD_BG = t["card"]
    BORDER_COLOR = t["border"]
    TEXT_PRIMARY = t["text"]
    TEXT_SECONDARY = t["sec"]
    ACCENT_GREEN = t["accent_green"]
    ACCENT_RED = t["error"]
    ACCENT_BLUE = t["accent_blue"]

    pop = tk.Toplevel(parent)
    pop.title(f"Mark Leave: {emp_name}")
    pop.geometry("400x480") # Increased height for the new field
    pop.configure(bg=BG_COLOR)
    pop.grab_set()

    style = ttk.Style(pop)
    style.theme_use("default")
    pop.option_add("*TCombobox*Listbox.background", CARD_BG)
    pop.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    pop.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)
    pop.option_add("*TCombobox*Listbox.selectForeground", TEXT_PRIMARY)
    style.configure("TCombobox", fieldbackground=BG_COLOR, background=CARD_BG, foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR, darkcolor=BORDER_COLOR)
    style.map("TCombobox", fieldbackground=[("readonly", BG_COLOR)], selectbackground=[("readonly", BG_COLOR)], selectforeground=[("readonly", TEXT_PRIMARY)])

    date_var = tk.StringVar(pop, value=date.today().strftime(date_fmt_code))
    to_date_var = tk.StringVar(pop, value="") # New Bulk Date Variable
    leave_type_var = tk.StringVar(pop, value="Unpaid Leave")
    notes_var = tk.StringVar(pop)

    tk.Label(pop, text=f"Mark Leave", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(15,5))
    tk.Label(pop, text=f"Employee: {emp_name}", font=("Arial", 10), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(0, 15))

    f = tk.Frame(pop, bg=BG_COLOR)
    f.pack(fill="both", expand=True, padx=20)

    # From Date
    tk.Label(f, text="From Date", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", pady=(0, 2))
    d_f = tk.Frame(f, bg=BG_COLOR); d_f.grid(row=1, column=0, sticky="w", pady=(0, 15))
    d_ent = tk.Entry(d_f, textvariable=date_var, font=("Arial", 11), width=15, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    d_ent.pack(side="left", ipady=4); enable_copy_paste(d_ent)
    tk.Button(d_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, date_var)).pack(side="left", padx=5)

    # To Date (Bulk Leave)
    tk.Label(f, text="To Date (Optional for multiple days)", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=(0, 2))
    td_f = tk.Frame(f, bg=BG_COLOR); td_f.grid(row=3, column=0, sticky="w", pady=(0, 15))
    td_ent = tk.Entry(td_f, textvariable=to_date_var, font=("Arial", 11), width=15, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    td_ent.pack(side="left", ipady=4); enable_copy_paste(td_ent)
    def open_to_calendar():
        if not to_date_var.get(): 
            to_date_var.set(date_var.get()) # Grab the 'From Date' so the calendar highlights it!
        NativeCalendar(pop, to_date_var)

    tk.Button(td_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=open_to_calendar).pack(side="left", padx=5)
    
    # --- THE FIX: Quick Clear Button ---
    tk.Button(td_f, text="✖", bg=BG_COLOR, fg=ACCENT_RED, relief="flat", cursor="hand2", font=("Arial", 10), command=lambda: to_date_var.set("")).pack(side="left", padx=2)

    tk.Label(f, text="Leave Type", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=4, column=0, sticky="w", pady=(0, 2))
    leave_cb = ttk.Combobox(f, textvariable=leave_type_var, state="readonly", values=["Paid Leave", "Unpaid Leave"], font=("Arial", 11), width=18)
    leave_cb.grid(row=5, column=0, sticky="w", pady=(0, 15))

    tk.Label(f, text="Reason / Description", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=6, column=0, sticky="w", pady=(0, 2))
    n_ent = tk.Entry(f, textvariable=notes_var, font=("Arial", 11), width=35, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    n_ent.grid(row=7, column=0, sticky="w", pady=(0, 15), ipady=4); enable_copy_paste(n_ent)

    def save_absent():
        start_str = date_var.get().strip()
        end_str = to_date_var.get().strip()
        
        # --- THE FIX: Apply Company Firewall Lock ---
        comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
        database.set_active_company(comp_id)
        # --------------------------------------------

        try:
            start_dt = datetime.strptime(start_str, date_fmt_code)
            end_dt = datetime.strptime(end_str, date_fmt_code) if end_str else start_dt
        except ValueError:
            messagebox.showerror("Error", "Invalid date format.", parent=pop)
            return

        if end_dt < start_dt:
            messagebox.showerror("Error", "'To Date' cannot be earlier than 'From Date'.", parent=pop)
            return

        current_dt = start_dt
        success_count = 0
        skipped_count = 0

        while current_dt <= end_dt:
            curr_str = current_dt.strftime(date_fmt_code)
            
            if database.check_employee_leave_exists(emp_id, curr_str):
                skipped_count += 1
            else:
                new_pay_id = database.add_employee_payment(emp_id, leave_type_var.get(), 0.0, curr_str, notes_var.get())
                if undo_cb: undo_cb("ADD_PAY", new_pay_id)
                success_count += 1
                
            current_dt += timedelta(days=1)
            
        if success_count > 0:
            database.log_audit("Employees", "Leave Marked", record_ref=emp_name, details=f"Marked {success_count} days as {leave_type_var.get()} • Notes: {notes_var.get()}", company_id=comp_id)

        if success_count == 0 and skipped_count > 0:
            messagebox.showerror("Duplicate Entry", "Leaves are already marked for all selected dates.", parent=pop)
            return

        if refresh_cb: refresh_cb()
        pop.destroy()
        
        if skipped_count > 0:
            messagebox.showinfo("Partial Success", f"Leave recorded for {success_count} day(s).\n\nSkipped {skipped_count} day(s) because they were already marked.", parent=parent)
        else:
            messagebox.showinfo("Success", f"Leave recorded for {success_count} day(s)!", parent=parent)

    tk.Button(pop, text="💾 Save Record", font=("Arial", 11, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", padx=20, pady=8, command=save_absent).pack(side="right", padx=20, pady=20)


def open_increase_salary_dialog(parent, emp_id, emp_name, current_sal, curr_fmt="₹", date_fmt_code="%d.%m.%Y", refresh_cb=None, undo_cb=None, anchor_widget=None):
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    BG_COLOR = "#0f172a" if is_dark else "#e0f2fe"
    CARD_BG = "#1e293b" if is_dark else "#f0f9ff"
    BORDER_COLOR = "#334155" if is_dark else "#7dd3fc"
    TEXT_PRIMARY = "#f8fafc" if is_dark else "#0f172a"
    TEXT_SECONDARY = "#94a3b8" if is_dark else "#0284c7"
    ACCENT_GREEN = "#10b981"
    ACCENT_BLUE = "#3b82f6" if is_dark else "#0ea5e9"

    pop = tk.Toplevel(parent)
    pop.title("Increase Salary")
    pop.configure(bg=BG_COLOR)
    pop.grab_set()

    pop.update_idletasks()
    w, h = 400, 360
    if anchor_widget:
        x = anchor_widget.winfo_rootx() - w + anchor_widget.winfo_width()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
    else:
        sw = pop.winfo_screenwidth(); sh = pop.winfo_screenheight()
        x = int((sw/2) - (w/2)); y = int((sh/2) - (h/2))
        pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    tk.Label(pop, text="Increase Base Salary", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(15, 5), padx=20, anchor="w")
    tk.Label(pop, text=f"Employee: {emp_name}", font=("Arial", 10), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(padx=20, anchor="w", pady=(0, 15))

    tk.Label(pop, text=f"Current Salary: {format_currency(current_sal, curr_fmt)}", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(padx=20, anchor="w", pady=(0, 10))

    tk.Label(pop, text="New Base Salary:", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(10, 2))
    sal_var = tk.StringVar()
    tk.Entry(pop, textvariable=sal_var, font=("Arial", 12, "bold"), bg=CARD_BG, fg=ACCENT_GREEN, insertbackground=TEXT_PRIMARY).pack(fill="x", padx=20, ipady=4)

    tk.Label(pop, text="Effective Date:", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).pack(anchor="w", padx=20, pady=(10, 2))
    date_f = tk.Frame(pop, bg=BG_COLOR)
    date_f.pack(fill="x", padx=20)
    date_var = tk.StringVar(value=datetime.today().strftime(date_fmt_code))
    tk.Entry(date_f, textvariable=date_var, font=("Arial", 11), bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY).pack(side="left", fill="x", expand=True, ipady=4)
    cal_btn = tk.Button(date_f, text="📅", font=("Arial", 11), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, cursor="hand2")
    cal_btn.pack(side="right", padx=(5, 0), ipady=2, ipadx=4)
    
    cal_btn.config(command=lambda: NativeCalendar(pop, date_var, cal_btn))

    def save():
        try: 
            clean_sal = re.sub(r'[^\d\.]', '', sal_var.get())
            new_sal = float(clean_sal) if clean_sal else 0.0
        except: messagebox.showerror("Error", "Invalid salary amount", parent=pop); return
        if new_sal <= 0: return

        # Capture Undo State (Before edit)
        old_row = database.get_employee_full_record(emp_id)

        emp = database.get_employee_dict(emp_id)
        if not emp: return
        hist_str = emp.get("salary_history", "")
        try: hist = json.loads(hist_str) if hist_str else [{"date": emp.get("join_date", ""), "salary": current_sal}]
        except: hist = [{"date": emp.get("join_date", ""), "salary": current_sal}]

        hist.append({"date": date_var.get(), "salary": new_sal})
        
        comp_id = getattr(parent.winfo_toplevel(), "active_company_id", 1)
        database.update_employee_salary(emp_id, new_sal, json.dumps(hist))
        database.log_audit("Employees", "Salary Increased", record_ref=emp_name, details=f"Changed base salary from @@CURR:{current_sal}@@ to @@CURR:{new_sal}@@", amount=new_sal, company_id=comp_id)

        # Capture Undo State (After edit)
        new_row = database.get_employee_full_record(emp_id)
        
        if undo_cb: undo_cb("EDIT_EMP", (old_row, new_row))

        messagebox.showinfo("Success", f"Salary updated to {format_currency(new_sal, curr_fmt)}", parent=pop)
        if refresh_cb: refresh_cb()
        pop.destroy()

    tk.Button(pop, text="Confirm Increase", font=("Arial", 11, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(20, 10), ipady=3)


def open_salary_history_dialog(parent, emp_id, emp_name, curr_fmt, date_fmt_code, anchor_widget=None):
    emp = database.get_employee_dict(emp_id)
    if not emp: return
    
    hist_str = emp.get("salary_history", "")
    join_date = emp.get("join_date", "")
    current_sal = emp.get("salary", 0.0)
    
    try:
        hist = json.loads(hist_str) if hist_str else [{"date": join_date, "salary": current_sal}]
    except:
        hist = [{"date": join_date, "salary": current_sal}]
        
    parsed_hist = []
    for h in hist:
        d_obj = datetime.min
        for fmt in (date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                d_obj = datetime.strptime(str(h["date"]).strip(), fmt)
                break
            except: pass
        if d_obj != datetime.min:
            parsed_hist.append((d_obj, h["date"], float(h["salary"])))
    parsed_hist.sort(key=lambda x: x[0])
    
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    BG_COLOR = "#0f172a" if is_dark else "#e0f2fe"
    CARD_BG = "#1e293b" if is_dark else "#f0f9ff"
    BORDER_COLOR = "#334155" if is_dark else "#7dd3fc"
    TEXT_PRIMARY = "#f8fafc" if is_dark else "#0f172a"
    
    pop = tk.Toplevel(parent)
    pop.title("Salary History")
    pop.configure(bg=BG_COLOR)
    pop.transient(parent)
    pop.grab_set()
    
    w, h = 420, 360
    if anchor_widget:
        pop.update_idletasks()
        x = anchor_widget.winfo_rootx() - w + anchor_widget.winfo_width()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
    else:
        sw = pop.winfo_screenwidth(); sh = pop.winfo_screenheight()
        x = int((sw/2) - (w/2)); y = int((sh/2) - (h/2))
        pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        
    tk.Label(pop, text=f"Salary History", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=(15, 5), padx=20, anchor="w")
    
    table_f = tk.Frame(pop, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
    table_f.pack(fill="both", expand=True, padx=20, pady=(10, 20))
    
    style = ttk.Style(pop)
    style.theme_use("default")
    
    style.configure("Hist.Vertical.TScrollbar", background=TEXT_SECONDARY, troughcolor=BG_COLOR, bordercolor=BG_COLOR, arrowcolor=TEXT_PRIMARY, relief="flat")
    style.map("Hist.Vertical.TScrollbar", background=[("active", ACCENT_BLUE)])
    
    scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="Hist.Vertical.TScrollbar")
    scroll_y.pack(side="right", fill="y")
    
    style.configure("Hist.Treeview.Heading", font=("Arial", 9, "bold"), background=CARD_BG, foreground=TEXT_PRIMARY)
    style.configure("Hist.Treeview", font=("Arial", 11), rowheight=30, background=BG_COLOR, fieldbackground=BG_COLOR, foreground=TEXT_PRIMARY, borderwidth=0)
    
    tree = ttk.Treeview(table_f, columns=("date", "amount"), show="headings", yscrollcommand=scroll_y.set, height=7, style="Hist.Treeview")
    tree.pack(side="left", fill="both", expand=True)
    scroll_y.config(command=tree.yview)
    
    tree.heading("date", text="EFFECTIVE DATE", anchor="w")
    tree.heading("amount", text="BASE SALARY", anchor="e")
    tree.column("date", width=180, anchor="w")
    tree.column("amount", width=180, anchor="e")
    
    tree.tag_configure("even", background=BG_COLOR, foreground=TEXT_PRIMARY)
    tree.tag_configure("odd", background=CARD_BG, foreground=TEXT_PRIMARY)
    tree.tag_configure("joined", foreground="#10b981", font=("Arial", 10, "bold"))
    
    for i, item in enumerate(parsed_hist):
        tag = "even" if i % 2 == 0 else "odd"
        d_str = smart_date_formatter(item[1], date_fmt_code)
        amt_str = format_currency(item[2], curr_fmt)
        
        if i == 0: 
            d_str += " (Joined)"
            tree.insert("", "end", values=(d_str, amt_str), tags=("joined", tag))
        else:
            tree.insert("", "end", values=(d_str, amt_str), tags=(tag,))

def open_leave_allocation_dialog(parent, emp_id, emp_name, current_year, refresh_cb=None, anchor_widget=None):
    from views.home_parts.ui_components import get_theme
    t = get_theme()
    
    pop = tk.Toplevel(parent)
    pop.title("Set Paid Leave Limit")
    pop.configure(bg=t["bg"])
    pop.grab_set()

    w, h = 350, 300
    if anchor_widget:
        pop.update_idletasks()
        x = anchor_widget.winfo_rootx() - w + anchor_widget.winfo_width()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
        pop.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
    else:
        sw = pop.winfo_screenwidth(); sh = pop.winfo_screenheight()
        pop.geometry(f"{w}x{h}+{int((sw/2) - (w/2))}+{int((sh/2) - (h/2))}")

    tk.Label(pop, text="Set Yearly Paid Leaves", font=("Arial", 14, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(20, 5), padx=20, anchor="w")
    tk.Label(pop, text=f"Employee: {emp_name}", font=("Arial", 10), bg=t["bg"], fg=t["sec"]).pack(padx=20, anchor="w", pady=(0, 15))

    tk.Label(pop, text="Target Year:", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["sec"]).pack(anchor="w", padx=20, pady=(5, 2))
    year_var = tk.StringVar(value=str(current_year))
    year_cb = ttk.Combobox(pop, textvariable=year_var, values=[str(y) for y in range(2020, 2035)], state="readonly", font=("Arial", 11))
    year_cb.pack(fill="x", padx=20, ipady=4)

    tk.Label(pop, text="Total Days Allotted:", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["sec"]).pack(anchor="w", padx=20, pady=(15, 2))
    days_var = tk.StringVar()
    
    # Auto-load existing allocation if it exists
    emp = database.get_employee_dict(emp_id)
    if emp:
        try:
            allocs = json.loads(emp.get("docs_json", "{}")).get("leave_allocations", {})
            days_var.set(str(allocs.get(str(current_year), 0)))
        except: days_var.set("0")
        
    def _update_days(*args):
        try:
            allocs = json.loads(emp.get("docs_json", "{}")).get("leave_allocations", {})
            days_var.set(str(allocs.get(year_var.get(), 0)))
        except: days_var.set("0")
    year_var.trace_add("write", _update_days)

    tk.Entry(pop, textvariable=days_var, font=("Arial", 12, "bold"), bg=t["card"], fg=t["accent_blue"], insertbackground=t["text"]).pack(fill="x", padx=20, ipady=4)

    def save():
        try: days = float(days_var.get())
        except: messagebox.showerror("Error", "Invalid number of days", parent=pop); return
        
        database.update_employee_leave_allocation(emp_id, year_var.get(), days)
        messagebox.showinfo("Success", f"Paid Leave allotment for {year_var.get()} updated to {days:g} days.", parent=pop)
        if refresh_cb: refresh_cb()
        pop.destroy()

    tk.Button(pop, text="Save Allotment", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=save).pack(fill="x", padx=20, pady=(20, 10), ipady=3)