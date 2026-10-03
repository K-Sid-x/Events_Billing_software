# MODULE: Catalog (Managing items, rates, categories, and HSN codes)
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json

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
from views.invoice_parts.helpers import format_currency, fetch_global_settings, enable_copy_paste
from views.inventory_parts.inv_forms import open_form
from views.inventory_parts.inv_exports import export_csv, export_pdf, trigger_csv_import

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

class InventoryView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._last_hovered = None 
        self.current_page = 1
        # --- THE FIX: Increased pagination to 50 items per page ---
        self.items_per_page = 50
        # ----------------------------------------------------------
        self.sort_col = None
        self.sort_reverse = False
        
        self.is_bulk_mode = False
        self.selected_items = set() 
        
        self.undo_stack = []
        self.redo_stack = []
        
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        if self.is_dark:
            self.BG = "#0f172a"; self.CARD = "#1e293b"; self.BORDER = "#334155"; self.FG = "#f8fafc"
            self.SEC_FG = "#94a3b8"; self.HEADER = "#475569"; self.BLUE = "#3b82f6"; self.BTN_HOVER = "#2563eb"
            self.HOVER_ROW = "#334155"; self.DANGER = "#ef4444"; self.FOCUS_BG = "#475569" 
        else:
            self.BG = "#e0f2fe"; self.CARD = "#f0f9ff"; self.BORDER = "#7dd3fc"; self.FG = "#0f172a"
            self.SEC_FG = "#0284c7"; self.HEADER = "#bae6fd"; self.BLUE = "#0ea5e9"; self.BTN_HOVER = "#0284c7"
            self.HOVER_ROW = "#bae6fd"; self.DANGER = "#ef4444"; self.FOCUS_BG = "#fef9c3" 

        self.GREEN = "#10b981"
        self.config(bg=self.BG)
        
        # --- THE FIX: Hard-Locked Company Identification ---
        self.has_gst = False
        try:
            self.app = self.winfo_toplevel()
            self.comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
            
            # --- THE FIX: MVC Compliant GST Fetch ---
            self.has_gst = database.get_company_gst_toggle(self.comp_id)
            # ----------------------------------------
        except:
            self.comp_id = 1
            self.curr_fmt, self.date_fmt_code = "Indian Rupees (₹)", "%Y-%m-%d"
            
        self.build_ui()

    def push_undo(self, act):
        self.undo_stack.append(act)
        if len(self.undo_stack) > 20: self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_btns()
        
    def update_undo_btns(self):
        # --- THE FIX: Sleek borders ALWAYS visible & Blue Highlight when active ---
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
        
        # --- THE FIX: Secure Multi-Company Undo Lock ---
        database.set_active_company(self.comp_id)
        # -----------------------------------------------
        
        if act['type'] == 'delete_main':
            new_ids = []
            # --- THE FIX: Use safe helper for Undo insertions instead of raw SQL! ---
            for item in act['items']:
                packed = json.dumps({"desc": item['desc'], "unit": item['unit'], "hsn": item['hsn'], "category": item['category']})
                new_id = database.add_inventory(item['name'], item['unit'], item['rate'], packed)
                new_ids.append(new_id)
            act['new_ids'] = new_ids
            # ------------------------------------------------------------------------
            
        elif act['type'] == 'edit_main':
            o = act['old']
            packed = json.dumps({"desc": o['desc'], "unit": o['unit'], "hsn": o['hsn'], "category": o['category']})
            self.safe_db_add(o['name'], o['unit'], o['rate'], packed, act['id'])
            
        self.update_undo_btns(); self.load_data()

    def exec_redo(self, e=None):
        if not self.redo_stack: return
        act = self.redo_stack.pop()
        self.undo_stack.append(act)
        
        # --- THE FIX: Secure Multi-Company Redo Lock ---
        database.set_active_company(self.comp_id)
        # -----------------------------------------------
        
        if act['type'] == 'delete_main':
            # --- THE FIX: Use safe helper for Redo deletions instead of raw SQL! ---
            for nid in act.get('new_ids', []):
                database.delete_inventory(nid)
            # -----------------------------------------------------------------------
                
        elif act['type'] == 'edit_main':
            n = act['new']
            packed = json.dumps({"desc": n['desc'], "unit": n['unit'], "hsn": n['hsn'], "category": n['category']})
            self.safe_db_add(n['name'], n['unit'], n['rate'], packed, act['id'])
            
        self.update_undo_btns(); self.load_data()

    def treeview_sort_column(self, col):
        if col in ["actions", "sno_sel"]: return 
        if self.sort_col == col: self.sort_reverse = not self.sort_reverse
        else: self.sort_col = col; self.sort_reverse = False
        self.current_page = 1 
        self.load_data()

    def build_ui(self):
        style = ttk.Style(self); style.theme_use("default")
        self.app.option_add("*TCombobox*Listbox.background", self.CARD)
        self.app.option_add("*TCombobox*Listbox.foreground", self.FG)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("Theme.TCombobox", fieldbackground=self.CARD, background=self.CARD, foreground=self.FG, arrowcolor=self.FG, bordercolor=self.BORDER)
        style.map("Theme.TCombobox", fieldbackground=[("readonly", "focus", self.FOCUS_BG), ("readonly", self.CARD)], selectbackground=[("readonly", self.CARD)], selectforeground=[("readonly", self.FG)])
        
        # --- THE FIX: Thick, Modern Labours-Style Scrollbars ---
        style.configure("Theme.Vertical.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.configure("Theme.Horizontal.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.map("Theme.Vertical.TScrollbar", background=[("active", self.BLUE)])
        style.map("Theme.Horizontal.TScrollbar", background=[("active", self.BLUE)])
        # -------------------------------------------------------
        
        style.configure("Inv.Treeview.Heading", font=("Arial", 10, "bold"), background=self.HEADER, foreground=self.FG, borderwidth=1, relief="raised", bordercolor=self.BORDER)
        style.map("Inv.Treeview.Heading", background=[('active', self.BORDER)])
        # --- THE FIX: Increased data font size to 12 and row height to 38 ---
        style.configure("Inv.Treeview", font=("Arial", 12), rowheight=38, background=self.CARD, fieldbackground=self.CARD, foreground=self.FG, borderwidth=0)
        # --------------------------------------------------------------------
        style.map("Inv.Treeview", background=[("selected", self.BLUE)], foreground=[("selected", "#ffffff")])

        # --- THE FIX: Removed the 30px padding to stretch the tab edge-to-edge like Invoices! ---
        main_container = tk.Frame(self, bg=self.BG)
        main_container.pack(fill="both", expand=True)
        # ----------------------------------------------------------------------------------------

        header_f = tk.Frame(main_container, bg=self.BG); header_f.pack(side="top", fill="x", pady=(0, 20))
        
        title_frame = tk.Frame(header_f, bg=self.BG); title_frame.pack(side="left")
        tk.Label(title_frame, text="Catalog Master", font=("Arial", 28, "bold"), bg=self.BG, fg=self.FG).pack(anchor="w")
        tk.Label(title_frame, text="Manage catalog items, categories, rates and HSN codes.", font=("Arial", 11), bg=self.BG, fg=self.SEC_FG).pack(anchor="w", pady=(5, 0))

        self.summary_card = tk.Frame(header_f, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, padx=25, pady=5)
        
        # --- THE FIX: Moved from right edge to sit next to the title (above the A-to-Z filter) ---
        self.summary_card.pack(side="left", padx=(50, 0), anchor="s", pady=(0, 5))
        # -----------------------------------------------------------------------------------------
        
        tk.Label(self.summary_card, text="TOTAL ITEMS", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG).pack(anchor="center")
        self.lbl_total_items = tk.Label(self.summary_card, text="0", font=("Arial", 22, "bold"), bg=self.CARD, fg=self.BLUE)
        self.lbl_total_items.pack(anchor="center")

        self.undo_redo_frame = tk.Frame(header_f, bg=self.BG)
        self.undo_redo_frame.pack(side="right", anchor="center", padx=20)
        
        self.btn_undo = tk.Button(self.undo_redo_frame, text="⟲ Undo", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG, relief="solid", bd=1, padx=10, pady=3, command=self.exec_undo, state="disabled")
        self.btn_undo.pack(side="left", padx=5)
        
        self.btn_redo = tk.Button(self.undo_redo_frame, text="⟳ Redo", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG, relief="solid", bd=1, padx=10, pady=3, command=self.exec_redo, state="disabled")
        self.btn_redo.pack(side="left", padx=5)
        
        # --- THE FIX: Smart Keybind Garbage Collection (Stops the Ghost Undo Crash) ---
        def bind_undo_keys(e=None):
            self.app.bind("<Control-z>", self.exec_undo); self.app.bind("<Control-Z>", self.exec_undo)
            self.app.bind("<Control-y>", self.exec_redo); self.app.bind("<Control-Y>", self.exec_redo)
            
        def unbind_undo_keys(e=None):
            self.app.unbind("<Control-z>"); self.app.unbind("<Control-Z>")
            self.app.unbind("<Control-y>"); self.app.unbind("<Control-Y>")

        self.bind("<Map>", bind_undo_keys)
        self.bind("<Unmap>", unbind_undo_keys)
        self.bind("<Destroy>", lambda e: unbind_undo_keys() if e.widget == self else None, add="+")
        
        bind_undo_keys() # Bind immediately on load
        # ------------------------------------------------------------------------------

        filter_bar = tk.Frame(main_container, bg=self.BG); filter_bar.pack(fill="x", pady=(0, 10))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(filter_bar, textvariable=self.search_var, font=("Arial", 11), width=30, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        search_entry.pack(side="left", ipady=4); search_entry.insert(0, "Search Catalog...")
        search_entry.bind("<FocusIn>", lambda args: search_entry.delete('0', 'end') if search_entry.get() == 'Search Catalog...' else None)
        search_entry.bind("<FocusOut>", lambda args: search_entry.insert(0, 'Search Catalog...') if not search_entry.get() else None)
        search_entry.bind("<KeyRelease>", self.on_search); search_entry.bind("<Return>", lambda e: self.tree.focus_set())
        self.app.bind("<Control-f>", lambda e: [search_entry.focus_set(), search_entry.select_range(0, tk.END)])

        # --- THE FIX: ADD CLEAR BUTTON ---
        btn_clear = tk.Button(filter_bar, text="✖", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.DANGER, relief="flat", cursor="hand2", command=lambda: [self.search_var.set("Search Catalog..."), self.tree.focus_set(), self.load_data()])
        btn_clear.pack(side="left", padx=(0, 10), ipady=3)
        add_hover(btn_clear, self.CARD, self.BORDER)

        self.cat_filter_var = tk.StringVar(value="All Categories")
        cat_filter_cb = ttk.Combobox(filter_bar, textvariable=self.cat_filter_var, values=["All Categories", "General", "Services", "Electronics", "Furniture", "Hardware", "Clothing", "Food & Bev", "Other"], font=("Arial", 10), state="readonly", style="Theme.TCombobox", width=15, cursor="hand2")
        cat_filter_cb.pack(side="left", padx=(10, 0), ipady=3); cat_filter_cb.bind("<<ComboboxSelected>>", self.on_search)

        # --- THE FIX: DEFAULT SORT A TO Z ---
        self.sort_var = tk.StringVar(value="A to Z")
        sort_dropdown = ttk.Combobox(filter_bar, textvariable=self.sort_var, values=["A to Z", "Z to A", "Latest Added", "Rate: Low to High", "Rate: High to Low"], font=("Arial", 10), state="readonly", style="Theme.TCombobox", width=18, cursor="hand2")
        sort_dropdown.pack(side="left", padx=(10, 0), ipady=3)
        # --- THE FIX: Clear column sorting override when dropdown is used ---
        sort_dropdown.bind("<<ComboboxSelected>>", lambda e: [setattr(self, 'sort_col', None), self.on_search(e)])
        # --------------------------------------------------------------------

        self.tool_bar = tk.Frame(main_container, bg=self.BG); self.tool_bar.pack(fill="x", pady=(0, 15))

        self.std_tools = tk.Frame(self.tool_bar, bg=self.BG); self.std_tools.pack(fill="both", expand=True)

        # --- THE FIX: Visual Layout -> [Import CSV] [Export CSV] [Export PDF] [Add Item] ---
        add_btn = tk.Button(self.std_tools, text="➕ Add Item", font=("Arial", 10, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_form(self))
        add_btn.pack(side="right"); add_hover(add_btn, self.BLUE, self.BTN_HOVER)

        export_pdf_btn = tk.Button(self.std_tools, text="🖨  Export PDF", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_pdf(self))
        export_pdf_btn.pack(side="right", padx=(0, 10)); add_hover(export_pdf_btn, self.CARD, self.BORDER)

        export_csv_btn = tk.Button(self.std_tools, text="⭳  Export CSV", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: export_csv(self))
        export_csv_btn.pack(side="right", padx=(0, 10)); add_hover(export_csv_btn, self.CARD, self.BORDER)
        
        import_csv_btn = tk.Button(self.std_tools, text="⬆  Import CSV", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: trigger_csv_import(self))
        import_csv_btn.pack(side="right", padx=(0, 10)); add_hover(import_csv_btn, self.CARD, self.BORDER)
        # -----------------------------------------------------------------------------------

        self.bulk_tools = tk.Frame(self.tool_bar, bg=self.BG)
        
        # --- THE FIX: Swap packing order so Cancel is on the far right ---
        btn_cancel_bulk = tk.Button(self.bulk_tools, text="Cancel", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=self.cancel_bulk_mode)
        btn_cancel_bulk.pack(side="right"); add_hover(btn_cancel_bulk, self.CARD, self.BORDER)

        self.btn_confirm_delete = tk.Button(self.bulk_tools, text="🗑 Confirm Delete", font=("Arial", 10, "bold"), bg=self.DANGER, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.confirm_bulk_delete)
        self.btn_confirm_delete.pack(side="right", padx=(0, 10))

        btn_select_all = tk.Button(self.bulk_tools, text="☑ Select All Visible", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=self.toggle_select_all)
        btn_select_all.pack(side="right", padx=(0, 10)); add_hover(btn_select_all, self.CARD, self.BORDER)
        # -----------------------------------------------------------------

        tk.Label(self.bulk_tools, text="Selection Mode Active", font=("Arial", 12, "bold"), bg=self.BG, fg=self.DANGER).pack(side="left")

        pag_frame = tk.Frame(main_container, bg=self.BG); pag_frame.pack(side="bottom", fill="x", pady=(10, 0))
        center_pag = tk.Frame(pag_frame, bg=self.BG); center_pag.pack(anchor="center") 
        
        self.btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", command=self.prev_page, padx=12, pady=3)
        self.btn_prev.pack(side="left", padx=5)
        add_hover(self.btn_prev, self.CARD, self.BORDER) 
        
        self.lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=self.BG, fg=self.SEC_FG)
        self.lbl_page.pack(side="left", padx=15)
        
        self.btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", command=self.next_page, padx=12, pady=3)
        self.btn_next.pack(side="left", padx=5)
        add_hover(self.btn_next, self.CARD, self.BORDER) 

        table_frame = tk.Frame(main_container, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        table_frame.pack(side="top", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", style="Theme.Vertical.TScrollbar")
        # --- THE FIX: Apply the custom style to the horizontal scrollbar ---
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", style="Theme.Horizontal.TScrollbar")
        # ------------------------------------------------------------------
        
        # --- THE FIX: Added 'ghost' to the column array ---
        if self.has_gst:
            self.columns = ("sno_sel", "name", "category", "unit", "hsn", "rate", "actions", "ghost")
        else:
            self.columns = ("sno_sel", "name", "category", "unit", "rate", "actions", "ghost")
            
        # --- THE FIX: Hardcoded visual height to 12 rows so a 50-item page fits on your monitor perfectly ---
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", height=12, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Inv.Treeview")
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        self.tree.heading("sno_sel", text="S.No", anchor="center") 
        self.tree.heading("name", text="ITEM NAME", anchor="center", command=lambda: self.treeview_sort_column("name"))
        self.tree.heading("category", text="CATEGORY", anchor="center", command=lambda: self.treeview_sort_column("category"))
        self.tree.heading("unit", text="UNIT", anchor="center")
        if self.has_gst:
            self.tree.heading("hsn", text="HSN / SAC", anchor="center")
        self.tree.heading("rate", text="RATE / UNIT", anchor="center", command=lambda: self.treeview_sort_column("rate"))
        self.tree.heading("actions", text="ACTIONS", anchor="center")
        self.tree.heading("ghost", text="")

        # --- THE FIX: MVC Compliant Column Width Fetch ---
        try:
            raw_setting = database.get_ui_setting("inv_grid_cols", "{}")
            w_dict = json.loads(raw_setting) if raw_setting else {}
        except:
            w_dict = {}
        # -------------------------------------------------

        self.tree.column("sno_sel", width=w_dict.get("sno_sel", 60), minwidth=40, stretch=False, anchor="center")
        self.tree.column("name", width=w_dict.get("name", 250), minwidth=150, stretch=False, anchor="w")
        self.tree.column("category", width=w_dict.get("category", 120), minwidth=100, stretch=False, anchor="center")
        self.tree.column("unit", width=w_dict.get("unit", 80), minwidth=50, stretch=False, anchor="center")
        if self.has_gst:
            self.tree.column("hsn", width=w_dict.get("hsn", 120), minwidth=80, stretch=False, anchor="center")
        self.tree.column("rate", width=w_dict.get("rate", 120), minwidth=80, stretch=False, anchor="e")
        
        # --- THE FIX: Lock actions, Stretch ghost ---
        self.tree.column("actions", width=w_dict.get("actions", 120), minwidth=100, stretch=False, anchor="center") 
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)
        # ------------------------------------------------- 
        
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.tree.tag_configure("evenrow", background=self.BG, foreground=self.FG)
        self.tree.tag_configure("oddrow", background=self.CARD, foreground=self.FG)
        self.tree.tag_configure("hover", background=self.HOVER_ROW) 
        self.tree.tag_configure("selected_row", background=self.BORDER)

        # --- THE FIX: Universal Focus & Highlight Dropper ---
        def clear_focus(event):
            # Only trigger if the click happened inside the Inventory tab
            if str(event.widget).startswith(str(self)):
                try:
                    w_class = event.widget.winfo_class()
                    # If clicking on the background (not a button, entry, or table)
                    if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button', 'Treeview'):
                        self.focus_set() # Removes the typing cursor from the search bar
                        # Removes the blue table highlight (unless we are in bulk selection mode)
                        if self.tree.selection() and not getattr(self, 'is_bulk_mode', False):
                            self.tree.selection_remove(self.tree.selection())
                except: pass
            
        self.bind_all("<ButtonPress-1>", clear_focus, add="+")
        # ----------------------------------------------------

        # --- THE FIX: Real-time width saving during separator drag ---
        def save_widths():
            # Exclude the ghost column from saving
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c != "ghost"}
            try:
                # --- THE FIX: Let the database engine handle the security stamp! ---
                database.save_ui_setting("inv_grid_cols", json.dumps(new_w))
                # -------------------------------------------------------------------
            except: pass

        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_widths)
                
        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after(50, save_widths) if self.tree.identify_region(e.x, e.y) == "separator" else None, add="+")
        # -------------------------------------------------------------

        self.tree.bind("<ButtonPress-1>", self.on_tree_bg_click)
        self.tree.bind("<ButtonRelease-1>", self.on_left_click, add="+")
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Return>", self.on_double_click) 
        self.tree.bind("<Motion>", self.custom_hover_motion)
        self.tree.bind("<Leave>", self.custom_hover_leave)

        self.load_data()

    def enable_bulk_mode(self, initial_row_id=None):
        self.is_bulk_mode = True; self.selected_items.clear()
        if initial_row_id: self.selected_items.add(int(initial_row_id))
        self.std_tools.pack_forget(); self.bulk_tools.pack(fill="both", expand=True)
        self.tree.heading("sno_sel", text="☑")
        self.update_bulk_delete_btn(); self.load_data()

    def cancel_bulk_mode(self):
        self.is_bulk_mode = False; self.selected_items.clear()
        self.bulk_tools.pack_forget(); self.std_tools.pack(fill="both", expand=True)
        self.tree.heading("sno_sel", text="S.No")
        self.load_data()

    def toggle_select_all(self):
        parsed = self.get_parsed_data()
        start_idx = (self.current_page - 1) * self.items_per_page
        visible_items = parsed[start_idx : start_idx + self.items_per_page]
        visible_ids = set(p['id'] for p in visible_items)
        if not visible_ids: return
        if visible_ids.issubset(self.selected_items): self.selected_items -= visible_ids
        else: self.selected_items |= visible_ids
        self.update_bulk_delete_btn(); self.load_data()

    def update_bulk_delete_btn(self):
        count = len(self.selected_items)
        self.btn_confirm_delete.config(text=f"🗑 Confirm Delete ({count})")

    def confirm_bulk_delete(self):
        if not self.selected_items: self.cancel_bulk_mode(); return
        
        allowed, err_msg = database.check_catalog_permission(action="delete", company_id=self.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
            
        if messagebox.askyesno("Confirm Delete", f"Permanently delete {len(self.selected_items)} selected items?"):
            deleted_items = []
            parsed = self.get_parsed_data()
            
            for item_id in list(self.selected_items):
                item_data = next((p for p in parsed if p['id'] == item_id), None)
                if item_data: deleted_items.append(item_data)
                # --- THE FIX: Route deletions securely through the backend ---
                database.delete_inventory(item_id)
                # -------------------------------------------------------------
                
            database.log_audit("Catalog", "Permanently Deleted", record_ref=f"{len(deleted_items)} Items", details=f"Deleted {len(deleted_items)} items from the catalog.", company_id=self.comp_id)
            self.push_undo({"type": "delete_main", "items": deleted_items})
            self.cancel_bulk_mode()

    # --- THE FIX: Use the secure database helper instead of raw UI SQL! ---
    def safe_db_add(self, name, unit, rate, packed_desc, item_id=None):
        database.set_active_company(self.comp_id)
        return database.upsert_inventory(name, unit, rate, packed_desc, item_id)
    # ----------------------------------------------------------------------

    def on_search(self, event=None):
        self.current_page = 1; self.load_data()

    def prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self.load_data()

    def next_page(self):
        if hasattr(self, 'total_pages') and self.current_page < self.total_pages: self.current_page += 1; self.load_data()

    # --- THE FIX: MVC Compliant Inventory Fetch ---
    def get_parsed_data(self):
        database.set_active_company(self.comp_id)
        all_items = database.get_all_inventory()
        # Sort manually here to preserve the descending ID order
        all_items.sort(key=lambda x: x[0], reverse=True)
        # ----------------------------------------------
        
        search = self.search_var.get().lower()

        parsed = []
        for i in all_items:
            name = i[1] if len(i) > 1 else ""
            raw_u = str(i[2]) if len(i) > 2 else "Nos."
            
            # --- THE FIX: Slice to extract short unit for the UI ---
            unit = raw_u.split("(")[-1].replace(")", "").strip() if "(" in raw_u else raw_u
            
            try: rate_val = float(i[3]) if len(i) > 3 else 0.0
            except: rate_val = 0.0
            raw_desc = str(i[4]) if len(i) > 4 else ""

            desc, hsn, cat, pics = raw_desc, "", "General", []
            if raw_desc and raw_desc.strip().startswith("{") and '"desc"' in raw_desc:
                try:
                    data = json.loads(raw_desc)
                    desc = data.get("desc", "")
                    j_unit = data.get("unit", unit)
                    unit = j_unit.split("(")[-1].replace(")", "").strip() if "(" in j_unit else j_unit
                    hsn = data.get("hsn", "")
                    cat = data.get("category", "General")
                    pics = data.get("pics", [])
                except: pass

            parsed.append({'id': i[0], 'name': name, 'unit': unit, 'hsn': hsn, 'rate': rate_val, 'desc': desc, 'category': cat, 'pics': pics})

        if search and search != "search catalog...":
            parsed = [p for p in parsed if search in str(p['name']).lower() or search in str(p['desc']).lower()]

        selected_cat = self.cat_filter_var.get()
        if selected_cat != "All Categories": parsed = [p for p in parsed if p['category'] == selected_cat]

        # --- THE FIX: Activate Table Headers for sorting! ---
        if self.sort_col:
            if self.sort_col == "name":
                parsed.sort(key=lambda x: str(x['name']).lower(), reverse=self.sort_reverse)
            elif self.sort_col == "category":
                parsed.sort(key=lambda x: str(x['category']).lower(), reverse=self.sort_reverse)
            elif self.sort_col == "rate":
                parsed.sort(key=lambda x: float(x['rate']), reverse=self.sort_reverse)
        else:
            sort_mode = self.sort_var.get()
            if sort_mode == "A to Z": parsed.sort(key=lambda x: str(x['name']).lower())
            elif sort_mode == "Z to A": parsed.sort(key=lambda x: str(x['name']).lower(), reverse=True)
            elif sort_mode == "Rate: Low to High": parsed.sort(key=lambda x: float(x['rate']))
            elif sort_mode == "Rate: High to Low": parsed.sort(key=lambda x: float(x['rate']), reverse=True)
            else: parsed.sort(key=lambda x: x['id'], reverse=True)
        # ----------------------------------------------------
            
        return parsed

    def load_data(self, event=None):
        parsed_items = self.get_parsed_data()
        
        self.total_pages = max(1, (len(parsed_items) + self.items_per_page - 1) // self.items_per_page)
        if self.current_page > self.total_pages: self.current_page = max(1, self.total_pages)

        start_idx = (self.current_page - 1) * self.items_per_page
        page_items = parsed_items[start_idx : start_idx + self.items_per_page]

        self.lbl_total_items.config(text=str(len(parsed_items)))
        self.lbl_page.config(text=f"Page {self.current_page} of {self.total_pages}")
        
        self.btn_prev.config(state="normal" if self.current_page > 1 else "disabled", bg=self.CARD if self.current_page > 1 else self.BG)
        self.btn_next.config(state="normal" if self.current_page < self.total_pages else "disabled", bg=self.CARD if self.current_page < self.total_pages else self.BG)

        for item in self.tree.get_children(): self.tree.delete(item)

        for local_index, item in enumerate(page_items):
            is_sel = item['id'] in self.selected_items
            col1_val = ("☑" if is_sel else "☐") if self.is_bulk_mode else (start_idx + local_index + 1)
            
            tag = "selected_row" if is_sel and self.is_bulk_mode else ("evenrow" if local_index % 2 == 0 else "oddrow")
            fmt_rate = format_currency(item['rate'], self.curr_fmt)
            
            # --- THE FIX: Append an empty string to the tuple for the ghost column ---
            if self.has_gst:
                vals = (col1_val, item['name'], item['category'], item['unit'], item['hsn'], fmt_rate, "⚙️ Edit" if not self.is_bulk_mode else "", "")
            else:
                vals = (col1_val, item['name'], item['category'], item['unit'], fmt_rate, "⚙️ Edit" if not self.is_bulk_mode else "", "")
                
            self.tree.insert("", "end", iid=str(item['id']), values=vals, tags=(tag,))

        for i in range(len(page_items), self.items_per_page):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            empty_vals = [""] * len(self.columns)
            self.tree.insert("", "end", iid=f"empty_{i}", values=empty_vals, tags=(tag, "empty"))

        self.tree.yview_moveto(0)

    def on_tree_bg_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell" and self.tree.selection(): self.tree.selection_remove(self.tree.selection())

    def on_left_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            row_id = self.tree.identify_row(event.y)
            if not row_id or str(row_id).startswith("empty_"): return

            if self.is_bulk_mode: 
                item_id = int(row_id)
                if item_id in self.selected_items: self.selected_items.remove(item_id)
                else: self.selected_items.add(item_id)
                
                is_sel = item_id in self.selected_items
                vals = list(self.tree.item(row_id, "values"))
                vals[0] = "☑" if is_sel else "☐"
                self.tree.item(row_id, values=vals, tags=("selected_row" if is_sel else "evenrow",))
                self.update_bulk_delete_btn()
            else:
                col = self.tree.identify_column(event.x)
                target_col = '#7' if self.has_gst else '#6'
                if col == target_col:
                    open_form(self, row_id)

    def on_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id or str(row_id).startswith("empty_"): return
        
        self.tree.selection_set(row_id)
        menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD, fg=self.FG, activebackground=self.BLUE)
        
        if not self.is_bulk_mode:
            menu.add_command(label="✏️ Edit Item", command=lambda: open_form(self, row_id))
            menu.add_command(label="📑 Duplicate Item", command=lambda: open_form(self, row_id, is_duplicate=True))
            menu.add_separator()
            menu.add_command(label="❌ Delete Item", command=lambda: self.enable_bulk_mode(row_id), foreground=self.DANGER)
        else:
            menu.add_command(label="Cancel Selection", command=self.cancel_bulk_mode)
            
        menu.tk_popup(event.x_root, event.y_root)

    def on_double_click(self, event=None):
        if self.is_bulk_mode: return 
        if not self.tree.selection(): return
        row_id = self.tree.selection()[0]
        if not row_id or str(row_id).startswith("empty_"): return
        self.view_item_details(row_id)

    def view_item_details(self, item_id):
        parsed = self.get_parsed_data()
        item = next((p for p in parsed if str(p['id']) == str(item_id)), None)
        if not item: return

        pop = tk.Toplevel(self)
        pop.title(f"Details: {item['name']}")
        pop.configure(bg=self.BG)
        pop.geometry("460x420")
        pop.grab_set()

        pop.update_idletasks()
        sw, sh = pop.winfo_screenwidth(), pop.winfo_screenheight()
        pop.geometry(f"+{int((sw/2)-(460/2))}+{int((sh/2)-(420/2))}")

        tk.Label(pop, text="Catalog Item Details", font=("Arial", 16, "bold"), bg=self.BG, fg=self.FG).pack(pady=(20, 15), anchor="w", padx=20)
        
        f = tk.Frame(pop, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        f.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        labels = [
            ("Item Name:", item['name']),
            ("Category:", item['category']),
            ("Unit:", item['unit'])
        ]
        if self.has_gst:
            labels.append(("HSN / SAC:", item['hsn']))
        
        labels.append(("Rate / Unit:", format_currency(item['rate'], self.curr_fmt)))
        labels.append(("Description:", item['desc'] if item['desc'] else "—"))

        for i, (lbl, val) in enumerate(labels):
            tk.Label(f, text=lbl, font=("Arial", 10, "bold"), bg=self.CARD, fg=self.SEC_FG).grid(row=i, column=0, sticky="ne", padx=(20, 10), pady=12)
            tk.Label(f, text=val, font=("Arial", 11), bg=self.CARD, fg=self.FG, wraplength=240, justify="left").grid(row=i, column=1, sticky="w", padx=(0, 20), pady=12)
            
        if item.get('pics'):
            pic_f = tk.Frame(f, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
            pic_f.grid(row=len(labels), column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 15))
            tk.Label(pic_f, text="Attached Pictures:", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).pack(anchor="w", padx=10, pady=(10, 5))
            
            btn_container = tk.Frame(pic_f, bg=self.BG)
            btn_container.pack(fill="x", padx=10, pady=(0, 10))
            
            for idx, pic in enumerate(item['pics']):
                path = pic.get("path", "")
                def open_img(p=path):
                    import os, webbrowser
                    if os.path.exists(p):
                        try: os.startfile(p)
                        except: webbrowser.open(p)
                tk.Button(btn_container, text=f"🖼️ View {idx+1}", font=("Arial", 9, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", command=open_img).pack(side="left", padx=(0, 10))

        tk.Button(pop, text="Close", font=("Arial", 10, "bold"), bg=self.BORDER, fg=self.FG, relief="flat", cursor="hand2", command=pop.destroy).pack(pady=(0, 20), ipadx=20, ipady=5)

    def custom_hover_motion(self, e):
        item = self.tree.identify_row(e.y)
        if item != self._last_hovered:
            if self._last_hovered and self.tree.exists(self._last_hovered):
                tags = list(self.tree.item(self._last_hovered, "tags"))
                if "hover" in tags: tags.remove("hover"); self.tree.item(self._last_hovered, tags=tuple(tags))
            if item and not str(item).startswith("empty_"):
                tags = list(self.tree.item(item, "tags"))
                if "hover" not in tags and "bulk_sel" not in tags: 
                    tags.append("hover"); self.tree.item(item, tags=tuple(tags))
            self._last_hovered = item

        if item and not str(item).startswith("empty_"): self.tree.config(cursor="hand2")
        else: self.tree.config(cursor="")

    def custom_hover_leave(self, e):
        if self._last_hovered and self.tree.exists(self._last_hovered):
            tags = list(self.tree.item(self._last_hovered, "tags"))
            if "hover" in tags: tags.remove("hover"); self.tree.item(self._last_hovered, tags=tuple(tags))
        self._last_hovered = None; self.tree.config(cursor="")