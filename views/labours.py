import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
    root_dir = parent_dir
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)

if root_dir not in sys.path: sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts import helpers

from views.labour_parts.labour_forms import open_labour_form
from views.labour_parts.labour_details import view_labour_details
from views.labour_parts.labour_ledger import open_labour_ledger

from views.labour_parts.labour_exports import (
    open_import_window, 
    show_export_menu, 
    print_bulk_id_cards
)
from views.labour_parts.labour_payments import LabourPaymentsDashboard

try:
    from PIL import Image, ImageTk, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class LaboursView(tk.Frame):
    _saved_col_widths = {}
    
    def __init__(self, parent):
        self.app = parent.winfo_toplevel()
        self.colors = self.get_theme_colors()
        super().__init__(parent, bg=self.colors["bg"])
        self.is_bulk_mode = False
        self.selected_items = set()
        self.photo_cache = []
        self.phone_map = {}
        
        self.undo_stack = []
        self.redo_stack = []
        
        self.build_ui()

    def get_theme_colors(self):
        is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        if is_dark:
            return {"bg": "#0f172a", "card": "#1e293b", "border": "#334155", "text": "#f8fafc", "text_sec": "#94a3b8", "accent_blue": "#3b82f6", "accent_green": "#10b981", "error": "#ef4444", "header": "#1e293b", "bulk_sel": "#2563eb"}
        else:
            return {"bg": "#f0f9ff", "card": "#ffffff", "border": "#bae6fd", "text": "#0f172a", "text_sec": "#0284c7", "accent_blue": "#0ea5e9", "accent_green": "#10b981", "error": "#ef4444", "header": "#f8fafc", "bulk_sel": "#bae6fd"}

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars ---
        
        # --- THE FIX: Adaptive Dark/Light Mode Styling for Comboboxes & Dropdowns ---
        self.app.option_add("*TCombobox*Listbox.background", self.colors["card"])
        self.app.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent_blue"])
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("TCombobox", fieldbackground=self.colors["bg"], background=self.colors["card"], foreground=self.colors["text"], arrowcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"])
        style.map("TCombobox", fieldbackground=[("readonly", self.colors["bg"])], selectbackground=[("readonly", self.colors["bg"])], selectforeground=[("readonly", self.colors["text"])])
        # ----------------------------------------------------------------------------
        
        style.configure("Labour.Vertical.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.configure("Labour.Horizontal.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.map("Labour.Vertical.TScrollbar", background=[("active", self.colors["accent_blue"])])
        style.map("Labour.Horizontal.TScrollbar", background=[("active", self.colors["accent_blue"])])

        style.configure("Labour.Treeview", font=("Segoe UI", 13), rowheight=125, background=self.colors["bg"], fieldbackground=self.colors["bg"], foreground=self.colors["text"], borderwidth=0)
        style.map("Labour.Treeview", background=[("selected", self.colors["border"])], foreground=[("selected", self.colors["text"])])
        style.configure("Labour.Treeview.Heading", font=("Segoe UI", 12, "bold"), background=self.colors["header"], foreground=self.colors["text"], borderwidth=1, bordercolor=self.colors["border"], relief="raised")
        style.map("Labour.Treeview.Heading", background=[('active', self.colors["border"])])

        main_container = tk.Frame(self, bg=self.colors["bg"])
        main_container.pack(fill="both", expand=True)

        def clear_search_focus(event):
            if hasattr(self, 'search_entry') and event.widget != self.search_entry:
                main_container.focus_set()
        
        main_container.bind("<Button-1>", clear_search_focus)

        # --- THE FIX: Header Frame for Title and Undo/Redo Engine ---
        header_f = tk.Frame(main_container, bg=self.colors["bg"])
        header_f.pack(fill="x", pady=(0, 20))

        tk.Label(header_f, text="Labours & Workers", font=("Segoe UI", 22, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")

        self.ur_frame = tk.Frame(header_f, bg=self.colors["bg"])
        self.ur_frame.pack(side="right", anchor="s") 
        
        # Styled with solid borders and padding to match Pic 2 exactly
        self.btn_undo = tk.Button(self.ur_frame, text="↺ Undo", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"], relief="solid", bd=1, cursor="arrow", state="disabled", command=self.exec_undo, padx=12, pady=4)
        self.btn_undo.pack(side="left", padx=5)
        
        self.btn_redo = tk.Button(self.ur_frame, text="↻ Redo", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"], relief="solid", bd=1, cursor="arrow", state="disabled", command=self.exec_redo, padx=12, pady=4)
        self.btn_redo.pack(side="left", padx=5)
        # ------------------------------------------------------------

        action_bar = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, padx=15, pady=10)
        action_bar.pack(fill="x", pady=(0, 20))
        action_bar.bind("<Button-1>", clear_search_focus)

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(action_bar, textvariable=self.search_var, font=("Segoe UI", 11), width=30, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        self.search_entry.pack(side="left", ipady=4)
        self.search_entry.insert(0, "Search Name/Role/Phone...")
        self.search_entry.bind("<FocusIn>", lambda args: self.search_entry.delete('0', 'end') if self.search_entry.get() == 'Search Name/Role/Phone...' else None)
        self.search_entry.bind("<FocusOut>", lambda args: self.search_entry.insert(0, 'Search Name/Role/Phone...') if not self.search_entry.get() else None)
        self.search_var.trace_add("write", lambda *args: self.load_data() if self.search_entry.get() != 'Search Name/Role/Phone...' else None)

        # --- THE FIX: Perfectly Sized Red 'X' Clear Button ---
        btn_clear_search = tk.Button(action_bar, text="✖", font=("Arial", 9), bg=self.colors["border"], fg=self.colors["error"], activebackground=self.colors["border"], activeforeground=self.colors["error"], relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=lambda: [self.search_var.set("Search Name/Role/Phone..."), self.focus_set(), self.load_data()])
        btn_clear_search.pack(side="left", padx=(2, 10), ipady=1, ipadx=3)
        # -----------------------------------------------------

        # --- THE FIX: Added Sort Dropdown to Labours ---
        if not hasattr(self, 'roster_sort_var'):
            self.roster_sort_var = tk.StringVar(value="ID (Ascending)")
            
        tk.Label(action_bar, text="Sort By:", bg=self.colors["card"], font=("Segoe UI", 9, "bold"), fg=self.colors["text_sec"]).pack(side="left", padx=(10, 5))
        sort_cb = ttk.Combobox(action_bar, textvariable=self.roster_sort_var, values=["ID (Ascending)", "ID (Descending)", "Name (A to Z)", "Name (Z to A)"], state="readonly", width=14, font=("Segoe UI", 10), cursor="hand2")
        sort_cb.pack(side="left", ipady=3)
        sort_cb.bind("<<ComboboxSelected>>", lambda e: self.load_data())
        # -----------------------------------------------

        self.btn_add = tk.Button(action_bar, text="➕ Add Worker", font=("Segoe UI", 11, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_labour_form(self))
        self.btn_add.pack(side="right")
        
        self.btn_import = tk.Button(action_bar, text="📥 Import", font=("Segoe UI", 11, "bold"), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_import_window(self))
        self.btn_import.pack(side="right", padx=(0, 10))

        self.btn_export = tk.Button(action_bar, text="📤 Export", font=("Segoe UI", 11, "bold"), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: show_export_menu(self))
        self.btn_export.pack(side="right", padx=(0, 10))

        self.btn_payments = tk.Button(action_bar, text="💸 Recent Payments", font=("Segoe UI", 11, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="solid", highlightbackground=self.colors["border"], bd=1, cursor="hand2", padx=15, pady=4, command=lambda: LabourPaymentsDashboard(self))
        self.btn_payments.pack(side="right", padx=(0, 10))

        self.btn_cancel_bulk = tk.Button(action_bar, text="✖ Cancel", font=("Segoe UI", 11, "bold"), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=self.cancel_bulk)
        self.btn_del_selected = tk.Button(action_bar, text="🗑 Delete Selected", font=("Segoe UI", 11, "bold"), bg=self.colors["error"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.delete_bulk)
        self.btn_bulk_export_action = tk.Button(action_bar, text="📤 Export Selected", font=("Segoe UI", 11, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: show_export_menu(self))
        self.btn_bulk_print_action = tk.Button(action_bar, text="🪪 Print Selected IDs", font=("Segoe UI", 11, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: print_bulk_id_cards(self, self.selected_items))
        
        self.btn_select_all = tk.Button(action_bar, text="☑ Select All", font=("Segoe UI", 11, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.select_all_bulk)

        table_frame = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        table_frame.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", style="Labour.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", style="Labour.Horizontal.TScrollbar")
        
        # --- THE FIX: Added Blood Type to Schema ---
        self.tree = ttk.Treeview(table_frame, columns=("sno", "worker_id", "name", "role", "blood_type", "phone", "balance", "actions", "ghost"), show="tree headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Labour.Treeview")
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)

        self.tree.heading("#0", text="PHOTO")
        
        comp_id_val = getattr(self.app, "active_company_id", 1)
        try:
            import json
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"labour_main_cols_{comp_id_val}",))
            res = c.fetchone()
            conn.close()
            cw = json.loads(res[0]) if res and res[0] else {}
        except:
            cw = {}

        self.tree.column("#0", width=cw.get("#0", 130), minwidth=80, anchor="center", stretch=False)
        self.tree.heading("sno", text="S.No")
        self.tree.heading("worker_id", text="ID NO.", anchor="center")
        self.tree.heading("name", text="NAME", anchor="w")
        self.tree.heading("role", text="ROLE/DESIGNATION", anchor="w")
        self.tree.heading("blood_type", text="BLOOD", anchor="center")
        self.tree.heading("phone", text="PHONE", anchor="center")
        self.tree.heading("balance", text="PAYABLE BAL.", anchor="center")
        self.tree.heading("actions", text="ACTIONS", anchor="center")

        self.tree.column("sno", width=cw.get("sno", 65), minwidth=50, anchor="center", stretch=False)
        self.tree.column("worker_id", width=cw.get("worker_id", 95), minwidth=70, anchor="center", stretch=False)
        self.tree.column("name", width=cw.get("name", 200), minwidth=150, anchor="w", stretch=False)
        self.tree.column("role", width=cw.get("role", 160), minwidth=120, anchor="w", stretch=False)
        self.tree.column("blood_type", width=cw.get("blood_type", 90), minwidth=60, anchor="center", stretch=False)
        self.tree.column("phone", width=cw.get("phone", 150), minwidth=120, anchor="center", stretch=False)
        self.tree.column("balance", width=cw.get("balance", 160), minwidth=120, anchor="center", stretch=False)
        self.tree.column("actions", width=cw.get("actions", 150), minwidth=120, anchor="center", stretch=False)
        
        self.tree.heading("ghost", text="")
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)
        # -------------------------------------------

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        self.tree.tag_configure("evenrow", background=self.colors["bg"], foreground=self.colors["text"])
        self.tree.tag_configure("oddrow", background=self.colors["card"], foreground=self.colors["text"])
        self.tree.tag_configure("bulk_sel", background=self.colors["bulk_sel"], foreground="#ffffff")

        def on_motion(event):
            region = self.tree.identify("region", event.x, event.y)
            if region == "cell":
                col = self.tree.identify_column(event.x)
                # --- THE FIX: Updated indices for new Blood Type column (#6=Phone, #8=Actions) ---
                if col in ('#3', '#6', '#8'): 
                    self.tree.config(cursor="hand2")
                else: self.tree.config(cursor="")
            else: self.tree.config(cursor="")
        self.tree.bind("<Motion>", on_motion)

        def on_table_press(event):
            self._table_press_region = self.tree.identify("region", event.x, event.y)
        self.tree.bind("<ButtonPress-1>", on_table_press, add="+")

        def safe_table_click(event):
            if getattr(self, "_table_press_region", "") != "cell": return
            self.on_table_click(event)
            
        self.tree.bind("<ButtonRelease-1>", safe_table_click, add="+")
        self.tree.bind("<Double-1>", self.on_table_double_click)
        self.tree.bind("<Button-3>", self.on_right_click)

        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, self.save_col_widths)
        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")

        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                self.tree.yview_moveto(self.tree.yview()[0] + (delta * 0.008))
            else:
                self.tree.xview_moveto(self.tree.xview()[0] + (delta * 0.02))
                
        self.tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        self.tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        self.load_data()

    def update_ur_btns(self):
        if self.undo_stack: self.btn_undo.config(state="normal", fg=self.colors["accent_blue"], cursor="hand2")
        else: self.btn_undo.config(state="disabled", fg=self.colors["text_sec"], cursor="arrow")
        if self.redo_stack: self.btn_redo.config(state="normal", fg=self.colors["accent_blue"], cursor="hand2")
        else: self.btn_redo.config(state="disabled", fg=self.colors["text_sec"], cursor="arrow")

    # --- THE FIX: Upgraded Undo/Redo Engine to support Payments and Workers ---
    def push_undo(self, action_type, data):
        self.undo_stack.append((action_type, data))
        self.redo_stack.clear()
        self.update_ur_btns()

    def exec_undo(self):
        if not self.undo_stack: return
        action_type, data = self.undo_stack.pop()
        
        try:
            if action_type == 'DELETE_LABOUR':
                for r_id in data: database.restore_deleted_labour(r_id)
                self.redo_stack.append((action_type, data))
                
            elif action_type == "BULK_DELETE_PAY":
                for row in data:
                    database.restore_labour_ledger_record(row)
                self.redo_stack.append((action_type, data))
                
            elif action_type == "DELETE_PAY":
                database.restore_labour_ledger_record(data)
                self.redo_stack.append((action_type, data))
                
        except Exception as e: messagebox.showerror("Undo Error", str(e), parent=self)
                
        self.update_ur_btns()
        self.load_data()
        
    def exec_redo(self):
        if not self.redo_stack: return
        action_type, data = self.redo_stack.pop()
        
        try:
            if action_type == 'DELETE_LABOUR':
                for r_id in data: database.delete_labour(r_id)
                self.undo_stack.append((action_type, data))
                
            elif action_type == "BULK_DELETE_PAY":
                for row in data:
                    database.delete_labour_ledger_and_attendance_rollback(row[0])
                self.undo_stack.append((action_type, data))
                
            elif action_type == "DELETE_PAY":
                database.delete_labour_ledger_and_attendance_rollback(data[0])
                self.undo_stack.append((action_type, data))
                
        except Exception as e: messagebox.showerror("Redo Error", str(e), parent=self)
                
        self.update_ur_btns()
        self.load_data()
    # --------------------------------------------------------------------------

    def enable_bulk(self, action="delete"):
        self.is_bulk_mode = True
        self.selected_items.clear()
        self.btn_add.pack_forget()
        self.btn_import.pack_forget()
        self.btn_export.pack_forget()
        self.btn_payments.pack_forget() 
        self.btn_cancel_bulk.pack(side="right", padx=(0, 10))
        
        if action == "delete":
            self.btn_del_selected.pack(side="right", padx=(0, 10))
        elif action == "export":
            self.btn_bulk_export_action.pack(side="right", padx=(0, 10))
        elif action == "print_id":
            self.btn_bulk_print_action.pack(side="right", padx=(0, 10))
            
        self.btn_select_all.pack(side="right", padx=(0, 10))
        self.update_bulk_visuals()

    def cancel_bulk(self):
        self.is_bulk_mode = False
        self.selected_items.clear()
        self.btn_cancel_bulk.pack_forget()
        self.btn_del_selected.pack_forget()
        self.btn_bulk_export_action.pack_forget()
        self.btn_bulk_print_action.pack_forget()
        self.btn_select_all.pack_forget()
        
        self.btn_add.pack(side="right")
        self.btn_import.pack(side="right", padx=(0, 10))
        self.btn_export.pack(side="right", padx=(0, 10))
        self.btn_payments.pack(side="right", padx=(0, 10))
        self.update_bulk_visuals()

    def select_all_bulk(self):
        all_items = [child for child in self.tree.get_children() if not str(child).startswith("empty_")]
        if len(self.selected_items) == len(all_items): self.selected_items.clear()
        else:
            for c in all_items: self.selected_items.add(c)
        self.update_bulk_visuals()

    def update_bulk_visuals(self):
        for item in self.tree.get_children():
            if str(item).startswith("empty_"): continue
            tags = list(self.tree.item(item, "tags"))
            if "bulk_sel" in tags: tags.remove("bulk_sel")
            vals = list(self.tree.item(item, "values"))
            raw_sno = str(vals[0]).replace("☑ ", "").replace("☐ ", "")
            
            if self.is_bulk_mode:
                if item in self.selected_items:
                    tags.append("bulk_sel")
                    vals[0] = f"☑ {raw_sno}"
                else: vals[0] = f"☐ {raw_sno}"
            else: vals[0] = raw_sno
            self.tree.item(item, tags=tuple(tags), values=vals)
            
        count = len(self.selected_items)
        if hasattr(self, 'btn_select_all'):
            if count > 0:
                self.btn_select_all.config(text=f"☑ Select All ({count})")
            else:
                self.btn_select_all.config(text="☑ Select All")

    def delete_bulk(self):
        if not self.selected_items: return
        allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(self.app, "active_company_id", 1))
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
        if messagebox.askyesno("Confirm", "Delete selected workers?"):
            ids_to_delete = list(self.selected_items)
            database.log_audit("Labours", "Bulk Deleted Workers", record_ref=f"{len(ids_to_delete)} Workers", details="Bulk deleted workers and their records.", company_id=getattr(self.app, "active_company_id", 1))
            for row_id in ids_to_delete: database.delete_labour(row_id)
            
            # --- THE FIX: Uses the new push_undo standard! ---
            self.push_undo('DELETE_LABOUR', ids_to_delete)
            # -------------------------------------------------
            
            self.cancel_bulk()
            if hasattr(self, 'search_entry'):
                self.search_entry.delete('0', 'end')
                self.search_entry.insert(0, 'Search Name/Role/Phone...')
            self.load_data()

    def save_col_widths(self):
        comp_id_val = getattr(self.app, "active_company_id", 1)
        new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"]}
        new_w["#0"] = self.tree.column("#0", "width")
        try:
            import json
            database.save_ui_setting(f"labour_main_cols_{comp_id_val}", json.dumps(new_w))
        except: pass

    def update_phone_display(self, row_id, num):
        self.clipboard_clear()
        self.clipboard_append(num)
        phones = self.phone_map.get(str(row_id), [])
        display_str = f"{num} ▼" if len(phones) > 1 else num
        self.tree.set(row_id, "phone", display_str)

    def on_table_click(self, event):
        self.focus_set()
        self.after(100, self.save_col_widths)
        
        region = self.tree.identify("region", event.x, event.y)
        if region == "separator": return
            
        row_id = self.tree.identify_row(event.y)
        
        if not row_id or str(row_id).startswith("empty_"): 
            if self.tree.selection():
                self.tree.selection_remove(self.tree.selection())
            return

        if self.is_bulk_mode:
            if row_id in self.selected_items: self.selected_items.remove(row_id)
            else: self.selected_items.add(row_id)
            self.update_bulk_visuals()
            return

        if region == "cell":
            col = self.tree.identify_column(event.x)
            # --- THE FIX: Updated indices (#6=Phone, #8=Actions) ---
            if col == '#6': 
                phones = self.phone_map.get(str(row_id), [])
                if len(phones) > 1:
                    menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 11), bg=self.colors["card"], fg=self.colors["text"])
                    for p in phones:
                        menu.add_command(label=f"📞 {p}", command=lambda num=p, r_id=row_id: self.update_phone_display(r_id, num))
                    menu.tk_popup(event.x_root, event.y_root)
                elif len(phones) == 1:
                    self.update_phone_display(row_id, phones[0])
            elif col == '#8': 
                bbox = self.tree.bbox(row_id, '#8')
                if bbox:
                    click_x = event.x - bbox[0]
                    if click_x < bbox[2] / 2:
                        open_labour_form(self, row_id)
                    else:
                        self.delete_single(row_id)
            # -------------------------------------------------------

    def toggle_pin(self, row_id, pin_state):
        database.toggle_labour_pin_status(row_id, pin_state)
        self.load_data()

    def on_right_click(self, event):
        self.focus_set()
        row_id = self.tree.identify_row(event.y)
        if row_id and not str(row_id).startswith("empty_"):
            self.tree.selection_set(row_id)
            menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 11), bg=self.colors["card"], fg=self.colors["text"])
            
            # Dynamic Pin/Unpin
            l_dict = database.get_labour_dict(row_id)
            is_pinned = int(l_dict.get('is_pinned', 0)) if l_dict else 0
            if is_pinned:
                menu.add_command(label="📌 Unpin from Top", command=lambda: self.toggle_pin(row_id, 0))
            else:
                menu.add_command(label="📌 Pin to Top", command=lambda: self.toggle_pin(row_id, 1))
            menu.add_separator()
            
            menu.add_command(label="💰 View Ledger & Log Work", command=lambda: open_labour_ledger(self, row_id))
            menu.add_command(label="👁️ View Details", command=lambda: view_labour_details(self, row_id))
            menu.add_command(label="✏️ Edit", command=lambda: open_labour_form(self, row_id))
            menu.add_command(label="❌ Delete", command=lambda: self.delete_single(row_id), foreground=self.colors["error"])
            menu.add_separator()
            menu.add_command(label="🪪 Print Selected IDs", command=lambda: self.enable_bulk("print_id"))
            menu.add_command(label="📤 Bulk Export", command=lambda: self.enable_bulk("export"))
            menu.add_command(label="🗑️ Bulk Delete", command=lambda: self.enable_bulk("delete"))
            menu.tk_popup(event.x_root, event.y_root)

    def on_table_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id and not str(row_id).startswith("empty_"):
            open_labour_ledger(self, row_id)

    def delete_single(self, row_id):
        allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(self.app, "active_company_id", 1))
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
        if messagebox.askyesno("Confirm", "Delete this worker?"):
            l_dict = database.get_labour_dict(row_id)
            w_name = l_dict.get('name', 'Worker') if l_dict else 'Worker'
            database.log_audit("Labours", "Deleted Worker", record_ref=w_name, details="Completely deleted worker and all associated records.", company_id=getattr(self.app, "active_company_id", 1))
            
            database.delete_labour(row_id)
            # --- THE FIX: Uses the new push_undo standard! ---
            self.push_undo('DELETE_LABOUR', [row_id])
            # -------------------------------------------------
            self.load_data()

    def load_data(self):
        self.photo_cache.clear() 
        self.phone_map.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        
        search = self.search_var.get().lower()
        if search == "search name/role/phone...": search = ""
        
        # --- THE FIX: Eliminate PRAGMA from Load Engine! ---
        labours = database.get_all_labours()
        
        # --- NEW CODE: Extract, Filter, then Sort ---
        sort_mode = getattr(self, 'roster_sort_var', tk.StringVar(value="ID (Ascending)")).get()
        import re
        def natural_sort_key(s):
            # Splits text and numbers so LAB-2 comes before LAB-10
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

        processed_labours = []

        for l in labours:
            l_dict = database.get_labour_dict(l[0])
            if not l_dict: continue
            
            l_id = l_dict.get('id')
            
            def scrub(v):
                return "" if not v or str(v).lower() in ("none", "unknown") else str(v).strip()
            
            name = scrub(l_dict.get('name'))
            phone = scrub(l_dict.get('phone'))
            role = scrub(l_dict.get('role'))
            blood = scrub(l_dict.get('blood_type'))
            if not blood: blood = "—"
            
            is_pinned = int(l_dict.get('is_pinned', 0))
            
            worker_id_str = str(l_dict.get('worker_id_str', ''))
            if not worker_id_str: worker_id_str = f"LAB-{int(l_id):04d}"

            if search and search not in name.lower() and search not in phone.lower() and search not in role.lower() and search not in worker_id_str.lower(): 
                continue

            processed_labours.append({
                "l_id": l_id,
                "l_dict": l_dict,
                "name": name,
                "phone": phone,
                "role": role,
                "blood": blood,
                "worker_id_str": worker_id_str,
                "is_pinned": is_pinned
            })

        # --- FIRST PASS: Apply Natural Sorting Filter ---
        if sort_mode == "ID (Descending)":
            processed_labours.sort(key=lambda x: natural_sort_key(x["worker_id_str"]), reverse=True)
        elif sort_mode == "Name (A to Z)":
            processed_labours.sort(key=lambda x: x["name"].lower())
        elif sort_mode == "Name (Z to A)":
            processed_labours.sort(key=lambda x: x["name"].lower(), reverse=True)
        else:
            processed_labours.sort(key=lambda x: natural_sort_key(x["worker_id_str"]))
            
        # --- SECOND PASS: Force Pinned to Top (Stable Sort) ---
        processed_labours.sort(key=lambda x: x["is_pinned"], reverse=True)

        # --- THE FIX: Fetch all balances in ONE lightning-fast query! ---
        all_balances = database.get_all_labour_balances()
        # ----------------------------------------------------------------

        display_idx = 1
        
        for p_labour in processed_labours:
            l_id = p_labour["l_id"]
            l_dict = p_labour["l_dict"]
            name = p_labour["name"]
            
            # Add visual indicator
            if p_labour["is_pinned"]: name = f"📌 {name}"
            phone = p_labour["phone"]
            role = p_labour["role"]
            blood = p_labour["blood"]
            worker_id_str = p_labour["worker_id_str"]
            photo = l_dict.get('photo_path', '')
            
            thumb_img = None
            if photo and os.path.exists(photo) and HAS_PIL:
                try:
                    img = Image.open(photo).convert("RGBA")
                    resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                    img = ImageOps.fit(img, (100, 100), method=resamp)
                    
                    bordered = ImageOps.expand(img, border=1, fill=self.colors["border"])
                    thumb_img = ImageTk.PhotoImage(bordered)
                    self.photo_cache.append(thumb_img) 
                except: pass

            phones_list = [p.strip() for p in phone.split(",")] if phone else []
            self.phone_map[str(l_id)] = phones_list
            if len(phones_list) > 1: display_phone = f"{phones_list[0]} ▼"
            elif len(phones_list) == 1: display_phone = phones_list[0]
            else: display_phone = "—"
            
            # --- THE FIX: Extract math instantly from the pre-loaded dictionary! ---
            bal_data = all_balances.get(l_id, {"wallet": 0.0, "payable": 0.0})
            global_payable = bal_data["payable"]
            # -----------------------------------------------------------------------
            
            if global_payable > 0: bal_str = f"+ {helpers.format_currency(global_payable)}"
            elif global_payable < 0: bal_str = f"- {helpers.format_currency(abs(global_payable))}"
            else: bal_str = helpers.format_currency(0)

            tag = "evenrow" if display_idx % 2 != 0 else "oddrow"
            sno_val = f"☑ {display_idx}" if self.is_bulk_mode and str(l_id) in self.selected_items else (f"☐ {display_idx}" if self.is_bulk_mode else str(display_idx))
            
            self.tree.insert("", "end", iid=str(l_id), image=thumb_img if thumb_img else "", values=(sno_val, worker_id_str, name, role or "—", blood, display_phone, bal_str, "✏️ Edit   ❌ Delete"), tags=(tag,))
            display_idx += 1
            
        for i in range(display_idx, 15):
            tag = "evenrow" if i % 2 != 0 else "oddrow"
            self.tree.insert("", "end", iid=f"empty_{i}", image="", values=("", "", "", "", "", "", "", ""), tags=(tag, "empty"))