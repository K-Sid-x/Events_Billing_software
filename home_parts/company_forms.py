import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import sys
import os
import shutil
import time
from datetime import datetime
from views.invoice_parts.calendar_widget import NativeCalendar
from views.invoice_parts.helpers import GST_STATE_CODES

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(parent_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

import database

try:
    from settings_parts.interactive_cropper import InteractiveCropper
except ImportError:
    InteractiveCropper = None

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = ImageTk = ImageDraw = None



def get_theme():
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    if is_dark:
        return {
            "bg": "#0f172a", "card": "#1e293b", "border": "#64748b", 
            "text": "#f8fafc", "sec": "#94a3b8", "accent_blue": "#3b82f6", "accent_green": "#10b981", "error": "#ef4444"
        }
    else:
        return {
            "bg": "#f0f9ff", "card": "#ffffff", "border": "#bae6fd", 
            "text": "#0f172a", "sec": "#0284c7", "accent_blue": "#0ea5e9", "accent_green": "#10b981", "error": "#ef4444"
        }

def enable_copy_paste(widget, theme):
    menu = tk.Menu(widget, tearoff=0, bg=theme["card"], fg=theme["text"], activebackground=theme["accent_blue"], activeforeground="#ffffff")
    menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
    def show_menu(e): menu.tk_popup(e.x_root, e.y_root)
    widget.bind("<Button-3>", show_menu)

def center_and_scale_window(window, width):
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    max_safe_height = screen_height - 120 
    calculated_height = min(850, max_safe_height)
    x = int((screen_width / 2) - (width / 2))
    y = int((screen_height / 2) - (calculated_height / 2) - 20)
    window.geometry(f"{width}x{calculated_height}+{x}+{y}")


def open_create_popup(home_view):
    if getattr(home_view.app, "current_role", "") != "Admin":
        messagebox.showerror("Access Denied", "Only the Master Admin can create a new company.", parent=home_view)
        return
    theme = get_theme()
    
    pop = tk.Toplevel(home_view)
    pop.title("Register New Company")
    pop.configure(bg=theme["card"])
    center_and_scale_window(pop, 700)
    pop.grab_set()

    style = ttk.Style()
    style.theme_use("default")
    
    style.configure("Form.Vertical.TScrollbar", background=theme["sec"], troughcolor=theme["card"], bordercolor=theme["card"], arrowcolor=theme["text"], relief="flat")
    style.map("Form.Vertical.TScrollbar", background=[("active", theme["accent_blue"])])
    
    style.configure("Theme.TCombobox", fieldbackground=theme["bg"], background=theme["card"], foreground=theme["text"], arrowcolor=theme["text"], bordercolor=theme["border"])
    style.map("Theme.TCombobox", fieldbackground=[("readonly", theme["bg"])], selectbackground=[("readonly", theme["bg"])], selectforeground=[("readonly", theme["text"])])
    pop.option_add("*TCombobox*Listbox.background", theme["card"])
    pop.option_add("*TCombobox*Listbox.foreground", theme["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", theme["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    canvas = tk.Canvas(pop, bg=theme["card"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(pop, orient="vertical", command=canvas.yview, style="Form.Vertical.TScrollbar")
    scroll_frame = tk.Frame(canvas, bg=theme["card"], padx=30, pady=20)

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=680)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    def _on_mousewheel(event): canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    pop.bind("<MouseWheel>", _on_mousewheel)

    tk.Label(scroll_frame, text="Business Setup", bg=theme["card"], font=("Segoe UI", 16, "bold"), fg=theme["text"]).pack(anchor="w", pady=(0, 20))

    logo_path = [""] 
    shape_var = tk.StringVar(value="Square")
    name_var = tk.StringVar()
    name_sec_var = tk.StringVar() 
    phone_var = tk.StringVar()
    email_var = tk.StringVar()
    gst_var = tk.IntVar(value=0); gstin_var = tk.StringVar(); state_var = tk.StringVar()
    btype_var = tk.StringVar(value="Service")
    fy_var = tk.StringVar(value="April") 
    pin_var = tk.StringVar()
    capital_var = tk.StringVar(value="0.00")
    capital_date_var = tk.StringVar(value=datetime.now().strftime("%d.%m.%Y"))
    pop.preview_img = None 

    def focus_next(event):
        event.widget.tk_focusNext().focus()
        return "break"

    tk.Label(scroll_frame, text="1. Company Branding", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(0, 10))
    
    preview_bg = theme["bg"]
    preview_frame = tk.Frame(scroll_frame, width=72, height=72, bg=preview_bg, highlightbackground=theme["border"], highlightthickness=1)
    preview_frame.pack_propagate(False)
    preview_frame.pack(anchor="w", pady=(0, 10))
    
    lbl_preview = tk.Label(preview_frame, text="No Logo", font=("Segoe UI", 8), bg=preview_bg, fg=theme["sec"])
    lbl_preview.pack(expand=True, fill="both")
    
    btn_logo = tk.Button(scroll_frame, text="📁 Upload Logo", font=("Segoe UI", 10, "bold"), bg=theme["bg"], fg=theme["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=2)
    btn_logo.pack(anchor="w", pady=(0, 5))

    def update_preview():
        if not logo_path[0] or not os.path.exists(logo_path[0]) or not Image:
            lbl_preview.config(image="", text="No Logo")
            btn_logo.config(text="📁 Upload Logo")
            return
        try:
            img = Image.open(logo_path[0]).convert("RGBA")
            try: resamp = Image.Resampling.LANCZOS
            except: resamp = Image.LANCZOS
            img.thumbnail((70, 70), resamp)
            
            if shape_var.get() == "Circle" and ImageDraw:
                scale = 4
                mask = Image.new("L", (img.size[0] * scale, img.size[1] * scale), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, img.size[0] * scale, img.size[1] * scale), fill=255)
                mask = mask.resize(img.size, resamp)
                
                circ = Image.new("RGBA", img.size, (0, 0, 0, 0))
                circ.paste(img, (0, 0), mask=mask)
                img = circ
                
            pop.preview_img = ImageTk.PhotoImage(img)
            lbl_preview.config(image=pop.preview_img, text="")
            btn_logo.config(text="📁 Change Logo")
        except: pass

    shape_var.trace_add("write", lambda *a: update_preview())

    def upload_logo():
        path = filedialog.askopenfilename(title="Select Logo", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path:
            if InteractiveCropper:
                def on_crop(cropped_path):
                    logo_path[0] = cropped_path
                    update_preview()
                InteractiveCropper(pop, path, on_crop)
            else:
                logo_path[0] = path
                update_preview()
    btn_logo.config(command=upload_logo)

    f_shape = tk.Frame(scroll_frame, bg=theme["card"])
    f_shape.pack(anchor="w", pady=(0, 20))
    tk.Label(f_shape, text="Logo Display Shape:", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
    tk.Radiobutton(f_shape, text="Square", variable=shape_var, value="Square", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)
    tk.Radiobutton(f_shape, text="Circle", variable=shape_var, value="Circle", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=10)

    tk.Label(scroll_frame, text="2. Business Details", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(10, 5))

    def make_entry(label_text, var):
        tk.Label(scroll_frame, text=label_text, bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        ent = tk.Entry(scroll_frame, textvariable=var, font=("Segoe UI", 11), width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        ent.pack(anchor="w", ipady=3)
        enable_copy_paste(ent, theme)
        ent.bind("<Return>", focus_next)
        return ent

    make_entry("Company Name *", name_var)
    make_entry("Secondary Company Name (Regional Language)", name_sec_var)
    
    tk.Label(scroll_frame, text="Company Address", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
    addr_text = tk.Text(scroll_frame, font=("Segoe UI", 11), height=3, width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    addr_text.pack(anchor="w")
    enable_copy_paste(addr_text, theme)

    ent_phone = make_entry("Primary Phone Number", phone_var)
    def format_phone(*args):
        raw = phone_var.get().replace("-", "")
        clean = ''.join(c for c in raw if c.isdigit())
        if len(clean) > 10: clean = clean[:10]
        fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
        if phone_var.get() != fmt:
            phone_var.set(fmt)
            ent_phone.after(1, lambda: ent_phone.icursor(tk.END))
    phone_var.trace_add("write", format_phone)

    make_entry("Email Address", email_var)
    
    tk.Label(scroll_frame, text="Opening Capital / Initial Bank Balance", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
    cap_f = tk.Frame(scroll_frame, bg=theme["card"])
    cap_f.pack(anchor="w")
    
    cap_ent = tk.Entry(cap_f, textvariable=capital_var, font=("Segoe UI", 11), width=20, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    cap_ent.pack(side="left", ipady=3)
    enable_copy_paste(cap_ent, theme)
    
    tk.Label(cap_f, text="As Of Date:", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(15, 5))
    cap_date_ent = tk.Entry(cap_f, textvariable=capital_date_var, font=("Segoe UI", 11), width=15, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    cap_date_ent.pack(side="left", ipady=3)
    if NativeCalendar:
        btn_cal = tk.Button(cap_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
        btn_cal.pack(side="left", padx=(5, 0))
        btn_cal.config(command=lambda b=btn_cal: NativeCalendar(pop, capital_date_var, anchor_widget=b))

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=15)
    
    tk.Label(scroll_frame, text="3. Software Logic", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(10, 5))

    tk.Checkbutton(scroll_frame, text="Enable GST Billing Features", variable=gst_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 5))
    
    gstin_container = tk.Frame(scroll_frame, bg=theme["card"])
    gstin_container.pack(fill="x")
    
    gstin_lbl = tk.Label(gstin_container, text="GSTIN Number", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold"))
    gstin_ent = tk.Entry(gstin_container, textvariable=gstin_var, font=("Segoe UI", 11), width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    enable_copy_paste(gstin_ent, theme)
    gstin_ent.bind("<Return>", focus_next)

    state_lbl = tk.Label(gstin_container, text="State / Province", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold"))
    state_combo = ttk.Combobox(gstin_container, textvariable=state_var, values=sorted(GST_STATE_CODES.values()), font=("Segoe UI", 11), state="readonly", width=53, style="Theme.TCombobox")
    
    def unbind_scroll(combo_widget):
        def prevent_scroll(event):
            _on_mousewheel(event)
            return "break" 
        combo_widget.bind("<MouseWheel>", prevent_scroll)
        combo_widget.bind("<Button-4>", prevent_scroll)
        combo_widget.bind("<Button-5>", prevent_scroll)

    unbind_scroll(state_combo)

    def validate_gstin(*args):
        val = gstin_var.get().upper()
        if gstin_var.get() != val: 
            gstin_var.set(val)
            gstin_ent.after(1, lambda: gstin_ent.icursor(tk.END)) 
            
        if len(val) >= 2:
            state_code = val[:2]
            if state_code in GST_STATE_CODES:
                state_var.set(GST_STATE_CODES[state_code])
                
        if len(val) == 15: 
            gstin_ent.config(highlightbackground=theme["accent_green"], highlightcolor=theme["accent_green"])
        elif len(val) > 0: 
            gstin_ent.config(highlightbackground=theme["error"], highlightcolor=theme["error"])
        else: 
            gstin_ent.config(highlightbackground=theme["border"], highlightcolor=theme["accent_blue"])
            
    gstin_var.trace_add("write", validate_gstin)

    def toggle_gst(*args):
        if gst_var.get() == 1:
            gstin_lbl.pack(anchor="w", pady=(5, 2))
            gstin_ent.pack(anchor="w", ipady=3)
            state_lbl.pack(anchor="w", pady=(10, 2))
            state_combo.pack(anchor="w", ipady=3)
        else:
            gstin_lbl.pack_forget()
            gstin_ent.pack_forget()
            state_lbl.pack_forget()
            state_combo.pack_forget()

    gst_var.trace("w", toggle_gst)
    toggle_gst()

    f_btype = tk.Frame(scroll_frame, bg=theme["card"])
    f_btype.pack(anchor="w", pady=(15, 5))
    tk.Label(f_btype, text="Business Type:", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
    tk.Radiobutton(f_btype, text="Service Based", variable=btype_var, value="Service", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)
    tk.Radiobutton(f_btype, text="Sales Based", variable=btype_var, value="Sales", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)

    f_fy = tk.Frame(scroll_frame, bg=theme["card"])
    f_fy.pack(anchor="w", pady=(5, 5))
    # --- THE FIX: This is correctly set to "readonly" so you can pick the month when creating a company ---
    tk.Label(f_fy, text="Financial Year Starts:", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
    fy_combo = ttk.Combobox(f_fy, textvariable=fy_var, values=["January", "April", "July"], state="readonly", width=15, style="Theme.TCombobox")
    fy_combo.pack(side="left", padx=5)
    unbind_scroll(fy_combo)

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=15)

    tk.Label(scroll_frame, text="Security Settings", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
    tk.Label(scroll_frame, text="Set a 4-digit PIN to lock this company (Leave blank for public access)", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 9)).pack(anchor="w")
    pin_entry = tk.Entry(scroll_frame, textvariable=pin_var, font=("Segoe UI", 11), width=20, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    pin_entry.pack(anchor="w", pady=(5, 10), ipady=3)

    def save():
        if not name_var.get().strip(): messagebox.showerror("Error", "Company Name is required.", parent=pop); return
        if pin_var.get().strip() and not pin_var.get().strip().isdigit(): messagebox.showerror("Error", "PIN must be numbers only.", parent=pop); return
        
        # --- NEW: Safely Copy Logo to Dedicated Folder ---
        final_logo_path = ""
        if logo_path[0] and os.path.exists(logo_path[0]):
            safe_dir = os.path.join(root_dir, "company_logos")
            os.makedirs(safe_dir, exist_ok=True)
            ext = os.path.splitext(logo_path[0])[1] or ".png"
            final_logo_path = os.path.join(safe_dir, f"logo_{int(time.time()*1000)}{ext}")
            try: 
                shutil.copy2(logo_path[0], final_logo_path)
                # Wipe the temp cropper file from the main folder
                if "cropped_" in logo_path[0] or "temp" in logo_path[0]:
                    try: os.remove(logo_path[0])
                    except: pass
            except: 
                final_logo_path = logo_path[0]
        # -------------------------------------------------
        
        default_json = {
            "fonts": {"name": 22, "sec": 16, "addr": 10, "contact": 10, "gst": 10},
            "pos": {"logo": [20, 20], "name": [180, 20], "sec": [180, 55], "addr": [180, 85], "contact": [180, 120], "gst": [180, 155]},
            "business_type": btype_var.get(),
            "state": state_var.get(),
            "fy_start": fy_var.get(),
            "opening_capital": capital_var.get().strip() or "0.00",
            "opening_capital_date": capital_date_var.get().strip()
        }

        # --- THE FIX: Safely capture the exact ID returned by our upgraded database helper! ---
        new_id = database.add_company(
            name_var.get().strip(), name_sec_var.get().strip(), addr_text.get("1.0", "end-1c").strip(), phone_var.get().strip(), "", "", email_var.get().strip(), 
            gst_var.get(), gstin_var.get().strip(), final_logo_path, 
            "Classic", 120, shape_var.get(), json.dumps(default_json), pin_var.get().strip()
        )
        
        state_val = state_var.get()
        state_code = state_val.split("Code - ")[1].strip() if "Code - " in state_val else ""
        
        database.update_company_tax_profile(new_id, state_val, state_code, btype_var.get())
        # --------------------------------------------------------------------------------------
        
        home_view.load_companies()
        pop.destroy()

    btn_save = tk.Button(scroll_frame, text="Create Company", bg=theme["accent_blue"], fg="#ffffff", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=30, pady=5, relief="flat", command=save)
    btn_save.pack(pady=20)


def open_edit_popup(home_view, comp_id):
    if getattr(home_view.app, "current_role", "") != "Admin":
        messagebox.showerror("Access Denied", "Only the Master Admin can edit company details.", parent=home_view)
        return
    comp = database.get_company(comp_id)
    if not comp: return

    theme = get_theme()

    pop = tk.Toplevel(home_view)
    pop.title("Edit Company Details")
    pop.configure(bg=theme["card"])
    center_and_scale_window(pop, 700)
    pop.grab_set()

    style = ttk.Style()
    
    # --- THE FIX: Switched to 'default' theme to perfectly match Stock scrollbars! ---
    style.theme_use("default")
    style.configure("Form.Vertical.TScrollbar", background=theme["sec"], troughcolor=theme["card"], bordercolor=theme["card"], arrowcolor=theme["text"], relief="flat")
    style.map("Form.Vertical.TScrollbar", background=[("active", theme["accent_blue"])])
    # ---------------------------------------------------------------------------------
    
    style.configure("Theme.TCombobox", fieldbackground=theme["bg"], background=theme["card"], foreground=theme["text"], arrowcolor=theme["text"], bordercolor=theme["border"])
    style.map("Theme.TCombobox", fieldbackground=[("readonly", theme["bg"])], selectbackground=[("readonly", theme["bg"])], selectforeground=[("readonly", theme["text"])])
    pop.option_add("*TCombobox*Listbox.background", theme["card"])
    pop.option_add("*TCombobox*Listbox.foreground", theme["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", theme["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    canvas = tk.Canvas(pop, bg=theme["card"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(pop, orient="vertical", command=canvas.yview, style="Form.Vertical.TScrollbar")
    scroll_frame = tk.Frame(canvas, bg=theme["card"], padx=30, pady=20)

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=680)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    def _on_mousewheel(event): canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    pop.bind("<MouseWheel>", _on_mousewheel)

    tk.Label(scroll_frame, text="Edit Business Setup", bg=theme["card"], font=("Segoe UI", 16, "bold"), fg=theme["text"]).pack(anchor="w", pady=(0, 20))

    try: t_json = json.loads(comp[14]) if len(comp)>14 and comp[14] else {}
    except: t_json = {}

    logo_path = [comp[10]] 
    shape_var = tk.StringVar(value=comp[13] if len(comp)>13 and comp[13] else "Square")
    name_var = tk.StringVar(value=comp[1])
    name_sec_var = tk.StringVar(value=comp[2] if len(comp)>2 and comp[2] else "")  
    phone_var = tk.StringVar(value=comp[4])
    email_var = tk.StringVar(value=comp[7])
    gst_var = tk.IntVar(value=comp[8])
    gstin_var = tk.StringVar(value=comp[9])
    state_var = tk.StringVar(value=t_json.get("state", ""))
    btype_var = tk.StringVar(value=t_json.get("business_type", "Service"))
    fy_var = tk.StringVar(value=t_json.get("fy_start", "April")) 
    capital_var = tk.StringVar(value=t_json.get("opening_capital", "0.00"))
    capital_date_var = tk.StringVar(value=t_json.get("opening_capital_date", datetime.now().strftime("%d.%m.%Y")))
    
    existing_pin = comp[15] if len(comp) > 15 else ""
    new_pin_var = tk.StringVar()
    remove_pin_var = tk.IntVar(value=0)
    
    pop.preview_img = None 

    def focus_next(event):
        event.widget.tk_focusNext().focus()
        return "break"

    tk.Label(scroll_frame, text="1. Company Branding", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(0, 10))
    
    preview_bg = theme["bg"]
    preview_frame = tk.Frame(scroll_frame, width=72, height=72, bg=preview_bg, highlightbackground=theme["border"], highlightthickness=1)
    preview_frame.pack_propagate(False)
    preview_frame.pack(anchor="w", pady=(0, 10))
    
    lbl_preview = tk.Label(preview_frame, text="No Logo", font=("Segoe UI", 8), bg=preview_bg, fg=theme["sec"])
    lbl_preview.pack(expand=True, fill="both")
    
    btn_logo = tk.Button(scroll_frame, text="📁 Change Logo" if logo_path[0] else "📁 Upload Logo", font=("Segoe UI", 10, "bold"), bg=theme["bg"], fg=theme["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=2)
    btn_logo.pack(anchor="w", pady=(0, 5))

    def update_preview():
        if not logo_path[0] or not os.path.exists(logo_path[0]) or not Image:
            lbl_preview.config(image="", text="No Logo")
            btn_logo.config(text="📁 Upload Logo")
            return
        try:
            img = Image.open(logo_path[0]).convert("RGBA")
            try: resamp = Image.Resampling.LANCZOS
            except: resamp = Image.LANCZOS
            img.thumbnail((70, 70), resamp)
            
            if shape_var.get() == "Circle" and ImageDraw:
                scale = 4
                mask = Image.new("L", (img.size[0] * scale, img.size[1] * scale), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, img.size[0] * scale, img.size[1] * scale), fill=255)
                mask = mask.resize(img.size, resamp)
                
                circ = Image.new("RGBA", img.size, (0, 0, 0, 0))
                circ.paste(img, (0, 0), mask=mask)
                img = circ
                
            pop.preview_img = ImageTk.PhotoImage(img)
            lbl_preview.config(image=pop.preview_img, text="")
            btn_logo.config(text="📁 Change Logo")
        except: pass

    update_preview()
    shape_var.trace_add("write", lambda *a: update_preview())

    def upload_logo():
        path = filedialog.askopenfilename(title="Select Logo", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path:
            if InteractiveCropper:
                def on_crop(cropped_path):
                    logo_path[0] = cropped_path
                    update_preview()
                InteractiveCropper(pop, path, on_crop)
            else:
                logo_path[0] = path
                update_preview()
    btn_logo.config(command=upload_logo)

    f_shape = tk.Frame(scroll_frame, bg=theme["card"])
    f_shape.pack(anchor="w", pady=(0, 20))
    tk.Label(f_shape, text="Logo Display Shape:", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
    tk.Radiobutton(f_shape, text="Square", variable=shape_var, value="Square", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)
    tk.Radiobutton(f_shape, text="Circle", variable=shape_var, value="Circle", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], cursor="hand2").pack(side="left", padx=5)

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=10)

    tk.Label(scroll_frame, text="2. Business Details", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(10, 5))

    def make_entry(label_text, var):
        tk.Label(scroll_frame, text=label_text, bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        ent = tk.Entry(scroll_frame, textvariable=var, font=("Segoe UI", 11), width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        ent.pack(anchor="w", ipady=3)
        enable_copy_paste(ent, theme)
        ent.bind("<Return>", focus_next)
        return ent

    make_entry("Company Name *", name_var)
    make_entry("Secondary Company Name (Regional Language)", name_sec_var) 
    
    tk.Label(scroll_frame, text="Company Address", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
    addr_text = tk.Text(scroll_frame, font=("Segoe UI", 11), height=3, width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    addr_text.pack(anchor="w")
    addr_text.insert("end", comp[3])
    enable_copy_paste(addr_text, theme)

    ent_phone = make_entry("Primary Phone Number", phone_var)
    def format_phone(*args):
        raw = phone_var.get().replace("-", "")
        clean = ''.join(c for c in raw if c.isdigit())
        if len(clean) > 10: clean = clean[:10]
        fmt = f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean
        if phone_var.get() != fmt:
            phone_var.set(fmt)
            ent_phone.after(1, lambda: ent_phone.icursor(tk.END))
    phone_var.trace_add("write", format_phone)
    format_phone() 

    make_entry("Email Address", email_var)
    
    tk.Label(scroll_frame, text="Opening Capital / Initial Bank Balance", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
    cap_f = tk.Frame(scroll_frame, bg=theme["card"])
    cap_f.pack(anchor="w")
    
    cap_ent = tk.Entry(cap_f, textvariable=capital_var, font=("Segoe UI", 11), width=20, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    cap_ent.pack(side="left", ipady=3)
    enable_copy_paste(cap_ent, theme)
    
    tk.Label(cap_f, text="As Of Date:", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(15, 5))
    cap_date_ent = tk.Entry(cap_f, textvariable=capital_date_var, font=("Segoe UI", 11), width=15, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    cap_date_ent.pack(side="left", ipady=3)
    if NativeCalendar:
        btn_cal = tk.Button(cap_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
        btn_cal.pack(side="left", padx=(5, 0))
        btn_cal.config(command=lambda b=btn_cal: NativeCalendar(pop, capital_date_var, anchor_widget=b))

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=15)
    
    tk.Label(scroll_frame, text="3. Software Logic", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(10, 5))

    tk.Checkbutton(scroll_frame, text="Enable GST Billing Features (Cannot be changed after creation)", variable=gst_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], font=("Segoe UI", 10, "bold"), state="disabled").pack(anchor="w", pady=(5, 5))
    
    gstin_container = tk.Frame(scroll_frame, bg=theme["card"])
    gstin_container.pack(fill="x")
    
    gstin_lbl = tk.Label(gstin_container, text="GSTIN Number (Cannot be changed)", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold"))
    gstin_ent = tk.Entry(gstin_container, textvariable=gstin_var, font=("Segoe UI", 11), width=55, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1, state="readonly", readonlybackground=theme["bg"])
    enable_copy_paste(gstin_ent, theme)
    gstin_ent.bind("<Return>", focus_next)

    state_lbl = tk.Label(gstin_container, text="State / Province (Cannot be changed)", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold"))
    state_combo = ttk.Combobox(gstin_container, textvariable=state_var, values=sorted(GST_STATE_CODES.values()), font=("Segoe UI", 11), state="disabled", width=53, style="Theme.TCombobox")
    
    def unbind_scroll(combo_widget):
        def prevent_scroll(event):
            _on_mousewheel(event)
            return "break" 
        combo_widget.bind("<MouseWheel>", prevent_scroll)
        combo_widget.bind("<Button-4>", prevent_scroll)
        combo_widget.bind("<Button-5>", prevent_scroll)

    unbind_scroll(state_combo)

    def validate_gstin(*args):
        val = gstin_var.get().upper()
        if gstin_var.get() != val: 
            gstin_var.set(val)
            gstin_ent.after(1, lambda: gstin_ent.icursor(tk.END)) 
            
        if len(val) >= 2:
            state_code = val[:2]
            if state_code in GST_STATE_CODES:
                state_var.set(GST_STATE_CODES[state_code])
                
        if len(val) == 15: 
            gstin_ent.config(highlightbackground=theme["accent_green"], highlightcolor=theme["accent_green"])
        elif len(val) > 0: 
            gstin_ent.config(highlightbackground=theme["error"], highlightcolor=theme["error"])
        else: 
            gstin_ent.config(highlightbackground=theme["border"], highlightcolor=theme["accent_blue"])
            
    gstin_var.trace_add("write", validate_gstin)
    validate_gstin()

    def toggle_gst(*args):
        if gst_var.get() == 1:
            gstin_lbl.pack(anchor="w", pady=(5, 2))
            gstin_ent.pack(anchor="w", ipady=3)
            state_lbl.pack(anchor="w", pady=(10, 2))
            state_combo.pack(anchor="w", ipady=3)
        else:
            gstin_lbl.pack_forget()
            gstin_ent.pack_forget()
            state_lbl.pack_forget()
            state_combo.pack_forget()

    gst_var.trace("w", toggle_gst)
    toggle_gst()

    f_btype = tk.Frame(scroll_frame, bg=theme["card"])
    f_btype.pack(anchor="w", pady=(15, 5))
    tk.Label(f_btype, text="Business Type (Cannot be changed after creation):", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
    tk.Radiobutton(f_btype, text="Service Based", variable=btype_var, value="Service", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], state="disabled").pack(side="left", padx=5)
    tk.Radiobutton(f_btype, text="Sales Based", variable=btype_var, value="Sales", bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], state="disabled").pack(side="left", padx=5)

    f_fy = tk.Frame(scroll_frame, bg=theme["card"])
    f_fy.pack(anchor="w", pady=(5, 5))
    # --- THE FIX: This is now locked so users don't break sequence numbering on edits! ---
    tk.Label(f_fy, text="Financial Year Starts (Cannot be changed after creation):", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
    fy_combo = ttk.Combobox(f_fy, textvariable=fy_var, values=["January", "April", "July"], state="disabled", width=15, style="Theme.TCombobox")
    fy_combo.pack(side="left", padx=5)
    unbind_scroll(fy_combo)

    tk.Frame(scroll_frame, bg=theme["border"], height=1).pack(fill="x", pady=15)

    tk.Label(scroll_frame, text="Security Settings", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 11, "bold", "underline")).pack(anchor="w", pady=(0, 10))
    
    if existing_pin:
        tk.Label(scroll_frame, text="Current Status: 🔒 PIN Protected", bg=theme["card"], fg=theme["accent_green"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        
        tk.Checkbutton(scroll_frame, text="Remove PIN completely (Make public)", variable=remove_pin_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"], font=("Segoe UI", 9)).pack(anchor="w")
        
        tk.Label(scroll_frame, text="Or set a NEW 4-digit PIN (Leave blank to keep current):", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 9)).pack(anchor="w", pady=(15, 2))
    else:
        tk.Label(scroll_frame, text="Current Status: 🔓 Unprotected", bg=theme["card"], fg=theme["sec"], font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))
        tk.Label(scroll_frame, text="Set a 4-digit PIN to lock this company:", bg=theme["card"], fg=theme["text"], font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 2))
        
    pin_entry = tk.Entry(scroll_frame, textvariable=new_pin_var, font=("Segoe UI", 11), width=20, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    pin_entry.pack(anchor="w", pady=(0, 10), ipady=3)

    def save():
        if not name_var.get().strip(): messagebox.showerror("Error", "Company Name is required.", parent=pop); return
        
        final_pin = existing_pin
        if remove_pin_var.get() == 1:
            final_pin = ""
        elif new_pin_var.get().strip():
            if not new_pin_var.get().strip().isdigit(): 
                messagebox.showerror("Error", "PIN must be numbers only.", parent=pop)
                return
            final_pin = new_pin_var.get().strip()

        # --- THE FIX: Safely Copy New Logo & Delete the Old Orphaned Logo ---
        final_logo_path = logo_path[0]
        if logo_path[0] and os.path.exists(logo_path[0]) and "company_logos" not in logo_path[0]:
            safe_dir = os.path.join(root_dir, "company_logos")
            os.makedirs(safe_dir, exist_ok=True)
            ext = os.path.splitext(logo_path[0])[1] or ".png"
            final_logo_path = os.path.join(safe_dir, f"logo_{int(time.time()*1000)}{ext}")
            try: 
                shutil.copy2(logo_path[0], final_logo_path)
                
                # Wipe the temp cropper file from the main folder
                if "cropped_" in logo_path[0] or "temp" in logo_path[0]:
                    try: os.remove(logo_path[0])
                    except: pass
                    
                # Wipe the old logo from the hard drive since it is being replaced
                if comp[10] and os.path.exists(comp[10]) and "company_logos" in comp[10]:
                    try: os.remove(comp[10])
                    except: pass
            except: 
                final_logo_path = logo_path[0]
        # --------------------------------------------------------------------

        t_json["business_type"] = btype_var.get()
        t_json["state"] = state_var.get()
        t_json["fy_start"] = fy_var.get()
        t_json["opening_capital"] = capital_var.get().strip() or "0.00"
        t_json["opening_capital_date"] = capital_date_var.get().strip()

        database.update_company(
            comp_id, name_var.get().strip(), name_sec_var.get().strip(), addr_text.get("1.0", "end-1c").strip(), 
            phone_var.get().strip(), comp[5], comp[6], email_var.get().strip(), 
            gst_var.get(), gstin_var.get().strip(), final_logo_path, 
            comp[11], comp[12], shape_var.get(), json.dumps(t_json), final_pin
        )
        
        # --- Tax Profile Security ---
        state_val = state_var.get()
        state_code = state_val.split("Code - ")[1].strip() if "Code - " in state_val else ""
        database.update_company_tax_profile(comp_id, state_val, state_code, btype_var.get())
        
        home_view.load_companies()
        pop.destroy()
        messagebox.showinfo("Success", "Company Details Updated!")

    btn_save = tk.Button(scroll_frame, text="Save Updates", bg=theme["accent_blue"], fg="#ffffff", font=("Segoe UI", 11, "bold"), cursor="hand2", padx=30, pady=5, relief="flat", command=save)
    btn_save.pack(pady=20)