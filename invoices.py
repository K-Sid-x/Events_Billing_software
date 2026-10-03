import tkinter as tk
from tkinter import ttk, messagebox
import database
import json
import os
import sys
import re
from datetime import datetime, date, timedelta

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if current_dir not in sys.path: sys.path.append(current_dir)
if parent_dir not in sys.path: sys.path.append(parent_dir)
# -----------------------------------------------

# --- NEW: Import Universal Theme Engine ---
from views.home_parts.ui_components import get_theme

from views.invoice_parts.payment_portal import open_payment_portal
from views.invoice_parts.new_invoice_dialog import open_new_invoice
from views.invoice_parts.helpers import add_hover, enable_copy_paste, format_currency, fetch_global_settings, smart_date_formatter

from views.invoice_parts.invoice_actions import show_preview_from_db, export_to_csv, export_to_pdf
from views.invoice_parts.recycle_bin import open_recycle_bin

class InvoicesView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = self.winfo_toplevel()
        
        self.bulk_mode = False
        self.bulk_selection = set()
        self.active_filter = "All"
        self.active_filter_card = None
        self.stat_cards = {}
        
        self.undo_stack = []
        self.redo_stack = []
        
        # --- THE FIX: Route Colors through the Universal Theme Engine ---
        t = get_theme()
        self.BG = t["bg"]; self.CARD = t["card"]; self.BORDER = t["border"]
        self.FG = t["text"]; self.SEC_FG = t["sec"]; self.BTN_HOVER = t["btn_hover"]
        self.BLUE = t["accent_blue"]; self.STRIPE_EVEN = t["stripe_even"]; self.STRIPE_ODD = t["stripe_odd"]
        self.RED = t["error"]; self.GREEN = t["accent_green"]; self.YELLOW = "#f59e0b"
        self.config(bg=self.BG)
        # ----------------------------------------------------------------

        self.comp_id = getattr(self.app, "active_company_id", 1)
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT gst_toggle FROM company WHERE id=?", (self.comp_id,))
            row = c.fetchone()
            self.has_gst = (row[0] == 1) if row else False
            conn.close()
        except:
            self.has_gst = True
            
        style = ttk.Style(self)
        style.theme_use("default")
        
        # --- THE FIX: Thick Solid Scrollbar Styles! ---
        style.configure("Inv.Vertical.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.configure("Inv.Horizontal.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.map("Inv.Vertical.TScrollbar", background=[("active", self.BLUE)])
        style.map("Inv.Horizontal.TScrollbar", background=[("active", self.BLUE)])
        # ----------------------------------------------
        
        self.app.option_add("*TCombobox*Listbox.background", self.CARD)
        self.app.option_add("*TCombobox*Listbox.foreground", self.FG)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("Theme.TCombobox", fieldbackground=self.CARD, background=self.CARD, foreground=self.FG, arrowcolor=self.FG, bordercolor=self.BORDER, lightcolor=self.BORDER, darkcolor=self.BORDER)
        style.map("Theme.TCombobox", fieldbackground=[("readonly", self.CARD)], selectbackground=[("readonly", self.CARD)], selectforeground=[("readonly", self.FG)])
        
        style.configure("Theme.Treeview.Heading", font=("Arial", 10, "bold"), background=self.CARD, foreground=self.FG, borderwidth=1, relief="solid", bordercolor=self.BORDER)
        style.map("Theme.Treeview.Heading", background=[("active", self.BORDER)])
        style.configure("Theme.Treeview", font=("Arial", 11), rowheight=38, background=self.CARD, fieldbackground=self.CARD, foreground=self.FG, borderwidth=0)
        style.map("Theme.Treeview", background=[("selected", self.BLUE)], foreground=[("selected", "#ffffff")])

        def on_bg_click(e):
            # 1. Safely ignore clicks if we are on a completely different tab
            if not self.winfo_exists() or not self.winfo_ismapped(): return
            
            # 2. Drop the blinking cursor if clicking on empty space
            try:
                w_class = e.widget.winfo_class()
                if w_class not in ('Entry', 'TCombobox', 'Text', 'Button', 'Treeview', 'Scrollbar'):
                    self.focus_set()
            except: pass
            
            # 3. Handle the filter resets
            try:
                if e.widget in (self, getattr(self, 'top_header', None), getattr(self, 'tiles_f', None), getattr(self, 'toolbar', None), getattr(self, 'table_frame', None), getattr(self, 'bulk_toolbar', None), getattr(self, 'pagination_frame', None)):
                    if self.active_filter != "All":
                        self.set_tile_filter("All", "TOTAL INVOICES")
            except: pass

        # Attach this universally so it catches clicks everywhere on this screen
        self.app.bind("<Button-1>", on_bg_click, add="+")
        
        self.top_header = tk.Frame(self, bg=self.BG)
        self.top_header.pack(fill="x", pady=(0, 15))
        self.top_header.bind("<Button-1>", on_bg_click)
        
        tk.Label(self.top_header, text="Invoices & Billing", font=("Arial", 20, "bold"), bg=self.BG, fg=self.FG).pack(side="left")
        
        add_btn = tk.Button(self.top_header, text="⊕ New Invoice", font=("Arial", 11, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=6, command=lambda: open_new_invoice(self))
        add_btn.pack(side="right")
        add_hover(add_btn, self.BLUE, "#2563eb")

        btn_group = tk.Frame(self.top_header, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        btn_group.pack(side="right", padx=(0, 15))

        self.undo_btn = tk.Button(btn_group, text="↺ Undo", font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=4, command=self.undo_last_delete)
        self.undo_btn.pack(side="left")

        tk.Frame(btn_group, width=1, bg=self.BORDER).pack(side="left", fill="y")

        self.redo_btn = tk.Button(btn_group, text="↻ Redo", font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=4, command=self.redo_last_undo)
        self.redo_btn.pack(side="left")

        self.stat_count_var = tk.StringVar(value="0")
        self.stat_billed_var = tk.StringVar(value="0.00")
        self.stat_paid_var = tk.StringVar(value="0")
        self.stat_unpaid_var = tk.StringVar(value="0")
        self.stat_draft_var = tk.StringVar(value="0") 
        self.stat_deleted_var = tk.StringVar(value="0")

        self.tiles_f = tk.Frame(self, bg=self.BG)
        self.tiles_f.pack(fill="x", pady=(0, 20))
        self.tiles_f.bind("<Button-1>", on_bg_click)
        
        self.create_stat_card(self.tiles_f, "TOTAL INVOICES", self.stat_count_var, self.FG, lambda: self.set_tile_filter("All", "TOTAL INVOICES")).pack(side="left", expand=True, fill="both", padx=(0, 10))
        self.create_stat_card(self.tiles_f, "BILLED", self.stat_billed_var, self.BLUE, lambda: self.set_tile_filter("All", "TOTAL INVOICES")).pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(self.tiles_f, "PAID INVOICES", self.stat_paid_var, self.GREEN, lambda: self.set_tile_filter("Paid", "PAID INVOICES")).pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(self.tiles_f, "UNPAID INVOICES", self.stat_unpaid_var, self.RED, lambda: self.set_tile_filter("Unpaid", "UNPAID INVOICES")).pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(self.tiles_f, "DRAFT INVOICES", self.stat_draft_var, "#f59e0b", lambda: self.open_drafts_popup()).pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(self.tiles_f, "DELETED INVOICES", self.stat_deleted_var, self.YELLOW, lambda: open_recycle_bin(self)).pack(side="left", expand=True, fill="both", padx=(10, 0))

        self.toolbar = tk.Frame(self, bg=self.BG)
        self.toolbar.pack(fill="x", pady=(0, 15))
        self.toolbar.bind("<Button-1>", on_bg_click)

        search_f = tk.Frame(self.toolbar, bg=self.BG)
        search_f.pack(side="left", padx=(0, 15))

        self.search_var = tk.StringVar()
        
        search_entry = tk.Entry(search_f, textvariable=self.search_var, font=("Arial", 11), width=32, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        search_entry.pack(side="left", ipady=3)
        search_entry.insert(0, "Search Customer or Invoice...")
        
        def clear_search_focus(event):
            if search_entry.get() == 'Search Customer or Invoice...': search_entry.delete('0', 'end')
                
        def restore_search_focus(event):
            if not search_entry.get().strip():
                search_entry.delete('0', 'end')
                search_entry.insert(0, "Search Customer or Invoice...")

        def force_clear_search():
            self.search_var.set("Search Customer or Invoice...")
            self.focus_set()
            self.current_page = 1
            self.load_data()

        btn_clear = tk.Button(search_f, text="✖", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.RED, relief="solid", bd=1, cursor="hand2", command=force_clear_search)
        btn_clear.pack(side="left", padx=(5, 0), ipady=3, ipadx=8)
        add_hover(btn_clear, self.CARD, self.BTN_HOVER)

        search_entry.bind("<FocusIn>", clear_search_focus)
        search_entry.bind("<FocusOut>", restore_search_focus)
        search_entry.bind("<KeyRelease>", self.load_data)
        enable_copy_paste(search_entry)

        tk.Label(self.toolbar, text="Period:", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).pack(side="left")
        self.period_var = tk.StringVar(value="All Time")
        period_combo = ttk.Combobox(self.toolbar, textvariable=self.period_var, values=["This Month", "This Financial Year", "All Time"], state="readonly", width=16, style="Theme.TCombobox", cursor="hand2")
        period_combo.pack(side="left", padx=(5, 15), ipady=3)
        period_combo.bind("<<ComboboxSelected>>", self.load_data)

        tk.Label(self.toolbar, text="Sort By:", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).pack(side="left", padx=(0, 5))
        # --- THE FIX: Default Sort by Date for Non-GST, Invoice No for GST ---
        default_sort = "Invoice No (High to Low)" if self.has_gst else "Date Wise"
        self.sort_var = tk.StringVar(value=default_sort)
        # ---------------------------------------------------------------------
        sort_combo = ttk.Combobox(self.toolbar, textvariable=self.sort_var, values=["Date Wise", "Invoice No (Low to High)", "Invoice No (High to Low)", "A to Z", "Z to A"], state="readonly", width=22, style="Theme.TCombobox", cursor="hand2")
        sort_combo.pack(side="left", ipady=3)
        sort_combo.bind("<<ComboboxSelected>>", self.load_data)

        btn_export_pdf = tk.Button(self.toolbar, text="🖨 Export PDF", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="solid", bd=1, cursor="hand2", command=lambda: export_to_pdf(self))
        btn_export_pdf.pack(side="right", padx=(10, 0), ipady=3, ipadx=5)
        add_hover(btn_export_pdf, self.CARD, self.BTN_HOVER)

        btn_export_csv = tk.Button(self.toolbar, text="📥 Export CSV", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="solid", bd=1, cursor="hand2", command=lambda: export_to_csv(self))
        btn_export_csv.pack(side="right", padx=(0, 0), ipady=3, ipadx=5)
        add_hover(btn_export_csv, self.CARD, self.BTN_HOVER)

        # --- THE FIX: Recent Payments Dashboard Button! ---
        self.btn_recent_pays = tk.Button(self.toolbar, text="💸 Recent Payments", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="solid", bd=1, cursor="hand2", command=self.open_recent_payments)
        self.btn_recent_pays.pack(side="right", padx=(10, 10), ipady=3, ipadx=5)
        add_hover(self.btn_recent_pays, self.CARD, self.BTN_HOVER)
        # --------------------------------------------------

        # --- THE FIX: Leave the frame empty so toggle_bulk_mode can dynamically populate it ---
        self.bulk_toolbar = tk.Frame(self, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, pady=10, padx=10)

        self.table_frame = tk.Frame(self, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        self.table_frame.pack(fill="both", expand=True)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.rowconfigure(0, weight=1)
        self.table_frame.bind("<Button-1>", on_bg_click)

        # --- THE FIX: Apply the isolated thick scrollbar styles ---
        tree_scroll_y = ttk.Scrollbar(self.table_frame, orient="vertical", style="Inv.Vertical.TScrollbar")
        tree_scroll_x = ttk.Scrollbar(self.table_frame, orient="horizontal", style="Inv.Horizontal.TScrollbar")
        # ----------------------------------------------------------

        # --- THE FIX: Inserted Ghost Column into the Main Grid! ---
        columns = ("sl_no", "date", "inv_num", "customer", "subtotal", "gst", "total", "tds", "status", "ghost")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings", height=15, style="Theme.Treeview", yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        
        self.tree.heading("sl_no", text="SL. NO.", anchor="center")
        self.tree.heading("date", text="DATE", anchor="w")
        self.tree.heading("inv_num", text="INVOICE NO.", anchor="w")
        self.tree.heading("customer", text="CUSTOMER", anchor="w")
        self.tree.heading("subtotal", text="SUBTOTAL", anchor="e")
        self.tree.heading("gst", text="GST", anchor="e")
        self.tree.heading("total", text="TOTAL", anchor="e")
        self.tree.heading("tds", text="TDS", anchor="e")
        self.tree.heading("status", text="STATUS", anchor="center")
        self.tree.heading("ghost", text="")

        try:
            raw_setting = database.get_ui_setting("inv_main_cols", "{}")
            w_dict = json.loads(raw_setting) if raw_setting else {}
        except:
            w_dict = {}

        self.tree.column("sl_no", width=w_dict.get("sl_no", 60), minwidth=60, anchor="center", stretch=False)
        self.tree.column("date", width=w_dict.get("date", 90), minwidth=90, anchor="w", stretch=False)
        self.tree.column("inv_num", width=w_dict.get("inv_num", 130), minwidth=130, anchor="w", stretch=False)
        self.tree.column("customer", width=w_dict.get("customer", 180), minwidth=130, anchor="w", stretch=False)
        self.tree.column("subtotal", width=w_dict.get("subtotal", 90), minwidth=90, anchor="e", stretch=False)
        self.tree.column("gst", width=w_dict.get("gst", 80), minwidth=80, anchor="e", stretch=False)
        self.tree.column("total", width=w_dict.get("total", 100), minwidth=100, anchor="e", stretch=False)
        self.tree.column("tds", width=w_dict.get("tds", 80), minwidth=80, anchor="e", stretch=False)
        self.tree.column("status", width=w_dict.get("status", 100), minwidth=100, anchor="center", stretch=False)
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)

        if not self.has_gst:
            self.tree["displaycolumns"] = ("sl_no", "date", "inv_num", "customer", "total", "tds", "status", "ghost")
        # -----------------------------------------------------------

        def save_main_widths():
            # --- THE FIX: Since 'customer' is no longer stretching, we MUST save its width! ---
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c != "ghost"}
            # --------------------------------------------------------------
            try: database.save_ui_setting("inv_main_cols", json.dumps(new_w))
            except: pass

        def on_main_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_main_widths)

        self.tree.bind("<B1-Motion>", on_main_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: [self.after(50, save_main_widths), self.on_left_click(e)])
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Motion>", self.on_mouse_motion)
        
        def prevent_dummy_select(event):
            for iid in self.tree.selection():
                if 'dummy' in self.tree.item(iid, 'tags'):
                    self.tree.selection_remove(iid)
        self.tree.bind("<<TreeviewSelect>>", prevent_dummy_select)

        # --- THE FIX: Subject Tooltip Setup ---
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry("+0+0")
        self.tooltip.configure(bg="#fef08a", highlightbackground="#ca8a04", highlightthickness=1)
        self.tooltip_lbl = tk.Label(self.tooltip, text="", font=("Arial", 10, "bold"), bg="#fef08a", fg="#854d0e", justify="left", wraplength=400)
        self.tooltip_lbl.pack(padx=8, pady=4)
        self.tooltip.withdraw()
        
        self.tree.bind("<Leave>", lambda e: self.tooltip.withdraw(), add="+")
        # --------------------------------------

        # --- THE FIX: Buttery Smooth X/Y Scrolling ---
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                self.tree.yview_moveto(self.tree.yview()[0] + (delta * 0.008))
            else:
                self.tree.xview_moveto(self.tree.xview()[0] + (delta * 0.02))

        self.tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        self.tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))
        # ---------------------------------------------

        # --- THE FIX: ADDING PAGINATION UI & STATE ---
        self.current_page = 1
        self.items_per_page = 50
        self.total_pages = 1

        self.pagination_frame = tk.Frame(self, bg=self.BG)
        
        # --- THE FIX: Anchor pagination to the bottom, then force table to shrink ---
        self.pagination_frame.pack(side="bottom", fill="x", pady=(5, 10))
        self.table_frame.pack_forget()
        self.table_frame.pack(side="top", fill="both", expand=True)
        # ----------------------------------------------------------------------------
        
        self.pagination_frame.bind("<Button-1>", on_bg_click)
        
        self.btn_prev = tk.Button(self.pagination_frame, text="< Previous", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG, relief="flat", cursor="hand2", command=self.prev_page)
        self.btn_prev.pack(side="left", expand=True, anchor="e", padx=10)
        
        self.lbl_page = tk.Label(self.pagination_frame, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=self.BG, fg=self.FG)
        self.lbl_page.pack(side="left", expand=False, anchor="center")
        
        self.btn_next = tk.Button(self.pagination_frame, text="Next >", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="solid", bd=1, cursor="hand2", command=self.next_page, padx=10, pady=3)
        self.btn_next.pack(side="left", expand=True, anchor="w", padx=10)
        # ---------------------------------------------
        
        for container in (self.top_header, self.toolbar):
            for child in container.winfo_children():
                if getattr(child, 'winfo_class', lambda: '')() == 'Label':
                    child.bind("<Button-1>", on_bg_click)
        
        self.set_tile_filter("All", "TOTAL INVOICES")

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    # --- THE FIX: Smart Recent Payments Modal (Bulk Export + Reverse Deletion logic) ---
    def open_recent_payments(self):
        from views.invoice_parts.calendar_widget import NativeCalendar
        import csv
        import tempfile
        import webbrowser
        from datetime import datetime, timedelta, date

        pop = tk.Toplevel(self.app)
        pop.title("Recent Payments Received")
        pop.geometry("1100x700")
        pop.configure(bg=self.BG)
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
        header_f = tk.Frame(pop, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        header_f.pack(fill="x", padx=20, pady=(20, 10))
        
        inner_f = tk.Frame(header_f, bg=self.CARD, pady=10, padx=10)
        inner_f.pack(fill="x")
        
        tk.Label(inner_f, text="💸 Recent Payments (Incoming)", font=("Arial", 14, "bold"), bg=self.CARD, fg=self.FG).pack(side="left", padx=(5, 15))
        
        tk.Label(inner_f, text="🔍 Search:", bg=self.CARD, font=("Arial", 9, "bold"), fg=self.SEC_FG).pack(side="left", padx=(5, 5))
        tk.Entry(inner_f, textvariable=search_var, font=("Arial", 10), width=25, bg=self.BG, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1).pack(side="left", ipady=3)
        
        btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.RED, relief="flat", cursor="hand2", command=lambda: search_var.set(""))
        btn_clear_search.pack(side="left", padx=(5, 5))
        
        btn_export = tk.Button(inner_f, text="📥 Export ▼", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="solid", highlightbackground=self.BORDER, bd=1, cursor="hand2", padx=8, pady=2)
        btn_export.pack(side="right", padx=(10, 5))
        
        export_menu = tk.Menu(btn_export, tearoff=0, font=("Arial", 10), bg=self.CARD, fg=self.FG, activebackground=self.BLUE, activeforeground="#ffffff")
        export_menu.add_command(label="⭳ Export as CSV", command=lambda: export_recent_csv())
        export_menu.add_command(label="🖨️ Export as PDF", command=lambda: export_recent_pdf())
        btn_export.config(command=lambda: export_menu.tk_popup(btn_export.winfo_rootx(), btn_export.winfo_rooty() + btn_export.winfo_height()))

        def trigger_clear_filter():
            from_var.set("")
            to_var.set("")
            filter_var.set("All Time")
            toggle_custom_date()
        
        btn_clear = tk.Button(inner_f, text="✖", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.RED, relief="flat", cursor="hand2", command=trigger_clear_filter)
        btn_clear.pack(side="right", padx=(5, 5))
        
        custom_date_f = tk.Frame(inner_f, bg=self.CARD)
        
        to_f = tk.Frame(custom_date_f, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
        to_f.pack(side="right", padx=(5, 0))
        to_btn = tk.Button(to_f, text="▼", bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2")
        to_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(to_f, textvariable=to_var, font=("Arial", 10), width=10, bg=self.BG, fg=self.FG, bd=0, insertbackground=self.FG).pack(side="left", ipady=4, padx=5)
        to_btn.config(command=lambda b=to_btn: NativeCalendar(pop, to_var, anchor_widget=b))
        tk.Label(custom_date_f, text="To:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(side="right", padx=(10, 0))
        
        from_f = tk.Frame(custom_date_f, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
        from_f.pack(side="right", padx=(5, 0))
        from_btn = tk.Button(from_f, text="▼", bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2")
        from_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(from_f, textvariable=from_var, font=("Arial", 10), width=10, bg=self.BG, fg=self.FG, bd=0, insertbackground=self.FG).pack(side="left", ipady=4, padx=5)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(pop, from_var, anchor_widget=b))
        tk.Label(custom_date_f, text="📅 From:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(side="right", padx=(10, 0))
        
        date_cb = ttk.Combobox(inner_f, textvariable=filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=12, font=("Arial", 10), cursor="hand2", style="Theme.TCombobox")
        date_cb.pack(side="right", padx=(5, 0))
        
        lbl_filter = tk.Label(inner_f, text="Filter:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG)
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
        bulk_f = tk.Frame(header_f, bg=self.CARD, pady=10, padx=10)
        tk.Label(bulk_f, text="Bulk Export Mode Active", font=("Arial", 11, "bold"), bg=self.CARD, fg=self.BLUE).pack(side="left", padx=(5, 15))
        
        btn_select_all = tk.Button(bulk_f, text="☑ Select All (0)", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: toggle_select_all())
        btn_select_all.pack(side="left", padx=(0, 10))
        
        tk.Button(bulk_f, text="✖ Cancel", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.RED, relief="flat", cursor="hand2", command=lambda: toggle_bulk_mode()).pack(side="right", padx=10)
        tk.Button(bulk_f, text="🖨️ Export PDF", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_pdf(selected_only=True)).pack(side="right", padx=(5, 10))
        tk.Button(bulk_f, text="⭳ Export CSV", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_csv(selected_only=True)).pack(side="right", padx=0)

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
                p_tree.heading("sno_sel", text="[ ✔ ]")
                update_bulk_btns()
                load_payments()

        def update_bulk_btns():
            btn_select_all.config(text=f"☑ Select All ({len(selected_items)})")

        def toggle_select_all():
            visible_ids = [str(iid) for iid in p_tree.get_children() if 'month_header' not in p_tree.item(iid, 'tags') and 'empty' not in p_tree.item(iid, 'tags')]
            if not visible_ids: return
            if all(iid in selected_items for iid in visible_ids):
                for iid in visible_ids: selected_items.remove(iid)
                p_tree.heading("sno_sel", text="[    ]")
            else:
                for iid in visible_ids: selected_items.add(iid)
                p_tree.heading("sno_sel", text="[ ✔ ]")
            update_bulk_btns()
            load_payments()

        # TABLE
        table_f = tk.Frame(pop, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="Inv.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="Inv.Horizontal.TScrollbar")
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        
        cols = ("sno_sel", "date", "party", "ref", "mode", "notes", "amount", "ghost")
        p_tree = ttk.Treeview(table_f, columns=cols, show="headings", height=15, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Theme.Treeview")
        p_tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=p_tree.yview)
        scroll_x.config(command=p_tree.xview)

        p_tree.heading("sno_sel", text="S.NO", anchor="center")
        p_tree.heading("date", text="DATE", anchor="center")
        p_tree.heading("party", text="CUSTOMER", anchor="w")
        p_tree.heading("ref", text="REFERENCE", anchor="w")
        p_tree.heading("mode", text="PAYMENT MODE", anchor="center")
        p_tree.heading("notes", text="NOTES", anchor="w")
        p_tree.heading("amount", text="AMOUNT", anchor="e")
        p_tree.heading("ghost", text="")

        try:
            raw_setting = database.get_ui_setting("inv_recent_cols", "{}")
            r_w = json.loads(raw_setting) if raw_setting else {}
        except:
            r_w = {}

        p_tree.column("sno_sel", width=r_w.get("sno_sel", 50), minwidth=30, anchor="center", stretch=False)
        p_tree.column("date", width=r_w.get("date", 120), minwidth=80, anchor="center", stretch=False)
        p_tree.column("party", width=r_w.get("party", 250), minwidth=150, anchor="w", stretch=False)
        p_tree.column("ref", width=r_w.get("ref", 200), minwidth=150, anchor="w", stretch=False)
        p_tree.column("mode", width=r_w.get("mode", 150), minwidth=100, anchor="center", stretch=False)
        p_tree.column("notes", width=r_w.get("notes", 200), minwidth=150, anchor="w", stretch=False)
        p_tree.column("amount", width=r_w.get("amount", 120), minwidth=100, anchor="e", stretch=False)
        p_tree.column("ghost", width=10, minwidth=10, stretch=True)

        def save_recent_widths():
            new_w = {c: p_tree.column(c, "width") for c in p_tree["columns"] if c != "ghost"}
            try: database.save_ui_setting("inv_recent_cols", json.dumps(new_w))
            except: pass

        def on_recent_sep_drag(event):
            if p_tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_recent_widths)

        p_tree.bind("<B1-Motion>", on_recent_sep_drag, add="+")
        p_tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_recent_widths), add="+")

        p_tree.tag_configure("even", background=self.STRIPE_EVEN, foreground=self.FG)
        p_tree.tag_configure("odd", background=self.STRIPE_ODD, foreground=self.FG)
        p_tree.tag_configure("month_header", background=self.BORDER, foreground=self.FG, font=("Arial", 10, "bold"))
        p_tree.tag_configure("normal_text", foreground=self.FG, font=("Arial", 10))
        
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
                    vals = list(p_tree.item(iid, "values"))
                    
                    # Flip the checkbox but leave the colors completely alone
                    if str(iid) in selected_items:
                        selected_items.remove(str(iid))
                        vals[0] = "[    ]"
                        p_tree.item(iid, values=vals)
                    else:
                        selected_items.add(str(iid))
                        vals[0] = "[ ✔ ]"
                        p_tree.item(iid, values=vals)
                        
                    update_bulk_btns()

        def prevent_native_selection(event):
            if is_bulk_mode[0]:
                for iid in p_tree.selection(): p_tree.selection_remove(iid)
            else:
                for iid in p_tree.selection():
                    if 'month_header' in p_tree.item(iid, 'tags') or 'empty' in p_tree.item(iid, 'tags'):
                        p_tree.selection_remove(iid)

        p_tree.bind("<ButtonRelease-1>", on_tree_click)
        p_tree.bind("<<TreeviewSelect>>", prevent_native_selection)

        def on_recent_double_click(e):
            if is_bulk_mode[0]: return
            region = p_tree.identify("region", e.x, e.y)
            if region == "cell":
                iid = p_tree.identify_row(e.y)
                if iid and not str(iid).startswith("month_") and not str(iid).startswith("empty_"):
                    row_vals = p_tree.item(iid, "values")
                    ref_str = row_vals[3] # Ref is index 3 because index 0 is sno
                    
                    if "Advance" in ref_str or "Refund" in ref_str: return
                    first_bill = ref_str.split(" | ")[0].strip()
                    
                    conn = database.get_connection()
                    c = conn.cursor()
                    c.execute("SELECT id FROM invoices WHERE invoice_number=? AND company_id=?", (first_bill, self.comp_id))
                    res = c.fetchone()
                    conn.close()
                    
                    if res: show_preview_from_db(self, res[0])

        p_tree.bind("<Double-1>", on_recent_double_click)
        
        def on_recent_motion(e):
            region = p_tree.identify("region", e.x, e.y)
            if region == "heading" and is_bulk_mode[0] and p_tree.identify_column(e.x) == "#1":
                p_tree.config(cursor="hand2")
                return
            if region == "cell":
                if is_bulk_mode[0]:
                    p_tree.config(cursor="hand2")
                    return
                col = p_tree.identify_column(e.x)
                if col == "#4": # Ref column
                    iid = p_tree.identify_row(e.y)
                    if iid and not str(iid).startswith("month_") and not str(iid).startswith("empty_"):
                        ref_str = p_tree.item(iid, "values")[3]
                        if "Advance" not in ref_str and "Refund" not in ref_str:
                            p_tree.config(cursor="hand2")
                            return
            p_tree.config(cursor="")

        p_tree.bind("<Motion>", on_recent_motion)

        def delete_selected_payments():
            selected = p_tree.selection()
            valid_ids = [iid for iid in selected if not str(iid).startswith("month_") and not str(iid).startswith("empty_")]
            if not valid_ids: return
            
            conn = database.get_connection()
            c = conn.cursor()
            for pid in valid_ids:
                c.execute("SELECT ref FROM party_payments WHERE id=?", (pid,))
                ref_row = c.fetchone()
                if ref_row and ref_row[0]:
                    for part in ref_row[0].split(" | "):
                        b_num = part.split(" (")[0].strip()
                        c.execute("SELECT ca_submitted FROM invoices WHERE invoice_number=? AND company_id=?", (b_num, self.comp_id))
                        inv_row = c.fetchone()
                        if inv_row and inv_row[0] == 1:
                            messagebox.showwarning("Locked", f"Payment deletion blocked.\n\nThis payment is linked to Invoice {b_num}, which is already GST Filed.", parent=pop)
                            conn.close()
                            return
            conn.close()
            
            msg = "Are you sure you want to delete this payment record?\n\nThis will permanently reverse the payment, restoring the invoice's balance and adjusting the customer's advance wallet accordingly."
            if len(valid_ids) > 1:
                msg = f"Are you sure you want to bulk delete {len(valid_ids)} payment records?\n\nThis will permanently reverse the payments, restoring invoice balances and advance wallets accordingly."
                
            if not messagebox.askyesno("Confirm Delete", msg, parent=pop):
                return
                
            try:
                for pid in valid_ids:
                    conn_a = database.get_connection()
                    cur_a = conn_a.cursor()
                    cur_a.execute("SELECT party_name, ref, amount, mode FROM party_payments WHERE id=?", (pid,))
                    p_row = cur_a.fetchone()
                    conn_a.close()
                    database.delete_party_payment(pid, self.comp_id)
                    if p_row:
                        database.log_audit(
                            "Invoices", "Payment Deleted", p_row[1] or "Payment",
                            f"Reversed & deleted payment ({p_row[3]}) for {p_row[0]}",
                            abs(float(p_row[2] or 0.0)), company_id=self.comp_id
                        )
                    
                load_payments()
                if hasattr(self, 'load_data'): self.load_data()
            except Exception as e:
                messagebox.showerror("Database Error", str(e), parent=pop)

        ctx_menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=self.CARD, fg=self.FG, activebackground=self.BLUE, activeforeground="#ffffff")
        def show_ctx_menu(event):
            if is_bulk_mode[0]: return
            iid = p_tree.identify_row(event.y)
            if iid and not str(iid).startswith("month_") and not str(iid).startswith("empty_"):
                if iid not in p_tree.selection(): p_tree.selection_set(iid)
                ctx_menu.delete(0, "end")
                sel_count = len(p_tree.selection())
                
                if sel_count == 1:
                    ctx_menu.add_command(label="⭳ Export Record (CSV)", command=lambda: export_recent_csv(selected_only=True, override_id=iid))
                    ctx_menu.add_command(label="🖨️ Export Record (PDF)", command=lambda: export_recent_pdf(selected_only=True, override_id=iid))
                    ctx_menu.add_separator()
                    ctx_menu.add_command(label="📄 Bulk Select / Export", command=lambda: toggle_bulk_mode(initial_id=iid))
                    ctx_menu.add_separator()
                    ctx_menu.add_command(label="❌ Delete Record", foreground=self.RED, command=delete_selected_payments)
                else:
                    ctx_menu.add_command(label=f"⭳ Bulk Export {sel_count} Items (CSV)", command=lambda: export_recent_csv(selected_only=True))
                    ctx_menu.add_command(label=f"🖨️ Bulk Export {sel_count} Items (PDF)", command=lambda: export_recent_pdf(selected_only=True))
                    ctx_menu.add_separator()
                    ctx_menu.add_command(label=f"🗑 Bulk Delete {sel_count} Items", foreground=self.RED, command=delete_selected_payments)
                
                ctx_menu.tk_popup(event.x_root, event.y_root)
                
        p_tree.bind("<Button-3>", show_ctx_menu)

        pag_frame = tk.Frame(pop, bg=self.BG)
        pag_frame.pack(side="bottom", fill="x", pady=(5, 15))
        center_pag = tk.Frame(pag_frame, bg=self.BG)
        center_pag.pack(anchor="center") 
        
        btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=10, pady=2)
        btn_prev.pack(side="left", padx=5)
        lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG)
        lbl_page.pack(side="left", padx=15)
        btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=10, pady=2)
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
                
                ref_lower = str(p_ref).lower()
                if p_type == 'receive' and 'refunded from vendor' in ref_lower:
                    continue
                if p_type == 'make' and 'refunded to customer' not in ref_lower and 'offset' not in ref_lower:
                    continue
                
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
            btn_prev.config(state="normal" if current_page[0] > 1 else "disabled", bg=self.CARD if current_page[0] > 1 else self.BG)
            btn_next.config(state="normal" if current_page[0] < total_pages else "disabled", bg=self.CARD if current_page[0] < total_pages else self.BG)

            current_month_group = ""
            row_counter = 0

            for index, (dt, r) in enumerate(page_items):
                p_id, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                
                import re
                p_ref = re.sub(r'\s*\([^)]*\)', '', str(p_ref)).strip()
                
                m_group = dt.strftime("%B, %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                if m_group != current_month_group:
                    current_month_group = m_group
                    bg_tag = "even" if row_counter % 2 == 0 else "odd"
                    p_tree.insert("", "end", iid=f"month_{m_group}_{index}", values=("", f"📅  {m_group}", "", "", "", "", "", ""), tags=(bg_tag, "month_header"))
                    row_counter += 1
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                if p_type == 'make':
                    amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)} (Refund)"
                elif p_amt < 0:
                    amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                else:
                    amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                    
                tag = "even" if row_counter % 2 == 0 else "odd"
                
                # --- THE FIX: Wider, bolder checkboxes! ---
                col1 = ("[ ✔ ]" if str(p_id) in selected_items else "[    ]") if is_bulk_mode[0] else (start_idx + index + 1)
                tag_tup = (tag, "normal_text")
                # ------------------------------------------
                
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
                
                import re
                p_ref = re.sub(r'\s*\([^)]*\)', '', str(p_ref)).strip()
                
                m_group = dt.strftime("%B %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                if m_group != current_month:
                    current_month = m_group
                    data.append(["", f"--- {current_month} ---", "", "", "", "", ""]) 
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                if p_type == 'make':
                    amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)} (Refund)"
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
                    writer.writerow(["S.NO", "Date", "Customer Name", "Reference", "Mode", "Notes", "Amount"]) 
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
            <body><h2>Recent Customer Payments</h2>
            <table><thead><tr><th style="width:5%">S.NO</th><th style="width:12%">Date</th><th style="width:20%">Customer Name</th><th style="width:20%">Reference</th><th style="width:15%">Mode</th><th style="width:15%">Notes</th><th style="width:13%; text-align:right;">Amount</th></tr></thead><tbody>
            """
            for r in data:
                if r[0] == "":
                    html_content += f'<tr class="month-header"><td colspan="7">{r[1]}</td></tr>'
                else:
                    html_content += f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td style="text-align:right;">{r[6]}</td></tr>'
            html_content += "</tbody></table><script>window.onload=function(){window.print();}</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="Payment_Hist_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
            webbrowser.open('file://' + os.path.realpath(path))

        load_payments()
    # ----------------------------------------------------

    def update_memory_buttons(self):
        has_undo = bool(self.undo_stack)
        has_redo = bool(self.redo_stack)
        
        if has_undo:
            self.undo_btn.config(state="normal", bg=self.BLUE, fg="#ffffff", cursor="hand2")
        else:
            self.undo_btn.config(state="disabled", bg=self.BG, fg=self.BORDER, cursor="arrow")
            
        if has_redo:
            self.redo_btn.config(state="normal", bg=self.BLUE, fg="#ffffff", cursor="hand2")
        else:
            self.redo_btn.config(state="disabled", bg=self.BG, fg=self.BORDER, cursor="arrow")

    def undo_last_delete(self):
        if not self.undo_stack:
            messagebox.showinfo("Undo Unavailable", "There are no actions from this session to undo.", parent=self)
            return
            
        # --- THE FIX: Multi-Company Firewall Lock ---
        database.set_active_company(self.comp_id)
        # --------------------------------------------
        
        last_action = self.undo_stack.pop()
        self.redo_stack.append(last_action)
        
        action_type = last_action["type"]
        ids = last_action["ids"]
        refund_mode = last_action.get("refund_mode", "none")
        
        if action_type == "delete":
            for iid in ids:
                database.restore_invoice(iid)
                inv_r, _ = database.get_invoice_by_id(iid)
                if inv_r:
                    database.log_audit("Invoices", "Undo Delete", inv_r[3], f"Restored invoice for {inv_r[4]} via Undo", inv_r[10], company_id=self.comp_id)
            try:
                conn = database.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT invoice_number FROM invoices WHERE id=?", (ids[0],))
                row = cur.fetchone()
                conn.close()
                if row: self.app.pending_highlight = row[0]
            except: pass
        else:
            for iid in ids:
                database.soft_delete_invoice(iid, refund_mode)
            
        self.load_data()

    def redo_last_undo(self):
        if not self.redo_stack:
            messagebox.showinfo("Redo Unavailable", "There is no action to redo.", parent=self)
            return
            
        # --- THE FIX: Multi-Company Firewall Lock ---
        database.set_active_company(self.comp_id)
        # --------------------------------------------
            
        next_action = self.redo_stack.pop()
        self.undo_stack.append(next_action)
        
        action_type = next_action["type"]
        ids = next_action["ids"]
        refund_mode = next_action.get("refund_mode", "none")
        
        if action_type == "delete":
            for iid in ids:
                inv_r, _ = database.get_invoice_by_id(iid)
                database.soft_delete_invoice(iid, refund_mode)
                if inv_r:
                    database.log_audit("Invoices", "Redo Delete", inv_r[3], f"Moved invoice for {inv_r[4]} to Recycle Bin via Redo", inv_r[10], company_id=self.comp_id)
        else:
            for iid in ids: database.restore_invoice(iid)
            
        self.load_data()

    def on_mouse_motion(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        
        if row_id and 'dummy' in self.tree.item(row_id, 'tags'):
            self.tree.config(cursor="")
            self.tooltip.withdraw()
            return
            
        if self.bulk_mode:
            self.tree.config(cursor="hand2"); self.tooltip.withdraw(); return
            
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell": 
            self.tree.config(cursor="hand2")
            
            # --- THE FIX: Show Subject Tooltip on Invoice No hover ---
            if col == "#3" and row_id:
                subj = getattr(self, "subj_map", {}).get(str(row_id), "")
                if subj:
                    self.tooltip_lbl.config(text=subj)
                    x = event.x_root + 15
                    y = event.y_root + 15
                    self.tooltip.wm_geometry(f"+{x}+{y}")
                    self.tooltip.deiconify()
                else:
                    self.tooltip.withdraw()
            else:
                self.tooltip.withdraw()
            # ---------------------------------------------------------
        else: 
            self.tree.config(cursor="")
            self.tooltip.withdraw()

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        if not row_id or 'dummy' in self.tree.item(row_id, 'tags'): return
        if self.bulk_mode: return
        
        column = self.tree.identify_column(event.x)
        
        # Route the double-click based on the specific column
        if column == '#3': # Invoice Number Column
            show_preview_from_db(self, row_id)
        elif column == '#4': # Customer Name Column
            customer_name = self.tree.item(row_id, "values")[3]
            # --- THE FIX: Fetch the exact Customer ID to pass to the portal ---
            try:
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("SELECT customer_id FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
                r = c.fetchone()
                conn.close()
                cust_id = r[0] if r else None
            except: cust_id = None
            open_payment_portal(self, customer_name, cust_id)
            # ------------------------------------------------------------------
        else: # Anywhere else on the row
            try:
                conn = database.get_connection()
                c = conn.cursor()
                # --- THE FIX: Only fetch the GST lock status. We no longer care about payments! ---
                c.execute("SELECT ca_submitted FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
                r = c.fetchone()
                conn.close()
                if r and r[0] == 1:
                    messagebox.showwarning("GST Filed", "This invoice is marked as 'GST Filed'.\n\nTo prevent data mismatch, editing is locked.", parent=self)
                    return
                # --------------------------------------------------------------------------------------
            except: pass
            open_new_invoice(self, row_id)

    def create_stat_card(self, parent, title, value_var, value_color, click_callback=None):
        card = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, padx=20, pady=15)
        lbl_title = tk.Label(card, text=title, font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, anchor="center", justify="center")
        lbl_title.pack(fill="x")
        lbl_val = tk.Label(card, textvariable=value_var, font=("Arial", 20, "bold"), bg=self.CARD, fg=value_color, anchor="center", justify="center")
        lbl_val.pack(fill="x", pady=(5, 0))
        
        if click_callback:
            def on_click(e): click_callback(); return "break"
            for w in (card, lbl_title, lbl_val):
                w.bind("<Button-1>", on_click)
                w.bind("<Enter>", lambda e: card.config(bg=self.BTN_HOVER) or lbl_title.config(bg=self.BTN_HOVER) or lbl_val.config(bg=self.BTN_HOVER))
                w.bind("<Leave>", lambda e: card.config(bg=self.CARD) or lbl_title.config(bg=self.CARD) or lbl_val.config(bg=self.CARD))
                w.config(cursor="hand2")
                
        self.stat_cards[title] = {"frame": card, "title": lbl_title, "val": lbl_val}
        return card

    def set_tile_filter(self, filter_val, card_title):
        self.focus_set()
        
        if self.active_filter == filter_val and filter_val != "All": 
            self.active_filter = "All"
            self.active_filter_card = self.stat_cards.get("TOTAL INVOICES", {}).get("frame")
        else: 
            self.active_filter = filter_val
            self.active_filter_card = self.stat_cards.get(card_title, {}).get("frame")
            
        for title, card_dict in self.stat_cards.items():
            card = card_dict["frame"]
            if card == self.active_filter_card:
                card.config(highlightbackground=self.BLUE, highlightthickness=2)
            else:
                card.config(highlightbackground=self.BORDER, highlightthickness=1)
        self.current_page = 1
        self.load_data()

    def toggle_bulk_mode(self, mode=None):
        if self.bulk_mode and not mode:
            self.bulk_mode = False
            self.bulk_action_type = None # <-- FIX: Clear memory
            self.bulk_selection.clear()
            self.bulk_toolbar.pack_forget()
            self.toolbar.pack(fill="x", pady=(0, 15), before=self.table_frame)
            self.tree.heading("sl_no", text="SL. NO.")
            self.load_data()
        else:
            self.bulk_mode = True
            self.bulk_action_type = mode # <-- FIX: Remember if we are exporting or deleting
            self.bulk_selection.clear()
            self.toolbar.pack_forget()
            
            for widget in self.bulk_toolbar.winfo_children(): widget.destroy()
            
            # --- THE FIX: Removed the redundant '0 Selected' label ---
            
            tk.Button(self.bulk_toolbar, text="✖ Cancel", font=("Arial", 9, "bold"), bg=self.BG, fg=self.RED, command=self.toggle_bulk_mode, relief="solid", bd=1, cursor="hand2").pack(side="right", padx=10, ipady=3, ipadx=5)
            
            if mode == "delete":
                # --- THE FIX: Save button to a variable and add (0) counter ---
                self.btn_bulk_del = tk.Button(self.bulk_toolbar, text="🗑 Delete Selected (0)", font=("Arial", 9, "bold"), bg=self.RED, fg="#ffffff", command=self.confirm_bulk_delete, relief="flat", cursor="hand2")
                self.btn_bulk_del.pack(side="right", padx=10, ipady=4, ipadx=5)
            elif mode == "export":
                # --- THE FIX: Swapped packing order so PDF appears first ---
                tk.Button(self.bulk_toolbar, text="🖨 Export PDF", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", command=lambda: self.execute_bulk_export("pdf"), relief="flat", cursor="hand2").pack(side="right", padx=(5, 10), ipady=4, ipadx=5)
                tk.Button(self.bulk_toolbar, text="📄 Export CSV", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", command=lambda: self.execute_bulk_export("csv"), relief="flat", cursor="hand2").pack(side="right", padx=0, ipady=4, ipadx=5)
            
            # --- THE FIX: Bound the Select All button to a variable and added the (0) counter ---
            self.btn_select_all = tk.Button(self.bulk_toolbar, text="☑ Select All (0)", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", cursor="hand2", relief="flat", command=self.select_all_bulk)
            self.btn_select_all.pack(side="right", padx=10, ipady=4, ipadx=5)
            
            self.bulk_toolbar.pack(fill="x", pady=(0, 15), before=self.table_frame)
            self.tree.heading("sl_no", text="[ ] ALL")
            self.load_data()

    def toggle_bulk_selection(self, row_id):
        # --- THE FIX: Only block selection if the user is trying to DELETE ---
        if row_id not in self.bulk_selection:
            if getattr(self, "bulk_action_type", None) == "delete":
                allowed, reason = database.check_invoice_permission(row_id, action="delete", company_id=self.comp_id)
                if not allowed:
                    messagebox.showwarning("Access Restricted", reason, parent=self)
                    return
                conn = database.get_connection()
                c = conn.cursor()
                # --- THE FIX: Added company_id lock ---
                c.execute("SELECT ca_submitted FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
                res = c.fetchone()
                conn.close()
                if res and res[0] == 1:
                    messagebox.showwarning("Locked", "This bill is GST Filed and cannot be deleted.", parent=self)
                    return
            self.bulk_selection.add(row_id)
        else: 
            self.bulk_selection.remove(row_id)
            
        vals = list(self.tree.item(row_id, "values"))
        vals[0] = "[✓]" if row_id in self.bulk_selection else "[  ]"
        self.tree.item(row_id, values=vals)
        
        # --- THE FIX: Verify widgets physically exist, and update both dynamic counters ---
        if hasattr(self, "btn_bulk_del") and self.btn_bulk_del.winfo_exists(): 
            self.btn_bulk_del.config(text=f"🗑 Delete Selected ({len(self.bulk_selection)})")
        if hasattr(self, "btn_select_all") and self.btn_select_all.winfo_exists():
            self.btn_select_all.config(text=f"☑ Select All ({len(self.bulk_selection)})")
        
        all_items = [child for child in self.tree.get_children() if "empty" not in self.tree.item(child, "tags")]
        if len(self.bulk_selection) == len(all_items) and len(all_items) > 0:
            self.tree.heading("sl_no", text="[✓] ALL")
        else:
            self.tree.heading("sl_no", text="[ ] ALL")

    def select_all_bulk(self):
        visible_ids = [iid for iid in self.tree.get_children() if 'dummy' not in self.tree.item(iid, "tags")]
        if not visible_ids: return
        
        # --- THE FIX: Only filter out locked items if we are DELETING ---
        valid_ids = []
        is_delete_mode = (getattr(self, "bulk_action_type", None) == "delete")
        
        conn = database.get_connection()
        c = conn.cursor()
        for iid in visible_ids:
            if is_delete_mode:
                # --- THE FIX: Added company_id lock ---
                c.execute("SELECT ca_submitted FROM invoices WHERE id=? AND company_id=?", (iid, self.comp_id))
                res = c.fetchone()
                if not (res and res[0] == 1):
                    valid_ids.append(iid)
            else:
                valid_ids.append(iid) # Export mode allows everything
        conn.close()
        
        all_selected = all(str(iid) in self.bulk_selection for iid in valid_ids)
        
        if all_selected:
            for iid in valid_ids:
                if str(iid) in self.bulk_selection:
                    self.bulk_selection.remove(str(iid))
                vals = list(self.tree.item(iid, "values"))
                vals[0] = "[ ]"
                self.tree.item(iid, values=vals)
            self.tree.heading("sl_no", text="[ ] ALL")
        else:
            for iid in valid_ids:
                self.bulk_selection.add(str(iid))
                vals = list(self.tree.item(iid, "values"))
                vals[0] = "[✓]"
                self.tree.item(iid, values=vals)
            self.tree.heading("sl_no", text="[✓] ALL")
            
        # --- THE FIX: Verify widgets physically exist, and update both dynamic counters ---
        if hasattr(self, "btn_bulk_del") and self.btn_bulk_del.winfo_exists(): 
            self.btn_bulk_del.config(text=f"🗑 Delete Selected ({len(self.bulk_selection)})")
        if hasattr(self, "btn_select_all") and self.btn_select_all.winfo_exists():
            self.btn_select_all.config(text=f"☑ Select All ({len(self.bulk_selection)})")

    def show_smart_delete_prompt(self, amount):
        dialog = tk.Toplevel(self)
        dialog.title("Smart Deletion Engine")
        dialog.geometry("500x250")
        dialog.configure(bg=self.BG)
        dialog.grab_set()
        dialog.transient(self.app)
        
        self.app.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() // 2) - 250
        y = self.app.winfo_rooty() + (self.app.winfo_height() // 2) - 125
        dialog.geometry(f"+{x}+{y}")

        result = tk.StringVar(value="cancel")
        
        tk.Label(dialog, text="⚠️ Payments Detected", font=("Arial", 14, "bold"), bg=self.BG, fg=self.RED).pack(pady=(20, 5))
        
        msg = f"This invoice has {format_currency(amount, self.curr_fmt)} recorded as received.\nHow would you like to handle these funds?"
        tk.Label(dialog, text=msg, font=("Arial", 11), bg=self.BG, fg=self.FG).pack(pady=(0, 20))
        
        btn_f = tk.Frame(dialog, bg=self.BG)
        btn_f.pack(fill="x", padx=20)
        
        def set_res(val):
            result.set(val)
            dialog.destroy()
            
        btn_wallet = tk.Button(btn_f, text="Move to Advance Wallet\n(Real Money Route)", font=("Arial", 10, "bold"), bg=self.GREEN, fg="white", relief="flat", cursor="hand2", command=lambda: set_res("wallet"))
        btn_wallet.pack(side="left", fill="x", expand=True, padx=5, ipady=5)
        
        btn_vapor = tk.Button(btn_f, text="Data-Entry Mistake\n(Vaporize Phantom Cash)", font=("Arial", 10, "bold"), bg=self.RED, fg="white", relief="flat", cursor="hand2", command=lambda: set_res("vaporize"))
        btn_vapor.pack(side="left", fill="x", expand=True, padx=5, ipady=5)

        tk.Button(dialog, text="Cancel Deletion", font=("Arial", 10), bg=self.BORDER, fg=self.FG, relief="flat", cursor="hand2", command=lambda: set_res("cancel")).pack(pady=15, ipady=3, ipadx=20)

        dialog.wait_window()
        return result.get()

    def attempt_soft_delete(self, row_id):
        allowed, reason = database.check_invoice_permission(row_id, action="delete", company_id=self.comp_id)
        if not allowed:
            messagebox.showwarning("Access Restricted", reason, parent=self)
            return

        conn = database.get_connection()
        c = conn.cursor()
        
        try:
            # --- THE FIX: Added company_id lock + total for audit ---
            c.execute("SELECT invoice_number, customer_name, amount_paid, company_id, write_off, total FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
            row = c.fetchone()
            
            if not row:
                conn.close()
                return
                
            inv_num, cust_name, paid_amt, comp_id, woff, inv_tot = row
            paid_amt = float(paid_amt or 0.0)
            woff = float(woff or 0.0)
            inv_tot = float(inv_tot or 0.0)
            
            refund_mode = 'none'
            
            if paid_amt > 0.01:
                res = self.show_smart_delete_prompt(paid_amt)
                if res == "cancel":
                    conn.close()
                    return
                refund_mode = res
            elif woff > 0.01:
                if not messagebox.askyesno("Confirm", f"This invoice has a Write-Off of {format_currency(woff, self.curr_fmt)}.\nVaporize this record?", parent=self):
                    conn.close()
                    return
                refund_mode = 'vaporize'
            else:
                if not messagebox.askyesno("Confirm", "Move invoice to Recycle Bin?", parent=self):
                    conn.close()
                    return
                refund_mode = 'vaporize'

            # --- THE FIX: Removed rogue logic. Let database.py handle the math securely. ---
            conn.commit()
            conn.close()

            database.soft_delete_invoice(row_id, refund_mode)
            database.log_audit(
                "Invoices", "Deleted", inv_num,
                f"Moved to Recycle Bin • Customer: {cust_name}",
                inv_tot, company_id=self.comp_id
            )
            
            self.undo_stack.append({"type": "delete", "ids": [row_id], "refund_mode": refund_mode})
            self.redo_stack.clear()
            self.load_data()
            
        except Exception as e:
            try: conn.close()
            except: pass
            print(f"Delete Error: {e}")

    def confirm_bulk_delete(self):
        if not self.bulk_selection:
            messagebox.showinfo("No Selection", "Please select at least one invoice.", parent=self); return

        for row_id in self.bulk_selection:
            allowed, reason = database.check_invoice_permission(row_id, action="delete", company_id=self.comp_id)
            if not allowed:
                messagebox.showwarning("Access Restricted", reason, parent=self)
                return
            
        conn = database.get_connection()
        c = conn.cursor()
        
        # --- THE FIX: The Vault Door (Hard abort if locked items found) ---
        for row_id in self.bulk_selection:
            # --- THE FIX: Added company_id lock ---
            c.execute("SELECT ca_submitted FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
            res = c.fetchone()
            if res and res[0] == 1:
                messagebox.showerror("Action Denied", "Deletion aborted.\n\nOne or more selected bills are GST Filed and locked. To protect compliance data, the batch has been cancelled.", parent=self)
                conn.close()
                return
        
        try: c.execute("ALTER TABLE invoices ADD COLUMN write_off REAL DEFAULT 0.0")
        except: pass
        
        placeholders = ",".join("?" for _ in self.bulk_selection)
        c.execute(f"SELECT SUM(amount_paid), SUM(write_off) FROM invoices WHERE id IN ({placeholders}) AND company_id=?", (*self.bulk_selection, self.comp_id))
        row = c.fetchone()
        tot_paid = float(row[0] or 0.0)
        tot_woff = float(row[1] or 0.0)
        
        refund_mode = 'none'
        
        if tot_paid > 0.01:
            res = self.show_smart_delete_prompt(tot_paid)
            if res == "cancel": 
                conn.close(); return
            refund_mode = res
        elif tot_woff > 0.01:
            if not messagebox.askyesno("Confirm", f"These invoices have Write-Offs totaling {format_currency(tot_woff, self.curr_fmt)}.\nVaporize these records?", parent=self):
                conn.close(); return
            refund_mode = 'vaporize'
        else:
            if not messagebox.askyesno("Confirm", f"Are you sure you want to delete {len(self.bulk_selection)} items?", parent=self):
                conn.close(); return
            refund_mode = 'vaporize'
            
        try:
            # --- THE FIX: Removed rogue logic. Let database.py handle the math securely. ---
            conn.commit()
            conn.close()

            for row_id in self.bulk_selection:
                inv_r, _ = database.get_invoice_by_id(row_id)
                database.soft_delete_invoice(row_id, refund_mode)
                if inv_r:
                    database.log_audit(
                        "Invoices", "Bulk Deleted", inv_r[3],
                        f"Bulk moved to Recycle Bin • Customer: {inv_r[4]}",
                        inv_r[10], company_id=self.comp_id
                    )
            
            self.undo_stack.append({"type": "delete", "ids": list(self.bulk_selection), "refund_mode": refund_mode})
            self.redo_stack.clear()
            self.update_memory_buttons()
            
            self.toggle_bulk_mode()
        except Exception as e:
            try: conn.close()
            except: pass
            print(f"Bulk Delete Error: {e}")

    def execute_bulk_export(self, fmt):
        if not self.bulk_selection:
            messagebox.showinfo("Bulk Action", "No items selected.", parent=self)
            return
            
        # --- THE FIX: Bypass pagination by building a fresh tree of ALL selected items directly from the DB ---
        orig_heading = self.tree.heading("sl_no", "text")
        self.tree.heading("sl_no", text="SL. NO.")
        
        for child in self.tree.get_children():
            self.tree.delete(child)

        conn = database.get_connection()
        c = conn.cursor()
        placeholders = ",".join("?" for _ in self.bulk_selection)
        c.execute(f"SELECT id, invoice_date, invoice_number, customer_name, subtotal, (cgst+sgst+igst) as total_gst, total, status, amount_paid, write_off FROM invoices WHERE id IN ({placeholders}) AND company_id=? ORDER BY id DESC", (*self.bulk_selection, self.comp_id))
        selected_rows = c.fetchall()
        
        # --- THE FIX: Fetch TDS logic for bulk export ---
        c.execute("SELECT ref, amount FROM party_payments WHERE company_id=? AND mode='TDS Deduction'", (self.comp_id,))
        tds_map = {}
        for ref_str, amt in c.fetchall():
            if ref_str:
                bill_no = ref_str.split(" (")[0].strip()
                tds_map[bill_no] = tds_map.get(bill_no, 0.0) + float(amt or 0.0)
        conn.close()
        # ------------------------------------------------

        export_idx = 1
        for row in selected_rows:
            inv_id, inv_date, inv_num, cust_name, sub, total_gst, tot, stat, amt_paid, woff = row
            woff = float(woff or 0.0)
            due = max(0.0, float(tot or 0.0) - float(amt_paid or 0.0) - woff)

            if due <= 0.01: stat_txt = "Paid"
            elif float(amt_paid or 0.0) > 0 or woff > 0: stat_txt = f"Partial ({format_currency(due, self.curr_fmt)} due)"
            else: stat_txt = "Unpaid"

            fmt_date = smart_date_formatter(inv_date, self.date_fmt_code)
            tds_val = tds_map.get(inv_num, 0.0)

            self.tree.insert("", "end", iid=str(inv_id), values=(
                export_idx, fmt_date, inv_num, cust_name, 
                format_currency(sub, self.curr_fmt), format_currency(total_gst, self.curr_fmt), 
                format_currency(tot, self.curr_fmt), format_currency(tds_val, self.curr_fmt), stat_txt, ""
            ))
            export_idx += 1
        # ----------------------------------------------------------------------------------------------------
            
        # Trigger the normal export functions (They will process the newly loaded tree!)
        try:
            if fmt == "pdf": export_to_pdf(self)
            elif fmt == "csv": export_to_csv(self)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self)
            
        # Restore the UI exactly as it was
        self.tree.heading("sl_no", text=orig_heading)
        self.toggle_bulk_mode()
        self.load_data()

    def load_data(self, event=None):
        if event:
            self.current_page = 1
            
        for item in self.tree.get_children(): self.tree.delete(item)

        conn = database.get_connection()
        c = conn.cursor()
        
        # --- THE FIX: Fetch customer receivable terms using Secure Database IDs ---
        c.execute("SELECT id, address FROM customers WHERE company_id=?", (self.comp_id,))
        cust_terms = {}
        for row in c.fetchall():
            c_id, c_addr = row[0], row[1]
            try:
                j_data = json.loads(c_addr)
                cust_terms[c_id] = int(j_data.get("receivable_terms", j_data.get("credit_period", 0)))
            except:
                cust_terms[c_id] = 0
        # ------------------------------------------------------------------------
        
        # We add 'customer_id' and 'place_of_service' to the very end of the SELECT query
        c.execute("SELECT id, invoice_date, invoice_number, customer_name, subtotal, (cgst+sgst+igst) as total_gst, total, status, amount_paid, write_off, customer_id, place_of_service FROM invoices WHERE company_id=? AND is_deleted=0 ORDER BY id DESC", (self.comp_id,))
        all_db_invoices = c.fetchall()
        
        c.execute("SELECT id FROM invoices WHERE company_id=? AND is_deleted=1", (self.comp_id,))
        deleted_invs = c.fetchall()
        
        # --- THE FIX: Load TDS history across all active invoices ---
        c.execute("SELECT ref, amount FROM party_payments WHERE company_id=? AND mode='TDS Deduction'", (self.comp_id,))
        self.tds_map = {}
        for ref_str, amt in c.fetchall():
            if ref_str:
                bill_no = ref_str.split(" (")[0].strip()
                self.tds_map[bill_no] = self.tds_map.get(bill_no, 0.0) + float(amt or 0.0)
        # ------------------------------------------------------------
        conn.close()
        
        period = getattr(self, "period_var", tk.StringVar(value="All Time")).get()
        now = datetime.now()
        
        fy_start_month = 4 
        try:
            comp_data = database.get_company(self.comp_id)
            if comp_data and len(comp_data) > 14 and comp_data[14]:
                t_json = json.loads(comp_data[14])
                fy_val = t_json.get("fy_start", "April")
                if fy_val == "January": fy_start_month = 1
                elif fy_val == "July": fy_start_month = 7
        except: pass

        def safe_date_parse(date_str):
            for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
                try: return datetime.strptime(str(date_str).strip()[:10], fmt)
                except: pass
            return datetime.min

        period_filtered_invoices = []
        for inv in all_db_invoices:
            dt = safe_date_parse(inv[1])
            if period == "This Month":
                if dt.year != now.year or dt.month != now.month: continue
            elif period == "This Financial Year":
                start_year = now.year if now.month >= fy_start_month else now.year - 1
                if dt < datetime(start_year, fy_start_month, 1): continue
            period_filtered_invoices.append(inv)
        
        real_invoices = [i for i in period_filtered_invoices if i[7] != 'Draft']
        
        self.stat_count_var.set(str(len(real_invoices)))
        total_billed = sum(float(i[6] or 0.0) for i in real_invoices)
        self.stat_billed_var.set(format_currency(total_billed, self.curr_fmt))
        
        self.stat_paid_var.set(str(sum(1 for i in real_invoices if i[7] == 'Paid')))
        
        # --- THE FIX: Calculate unpaid count and total unpaid amount ---
        unpaid_count = 0
        tot_unpaid_amt = 0.0
        for i in real_invoices:
            if i[7] in ['Unpaid', 'Partial']:
                due = max(0.0, float(i[6] or 0.0) - float(i[8] or 0.0) - float(i[9] or 0.0))
                if due > 0.01:
                    unpaid_count += 1
                    tot_unpaid_amt += due
                    
        unpaid_str = f"{unpaid_count}  |  {format_currency(tot_unpaid_amt, self.curr_fmt)}"
        self.stat_unpaid_var.set(unpaid_str)
        
        str_len = len(unpaid_str)
        if str_len > 18: font_sz = 13
        elif str_len > 12: font_sz = 15
        elif str_len > 9: font_sz = 17
        else: font_sz = 20
        self.stat_cards["UNPAID INVOICES"]["val"].config(font=("Arial", font_sz, "bold"))
        # ---------------------------------------------------------------
        
        self.stat_draft_var.set(str(sum(1 for i in period_filtered_invoices if i[7] == 'Draft')))
        self.stat_deleted_var.set(str(len(deleted_invs)) if deleted_invs else "0")

        display_list = [list(i) for i in real_invoices]
        
        search = self.search_var.get().lower()
        if search and search != "search customer or invoice...":
            display_list = [i for i in display_list if search in i[2].lower() or search in i[3].lower()]
            
        if self.active_filter != "All": 
            # --- THE FIX: Allow both 'Unpaid' and 'Partial' to show when the Unpaid tile is active ---
            if self.active_filter == "Unpaid":
                display_list = [i for i in display_list if i[7] in ["Unpaid", "Partial"]]
            else:
                display_list = [i for i in display_list if i[7] == self.active_filter]

        s = self.sort_var.get()
        if s == "Date Wise": 
            display_list.sort(key=lambda x: safe_date_parse(x[1]), reverse=True)
        elif s == "Invoice No (Low to High)": 
            display_list.sort(key=lambda x: int(re.findall(r'\d+', str(x[2]))[-1]) if re.findall(r'\d+', str(x[2])) else 0)
        elif s == "Invoice No (High to Low)": 
            display_list.sort(key=lambda x: int(re.findall(r'\d+', str(x[2]))[-1]) if re.findall(r'\d+', str(x[2])) else 0, reverse=True)
        elif s == "A to Z": 
            display_list.sort(key=lambda x: x[3].lower())
        elif s == "Z to A": 
            display_list.sort(key=lambda x: x[3].lower(), reverse=True)

        # --- THE FIX: PAGINATION MATH, AUTO-JUMP, & SLICING ---
        import math
        
        if hasattr(self.app, 'pending_highlight') and self.app.pending_highlight:
            target_ref = str(self.app.pending_highlight)
            for t_idx, t_item in enumerate(display_list):
                if str(t_item[2]) == target_ref:
                    self.current_page = (t_idx // self.items_per_page) + 1
                    break
                    
        self.total_pages = math.ceil(len(display_list) / self.items_per_page)
        if self.total_pages < 1: self.total_pages = 1
        if self.current_page > self.total_pages: self.current_page = self.total_pages

        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        paginated_list = display_list[start_idx:end_idx]

        self.lbl_page.config(text=f"Page {self.current_page} of {self.total_pages}")
        
        if self.current_page <= 1:
            self.btn_prev.config(state="disabled", fg=self.BORDER, bg=self.BG, cursor="arrow")
        else:
            self.btn_prev.config(state="normal", fg=self.SEC_FG, bg=self.BG, cursor="hand2")
            
        if self.current_page >= self.total_pages:
            self.btn_next.config(state="disabled", bg=self.BG, fg=self.BORDER, cursor="arrow")
        else:
            self.btn_next.config(state="normal", bg=self.CARD, fg=self.FG, cursor="hand2")
        # ------------------------------------------

        self.tree.tag_configure('even', background=self.STRIPE_EVEN)
        self.tree.tag_configure('odd', background=self.STRIPE_ODD)
        self.tree.tag_configure('paid', foreground=self.GREEN)
        self.tree.tag_configure('unpaid', foreground=self.RED)
        self.tree.tag_configure('partial', foreground="#d97706")
        # --- THE FIX: Add configuration for overdue tag ---
        self.tree.tag_configure('status_overdue', foreground="#ef4444")
        # --------------------------------------------------
        self.tree.tag_configure('highlight_target', background=self.YELLOW, foreground="#0f172a")
        
        # --- THE FIX: ADD MONTH HEADER TAG ---
        self.tree.tag_configure('month_header', background=self.BORDER, foreground=self.FG, font=("Arial", 10, "bold"))
        last_month_str = ""
        
        self.subj_map = getattr(self, "subj_map", {})
        self.subj_map.clear()

        for idx, i in enumerate(paginated_list, start_idx + 1):
            # Unpack the first 10 items normally, and grab the 11th/12th item safely
            inv_id, inv_date, inv_num, cust_name, sub, total_gst, tot, stat, amt_paid, woff = i[:10]
            cust_id = i[10] if len(i) > 10 else None
            place_str = i[11] if len(i) > 11 and i[11] else ""
            
            subj_text = ""
            if "@@SUBJ@@" in place_str:
                m = re.search(r'@@SUBJ@@(.*?)@@', place_str + "@@", re.DOTALL)
                if m:
                    p = m.group(1).split('||')
                    if p and p[0].strip():
                        subj_text = p[0].strip().replace("@@B@@", "").replace("@@U@@", "")
            self.subj_map[str(inv_id)] = subj_text
            
            woff = woff if woff else 0.0
            due = max(0.0, float(tot or 0.0) - float(amt_paid or 0.0) - woff)
            
            # --- THE FIX: Calculate Overdue Status using Database IDs ---
            is_overdue = False
            try:
                if due > 0.01:
                    inv_dt = safe_date_parse(inv_date).date()
                    p_terms = cust_terms.get(cust_id, 0)
                    if p_terms > 0:
                        due_dt = inv_dt + timedelta(days=p_terms)
                        if date.today() > due_dt:
                            is_overdue = True
            except: pass
            
            if due <= 0.01:
                stat_txt = "Paid"
                status_tag = 'paid'
                stripe_tag = 'even' if idx % 2 == 0 else 'odd'
            elif (amt_paid or 0.0) > 0 or woff > 0:
                stat_txt = f"OVERDUE ({format_currency(due, self.curr_fmt)} due)" if is_overdue else f"Partial ({format_currency(due, self.curr_fmt)} due)"
                status_tag = 'status_overdue' if is_overdue else 'partial'
                stripe_tag = 'even' if idx % 2 == 0 else 'odd'
            else:
                stat_txt = "OVERDUE (Unpaid)" if is_overdue else "Unpaid"
                status_tag = 'status_overdue' if is_overdue else 'unpaid'
                stripe_tag = 'even' if idx % 2 == 0 else 'odd'
            # ------------------------------------------------------
                
            formatted_date = smart_date_formatter(inv_date, self.date_fmt_code)
            
            # --- THE FIX: INJECT MONTH HEADER (ONLY IF CHRONOLOGICAL) ---
            if self.sort_var.get() == "Date Wise":
                dt = safe_date_parse(inv_date)
                current_month_str = dt.strftime("%B, %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                
                if current_month_str != last_month_str:
                    # Note: Added an extra "" to match the 10 columns!
                    self.tree.insert("", "end", iid=f"dummy_header_{current_month_str}_{idx}", values=("", f"📅  {current_month_str}", "", "", "", "", "", "", "", ""), tags=("month_header", "dummy"))
                    last_month_str = current_month_str
            # ------------------------------------------------------------
            
            display_idx = "[✓]" if self.bulk_mode and str(inv_id) in self.bulk_selection else "[  ]" if self.bulk_mode else idx
            
            # --- THE FIX: Inject TDS Value into the Main View ---
            tds_val = self.tds_map.get(inv_num, 0.0)
            
            self.tree.insert("", "end", iid=str(inv_id), values=(
                display_idx, formatted_date, inv_num, cust_name, 
                format_currency(sub, self.curr_fmt), format_currency(total_gst, self.curr_fmt), 
                format_currency(tot, self.curr_fmt), format_currency(tds_val, self.curr_fmt), stat_txt, ""
            ), tags=(stripe_tag, status_tag))
            # ----------------------------------------------------
            
        current_rows = len(paginated_list)
        if current_rows < 15:
            for idx in range(current_rows + 1, 16):
                stripe_tag = 'even' if idx % 2 == 0 else 'odd'
                # Note: Added an extra "" to match the 10 columns!
                self.tree.insert("", "end", iid=f"dummy_{idx}", values=("", "", "", "", "", "", "", "", "", ""), tags=(stripe_tag, 'dummy'))
        
        if hasattr(self.app, 'pending_highlight') and self.app.pending_highlight:
            target_ref = str(self.app.pending_highlight)
            for child in self.tree.get_children():
                if str(self.tree.item(child)['values'][2]) == target_ref:
                    self.tree.see(child)
                    current_tags = list(self.tree.item(child, 'tags'))
                    self.tree.item(child, tags=tuple(current_tags + ['highlight_target']))
                    self.app.pending_highlight = None 
                    def clear_highlight_and_select(item_id=child, orig_tags=current_tags):
                        try:
                            if self.tree.exists(item_id):
                                self.tree.item(item_id, tags=tuple(orig_tags))
                                self.tree.selection_set(item_id); self.tree.focus(item_id)
                        except: pass
                    self.after(2500, clear_highlight_and_select)
                    break

        self.update_memory_buttons()

    def on_left_click(self, event):
        self.focus_set()
        
        region = self.tree.identify("region", event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        
        if region == "heading" or not row_id or 'dummy' in self.tree.item(row_id, 'tags'): 
            if self.active_filter != "All": 
                self.set_tile_filter("All", "TOTAL INVOICES")
            return

        if self.bulk_mode: self.toggle_bulk_selection(row_id); return

    def on_right_click(self, event):
        if self.bulk_mode: return
        row_id = self.tree.identify_row(event.y)
        if row_id and 'dummy' not in self.tree.item(row_id, 'tags'):
            self.tree.selection_set(row_id)
            menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD, fg=self.FG, activebackground=self.BLUE, activeforeground="#ffffff")
            
            try:
                conn = database.get_connection()
                c = conn.cursor()
                # --- THE FIX: Only check if it's GST Locked ---
                c.execute("SELECT ca_submitted FROM invoices WHERE id=? AND company_id=?", (row_id, self.comp_id))
                r = c.fetchone()
                conn.close()
                is_locked = (r and r[0] == 1)
            except: 
                is_locked = False

            if is_locked:
                menu.add_command(label="🔒 Cannot Edit (GST Filed)", foreground="#ef4444", command=lambda: messagebox.showwarning("GST Filed", "This invoice is marked as 'GST Filed' and cannot be edited.", parent=self))
            else:
                menu.add_command(label="✏️ Edit Invoice", command=lambda: open_new_invoice(self, edit_inv_id=row_id))
                
            # --- THE FIX: Added Duplicate/Clone Button ---
            menu.add_command(label="⎘ Duplicate / Clone", command=lambda: open_new_invoice(self, clone_id=row_id))
            # ---------------------------------------------
            
            menu.add_command(label="👁 Generate Preview", command=lambda: show_preview_from_db(self, row_id))
            menu.add_separator()
            
            if is_locked:
                menu.add_command(label="🔒 Cannot Delete (GST Filed)", foreground="#ef4444", command=lambda: messagebox.showwarning("GST Filed", "This invoice is marked as 'GST Filed' and cannot be deleted.", parent=self))
            else:
                menu.add_command(label="❌ Move to Recycle Bin", command=lambda: self.attempt_soft_delete(row_id))
                
            menu.add_separator()
            menu.add_command(label="📄 Bulk Export", command=lambda: self.toggle_bulk_mode("export"))
            if is_locked:
                menu.add_command(label="🔒 Cannot Bulk Delete (GST Filed)", foreground="#ef4444", command=lambda: messagebox.showwarning("GST Filed", "This invoice is marked as 'GST Filed'. Bulk deletion involves locked documents.", parent=self.winfo_toplevel()))
            else:
                menu.add_command(label="🗑 Bulk Delete", command=lambda: self.toggle_bulk_mode("delete"))
            
            menu.tk_popup(event.x_root, event.y_root)

    def open_drafts_popup(self):
        pop = tk.Toplevel(self)
        pop.title("Draft Invoices") 
        
        pop.geometry("650x500") 
        pop.configure(bg=self.BG)
        pop.transient(self.app)
        pop.focus_force()
        pop.grab_set()
        
        tk.Label(pop, text="Draft Invoices", font=("Arial", 16, "bold"), bg=self.BG, fg=self.FG).pack(pady=(20, 5))
        tk.Label(pop, text="Double-click an invoice to Edit & Post. These bills do not affect inventory or P&L.", font=("Arial", 10), bg=self.BG, fg=self.SEC_FG, wraplength=550, justify="center").pack(pady=(0, 20))
        
        list_f = tk.Frame(pop, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        list_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        columns = ("date", "inv_num", "customer", "total", "actions", "ghost")
        tree = ttk.Treeview(list_f, columns=columns, show="headings", height=10, style="Theme.Treeview")
        
        tree.heading("date", text="DATE", anchor="center")
        tree.heading("inv_num", text="INVOICE NO.", anchor="center")
        tree.heading("customer", text="CUSTOMER", anchor="w")
        tree.heading("total", text="TOTAL", anchor="e")
        tree.heading("actions", text="ACTIONS", anchor="center")
        tree.heading("ghost", text="")

        try:
            raw_setting = database.get_ui_setting("inv_drafts_cols", "{}")
            d_w = json.loads(raw_setting) if raw_setting else {}
        except:
            d_w = {}

        tree.column("date", width=d_w.get("date", 90), anchor="center", stretch=False)
        tree.column("inv_num", width=d_w.get("inv_num", 100), anchor="center", stretch=False)
        tree.column("customer", width=d_w.get("customer", 170), anchor="w", stretch=False)
        tree.column("total", width=d_w.get("total", 100), anchor="e", stretch=False)
        tree.column("actions", width=d_w.get("actions", 100), anchor="center", stretch=False)
        tree.column("ghost", width=10, minwidth=10, stretch=True)

        def save_draft_widths():
            new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "ghost"}
            try: database.save_ui_setting("inv_drafts_cols", json.dumps(new_w))
            except: pass

        def on_draft_sep_drag(event):
            if tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_draft_widths)

        tree.bind("<B1-Motion>", on_draft_sep_drag, add="+")
        tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_draft_widths), add="+")

        # --- THE FIX: Apply the thick scrollbar style to Drafts ---
        scroll = ttk.Scrollbar(list_f, orient="vertical", command=tree.yview, style="Inv.Vertical.TScrollbar")
        # ----------------------------------------------------------
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        def load_drafts():
            for item in tree.get_children(): tree.delete(item)
            
            conn = database.get_connection(); cursor = conn.cursor()
            cursor.execute("SELECT id, invoice_date, invoice_number, customer_name, total FROM invoices WHERE company_id=? AND status='Draft' AND is_deleted=0 ORDER BY id DESC", (self.comp_id,))
            drafts = cursor.fetchall()
            conn.close()
            
            if not drafts:
                self.stat_draft_var.set("0")
                self.load_data()
                for idx in range(1, 11):
                    stripe = "even" if idx % 2 == 0 else "odd"
                    tree.insert("", "end", iid=f"dummy_{idx}", values=("", "", "", "", "", ""), tags=(stripe, 'dummy'))
                tree.tag_configure("even", background=self.STRIPE_EVEN)
                tree.tag_configure("odd", background=self.STRIPE_ODD)
                return
                
            self.stat_draft_var.set(str(len(drafts)))
            for idx, d in enumerate(drafts, 1):
                stripe = "even" if idx % 2 == 0 else "odd"
                f_date = smart_date_formatter(d[1], self.date_fmt_code)
                tree.insert("", "end", iid=str(d[0]), values=(f_date, d[2], d[3], format_currency(d[4], self.curr_fmt), "❌ Delete", ""), tags=(stripe,))
            
            current_rows = len(drafts)
            if current_rows < 10:
                for idx in range(current_rows + 1, 11):
                    stripe = "even" if idx % 2 == 0 else "odd"
                    tree.insert("", "end", iid=f"dummy_{idx}", values=("", "", "", "", "", ""), tags=(stripe, 'dummy'))
                    
            tree.tag_configure("even", background=self.STRIPE_EVEN)
            tree.tag_configure("odd", background=self.STRIPE_ODD)

        def on_click(event):
            region = tree.identify("region", event.x, event.y)
            if region == "cell":
                col = tree.identify_column(event.x)
                row_id = tree.identify_row(event.y)
                
                if not row_id or 'dummy' in tree.item(row_id, 'tags'): return 
                
                if col == "#5":
                    if messagebox.askyesno("Confirm Delete", "Permanently delete this draft?", parent=pop):
                        inv_r, _ = database.get_invoice_by_id(row_id)
                        database.hard_delete_invoice(row_id)
                        if inv_r:
                            database.log_audit(
                                "Invoices", "Draft Deleted", inv_r[3],
                                f"Permanently deleted draft for {inv_r[4]}",
                                inv_r[10], company_id=self.comp_id
                            )
                        load_drafts()
                        self.load_data()

        def on_double_click(event):
            region = tree.identify("region", event.x, event.y)
            if region == "cell":
                col = tree.identify_column(event.x)
                row_id = tree.identify_row(event.y)
                
                if not row_id or 'dummy' in tree.item(row_id, 'tags'): return 
                
                if col == "#2":
                    pop.destroy()
                    open_new_invoice(self, row_id)
                    
        tree.bind("<ButtonRelease-1>", on_click)
        tree.bind("<Double-1>", on_double_click)
        tree.bind("<Motion>", lambda e: tree.config(cursor="hand2") if tree.identify_column(e.x) in ("#2", "#5") and tree.identify_row(e.y) and 'dummy' not in tree.item(tree.identify_row(e.y), 'tags') else tree.config(cursor=""))

        pop.update_idletasks()
        try:
            main_x = self.winfo_rootx()
            main_y = self.winfo_rooty()
            main_w = self.winfo_width()
            main_h = self.winfo_height()
            
            x = main_x + (main_w // 2) - (650 // 2)
            y = main_y + (main_h // 2) - (500 // 2)
            pop.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        load_drafts()