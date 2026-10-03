import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json

# Ensure routing
# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path: sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings

from views.stock_parts.stock_forms import open_add_popup, open_loss_popup, open_audit_popup
from views.stock_parts.stock_history import open_history_popup
from views.stock_parts.stock_exports import export_csv, export_pdf, generate_purchase_order, trigger_csv_import

# --- SAFE HARBOR BACKGROUND ENGINE (UI Button Removed) ---
try:
    from views.stock_parts.stock_recovery import run_silent_backup
except ImportError:
    run_silent_backup = lambda x: None

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

class StockView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._last_hovered = None 
        self.current_page = 1
        
        # --- THE FIX: Load 50 items per page! ---
        self.items_per_page = 50
        
        # State Tracking for Context-Aware Bulk Mode
        self.is_bulk_mode = False
        self.bulk_mode_type = "" 
        self.selected_items = set() 
        self.show_low_stock_only = False 
        
        self.undo_stack = []
        self.redo_stack = [] 
        
        try:
            self.app = self.winfo_toplevel()
            self.comp_id = getattr(self.app, "active_company_id", 1)
        except:
            self.comp_id = 1
            
        # --- THE FIX: MVC Compliant Business Type Fetch ---
        self.b_type = database.get_company_business_type(self.comp_id)
        # --------------------------------------------------

        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        if self.is_dark:
            self.BG = "#0f172a"; self.CARD = "#1e293b"; self.BORDER = "#334155"; self.FG = "#f8fafc"
            self.SEC_FG = "#94a3b8"; self.HEADER = "#475569"; self.BLUE = "#3b82f6"; self.BTN_HOVER = "#2563eb"
            self.HOVER_ROW = "#334155"; self.DANGER = "#ef4444"; self.FOCUS_BG = "#475569"
            self.LOW_STOCK_BG_1 = "#450a0a" 
            self.LOW_STOCK_BG_2 = "#3a0505" 
        else:
            self.BG = "#e0f2fe"; self.CARD = "#f0f9ff"; self.BORDER = "#7dd3fc"; self.FG = "#0f172a"
            self.SEC_FG = "#0284c7"; self.HEADER = "#bae6fd"; self.BLUE = "#0ea5e9"; self.BTN_HOVER = "#0284c7"
            self.HOVER_ROW = "#bae6fd"; self.DANGER = "#ef4444"; self.FOCUS_BG = "#fef9c3"
            self.LOW_STOCK_BG_1 = "#fef2f2" 
            self.LOW_STOCK_BG_2 = "#fee2e2" 

        self.GREEN = "#10b981"; self.YELLOW = "#f59e0b"; self.PURPLE = "#8b5cf6" 

        self.config(bg=self.BG)
        
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
            
        run_silent_backup(self)
        self.build_ui()

    def build_ui(self):
        style = ttk.Style(self); style.theme_use("default")
        self.app.option_add("*TCombobox*Listbox.background", self.CARD)
        self.app.option_add("*TCombobox*Listbox.foreground", self.FG)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("Theme.TCombobox", fieldbackground=self.CARD, background=self.CARD, foreground=self.FG, arrowcolor=self.FG, bordercolor=self.BORDER)
        style.map("Theme.TCombobox", fieldbackground=[("readonly", "focus", self.FOCUS_BG), ("readonly", self.CARD)], selectbackground=[("readonly", self.CARD)], selectforeground=[("readonly", self.FG)])
        
        style.configure("Stock.Vertical.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.configure("Stock.Horizontal.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.map("Stock.Vertical.TScrollbar", background=[("active", self.BLUE)])
        style.map("Stock.Horizontal.TScrollbar", background=[("active", self.BLUE)])
        
        style.configure("Stock.Treeview.Heading", font=("Arial", 10, "bold"), background=self.HEADER, foreground=self.FG, borderwidth=1, relief="raised", bordercolor=self.BORDER)
        style.map("Stock.Treeview.Heading", background=[('active', self.BORDER)])
        style.configure("Stock.Treeview", font=("Arial", 12), rowheight=38, background=self.CARD, fieldbackground=self.CARD, foreground=self.FG, borderwidth=0)
        style.map("Stock.Treeview", background=[("selected", self.BLUE)], foreground=[("selected", "#ffffff")])

        main_container = tk.Frame(self, bg=self.BG)
        main_container.pack(fill="both", expand=True)

        header_f = tk.Frame(main_container, bg=self.BG); header_f.pack(fill="x", pady=(0, 20))
        
        title_frame = tk.Frame(header_f, bg=self.BG); title_frame.pack(side="left")
        tk.Label(title_frame, text="Stock & Inventory Ledger", font=("Arial", 28, "bold"), bg=self.BG, fg=self.FG).pack(anchor="w")
        
        self.undo_redo_frame = tk.Frame(header_f, bg=self.BG)
        self.undo_redo_frame.pack(side="right", anchor="center", padx=10)
        
        self.btn_undo = tk.Button(self.undo_redo_frame, text="⟲ Undo", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG, relief="solid", bd=1, padx=10, pady=3, command=lambda: self.exec_undo() if hasattr(self, 'exec_undo') else None, state="disabled")
        self.btn_undo.pack(side="left", padx=5)
        
        self.btn_redo = tk.Button(self.undo_redo_frame, text="⟳ Redo", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG, relief="solid", bd=1, padx=10, pady=3, command=lambda: self.exec_redo() if hasattr(self, 'exec_redo') else None, state="disabled")
        self.btn_redo.pack(side="left", padx=5)
        
        self.app.bind("<Control-z>", lambda e: self.exec_undo() if hasattr(self, 'exec_undo') else None)
        self.app.bind("<Control-y>", lambda e: self.exec_redo() if hasattr(self, 'exec_redo') else None)

        tiles_f = tk.Frame(main_container, bg=self.BG); tiles_f.pack(fill="x", pady=(0, 20))

        def create_tile(parent, title, val_color, pad_left=0, pad_right=0, click_cmd=None):
            f = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, padx=20, pady=20)
            lbl_title = tk.Label(f, text=title, font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG)
            lbl_title.pack(anchor="w")
            lbl_val = tk.Label(f, text="0.00", font=("Arial", 26, "bold"), bg=self.CARD, fg=val_color)
            lbl_val.pack(anchor="w", pady=(5, 0))
            f.pack(side="left", expand=True, fill="both", padx=(pad_left, pad_right))
            
            if click_cmd:
                f.config(cursor="hand2"); lbl_title.config(cursor="hand2"); lbl_val.config(cursor="hand2")
                f.bind("<Button-1>", lambda e: click_cmd(f))
                lbl_title.bind("<Button-1>", lambda e: click_cmd(f))
                lbl_val.bind("<Button-1>", lambda e: click_cmd(f))
                
            return lbl_val

        # --- THE FIX: Rename Tile to reflect Asset Book Value ---
        self.lbl_net_stock = create_tile(tiles_f, "TOTAL NET BOOK VALUE", self.BLUE, pad_right=10)
        # --------------------------------------------------------
        self.lbl_total_loss = create_tile(tiles_f, "TOTAL LOSS VALUE", self.DANGER, pad_left=10, pad_right=10)
        
        if self.b_type == "Sales": 
            self.lbl_total_sold = create_tile(tiles_f, "TOTAL SOLD VALUE", self.PURPLE, pad_left=10, pad_right=10)
            
            def toggle_low_stock_filter(tile_frame):
                self.show_low_stock_only = not self.show_low_stock_only
                bg_color = self.LOW_STOCK_BG_1 if self.show_low_stock_only else self.CARD
                tile_frame.config(bg=bg_color)
                for child in tile_frame.winfo_children(): child.config(bg=bg_color)
                self.load_data()
                
            self.lbl_low_stock_alert = create_tile(tiles_f, "LOW STOCK (Click to Filter)", self.DANGER, pad_left=10, pad_right=10, click_cmd=toggle_low_stock_filter)

        self.lbl_total_items = create_tile(tiles_f, "TOTAL ITEMS", self.FG, pad_left=10)

        filter_bar = tk.Frame(main_container, bg=self.BG); filter_bar.pack(fill="x", pady=(0, 10))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_bar, textvariable=self.search_var, font=("Arial", 11), width=30, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        search_entry.pack(side="left", ipady=4); search_entry.insert(0, "Search Stock...")
        search_entry.bind("<FocusIn>", lambda args: search_entry.delete('0', 'end') if search_entry.get() == 'Search Stock...' else None)
        search_entry.bind("<FocusOut>", lambda args: search_entry.insert(0, 'Search Stock...') if not search_entry.get() else None)
        search_entry.bind("<KeyRelease>", self.load_data); search_entry.bind("<Return>", lambda e: self.tree.focus_set())
        
        btn_clear = tk.Button(filter_bar, text="✖", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.DANGER, relief="flat", cursor="hand2", command=lambda: [self.search_var.set("Search Stock..."), self.tree.focus_set(), self.load_data()])
        btn_clear.pack(side="left", padx=(0, 10), ipady=3)
        add_hover(btn_clear, self.CARD, self.BORDER)

        self.app.bind("<Control-f>", lambda e: [search_entry.focus_set(), search_entry.select_range(0, tk.END)])

        self.filter_var = tk.StringVar(value="A to Z")
        filter_combo = ttk.Combobox(filter_bar, textvariable=self.filter_var, values=["A to Z", "Z to A", "Highest Value", "Lowest Value"], font=("Arial", 10), state="readonly", width=18, style="Theme.TCombobox", cursor="hand2")
        filter_combo.pack(side="left", padx=(10, 0), ipady=3); filter_combo.bind("<<ComboboxSelected>>", self.load_data)

        self.tool_bar = tk.Frame(main_container, bg=self.BG); self.tool_bar.pack(fill="x", pady=(0, 15))

        self.std_tools = tk.Frame(self.tool_bar, bg=self.BG); self.std_tools.pack(fill="both", expand=True)

        self.left_tools = tk.Frame(self.std_tools, bg=self.BG); self.left_tools.pack(side="left")
        self.right_tools = tk.Frame(self.std_tools, bg=self.BG); self.right_tools.pack(side="right")

        add_btn = tk.Button(self.right_tools, text="➕ Add Stock", font=("Arial", 10, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_add_popup(self))
        add_btn.pack(side="right"); add_hover(add_btn, self.BLUE, self.BTN_HOVER)

        loss_btn = tk.Button(self.right_tools, text="➖ Record Loss", font=("Arial", 10, "bold"), bg=self.DANGER, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_loss_popup(self))
        loss_btn.pack(side="right", padx=(0, 10)); add_hover(loss_btn, self.DANGER, "#dc2626")
        
        audit_btn = tk.Button(self.right_tools, text="⚖️ Stock Audit", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_audit_popup(self))
        audit_btn.pack(side="right", padx=(0, 10)); add_hover(audit_btn, self.CARD, self.BORDER)

        if self.b_type == "Sales":
            po_btn = tk.Button(self.left_tools, text="📑 Generate PO", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: generate_purchase_order(self))
            po_btn.pack(side="left", padx=(0, 10)); add_hover(po_btn, self.CARD, self.BORDER)

        import_csv_btn = tk.Button(self.left_tools, text="⭳ Import CSV", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: trigger_csv_import(self))
        import_csv_btn.pack(side="left", padx=(0, 10)); add_hover(import_csv_btn, self.CARD, self.BORDER)

        export_csv_btn = tk.Button(self.left_tools, text="⭳  Export CSV", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_csv(self))
        export_csv_btn.pack(side="left", padx=(0, 10)); add_hover(export_csv_btn, self.CARD, self.BORDER)

        export_pdf_btn = tk.Button(self.left_tools, text="🖨  Export PDF", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_pdf(self))
        export_pdf_btn.pack(side="left", padx=(0, 10)); add_hover(export_pdf_btn, self.CARD, self.BORDER)

        self.bulk_tools = tk.Frame(self.tool_bar, bg=self.BG)
        
        self.lbl_bulk_mode = tk.Label(self.bulk_tools, text="Selection Mode Active", font=("Arial", 11, "bold"), bg=self.BG, fg=self.DANGER)
        self.lbl_bulk_mode.pack(side="left", padx=(0, 15))
        
        self.btn_select_all = tk.Button(self.bulk_tools, text="☑ Select Visible", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=self.toggle_select_all)
        self.btn_select_all.pack(side="left", padx=(0, 10)); add_hover(self.btn_select_all, self.CARD, self.BORDER)

        self.btn_cancel_bulk = tk.Button(self.bulk_tools, text="Cancel", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=self.cancel_bulk_mode)
        self.btn_cancel_bulk.pack(side="left", padx=(0, 10)); add_hover(self.btn_cancel_bulk, self.CARD, self.BORDER)
        
        self.btn_bulk_delete = tk.Button(self.bulk_tools, text="🗑 Confirm Delete", font=("Arial", 10, "bold"), bg=self.DANGER, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.confirm_bulk_delete)
        self.btn_bulk_po = tk.Button(self.bulk_tools, text="📑 Generate PO", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: generate_purchase_order(self))
        self.btn_bulk_export_pdf = tk.Button(self.bulk_tools, text="🖨️ Export PDF", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_pdf(self))
        self.btn_bulk_export_csv = tk.Button(self.bulk_tools, text="⭳ Export CSV", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_csv(self))
        
        add_hover(self.btn_bulk_po, self.CARD, self.BORDER)
        add_hover(self.btn_bulk_export_pdf, self.CARD, self.BORDER)
        add_hover(self.btn_bulk_export_csv, self.CARD, self.BORDER)

        pag_frame = tk.Frame(main_container, bg=self.BG); pag_frame.pack(side="bottom", fill="x", pady=(10, 0))
        center_pag = tk.Frame(pag_frame, bg=self.BG); center_pag.pack(anchor="center") 
        self.btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", command=self.prev_page, padx=12, pady=3)
        self.btn_prev.pack(side="left", padx=5)
        self.lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG)
        self.lbl_page.pack(side="left", padx=15)
        self.btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", command=self.next_page, padx=12, pady=3)
        self.btn_next.pack(side="left", padx=5)

        table_frame = tk.Frame(main_container, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        table_frame.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", style="Stock.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", style="Stock.Horizontal.TScrollbar")

        columns = ("sno_sel", "item", "added", "loss", "sold", "net", "unit", "total", "actions", "ghost") if self.b_type == "Sales" else ("sno_sel", "item", "added", "loss", "net", "unit", "total", "actions", "ghost")

        # --- THE FIX: Lock visual height to 15 so scrollbar works perfectly for the 50 items! ---
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Stock.Treeview")
        
        # --- THE FIX: Two-Way Scroll Binding ---
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        # ---------------------------------------

        for col in columns: 
            if col == "ghost": self.tree.heading(col, text="", anchor="center")
            else: self.tree.heading(col, text=col.upper().replace("_SEL","").replace("SNO", "S.No").replace("ITEM", "ITEM NAME").replace("TOTAL", "NET VALUE").replace("ACTIONS", "ACTIONS"), anchor="center")
        self.tree.heading("item", anchor="center") 

        try:
            raw_setting = database.get_ui_setting(f"stock_main_cols_{self.comp_id}", "{}")
            w_dict = json.loads(raw_setting) if raw_setting else {}
        except Exception:
            w_dict = {}

        self.tree.column("sno_sel", width=w_dict.get("sno_sel", 60), minwidth=30, stretch=False, anchor="center")
        self.tree.column("item", width=w_dict.get("item", 180 if self.b_type == "Sales" else 240), minwidth=100, stretch=False, anchor="w")
        self.tree.column("added", width=w_dict.get("added", 80), minwidth=30, stretch=False, anchor="center")
        self.tree.column("loss", width=w_dict.get("loss", 80), minwidth=30, stretch=False, anchor="center")
        if self.b_type == "Sales": self.tree.column("sold", width=w_dict.get("sold", 80), minwidth=30, stretch=False, anchor="center")
        self.tree.column("net", width=w_dict.get("net", 80), minwidth=30, stretch=False, anchor="center")
        self.tree.column("unit", width=w_dict.get("unit", 70), minwidth=30, stretch=False, anchor="center")
        self.tree.column("total", width=w_dict.get("total", 120), minwidth=30, stretch=False, anchor="center")
        
        self.tree.column("actions", width=w_dict.get("actions", 100), minwidth=65, stretch=False, anchor="center")
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)
        
        def save_main_widths():
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c != "ghost"}
            try:
                import json
                database.save_ui_setting(f"stock_main_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_main_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_main_widths)

        self.tree.bind("<B1-Motion>", on_main_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after(50, save_main_widths) if self.tree.identify_region(e.x, e.y) == "separator" else None, add="+")

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)

        self.tree.tag_configure("evenrow", background=self.BG, foreground=self.FG)
        self.tree.tag_configure("oddrow", background=self.CARD, foreground=self.FG)
        self.tree.tag_configure("hover", background=self.HOVER_ROW) 
        self.tree.tag_configure("selected_row", background=self.BORDER)
        
        self.tree.tag_configure("low_stock_1", background=self.LOW_STOCK_BG_1, foreground=self.DANGER if not self.is_dark else self.YELLOW, font=("Arial", 10, "bold"))
        self.tree.tag_configure("low_stock_2", background=self.LOW_STOCK_BG_2, foreground=self.DANGER if not self.is_dark else self.YELLOW, font=("Arial", 10, "bold"))

        self.tree.bind("<ButtonPress-1>", self.on_tree_bg_click)
        self.tree.bind("<ButtonRelease-1>", self.on_left_click)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Return>", self.on_double_click) 
        self.tree.bind("<Motion>", self.custom_hover_motion)
        self.tree.bind("<Leave>", self.custom_hover_leave)
        
        # --- THE FIX: Hard lock physically forbids empty padding rows from holding a selection! ---
        def enforce_selection(e):
            for i in self.tree.selection():
                if str(i).startswith("empty_"): self.tree.selection_remove(i)
        self.tree.bind("<<TreeviewSelect>>", enforce_selection)
        # ------------------------------------------------------------------------------------------
        
        def _fast_scroll(event, direction, target_tree):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                target_tree.yview_moveto(target_tree.yview()[0] + (delta * 0.008))
            else:
                target_tree.xview_moveto(target_tree.xview()[0] + (delta * 0.02))

        self.tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y", self.tree))
        self.tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x", self.tree))
        
        def drop_focus(event):
            try:
                w_class = event.widget.winfo_class()
                if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button', 'Treeview', 'Scrollbar', 'TScrollbar'):
                    self.focus_set()
                    # --- THE FIX: Wipe the table highlight when clicking ANYWHERE away from the table! ---
                    if self.tree.selection():
                        self.tree.selection_remove(self.tree.selection())
            except: pass

        self.bind("<ButtonPress-1>", drop_focus, add="+")
        main_container.bind("<ButtonPress-1>", drop_focus, add="+")
        header_f.bind("<ButtonPress-1>", drop_focus, add="+")
        tiles_f.bind("<ButtonPress-1>", drop_focus, add="+")
        filter_bar.bind("<ButtonPress-1>", drop_focus, add="+")
        self.tool_bar.bind("<ButtonPress-1>", drop_focus, add="+")
        table_frame.bind("<ButtonPress-1>", drop_focus, add="+")

        self.load_data()

    def push_undo(self, act):
        self.undo_stack.append(act)
        if len(self.undo_stack) > 20: self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_btns()
        
    def update_undo_btns(self):
        if self.undo_stack:
            self.btn_undo.config(bg=self.CARD, fg=self.BLUE, state="normal", cursor="hand2", relief="solid", bd=1, command=self.exec_undo)
            add_hover(self.btn_undo, self.CARD, self.BORDER)
        else:
            self.btn_undo.config(bg=self.BG, fg=self.SEC_FG, state="disabled", cursor="", relief="solid", bd=1)
            self.btn_undo.unbind("<Enter>"); self.btn_undo.unbind("<Leave>")
            
        if self.redo_stack:
            self.btn_redo.config(bg=self.CARD, fg=self.BLUE, state="normal", cursor="hand2", relief="solid", bd=1, command=self.exec_redo)
            add_hover(self.btn_redo, self.CARD, self.BORDER)
        else:
            self.btn_redo.config(bg=self.BG, fg=self.SEC_FG, state="disabled", cursor="", relief="solid", bd=1)
            self.btn_redo.unbind("<Enter>"); self.btn_redo.unbind("<Leave>")
            
    def exec_undo(self, e=None):
        if not self.undo_stack: return
        act = self.undo_stack.pop()
        self.redo_stack.append(act)
        
        if act['type'] == 'delete_stock':
            database.restore_stock_records(act['records'])
            
        self.update_undo_btns(); self.load_data()

    def exec_redo(self, e=None):
        if not self.redo_stack: return
        act = self.redo_stack.pop()
        self.undo_stack.append(act)
        
        if act['type'] == 'delete_stock':
            for r in act['records']:
                database.delete_single_stock_record(r[0])
                
        self.update_undo_btns(); self.load_data()

    def get_parsed_data(self, ignore_filters=False):
        # --- THE FIX: MVC Compliant Fetch (No raw SQL in UI) ---
        raw = database.get_company_stock_raw(self.comp_id)
        
        inventory = {}

        for r in raw:
            name, qty, unit, price, t_type, notes_raw = r[1], r[2], r[3], r[4], r[5], r[6]
            date_str = r[7] if len(r) > 7 else None
            
            if name not in inventory:
                inventory[name] = {'added':0, 'loss':0, 'sold':0, 'net':0, 'unit':unit, 'adds':[], 'latest_price':price, 'reorder':5, 'dep_rate':0.0, 'first_date':None, 'loss_val':0.0, 'sold_val':0.0}

            try: j = json.loads(notes_raw)
            except: j = {}
            
            if "reorder_level" in j: inventory[name]['reorder'] = float(j["reorder_level"])
            if "depreciation" in j: inventory[name]['dep_rate'] = float(j["depreciation"])
            
            if t_type == 'ADD': 
                inventory[name]['latest_price'] = price
                if date_str:
                    from datetime import datetime
                    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                        try:
                            parsed_d = datetime.strptime(str(date_str).strip(), fmt).date()
                            if not inventory[name]['first_date'] or parsed_d < inventory[name]['first_date']:
                                inventory[name]['first_date'] = parsed_d
                            break
                        except: pass

            if t_type == 'ADD':
                inventory[name]['added'] += qty
                inventory[name]['net'] += qty
                inventory[name]['adds'].append({'qty': qty, 'price': price})
            else:
                rem = qty; cost = 0.0
                for a in inventory[name]['adds']:
                    if a['qty'] > 0:
                        if a['qty'] >= rem:
                            a['qty'] -= rem; cost += rem * a['price']; rem = 0; break
                        else:
                            rem -= a['qty']; cost += a['qty'] * a['price']; a['qty'] = 0

                if t_type == 'LOSS': inventory[name]['loss'] += qty; inventory[name]['loss_val'] += cost; inventory[name]['net'] -= qty
                elif t_type == 'SOLD': inventory[name]['sold'] += qty; inventory[name]['sold_val'] += cost; inventory[name]['net'] -= qty

        parsed = []
        from datetime import date
        today = date.today()
        
        for name, data in inventory.items():
            # --- THE FIX: Calculate Live Prorated Net Book Value ---
            gross_val = 0.0
            if self.b_type == "Sales":
                gross_val = sum(a['qty'] * a['price'] for a in data['adds'])
            else:
                gross_val = data['net'] * data['latest_price']
                
            dep_amount = 0.0
            if data['dep_rate'] > 0 and data['first_date']:
                days_owned = (today - data['first_date']).days
                if days_owned > 0:
                    dep_factor = (data['dep_rate'] / 100.0) * (days_owned / 365.25)
                    if dep_factor > 1.0: dep_factor = 1.0
                    dep_amount = gross_val * dep_factor
                    
            net_val = gross_val - dep_amount
            # -------------------------------------------------------

            if self.b_type == "Sales":
                parsed.append([name, data['added'], data['loss'], data['sold'], data['net'], data['unit'], net_val, data['loss_val'], data['sold_val'], data['reorder']])
            else:
                parsed.append([name, data['added'], data['loss'], data['sold'], data['net'], data['unit'], net_val, data['loss'] * data['latest_price'], data['sold'] * data['latest_price'], data['reorder']])

        if not ignore_filters:
            search = self.search_var.get().lower()
            if search and search != "search stock...": parsed = [i for i in parsed if search in i[0].lower()]

            f = self.filter_var.get()
            if f == "A to Z": parsed.sort(key=lambda x: x[0].lower())
            elif f == "Z to A": parsed.sort(key=lambda x: x[0].lower(), reverse=True)
            elif f == "Highest Value": parsed.sort(key=lambda x: x[6], reverse=True)
            elif f == "Lowest Value": parsed.sort(key=lambda x: x[6])

            if self.show_low_stock_only:
                parsed = [i for i in parsed if i[4] <= i[9]]
        else:
            parsed.sort(key=lambda x: x[0].lower())

        return parsed

    def load_data(self, event=None):
        for item in self.tree.get_children(): self.tree.delete(item)
        
        item_list = self.get_parsed_data()
        self.total_pages = max(1, (len(item_list) + self.items_per_page - 1) // self.items_per_page)
        if self.current_page > self.total_pages: self.current_page = max(1, self.total_pages)

        start_idx = (self.current_page - 1) * self.items_per_page
        page_items = item_list[start_idx : start_idx + self.items_per_page]

        self.lbl_page.config(text=f"Page {self.current_page} of {self.total_pages}")
        self.btn_prev.config(state="normal" if self.current_page > 1 else "disabled", bg=self.CARD if self.current_page > 1 else self.BG)
        self.btn_next.config(state="normal" if self.current_page < self.total_pages else "disabled", bg=self.CARD if self.current_page < self.total_pages else self.BG)

        for index, i in enumerate(page_items):
            name, add, loss, sold, net, unit, n_val, l_val, s_val, reorder = i

            is_sel = name in self.selected_items
            col1 = ("☑" if is_sel else "☐") if self.is_bulk_mode else (start_idx + index + 1)
            
            if is_sel and self.is_bulk_mode: tag = "selected_row"
            elif net <= reorder and self.b_type == "Sales": 
                tag = "low_stock_1" if index % 2 == 0 else "low_stock_2"
            else: tag = "evenrow" if index % 2 == 0 else "oddrow"

            vals = (col1, name, f"{add:g}", f"{loss:g}", f"{sold:g}", f"{net:g}", unit, format_currency(n_val, self.curr_fmt), "🔍 History", "") if self.b_type == "Sales" else (col1, name, f"{add:g}", f"{loss:g}", f"{net:g}", unit, format_currency(n_val, self.curr_fmt), "🔍 History", "")
            self.tree.insert("", "end", iid=name, values=vals, tags=(tag,))

        empty_tuple = ("", "", "", "", "", "", "", "", "", "") if self.b_type == "Sales" else ("", "", "", "", "", "", "", "", "")
        
        for i in range(len(page_items), self.items_per_page):
            self.tree.insert("", "end", iid=f"empty_{i}", values=empty_tuple, tags=("evenrow" if i % 2 == 0 else "oddrow", "empty"))

        self.tree.yview_moveto(0)
        
        t_net, t_loss, t_sold, low_count = 0.0, 0.0, 0.0, 0
        
        for t in item_list:
            t_net += t[6]
            t_loss += t[7]
            if self.b_type == "Sales": t_sold += t[8]
            
            net_qty = t[4]
            reorder_lvl = t[9]
            if net_qty <= reorder_lvl: low_count += 1
            
        allowed_fin, _ = database.check_stock_permission(action="view_financials", company_id=self.comp_id)
        
        if allowed_fin:
            self.lbl_net_stock.config(text=format_currency(t_net, self.curr_fmt))
            self.lbl_total_loss.config(text=format_currency(t_loss, self.curr_fmt))
            if self.b_type == "Sales": 
                self.lbl_total_sold.config(text=format_currency(t_sold, self.curr_fmt))
        else:
            self.lbl_net_stock.config(text="🔒 Hidden")
            self.lbl_total_loss.config(text="🔒 Hidden")
            if self.b_type == "Sales": 
                self.lbl_total_sold.config(text="🔒 Hidden")
                
        self.lbl_total_items.config(text=str(len(item_list))) 
        if self.b_type == "Sales": 
            self.lbl_low_stock_alert.config(text=str(low_count))

    def prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self.load_data()
    def next_page(self):
        if hasattr(self, 'total_pages') and self.current_page < self.total_pages: self.current_page += 1; self.load_data()

    def enable_bulk_mode(self, mode_type, initial_item=None):
        self.is_bulk_mode = True
        self.bulk_mode_type = mode_type
        self.selected_items.clear()
        if initial_item: self.selected_items.add(initial_item)
        
        self.std_tools.pack_forget()
        self.bulk_tools.pack(fill="both", expand=True)
        
        self.btn_bulk_delete.pack_forget()
        self.btn_bulk_po.pack_forget()
        self.btn_bulk_export_csv.pack_forget()
        self.btn_bulk_export_pdf.pack_forget()
        
        if mode_type == "delete":
            self.lbl_bulk_mode.config(text="Delete Mode Active")
            self.btn_bulk_delete.pack(side="right")
        elif mode_type == "po":
            self.lbl_bulk_mode.config(text="PO Generation Mode Active")
            self.btn_bulk_po.pack(side="right")
        elif mode_type == "export":
            self.lbl_bulk_mode.config(text="Export Items Mode Active")
            self.btn_bulk_export_csv.pack(side="right", padx=(0,10))
            self.btn_bulk_export_pdf.pack(side="right")

        self.tree.heading("sno_sel", text="☑")
        self.update_bulk_action_btns()
        self.load_data()

    def cancel_bulk_mode(self):
        self.is_bulk_mode = False; self.bulk_mode_type = ""
        self.selected_items.clear()
        self.bulk_tools.pack_forget()
        self.std_tools.pack(fill="both", expand=True)
        self.tree.heading("sno_sel", text="S.No")
        self.load_data()

    def toggle_select_all(self):
        start = (self.current_page - 1) * self.items_per_page
        visible_names = set(i[0] for i in self.get_parsed_data()[start : start + self.items_per_page])
        if not visible_names: return
        if visible_names.issubset(self.selected_items): self.selected_items -= visible_names
        else: self.selected_items |= visible_names
        self.update_bulk_action_btns(); self.load_data()

    def update_bulk_action_btns(self):
        count = len(self.selected_items)
        self.btn_bulk_delete.config(text=f"🗑 Confirm Delete ({count})")
        self.btn_bulk_po.config(text=f"📑 Generate PO ({count})")
        self.btn_bulk_export_pdf.config(text=f"🖨️ Export PDF ({count})")
        self.btn_bulk_export_csv.config(text=f"⭳ Export CSV ({count})")

    def confirm_bulk_delete(self):
        if not self.selected_items: self.cancel_bulk_mode(); return
        
        allowed, err_msg = database.check_stock_permission(action="delete", company_id=self.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
            
        if messagebox.askyesno("Confirm Delete", f"Permanently delete ALL history for {len(self.selected_items)} selected items?"):
            deleted_records = []
            for name in list(self.selected_items):
                rows_to_save = database.get_stock_records_by_name(name)
                if rows_to_save:
                    deleted_records.extend(rows_to_save)
                database.delete_stock_by_name(name)
            
            database.log_audit("Stock", "Bulk Deleted", record_ref=f"{len(self.selected_items)} Items", details=f"Permanently wiped stock history for {len(self.selected_items)} items.", company_id=self.comp_id)
            self.push_undo({"type": "delete_stock", "records": deleted_records, "names": list(self.selected_items)})
            self.cancel_bulk_mode()
            self.load_data()

    def on_tree_bg_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        
        # --- THE FIX: Let the column separators pass through so you can resize headers! ---
        if region == "separator":
            return
        # ----------------------------------------------------------------------------------
            
        item = self.tree.identify_row(event.y)
        
        # --- THE FIX: Defeat Tkinter's stubborn selection ghosting race condition! ---
        if not item or str(item).startswith("empty_") or region == "nothing":
            # Using .after(10) guarantees our un-highlight happens LAST, beating Tkinter's default bindings.
            self.after(10, lambda: self.tree.selection_remove(self.tree.selection()) if self.tree.selection() else None)
            return "break"
        # -----------------------------------------------------------------------------

    def on_left_click(self, event):
        if self.tree.identify("region", event.x, event.y) == "cell":
            column = self.tree.identify_column(event.x)
            item_name = self.tree.identify_row(event.y)
            if not item_name or str(item_name).startswith("empty_"): return

            if self.is_bulk_mode:
                if item_name in self.selected_items: self.selected_items.remove(item_name)
                else: self.selected_items.add(item_name)
                
                vals = list(self.tree.item(item_name, "values"))
                vals[0] = "☑" if item_name in self.selected_items else "☐"
                self.tree.item(item_name, values=vals, tags=("selected_row" if item_name in self.selected_items else "evenrow",))
                self.update_bulk_action_btns()
                
            elif not self.is_bulk_mode and (column == '#8' or (self.b_type == "Sales" and column == '#9')): 
                open_history_popup(self, item_name)

    def on_right_click(self, event):
        item_name = self.tree.identify_row(event.y)
        if not item_name or str(item_name).startswith("empty_"): return
        self.tree.selection_set(item_name)
        
        menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD, fg=self.FG, activebackground=self.BLUE)
        if not self.is_bulk_mode:
            menu.add_command(label="🔍 History Ledger", command=lambda: open_history_popup(self, item_name))
            menu.add_command(label="✏️ Edit Item Details", command=lambda: self.open_edit_item_popup(item_name))
            menu.add_separator()
            # --- THE FIX: Cleaned up the menu labels ---
            menu.add_command(label="⭳ Export", command=lambda: self.export_single_item(item_name))
            menu.add_command(label="⭳ Bulk Export", command=lambda: self.enable_bulk_mode("export", item_name))
            if self.b_type == "Sales":
                menu.add_command(label="📑 Generate PO", command=lambda: self.enable_bulk_mode("po", item_name))
            menu.add_separator()
            menu.add_command(label="❌ Delete", command=lambda: self.delete_single_item(item_name), foreground=self.DANGER)
            # -------------------------------------------
            menu.add_command(label="🗑 Bulk Delete", command=lambda: self.enable_bulk_mode("delete", item_name), foreground=self.DANGER)
        else:
            menu.add_command(label="Cancel Selection", command=self.cancel_bulk_mode)
            
        menu.tk_popup(event.x_root, event.y_root)

    def export_single_item(self, item_name):
        old_mode = self.is_bulk_mode
        old_selected = set(self.selected_items)
        
        self.is_bulk_mode = True
        self.selected_items = {item_name}
        
        export_csv(self)
        
        self.is_bulk_mode = old_mode
        self.selected_items = old_selected

    def delete_single_item(self, item_name):
        allowed, err_msg = database.check_stock_permission(action="delete", company_id=self.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
            
        if messagebox.askyesno("Confirm Delete", f"Permanently delete ALL history for '{item_name}'?"):
            rows_to_save = database.get_stock_records_by_name(item_name)
            database.delete_stock_by_name(item_name)
            
            database.log_audit("Stock", "Item Deleted", record_ref=item_name, details=f"Permanently wiped all stock history for '{item_name}'.", company_id=self.comp_id)
            
            if rows_to_save:
                self.push_undo({"type": "delete_stock", "records": rows_to_save, "names": [item_name]})
            self.load_data()

    def open_edit_item_popup(self, old_name):
        popup = tk.Toplevel(self)
        popup.title(f"Edit Item: {old_name}")
        popup.configure(bg=self.CARD)
        popup.grab_set()
        
        popup.update_idletasks()
        # --- THE FIX: Made the popup taller to fit the new field ---
        w, h = 450, 420
        # -----------------------------------------------------------
        sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
        popup.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")
        
        tk.Label(popup, text="✏️ Edit Stock Item", font=("Arial", 16, "bold"), bg=self.CARD, fg=self.FG).pack(pady=(15, 15))
        
        form = tk.Frame(popup, bg=self.CARD)
        form.pack(fill="both", expand=True, padx=25)
        
        tk.Label(form, text="Item Name:", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(anchor="w")
        name_var = tk.StringVar(value=old_name)
        name_entry = tk.Entry(form, textvariable=name_var, font=("Arial", 11), bg=self.BG, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        name_entry.pack(fill="x", pady=(0, 15), ipady=4)
        name_entry.focus_set()
        
        info = database.get_latest_stock_info(old_name)
        current_unit = info[0] if info else "Numbers (Nos.)"
        
        tk.Label(form, text="Unit:", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(anchor="w")
        full_units = ["Numbers (Nos.)", "Kilograms (Kg)", "Pieces (Pcs)", "Packets (Pkts)", "Running Feet (Rft)", "Running Metre (Rmt)", "Square Feet (Sq.ft.)", "Bundles (Bdl.)"]
        unit_var = tk.StringVar(value=next((u for u in full_units if current_unit in u), full_units[0]))
        unit_combo = ttk.Combobox(form, textvariable=unit_var, values=full_units, state="readonly", style="Theme.TCombobox")
        unit_combo.pack(fill="x", pady=(0, 15), ipady=4)
        
        # --- THE FIX: MVC Compliant Reorder Level and Depreciation Fetch ---
        reorder_level = database.get_stock_reorder_level(old_name, self.comp_id)
        depreciation_rate = 0.0
        info = database.get_latest_stock_info(old_name)
        if info and info[2]:
            try:
                j = json.loads(info[2])
                if "depreciation" in j: depreciation_rate = float(j["depreciation"])
            except: pass
        # -------------------------------------------------------------------
            
        tk.Label(form, text="Low Stock Alert Level:", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(anchor="w")
        reorder_var = tk.StringVar(value=str(reorder_level))
        reorder_entry = tk.Entry(form, textvariable=reorder_var, font=("Arial", 11), bg=self.BG, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        reorder_entry.pack(fill="x", pady=(0, 15), ipady=4)
        
        # --- THE FIX: Inject the Depreciation Edit UI ---
        tk.Label(form, text="Depreciation % / Yr:", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(anchor="w")
        dep_var = tk.StringVar(value=str(depreciation_rate))
        dep_entry = tk.Entry(form, textvariable=dep_var, font=("Arial", 11), bg=self.BG, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        dep_entry.pack(fill="x", pady=(0, 15), ipady=4)
        # ------------------------------------------------
        
        def save_edit():
            new_name = name_var.get().strip()
            new_unit_full = unit_var.get().strip()
            new_unit = new_unit_full.split("(")[-1].replace(")", "").strip() if "(" in new_unit_full else new_unit_full
            
            if not new_name:
                messagebox.showerror("Error", "Item name cannot be empty.", parent=popup)
                return
                
            # Check if name is already taken
            if new_name.lower() != old_name.lower():
                if database.check_stock_name_exists(new_name):
                    messagebox.showerror("Error", "An item with this name already exists.", parent=popup)
                    return
                    
            database.update_stock_item_details(old_name, new_name, new_unit)
            
            # --- THE FIX: Bulk update both variables safely ---
            try: new_reorder = float(reorder_var.get())
            except: new_reorder = 0.0
            try: new_dep = float(dep_var.get())
            except: new_dep = 0.0
            
            database.bulk_update_stock_reorder_level(new_name, new_reorder)
            # --- THE FIX: MVC Compliant Bulk Depreciation Update ---
            database.bulk_update_stock_depreciation(new_name, new_dep, self.comp_id)
            # -------------------------------------------------------
                
            self.load_data()
            popup.destroy()
            
        btn_save = tk.Button(form, text="💾 Save Changes", font=("Arial", 11, "bold"), bg=self.GREEN, fg="#ffffff", relief="flat", cursor="hand2", command=save_edit)
        btn_save.pack(fill="x", pady=(5,0), ipady=3)
        
        popup.bind("<Return>", lambda e: save_edit())
        popup.bind("<Escape>", lambda e: popup.destroy())

    def on_double_click(self, event=None):
        if self.is_bulk_mode or not self.tree.selection(): return 
        item_name = self.tree.selection()[0]
        if not item_name or str(item_name).startswith("empty_"): return
        open_history_popup(self, item_name)

    def custom_hover_motion(self, e, target_tree=None):
        if target_tree is None: target_tree = self.tree
        item = target_tree.identify_row(e.y)
        if item != self._last_hovered:
            if self._last_hovered and target_tree.exists(self._last_hovered):
                tags = list(target_tree.item(self._last_hovered, "tags"))
                if "hover" in tags: tags.remove("hover"); target_tree.item(self._last_hovered, tags=tuple(tags))
            if item and not str(item).startswith("empty_"):
                tags = list(target_tree.item(item, "tags"))
                if "hover" not in tags: tags.append("hover"); target_tree.item(item, tags=tuple(tags))
            self._last_hovered = item
        target_tree.config(cursor="hand2" if item and not str(item).startswith("empty_") else "")

    def custom_hover_leave(self, e, target_tree=None):
        if target_tree is None: target_tree = self.tree
        if self._last_hovered and target_tree.exists(self._last_hovered):
            tags = list(target_tree.item(self._last_hovered, "tags"))
            if "hover" in tags: tags.remove("hover"); target_tree.item(self._last_hovered, tags=tuple(tags))
        self._last_hovered = None; target_tree.config(cursor="")