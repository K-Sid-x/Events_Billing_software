import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import shutil
import time
import re
import json

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
from views.labour_parts.labour_details import view_document

# --- THE FIX: Added missing calendar and helper imports ---
from views.invoice_parts.helpers import fetch_global_settings
from views.invoice_parts.calendar_widget import NativeCalendar
# ----------------------------------------------------------
# --- THE FIX: Import the Centralized Image Cropper ---
from settings_parts.interactive_cropper import InteractiveCropper
# ---------------------------------------------------

def safe_copy_paste(widget):
    menu = tk.Menu(widget, tearoff=0, font=("Segoe UI", 10))
    menu.add_command(label="✂️ Cut", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="📋 Copy", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="📋 Paste", command=lambda: widget.event_generate("<<Paste>>"))
    widget.bind("<Button-3>", lambda e: [widget.focus_set(), menu.tk_popup(e.x_root, e.y_root)])

try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def open_labour_form(parent_view, labour_id=None):
    t = parent_view.colors
    pop = tk.Toplevel(parent_view)
    pop.title("Add Worker" if not labour_id else "Edit Worker")
    pop.geometry("800x680")
    pop.configure(bg=t["bg"])
    pop.grab_set()
    
    comp_id = getattr(parent_view.app, "active_company_id", 1)
    _, date_fmt_code = fetch_global_settings(comp_id)

    pop.update_idletasks()
    sw = pop.winfo_screenwidth(); sh = pop.winfo_screenheight()
    x = int((sw/2) - (800/2)); y = int((sh/2) - (680/2))
    pop.geometry(f"+{max(0,x)}+{max(0,y)}")

    style = ttk.Style(pop)
    style.configure("Worker.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], bordercolor=t["border"])
    style.map("Worker.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
    pop.option_add("*TCombobox*Listbox.background", t["card"])
    pop.option_add("*TCombobox*Listbox.foreground", t["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars ---
    
    # --- THE FIX: Use 'text_sec' instead of 'card' so the scrollbar is visible! ---
    style.configure("Dialog.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("Dialog.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    # ------------------------------------------------------------------------------

    tk.Label(pop, text=pop.title(), font=("Arial", 16, "bold"), bg=t["bg"], fg=t["text"]).pack(anchor="w", padx=20, pady=15)
    
    bottom_wrapper = tk.Frame(pop, bg=t["bg"])
    bottom_wrapper.pack(side="bottom", fill="x")
    tk.Frame(bottom_wrapper, bg=t["border"], height=1).pack(fill="x", padx=20, pady=(15, 10))

    container = tk.Frame(pop, bg=t["bg"])
    container.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    canvas = tk.Canvas(container, bg=t["bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Dialog.Vertical.TScrollbar")
    main_f = tk.Frame(canvas, bg=t["bg"])
    main_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=main_f, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        mult = int(-1*(event.delta/120)*2) if os.name == 'nt' else int(-1*event.delta)
        canvas.yview_scroll(mult, "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    left_f = tk.Frame(main_f, bg=t["bg"], width=180)
    left_f.pack(side="left", fill="y", padx=(0, 20))
    
    photo_var = tk.StringVar()
    photo_lbl = tk.Label(left_f, bg=t["card"], text="Click to\nAdd Photo", font=("Arial", 10), fg=t["text_sec"], cursor="hand2", highlightbackground=t["border"], highlightthickness=1)
    photo_lbl.pack(pady=10); photo_lbl.config(width=18, height=9) 
    
    def update_photo_preview(*args):
        path = photo_var.get()
        if path and os.path.exists(path):
            try:
                img = Image.open(path).convert("RGBA")
                img = ImageOps.fit(img, (140, 140), method=Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
                photo_img = ImageTk.PhotoImage(img)
                photo_lbl.config(image=photo_img, text="", width=140, height=140, highlightthickness=0, bd=2, relief="solid")
                photo_lbl.image = photo_img
            except: pass

    def browse_photo(e):
        path = filedialog.askopenfilename(parent=pop, title="Select Photo", filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        pop.lift(); pop.focus_force()
        if path: 
            if HAS_PIL: InteractiveCropper(pop, path, lambda final_path: [photo_var.set(final_path), update_photo_preview(), pop.lift(), pop.focus_force()])
            else: photo_var.set(path); update_photo_preview()

    photo_lbl.bind("<Button-1>", browse_photo)

    right_f = tk.Frame(main_f, bg=t["bg"])
    right_f.pack(side="left", fill="both", expand=True)

    profile_type_var = tk.StringVar(value="Individual") 
    
    # Fetch all existing IDs once for real-time validation
    all_existing_ids = database.get_all_labour_id_strings()

    id_container = tk.Frame(right_f, bg=t["bg"])
    id_container.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    id_frame = tk.Frame(id_container, bg=t["bg"])
    id_frame.pack(anchor="w")
    tk.Label(id_frame, text="Worker ID NO.", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=(0, 10))
    
    worker_id_var = tk.StringVar()
    id_ent = tk.Entry(id_frame, textvariable=worker_id_var, font=("Arial", 11, "bold"), width=15, bg=t["card"], fg=t["accent_blue"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    id_ent.pack(side="left", ipady=3)

    # Real-time Warning Label
    warn_lbl = tk.Label(id_container, text="⚠️ Worker ID already exists!", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["error"])

    def check_worker_id(*args):
        wid = worker_id_var.get().strip().lower()
        if not wid:
            warn_lbl.pack_forget()
            return
        is_dup = any((str(r_id) != str(labour_id) and e_str == wid) for r_id, e_str in all_existing_ids)
        if is_dup:
            warn_lbl.pack(anchor="w", padx=105, pady=(2, 0))
        else:
            warn_lbl.pack_forget()

    worker_id_var.trace_add("write", check_worker_id)
    
    def open_id_format():
        f_pop = tk.Toplevel(pop)
        f_pop.title("ID Format")
        f_pop.geometry("300x250")
        f_pop.configure(bg=t["bg"])
        f_pop.grab_set()
        
        prefix_key = f"lab_prefix_{comp_id}"
        seq_key = f"lab_seq_{comp_id}"
        
        tk.Label(f_pop, text="Prefix (e.g., LAB-, EMP-):", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(15,2))
        pref_var = tk.StringVar(value=database.get_ui_setting(prefix_key, "EMP-"))
        tk.Entry(f_pop, textvariable=pref_var, font=("Arial", 11), bg=t["card"], fg=t["text"]).pack(ipady=4)
        
        tk.Label(f_pop, text="Next Sequence Number:", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(15,2))
        seq_var = tk.StringVar(value=database.get_ui_setting(seq_key, "1"))
        tk.Entry(f_pop, textvariable=seq_var, font=("Arial", 11), bg=t["card"], fg=t["text"]).pack(ipady=4)
        
        def save_fmt():
            pref = pref_var.get()
            try: seq = int(seq_var.get())
            except: seq = 1
            
            # --- THE FIX: Use safe backend helper for instant scaling ---
            existing = [e[1] for e in database.get_all_labour_id_strings()]
            while f"{pref}{seq:04d}".lower() in existing:
                seq += 1
            # ------------------------------------------------------------
            
            database.save_ui_setting(prefix_key, pref)
            database.save_ui_setting(seq_key, str(seq))
            worker_id_var.set(f"{pref}{seq:04d}")
            f_pop.destroy()
            
        tk.Button(f_pop, text="Save Format", bg=t["accent_blue"], fg="white", font=("Arial", 10, "bold"), command=save_fmt).pack(pady=20, fill="x", padx=40)

    tk.Button(id_frame, text="⚙️ Format", font=("Arial", 9), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", command=open_id_format).pack(side="left", padx=10)

    tk.Label(right_f, text="Worker Full Name *", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 2))
    name_var = tk.StringVar()
    n_ent = tk.Entry(right_f, textvariable=name_var, font=("Arial", 11), width=45, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    n_ent.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 15), ipady=4); safe_copy_paste(n_ent)

    # --- THE FIX: DOB Field Added Here ---
    tk.Label(right_f, text="Date of Birth", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 2))
    dob_f = tk.Frame(right_f, bg=t["bg"])
    dob_f.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 15))
    dob_var = tk.StringVar()
    dob_ent = tk.Entry(dob_f, textvariable=dob_var, font=("Arial", 11), width=15, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    dob_ent.pack(side="left", ipady=3); safe_copy_paste(dob_ent)
    tk.Button(dob_f, text="📅", font=("Arial", 11), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", command=lambda: NativeCalendar(pop, dob_var)).pack(side="left", padx=5, ipady=1, ipadx=4)
    # -------------------------------------

    tk.Label(right_f, text="Contact Numbers", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 2))
    phones_frame = tk.Frame(right_f, bg=t["bg"])
    phones_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 10))
    phones_data = []

    def add_phone_field(pnum=""):
        if len(phones_data) >= 3:
            messagebox.showinfo("Limit reached", "Maximum of 3 phone numbers allowed.", parent=pop); return
        row = tk.Frame(phones_frame, bg=t["bg"])
        row.pack(fill="x", pady=3)
        n_var = tk.StringVar(value=pnum)
        ent = tk.Entry(row, textvariable=n_var, font=("Arial", 11), width=25, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
        ent.pack(side="left", fill="x", expand=True, ipady=3); safe_copy_paste(ent)

        def format_phone(*args, var=n_var, entry=ent):
            raw = var.get().replace("-", "")
            clean = ''.join(c for c in raw if c.isdigit())
            if len(clean) > 10: clean = clean[:10]
            fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
            if var.get() != fmt:
                var.set(fmt)
                entry.after(1, lambda: entry.icursor(tk.END))
                
        n_var.trace_add("write", format_phone)
        phones_data.append(n_var)

    tk.Button(right_f, text="+ Add another phone", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["accent_blue"], relief="flat", cursor="hand2", command=add_phone_field).grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 15))

    tk.Label(right_f, text="Blood Type", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=8, column=0, sticky="w", pady=(0, 2))
    blood_var = tk.StringVar(value="Unknown")
    blood_cb = ttk.Combobox(right_f, textvariable=blood_var, values=["Unknown", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], state="readonly", font=("Arial", 10), width=18, style="Worker.TCombobox")
    blood_cb.grid(row=9, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=3)
    blood_cb.bind("<MouseWheel>", lambda e: "break")

    tk.Label(right_f, text="Role / Designation", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=8, column=1, sticky="w", pady=(0, 2))
    role_var = tk.StringVar()
    r_ent = tk.Entry(right_f, textvariable=role_var, font=("Arial", 11), width=20, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    r_ent.grid(row=9, column=1, sticky="w", pady=(0, 15), ipady=4); safe_copy_paste(r_ent)

    tk.Label(right_f, text="Physical Address", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=10, column=0, columnspan=2, sticky="w", pady=(0, 2))
    addr_text = tk.Text(right_f, font=("Arial", 11), height=3, width=45, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    addr_text.grid(row=11, column=0, columnspan=2, sticky="w", pady=(0, 15))
    safe_copy_paste(addr_text)

    tk.Label(right_f, text="Emergency Contacts", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=12, column=0, columnspan=2, sticky="w", pady=(0, 2))
    emerg_frame = tk.Frame(right_f, bg=t["bg"])
    emerg_frame.grid(row=13, column=0, columnspan=2, sticky="w", pady=(0, 10))
    emerg_data = []

    def add_emerg_field(pnum=""):
        if len(emerg_data) >= 3:
            messagebox.showinfo("Limit reached", "Maximum of 3 emergency contacts allowed.", parent=pop); return
        row = tk.Frame(emerg_frame, bg=t["bg"])
        row.pack(fill="x", pady=3)
        n_var = tk.StringVar(value=pnum)
        ent = tk.Entry(row, textvariable=n_var, font=("Arial", 11), width=25, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
        ent.pack(side="left", fill="x", expand=True, ipady=3); safe_copy_paste(ent)

        def format_emerg(*args, var=n_var, entry=ent):
            raw = var.get().replace("-", "")
            clean = ''.join(c for c in raw if c.isdigit())
            if len(clean) > 10: clean = clean[:10]
            fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
            if var.get() != fmt:
                var.set(fmt)
                entry.after(1, lambda: entry.icursor(tk.END))
                
        n_var.trace_add("write", format_emerg)
        emerg_data.append(n_var)

    tk.Button(right_f, text="+ Add emergency contact", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["error"], relief="flat", cursor="hand2", command=add_emerg_field).grid(row=14, column=0, columnspan=2, sticky="w", pady=(0, 15))

    tk.Label(right_f, text="Documents & ID Files", font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).grid(row=15, column=0, columnspan=2, sticky="w", pady=(5, 2))
    doc_container = tk.Frame(right_f, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
    doc_container.grid(row=16, column=0, columnspan=2, sticky="ew")
    docs_list_f = tk.Frame(doc_container, bg=t["card"]); docs_list_f.pack(fill="x", padx=10, pady=10)
    docs_data = []

    def refresh_docs():
        for widget in docs_list_f.winfo_children(): widget.destroy()
        if not docs_data:
            tk.Label(docs_list_f, text="No documents attached yet.", font=("Arial", 9, "italic"), bg=t["card"], fg=t["text_sec"]).pack(anchor="w")
        for idx, d_var in enumerate(docs_data):
            row = tk.Frame(docs_list_f, bg=t["bg"], highlightbackground=t["border"], highlightthickness=1, pady=5, padx=5); row.pack(fill="x", pady=2)
            path = d_var.get()
            ext = os.path.splitext(path)[1].lower()
            if ext == '.pdf': icon = "📄"
            elif ext in ['.jpg', '.jpeg', '.png']: icon = "🖼️"
            else: icon = "📁"
            tk.Label(row, text=f"{icon} {os.path.basename(path)[:30]}", font=("Arial", 8), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=5)
            tk.Button(row, text="❌", font=("Arial", 8), bg=t["bg"], fg=t["error"], relief="flat", cursor="hand2", command=lambda i=idx: [docs_data.pop(i), refresh_docs()]).pack(side="right", padx=5)
            tk.Button(row, text="👁️", font=("Arial", 8), bg=t["bg"], fg=t["accent_blue"], relief="flat", cursor="hand2", command=lambda p=path: view_document(p, pop)).pack(side="right", padx=2)

    def browse_document():
        path = filedialog.askopenfilename(parent=pop, title="Select ID/Document", filetypes=[("All Files", "*.*"), ("PDF", "*.pdf"), ("Images", "*.png *.jpg *.jpeg")])
        pop.lift(); pop.focus_force()
        if path: 
            var = tk.StringVar(value=path)
            docs_data.append(var)
            refresh_docs()

    tk.Button(doc_container, text="📎 + Add Document", font=("Arial", 9, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", command=browse_document).pack(anchor="w", padx=10, pady=(0, 10))

    if labour_id:
        # --- THE FIX: Use safe dict helper instead of raw PRAGMA schema query! ---
        w_dict = database.get_labour_dict(labour_id)
        if w_dict:
            exist_id = str(w_dict.get('worker_id_str', ''))
        # -------------------------------------------------------------------------
            if not exist_id: exist_id = f"LAB-{int(labour_id):04d}"
            worker_id_var.set(exist_id)
            
            profile_type_var.set(w_dict.get('profile_type', 'Individual'))
            name_var.set(w_dict.get('name', ''))
            
            from views.invoice_parts.helpers import smart_date_formatter
            dob_var.set(smart_date_formatter(w_dict.get('dob', ''), date_fmt_code))
            
            raw_phone = w_dict.get('phone', '')
            if raw_phone:
                for p in raw_phone.split(","):
                    if p.strip(): add_phone_field(p.strip())
            else: add_phone_field("")
                
            addr_text.insert("1.0", w_dict.get('address', ''))
            blood_var.set(w_dict.get('blood_type', 'Unknown'))
            role_var.set(w_dict.get('role', ''))
            
            raw_emerg = w_dict.get('emergency_contact', '')
            if raw_emerg:
                for p in raw_emerg.split(","):
                    if p.strip(): add_emerg_field(p.strip())
            else: add_emerg_field("")
            
            photo_path = w_dict.get('photo_path', '')
            if photo_path and os.path.exists(photo_path):
                photo_var.set(photo_path)
                update_photo_preview()
                
            raw_docs = w_dict.get('doc_path', '')
            if raw_docs:
                try:
                    paths = json.loads(raw_docs)
                    for p in paths:
                        if p and os.path.exists(p): docs_data.append(tk.StringVar(value=p))
                except:
                    if os.path.exists(raw_docs): docs_data.append(tk.StringVar(value=raw_docs))
            refresh_docs()
    else:
        pref = database.get_ui_setting(f"lab_prefix_{comp_id}", "EMP-")
        try: seq = int(database.get_ui_setting(f"lab_seq_{comp_id}", "1"))
        except: seq = 1
        
        # --- THE FIX: Use safe backend helper for instant scaling ---
        existing = [e[1] for e in database.get_all_labour_id_strings()]
        while f"{pref}{seq:04d}".lower() in existing:
            seq += 1
        # ------------------------------------------------------------
        
        worker_id_var.set(f"{pref}{seq:04d}")
        
        add_phone_field("")
        add_emerg_field("")
        refresh_docs()

    def flash_red(widget):
        original_bg = t["border"]
        def toggle(count):
            if not widget.winfo_exists(): return
            if count > 0:
                widget.config(highlightbackground=t["error"] if count % 2 != 0 else original_bg)
                pop.after(150, toggle, count - 1)
            else: widget.config(highlightbackground=original_bg)
        toggle(6)

    def save_worker():
        name = name_var.get().strip()
        if not name:
            flash_red(n_ent)
            return
            
        wid = worker_id_var.get().strip()
        if not wid:
            messagebox.showerror("Error", "Worker ID cannot be empty.", parent=pop)
            flash_red(id_ent)
            return
            
        # --- THE FIX: Fast Duplicate Checking & Removed Raw SQL! ---
        all_ids = database.get_all_labour_id_strings()
        is_dup = any((str(r_id) != str(labour_id) and e_str == wid.lower()) for r_id, e_str in all_ids)
            
        if is_dup:
            messagebox.showerror("Duplicate ID", f"The ID '{wid}' is already assigned to another worker.\n\nPlease type a unique ID or use the 'Format' button to auto-generate the next available number.", parent=pop)
            flash_red(id_ent)
            return
            
        p_type = profile_type_var.get()
        d_rate = 0.0 

        phone_parts = [v.get().strip() for v in phones_data if v.get().strip()]
        combined_phone = ", ".join(phone_parts)
        
        emerg_parts = [v.get().strip() for v in emerg_data if v.get().strip()]
        combined_emerg = ", ".join(emerg_parts)
        
        address = addr_text.get("1.0", "end-1c").strip()
        
        try:
            # --- THE FIX: The Chicken & Egg Solution ---
            # 1. If this is a new worker, save them to the DB FIRST to generate an ID
            current_id = labour_id
            
            if not current_id:
                # 2. Grab the fresh ID securely directly from the insertion helper!
                current_id = database.add_labour(name, combined_phone, address, blood_var.get(), role_var.get(), "", "[]", p_type, d_rate, 0.0, 0.0, combined_emerg, worker_id_var.get(), dob_var.get())
                
                # --- THE FIX: Removed destructive auto-increment logic! ---
                # By not forcing the sequence to jump permanently in the database, 
                # the intelligent 'while' loop at the top of this file will automatically 
                # scan and fill any available gaps without skipping numbers.
                # ----------------------------------------------------------

            # 3. NOW generate the vault folder using the guaranteed ID!
            from views.invoice_parts.helpers import get_vault_path
            worker_folder = get_vault_path(ROOT_DIR, comp_id, name, "Labours", current_id)
            
            def secure_copy(filepath, prefix):
                if not filepath or not os.path.exists(filepath): return filepath
                try:
                    # If it's already inside the exact worker folder, skip copying
                    if os.path.abspath(worker_folder) == os.path.dirname(os.path.abspath(filepath)):
                        return filepath
                except: pass
                
                os.makedirs(worker_folder, exist_ok=True)
                ext = os.path.splitext(filepath)[1] or (".png" if prefix == "photo" else ".pdf")
                
                if prefix == "photo":
                    new_path = os.path.join(worker_folder, f"profile_photo{ext}")
                    try: 
                        if HAS_PIL:
                            with Image.open(filepath) as img:
                                img.thumbnail((400, 400))
                                if ext.lower() in ['.jpg', '.jpeg'] and img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(new_path)
                        else:
                            shutil.copy2(filepath, new_path)
                        return new_path
                    except: return filepath
                else:
                    safe_doc_name = f"doc_{int(time.time()*1000)}_{len(final_docs)}{ext}"
                    new_path = os.path.join(worker_folder, safe_doc_name)
                    try:
                        shutil.copy2(filepath, new_path)
                        return new_path
                    except: return filepath

            # 4. Safely move the profile photo
            final_photo = secure_copy(photo_var.get(), "photo")

            # 5. Safely move the documents
            final_docs = []
            for d_var in docs_data:
                d_path = d_var.get()
                if d_path and os.path.exists(d_path):
                    final_docs.append(secure_copy(d_path, "doc"))

            packed_docs = json.dumps(final_docs)

            # 6. Finally, UPDATE the record with the correct permanent file paths!
            database.update_labour(current_id, name, combined_phone, address, blood_var.get(), role_var.get(), final_photo, packed_docs, p_type, d_rate, 0.0, 0.0, combined_emerg, worker_id_var.get(), dob_var.get())
            # -------------------------------------------
            
            if labour_id:
                database.log_audit("Labours", "Edited Worker", record_ref=name, details="Updated worker profile and basic info.", company_id=comp_id)
            else:
                database.log_audit("Labours", "Added Worker", record_ref=name, details=f"Registered new worker with ID {worker_id_var.get()}", company_id=comp_id)
                
            parent_view.load_data()
            pop.destroy()
            
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=pop)

    tk.Button(bottom_wrapper, text="Save Worker", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=save_worker).pack(side="right", padx=20, pady=(0, 20))