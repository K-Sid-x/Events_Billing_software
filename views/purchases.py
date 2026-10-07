import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import csv
import json
import tempfile
import webbrowser
from datetime import date, datetime, timedelta
from views.home_parts.ui_components import get_theme

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(current_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings, smart_date_formatter, on_tree_hover
from views.invoice_parts.calendar_widget import NativeCalendar

from views.purchase_parts.engines.purchase_forms import open_purchase_form
from views.purchase_parts.print_studio.purchase_settings import PurchaseSettingsWindow

try:
    from views.purchase_parts.print_studio.purchase_preview_window import open_purchase_preview
except ImportError:
    pass

try:
    from views.purchase_parts.payment_gateway.purchase_payment_portal import open_purchase_payment_portal
except ImportError:
    pass


class PurchasesView(tk.Frame):
    def __init__(self, parent):
        self.app = parent.winfo_toplevel()
        self.comp_id = getattr(self.app, "active_company_id", 1)
        
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
        self.active_tile_filter = "All" 
        
        comp = database.get_company(self.comp_id)
        self.has_gst = (comp and comp[8] == 1)

        self.is_bulk_mode = False
        self.bulk_action_type = None
        self.selected_bulk_ids = set()
        
        self.undo_stack = []
        self.redo_stack = []

        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        t = get_theme()
        
        self.colors = {
            "bg": t["bg"], "card": t["card"], "border": t["border"], 
            "text": t["text"], "text_sec": t["sec"], "accent_blue": t["accent_blue"], 
            "accent_green": t["accent_green"], "error": t["error"], "header": t["card"],
            "stripe_even": t["stripe_even"], "stripe_odd": t["stripe_odd"], "hover": t["card_hover"],
            "pending_even": "#3a1c1d" if self.is_dark else "#fef2f2",
            "pending_odd": "#472223" if self.is_dark else "#fecaca",
            "partial_even": "#422f00" if self.is_dark else "#fffbeb",
            "partial_odd": "#594000" if self.is_dark else "#fef3c7",
            "tile_hover": t["btn_hover"], "bulk_select": t["bulk_sel"]
        }

        super().__init__(parent, bg=self.colors["bg"])
        self.build_ui()

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default")
        
        # --- THE FIX: Thick Solid Scrollbar Styles to match Invoices! ---
        style.configure("Purch.Vertical.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.configure("Purch.Horizontal.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.map("Purch.Vertical.TScrollbar", background=[("active", self.colors["accent_blue"])])
        style.map("Purch.Horizontal.TScrollbar", background=[("active", self.colors["accent_blue"])])
        # ----------------------------------------------------------------
        
        style.configure("Purch.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.colors["header"], foreground=self.colors["text"], borderwidth=1, bordercolor=self.colors["border"])
        style.configure("Purch.Treeview", font=("Segoe UI", 11), rowheight=38, background=self.colors["card"], fieldbackground=self.colors["card"], foreground=self.colors["text"], borderwidth=0)
        # --- THE FIX: Map the selection color to your Accent Blue to match Invoices ---
        style.map("Purch.Treeview", background=[("selected", self.colors["accent_blue"])], foreground=[("selected", "#ffffff")])

        self.option_add('*TCombobox*Listbox.background', self.colors["card"])
        self.option_add('*TCombobox*Listbox.foreground', self.colors["text"])
        self.option_add('*TCombobox*Listbox.selectBackground', self.colors["accent_blue"])
        self.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
        
        style.configure('TCombobox', arrowcolor=self.colors["text"])
        style.map('TCombobox', 
                  fieldbackground=[('readonly', self.colors["bg"])],
                  selectbackground=[('readonly', self.colors["bg"])],
                  selectforeground=[('readonly', self.colors["text"])],
                  foreground=[('readonly', self.colors["text"])],
                  background=[('readonly', self.colors["bg"])],
                  arrowcolor=[('readonly', self.colors["text"])])

        # --- THE FIX: Removed extra 30px padding to stretch the tab exactly like Invoices ---
        main_container = tk.Frame(self, bg=self.colors["bg"])
        main_container.pack(fill="both", expand=True)

        header_f = tk.Frame(main_container, bg=self.colors["bg"])
        header_f.pack(fill="x", pady=(0, 15))
        
        title_f = tk.Frame(header_f, bg=self.colors["bg"])
        title_f.pack(side="left")
        # --- THE FIX: Removed the redundant 'Purchases' subtitle to perfectly match Invoices layout ---
        tk.Label(title_f, text="Purchase Bills & Expenses", font=("Segoe UI", 20, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(anchor="w")

        btn_f = tk.Frame(header_f, bg=self.colors["bg"])
        btn_f.pack(side="right", anchor="s")
        
        self.btn_undo = tk.Button(btn_f, text="↺ Undo", font=("Segoe UI", 10, "bold"), relief="solid", bd=1, highlightbackground=self.colors["border"], padx=15, pady=6)
        self.btn_undo.config(command=self.perform_undo)
        self.btn_undo.pack(side="left", padx=(0, 10))

        self.btn_redo = tk.Button(btn_f, text="↻ Redo", font=("Segoe UI", 10, "bold"), relief="solid", bd=1, highlightbackground=self.colors["border"], padx=15, pady=6)
        self.btn_redo.config(command=self.perform_redo)
        self.btn_redo.pack(side="left", padx=(0, 10))
        
        btn_settings = tk.Button(btn_f, text="⚙ Purchase Settings", font=("Segoe UI", 10, "bold"), bg=self.colors["header"], fg=self.colors["text"], relief="solid", bd=1, highlightbackground=self.colors["border"], padx=15, pady=6)
        btn_settings.config(command=lambda: PurchaseSettingsWindow(self.app, self.comp_id))
        btn_settings.pack(side="left", padx=(0, 10))
        
        tk.Button(btn_f, text="⊕ New Purchase", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", padx=15, pady=6, cursor="hand2", command=lambda: open_purchase_form(self, self.comp_id, self.curr_fmt, self.date_fmt_code, self.load_data)).pack(side="left")

        self.update_memory_buttons()

        tiles_f = tk.Frame(main_container, bg=self.colors["bg"])
        tiles_f.pack(fill="x", pady=(0, 20))
        
        self.tile_frames = {}

        def make_clickable_tile(parent, title, color, filter_key):
            f = tk.Frame(parent, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, padx=15, pady=15, cursor="hand2" if filter_key else "")
            f.pack(side="left", fill="x", expand=True, padx=(0, 15) if title != "DELETED BILLS" else 0)
            
            lbl_title = tk.Label(f, text=title, font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"])
            lbl_title.pack(anchor="center")
            lbl_val = tk.Label(f, text="0", font=("Segoe UI", 20, "bold"), bg=self.colors["card"], fg=color)
            lbl_val.pack(anchor="center", pady=(5, 0))
            
            if filter_key:
                def on_enter(e): f.config(bg=self.colors["tile_hover"]); lbl_title.config(bg=self.colors["tile_hover"]); lbl_val.config(bg=self.colors["tile_hover"])
                def on_leave(e): f.config(bg=self.colors["card"]); lbl_title.config(bg=self.colors["card"]); lbl_val.config(bg=self.colors["card"])
                def on_click(e): 
                    if filter_key == "Deleted":
                        self.open_deleted_bills_window()
                        return  
                    if filter_key == "Drafts":
                        self.open_drafts_window()
                        return
                        
                    if filter_key == "Total":
                        self.active_tile_filter = "All"
                    else:
                        self.active_tile_filter = "All" if self.active_tile_filter == filter_key else filter_key
                    self.load_data()
                    
                f.bind("<Enter>", on_enter); lbl_title.bind("<Enter>", on_enter); lbl_val.bind("<Enter>", on_enter)
                f.bind("<Leave>", on_leave); lbl_title.bind("<Leave>", on_leave); lbl_val.bind("<Leave>", on_leave)
                f.bind("<Button-1>", on_click); lbl_title.bind("<Button-1>", on_click); lbl_val.bind("<Button-1>", on_click)
                self.tile_frames[filter_key] = f

            return lbl_val

        self.lbl_t_count = make_clickable_tile(tiles_f, "TOTAL BILLS", self.colors["text"], "Total")
        self.lbl_t_billed = make_clickable_tile(tiles_f, "BILLED", self.colors["accent_blue"], None) 
        self.lbl_t_paid = make_clickable_tile(tiles_f, "PAID BILLS", self.colors["accent_green"], "Paid")
        self.lbl_t_unpaid = make_clickable_tile(tiles_f, "UNPAID BILLS", self.colors["error"], "Unpaid")
        self.lbl_t_drafts = make_clickable_tile(tiles_f, "DRAFTS", "#94a3b8", "Drafts")
        self.lbl_t_deleted = make_clickable_tile(tiles_f, "DELETED BILLS", "#f59e0b", "Deleted")

        toolbar_container = tk.Frame(main_container, bg=self.colors["bg"])
        toolbar_container.pack(fill="x", pady=(0, 10))

        self.left_toolbar = tk.Frame(toolbar_container, bg=self.colors["bg"])
        self.left_toolbar.pack(side="left", fill="y")

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(self.left_toolbar, textvariable=self.search_var, font=("Segoe UI", 10), width=22, bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        search_entry.pack(side="left", ipady=3)
        search_entry.insert(0, "Search Vendor or Bill...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, "end") if search_entry.get() == "Search Vendor or Bill..." else None)
        search_entry.bind("<FocusOut>", lambda e: search_entry.insert(0, "Search Vendor or Bill...") if not search_entry.get() else None)
        self.search_var.trace_add("write", lambda *args: [setattr(self, 'current_page', 1), self.tree.yview_moveto(0), self.load_data()] if search_entry.get() != "Search Vendor or Bill..." else None)

        # --- THE FIX: Added 'X' Clear Button for Search (Styled to match Invoices exactly!) ---
        def force_clear_search():
            self.search_var.set("Search Vendor or Bill...")
            self.focus_set()
            self.current_page = 1
            self.load_data()

        btn_clear_search = tk.Button(self.left_toolbar, text="✖", font=("Arial", 10, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="solid", bd=1, cursor="hand2", command=force_clear_search)
        btn_clear_search.pack(side="left", padx=(5, 0), ipady=3, ipadx=8)
        
        def add_hover_effect(widget, default_bg, hover_bg):
            widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
            widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))
            
        add_hover_effect(btn_clear_search, self.colors["card"], self.colors["hover"])
        # ------------------------------------------------------------------------------------

        tk.Label(self.left_toolbar, text="Sort By:", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(side="left", padx=(15, 5))
        self.sort_var = tk.StringVar(value="Latest")
        sort_cb = ttk.Combobox(self.left_toolbar, textvariable=self.sort_var, values=["Latest", "Oldest"], state="readonly", width=8, font=("Segoe UI", 10))
        sort_cb.pack(side="left", ipady=2)
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        tk.Label(self.left_toolbar, text="Period:", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(side="left", padx=(15, 5))
        self.filter_var = tk.StringVar(value="All Time")
        # --- THE FIX: Removed 'Last Month' from the dropdown list ---
        filter_cb = ttk.Combobox(self.left_toolbar, textvariable=self.filter_var, values=["All Time", "This Month", "This Financial Year", "Custom Date Range"], state="readonly", width=18, font=("Segoe UI", 10))
        filter_cb.pack(side="left", ipady=2)
        filter_cb.bind("<<ComboboxSelected>>", self.on_filter_change)
        
        self.custom_date_f = tk.Frame(self.left_toolbar, bg=self.colors["bg"])
        
        self.from_var = tk.StringVar(value="")
        ent_from = tk.Entry(self.custom_date_f, textvariable=self.from_var, width=11, font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"])
        ent_from.pack(side="left", padx=(5, 0), ipady=3)
        btn_from = tk.Button(self.custom_date_f, text="📅", bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2")
        btn_from.config(command=lambda b=btn_from: NativeCalendar(self.app, self.from_var, anchor_widget=b))
        btn_from.pack(side="left")

        tk.Label(self.custom_date_f, text="-", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(side="left", padx=2)

        self.to_var = tk.StringVar(value="")
        ent_to = tk.Entry(self.custom_date_f, textvariable=self.to_var, width=11, font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"])
        ent_to.pack(side="left", ipady=3)
        btn_to = tk.Button(self.custom_date_f, text="📅", bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2")
        btn_to.config(command=lambda b=btn_to: NativeCalendar(self.app, self.to_var, anchor_widget=b))
        btn_to.pack(side="left")
        
        # --- THE FIX: Replaced 'Go' with '✖' Clear button and added auto-filtering ---
        def clear_custom_filter():
            self.filter_var.set("All Time")
            self.from_var.set("")
            self.to_var.set("")
            self.on_filter_change()

        tk.Button(self.custom_date_f, text="✖", font=("Arial", 9, "bold"), bg=self.colors.get("error", "#ef4444"), fg="#ffffff", relief="flat", cursor="hand2", command=clear_custom_filter).pack(side="left", padx=(10, 0))

        # Auto-trigger grid reload the instant dates change
        self.from_var.trace_add("write", lambda *args: self.load_data() if self.filter_var.get() == "Custom Date Range" else None)
        self.to_var.trace_add("write", lambda *args: self.load_data() if self.filter_var.get() == "Custom Date Range" else None)
        # ----------------------------------------------------------------------------

        self.right_toolbar = tk.Frame(toolbar_container, bg=self.colors["bg"])
        self.right_toolbar.pack(side="right", fill="y")
        
        self.normal_actions = tk.Frame(self.right_toolbar, bg=self.colors["bg"])
        self.bulk_actions = tk.Frame(self.right_toolbar, bg=self.colors["bg"], padx=10, pady=2)
        
        # --- THE FIX: Moved Recent Payments to the left of the Export buttons ---
        tk.Button(self.normal_actions, text="⎙ Export PDF", command=self.export_pdf, font=("Segoe UI", 9, "bold"), bg=self.colors["header"], fg=self.colors["text"], relief="solid", bd=1, highlightbackground=self.colors["border"], padx=10, pady=3, cursor="hand2").pack(side="right")
        tk.Button(self.normal_actions, text="📄 Export CSV", command=self.export_csv, font=("Segoe UI", 9, "bold"), bg=self.colors["header"], fg=self.colors["text"], relief="solid", bd=1, highlightbackground=self.colors["border"], padx=10, pady=3, cursor="hand2").pack(side="right", padx=(10, 10))
        tk.Button(self.normal_actions, text="💸 Recent Payments", command=self.show_recent_payments, font=("Segoe UI", 9, "bold"), bg=self.colors["header"], fg=self.colors["text"], relief="solid", bd=1, highlightbackground=self.colors["border"], padx=10, pady=3, cursor="hand2").pack(side="right", padx=(0, 0))
        
        self.normal_actions.pack(fill="both", expand=True)

        self.table_f = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        self.table_f.pack(fill="both", expand=True)
        
        scroll_y = ttk.Scrollbar(self.table_f, orient="vertical", style="Purch.Vertical.TScrollbar")
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Load company-specific column widths ---
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"purch_grid_cols_{self.comp_id}",))
            # ----------------------------------------------------
            res = c.fetchone()
            conn.close()
            w_dict = json.loads(res[0]) if res and res[0] else {}
        except:
            w_dict = {}
        
        if self.has_gst:
            tree_cols = ("sl", "date", "bill", "vendor", "subtotal", "gst", "total", "status", "action")
            cols = [
                ("sl", "SL. NO.", w_dict.get("sl", 60), "center", False), 
                ("date", "DATE", w_dict.get("date", 110), "center", False), 
                ("bill", "BILL NO.", w_dict.get("bill", 110), "center", False), 
                ("vendor", "VENDOR", w_dict.get("vendor", 200), "w", False), 
                ("subtotal", "SUBTOTAL", w_dict.get("subtotal", 130), "e", False), 
                ("gst", "GST", w_dict.get("gst", 110), "e", False), 
                ("total", "TOTAL", w_dict.get("total", 130), "e", False), 
                ("status", "STATUS", w_dict.get("status", 110), "center", False), 
                # --- THE FIX: Re-enable stretch=True ONLY for the Actions column to fill the gap ---
                ("action", "ACTIONS", w_dict.get("action", 150), "center", True)
            ]
        else:
            tree_cols = ("sl", "date", "bill", "vendor", "total", "status", "action")
            cols = [
                ("sl", "SL. NO.", w_dict.get("sl", 60), "center", False), 
                ("date", "DATE", w_dict.get("date", 110), "center", False), 
                ("bill", "BILL NO.", w_dict.get("bill", 110), "center", False), 
                ("vendor", "VENDOR", w_dict.get("vendor", 350), "w", False), 
                ("total", "TOTAL AMOUNT", w_dict.get("total", 140), "e", False), 
                ("status", "STATUS", w_dict.get("status", 120), "center", False), 
                # --- THE FIX: Re-enable stretch=True ONLY for the Actions column to fill the gap ---
                ("action", "ACTIONS", w_dict.get("action", 150), "center", True)
            ]
        
        # --- THE FIX: Added horizontal scrollbar and Shift+Scroll smooth scrolling ---
        scroll_x = ttk.Scrollbar(self.table_f, orient="horizontal", style="Purch.Horizontal.TScrollbar")
        self.tree = ttk.Treeview(self.table_f, columns=tree_cols, show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Purch.Treeview")
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)
        
        def _h_scroll(event):
            self.tree.xview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        self.tree.bind("<Shift-MouseWheel>", _h_scroll)
                
        for c, t, w, a, stretch in cols:
            self.tree.heading(c, text=t, anchor=a)
            self.tree.column(c, width=w, anchor=a, stretch=stretch)

        self.tree.tag_configure("stripe_even", background=self.colors["stripe_even"])
        self.tree.tag_configure("stripe_odd", background=self.colors["stripe_odd"])
        self.tree.tag_configure("pending_even", background=self.colors["pending_even"])
        self.tree.tag_configure("pending_odd", background=self.colors["pending_odd"])
        self.tree.tag_configure("partial_even", background=self.colors["partial_even"])
        self.tree.tag_configure("partial_odd", background=self.colors["partial_odd"])
        
        self.tree.tag_configure("status_paid", foreground=self.colors["accent_green"])
        # --- THE FIX: Set Unpaid text strictly to Red to match Invoices ---
        self.tree.tag_configure("status_unpaid", foreground=self.colors["error"])
        # ------------------------------------------------------------------
        self.tree.tag_configure("status_partial", foreground="#d97706")
        
        self.tree.tag_configure("status_overdue", foreground=self.colors["error"])
        
        self.tree.tag_configure("bulk_selected", background=self.colors["bulk_select"], foreground="#ffffff")
        
        on_tree_hover(self.tree, self.colors["hover"])

        self.ctx_menu = tk.Menu(self, tearoff=0, bg=self.colors["card"], fg=self.colors["text"], bd=1, activebackground=self.colors["accent_blue"], activeforeground="#ffffff")
        
        self.tree.bind("<Button-3>", self.show_ctx_menu)
        self.tree.bind("<Button-2>", self.show_ctx_menu)
        
        self.tree.bind("<Motion>", self.on_tree_motion)
        
        # --- THE FIX: Prevent Dummy/Header Row Selection ---
        def prevent_dummy_select(event):
            for iid in self.tree.selection():
                if 'empty' in self.tree.item(iid, 'tags'):
                    self.tree.selection_remove(iid)
        self.tree.bind("<<TreeviewSelect>>", prevent_dummy_select)
        # ---------------------------------------------------
        
        # --- THE FIX: Real-time width saving during separator drag ---
        def save_widths():
            # Exclude the stretching columns so they remain dynamic!
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c not in ("vendor", "action")}
            try:
                database.save_ui_setting(f"purch_grid_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_widths)
                
        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: [self.after(50, save_widths), self.on_grid_click(e)])
        self.tree.bind("<Double-1>", self.on_grid_double_click)

        # --- THE FIX: Bind all frames directly for executable compatibility ---
        def on_bg_click(e):
            if self.active_tile_filter != "All":
                self.active_tile_filter = "All"
                self.current_page = 1
                self.load_data()

        self.pagination_frame = tk.Frame(main_container, bg=self.colors["bg"])
        
        for frame in (self, main_container, tiles_f, header_f, title_f, toolbar_container, self.left_toolbar, self.right_toolbar, self.table_f, self.pagination_frame):
            frame.bind("<Button-1>", lambda e: on_bg_click(e))
        # --------------------------------------------------------------------

        # --- THE FIX: Add Pagination UI ---
        self.current_page = 1
        self.items_per_page = 50
        self.total_pages = 1

        self.pagination_frame = tk.Frame(main_container, bg=self.colors["bg"])
        self.pagination_frame.pack(side="bottom", fill="x", pady=(5, 10))
        
        self.table_f.pack_forget()
        self.table_f.pack(side="top", fill="both", expand=True)

        self.btn_prev = tk.Button(self.pagination_frame, text="< Previous", font=("Segoe UI", 10, "bold"), bg=self.colors["bg"], fg=self.colors["text_sec"], relief="flat", cursor="hand2", command=self.prev_page)
        self.btn_prev.pack(side="left", expand=True, anchor="e", padx=10)
        
        self.lbl_page = tk.Label(self.pagination_frame, text="Page 1 of 1", font=("Segoe UI", 10, "bold"), bg=self.colors["bg"], fg=self.colors["text"])
        self.lbl_page.pack(side="left", expand=False, anchor="center")
        
        self.btn_next = tk.Button(self.pagination_frame, text="Next >", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="solid", bd=1, cursor="hand2", command=self.next_page, padx=10, pady=3)
        self.btn_next.pack(side="left", expand=True, anchor="w", padx=10)

        self.load_data()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    def update_dynamic_tile(self, label_widget, val_str):
        str_len = len(val_str)
        if str_len > 18: font_sz = 13
        elif str_len > 12: font_sz = 15
        elif str_len > 9: font_sz = 17
        else: font_sz = 20
        label_widget.config(text=val_str, font=("Segoe UI", font_sz, "bold"))

    def open_drafts_window(self):
        pop = tk.Toplevel(self)
        pop.title("Draft Purchase Bills")
        pop.configure(bg=self.colors["bg"])
        pop.grab_set()

        pop.update_idletasks()
        try:
            draft_f = self.tile_frames["Drafts"]
            win_w = 700
            x = draft_f.winfo_rootx() + draft_f.winfo_width() - win_w
            if x < 0: x = 10
            y = draft_f.winfo_rooty() + draft_f.winfo_height() + 10
            pop.geometry(f"{win_w}x450+{int(x)}+{int(y)}")
        except:
            pop.geometry("700x450")

        tk.Label(pop, text="Draft Purchase Bills", font=("Segoe UI", 16, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(pady=(15, 5))
        tk.Label(pop, text="Double-click to Edit & Post. These bills do not affect inventory or P&L.", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(pady=(0, 15))

        f = tk.Frame(pop, bg=self.colors["card"], highlightthickness=1, highlightbackground=self.colors["border"])
        f.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        tree = ttk.Treeview(f, columns=("date", "bill", "vendor", "total", "actions"), show="headings", style="Purch.Treeview")
        tree.heading("date", text="DATE", anchor="center")
        tree.heading("bill", text="BILL NO.", anchor="center")
        tree.heading("vendor", text="VENDOR", anchor="w")
        tree.heading("total", text="TOTAL", anchor="e")
        tree.heading("actions", text="ACTIONS", anchor="center")
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"purch_drafts_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            d_w = json.loads(res[0]) if res and res[0] else {}
        except:
            d_w = {}

        tree.column("date", width=d_w.get("date", 100), anchor="center", stretch=False)
        tree.column("bill", width=d_w.get("bill", 100), anchor="center", stretch=False)
        tree.column("vendor", width=d_w.get("vendor", 150), anchor="w", stretch=True)
        tree.column("total", width=d_w.get("total", 100), anchor="e", stretch=False)
        tree.column("actions", width=d_w.get("actions", 100), anchor="center", stretch=False)
        
        def save_draft_widths():
            new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "vendor"}
            try:
                database.save_ui_setting(f"purch_drafts_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_draft_sep_drag(event):
            if tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_draft_widths)

        tree.bind("<B1-Motion>", on_draft_sep_drag, add="+")
        tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_draft_widths), add="+")

        tree.pack(fill="both", expand=True)
        
        tree.tag_configure("stripe_even", background=self.colors["stripe_even"])
        tree.tag_configure("stripe_odd", background=self.colors["stripe_odd"])

        def load_drafts():
            for c in tree.get_children(): tree.delete(c)
            try:
                conn = database.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id, purchase_date, bill_number, vendor_name, total FROM purchases WHERE (COALESCE(is_draft, 0) = 1 OR LOWER(COALESCE(status, '')) = 'draft') AND COALESCE(is_deleted, 0) = 0 AND company_id=?", (self.comp_id,))
                rows = cur.fetchall()
                conn.close()
                idx = 0
                for r in rows:
                    tag = "stripe_even" if idx%2==0 else "stripe_odd"
                    fmt_d = smart_date_formatter(r[1], self.date_fmt_code)
                    tot = format_currency(r[4], self.curr_fmt)
                    tree.insert("", "end", iid=str(r[0]), values=(fmt_d, r[2], r[3], tot, "❌ Delete"), tags=(tag,))
                    idx += 1
                for j in range(idx, 15):
                    tag = "stripe_even" if j%2==0 else "stripe_odd"
                    tree.insert("", "end", values=("", "", "", "", ""), tags=(tag, "empty"))
            except Exception as e: print(e)
            
        load_drafts()

        def on_draft_click(e):
            reg = tree.identify("region", e.x, e.y)
            if reg == "cell":
                col = tree.identify_column(e.x)
                if col == "#5": 
                    sel = tree.selection()
                    if not sel: return
                    iid = sel[0]
                    if "empty" in tree.item(iid, "tags"): return
                    
                    if messagebox.askyesno("Delete Draft", "Permanently vaporize this draft? This cannot be undone.", parent=pop):
                        conn = database.get_connection()
                        conn.cursor().execute("DELETE FROM purchase_items WHERE purchase_id=?", (iid,))
                        # --- THE FIX: Added company_id lock ---
                        conn.cursor().execute("DELETE FROM purchases WHERE id=? AND company_id=?", (iid, self.comp_id))
                        conn.commit()
                        conn.close()
                        load_drafts()
                        self.load_data()

        def on_draft_double_click(e):
            reg = tree.identify("region", e.x, e.y)
            if reg == "cell":
                sel = tree.selection()
                if not sel: return
                iid = sel[0]
                if "empty" in tree.item(iid, "tags"): return
                col = tree.identify_column(e.x)
                if col != "#5": 
                    pop.destroy()
                    open_purchase_form(self, self.comp_id, self.curr_fmt, self.date_fmt_code, self.load_data, purchase_id=iid)

        tree.bind("<ButtonRelease-1>", on_draft_click)
        tree.bind("<Double-1>", on_draft_double_click)
        on_tree_hover(tree, self.colors["hover"])

    def show_smart_delete_prompt(self, amount):
        dialog = tk.Toplevel(self)
        dialog.title("Smart Deletion Engine")
        dialog.geometry("500x250")
        dialog.configure(bg=self.colors["bg"])
        dialog.grab_set()
        dialog.transient(self)
        
        self.app.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() // 2) - 250
        y = self.app.winfo_rooty() + (self.app.winfo_height() // 2) - 125
        dialog.geometry(f"+{x}+{y}")

        result = tk.StringVar(value="cancel")
        
        tk.Label(dialog, text="⚠️ Payments Detected", font=("Segoe UI", 14, "bold"), bg=self.colors["bg"], fg=self.colors["error"]).pack(pady=(20, 5))
        
        msg = f"This bill has {format_currency(amount, self.curr_fmt)} recorded as paid.\nHow would you like to handle these funds?"
        tk.Label(dialog, text=msg, font=("Segoe UI", 11), bg=self.colors["bg"], fg=self.colors["text"]).pack(pady=(0, 20))
        
        btn_f = tk.Frame(dialog, bg=self.colors["bg"])
        btn_f.pack(fill="x", padx=20)
        
        def set_res(val):
            result.set(val)
            dialog.destroy()
            
        btn_wallet = tk.Button(btn_f, text="Move to Advance Wallet\n(Real Money Route)", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_green"], fg="white", relief="flat", cursor="hand2", command=lambda: set_res("wallet"))
        btn_wallet.pack(side="left", fill="x", expand=True, padx=5, ipady=5)
        
        btn_vapor = tk.Button(btn_f, text="Data-Entry Mistake\n(Vaporize Phantom Cash)", font=("Segoe UI", 10, "bold"), bg=self.colors["error"], fg="white", relief="flat", cursor="hand2", command=lambda: set_res("vaporize"))
        btn_vapor.pack(side="left", fill="x", expand=True, padx=5, ipady=5)

        tk.Button(dialog, text="Cancel Deletion", font=("Segoe UI", 10), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", command=lambda: set_res("cancel")).pack(pady=15, ipady=3, ipadx=20)

        dialog.wait_window()
        return result.get()

    def open_deleted_bills_window(self):
        pop = tk.Toplevel(self)
        pop.title("Deleted Purchase Bills")
        pop.configure(bg=self.colors["bg"])
        pop.grab_set()

        pop.update_idletasks()
        try:
            del_f = self.tile_frames["Deleted"]
            win_w = 600
            x = del_f.winfo_rootx() + del_f.winfo_width() - win_w
            if x < 0: x = 10
            y = del_f.winfo_rooty() + del_f.winfo_height() + 10
            pop.geometry(f"{win_w}x450+{int(x)}+{int(y)}")
        except:
            pop.geometry("600x450")

        tk.Label(pop, text="Deleted Purchase Bills", font=("Segoe UI", 16, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(pady=(15, 5))
        tk.Label(pop, text="Restoring a purchase bill will return it to your active Purchases ledger.", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(pady=(0, 15))

        f = tk.Frame(pop, bg=self.colors["card"], highlightthickness=1, highlightbackground=self.colors["border"])
        f.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        tree = ttk.Treeview(f, columns=("bill", "actions"), show="headings", style="Purch.Treeview")
        tree.heading("bill", text="BILL NO.", anchor="center")
        tree.heading("actions", text="ACTIONS", anchor="center")
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"purch_del_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            del_w = json.loads(res[0]) if res and res[0] else {}
        except:
            del_w = {}

        tree.column("bill", width=del_w.get("bill", 200), anchor="center", stretch=True)
        tree.column("actions", width=del_w.get("actions", 250), anchor="center", stretch=False)

        def save_del_widths():
            new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "bill"}
            try:
                database.save_ui_setting(f"purch_del_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_del_sep_drag(event):
            if tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_del_widths)

        tree.bind("<B1-Motion>", on_del_sep_drag, add="+")
        tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_del_widths), add="+")

        tree.pack(fill="both", expand=True)
        
        tree.tag_configure("stripe_even", background=self.colors["stripe_even"])
        tree.tag_configure("stripe_odd", background=self.colors["stripe_odd"])

        def load_del():
            for c in tree.get_children(): tree.delete(c)
            try:
                conn = database.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT id, bill_number FROM purchases WHERE is_deleted=1 AND company_id=?", (self.comp_id,))
                rows = cur.fetchall()
                conn.close()
                idx = 0
                for r in rows:
                    tag = "stripe_even" if idx%2==0 else "stripe_odd"
                    tree.insert("", "end", iid=str(r[0]), values=(r[1], "👁 View | ↺ Restore | ❌ Del"), tags=(tag,))
                    idx += 1
                for j in range(idx, 15):
                    tag = "stripe_even" if j%2==0 else "stripe_odd"
                    tree.insert("", "end", values=("", ""), tags=(tag, "empty"))
            except Exception as e: print(e)
            
        load_del()

        def on_del_click(e):
            reg = tree.identify("region", e.x, e.y)
            if reg == "cell":
                col = tree.identify_column(e.x)
                if col == "#2":
                    sel = tree.selection()
                    if not sel: return
                    iid = sel[0]
                    if "empty" in tree.item(iid, "tags"): return
                    
                    bbox = tree.bbox(iid, col)
                    if bbox:
                        cx, cy, cw, ch = bbox
                        if e.x >= cx + (cw * 0.33) and e.x < cx + (cw * 0.66):
                            database.restore_purchase(iid)
                            load_del()
                            self.load_data()
                        elif e.x >= cx + (cw * 0.66):
                            curr_role = getattr(self.app, "current_role", "Admin")
                            curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
                            if curr_role != "Admin" and str(curr_uid) != "1":
                                messagebox.showerror("Access Denied", "Permanently deleting bills is locked to Admin only.", parent=pop)
                                return
                                
                            if messagebox.askyesno("Warning", "Permanently delete this record? This cannot be undone.", parent=pop):
                                database.hard_delete_purchase(iid)
                                database.log_audit("Purchases", "Permanently Deleted", record_ref="Recycle Bin", details="Permanently deleted a purchase bill.", company_id=self.comp_id)
                                load_del()
                                self.load_data()

        def on_del_double_click(e):
            reg = tree.identify("region", e.x, e.y)
            if reg == "cell":
                col = tree.identify_column(e.x)
                if col == "#2":
                    sel = tree.selection()
                    if not sel: return
                    iid = sel[0]
                    if "empty" in tree.item(iid, "tags"): return
                    bbox = tree.bbox(iid, col)
                    if bbox:
                        cx, cy, cw, ch = bbox
                        if e.x < cx + (cw * 0.33):
                            try: open_purchase_preview(self, iid)
                            except: pass

        tree.bind("<ButtonRelease-1>", on_del_click)
        tree.bind("<Double-1>", on_del_double_click)
        on_tree_hover(tree, self.colors["hover"])

    def update_memory_buttons(self):
        if self.undo_stack:
            self.btn_undo.config(state="normal", bg=self.colors["accent_blue"], fg="#ffffff", cursor="hand2")
        else:
            self.btn_undo.config(state="disabled", bg=self.colors["bg"], fg=self.colors["border"], cursor="arrow")
            
        if self.redo_stack:
            self.btn_redo.config(state="normal", bg=self.colors["accent_blue"], fg="#ffffff", cursor="hand2")
        else:
            self.btn_redo.config(state="disabled", bg=self.colors["bg"], fg=self.colors["border"], cursor="arrow")

    def perform_undo(self):
        if not self.undo_stack: return
            
        last_action = self.undo_stack.pop()
        self.redo_stack.append(last_action)

        action_type = last_action["type"]
        ids = last_action["ids"]
        refund_mode = last_action.get("refund_mode", "none")

        try:
            if action_type == "delete":
                for pid in ids: database.restore_purchase(pid)
            else:
                for pid in ids: database.soft_delete_purchase(pid, refund_mode)
                
            self.load_data()
            self.update_memory_buttons()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self)

    def perform_redo(self):
        if not self.redo_stack: return
            
        next_action = self.redo_stack.pop()
        self.undo_stack.append(next_action)

        action_type = next_action["type"]
        ids = next_action["ids"]
        refund_mode = next_action.get("refund_mode", "none")

        try:
            if action_type == "delete":
                for pid in ids: database.soft_delete_purchase(pid, refund_mode)
            else:
                for pid in ids: database.restore_purchase(pid)
                
            self.load_data()
            self.update_memory_buttons()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self)

    def on_filter_change(self, event=None):
        if self.filter_var.get() == "Custom Date Range":
            self.custom_date_f.pack(side="left", padx=(10, 0))
        else:
            self.custom_date_f.pack_forget()
            self.load_data()

    def show_ctx_menu(self, event):
        if self.is_bulk_mode: return
        iid = self.tree.identify_row(event.y)
        if iid and "empty" not in self.tree.item(iid, "tags"):
            self.tree.selection_set(iid)
            
            self.ctx_menu.delete(0, "end")
            
            rec_path = ""
            is_locked = False
            
            # --- THE FIX: Hyper-clean database query mimicking invoices.py ---
            try:
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("SELECT receipt_path, ca_submitted, amount_paid, write_off FROM purchases WHERE id=?", (iid,))
                row = c.fetchone()
                conn.close()
                
                if row:
                    rec_path = row[0] if row[0] else ""
                    is_locked = (row[1] == 1)
                    has_payments = (float(row[2] or 0.0) > 0.01 or float(row[3] or 0.0) > 0.01)
                else:
                    rec_path = ""
                    is_locked = False
                    has_payments = False
            except: 
                is_locked = False
                has_payments = False
                rec_path = ""
            
            # --- THE FIX: Bulletproof warning popups attached to the root window ---
            if is_locked:
                self.ctx_menu.add_command(label="🔒 Cannot Edit (GST Filed)", foreground=self.colors["error"], command=lambda: messagebox.showwarning("GST Filed", "This bill is marked as 'GST Filed' and cannot be edited.", parent=self.winfo_toplevel()))
            elif has_payments:
                self.ctx_menu.add_command(label="🔒 Cannot Edit (Payment Attached)", foreground=self.colors["error"], command=lambda: messagebox.showwarning("Payment Attached", "Cannot edit this bill because it has payments or write-offs attached.\n\nPlease go to the vendor's Ledger and delete the payment records before editing.", parent=self.winfo_toplevel()))
            else:
                self.ctx_menu.add_command(label="✏ Edit Record", command=self.ctx_edit)
                
            # --- THE FIX: Added Duplicate/Clone Button ---
            self.ctx_menu.add_command(label="⎘ Duplicate / Clone", command=self.ctx_clone)
            # ---------------------------------------------
            
            self.ctx_menu.add_command(label="👁 Preview Bill", command=self.ctx_preview)
            
            if rec_path and os.path.exists(rec_path):
                self.ctx_menu.add_separator()
                self.ctx_menu.add_command(label="🖼️ View Attached Receipt", command=lambda p=rec_path: self.ctx_view_receipt(p))
            
            self.ctx_menu.add_separator()
            
            if is_locked:
                self.ctx_menu.add_command(label="🔒 Cannot Return (GST Filed)", foreground=self.colors["error"], command=lambda: messagebox.showwarning("GST Filed", "This bill is marked as 'GST Filed' and cannot be returned.", parent=self.winfo_toplevel()))
            else:
                self.ctx_menu.add_command(label="🔙 Record Return / Debit Note", command=self.ctx_debit_note)
            
            self.ctx_menu.add_separator()
            self.ctx_menu.add_command(label="📄 Bulk Export", command=lambda: self.toggle_bulk_mode("export"))
            
            if is_locked:
                self.ctx_menu.add_command(label="🔒 Cannot Delete (GST Filed)", foreground=self.colors["error"], command=lambda: messagebox.showwarning("GST Filed", "This bill is marked as 'GST Filed' and cannot be deleted.", parent=self.winfo_toplevel()))
            else:
                self.ctx_menu.add_command(label="🗑 Bulk Delete", command=lambda: self.toggle_bulk_mode("delete"))
                
            self.ctx_menu.post(event.x_root, event.y_root)

    def ctx_view_receipt(self, path):
        try: os.startfile(path)
        except: webbrowser.open(path)

    def ctx_preview(self):
        sel = self.tree.selection()
        if sel:
            try: open_purchase_preview(self, sel[0])
            except: messagebox.showinfo("Notice", "Preview Window file not loaded yet.")

    def ctx_edit(self):
        sel = self.tree.selection()
        if sel:
            open_purchase_form(self, self.comp_id, self.curr_fmt, self.date_fmt_code, self.load_data, purchase_id=sel[0])

    def ctx_clone(self):
        sel = self.tree.selection()
        if sel:
            open_purchase_form(self, self.comp_id, self.curr_fmt, self.date_fmt_code, self.load_data, clone_id=sel[0])

    def ctx_debit_note(self):
        sel = self.tree.selection()
        if not sel: return
        p_id = sel[0]

        allowed, err_msg = database.check_purchase_permission(p_id, action="return", company_id=self.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self.app)
            return

        try:
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Fetch purchase_date to protect ledger chronology ---
            c.execute("SELECT bill_number, vendor_name, total, amount_paid, write_off, purchase_date FROM purchases WHERE id=?", (p_id,))
            row = c.fetchone()
            conn.close()
        except: return

        if not row: return
        b_num, v_name, tot, paid, woff, p_date = row
        # -----------------------------------------------------------------
        woff = woff if woff else 0.0
        
        pop = tk.Toplevel(self)
        pop.title("Debit Note / Return")
        pop.geometry("450x380")
        pop.configure(bg=self.colors["bg"])
        pop.grab_set()

        pop.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() // 2) - 225
        y = self.app.winfo_rooty() + (self.app.winfo_height() // 2) - 190
        pop.geometry(f"+{x}+{y}")

        tk.Label(pop, text=f"Record Return: {b_num}", font=("Segoe UI", 14, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(pady=(15, 10))
        
        info_f = tk.Frame(pop, bg=self.colors["card"], padx=10, pady=10, highlightbackground=self.colors["border"], highlightthickness=1)
        info_f.pack(fill="x", padx=30, pady=(0, 15))
        tk.Label(info_f, text=f"Current Bill Total: {format_currency(tot, self.curr_fmt)}", font=("Segoe UI", 11), bg=self.colors["card"], fg=self.colors["text"]).pack(anchor="w")

        form_f = tk.Frame(pop, bg=self.colors["bg"])
        form_f.pack(fill="x", padx=30)
        
        tk.Label(form_f, text="Return Amount:", bg=self.colors["bg"], fg=self.colors["text_sec"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 2))
        amt_var = tk.StringVar(value="0")
        ent_amt = tk.Entry(form_f, textvariable=amt_var, font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        ent_amt.pack(fill="x", ipady=4)
        ent_amt.bind("<FocusIn>", lambda e: ent_amt.delete(0, 'end') if amt_var.get() == '0' else None)

        tk.Label(form_f, text="Reason / Notes:", bg=self.colors["bg"], fg=self.colors["text_sec"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        note_var = tk.StringVar(value="Damaged/Returned Goods")
        ent_note = tk.Entry(form_f, textvariable=note_var, font=("Segoe UI", 11), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        ent_note.pack(fill="x", ipady=4)

        def save_return():
            try: 
                ret_amt = float(amt_var.get().replace(",", ""))
            except: 
                messagebox.showerror("Error", "Invalid amount.", parent=pop)
                return
                
            if ret_amt <= 0: return
            if ret_amt > tot:
                messagebox.showerror("Error", "Return amount cannot exceed the bill total.", parent=pop)
                return
                
            new_tot = tot - ret_amt
            new_paid = paid
            new_woff = woff
            refund_cash = 0.0

            if (new_paid + new_woff) > new_tot:
                excess = (new_paid + new_woff) - new_tot
                
                if new_woff >= excess:
                    new_woff -= excess
                    excess = 0.0
                else:
                    excess -= new_woff
                    new_woff = 0.0

                if excess > 0:
                    refund_cash = excess
                    new_paid -= excess

            new_bal = max(0.0, new_tot - new_paid - new_woff)
            if new_bal <= 0.01: stat = 'Paid'
            elif new_paid > 0 or new_woff > 0: stat = 'Partial'
            else: stat = 'Unpaid'

            try:
                conn = database.get_connection()
                c = conn.cursor()
                
                # --- THE FIX: Fetch vendor ID for Debit Notes ---
                c.execute("SELECT id FROM customers WHERE name=? AND company_id=?", (v_name, self.comp_id))
                v_row = c.fetchone()
                vend_id = v_row[0] if v_row else None
                # ------------------------------------------------
                
                c.execute("UPDATE purchases SET total=?, amount_paid=?, write_off=?, balance_due=?, status=? WHERE id=?", (new_tot, new_paid, new_woff, new_bal, stat, p_id))

                # --- THE FIX: Unified Debit Note Ledger Log (Bypasses General Expenses to stop double-counting!) ---
                note = note_var.get() or f"Debit Note / Return for Bill #{b_num}"
                ref_str = f"Debit Note | {b_num} ({ret_amt})"
                
                c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'System Adjustment', ?, ?)",
                          (self.comp_id, v_name, vend_id, p_date, ret_amt, ref_str, note))

                if refund_cash > 0:
                    c.execute("SELECT id, address FROM customers WHERE name=? AND company_id=?", (v_name, self.comp_id))
                    c_row = c.fetchone()
                    if c_row:
                        c_id, raw_addr = c_row[0], c_row[1]
                        try: j_data = json.loads(raw_addr)
                        except: j_data = {"address": raw_addr if raw_addr else "", "advance_out": 0.0}
                        
                        curr_adv = float(j_data.get("advance_out", j_data.get("advance_wallet", 0.0)))
                        j_data["advance_out"] = curr_adv + refund_cash
                        c.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), c_id))
                    else:
                        j_data = {"address": "", "advance_out": refund_cash}
                        c.execute("INSERT INTO customers (company_id, name, address) VALUES (?, ?, ?)", (self.comp_id, v_name, json.dumps(j_data)))

                    note_w = f"Debit Note (Bill #{b_num}): Refund transferred to Advance"
                    ref_str_w = f"Advance Wallet | {b_num} ({refund_cash})"
                    c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'System Reversal', ?, ?)",
                              (self.comp_id, v_name, vend_id, p_date, -refund_cash, ref_str_w, note_w))
                # ---------------------------------------------------------------------------------------------------

                conn.commit()
                conn.close()
                database.log_audit("Purchases", "Debit Note / Return", record_ref=b_num, details=f"Recorded return of @@CURR:{ret_amt}@@ for {v_name}", amount=ret_amt, company_id=self.comp_id)
                self.load_data()
                pop.destroy()
                messagebox.showinfo("Success", f"Debit Note applied. Bill reduced by {format_currency(ret_amt, self.curr_fmt)}.", parent=self.app)
            except Exception as e:
                messagebox.showerror("Database Error", str(e), parent=pop)

        tk.Button(pop, text="Apply Debit Note", font=("Segoe UI", 11, "bold"), bg=self.colors["error"], fg="#ffffff", relief="flat", cursor="hand2", command=save_return).pack(fill="x", padx=30, pady=(20, 10), ipady=5)

    def toggle_bulk_mode(self, mode=None):
        if self.is_bulk_mode and not mode:
            self.is_bulk_mode = False
            self.bulk_action_type = None
            self.selected_bulk_ids.clear()
            
            self.bulk_actions.pack_forget()
            self.normal_actions.pack(fill="both", expand=True)
            
            self.tree.heading("sl", text="SL. NO.")
            self.load_data()
        else:
            self.is_bulk_mode = True
            self.bulk_action_type = mode
            self.selected_bulk_ids.clear()
            
            self.normal_actions.pack_forget()
            
            for widget in self.bulk_actions.winfo_children(): widget.destroy()
            
            # --- THE FIX: Removed the redundant '0 Selected' label ---
            
            tk.Button(self.bulk_actions, text="✖ Cancel", font=("Segoe UI", 9, "bold"), bg=self.colors["error"], fg="#ffffff", command=self.toggle_bulk_mode, relief="flat", cursor="hand2").pack(side="right")
            
            if mode == "delete":
                # --- THE FIX: Save button to a variable and add (0) counter ---
                self.btn_bulk_del = tk.Button(self.bulk_actions, text="🗑 Delete Selected (0)", font=("Segoe UI", 9, "bold"), bg=self.colors["error"], fg="#ffffff", command=lambda: self.execute_bulk_action("delete"), relief="flat", cursor="hand2")
                self.btn_bulk_del.pack(side="right", padx=10)
            elif mode == "export":
                # --- THE FIX: Swapped packing order so CSV and PDF buttons flip on screen ---
                tk.Button(self.bulk_actions, text="🖨 Export PDF", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", command=lambda: self.execute_bulk_action("export_pdf"), relief="flat", cursor="hand2").pack(side="right", padx=(5, 10))
                tk.Button(self.bulk_actions, text="📄 Export CSV", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", command=lambda: self.execute_bulk_action("export_csv"), relief="flat", cursor="hand2").pack(side="right", padx=0)
            
            # --- THE FIX: Added the missing Select All button with dynamic counter for Purchases ---
            self.btn_select_all = tk.Button(self.bulk_actions, text="☑ Select All (0)", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", command=self.toggle_select_all, relief="flat", cursor="hand2")
            self.btn_select_all.pack(side="right", padx=10)
            
            self.bulk_actions.pack(fill="both", expand=True)
            self.tree.heading("sl", text="[ ] ALL")
            
            for child in self.tree.get_children():
                if "empty" in self.tree.item(child, "tags"): continue
                vals = list(self.tree.item(child, "values"))
                vals[0] = "[ ]"
                self.tree.item(child, values=vals)

    def toggle_row_selection(self, p_id):
        vals = list(self.tree.item(p_id, "values"))
        current_tags = self.tree.item(p_id, "tags")
        
        # --- THE FIX: Only block selection if the user is trying to DELETE ---
        if p_id not in self.selected_bulk_ids:
            if self.bulk_action_type == "delete":
                conn = database.get_connection()
                c = conn.cursor()
                # --- THE FIX: Added company_id lock ---
                c.execute("SELECT ca_submitted FROM purchases WHERE id=? AND company_id=?", (p_id, self.comp_id))
                res = c.fetchone()
                conn.close()
                if res and res[0] == 1:
                    messagebox.showwarning("Locked", "This bill is GST Filed and cannot be deleted.", parent=self)
                    return
            self.selected_bulk_ids.add(p_id)
            vals[0] = "[✓]" 
            new_tags = current_tags + ("bulk_selected",)
        else:
            self.selected_bulk_ids.remove(p_id)
            vals[0] = "[ ]"
            new_tags = tuple(t for t in current_tags if t != "bulk_selected")
            
        self.tree.item(p_id, values=vals, tags=new_tags)
        
        # --- THE FIX: Verify widgets physically exist, and update both dynamic counters ---
        if hasattr(self, "btn_bulk_del") and self.btn_bulk_del.winfo_exists(): 
            self.btn_bulk_del.config(text=f"🗑 Delete Selected ({len(self.selected_bulk_ids)})")
        if hasattr(self, "btn_select_all") and self.btn_select_all.winfo_exists():
            self.btn_select_all.config(text=f"☑ Select All ({len(self.selected_bulk_ids)})")
        
        all_items = [child for child in self.tree.get_children() if "empty" not in self.tree.item(child, "tags")]
        if len(self.selected_bulk_ids) == len(all_items) and len(all_items) > 0:
            self.tree.heading("sl", text="[✓] ALL")
        else:
            self.tree.heading("sl", text="[ ] ALL")

    def toggle_select_all(self):
        all_items = [child for child in self.tree.get_children() if "empty" not in self.tree.item(child, "tags")]
        
        # --- THE FIX: Only filter out locked items if we are DELETING ---
        valid_items = []
        conn = database.get_connection()
        c = conn.cursor()
        for iid in all_items:
            if self.bulk_action_type == "delete":
                # --- THE FIX: Added company_id lock ---
                c.execute("SELECT ca_submitted FROM purchases WHERE id=? AND company_id=?", (iid, self.comp_id))
                res = c.fetchone()
                if not (res and res[0] == 1):
                    valid_items.append(iid)
            else:
                valid_items.append(iid) # Export mode allows everything
        conn.close()
        
        if len(self.selected_bulk_ids) == len(valid_items) and len(valid_items) > 0:
            self.selected_bulk_ids.clear()
            for child in valid_items:
                vals = list(self.tree.item(child, "values"))
                vals[0] = "[ ]"
                new_tags = tuple(t for t in self.tree.item(child, "tags") if t != "bulk_selected")
                self.tree.item(child, values=vals, tags=new_tags)
            self.tree.heading("sl", text="[ ] ALL")
        else:
            for child in valid_items:
                self.selected_bulk_ids.add(child)
                vals = list(self.tree.item(child, "values"))
                vals[0] = "[✓]" 
                curr_tags = self.tree.item(child, "tags")
                new_tags = curr_tags if "bulk_selected" in curr_tags else curr_tags + ("bulk_selected",)
                self.tree.item(child, values=vals, tags=new_tags)
            self.tree.heading("sl", text="[✓] ALL")
            
        # --- THE FIX: Verify widgets physically exist, and update both dynamic counters ---
        if hasattr(self, "btn_bulk_del") and self.btn_bulk_del.winfo_exists(): 
            self.btn_bulk_del.config(text=f"🗑 Delete Selected ({len(self.selected_bulk_ids)})")
        if hasattr(self, "btn_select_all") and self.btn_select_all.winfo_exists():
            self.btn_select_all.config(text=f"☑ Select All ({len(self.selected_bulk_ids)})")

    def execute_bulk_action(self, action):
        if not self.selected_bulk_ids:
            messagebox.showinfo("Bulk Action", "No items selected.", parent=self)
            return
            
        # --- THE FIX: Route the new bulk export buttons correctly ---
        if action == "export_csv":
            self.export_csv(bulk_ids=self.selected_bulk_ids)
            self.toggle_bulk_mode()
            return
        elif action == "export_pdf":
            self.export_pdf(bulk_ids=self.selected_bulk_ids)
            self.toggle_bulk_mode()
            return
            
        action_word = "Delete" if action == "delete" else "Restore"
        refund_mode = 'none'
        
        if action == "delete":
            conn = database.get_connection()
            c = conn.cursor()
            
            # --- THE FIX: The Vault Door (Hard abort if locked items found) ---
            allowed_ids = []
            skipped_locked = 0
            for row_id in self.selected_bulk_ids:
                c.execute("SELECT ca_submitted FROM purchases WHERE id=?", (row_id,))
                res = c.fetchone()
                if res and res[0] == 1:
                    messagebox.showerror("Action Denied", "Deletion aborted.\n\nOne or more selected bills are GST Filed and locked. To protect compliance data, the batch has been cancelled.", parent=self)
                    conn.close()
                    return
                allowed, _ = database.check_purchase_permission(row_id, action="delete", company_id=self.comp_id)
                if allowed: allowed_ids.append(row_id)
                else: skipped_locked += 1
            
            if not allowed_ids:
                messagebox.showerror("Access Denied", "All selected bills are locked from deletion due to your account permissions.", parent=self)
                conn.close()
                return
            self.selected_bulk_ids = set(allowed_ids)
                    
            try: c.execute("ALTER TABLE purchases ADD COLUMN write_off REAL DEFAULT 0.0")
            except: pass
            
            placeholders = ",".join("?" for _ in self.selected_bulk_ids)
            c.execute(f"SELECT SUM(amount_paid), SUM(write_off) FROM purchases WHERE id IN ({placeholders}) AND company_id=?", (*self.selected_bulk_ids, self.comp_id))
            row = c.fetchone()
            tot_paid = row[0] if row and row[0] else 0.0
            tot_woff = row[1] if row and row[1] else 0.0
            conn.close()
            
            if tot_paid > 0.01:
                res = self.show_smart_delete_prompt(tot_paid)
                if res == "cancel": return
                refund_mode = res
            elif tot_woff > 0.01:
                if not messagebox.askyesno("Confirm", f"This bill has a Write-Off of {format_currency(tot_woff, self.curr_fmt)}.\nVaporize this record?", parent=self):
                    return
                refund_mode = 'vaporize'
            else:
                if not messagebox.askyesno("Confirm", f"Are you sure you want to delete {len(self.selected_bulk_ids)} items?", parent=self):
                    return
                refund_mode = 'vaporize'
        else:
            if not messagebox.askyesno("Confirm", f"Are you sure you want to restore {len(self.selected_bulk_ids)} items?", parent=self):
                return
            
        try:
            if action == "delete":
                for pid in self.selected_bulk_ids: database.soft_delete_purchase(pid, refund_mode)
                database.log_audit("Purchases", "Moved to Recycle Bin", record_ref=f"{len(self.selected_bulk_ids)} Bills", details=f"Moved {len(self.selected_bulk_ids)} bills to the Recycle Bin.", company_id=self.comp_id)
                if 'skipped_locked' in locals() and skipped_locked > 0:
                    messagebox.showwarning("Partial Deletion", f"Moved {len(self.selected_bulk_ids)} bills to the Recycle Bin.\n\n{skipped_locked} past-date bill(s) were skipped due to your account permissions.", parent=self)
            else:
                for pid in self.selected_bulk_ids: database.restore_purchase(pid)
                database.log_audit("Purchases", "Restored", record_ref=f"{len(self.selected_bulk_ids)} Bills", details=f"Restored {len(self.selected_bulk_ids)} bills from the Recycle Bin.", company_id=self.comp_id)
            
            self.undo_stack.append({"type": action, "ids": list(self.selected_bulk_ids), "refund_mode": refund_mode})
            self.redo_stack.clear()
            self.update_memory_buttons()
            
            messagebox.showinfo("Success", f"{len(self.selected_bulk_ids)} items {action_word}d successfully.", parent=self)
            
            if self.is_bulk_mode:
                self.toggle_bulk_mode() 
            else:
                self.selected_bulk_ids.clear()
                self.load_data()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self)

    def export_csv(self, bulk_ids=None):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Save Purchases CSV")
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                headers = [self.tree.heading(c)["text"] for c in self.tree["columns"] if c != "action"]
                # --- THE FIX: Force the first header to be SL. NO. instead of the checkbox ---
                headers[0] = "SL. NO."
                writer.writerow(headers)
                
                export_idx = 1
                for child in self.tree.get_children():
                    if "empty" in self.tree.item(child, "tags"): continue
                    if bulk_ids and child not in bulk_ids: continue
                    
                    row_vals = list(self.tree.item(child, "values"))
                    # --- THE FIX: Replace the checkbox with a clean sequential number ---
                    row_vals[0] = export_idx
                    writer.writerow(row_vals[:-1]) 
                    export_idx += 1
                    
            messagebox.showinfo("Success", "CSV Exported Successfully!", parent=self)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)

    def export_pdf(self, bulk_ids=None):
        # --- THE FIX: Changed title from 'Purchase Bills & Expenses Ledger' to 'Purchase Bills' ---
        html = f"<html><head><title>Purchases Export</title><style>body{{font-family:Arial, sans-serif;}} table{{width:100%; border-collapse:collapse; margin-top:20px;}} th,td{{border:1px solid #ddd; padding:8px; text-align:center; white-space:nowrap;}} th{{background-color:#f2f2f2;}}</style></head><body><h2>Purchase Bills</h2><table><tr>"
        headers = [self.tree.heading(c)["text"] for c in self.tree["columns"] if c != "action"]
        # --- THE FIX: Force the first header to be SL. NO. instead of the checkbox ---
        headers[0] = "SL. NO."
        
        for h in headers: html += f"<th>{h}</th>"
        html += "</tr>"
        
        has_data = False
        export_idx = 1
        for child in self.tree.get_children():
            if "empty" in self.tree.item(child, "tags"): continue
            
            if bulk_ids and child not in bulk_ids: continue
            
            has_data = True
            vals = list(self.tree.item(child, "values"))
            # --- THE FIX: Replace the checkbox with a clean sequential number ---
            vals[0] = export_idx
            
            html += "<tr>"
            for v in vals[:-1]: html += f"<td>{v}</td>"
            html += "</tr>"
            export_idx += 1
            
        html += "</table>"
        if not has_data: html += "<p>No active filters generated any records.</p>"
        html += "<script>window.onload=function(){window.print();}</script></body></html>"
        
        # --- THE FIX: Tagged prefix for the Sweeper ---
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Purchase_Report_")
        # ----------------------------------------------
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))

    def on_tree_motion(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree.identify_column(event.x)
            action_col = "#9" if self.has_gst else "#7"
            
            if self.is_bulk_mode:
                self.tree.config(cursor="hand2")
            elif col in ("#3", "#4", action_col):
                self.tree.config(cursor="hand2")
            else:
                self.tree.config(cursor="")
                
        elif region == "heading" and self.is_bulk_mode and self.tree.identify_column(event.x) == "#1":
            self.tree.config(cursor="hand2")
        else:
            self.tree.config(cursor="")

    def on_grid_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return
        
        item = self.tree.selection()
        if not item or "empty" in self.tree.item(item[0], "tags"): return
        
        col = self.tree.identify_column(event.x)
        p_id = item[0]
        
        action_col = "#9" if self.has_gst else "#7"

        if col == "#4": 
            try: open_purchase_payment_portal(self, p_id)
            except NameError: pass
                
        elif col == "#3":
            try: open_purchase_preview(self, p_id)
            except NameError: pass
                
        elif col == action_col: 
            bbox = self.tree.bbox(p_id, col)
            if bbox:
                cx, cy, cw, ch = bbox
                if event.x < cx + (cw * 0.65):
                    try: open_purchase_preview(self, p_id)
                    except: pass
        else:
            # --- THE FIX: Double-clicking anywhere else opens the Editor or shows the Warning ---
            try:
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("SELECT COALESCE(ca_submitted, 0), amount_paid, write_off FROM purchases WHERE id=? AND company_id=?", (p_id, self.comp_id))
                r = c.fetchone()
                conn.close()
                if r:
                    if r[0] == 1:
                        messagebox.showwarning("GST Filed", "This bill is marked as 'GST Filed'.\n\nTo prevent data mismatch, editing is locked.", parent=self.winfo_toplevel())
                        return
                    # --- THE FIX: Strict Tally-Style Payment Lock for Purchases ---
                    if float(r[1] or 0.0) > 0.01 or float(r[2] or 0.0) > 0.01:
                        messagebox.showwarning("Payment Attached", "Cannot edit this bill because it has payments or write-offs attached.\n\nPlease go to the vendor's Ledger and delete the payment records before editing.", parent=self.winfo_toplevel())
                        return
            except: pass
            
            try:
                from views.purchase_parts.engines.purchase_forms import open_purchase_form
                open_purchase_form(self, self.comp_id, self.curr_fmt, self.date_fmt_code, self.load_data, purchase_id=p_id)
            except: pass

    def on_grid_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        
        if region == "separator":
            return

        if region == "heading" and self.is_bulk_mode and self.tree.identify_column(event.x) == "#1":
            self.toggle_select_all()
            return
            
        # --- THE FIX: Clear filter if clicking empty grid space ---
        if region == "nothing":
            if self.active_tile_filter != "All":
                self.active_tile_filter = "All"
                self.current_page = 1
                self.load_data()
            return
            
        if region != "cell": return
        
        item = self.tree.selection()
        if not item or "empty" in self.tree.item(item[0], "tags"):
            if self.active_tile_filter != "All":
                self.active_tile_filter = "All"
                self.current_page = 1
                self.load_data()
            return
        # ----------------------------------------------------------
        
        col = self.tree.identify_column(event.x)
        p_id = item[0]

        if self.is_bulk_mode:
            self.toggle_row_selection(p_id)
            return

        action_col = "#9" if self.has_gst else "#7"

        if col == action_col: 
            bbox = self.tree.bbox(p_id, col)
            if bbox:
                cx, cy, cw, ch = bbox
                if event.x >= cx + (cw * 0.65):
                    # --- THE FIX: Hard lock the trash can icon ---
                    try:
                        conn = database.get_connection()
                        c = conn.cursor()
                        # --- THE FIX: Added company_id lock ---
                        c.execute("SELECT COALESCE(ca_submitted, 0) FROM purchases WHERE id=? AND company_id=?", (p_id, self.comp_id))
                        row = c.fetchone()
                        conn.close()
                        if row and row[0] == 1:
                            messagebox.showwarning("Locked", "This bill is marked as 'GST Filed'.\n\nFinancial alterations are locked.", parent=self)
                            return
                    except: pass
                    
                    self.selected_bulk_ids = {p_id}
                    self.execute_bulk_action("delete")

    def get_date_range(self):
        opt = self.filter_var.get()
        today = date.today()
        if opt == "This Month":
            start = today.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
        elif opt == "This Financial Year":
            start_year = today.year if today.month >= 4 else today.year - 1
            return f"{start_year}-04-01", f"{start_year+1}-03-31"
        elif opt == "Custom Date Range":
            try:
                if not self.from_var.get() or not self.to_var.get(): return None, None
                start = datetime.strptime(self.from_var.get(), self.date_fmt_code).strftime("%Y-%m-%d")
                end = datetime.strptime(self.to_var.get(), self.date_fmt_code).strftime("%Y-%m-%d")
                return start, end
            except: pass
        return None, None

    def load_data(self, event=None):
        if event:
            self.current_page = 1
            
        if self.is_bulk_mode: return 
        
        for child in self.tree.get_children(): self.tree.delete(child)
        
        search_term = self.search_var.get().lower()
        if search_term == "search vendor or bill...": search_term = ""
        
        start_date, end_date = self.get_date_range()
        sort_order = "DESC" if self.sort_var.get() == "Latest" else "ASC"

        for key, frame in self.tile_frames.items():
            is_active = (key == self.active_tile_filter) or (self.active_tile_filter == "All" and key == "Total")
            if is_active: 
                frame.config(highlightbackground=self.colors["accent_blue"], highlightthickness=2)
            else: 
                frame.config(highlightbackground=self.colors["border"], highlightthickness=1)

        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            try: c.execute("ALTER TABLE purchases ADD COLUMN write_off REAL DEFAULT 0.0")
            except: pass
            
            # --- THE FIX: Fetch aliases alongside payable_terms & payable_days ---
            c.execute("SELECT id, name, address, alias FROM customers WHERE company_id=?", (self.comp_id,))
            cust_terms = {}
            cust_aliases = {}
            for row in c.fetchall():
                c_id, c_name, c_addr = row[0], row[1], row[2]
                alias = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                cust_aliases[c_name.lower()] = alias
                try:
                    j_data = json.loads(c_addr)
                    raw_terms = j_data.get("payable_terms", j_data.get("payable_days", 0))
                    t_val = int("".join(filter(str.isdigit, str(raw_terms))) or 0)
                    cust_terms[c_name.lower()] = t_val
                    cust_terms[f"id_{c_id}"] = t_val
                except:
                    cust_terms[c_name.lower()] = 0
            # ---------------------------------------------------------------------
            
            query = f"SELECT id, purchase_date, bill_number, vendor_name, subtotal, cgst, sgst, igst, total, status, amount_paid, write_off FROM purchases WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 AND COALESCE(is_draft, 0) = 0 AND LOWER(COALESCE(status, '')) != 'draft' ORDER BY id {sort_order}"
            params = [self.comp_id]
            
            c.execute(query, tuple(params))
            rows = c.fetchall()
            
            c.execute("SELECT COUNT(id) FROM purchases WHERE company_id=? AND is_deleted=1", (self.comp_id,))
            deleted_count = c.fetchone()[0]
            
            try:
                c.execute("SELECT COUNT(id) FROM purchases WHERE company_id=? AND COALESCE(is_deleted, 0) = 0 AND (COALESCE(is_draft, 0) = 1 OR LOWER(COALESCE(status, '')) = 'draft')", (self.comp_id,))
                draft_count = c.fetchone()[0]
            except: draft_count = 0
            
            # --- THE FIX: Pre-parse the Dates for Pure Mathematical Filtering ---
            def safe_p_date(d_str):
                if not d_str: return datetime.min
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                    try: return datetime.strptime(str(d_str).strip()[:10], fmt)
                    except: pass
                return datetime.min

            try: start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
            except: start_dt = None
            try: end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
            except: end_dt = None
            # --------------------------------------------------------------------
            
            tot_count = 0; tot_billed = 0.0; paid_count = 0; unpaid_count = 0
            tot_unpaid_amt = 0.0
            filtered_rows = []
            
            for r in rows:
                p_id, p_date, b_num, v_name, sub, cgst, sgst, igst, tot, stat, amt_paid, woff = r
                woff = woff if woff else 0.0
                
                # --- THE FIX: Math-Based Date Filtering ---
                if start_dt and end_dt:
                    p_dt = safe_p_date(p_date)
                    if p_dt == datetime.min or p_dt < start_dt or p_dt > end_dt: 
                        continue
                # ------------------------------------------
                
                if search_term:
                    full_txt = f"{p_date} {b_num} {v_name} {tot}".lower()
                    if search_term not in full_txt: continue
                
                # Calculate dynamic stats ONLY for the bills actively shown on screen!
                tot_count += 1
                tot_billed += (tot if tot else 0.0)
                
                due = max(0.0, (tot if tot else 0.0) - (amt_paid if amt_paid else 0.0) - woff)
                
                if due <= 0.01: 
                    paid_count += 1
                else: 
                    unpaid_count += 1
                    tot_unpaid_amt += due
                
                if self.active_tile_filter == "Paid" and due > 0.01: continue
                if self.active_tile_filter == "Unpaid" and due <= 0.01: continue
                
                filtered_rows.append(r)

            # --- THE FIX: Bulletproof Python-side Chronological Sorting ---
            if self.sort_var.get() == "Latest":
                filtered_rows.sort(key=lambda x: (safe_p_date(x[1]), x[0]), reverse=True)
            else:
                filtered_rows.sort(key=lambda x: (safe_p_date(x[1]), x[0]))
            # --------------------------------------------------------------

            # --- THE FIX: Calculate Pagination Math & Apply Slice ---
            import math
            self.total_pages = math.ceil(len(filtered_rows) / self.items_per_page)
            if self.total_pages < 1: self.total_pages = 1
            if self.current_page > self.total_pages: self.current_page = self.total_pages

            start_idx = (self.current_page - 1) * self.items_per_page
            end_idx = start_idx + self.items_per_page
            paginated_list = filtered_rows[start_idx:end_idx]

            if hasattr(self, 'lbl_page'):
                self.lbl_page.config(text=f"Page {self.current_page} of {self.total_pages}")
                
                if self.current_page <= 1:
                    self.btn_prev.config(state="disabled", fg=self.colors["border"], bg=self.colors["bg"], cursor="arrow")
                else:
                    self.btn_prev.config(state="normal", fg=self.colors["text_sec"], bg=self.colors["bg"], cursor="hand2")
                    
                if self.current_page >= self.total_pages:
                    self.btn_next.config(state="disabled", bg=self.colors["bg"], fg=self.colors["border"], cursor="arrow")
                else:
                    self.btn_next.config(state="normal", bg=self.colors["card"], fg=self.colors["text"], cursor="hand2")
            
            display_idx = start_idx + 1
            
            # --- THE FIX: ADD MONTH HEADER TAG & DATE PARSER ---
            self.tree.tag_configure("month_header", background=self.colors["border"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
            last_month_str = ""
            # ---------------------------------------------------
            
            for r in paginated_list:
                p_id, p_date, b_num, v_name, sub, cgst, sgst, igst, tot, stat, amt_paid, woff = r
                woff = woff if woff else 0.0
                
                # --- THE FIX: Display clean vendor name without alias in the main grid ---
                display_v_name = v_name
                # -------------------------------------------------------------------------

                due = max(0.0, tot - amt_paid - woff)
                
                # --- THE FIX: Parse any date format safely to highlight overdue bills ---
                is_overdue = False
                try:
                    if due > 0.01:
                        parsed_dt = safe_p_date(p_date)
                        if parsed_dt != datetime.min:
                            p_dt = parsed_dt.date()
                            p_terms = cust_terms.get(v_name.lower(), 0)
                            if p_terms > 0:
                                due_dt = p_dt + timedelta(days=p_terms)
                                if date.today() > due_dt:
                                    is_overdue = True
                except: pass
                # ------------------------------------------------------------------------
                
                if due <= 0.01:
                    stat_txt = "Paid"
                    stat_tag = "status_paid"
                    bg_tag = "stripe_even" if display_idx % 2 == 0 else "stripe_odd"
                elif amt_paid > 0 or woff > 0:
                    stat_txt = f"OVERDUE ({format_currency(due, self.curr_fmt)} due)" if is_overdue else f"Partial ({format_currency(due, self.curr_fmt)} due)"
                    stat_tag = "status_overdue" if is_overdue else "status_partial"
                    # --- THE FIX: Only apply the warning colors if ACTUALLY overdue ---
                    bg_tag = ("partial_even" if display_idx % 2 == 0 else "partial_odd") if is_overdue else ("stripe_even" if display_idx % 2 == 0 else "stripe_odd")
                else:
                    stat_txt = "OVERDUE (Unpaid)" if is_overdue else "Unpaid"
                    stat_tag = "status_overdue" if is_overdue else "status_unpaid"
                    # --- THE FIX: Only apply the warning colors if ACTUALLY overdue ---
                    bg_tag = ("pending_even" if display_idx % 2 == 0 else "pending_odd") if is_overdue else ("stripe_even" if display_idx % 2 == 0 else "stripe_odd")

                tot_gst = (cgst if cgst else 0.0) + (sgst if sgst else 0.0) + (igst if igst else 0.0)
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                action_txt = "👁 Preview | ❌ Delete"
                
                # --- THE FIX: INJECT MONTH HEADER BEFORE THE ROW ---
                dt = safe_p_date(p_date)
                current_month_str = dt.strftime("%B, %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                
                if current_month_str != last_month_str:
                    if self.has_gst: empty_tup = ("", f"📅  {current_month_str}", "", "", "", "", "", "", "")
                    else: empty_tup = ("", f"📅  {current_month_str}", "", "", "", "", "")
                    self.tree.insert("", "end", iid=f"empty_header_{current_month_str}_{display_idx}", values=empty_tup, tags=("month_header", "empty"))
                    last_month_str = current_month_str
                # ---------------------------------------------------
                
                # --- THE FIX: Inject display_v_name into the table instead of the raw v_name ---
                if self.has_gst:
                    self.tree.insert("", "end", iid=str(p_id), values=(display_idx, fmt_date, b_num, display_v_name, format_currency(sub, self.curr_fmt), format_currency(tot_gst, self.curr_fmt), format_currency(tot, self.curr_fmt), stat_txt, action_txt), tags=(bg_tag, stat_tag))
                else:
                    self.tree.insert("", "end", iid=str(p_id), values=(display_idx, fmt_date, b_num, display_v_name, format_currency(tot, self.curr_fmt), stat_txt, action_txt), tags=(bg_tag, stat_tag))
                # -------------------------------------------------------------------------------

                display_idx += 1
                
            current_rows = len(paginated_list)
            if current_rows < 15:
                for idx in range(current_rows + 1, 16):
                    tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
                    empty_tup = ("", "", "", "", "", "", "", "", "") if self.has_gst else ("", "", "", "", "", "", "")
                    self.tree.insert("", "end", values=empty_tup, tags=(tag, "empty"))
                
            self.lbl_t_count.config(text=str(tot_count))
            
            # --- THE FIX: Hide Financial Totals for Non-Admins (Based on Settings) ---
            hide_money = False
            try:
                curr_role = getattr(self.app, "current_role", "Admin")
                curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
                
                if curr_role != "Admin" and str(curr_uid) != "1":
                    perms = database.get_user_permissions(curr_uid)
                    rules_data = perms.get("purchase_rules", {})
                    cid_str = str(self.comp_id)
                    if isinstance(rules_data, dict) and ("global" in rules_data or any(k.isdigit() for k in rules_data.keys())):
                        rules = rules_data.get(cid_str, rules_data.get("global", {}))
                    else:
                        rules = rules_data
                    hide_money = rules.get("hide_financials", False)
            except Exception: pass
            
            if hide_money:
                self.update_dynamic_tile(self.lbl_t_billed, "****")
            else:
                self.update_dynamic_tile(self.lbl_t_billed, format_currency(tot_billed, self.curr_fmt))
            # -----------------------------------------------------------------------
            
            self.lbl_t_paid.config(text=str(paid_count))
            
            # --- THE FIX: Format unpaid string and set it ---
            if hide_money:
                unpaid_str = f"{unpaid_count}  |  ****"
            else:
                unpaid_str = f"{unpaid_count}  |  {format_currency(tot_unpaid_amt, self.curr_fmt)}"
                
            self.update_dynamic_tile(self.lbl_t_unpaid, unpaid_str)
            # ------------------------------------------------
            
            self.lbl_t_deleted.config(text=str(deleted_count))
            
            if hasattr(self, 'lbl_t_drafts'):
                self.lbl_t_drafts.config(text=str(draft_count))
            
            conn.close()
        except Exception as e:
            print("Error loading purchases:", e)

    def attempt_soft_delete(self, row_id):
        allowed, err_msg = database.check_purchase_permission(row_id, action="delete", company_id=self.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self.app)
            return

        # --- THE BULLETPROOF FIX: We untangle the wallet manually to bypass database.py ---
        conn = database.get_connection()
        c = conn.cursor()
        
        try:
            # --- THE FIX: Added purchase_date and total to protect ledger chronology & log audit ---
            c.execute("SELECT bill_number, vendor_name, amount_paid, company_id, write_off, purchase_date, total FROM purchases WHERE id=? AND company_id=?", (row_id, self.comp_id))
            row = c.fetchone()
            
            if not row:
                conn.close()
                return
                
            b_num, v_name, paid_amt, comp_id, woff, p_date = row
            paid_amt = float(paid_amt or 0.0)
            woff = float(woff or 0.0)
            
            refund_mode = 'none'
            
            if paid_amt > 0.01:
                res = self.show_smart_delete_prompt(paid_amt)
                if res == "cancel":
                    conn.close()
                    return
                refund_mode = res
            elif woff > 0.01:
                if not messagebox.askyesno("Confirm", f"This bill has a Write-Off of {format_currency(woff, self.curr_fmt)}.\nVaporize this record?", parent=self):
                    conn.close()
                    return
                refund_mode = 'vaporize'
            else:
                if not messagebox.askyesno("Confirm", "Move bill to Recycle Bin?", parent=self):
                    conn.close()
                    return
                refund_mode = 'vaporize'

            conn.commit()
            conn.close()

            database.soft_delete_purchase(row_id, refund_mode)
            database.log_audit("Purchases", "Moved to Recycle Bin", record_ref=b_num, details=f"Vendor: {v_name}", amount=float(row[6] or 0.0), company_id=self.comp_id)
            
            self.undo_stack.append({"type": "delete", "ids": [row_id], "refund_mode": refund_mode})
            self.redo_stack.clear()
            self.load_data()
            
        except Exception as e:
            try: conn.close()
            except: pass
            print(f"Delete Error: {e}")
       # --- THE FIX: Smart Recent Payments Modal (Bulk Export + Reverse Deletion logic) ---
    def show_recent_payments(self):
        from views.invoice_parts.calendar_widget import NativeCalendar
        import csv
        import tempfile
        import webbrowser
        from datetime import datetime, timedelta, date

        pop = tk.Toplevel(self.app)
        pop.title("Recent Vendor Payments")
        pop.geometry("1100x700")
        pop.configure(bg=self.colors["bg"])
        pop.grab_set()
        pop.transient(self.app)
        
        pop.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() // 2) - 550
        y = self.app.winfo_rooty() + (self.app.winfo_height() // 2) - 350
        pop.geometry(f"+{max(0,x)}+{max(0,y)}")

        search_var = tk.StringVar()
        filter_var = tk.StringVar(value="All Time")
        from_var = tk.StringVar()
        to_var = tk.StringVar()

        current_page = [1]
        items_per_page = 50
        filtered_rows = []
        
        is_bulk_mode = [False]
        selected_items = set()

        # TOOLBAR
        header_f = tk.Frame(pop, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        header_f.pack(fill="x", padx=20, pady=(20, 10))
        
        inner_f = tk.Frame(header_f, bg=self.colors["card"], pady=10, padx=10)
        inner_f.pack(fill="x")
        
        tk.Label(inner_f, text="💸 Recent Payments", font=("Arial", 14, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack(side="left", padx=(5, 15))
        
        tk.Label(inner_f, text="🔍 Search:", bg=self.colors["card"], font=("Arial", 9, "bold"), fg=self.colors["text_sec"]).pack(side="left", padx=(5, 5))
        tk.Entry(inner_f, textvariable=search_var, font=("Arial", 10), width=25, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1).pack(side="left", ipady=3)
        
        btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=lambda: search_var.set(""))
        btn_clear_search.pack(side="left", padx=(5, 5))
        
        btn_bulk_mode = tk.Button(inner_f, text="📄 Bulk Export", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="solid", highlightbackground=self.colors["border"], bd=1, cursor="hand2", padx=8, pady=2, command=lambda: toggle_bulk_mode())
        btn_bulk_mode.pack(side="right", padx=(10, 5))

        def trigger_clear_all():
            search_var.set("")
            from_var.set("")
            to_var.set("")
            filter_var.set("All Time")
            toggle_custom_date()
        
        btn_clear = tk.Button(inner_f, text="✖ Clear All", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=trigger_clear_all)
        btn_clear.pack(side="right", padx=(10, 5))
        
        custom_date_f = tk.Frame(inner_f, bg=self.colors["card"])
        
        to_f = tk.Frame(custom_date_f, bg=self.colors["bg"], highlightbackground=self.colors["border"], highlightthickness=1)
        to_f.pack(side="right", padx=(5, 0))
        to_btn = tk.Button(to_f, text="▼", bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2")
        to_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(to_f, textvariable=to_var, font=("Arial", 10), width=10, bg=self.colors["bg"], fg=self.colors["text"], bd=0, insertbackground=self.colors["text"]).pack(side="left", ipady=4, padx=5)
        to_btn.config(command=lambda b=to_btn: NativeCalendar(pop, to_var, anchor_widget=b))
        tk.Label(custom_date_f, text="To:", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side="right", padx=(10, 0))
        
        from_f = tk.Frame(custom_date_f, bg=self.colors["bg"], highlightbackground=self.colors["border"], highlightthickness=1)
        from_f.pack(side="right", padx=(5, 0))
        from_btn = tk.Button(from_f, text="▼", bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2")
        from_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(from_f, textvariable=from_var, font=("Arial", 10), width=10, bg=self.colors["bg"], fg=self.colors["text"], bd=0, insertbackground=self.colors["text"]).pack(side="left", ipady=4, padx=5)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(pop, from_var, anchor_widget=b))
        tk.Label(custom_date_f, text="📅 From:", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side="right", padx=(10, 0))
        
        date_cb = ttk.Combobox(inner_f, textvariable=filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=12, font=("Arial", 10), cursor="hand2", style="Theme.TCombobox")
        date_cb.pack(side="right", padx=(5, 0))
        lbl_filter = tk.Label(inner_f, text="Filter:", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"])
        lbl_filter.pack(side="right", padx=(10,0))
        
        def toggle_custom_date(*args):
            if filter_var.get() == "Custom Range": 
                custom_date_f.pack(side="right", before=date_cb)
                lbl_filter.config(text="Custom:")
            else: 
                custom_date_f.pack_forget()
                lbl_filter.config(text="Filter:")
            current_page[0] = 1
            load_payments()
            
        date_cb.bind("<<ComboboxSelected>>", toggle_custom_date)
        custom_date_f.pack_forget()

        # BULK TOOLBAR
        bulk_f = tk.Frame(header_f, bg=self.colors["card"], pady=10, padx=10)
        tk.Label(bulk_f, text="Bulk Export Mode Active", font=("Arial", 11, "bold"), bg=self.colors["card"], fg=self.colors["accent_blue"]).pack(side="left", padx=(5, 15))
        
        btn_select_all = tk.Button(bulk_f, text="☑ Select All (0)", font=("Arial", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: toggle_select_all())
        btn_select_all.pack(side="left", padx=(0, 10))
        
        tk.Button(bulk_f, text="✖ Cancel", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=lambda: toggle_bulk_mode()).pack(side="right", padx=10)
        tk.Button(bulk_f, text="🖨️ Export PDF", font=("Arial", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_pdf(selected_only=True)).pack(side="right", padx=(5, 10))
        tk.Button(bulk_f, text="⭳ Export CSV", font=("Arial", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_csv(selected_only=True)).pack(side="right", padx=0)

        def toggle_bulk_mode(initial_id=None):
            if is_bulk_mode[0]:
                is_bulk_mode[0] = False
                selected_items.clear()
                bulk_f.pack_forget()
                inner_f.pack(fill="x")
                p_tree.heading("sno_sel", text="S.NO")
                load_payments()
            else:
                is_bulk_mode[0] = True
                selected_items.clear()
                if initial_id: selected_items.add(str(initial_id))
                inner_f.pack_forget()
                bulk_f.pack(fill="x")
                p_tree.heading("sno_sel", text="☑")
                update_bulk_btns()
                load_payments()

        def update_bulk_btns():
            btn_select_all.config(text=f"☑ Select All ({len(selected_items)})")

        def toggle_select_all():
            visible_ids = [str(iid) for iid in p_tree.get_children() if 'month_header' not in p_tree.item(iid, 'tags') and 'empty' not in p_tree.item(iid, 'tags')]
            if not visible_ids: return
            if all(iid in selected_items for iid in visible_ids):
                for iid in visible_ids: selected_items.remove(iid)
                p_tree.heading("sno_sel", text="[ ]")
            else:
                for iid in visible_ids: selected_items.add(iid)
                p_tree.heading("sno_sel", text="[✓]")
            update_bulk_btns()
            load_payments()

        # TABLE
        table_f = tk.Frame(pop, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="Inv.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="Inv.Horizontal.TScrollbar")
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        
        cols = ("sno_sel", "date", "party", "ref", "mode", "notes", "amount", "ghost")
        p_tree = ttk.Treeview(table_f, columns=cols, show="headings", height=15, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Purch.Treeview")
        p_tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=p_tree.yview)
        scroll_x.config(command=p_tree.xview)

        p_tree.heading("sno_sel", text="S.NO", anchor="center")
        p_tree.heading("date", text="DATE", anchor="center")
        p_tree.heading("party", text="VENDOR NAME", anchor="w")
        p_tree.heading("ref", text="REFERENCE", anchor="w")
        p_tree.heading("mode", text="PAYMENT MODE", anchor="center")
        p_tree.heading("notes", text="NOTES", anchor="w")
        p_tree.heading("amount", text="AMOUNT", anchor="e")
        p_tree.heading("ghost", text="")

        p_tree.column("sno_sel", width=60, minwidth=30, anchor="center", stretch=False)
        p_tree.column("date", width=120, minwidth=80, anchor="center", stretch=False)
        p_tree.column("party", width=250, minwidth=150, anchor="w", stretch=False)
        p_tree.column("ref", width=200, minwidth=150, anchor="w", stretch=False)
        p_tree.column("mode", width=150, minwidth=100, anchor="center", stretch=False)
        p_tree.column("notes", width=200, minwidth=150, anchor="w", stretch=True)
        p_tree.column("amount", width=120, minwidth=100, anchor="e", stretch=False)
        p_tree.column("ghost", width=10, minwidth=10, stretch=True)

        p_tree.tag_configure("even", background=self.colors["stripe_even"], foreground=self.colors["text"])
        p_tree.tag_configure("odd", background=self.colors["stripe_odd"], foreground=self.colors["text"])
        p_tree.tag_configure("month_header", background=self.colors["border"], foreground=self.colors["text"], font=("Arial", 10, "bold"))
        p_tree.tag_configure("normal_text", foreground=self.colors["text"], font=("Arial", 10))
        
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y": p_tree.yview_moveto(p_tree.yview()[0] + (delta * 0.008))
            else: p_tree.xview_moveto(p_tree.xview()[0] + (delta * 0.02))

        p_tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        p_tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        def on_tree_click(event):
            region = p_tree.identify("region", event.x, event.y)
            if region == "heading" and is_bulk_mode[0] and p_tree.identify_column(event.x) == "#1":
                toggle_select_all()
                return
            if region == "cell":
                iid = p_tree.identify_row(event.y)
                if not iid or 'month_header' in p_tree.item(iid, 'tags') or 'empty' in p_tree.item(iid, 'tags'): return
                if is_bulk_mode[0]:
                    if str(iid) in selected_items: selected_items.remove(str(iid))
                    else: selected_items.add(str(iid))
                    update_bulk_btns()
                    load_payments()

        p_tree.bind("<ButtonRelease-1>", on_tree_click)

        def delete_single_payment(pid):
            # --- THE FIX: Clean UI pre-check for Past Payment Deletions ---
            curr_role = getattr(self.app, "current_role", "Admin")
            curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
            
            if curr_role != "Admin" and str(curr_uid) != "1":
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("SELECT pay_date FROM party_payments WHERE id=?", (pid,))
                row = c.fetchone()
                conn.close()
                
                if row:
                    p_date = str(row[0]).strip()
                    today_date = date.today()
                    pay_dt = None
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            pay_dt = datetime.strptime(p_date[:10], fmt).date()
                            break
                        except Exception: pass
                    
                    if pay_dt and pay_dt != today_date:
                        perms = database.get_user_permissions(curr_uid)
                        p_rules = perms.get("purchase_rules", {})
                        i_rules = perms.get("invoice_rules", {})
                        pt_rules = perms.get("party_rules", {})
                        if p_rules.get("lock_past_payments", False) or i_rules.get("lock_past_payments", False) or pt_rules.get("lock_past_payments", False):
                            messagebox.showerror("Access Denied", f"This payment is from a previous date ({p_date}).\n\nDeleting past days' payment entries is locked for your account.\n\nPlease contact the Admin.", parent=pop)
                            return
            # --------------------------------------------------------------

            if not messagebox.askyesno("Confirm Delete", "Permanently delete this payment record?\n\nThis will reverse the amount from the bill balance and/or Advance Wallet.", parent=pop):
                return
            try:
                # --- THE FIX: Route directly to the master database engine to prevent isolated logic failure! ---
                database.delete_party_payment(pid, self.comp_id)
                
                load_payments()
                if hasattr(self, 'load_data'): self.load_data()
            except ValueError as ve:
                messagebox.showerror("Access Denied", str(ve), parent=pop)
            except Exception as e:
                messagebox.showerror("Database Error", str(e), parent=pop)

        ctx_menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=self.colors["card"], fg=self.colors["text"])
        def show_ctx_menu(event):
            if is_bulk_mode[0]: return
            iid = p_tree.identify_row(event.y)
            if iid and not str(iid).startswith("month_") and not str(iid).startswith("empty_"):
                if iid not in p_tree.selection(): p_tree.selection_set(iid)
                ctx_menu.delete(0, "end")
                ctx_menu.add_command(label="⭳ Export Record (CSV)", command=lambda: export_recent_csv(selected_only=True, override_id=iid))
                ctx_menu.add_command(label="🖨️ Export Record (PDF)", command=lambda: export_recent_pdf(selected_only=True, override_id=iid))
                ctx_menu.add_separator()
                ctx_menu.add_command(label="📄 Bulk Export", command=lambda: toggle_bulk_mode(initial_id=iid))
                ctx_menu.add_separator()
                ctx_menu.add_command(label="❌ Delete Record", foreground=self.colors["error"], command=lambda: delete_single_payment(iid))
                ctx_menu.tk_popup(event.x_root, event.y_root)
        p_tree.bind("<Button-3>", show_ctx_menu)

        pag_frame = tk.Frame(pop, bg=self.colors["bg"])
        pag_frame.pack(side="bottom", fill="x", pady=(5, 15))
        center_pag = tk.Frame(pag_frame, bg=self.colors["bg"])
        center_pag.pack(anchor="center") 
        
        btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=10, pady=2)
        btn_prev.pack(side="left", padx=5)
        lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 9, "bold"), bg=self.colors["bg"], fg=self.colors["text_sec"])
        lbl_page.pack(side="left", padx=15)
        btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=10, pady=2)
        btn_next.pack(side="left", padx=5)

        def load_payments(*args):
            for i in p_tree.get_children(): p_tree.delete(i)
            
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT id, pay_date, party_name, mode, ref, amount, notes, pay_type FROM party_payments WHERE company_id=? AND pay_type IN ('make', 'receive') ORDER BY id DESC", (self.comp_id,))
            rows = c.fetchall()
            conn.close()

            search = search_var.get().lower()
            val = filter_var.get()
            today = date.today()
            from_dt, to_dt = None, None

            if val == "Today":
                from_dt = datetime.combine(today, datetime.min.time())
                to_dt = datetime.combine(today, datetime.max.time())
            elif val == "This Week":
                start = today - timedelta(days=today.weekday())
                from_dt = datetime.combine(start, datetime.min.time())
                to_dt = datetime.combine(today, datetime.max.time())
            elif val == "This Month":
                start = today.replace(day=1)
                from_dt = datetime.combine(start, datetime.min.time())
                to_dt = datetime.combine(today, datetime.max.time())
            elif val == "Last Month":
                first_this = today.replace(day=1)
                last_month_end = first_this - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                from_dt = datetime.combine(last_month_start, datetime.min.time())
                to_dt = datetime.combine(last_month_end, datetime.max.time())
            elif val == "Custom Range":
                from_str = from_var.get().strip()
                to_str = to_var.get().strip()
                if from_str:
                    try: from_dt = datetime.strptime(from_str, self.date_fmt_code)
                    except: pass
                if to_str:
                    try: to_dt = datetime.strptime(to_str, self.date_fmt_code)
                    except: pass

            filtered_rows.clear()
            
            parsed_rows = []
            for r in rows:
                p_id, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                
                # --- THE FIX: Smart Filter to Ignore Client Transactions ---
                ref_lower = str(p_ref).lower()
                if p_type == 'make' and 'refunded to customer' in ref_lower:
                    continue
                if p_type == 'receive' and 'refunded from vendor' not in ref_lower and 'offset' not in ref_lower:
                    continue
                # -----------------------------------------------------------
                
                dt = datetime.min
                for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(p_date, fmt)
                        break
                    except: pass
                parsed_rows.append((dt, r))
                
            parsed_rows.sort(key=lambda x: x[0], reverse=True)

            for dt, r in parsed_rows:
                p_id, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                if dt != datetime.min:
                    if from_dt and dt < from_dt: continue
                    if to_dt and dt > to_dt: continue
                
                if search:
                    amt_str = format_currency(abs(p_amt), self.curr_fmt)
                    full_text = f"{p_party} {p_mode} {p_ref} {p_notes} {amt_str}".lower()
                    if search not in full_text: continue
                    
                filtered_rows.append((dt, r))

            total_pages = max(1, (len(filtered_rows) + items_per_page - 1) // items_per_page)
            if current_page[0] > total_pages: current_page[0] = max(1, total_pages)
            
            start_idx = (current_page[0] - 1) * items_per_page
            page_items = filtered_rows[start_idx : start_idx + items_per_page]

            lbl_page.config(text=f"Page {current_page[0]} of {total_pages}")
            btn_prev.config(state="normal" if current_page[0] > 1 else "disabled", bg=self.colors["card"] if current_page[0] > 1 else self.colors["bg"])
            btn_next.config(state="normal" if current_page[0] < total_pages else "disabled", bg=self.colors["card"] if current_page[0] < total_pages else self.colors["bg"])

            current_month_group = ""
            row_counter = 0

            for index, (dt, r) in enumerate(page_items):
                p_id, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                
                m_group = dt.strftime("%B, %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                if m_group != current_month_group:
                    current_month_group = m_group
                    bg_tag = "even" if row_counter % 2 == 0 else "odd"
                    p_tree.insert("", "end", iid=f"month_{m_group}_{index}", values=("", f"📅  {m_group}", "", "", "", "", ""), tags=(bg_tag, "month_header"))
                    row_counter += 1
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                if p_type == 'receive':
                    amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)} (Refund)"
                elif p_amt < 0:
                    amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                else:
                    amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                    
                tag = "even" if row_counter % 2 == 0 else "odd"
                
                col1 = ("☑" if str(p_id) in selected_items else "☐") if is_bulk_mode[0] else (start_idx + index + 1)
                if is_bulk_mode[0] and str(p_id) in selected_items:
                    tag_tup = ("selected_row",)
                    p_tree.tag_configure("selected_row", background=self.colors["bulk_select"], foreground="#ffffff")
                else:
                    tag_tup = (tag, "normal_text")
                    
                p_tree.insert("", "end", iid=str(p_id), values=(col1, fmt_date, p_party, p_ref, p_mode, p_notes, amt_str, ""), tags=tag_tup)
                row_counter += 1
                
            for i in range(row_counter, items_per_page + 2):
                tag = "even" if i % 2 == 0 else "odd"
                p_tree.insert("", "end", iid=f"empty_{i}", values=("", "", "", "", "", "", "", ""), tags=(tag, "empty"))

        def page_prev():
            if current_page[0] > 1: current_page[0] -= 1; load_payments()
        def page_next():
            total_pages = max(1, (len(filtered_rows) + items_per_page - 1) // items_per_page)
            if current_page[0] < total_pages: current_page[0] += 1; load_payments()
            
        btn_prev.config(command=page_prev)
        btn_next.config(command=page_next)

        search_var.trace_add("write", lambda *a: [current_page.__setitem__(0, 1), load_payments()])
        from_var.trace_add("write", lambda *a: [current_page.__setitem__(0, 1), load_payments()])
        to_var.trace_add("write", lambda *a: [current_page.__setitem__(0, 1), load_payments()])

        def get_export_data(selected_only=False, override_id=None):
            data = []
            sno = 1
            current_month = ""
            
            sel_ids = []
            if selected_only:
                if override_id: sel_ids = [str(override_id)]
                else: sel_ids = list(selected_items)
            
            for dt, r in filtered_rows:
                p_id = str(r[0])
                if selected_only and p_id not in sel_ids:
                    continue
                
                _, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                
                m_group = dt.strftime("%B %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                if m_group != current_month:
                    current_month = m_group
                    data.append(["", f"--- {current_month} ---", "", "", "", "", ""]) 
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                if p_type == 'receive':
                    amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)} (Refund)"
                elif p_amt < 0:
                    amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                else:
                    amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                    
                data.append([str(sno), fmt_date, p_party, p_ref, p_mode, p_notes, amt_str])
                sno += 1
            return data

        def export_recent_csv(selected_only=False, override_id=None):
            data = get_export_data(selected_only, override_id)
            if not data:
                messagebox.showinfo("Empty", "No data to export.", parent=pop)
                return
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Export Payments CSV", parent=pop)
            if not file_path: return
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow(["S.NO", "Date", "Vendor Name", "Reference", "Mode", "Notes", "Amount"]) 
                    writer.writerows(data)
                messagebox.showinfo("Export Successful", f"Payments exported to:\n{file_path}", parent=pop)
            except Exception as e: messagebox.showerror("Export Failed", str(e), parent=pop)

        def export_recent_pdf(selected_only=False, override_id=None):
            data = get_export_data(selected_only, override_id)
            if not data:
                messagebox.showinfo("Empty", "No data to export.", parent=pop)
                return
            html_content = f"""
            <html>
            <head><meta charset="utf-8"><title>Payments Export</title>
            <style>
                @media print {{ @page {{ margin: 0; size: landscape; }} body {{ margin: 1.5cm; }} }}
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                th, td {{ padding: 8px 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
                th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                .month-header td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; text-decoration: underline; border-bottom: 1px solid #cbd5e1; color: #1e293b; }}
            </style>
            </head>
            <body><h2>Recent Vendor Payments</h2>
            <table><thead><tr><th style="width:5%">S.NO</th><th style="width:12%">Date</th><th style="width:20%">Vendor Name</th><th style="width:20%">Reference</th><th style="width:15%">Mode</th><th style="width:15%">Notes</th><th style="width:13%; text-align:right;">Amount</th></tr></thead><tbody>
            """
            for r in data:
                if r[0] == "":
                    html_content += f'<tr class="month-header"><td colspan="7">{r[1]}</td></tr>'
                else:
                    html_content += f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td style="text-align:right;">{r[6]}</td></tr>'
            html_content += "</tbody></table><script>window.onload=function(){window.print();}</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="Purchase_Payment_Hist_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
            webbrowser.open('file://' + os.path.realpath(path))

        # The redundant global focus listener has been stripped out to prevent memory leaks.
        # Focus dropping is now handled universally by main.py
        
        load_payments()
    # ----------------------------------------------------