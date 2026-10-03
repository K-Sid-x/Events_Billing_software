import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, filedialog
import sqlite3
import json
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

import database
from views.home_parts.ui_components import get_theme

try:
    from settings_parts.interactive_cropper import InteractiveCropper
except ImportError:
    pass

from views.purchase_parts.ui_components.purch_part1_header import build_part_1
from views.purchase_parts.ui_components.purch_part2_details import build_part_2
from views.purchase_parts.ui_components.purch_part3_table import build_part_3
from views.purchase_parts.ui_components.purch_part4_footer import build_part_4
from views.purchase_parts.print_studio.purch_preview_renderer import render_purch_preview

def patch_company_db():
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("ALTER TABLE company ADD COLUMN purchase_template_json TEXT")
        conn.commit(); conn.close()
    except: pass

PURCH_FONTS = {
    "name": 22, "sec": 12, "addr": 10, "contact": 10, "gst": 10, "doc_title": 16,
    "vend_title": 10, "vend_name": 12, "vend_addr": 10, "vend_gst": 10,
    "buyer_title": 10, "buyer_name": 12, "buyer_addr": 10, "buyer_gst": 10,
    "meta_title": 10, "vno_l": 10, "vno_v": 11, "vdt_l": 10, "vdt_v": 11,
    "sbl_l": 10, "sbl_v": 11, "sdt_l": 10, "sdt_v": 11, "ewy_l": 10, "ewy_v": 11,
    "th_slno": 10, "th_part": 10, "th_hsn": 10, "th_qty": 10, "th_gst": 10, "th_rate_inc": 10, "th_rate": 10, "th_amt": 10,
    "tr_slno": 11, "tr_part": 11, "tr_hsn": 11, "tr_qty": 11, "tr_gst": 11, "tr_rate_inc": 11, "tr_rate": 11, "tr_amt": 11,
    "tax_title": 10, "tax_lbl": 10, "tax_val": 10, "tax_sum_tot_lbl": 10, "tax_sum_tot_val": 10,
    "amt_w_l": 10, "amt_w_v": 10, 
    "subtotal_lbl": 11, "subtotal_val": 11, "tax_totals_lbl": 11, "tax_totals_val": 11, 
    "round_off_lbl": 11, "round_off_val": 11,
    "g_total_lbl": 12, "g_total_val": 12, 
    "signature": 11, "page_num": 8
}

PURCH_BOLDS = [
    "name", "doc_title", "vend_title", "vend_name", "buyer_title", "buyer_name", 
    "meta_title", "vno_l", "vdt_l", "sbl_l", "sdt_l", "ewy_l", 
    "th_slno", "th_part", "th_hsn", "th_qty", "th_gst", "th_rate_inc", "th_rate", "th_amt", 
    "tax_title", "tax_sum_tot_lbl", "tax_sum_tot_val", "amt_w_l", "subtotal_lbl", "subtotal_val", "tax_totals_lbl", "tax_totals_val", "round_off_lbl", "round_off_val", "g_total_lbl", "g_total_val", "signature"
]

