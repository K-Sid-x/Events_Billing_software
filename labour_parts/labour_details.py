import tkinter as tk
from tkinter import ttk
import os
import tempfile
import webbrowser
import base64
import json
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

# --- THE FIX: Import Date Formatters ---
from views.invoice_parts.helpers import fetch_global_settings, smart_date_formatter
# ---------------------------------------

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def view_document(path, parent):
    if not path or not os.path.exists(path): return
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.pdf':
        webbrowser.open('file://' + os.path.realpath(path))
    elif ext in ['.jpg', '.jpeg', '.png']:
        pop = tk.Toplevel(parent)
        pop.title("Document Viewer")
        pop.geometry("700x700")
        pop.configure(bg="#0f172a")
        pop.grab_set()
        
        try:
            img = Image.open(path)
            resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
            img.thumbnail((650, 650), resamp)
            tk_img = ImageTk.PhotoImage(img)
            lbl = tk.Label(pop, image=tk_img, bg="#0f172a")
            lbl.image = tk_img
            lbl.pack(expand=True, fill="both")
        except:
            tk.Label(pop, text="Failed to load image.", fg="white", bg="#0f172a").pack(expand=True)

def view_labour_details(parent_view, labour_id):
    # --- THE FIX: Use safe dict helper instead of raw PRAGMA schema query! ---
    w_dict = database.get_labour_dict(labour_id)
    if not w_dict: return
    # -------------------------------------------------------------------------
    
    t = parent_view.colors
    app = parent_view.app
    try:
        comp_id = getattr(app, "active_company_id", 1)
        comp = database.get_company(comp_id) if comp_id else database.get_company(1)
        comp_name = comp[1] if comp else "COMPANY NAME"
    except:
        comp_name = "COMPANY NAME"

    pop = tk.Toplevel(parent_view)
    pop.title(f"Details: {w_dict.get('name', 'Worker')}")
    # --- THE FIX: Widen window so "View" buttons are never pushed under the scrollbar ---
    pop.geometry("550x600")
    # -----------------------------------------------------------------------------------
    pop.configure(bg=t["bg"])
    pop.grab_set() # <--- THE BUG FIX FOR THE FREEZE
    
    tk.Label(pop, text="Worker Full Details", font=("Arial", 18, "bold"), bg=t["bg"], fg=t["text"]).pack(pady=(20, 10), padx=20, anchor="w")
    
    emp_photo = w_dict.get('photo_path', '')

    def print_id_card():
        # --- THE FIX: Fetch Company Logo & Format Worker ID ---
        comp_logo = comp[10] if comp and len(comp) > 10 else ""
        comp_logo_html = ""
        if comp_logo and os.path.exists(comp_logo):
            try:
                with open(comp_logo, "rb") as l_file:
                    comp_logo_html = f'<img src="data:image/png;base64,{base64.b64encode(l_file.read()).decode()}" style="max-height: 35px; max-width: 150px; margin-bottom: 5px; object-fit: contain;"><br>'
            except: pass
            
        worker_id_str = str(w_dict.get('worker_id_str', ''))
        if not worker_id_str: worker_id_str = f"LAB-{int(w_dict.get('id', 0)):04d}"
        
        img_html = ""
        if emp_photo and os.path.exists(emp_photo):
            try:
                with open(emp_photo, "rb") as img_file:
                    b64_string = base64.b64encode(img_file.read()).decode()
                import mimetypes
                mime_type, _ = mimetypes.guess_type(emp_photo)
                if not mime_type: mime_type = "image/png"
                img_html = f'<img src="data:{mime_type};base64,{b64_string}" alt="Photo">'
            except: img_html = '<div class="no-photo">👤</div>'
        else: img_html = '<div class="no-photo">👤</div>'

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
        
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>ID Card - {w_dict.get('name', '')}</title>
            <style>
                @media print {{ @page {{ margin: 0; size: auto; }} body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
                body {{ display: flex; justify-content: center; padding-top: 50px; font-family: 'Arial', sans-serif; background: #f1f5f9; gap: 30px; }}
                .id-card {{ width: 270px; height: 410px; background: white; border: 2px solid #cbd5e1; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; padding: 25px 20px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; position: relative; overflow: hidden; }}
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
            <script>window.onload = function() {{ window.print(); }}</script>
        </body>
        </html>
        """
        # --- THE FIX: Tagged prefix for the Sweeper ---
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Labour_ID_Card_")
        with os.fdopen(fd, 'w', encoding='utf-8') as html_file: html_file.write(html_content)
        webbrowser.open('file://' + os.path.realpath(path))

    btn_print = tk.Button(pop, text="🪪 Print ID Card", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", pady=10, command=print_id_card)
    btn_print.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

    container = tk.Frame(pop, bg=t["bg"])
    container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    style = ttk.Style(pop)
    style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars ---
    
    # --- THE FIX: Thick Dark Scrollbar for Details Canvas ---
    style.configure("Details.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("Details.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    # --------------------------------------------------------
    
    canvas = tk.Canvas(container, bg=t["bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Details.Vertical.TScrollbar")
    f = tk.Frame(canvas, bg=t["card"], padx=20, pady=10, highlightbackground=t["border"], highlightthickness=1)
    
    f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=f, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    pop.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1*(event.delta/120)*2) if os.name=='nt' else int(-1*event.delta), "units"))

    photo_f = tk.Frame(f, bg=t["card"])
    photo_f.grid(row=0, column=0, columnspan=2, pady=(0, 20))
    photo_lbl = tk.Label(photo_f, bg=t["card"], highlightthickness=0, bd=0); photo_lbl.pack()
    
    if emp_photo and os.path.exists(emp_photo) and HAS_PIL:
        try:
            img = Image.open(emp_photo).convert("RGBA")
            img = ImageOps.fit(img, (120, 120), method=Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            photo_lbl.config(image=photo_img, bd=2, relief="solid")
            photo_lbl.image = photo_img
        except: photo_lbl.config(text="👤", font=("Arial", 48), fg=t["text_sec"], width=3, height=1)
    else: photo_lbl.config(text="👤", font=("Arial", 48), fg=t["text_sec"], width=3, height=1)

    def clean_ui_val(v):
        return str(v).strip() if v and str(v).lower() not in ("none", "unknown", "") else "—"

    worker_id_str = str(w_dict.get('worker_id_str', ''))
    if not worker_id_str: worker_id_str = f"LAB-{int(w_dict.get('id', 0)):04d}"
    
    # --- THE FIX: Format Date of Birth ---
    dob_val = w_dict.get('dob', '')
    if dob_val:
        try:
            comp_id = getattr(parent_view.app, "active_company_id", 1)
            _, date_fmt_code = fetch_global_settings(comp_id)
            dob_val = smart_date_formatter(dob_val, date_fmt_code)
        except: pass
    # -------------------------------------

    labels = [
        ("Worker ID:", worker_id_str),
        ("Name:", clean_ui_val(w_dict.get('name'))), 
        ("Date of Birth:", clean_ui_val(dob_val)),
        ("Contact Numbers:", clean_ui_val(w_dict.get('phone'))),
        ("Emergency Contact:", clean_ui_val(w_dict.get('emergency_contact'))),
        ("Blood Type:", clean_ui_val(w_dict.get('blood_type'))),
        ("Role:", clean_ui_val(w_dict.get('role')))
    ]

    def show_copy_menu(event, text_widget):
        try:
            text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            menu = tk.Menu(pop, tearoff=0, font=("Segoe UI", 10), bg=t["card"], fg=t["text"])
            menu.add_command(label="📋 Copy", command=lambda: text_widget.event_generate("<<Copy>>"))
            menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            pass
            
    for i, (lbl, val) in enumerate(labels, start=1):
        tk.Label(f, text=lbl, font=("Arial", 10, "bold"), bg=t["card"], fg=t["text_sec"]).grid(row=i, column=0, sticky="ne", pady=8, padx=(0,15))
        
        lines = str(val).count('\n') + (len(str(val)) // 28) + 1
        txt = tk.Text(f, font=("Arial", 12), bg=t["card"], fg=t["text"], bd=0, highlightthickness=0, wrap="word", height=lines, width=28)
        txt.insert("1.0", val)
        txt.configure(state="disabled") 
        txt.bind("<Button-3>", lambda e, tw=txt: show_copy_menu(e, tw))
        txt.grid(row=i, column=1, sticky="w", pady=8)

    # Document Viewer Section
    raw_docs = w_dict.get('doc_path', '')
    docs = []
    if raw_docs:
        try:
            docs = json.loads(raw_docs)
        except:
            if os.path.exists(raw_docs): docs = [raw_docs]
            
    if docs:
        tk.Label(f, text="Documents:", font=("Arial", 10, "bold"), bg=t["card"], fg=t["text_sec"]).grid(row=len(labels)+1, column=0, sticky="ne", pady=8, padx=(0,15))
        doc_f = tk.Frame(f, bg=t["card"])
        doc_f.grid(row=len(labels)+1, column=1, sticky="w", pady=8)
        
        for d in docs:
            if os.path.exists(d):
                row_f = tk.Frame(doc_f, bg=t["bg"], pady=4, padx=8, highlightbackground=t["border"], highlightthickness=1)
                row_f.pack(fill="x", pady=2)
                
                # --- THE FIX: Added dynamic document icons to match Employees ---
                ext = os.path.splitext(d)[1].lower()
                if ext == '.pdf': icon = "📄"
                elif ext in ['.jpg', '.jpeg', '.png']: icon = "🖼️"
                elif ext in ['.doc', '.docx']: icon = "📝"
                elif ext in ['.xls', '.xlsx', '.csv']: icon = "📊"
                else: icon = "📁"
                
                # --- THE FIX: Hard-limit the width and force Left-Anchor so it truncates instead of stretching! ---
                tk.Label(row_f, text=f"{icon} {os.path.basename(d)}", width=25, anchor="w", font=("Arial", 9), bg=t["bg"], fg=t["text"]).pack(side="left", padx=5)
                # --------------------------------------------------------------------------------------------------
                tk.Button(row_f, text="👁️ View", font=("Arial", 8, "bold"), bg=t["accent_blue"], fg="white", relief="flat", cursor="hand2", command=lambda path=d: view_document(path, pop)).pack(side="right", padx=5)