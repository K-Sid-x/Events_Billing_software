import tkinter as tk
from tkinter import ttk
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

from utils.print_parts.canvas_engine import draw_pages
from utils.print_parts.pdf_engine import perform_print, send_to_whatsapp

class PrintStudio(tk.Toplevel):
    def __init__(self, parent, inv_data, items_data, comp_dict, banks_data, settings):
        super().__init__(parent)
        self.title(f"Print Studio: {inv_data.get('inv_num', '')}")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(bg="#525659")
        
        # Forces the Live Preview to open maximized safely
        try:
            self.state('zoomed')
        except:
            self.attributes('-zoomed', True)
            
        self.grab_set()

        self.inv_data = inv_data
        self.items_data = items_data
        self.comp_dict = comp_dict
        self.banks_data = banks_data
        self.settings = settings

        self.zoom_var = tk.IntVar(value=100)
        self.current_page_var = tk.StringVar(value="1")
        self.page_wrappers = []
        self.total_pages = 1

        self.sizes = {
            "A4 (210*297mm)": {"px": (794, 1123), "mm": (210, 297)},
            "Letter (216*279mm)": {"px": (816, 1054), "mm": (216, 279)},
            "Tabloid (279*432mm)": {"px": (1054, 1633), "mm": (279, 432)},
            "Legal (216*356mm)": {"px": (816, 1346), "mm": (216, 356)},
            "A5 (148*210mm)": {"px": (559, 794), "mm": (148, 210)}
        }

        self.setup_styles()
        self.setup_sidebar()
        self.setup_preview()
        
        # Give the operating system 150 milliseconds to finish maximizing the window 
        # before Python calculates the canvas sizes!
        self.after(150, self.update_canvas_size)

    def setup_styles(self):
        self.style = ttk.Style()
        
        # --- THE FIX: Removed theme_use('clam') to prevent the White Void Bug! ---
        
        # Configure advanced layout mapping for Combobox components
        self.style.configure("StudioDark.TCombobox", 
                             fieldbackground="#3d3d3d", 
                             background="#4a4a4a", 
                             foreground="#ffffff", 
                             bordercolor="#1a1a1a", 
                             darkcolor="#3d3d3d", 
                             lightcolor="#4a4a4a",
                             arrowcolor="#ffffff",
                             padding=5)
                             
        self.style.map("StudioDark.TCombobox", 
                       fieldbackground=[('readonly', '#3d3d3d')],
                       foreground=[('readonly', '#ffffff')])
                       
        # Fix dropdown overlay colors popups
        self.option_add("*TCombobox*Listbox.background", "#3d3d3d")
        self.option_add("*TCombobox*Listbox.foreground", "#ffffff")
        self.option_add("*TCombobox*Listbox.selectBackground", "#11c176")
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", ("Arial", 10))

    def setup_sidebar(self):
        sidebar = tk.Frame(self, bg="#2b2b2b", width=320)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        side_inner = tk.Frame(sidebar, bg="#2b2b2b", padx=25, pady=30)
        side_inner.pack(fill="both", expand=True)

        # Back Button Navigation
        btn_back = tk.Button(side_inner, text="← Back", font=("Arial", 11), relief="flat", cursor="hand2", 
                             command=self.destroy, bg="#2b2b2b", fg="#ffffff", 
                             activebackground="#2b2b2b", activeforeground="#11c176", bd=0)
        btn_back.pack(anchor="w", pady=(0, 15))
        
        tk.Label(side_inner, text="Print Studio", font=("Arial", 26, "bold"), bg="#2b2b2b", fg="#ffffff").pack(anchor="w", pady=(0, 25))

        # Walk up to root app to check user role
        root_app = self.master
        while getattr(root_app, "master", None) is not None:
            root_app = root_app.master
        is_admin = getattr(root_app, "current_role", "Admin") == "Admin"
        restrict_editor_print = (not is_admin) and bool(self.settings.get("from_editor", False))

        p_row = tk.Frame(side_inner, bg="#2b2b2b")

        # Hero Accent Action Button (Triggers instant browser preview)
        btn_print = tk.Button(p_row, text="🖨\nPrint", font=("Arial", 12, "bold"), bg="#11c176", fg="#ffffff", 
                              width=8, height=3, cursor="hand2", relief="flat", bd=0,
                              activebackground="#0ea966", activeforeground="#ffffff")
        btn_print.pack(side="left")
        btn_print.config(command=lambda: perform_print(self))
        
        # Hover transformations for Print Button
        btn_print.bind("<Enter>", lambda e: btn_print.config(bg="#15d483"))
        btn_print.bind("<Leave>", lambda e: btn_print.config(bg="#11c176"))
        
        # Symmetrical Layout Container for Copies
        copies_frame = tk.Frame(p_row, bg="#2b2b2b")
        copies_frame.pack(side="left", fill="both", expand=True, padx=(18, 0))
        
        tk.Label(copies_frame, text="Copies:", bg="#2b2b2b", fg="#aaaaaa", font=("Arial", 10, "bold")).pack(anchor="w", pady=(2, 2))
        self.sp_copies = tk.Spinbox(copies_frame, from_=1, to=100, width=6, font=("Arial", 11, "bold"), 
                                    bg="#3d3d3d", fg="#ffffff", bd=0, buttonbackground="#4a4a4a", 
                                    justify="center", relief="flat")
        self.sp_copies.pack(anchor="w", ipady=3)

        # --- THE NEW WHATSAPP BUTTON ---
        btn_wa = tk.Button(side_inner, text="📲 Send to WhatsApp", font=("Arial", 11, "bold"), bg="#25D366", fg="#ffffff", cursor="hand2", relief="flat", bd=0, activebackground="#1da851", activeforeground="#ffffff", pady=8)
        btn_wa.config(command=lambda: send_to_whatsapp(self))

        if restrict_editor_print:
            lock_f = tk.Frame(side_inner, bg="#3d3d3d", padx=12, pady=10, highlightbackground="#ef4444", highlightthickness=1)
            lock_f.pack(fill="x", pady=(0, 20))
            tk.Label(
                lock_f, text="🔒 Preview Only Mode\nSave invoice first to Print or Share",
                font=("Arial", 9, "bold"), bg="#3d3d3d", fg="#f8fafc", justify="left"
            ).pack(anchor="w")
        else:
            p_row.pack(fill="x", pady=(0, 20))
            btn_wa.pack(fill="x", pady=(0, 20))

        # Symmetrical Layout Container for Pages Matrix
        tk.Label(side_inner, text="Pages to Print", bg="#2b2b2b", fg="#aaaaaa", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 5))
        pg_row = tk.Frame(side_inner, bg="#2b2b2b")
        pg_row.pack(fill="x", pady=(0, 25))
        
        self.e_from = tk.Entry(pg_row, width=5, font=("Arial", 11, "bold"), justify="center", bg="#3d3d3d", fg="#ffffff", relief="flat", bd=0, insertbackground="white")
        self.e_from.pack(side="left", ipady=4)
        self.e_from.insert(0, "1")
        
        tk.Label(pg_row, text="to", bg="#2b2b2b", fg="#ffffff", font=("Arial", 11, "italic")).pack(side="left", padx=10)
        
        self.e_to = tk.Entry(pg_row, width=5, font=("Arial", 11, "bold"), justify="center", bg="#3d3d3d", fg="#ffffff", relief="flat", bd=0, insertbackground="white")
        self.e_to.pack(side="left", ipady=4)
        self.e_to.insert(0, "1")

        # Destination Selection Combobox Setup
        tk.Label(side_inner, text="Print Destination", font=("Arial", 10, "bold"), bg="#2b2b2b", fg="#aaaaaa").pack(anchor="w", pady=(0, 5))
        self.cb_printer = ttk.Combobox(side_inner, values=["Web Browser (HTML Auto-Print)"], state="readonly", style="StudioDark.TCombobox")
        self.cb_printer.current(0)
        self.cb_printer.pack(fill="x", pady=(0, 25))

        # Size Engine Setup
        tk.Label(side_inner, text="Paper Configuration", font=("Arial", 10, "bold"), bg="#2b2b2b", fg="#aaaaaa").pack(anchor="w", pady=(0, 5))
        page_sizes_list = list(self.sizes.keys())
        self.cb_s3 = ttk.Combobox(side_inner, values=page_sizes_list, state="readonly", style="StudioDark.TCombobox")
        saved_sz = self.settings.get("page_size", "A4 (210*297mm)")
        if saved_sz in page_sizes_list: self.cb_s3.set(saved_sz)
        else: self.cb_s3.set("A4 (210*297mm)")
        self.cb_s3.pack(fill="x")
        self.cb_s3.bind("<<ComboboxSelected>>", self.update_canvas_size)

    def setup_preview(self):
        self.preview_container = tk.Frame(self, bg="#525659")
        self.preview_container.pack(side="right", fill="both", expand=True)

        zoom_bar = tk.Frame(self.preview_container, bg="#333333", height=40)
        zoom_bar.pack(side="bottom", fill="x")

        page_ctrl = tk.Frame(zoom_bar, bg="#333333")
        page_ctrl.pack(side="left", padx=20, pady=5)
        
        tk.Button(page_ctrl, text=" ◀ ", font=("Arial", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: self.change_page(-1)).pack(side="left", padx=5)
        self.ent_page = tk.Entry(page_ctrl, textvariable=self.current_page_var, font=("Arial", 10, "bold"), width=4, justify="center", bg="#4a4a4a", fg="white", relief="flat", bd=0, insertbackground="white")
        self.ent_page.pack(side="left", ipady=3)
        self.ent_page.bind("<Return>", self.scroll_to_current_page)
        
        self.lbl_total = tk.Label(page_ctrl, text="of 1", font=("Arial", 10, "bold"), bg="#333333", fg="#aaaaaa")
        self.lbl_total.pack(side="left", padx=8)
        tk.Button(page_ctrl, text=" ▶ ", font=("Arial", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: self.change_page(1)).pack(side="left", padx=5)
        
        z_ctrl = tk.Frame(zoom_bar, bg="#333333")
        z_ctrl.pack(side="right", padx=20, pady=5)
        
        tk.Button(z_ctrl, text="  -  ", font=("Arial", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: self.set_zoom(-25)).pack(side="left", padx=5)
        self.lbl_z = tk.Label(z_ctrl, text="100%", font=("Arial", 10, "bold"), bg="#333333", fg="white", width=6)
        self.lbl_z.pack(side="left")
        tk.Button(z_ctrl, text="  +  ", font=("Arial", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: self.set_zoom(25)).pack(side="left", padx=5)

        self.canvas = tk.Canvas(self.preview_container, bg="#525659", highlightthickness=0)
        
        # Apply structured layout variables to custom scroll bars
        self.scrollbar_y = ttk.Scrollbar(self.preview_container, orient="vertical", command=self.canvas.yview)
        self.scrollbar_x = ttk.Scrollbar(self.preview_container, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        self.scrollbar_y.pack(side="right", fill="y")
        self.scrollbar_x.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Advanced scroll tracking so it doesn't break when you return from child windows
        def _on_mousewheel(event):
            try:
                widget = self.winfo_containing(event.x_root, event.y_root)
                if not widget or not str(widget).startswith(str(self)): return
                if isinstance(widget, (tk.Listbox, ttk.Combobox, tk.Entry, tk.Spinbox)): return
                if event.delta: self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except: pass
            
        def _restore_scroll(e=None):
            self.bind_all("<MouseWheel>", _on_mousewheel)
            
        self.bind("<Enter>", _restore_scroll)
        self.bind("<FocusIn>", _restore_scroll)
        self.bind("<Destroy>", lambda e: self.unbind_all("<MouseWheel>") if e.widget == self else None)

    def set_zoom(self, val):
        z = self.zoom_var.get() + val
        if 25 <= z <= 300:
            self.zoom_var.set(z)
            self.lbl_z.config(text=f"{z}%")
            self.update_canvas_size()

    def change_page(self, delta):
        try: p = int(self.current_page_var.get())
        except: p = 1
        new_p = p + delta
        if 1 <= new_p <= self.total_pages:
            self.current_page_var.set(str(new_p))
            self.scroll_to_current_page()

    def scroll_to_current_page(self, *args):
        try:
            p = int(self.current_page_var.get())
            if 1 <= p <= self.total_pages and self.page_wrappers:
                y_target = self.page_wrappers[p-1] - 40 
                scrollregion = self.canvas.cget("scrollregion")
                if scrollregion:
                    scroll_h = float(scrollregion.split()[3])
                    self.canvas.yview_moveto(y_target / scroll_h)
        except: pass

    def update_canvas_size(self, *args):
        self.update_idletasks()  # Forces the OS to physically render all graphics and fonts before doing the math!
        draw_pages(self)