class PurchaseSettingsWindow(tk.Toplevel):
    def __init__(self, parent, comp_id):
        super().__init__(parent)
        patch_company_db()
        self.comp_id = comp_id
        
        self.title("Purchase Voucher Customization")
        try: self.state('zoomed')
        except tk.TclError: self.attributes('-zoomed', True)
        self.grab_set()
        
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        t = get_theme()
        
        self.BG_COLOR = t["bg"]
        self.CARD_BG = t["card"]
        self.BORDER_COLOR = t["border"]
        self.TEXT_PRIMARY = t["text"]
        self.TEXT_SECONDARY = t["sec"]
        self.ACCENT_GREEN = t["accent_green"]
        self.ACCENT_BLUE = t["accent_blue"]

        self.configure(bg=self.BG_COLOR)
        
        self.undo_stack = []
        self.redo_stack = []
        self.is_undoing = False
        
        self.fetch_active_company_data()
        self.setup_variables()
        self.build_ui()
        self.load_from_db()
        
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.after(100, self.schedule_preview)

    def _on_mousewheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if not widget: return
            if str(widget).startswith(str(self.left_canvas)):
                if event.delta < 0: self.left_canvas.yview_scroll(1, "units")
                elif event.delta > 0: self.left_canvas.yview_scroll(-1, "units")
            elif str(widget).startswith(str(self.cvs)):
                if event.delta < 0: self.cvs.yview_scroll(1, "units")
                elif event.delta > 0: self.cvs.yview_scroll(-1, "units")
        except: pass

    def fetch_active_company_data(self):
        self.comp_name = "YOUR COMPANY NAME"
        self.comp_sec = ""
        self.comp_address = "123 Business Road, Corporate City"
        self.comp_phone = ""
        self.comp_phone2 = ""
        self.comp_phone3 = ""
        self.comp_email = ""
        self.comp_gstin = ""
        self.comp_logo = ""
        
        self.currency_format = "Indian"
        self.currency_sym = "₹"
        self.date_format = "DD.MM.YYYY"
        
        try:
            comp_row = database.get_company(self.comp_id)
            if comp_row:
                self.comp_name = str(comp_row[1]) if comp_row[1] else self.comp_name
                self.comp_sec = str(comp_row[2]) if comp_row[2] else ""
                self.comp_address = str(comp_row[3]) if comp_row[3] else self.comp_address
                self.comp_phone = str(comp_row[4]) if comp_row[4] else ""
                self.comp_phone2 = str(comp_row[5]) if comp_row[5] else ""
                self.comp_phone3 = str(comp_row[6]) if comp_row[6] else ""
                self.comp_email = str(comp_row[7]) if comp_row[7] else ""
                self.comp_gstin = str(comp_row[9]) if comp_row[9] else ""
                self.comp_logo = str(comp_row[10]) if comp_row[10] else ""
                
                if len(comp_row) > 14 and comp_row[14]:
                    try:
                        m_data = json.loads(comp_row[14])
                        self.date_format = m_data.get("date_format", "DD.MM.YYYY")
                        raw_curr = m_data.get("currency_format", "Indian Rupees (₹)")
                        if "Dollar" in raw_curr:
                            self.currency_format = "International"; self.currency_sym = "$"
                        elif "Euro" in raw_curr:
                            self.currency_format = "International"; self.currency_sym = "€"
                        elif "Pound" in raw_curr:
                            self.currency_format = "International"; self.currency_sym = "£"
                        elif "Generic" in raw_curr:
                            self.currency_format = "International"; self.currency_sym = ""
                        else:
                            self.currency_format = "Indian"; self.currency_sym = "₹"
                    except: pass
        except: pass

    def setup_variables(self):
        self.name_var = tk.StringVar(value=self.comp_name)
        self.sec_var = tk.StringVar(value=self.comp_sec)
        self.addr_var = tk.StringVar(value=self.comp_address)
        self.p1_var = tk.StringVar(value=self.comp_phone)
        self.p2_var = tk.StringVar(value=self.comp_phone2)
        self.p3_var = tk.StringVar(value=self.comp_phone3)
        self.email_var = tk.StringVar(value=self.comp_email)
        self.gst_var = tk.StringVar(value=self.comp_gstin)

        self.layout_var = tk.StringVar(value="Split Header (Left-Center-Right)")
        self.header_spacing_var = tk.StringVar(value="20")
        self.swap_title_order_var = tk.IntVar(value=0)
        self.logo_path_var = tk.StringVar(value=self.comp_logo)
        self.logo_size_var = tk.StringVar(value="120")
        self.logo_shape_var = tk.StringVar(value="Original")
        self.paper_size_var = tk.StringVar(value="A4 (210*297mm)")

        self.doc_title_var = tk.StringVar(value="PURCHASE VOUCHER")
        self.font_family = tk.StringVar(value="Arial")
        
        self.prev_split_var = tk.IntVar(value=0)
        self.prev_split_var.trace_add("write", lambda *args: self.schedule_preview())
        
        self.w_slno = tk.IntVar(value=5); self.w_hsn = tk.IntVar(value=10); self.w_qty = tk.IntVar(value=8)
        self.w_gst = tk.IntVar(value=6); self.w_rate_inc = tk.IntVar(value=12); self.w_rate = tk.IntVar(value=12)
        self.w_amt = tk.IntVar(value=15)
        
        for w in [self.w_slno, self.w_hsn, self.w_qty, self.w_gst, self.w_rate_inc, self.w_rate, self.w_amt]:
            w.trace_add("write", lambda *args: self.schedule_preview())
            
        self.fonts = {k: tk.StringVar(value=str(v)) for k, v in PURCH_FONTS.items()}
        self.colors = {k: tk.StringVar(value="#000000") for k in PURCH_FONTS.keys()}
        self.bolds = {k: tk.BooleanVar(value=(k in PURCH_BOLDS)) for k in PURCH_FONTS.keys()}
        self.underlines = {k: tk.BooleanVar(value=False) for k in PURCH_FONTS.keys()}
        
        self.master_row_scale_var = tk.IntVar(value=0)
        self.master_row_scale_last = 0

        def on_master_scale_change(*args):
            try:
                val = self.master_row_scale_var.get()
                delta = val - self.master_row_scale_last
                if delta == 0: return

                keys = ["tr_slno", "tr_part", "tr_hsn", "tr_qty", "tr_gst", "tr_rate_inc", "tr_rate", "tr_amt"]
                for k in keys:
                    try:
                        curr = int(float(self.fonts[k].get()))
                        new_val = max(6, min(40, curr + delta))
                        self.fonts[k].set(str(new_val))
                    except: pass
                
                self.master_row_scale_last = val
            except: pass

        self.master_row_scale_var.trace_add("write", on_master_scale_change)
        
        self.colors["primary_color"] = tk.StringVar(value="#0f172a")
        self.colors["secondary_color"] = tk.StringVar(value="#475569")
        self.colors["accent_color"] = tk.StringVar(value="#10b981")
        self.colors["tab_head_bg"] = tk.StringVar(value="#475569")
        self.colors["meta_head_bg"] = tk.StringVar(value="#ffffff")
        
        # --- THE FIX: Added independent background colors for Tax Box & Tax Headers ---
        self.colors["tax_title_bg"] = tk.StringVar(value="#ffffff")
        self.colors["tax_head_bg"] = tk.StringVar(value="#e2e8f0")
        
        self.color_btns = {}
        
        all_vars = [self.name_var, self.sec_var, self.addr_var, self.p1_var, self.p2_var, self.p3_var, self.email_var, self.gst_var, self.doc_title_var, self.font_family, self.swap_title_order_var, self.logo_size_var, self.logo_shape_var, self.layout_var, self.header_spacing_var] + list(self.fonts.values()) + list(self.colors.values()) + list(self.bolds.values()) + list(self.underlines.values())
        for v in all_vars: v.trace_add("write", lambda *args: self.schedule_preview())
        
        self.preview_timer = None
        self.undo_timer = None

    def push_undo_state(self):
        if self.is_undoing: return
        state = {
            "fonts": {k: v.get() for k,v in self.fonts.items()},
            "colors": {k: v.get() for k,v in self.colors.items()},
            "bolds": {k: v.get() for k,v in self.bolds.items()},
            "underlines": {k: v.get() for k,v in self.underlines.items()}
        }
        if not self.undo_stack or self.undo_stack[-1] != state:
            self.undo_stack.append(state)
            self.redo_stack.clear()
            self.update_undo_ui()
            
    def undo_action(self):
        if len(self.undo_stack) > 1:
            self.is_undoing = True
            curr_state = self.undo_stack.pop()
            self.redo_stack.append(curr_state)
            self.apply_state(self.undo_stack[-1])
            self.is_undoing = False
            self.update_undo_ui()
            self.schedule_preview()
            
    def redo_action(self):
        if self.redo_stack:
            self.is_undoing = True
            next_state = self.redo_stack.pop()
            self.undo_stack.append(next_state)
            self.apply_state(next_state)
            self.is_undoing = False
            self.update_undo_ui()
            self.schedule_preview()
            
    def apply_state(self, state):
        for k, v in state["fonts"].items(): self.fonts[k].set(v)
        for k, v in state["colors"].items(): 
            self.colors[k].set(v)
            if k in self.color_btns: self.color_btns[k].config(bg=v)
        for k, v in state["bolds"].items(): self.bolds[k].set(v)
        for k, v in state["underlines"].items(): self.underlines[k].set(v)
        
    def update_undo_ui(self):
        if hasattr(self, 'btn_undo'):
            self.btn_undo.config(state="normal" if len(self.undo_stack) > 1 else "disabled", fg=self.ACCENT_BLUE if len(self.undo_stack) > 1 else self.TEXT_SECONDARY)
            self.btn_redo.config(state="normal" if self.redo_stack else "disabled", fg=self.ACCENT_GREEN if self.redo_stack else self.TEXT_SECONDARY)

    def schedule_preview(self):
        if not getattr(self, 'is_undoing', False):
            if hasattr(self, 'undo_timer') and self.undo_timer: self.after_cancel(self.undo_timer)
            self.undo_timer = self.after(500, self.push_undo_state)
            
        if self.preview_timer: self.after_cancel(self.preview_timer)
        self.preview_timer = self.after(150, self.render_preview)

    def reset_fonts_colors(self, cat):
        keys = []
        if cat == 1: keys = ["name", "sec", "addr", "contact", "gst", "doc_title"]
        elif cat == "vendor": keys = ["vend_title", "vend_name", "vend_addr", "vend_gst"]
        elif cat == "buyer": keys = ["buyer_title", "buyer_name", "buyer_addr", "buyer_gst"]
        elif cat == "meta": 
            keys = ["meta_title", "vno_l", "vno_v", "vdt_l", "vdt_v", "sbl_l", "sbl_v", "sdt_l", "sdt_v", "ewy_l", "ewy_v"]
            self.colors["meta_head_bg"].set("#ffffff")
            if "meta_head_bg" in self.color_btns: self.color_btns["meta_head_bg"].config(bg="#ffffff")
        elif cat == 3:
            keys = ["th_slno", "th_part", "th_hsn", "th_qty", "th_gst", "th_rate_inc", "th_rate", "th_amt"]
            self.colors["tab_head_bg"].set("#475569")
            if "tab_head_bg" in self.color_btns: self.color_btns["tab_head_bg"].config(bg="#475569")
        elif cat == 4: 
            keys = ["tr_slno", "tr_part", "tr_hsn", "tr_qty", "tr_gst", "tr_rate_inc", "tr_rate", "tr_amt"]
            self.master_row_scale_last = 0
            if hasattr(self, 'master_row_scale_var'): self.master_row_scale_var.set(0)
        elif cat == "tax": 
            keys = ["tax_title", "tax_lbl", "tax_val", "tax_sum_tot_lbl", "tax_sum_tot_val"]
            self.colors["tax_head_bg"].set("#e2e8f0")
            if "tax_head_bg" in self.color_btns: self.color_btns["tax_head_bg"].config(bg="#e2e8f0")
            self.colors["tax_title_bg"].set("#ffffff")
            if "tax_title_bg" in self.color_btns: self.color_btns["tax_title_bg"].config(bg="#ffffff")
        elif cat == 5: 
            keys = ["amt_w_l", "amt_w_v", "subtotal_lbl", "subtotal_val", "tax_totals_lbl", "tax_totals_val", "round_off_lbl", "round_off_val", "g_total_lbl", "g_total_val", "signature", "page_num"]

        self.push_undo_state()
        for k in keys:
            if k in self.fonts: self.fonts[k].set("11")
            if k in self.colors: self.colors[k].set("#000000")
            if k in self.color_btns: self.color_btns[k].config(bg="#000000")
            if k in self.bolds: self.bolds[k].set(False)
            if k in self.underlines: self.underlines[k].set(False)
            
        self.schedule_preview()

    def _create_full_font_row(self, parent, label, key, row):
        tk.Label(parent, text=label, font=("Arial", 9), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, width=19, anchor="w").grid(row=row, column=0, sticky="w", pady=(15, 0))
        tk.Scale(parent, from_=6, to=40, orient="horizontal", variable=self.fonts[key], bg=self.CARD_BG, fg=self.TEXT_PRIMARY, bd=0, highlightthickness=0, length=80, sliderlength=15).grid(row=row, column=1, padx=(5,5))
        btn_c = tk.Button(parent, width=2, bg=self.colors[key].get(), relief="solid", bd=1, highlightbackground=self.BORDER_COLOR, cursor="hand2")
        btn_c.config(command=lambda k=key, b=btn_c: self.pick_color(k, b))
        btn_c.grid(row=row, column=2, padx=2, pady=(15, 0))
        tk.Checkbutton(parent, text="B", variable=self.bolds[key], font=("Arial", 9, "bold"), indicatoron=False, width=2, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, selectcolor=self.ACCENT_BLUE, cursor="hand2").grid(row=row, column=3, padx=2, pady=(15, 0))
        tk.Checkbutton(parent, text="U", variable=self.underlines[key], font=("Arial", 9, "underline"), indicatoron=False, width=2, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, selectcolor=self.ACCENT_BLUE, cursor="hand2").grid(row=row, column=4, padx=2, pady=(15, 0))
        self.color_btns[key] = btn_c

    def pick_color(self, key, btn):
        current_color = self.colors[key].get() if key in self.colors else "#ffffff"
        color = colorchooser.askcolor(color=current_color, parent=self, title="Choose Color")[1]
        if color:
            self.colors[key].set(color)
            btn.config(bg=color)

    def browse_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path:
            try:
                InteractiveCropper(self, path, self.on_logo_cropped)
            except NameError:
                self.logo_path_var.set(path)
                self.schedule_preview()

    def on_logo_cropped(self, final_path):
        self.logo_path_var.set(final_path)
        self.schedule_preview() 

    def build_ui(self):
        top_f = tk.Frame(self, bg=self.CARD_BG, pady=10, padx=20, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        top_f.pack(fill="x", pady=(0, 10))
        
        tk.Label(top_f, text="⚙️ Purchase Settings", font=("Arial", 16, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(0, 30))
        
        self.btn_p1 = tk.Button(top_f, text="Part 1: Header", font=("Arial", 10, "bold"), bg=self.ACCENT_BLUE, fg="white", relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(1))
        self.btn_p2 = tk.Button(top_f, text="Part 2: Details", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(2))
        self.btn_p3 = tk.Button(top_f, text="Part 3: Table", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(3))
        self.btn_p4 = tk.Button(top_f, text="Part 4: Footer", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(4))
        
        self.btn_p1.pack(side="left", padx=5); self.btn_p2.pack(side="left", padx=5)
        self.btn_p3.pack(side="left", padx=5); self.btn_p4.pack(side="left", padx=5)
        
        tk.Button(top_f, text="💾 Save Configuration", font=("Arial", 10, "bold"), bg=self.ACCENT_GREEN, fg="#ffffff", relief="flat", cursor="hand2", padx=15, command=self.save_to_db).pack(side="right")

        self.btn_redo = tk.Button(top_f, text="↻ Redo", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY, relief="solid", bd=1, highlightbackground=self.BORDER_COLOR, cursor="hand2", padx=10, state="disabled", command=self.redo_action)
        self.btn_redo.pack(side="right", padx=(0, 10))
        
        self.btn_undo = tk.Button(top_f, text="↺ Undo", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY, relief="solid", bd=1, highlightbackground=self.BORDER_COLOR, cursor="hand2", padx=10, state="disabled", command=self.undo_action)
        self.btn_undo.pack(side="right", padx=(0, 5))

        split = tk.PanedWindow(self, orient="horizontal", sashwidth=5, bg=self.BORDER_COLOR)
        split.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        left_container = tk.Frame(split, bg=self.CARD_BG, width=480)
        split.add(left_container, minsize=480)

        self.left_canvas = tk.Canvas(left_container, bg=self.CARD_BG, highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_panel = tk.Frame(self.left_canvas, bg=self.CARD_BG)

        self.left_panel.bind("<Configure>", lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.create_window((0, 0), window=self.left_panel, anchor="nw")
        self.left_canvas.configure(yscrollcommand=left_scroll.set)

        self.left_canvas.pack(side="left", fill="both", expand=True)
        left_scroll.pack(side="right", fill="y")
        
        right_container = tk.Frame(split, bg=self.BG_COLOR)
        split.add(right_container, minsize=500)
        
        prev_ctrl = tk.Frame(right_container, bg=self.BG_COLOR)
        prev_ctrl.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(prev_ctrl, text="Live Preview Data:", font=("Arial", 9, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(side="left")
        chk_split = tk.Checkbutton(prev_ctrl, text="Multi-Page (Split)", variable=self.prev_split_var, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, selectcolor=self.CARD_BG, activebackground=self.BG_COLOR, activeforeground=self.TEXT_PRIMARY, font=("Arial", 9, "bold"), cursor="hand2")
        chk_split.pack(side="left", padx=(10, 5))
        
        cvs_wrapper = tk.Frame(right_container, bg=self.BG_COLOR)
        cvs_wrapper.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.cvs = tk.Canvas(cvs_wrapper, bg=self.BG_COLOR, highlightthickness=0)
        cvs_scroll = ttk.Scrollbar(cvs_wrapper, orient="vertical", command=self.cvs.yview)
        self.cvs.configure(yscrollcommand=cvs_scroll.set)
        
        cvs_scroll.pack(side="right", fill="y", padx=(10, 0))
        self.cvs.pack(side="left", fill="both", expand=True)
        
        self.cvs.bind("<Configure>", lambda e: self.schedule_preview())

        self.f_p1 = tk.Frame(self.left_panel, bg=self.CARD_BG, padx=15, pady=15)
        self.f_p2 = tk.Frame(self.left_panel, bg=self.CARD_BG, padx=15, pady=15)
        self.f_p3 = tk.Frame(self.left_panel, bg=self.CARD_BG, padx=15, pady=15)
        self.f_p4 = tk.Frame(self.left_panel, bg=self.CARD_BG, padx=15, pady=15)

        build_part_1(self.f_p1, self)
        build_part_2(self.f_p2, self)
        build_part_3(self.f_p3, self)
        build_part_4(self.f_p4, self)

        self.show_part(1)

    def show_part(self, p):
        for btn in [self.btn_p1, self.btn_p2, self.btn_p3, self.btn_p4]: btn.config(bg=self.BG_COLOR, fg=self.TEXT_PRIMARY)
        for f in [self.f_p1, self.f_p2, self.f_p3, self.f_p4]: f.pack_forget()
            
        if p == 1: self.btn_p1.config(bg=self.ACCENT_BLUE, fg="white"); self.f_p1.pack(fill="both", expand=True)
        elif p == 2: self.btn_p2.config(bg=self.ACCENT_BLUE, fg="white"); self.f_p2.pack(fill="both", expand=True)
        elif p == 3: self.btn_p3.config(bg=self.ACCENT_BLUE, fg="white"); self.f_p3.pack(fill="both", expand=True)
        elif p == 4: self.btn_p4.config(bg=self.ACCENT_BLUE, fg="white"); self.f_p4.pack(fill="both", expand=True)
        
        self.update_idletasks()
        self.left_canvas.yview_moveto(0)
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def load_from_db(self):
        try:
            conn = database.get_connection()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT purchase_template_json FROM company WHERE id=?", (self.comp_id,))
            row = c.fetchone()
            conn.close()
            
            if row and row["purchase_template_json"]:
                data = json.loads(row["purchase_template_json"])
                
                # --- THE FIX: Let the UI inherit fresh data from the main company profile ---
                # We completely removed the lines that were loading stale comp_name, comp_p1, etc.
                
                self.doc_title_var.set(data.get("doc_title", "PURCHASE VOUCHER"))
                self.logo_path_var.set(data.get("logo_path", ""))
                self.logo_shape_var.set(data.get("logo_shape", "Original"))
                self.logo_size_var.set(data.get("logo_size", "120"))
                self.swap_title_order_var.set(data.get("swap_title_order", 0))
                self.layout_var.set(data.get("layout", "Split Header (Left-Center-Right)"))
                self.header_spacing_var.set(data.get("header_spacing", "20"))
                
                f_db = data.get("fonts", {}); c_db = data.get("colors", {}); b_db = data.get("bolds", {}); u_db = data.get("underlines", {})
                
                for k in self.fonts:
                    if k in f_db: self.fonts[k].set(str(f_db[k]))
                for k in self.colors:
                    if k in c_db: 
                        self.colors[k].set(c_db[k])
                        if k in self.color_btns: self.color_btns[k].config(bg=c_db[k])
                for k in self.bolds:
                    if k in b_db: self.bolds[k].set(b_db[k])
                for k in self.underlines:
                    if k in u_db: self.underlines[k].set(u_db[k])
                    
                w_db = data.get("col_widths", {})
                self.w_slno.set(w_db.get("w_slno", 5)); self.w_hsn.set(w_db.get("w_hsn", 10)); self.w_qty.set(w_db.get("w_qty", 8))
                self.w_gst.set(w_db.get("w_gst", 6)); self.w_rate_inc.set(w_db.get("w_rate_inc", 12)); self.w_rate.set(w_db.get("w_rate", 12))
                self.w_amt.set(w_db.get("w_amt", 15))
        except Exception as e: print(e)

    def save_to_db(self):
        data = {
            "comp_name": self.name_var.get(), "comp_sec": self.sec_var.get(), "comp_addr": self.addr_var.get(),
            "comp_p1": self.p1_var.get(), "comp_p2": self.p2_var.get(), "comp_p3": self.p3_var.get(),
            "comp_email": self.email_var.get(), "comp_gst": self.gst_var.get(),
            "doc_title": self.doc_title_var.get(),
            "logo_path": self.logo_path_var.get(), "logo_shape": self.logo_shape_var.get(), 
            "logo_size": self.logo_size_var.get(), "swap_title_order": self.swap_title_order_var.get(),
            "layout": self.layout_var.get(), "header_spacing": self.header_spacing_var.get(),
            "fonts": {k: int(float(v.get() or 10)) for k, v in self.fonts.items()},
            "colors": {k: v.get() for k, v in self.colors.items()},
            "bolds": {k: v.get() for k, v in self.bolds.items()},
            "underlines": {k: v.get() for k, v in self.underlines.items()},
            "col_widths": {
                "w_slno": self.w_slno.get(), "w_hsn": self.w_hsn.get(), "w_qty": self.w_qty.get(), 
                "w_gst": self.w_gst.get(), "w_rate_inc": self.w_rate_inc.get(), "w_rate": self.w_rate.get(), "w_amt": self.w_amt.get()
            }
        }
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            # --- THE FIX: Safely update ONLY the template JSON to prevent global profile corruption! ---
            c.execute("""
                UPDATE company 
                SET purchase_template_json=?
                WHERE id=?
            """, (json.dumps(data), self.comp_id))
                  
            conn.commit(); conn.close()
            messagebox.showinfo("Saved", "Purchase Voucher Settings Saved!", parent=self)
        except Exception as e: messagebox.showerror("Error", str(e), parent=self)

    def render_preview(self):
        render_purch_preview(self)