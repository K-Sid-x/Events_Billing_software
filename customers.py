import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import csv
import database
import tempfile
import webbrowser
from views.home_parts.ui_components import get_theme

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings, enable_copy_paste, smart_date_formatter
from views.customers_parts.customer_profile import view_profile
from views.customers_parts.customer_forms import open_form

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

class CustomersView(tk.Frame):
    def __init__(self, parent):
        self.app = parent.winfo_toplevel()
        self._last_hovered = None 
        self._pressed_region = None 
        
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"cust_grid_cols_{comp_id}",))
            res = c.fetchone()
            conn.close()
            self.app.customer_col_widths = json.loads(res[0]) if res and res[0] else {}
        except:
            if not hasattr(self.app, 'customer_col_widths'): self.app.customer_col_widths = {}
            
        if not hasattr(self.app, 'customer_phone_prefs'): self.app.customer_phone_prefs = {}
        
        self.is_bulk_mode = False
        self.selected_items = set()
        
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
            
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT gst_toggle FROM company WHERE id=?", (comp_id,))
            row = c.fetchone()
            conn.close()
            self.is_gst_company = (row[0] == 1) if row else False
        except Exception:
            self.curr_fmt, self.date_fmt_code = "Indian Rupees (₹)", "%Y-%m-%d"
            self.is_gst_company = False
            
        self.colors = self.get_theme_colors()
        super().__init__(parent, bg=self.colors["bg"])
        self.phone_data_map = {} 
        self.build_ui()

    def get_theme_colors(self):
        return get_theme()
        
    def apply_theme(self, *args):
        self.colors = self.get_theme_colors()
        self.config(bg=self.colors["bg"])
        for widget in self.winfo_children(): widget.destroy()
        self.phone_data_map.clear()
        self.build_ui()

    def treeview_sort_column(self, col, reverse):
        if col in ["actions", "sno_sel"]: return 
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('') if not str(k).startswith("empty_")]
        if col == "balance":
            def parse_num(val):
                try:
                    clean_val = ''.join(c for c in str(val) if c.isdigit() or c in '.-')
                    return float(clean_val) if clean_val else 0.0
                except: return 0.0
            l.sort(key=lambda t: parse_num(t[0]), reverse=reverse)
        else:
            l.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)

        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)
            tag = "evenrow" if index % 2 == 0 else "oddrow"
            if self.is_bulk_mode and k in self.selected_items: tag = "bulk_sel"
            self.tree.item(k, tags=(tag,))
            new_sno = str(index + 1)
            if self.is_bulk_mode: new_sno = f"☑ {new_sno}" if k in self.selected_items else f"☐ {new_sno}"
            current_vals = list(self.tree.item(k, "values"))
            current_vals[0] = new_sno
            self.tree.item(k, values=current_vals)
            
        empty_items = [k for k in self.tree.get_children('') if str(k).startswith("empty_")]
        for idx, k in enumerate(empty_items):
            self.tree.move(k, '', 'end')
            tag = "evenrow" if (len(l) + idx) % 2 == 0 else "oddrow"
            self.tree.item(k, tags=(tag, "empty"))

        self.tree.heading(col, command=lambda _col=col: self.treeview_sort_column(_col, not reverse))

    def build_ui(self):
        style = ttk.Style(self)
        
        # --- THE FIX: Killed 'clam' and forced 'default' to unlock our custom styles! ---
        style.theme_use("default") 
        # --------------------------------------------------------------------------------
            
        # --- THE FIX: Thick Solid Scrollbar Styles! ---
        style.configure("Cust.Vertical.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.configure("Cust.Horizontal.TScrollbar", background=self.colors["text_sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.map("Cust.Vertical.TScrollbar", background=[("active", self.colors["accent_blue"])])
        style.map("Cust.Horizontal.TScrollbar", background=[("active", self.colors["accent_blue"])])
        # ----------------------------------------------

        # --- THE FIX: Increased font size to 11 and rowheight to 38 to match other ledgers ---
        style.configure("Cust.Treeview", font=("Segoe UI", 11), rowheight=38, background=self.colors["card"], fieldbackground=self.colors["card"], foreground=self.colors["text"], borderwidth=0)
        style.map("Cust.Treeview", background=[("selected", self.colors["border"])], foreground=[("selected", self.colors["text"])])

        style.configure("Cust.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.colors["header"], foreground=self.colors["text"], borderwidth=1, bordercolor=self.colors["border"], relief="solid")
        style.map("Cust.Treeview.Heading", background=[('active', self.colors["border"])], foreground=[('active', self.colors["text"])])

        style.configure("Theme.TCombobox", fieldbackground=self.colors["card"], background=self.colors["header"], foreground=self.colors["text"], arrowcolor=self.colors["text"], bordercolor=self.colors["border"])
        style.map("Theme.TCombobox", fieldbackground=[("readonly", self.colors["card"])], selectbackground=[("readonly", self.colors["card"])], selectforeground=[("readonly", self.colors["text"])])

        self.app.option_add("*TCombobox*Listbox.background", self.colors["card"])
        self.app.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent_blue"])
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        # --- THE FIX: Removed 30px padding and synced header text sizing ---
        main_container = tk.Frame(self, bg=self.colors["bg"])
        main_container.pack(fill="both", expand=True)

        header_f = tk.Frame(main_container, bg=self.colors["bg"])
        header_f.pack(fill="x", pady=(0, 20))
        
        tk.Label(header_f, text="Parties (Customers & Suppliers)", font=("Segoe UI", 20, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(anchor="w")

        action_bar = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, padx=15, pady=10)
        action_bar.pack(fill="x", pady=(0, 20))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(action_bar, textvariable=self.search_var, font=("Segoe UI", 11), width=30, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        search_entry.pack(side="left", ipady=4)
        search_entry.insert(0, "Search Parties...")
        search_entry.bind("<FocusIn>", lambda args: search_entry.delete('0', 'end') if search_entry.get() == 'Search Parties...' else None)
        search_entry.bind("<FocusOut>", lambda args: search_entry.insert(0, 'Search Parties...') if not search_entry.get() else None)
        self.search_var.trace_add("write", lambda *args: [self.tree.yview_moveto(0), self.load_data()] if search_entry.get() != 'Search Parties...' else None)
        enable_copy_paste(search_entry) 

        self.filter_var = tk.StringVar(value="Alphabetical (A-Z)")
        filter_opts = ["Alphabetical (A-Z)", "Receivables (They Owe You)", "Payables (You Owe Them)", "Highest Balance", "Lowest Balance"]
        self.filter_combo = ttk.Combobox(action_bar, textvariable=self.filter_var, values=filter_opts, state="readonly", width=22, font=("Segoe UI", 10), style="Theme.TCombobox", cursor="hand2")
        self.filter_combo.pack(side="left", padx=(15, 0), ipady=3)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: [self.tree.yview_moveto(0), self.load_data()])

        self.hide_settled_var = tk.BooleanVar(value=False)
        chk_hide = tk.Checkbutton(action_bar, text="Hide Settled (₹0.00)", variable=self.hide_settled_var, command=lambda: [self.tree.yview_moveto(0), self.load_data()], bg=self.colors["card"], fg=self.colors["text"], selectcolor=self.colors["bg"], activebackground=self.colors["card"], activeforeground=self.colors["text"], cursor="hand2", font=("Segoe UI", 10, "bold"))
        chk_hide.pack(side="left", padx=(15, 0))

        # --- THE FIX: Save the Add Party button to 'self' so we can hide/show it ---
        self.btn_add_party = tk.Button(action_bar, text="➕ Add Party", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_form(self))
        self.btn_add_party.pack(side="right")
        add_hover(self.btn_add_party, self.colors["accent_blue"], "#2563eb" if self.colors["bg"] == "#0f172a" else "#0284c7")

        self.btn_export = tk.Button(action_bar, text="📤 Export", font=("Segoe UI", 10, "bold"), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=self.show_export_menu)
        self.btn_export.pack(side="right", padx=(0, 10))
        add_hover(self.btn_export, self.colors["border"], self.colors["card_hover"])

        # --- THE FIX: The New Master Timeline Button ---
        self.btn_recent_pays = tk.Button(action_bar, text="💸 All Transactions", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.show_recent_payments)
        self.btn_recent_pays.pack(side="right", padx=(0, 10))
        add_hover(self.btn_recent_pays, self.colors["accent_blue"], "#2563eb" if self.colors["bg"] == "#0f172a" else "#0284c7")
        # -----------------------------------------------

        self.btn_cancel_bulk = tk.Button(action_bar, text="✖ Cancel", font=("Segoe UI", 10, "bold"), bg=self.colors["border"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=self.cancel_bulk)
        add_hover(self.btn_cancel_bulk, self.colors["border"], self.colors["card_hover"])
        
        self.btn_del_bulk = tk.Button(action_bar, text="🗑 Delete Selected (0)", font=("Segoe UI", 10, "bold"), bg=self.colors["error"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.delete_bulk)
        
        # --- THE FIX: Injected Bulk Export and Select All buttons ---
        self.btn_export_pdf_bulk = tk.Button(action_bar, text="🖨 Export PDF", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: self.execute_bulk_export("pdf"))
        self.btn_export_csv_bulk = tk.Button(action_bar, text="📄 Export CSV", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: self.execute_bulk_export("csv"))
        self.btn_select_all = tk.Button(action_bar, text="☑ Select All (0)", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.select_all_bulk)
        
        def remove_focus(e):
            if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']:
                self.focus_set()
                
        self.bind("<ButtonPress-1>", remove_focus)
        main_container.bind("<ButtonPress-1>", remove_focus)
        header_f.bind("<ButtonPress-1>", remove_focus)
        action_bar.bind("<ButtonPress-1>", remove_focus)

        table_frame = tk.Frame(main_container, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        table_frame.pack(fill="both", expand=True)
        table_frame.bind("<ButtonPress-1>", remove_focus)

        # --- THE FIX: Apply isolated thick scrollbar styles ---
        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", style="Cust.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", style="Cust.Horizontal.TScrollbar")
        # ------------------------------------------------------

        # --- THE FIX: Ghost column architecture for perfectly rigid main tables ---
        self.all_cols = ("sno_sel", "name", "phone", "pan", "gstin", "balance", "actions", "ghost")
        self.tree = ttk.Treeview(table_frame, columns=self.all_cols, show="headings", height=15, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Cust.Treeview")
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        self.tree.heading("sno_sel", text="S.No", anchor="center")
        self.tree.heading("name", text="PARTY NAME", anchor="w", command=lambda: self.treeview_sort_column("name", False))
        self.tree.heading("phone", text="PHONE", anchor="center", command=lambda: self.treeview_sort_column("phone", False))
        self.tree.heading("pan", text="PAN NUMBER", anchor="center", command=lambda: self.treeview_sort_column("pan", False))
        self.tree.heading("gstin", text="GSTIN", anchor="center", command=lambda: self.treeview_sort_column("gstin", False))
        self.tree.heading("balance", text="NET BALANCE DUE", anchor="center", command=lambda: self.treeview_sort_column("balance", False))
        self.tree.heading("actions", text="ACTIONS", anchor="center")
        self.tree.heading("ghost", text="")

        self.tree.column("sno_sel", width=self.app.customer_col_widths.get("sno_sel", 70), minwidth=50, stretch=False, anchor="center")
        self.tree.column("name", width=self.app.customer_col_widths.get("name", 200), minwidth=150, stretch=False, anchor="w") 
        self.tree.column("phone", width=self.app.customer_col_widths.get("phone", 150), minwidth=120, stretch=False, anchor="center")
        self.tree.column("pan", width=self.app.customer_col_widths.get("pan", 120), minwidth=100, stretch=False, anchor="center")
        self.tree.column("gstin", width=self.app.customer_col_widths.get("gstin", 120), minwidth=100, stretch=False, anchor="center")
        self.tree.column("balance", width=self.app.customer_col_widths.get("balance", 200), minwidth=150, stretch=False, anchor="center") 
        self.tree.column("actions", width=150, minwidth=120, stretch=False, anchor="center")
        self.tree.column("ghost", width=10, minwidth=10, stretch=True)
        
        if not self.is_gst_company:
            self.tree["displaycolumns"] = ("sno_sel", "name", "phone", "pan", "balance", "actions", "ghost")
        # ------------------------------------------------------------------------
            
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        
        self.tree.tag_configure("evenrow", background=self.colors["bg"], foreground=self.colors["text"])
        self.tree.tag_configure("oddrow", background=self.colors["card"], foreground=self.colors["text"])
        self.tree.tag_configure("hover", background=self.colors["card_hover"])
        self.tree.tag_configure("bulk_sel", background=self.colors["bulk_sel"], foreground="#ffffff" if self.colors["bg"] == "#0f172a" else "#000000")

        self.tree.bind("<ButtonPress-1>", self.on_tree_press)
        self.tree.bind("<Double-1>", self.on_table_double_click)
        
        # --- THE FIX: Real-time width saving during separator drag ---
        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, self.save_col_widths)
                
        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after(50, self.save_col_widths) if self.tree.identify_region(e.x, e.y) == "separator" else self.on_table_click(e), add="+")
        # -------------------------------------------------------------
        
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Motion>", self.custom_hover_motion)
        self.tree.bind("<Leave>", self.custom_hover_leave)
        
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
        
        self.load_data()

    def show_export_menu(self):
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["text"], activebackground=self.colors["accent_blue"])
        menu.add_command(label="📊 Export to CSV (Excel)", command=self.export_csv)
        menu.add_command(label="📄 Export to PDF", command=self.export_pdf)
        x = self.btn_export.winfo_rootx()
        y = self.btn_export.winfo_rooty() + self.btn_export.winfo_height()
        menu.tk_popup(x, y)

    def get_export_data(self):
        visible_cols = self.tree["displaycolumns"]
        
        # --- THE FIX: Bulletproof check that catches any variation of #all ---
        if not visible_cols or '#all' in visible_cols or visible_cols == '#all': 
            visible_cols = self.all_cols
            
        # Ignore both actions and ghost columns during export
        export_cols = [c for c in visible_cols if c not in ("actions", "ghost")]
        headers = [self.tree.heading(c)["text"] for c in export_cols]
        # --- THE FIX: Clean header for SL NO ---
        if "sno_sel" in export_cols: headers[0] = "SL. NO."
        
        data = []
        export_idx = 1
        for item in self.tree.get_children():
            if not str(item).startswith("empty_"):
                # --- THE FIX: Ignore unselected items if we are in Bulk Export mode ---
                if getattr(self, "is_bulk_mode", False) and getattr(self, "bulk_action_type", None) == "export":
                    if item not in self.selected_items:
                        continue
                        
                row_vals = self.tree.item(item, "values")
                clean_row = []
                for c in export_cols:
                    idx = self.all_cols.index(c)
                    # --- THE FIX: Inject sequential number, strip dropdown arrows ---
                    if c == "sno_sel":
                        val = str(export_idx)
                    else:
                        val = str(row_vals[idx]).replace(" ▼", "")
                    clean_row.append(val)
                data.append(clean_row)
                export_idx += 1
        return headers, data

    def export_csv(self):
        headers, data = self.get_export_data()
        if not data: 
            messagebox.showinfo("Export", "No data to export.", parent=self)
            return
            
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export Parties", parent=self)
        if filepath:
            try:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(data)
                messagebox.showinfo("Export", "CSV Exported Successfully!", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export CSV: {e}", parent=self)

    def export_pdf(self):
        headers, data = self.get_export_data()
        if not data: 
            messagebox.showinfo("Export", "No data to export.", parent=self)
            return
            
        try:
            fd, filepath = tempfile.mkstemp(suffix=".html", prefix="Parties_Ledger_")
            html = """
            <html><head><style>
            body{font-family:Arial,sans-serif;padding:20px;color:#0f172a;}
            table{width:100%;border-collapse:collapse;margin-top:20px;}
            th,td{border:1px solid #cbd5e1;padding:10px;text-align:left;white-space:nowrap;}
            th{background:#f8fafc;font-weight:bold;}
            </style></head><body>
            <h2>Parties & Ledger Balances</h2><table><tr>
            """
            for h in headers: html += f"<th>{h}</th>"
            html += "</tr>"
            for row in data:
                html += "<tr>"
                for cell in row: html += f"<td>{cell}</td>"
                html += "</tr>"
            html += "</table><script>window.print();</script></body></html>"
            
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
            webbrowser.open('file://' + os.path.realpath(filepath))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {e}", parent=self)

    def enable_bulk(self, mode="delete"):
        if mode == "delete" and getattr(self.app, "current_role", "Admin") != "Admin":
            messagebox.showerror("Access Denied", "Only the Admin can permanently delete parties.", parent=self)
            return

        self.is_bulk_mode = True
        self.bulk_action_type = mode
        self.selected_items.clear()
        
        if hasattr(self, 'btn_export'): self.btn_export.pack_forget()
        if hasattr(self, 'btn_add_party'): self.btn_add_party.pack_forget()
        
        self.btn_cancel_bulk.pack(side="right", padx=(0, 10))
        
        # --- THE FIX: Dynamically pack buttons based on the requested Bulk Mode ---
        if mode == "delete":
            self.btn_del_bulk.config(text="🗑 Delete Selected (0)")
            self.btn_del_bulk.pack(side="right", padx=(0, 10))
        elif mode == "export":
            self.btn_export_pdf_bulk.pack(side="right", padx=(0, 10))
            self.btn_export_csv_bulk.pack(side="right", padx=(0, 10))
            
        self.btn_select_all.config(text="☑ Select All (0)")
        self.btn_select_all.pack(side="right", padx=(0, 10))
        
        self.update_bulk_visuals()

    def cancel_bulk(self):
        self.is_bulk_mode = False
        self.bulk_action_type = None
        self.selected_items.clear()
        
        self.btn_del_bulk.pack_forget()
        self.btn_export_pdf_bulk.pack_forget()
        self.btn_export_csv_bulk.pack_forget()
        self.btn_select_all.pack_forget()
        self.btn_cancel_bulk.pack_forget()
        
        if hasattr(self, 'btn_add_party'): self.btn_add_party.pack(side="right")
        if hasattr(self, 'btn_export'): self.btn_export.pack(side="right", padx=(0, 10))
        
        self.update_bulk_visuals()

    def select_all_bulk(self):
        all_items = [child for child in self.tree.get_children() if not str(child).startswith("empty_")]
        if len(self.selected_items) == len(all_items) and len(all_items) > 0:
            self.selected_items.clear()
        else:
            for child in all_items: self.selected_items.add(child)
        self.update_bulk_visuals()
        
    def execute_bulk_export(self, fmt):
        if not self.selected_items:
            messagebox.showinfo("Export", "No items selected.", parent=self)
            return
        if fmt == "pdf": self.export_pdf()
        else: self.export_csv()
        self.cancel_bulk()

    def update_bulk_visuals(self):
        if self.is_bulk_mode:
            if hasattr(self, 'btn_del_bulk') and self.btn_del_bulk.winfo_ismapped():
                self.btn_del_bulk.config(text=f"🗑 Delete Selected ({len(self.selected_items)})")
            if hasattr(self, 'btn_select_all') and self.btn_select_all.winfo_ismapped():
                self.btn_select_all.config(text=f"☑ Select All ({len(self.selected_items)})")
                
        for item in self.tree.get_children():
            if str(item).startswith("empty_"): continue
            tags = list(self.tree.item(item, "tags"))
            if "bulk_sel" in tags: tags.remove("bulk_sel")
            current_vals = list(self.tree.item(item, "values"))
            raw_sno = str(current_vals[0]).replace("☑ ", "").replace("☐ ", "")
            if self.is_bulk_mode:
                if item in self.selected_items:
                    tags.append("bulk_sel")
                    current_vals[0] = f"☑ {raw_sno}"
                else:
                    current_vals[0] = f"☐ {raw_sno}"
            else:
                current_vals[0] = raw_sno
            self.tree.item(item, tags=tuple(tags), values=current_vals)

    def delete_bulk(self):
        if getattr(self.app, "current_role", "Admin") != "Admin":
            messagebox.showerror("Access Denied", "Only the Admin can permanently delete parties.", parent=self)
            return
        if not self.selected_items: return
        if messagebox.askyesno("Confirm Bulk Delete", f"Are you absolutely sure you want to permanently delete {len(self.selected_items)} parties?"):
            
            conn = database.get_connection()
            c = conn.cursor()
            comp_id = getattr(self.app, "active_company_id", 1)
            
            skipped_count = 0
            deleted_count = 0
            deleted_names = []
            
            for row_id in list(self.selected_items):
                # --- THE FIX: Safely check for active transactions, Opening Balance, or Advance Wallet before deleting ---
                c.execute("SELECT COUNT(id) FROM invoices WHERE customer_id=? AND company_id=? AND is_deleted=0", (row_id, comp_id))
                inv_count = c.fetchone()[0]
                
                c.execute("SELECT COUNT(id) FROM purchases WHERE vendor_id=? AND company_id=? AND is_deleted=0", (row_id, comp_id))
                purch_count = c.fetchone()[0]

                has_active_bal = False
                c.execute("SELECT name, address FROM customers WHERE id=? AND company_id=?", (row_id, comp_id))
                addr_row = c.fetchone()
                p_name = str(addr_row[0]) if addr_row and addr_row[0] else f"ID #{row_id}"
                if addr_row and len(addr_row) > 1 and addr_row[1]:
                    raw_addr = str(addr_row[1]).strip()
                    if raw_addr.startswith("{"):
                        try:
                            j = json.loads(raw_addr)
                            ob_val = float(j.get("opening_balance", 0.0) or 0.0)
                            ob_paid = float(j.get("ob_paid", 0.0) or 0.0)
                            ob_due = max(0.0, ob_val - ob_paid)
                            adv_in = float(j.get("advance_in", j.get("advance_wallet", 0.0)) or 0.0)
                            adv_out = float(j.get("advance_out", 0.0) or 0.0)
                            if ob_due > 0.009 or adv_in > 0.009 or adv_out > 0.009:
                                has_active_bal = True
                        except Exception:
                            pass
                
                if inv_count > 0 or purch_count > 0 or has_active_bal:
                    skipped_count += 1
                else:
                    database.delete_customer(row_id)
                    deleted_count += 1
                    deleted_names.append(p_name)
            # -----------------------------------------------------------------------------------
            
            conn.close()
            if deleted_names:
                database.log_audit(
                    "Parties", "Bulk Deleted",
                    record_ref=f"{deleted_count} Parties",
                    details=f"Permanently deleted parties: {', '.join(deleted_names)}",
                    amount=0.0, company_id=comp_id
                )
            
            if skipped_count > 0:
                messagebox.showwarning("Partial Deletion", f"Successfully deleted {deleted_count} parties.\n\n{skipped_count} parties were skipped because they have active Invoices, Purchases, Opening Balances, or Advance Wallet funds.", parent=self)
                
            self.cancel_bulk()
            self.load_data()

    def on_tree_press(self, event):
        self._pressed_region = self.tree.identify_region(event.x, event.y)
        if event.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox']: self.focus_set()

    def on_right_click(self, event):
        if getattr(self, '_pressed_region', None) == "separator": return
        region = self.tree.identify("region", event.x, event.y)
        if region in ["cell", "tree"]:
            row_id = self.tree.identify_row(event.y)
            if not row_id or str(row_id).startswith("empty_"): return
            self.tree.selection_set(row_id)
            is_admin = (getattr(self.app, "current_role", "Admin") == "Admin")
            menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["text"], activebackground=self.colors["accent_blue"])
            menu.add_command(label="✏️ Edit Party", command=lambda: open_form(self, row_id))
            if not self.is_bulk_mode:
                menu.add_separator()
                menu.add_command(label="📄 Bulk Export", command=lambda: self.enable_bulk("export"))
                if is_admin:
                    menu.add_command(label="🗑️ Bulk Delete", command=lambda: self.enable_bulk("delete"))
            if is_admin:
                menu.add_separator()
                menu.add_command(label="❌ Delete Party", command=lambda: self.delete_customer(row_id), foreground=self.colors["error"])
            menu.tk_popup(event.x_root, event.y_root)

    def on_table_click(self, event):
        self.after(100, self.save_col_widths) 
        if getattr(self, '_pressed_region', None) == "separator": return
        region = self.tree.identify("region", event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        if not row_id or str(row_id).startswith("empty_"): return

        if self.is_bulk_mode:
            if row_id in self.selected_items: self.selected_items.remove(row_id)
            else: self.selected_items.add(row_id)
            self.update_bulk_visuals()
            return

        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == '#3':
                parts = self.phone_data_map.get(row_id, [])
                if len(parts) <= 1: return 
                menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["text"], activebackground=self.colors["accent_blue"])
                menu.add_command(label="Switch displayed number:", state="disabled", foreground=self.colors["text_sec"])
                menu.add_separator()
                for p in parts:
                    clean_val = p.split(":", 1)[1].strip() if ":" in p else p
                    menu.add_command(label=p, command=lambda text=clean_val, r=row_id: self.select_phone(r, text))
                menu.tk_popup(event.x_root, event.y_root)

    def on_table_double_click(self, event):
        if getattr(self, '_pressed_region', None) == "separator": return
        region = self.tree.identify("region", event.x, event.y)
        row_id = self.tree.identify_row(event.y)
        if not row_id or str(row_id).startswith("empty_"): return
        if self.is_bulk_mode: return
        
        if region == "cell":
            column = self.tree.identify_column(event.x)
            action_col = '#7' if getattr(self, "is_gst_company", True) else '#6'
            
            if column == action_col: 
                # --- THE FIX: Double click to Edit/Delete (Delete locked to Admin) ---
                if getattr(self.app, "current_role", "Admin") != "Admin":
                    open_form(self, row_id)
                else:
                    bbox = self.tree.bbox(row_id, column)
                    if bbox:
                        cx, cy, cw, ch = bbox
                        if event.x < cx + (cw / 2):
                            open_form(self, row_id)
                        else:
                            self.delete_customer(row_id)
            elif column == '#2':
                # --- THE FIX: Only Party Name opens the Ledger Profile ---
                view_profile(self, row_id)

    def select_phone(self, row_id, text):
        self.app.customer_phone_prefs[str(row_id)] = text
        self.tree.set(row_id, "phone", f"{text} ▼")

    def save_col_widths(self):
        # --- THE FIX: Ignore the ghost column and route to the safe backend helper ---
        for col in self.all_cols: 
            if col != "ghost": 
                # MATHEMATICAL CLAMP: Prevent 0-width crashes
                self.app.customer_col_widths[col] = max(30, self.tree.column(col, "width"))
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            key = f"cust_grid_cols_{comp_id}"
            database.save_ui_setting(key, json.dumps(self.app.customer_col_widths))
        except: pass
        # -----------------------------------------------------------------------------

    def custom_hover_motion(self, e):
        item = self.tree.identify_row(e.y)
        col = self.tree.identify_column(e.x)
        action_col = '#7' if getattr(self, "is_gst_company", True) else '#6'
        
        if self._last_hovered and self._last_hovered != item and self.tree.exists(self._last_hovered):
            tags = list(self.tree.item(self._last_hovered, "tags"))
            if "hover" in tags: 
                tags.remove("hover")
                self.tree.item(self._last_hovered, tags=tuple(tags))
                
        self._last_hovered = item
        if item and not str(item).startswith("empty_"):
            tags = list(self.tree.item(item, "tags"))
            if "hover" not in tags and "bulk_sel" not in tags: 
                tags.append("hover")
                self.tree.item(item, tags=tuple(tags))
                
            # --- THE FIX: Hand cursor ONLY appears on Party Name, Actions, or Phone dropdown ---
            is_clickable = False
            if col == '#2' or col == action_col:
                is_clickable = True
            elif col == '#3':
                parts = self.phone_data_map.get(item, [])
                if len(parts) > 1:
                    is_clickable = True
                    
            if is_clickable:
                self.tree.config(cursor="hand2")
            else:
                self.tree.config(cursor="")
        else:
            self.tree.config(cursor="")

    def custom_hover_leave(self, e):
        if self._last_hovered and self.tree.exists(self._last_hovered):
            tags = list(self.tree.item(self._last_hovered, "tags"))
            if "hover" in tags: 
                tags.remove("hover")
                self.tree.item(self._last_hovered, tags=tuple(tags))
        self._last_hovered = None
        self.tree.config(cursor="")

    # --- THE FIX: Calculate Net Balance strictly using Database ID! ---
    def get_customer_balance(self, cust_id):
        total_due = 0.0
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            
            s_pend = 0.0
            p_pend = 0.0
            ob_val = 0.0
            adv_in = 0.0
            adv_out = 0.0
            
            conn = database.get_connection()
            c = conn.cursor()
            
            # Sum up Sales (ignore drafts and deleted)
            c.execute("SELECT SUM(balance_due) FROM invoices WHERE customer_id=? AND company_id=? AND is_deleted=0 AND status != 'Draft'", (cust_id, comp_id))
            s_res = c.fetchone()
            s_pend = float(s_res[0]) if s_res and s_res[0] else 0.0
            
            # Sum up Purchases (ignore drafts and deleted)
            c.execute("SELECT SUM(balance_due) FROM purchases WHERE vendor_id=? AND company_id=? AND is_deleted=0 AND is_draft=0", (cust_id, comp_id))
            p_res = c.fetchone()
            p_pend = float(p_res[0]) if p_res and p_res[0] else 0.0
            
            # Extract Address JSON for Opening Balances and Wallets
            c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (cust_id, comp_id))
            c_row = c.fetchone()
            if c_row and c_row[0]:
                raw_addr = str(c_row[0]).strip()
                if raw_addr.startswith("{"):
                    try:
                        j = json.loads(raw_addr)
                        raw_ob = float(j.get("opening_balance", 0.0) or 0.0)
                        ob_paid = float(j.get("ob_paid", 0.0) or 0.0)
                        ob_val = max(0.0, raw_ob - ob_paid)
                        
                        if not j.get("ob_type", "").startswith("They"): ob_val = -ob_val
                        
                        adv_in = float(j.get("advance_in", j.get("advance_wallet", 0.0)))
                        adv_out = float(j.get("advance_out", 0.0))
                    except: pass
            
            conn.close()
            
            total_due = ob_val + s_pend - p_pend - adv_in + adv_out
            
        except Exception as e:
            print("Main Page Math Engine Error:", e)
            
        return total_due

    def load_data(self, event=None):
        for item in self.tree.get_children(): self.tree.delete(item)
        
        # --- THE FIX: Direct strict query pulling ALIAS for the display grid ---
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, name, phone, gstin, email, address, state, state_code, alias FROM customers WHERE company_id=?", (comp_id,))
            customers = cur.fetchall()
            conn.close()
        except:
            customers = []
            
        search = self.search_var.get().lower()
        if search == "search parties...": search = ""
        hide_settled = self.hide_settled_var.get()
        filter_opt = self.filter_var.get()
        self.phone_data_map.clear()
        
        records = []
        for c in customers:
            cust_id = c[0]
            customer_name = str(c[1])
            alias = str(c[8]).strip() if len(c) > 8 and c[8] else ""
            display_name = f"{customer_name} ({alias})" if alias else customer_name
            
            # --- THE FIX: Use secure Database ID for math engine! ---
            total_due = self.get_customer_balance(cust_id)
            
            if hide_settled and round(total_due, 2) == 0.00: continue
            if filter_opt == "Receivables (They Owe You)" and total_due <= 0: continue
            if filter_opt == "Payables (You Owe Them)" and total_due >= 0: continue

            pan_val = "Not Provided"
            raw_addr = str(c[5]) if len(c) > 5 and c[5] else ""
            if raw_addr and raw_addr.strip().startswith("{"):
                try:
                    pan_val = str(json.loads(raw_addr).get("pan", "Not Provided"))
                    if not pan_val.strip(): pan_val = "Not Provided"
                except: pass

            if search:
                phone_str, gstin_str, pan_str = str(c[2]).lower(), str(c[3]).lower(), pan_val.lower()
                if not (search in customer_name.lower() or search in phone_str or search in gstin_str or search in pan_str): continue

            raw_phone = str(c[2]) if c[2] and c[2] != "None" else ""
            display_phone = ""
            if raw_phone:
                parts = [p.strip() for p in raw_phone.split(",") if p.strip()]
                self.phone_data_map[str(c[0])] = parts 
                if str(c[0]) in self.app.customer_phone_prefs:
                    display_phone = self.app.customer_phone_prefs[str(c[0])] + " ▼"
                elif parts:
                    first_part = parts[0]
                    display_phone = first_part.split(":", 1)[1].strip() if ":" in first_part else first_part
                    if len(parts) > 1: display_phone += " ▼"
            else: self.phone_data_map[str(c[0])] = []

            # --- THE FIX: Revert to strictly showing the clean raw name in the table! ---
            records.append({'id': c[0], 'name': customer_name, 'phone': display_phone, 'pan': pan_val, 'gstin': c[3], 'balance': total_due})

        if filter_opt == "Highest Balance": records.sort(key=lambda x: x['balance'], reverse=True)
        elif filter_opt == "Lowest Balance": records.sort(key=lambda x: x['balance'])
        elif filter_opt == "Z to A": records.sort(key=lambda x: str(x['name']).lower(), reverse=True)
        else: records.sort(key=lambda x: str(x['name']).lower())

        display_index = 1
        for rec in records:
            formatted = format_currency(abs(rec['balance']), self.curr_fmt)
            if rec['balance'] > 0: formatted_balance = f"+ {formatted} (Receivable)"
            elif rec['balance'] < 0: formatted_balance = f"- {formatted} (Payable)"
            else: formatted_balance = "0.00 (Settled)"

            tag = "evenrow" if display_index % 2 != 0 else "oddrow"
            if self.is_bulk_mode and str(rec['id']) in self.selected_items: tag = "bulk_sel"

            sno_display = str(display_index)
            if self.is_bulk_mode: sno_display = f"☑ {sno_display}" if str(rec['id']) in self.selected_items else f"☐ {sno_display}"

            action_txt = "✏️ Edit | ❌ Delete" if getattr(self.app, "current_role", "Admin") == "Admin" else "✏️ Edit"
            # --- THE FIX: Add the empty ghost string at the end of the tuple ---
            self.tree.insert("", "end", iid=str(rec['id']), values=(sno_display, rec['name'], rec['phone'], rec['pan'], rec['gstin'], formatted_balance, action_txt, ""), tags=(tag,))
            display_index += 1

        for i in range(display_index, 16):
            tag = "evenrow" if i % 2 != 0 else "oddrow"
            self.tree.insert("", "end", iid=f"empty_{i}", values=("", "", "", "", "", "", "", ""), tags=(tag, "empty"))
            # -------------------------------------------------------------------

    def delete_customer(self, row_id):
        if getattr(self.app, "current_role", "Admin") != "Admin":
            messagebox.showerror("Access Denied", "Only the Admin can permanently delete parties.", parent=self)
            return

        # --- THE FIX: Prevent deletion of parties with active transactions or balances ---
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT name, address FROM customers WHERE id=?", (row_id,))
        row = c.fetchone()
        if not row: conn.close(); return
        c_name = row[0]
        raw_addr = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        
        comp_id = getattr(self.app, "active_company_id", 1)
        
        # --- THE FIX: Check strictly by Database ID instead of Text Name ---
        c.execute("SELECT COUNT(id) FROM invoices WHERE customer_id=? AND company_id=? AND is_deleted=0", (row_id, comp_id))
        inv_count = c.fetchone()[0]
        c.execute("SELECT COUNT(id) FROM purchases WHERE vendor_id=? AND company_id=? AND is_deleted=0", (row_id, comp_id))
        purch_count = c.fetchone()[0]
        # -------------------------------------------------------------------
        
        if inv_count > 0 or purch_count > 0:
            messagebox.showerror("Action Denied", f"Cannot delete '{c_name}' because they have active Invoices or Purchases.\n\nPlease delete all their transactions first.", parent=self)
            conn.close()
            return

        if raw_addr.startswith("{"):
            try:
                j = json.loads(raw_addr)
                ob_val = float(j.get("opening_balance", 0.0) or 0.0)
                ob_paid = float(j.get("ob_paid", 0.0) or 0.0)
                ob_due = max(0.0, ob_val - ob_paid)
                adv_in = float(j.get("advance_in", j.get("advance_wallet", 0.0)) or 0.0)
                adv_out = float(j.get("advance_out", 0.0) or 0.0)
                if ob_due > 0.009 or adv_in > 0.009 or adv_out > 0.009:
                    messagebox.showerror(
                        "Action Denied",
                        f"Cannot delete '{c_name}' because they have an active Opening Balance or Advance Wallet balance.\n\n"
                        f"Please settle or clear their Opening Balance / Advance Wallet first.",
                        parent=self
                    )
                    conn.close()
                    return
            except Exception:
                pass

        if messagebox.askyesno("Confirm Delete", f"Delete {c_name} entirely?"):
            comp_id = getattr(self.app, "active_company_id", 1)
            # --- THE FIX: Added company_id lock ---
            c.execute("DELETE FROM customers WHERE id=? AND company_id=?", (row_id, comp_id))
            conn.commit()
            conn.close()
            database.log_audit("Parties", "Deleted", record_ref=c_name, details=f"Permanently deleted party '{c_name}'", amount=0.0, company_id=comp_id)
            self.load_data()
        else:
            conn.close()

    # =========================================================================
    # MASTER TIMELINE ENGINE
    # =========================================================================
    def show_recent_payments(self):
        # --- THE FIX: We must define comp_id for the Customers tab so the Database queries don't crash! ---
        self.comp_id = getattr(self.app, "active_company_id", 1)
        
        from views.invoice_parts.calendar_widget import NativeCalendar
        import csv
        import tempfile
        import webbrowser
        from datetime import datetime, timedelta, date

        pop = tk.Toplevel(self.app)
        pop.title("All Transactions (Payments & Offsets)")
        pop.geometry("1150x700")
        pop.configure(bg=self.colors["bg"])
        pop.grab_set()
        pop.transient(self.app)
        
        pop.update_idletasks()
        x = self.app.winfo_rootx() + (self.app.winfo_width() // 2) - 575
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
        
        # --- THE FIX: Upgraded the UI Fonts to Segoe UI to perfectly match your other tabs ---
        tk.Label(inner_f, text="💸 All Transactions", font=("Segoe UI", 14, "bold"), bg=self.colors["card"], fg=self.colors["text"]).pack(side="left", padx=(5, 15))
        
        tk.Label(inner_f, text="🔍 Search:", bg=self.colors["card"], font=("Segoe UI", 9, "bold"), fg=self.colors["text_sec"]).pack(side="left", padx=(5, 5))
        tk.Entry(inner_f, textvariable=search_var, font=("Segoe UI", 10), width=25, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1).pack(side="left", ipady=3)
        
        btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 9, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=lambda: search_var.set(""))
        btn_clear_search.pack(side="left", padx=(5, 5))
        
        # --- THE FIX: Instant Export Dropdown ---
        btn_export = tk.Button(inner_f, text="📥 Export ▼", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="solid", highlightbackground=self.colors["border"], bd=1, cursor="hand2", padx=8, pady=2)
        btn_export.pack(side="right", padx=(10, 5))
        
        export_menu = tk.Menu(btn_export, tearoff=0, font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["text"], activebackground=self.colors["accent_blue"], activeforeground="#ffffff")
        export_menu.add_command(label="⭳ Export as CSV", command=lambda: export_recent_csv())
        export_menu.add_command(label="🖨️ Export as PDF", command=lambda: export_recent_pdf())
        btn_export.config(command=lambda: export_menu.tk_popup(btn_export.winfo_rootx(), btn_export.winfo_rooty() + btn_export.winfo_height()))
        # ----------------------------------------

        # --- THE FIX: Filter-Only Clear Button (Doesn't touch the Search box) ---
        def trigger_clear_filter():
            from_var.set("")
            to_var.set("")
            filter_var.set("All Time")
            toggle_custom_date()
        
        btn_clear = tk.Button(inner_f, text="✖", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=trigger_clear_filter)
        btn_clear.pack(side="right", padx=(5, 5))
        # ------------------------------------------------------------------------
        
        custom_date_f = tk.Frame(inner_f, bg=self.colors["card"])
        
        to_f = tk.Frame(custom_date_f, bg=self.colors["bg"], highlightbackground=self.colors["border"], highlightthickness=1)
        to_f.pack(side="right", padx=(5, 0))
        to_btn = tk.Button(to_f, text="▼", bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2")
        to_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(to_f, textvariable=to_var, font=("Segoe UI", 10), width=10, bg=self.colors["bg"], fg=self.colors["text"], bd=0, insertbackground=self.colors["text"]).pack(side="left", ipady=4, padx=5)
        to_btn.config(command=lambda b=to_btn: NativeCalendar(pop, to_var, anchor_widget=b))
        tk.Label(custom_date_f, text="To:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side="right", padx=(10, 0))
        
        from_f = tk.Frame(custom_date_f, bg=self.colors["bg"], highlightbackground=self.colors["border"], highlightthickness=1)
        from_f.pack(side="right", padx=(5, 0))
        from_btn = tk.Button(from_f, text="▼", bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2")
        from_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(from_f, textvariable=from_var, font=("Segoe UI", 10), width=10, bg=self.colors["bg"], fg=self.colors["text"], bd=0, insertbackground=self.colors["text"]).pack(side="left", ipady=4, padx=5)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(pop, from_var, anchor_widget=b))
        tk.Label(custom_date_f, text="📅 From:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"]).pack(side="right", padx=(10, 0))
        
        date_cb = ttk.Combobox(inner_f, textvariable=filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=12, font=("Segoe UI", 10), cursor="hand2", style="Theme.TCombobox")
        date_cb.pack(side="right", padx=(5, 0))
        lbl_filter = tk.Label(inner_f, text="Filter:", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"])
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
        tk.Label(bulk_f, text="Bulk Export Mode Active", font=("Segoe UI", 11, "bold"), bg=self.colors["card"], fg=self.colors["accent_blue"]).pack(side="left", padx=(5, 15))
        
        btn_select_all = tk.Button(bulk_f, text="☑ Select All (0)", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: toggle_select_all())
        btn_select_all.pack(side="left", padx=(0, 10))
        
        tk.Button(bulk_f, text="✖ Cancel", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["error"], relief="flat", cursor="hand2", command=lambda: toggle_bulk_mode()).pack(side="right", padx=10)
        tk.Button(bulk_f, text="🖨️ Export PDF", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_pdf(selected_only=True)).pack(side="right", padx=(5, 10))
        tk.Button(bulk_f, text="⭳ Export CSV", font=("Segoe UI", 9, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=10, pady=4, command=lambda: export_recent_csv(selected_only=True)).pack(side="right", padx=0)

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
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="Cust.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="Cust.Horizontal.TScrollbar")
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        
        cols = ("sno_sel", "date", "party", "dir", "ref", "mode", "notes", "amount", "ghost")
        p_tree = ttk.Treeview(table_f, columns=cols, show="headings", height=15, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Cust.Treeview")
        p_tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=p_tree.yview)
        scroll_x.config(command=p_tree.xview)

        p_tree.heading("sno_sel", text="S.NO", anchor="center")
        p_tree.heading("date", text="DATE", anchor="center")
        p_tree.heading("party", text="PARTY", anchor="w")
        p_tree.heading("dir", text="DIRECTION", anchor="center")
        p_tree.heading("ref", text="REFERENCE", anchor="w")
        p_tree.heading("mode", text="PAYMENT MODE", anchor="center")
        p_tree.heading("notes", text="NOTES", anchor="w")
        p_tree.heading("amount", text="AMOUNT", anchor="e")
        p_tree.heading("ghost", text="")

        try:
            raw_setting = database.get_ui_setting(f"master_timeline_cols_{self.comp_id}", "{}")
            r_w = json.loads(raw_setting) if raw_setting else {}
        except:
            r_w = {}

        p_tree.column("sno_sel", width=r_w.get("sno_sel", 50), minwidth=30, anchor="center", stretch=False)
        p_tree.column("date", width=r_w.get("date", 100), minwidth=80, anchor="center", stretch=False)
        p_tree.column("party", width=r_w.get("party", 180), minwidth=120, anchor="w", stretch=False)
        p_tree.column("dir", width=r_w.get("dir", 120), minwidth=80, anchor="center", stretch=False)
        p_tree.column("ref", width=r_w.get("ref", 180), minwidth=120, anchor="w", stretch=False)
        p_tree.column("mode", width=r_w.get("mode", 130), minwidth=100, anchor="center", stretch=False)
        # --- THE FIX: stretch=False allows free manual resizing! ---
        p_tree.column("notes", width=r_w.get("notes", 180), minwidth=120, anchor="w", stretch=False)
        p_tree.column("amount", width=r_w.get("amount", 120), minwidth=100, anchor="e", stretch=False)
        p_tree.column("ghost", width=10, minwidth=10, stretch=True)

        def save_recent_widths():
            new_w = {c: p_tree.column(c, "width") for c in p_tree["columns"] if c != "ghost"}
            try: database.save_ui_setting(f"master_timeline_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_recent_sep_drag(event):
            if p_tree.identify_region(event.x, event.y) == "separator":
                pop.after(50, save_recent_widths)

        p_tree.bind("<B1-Motion>", on_recent_sep_drag, add="+")
        p_tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_recent_widths), add="+")

        # --- THE FIX: Proper Universal Stripe & Status Colors ---
        p_tree.tag_configure("even", background=self.colors.get("stripe_even", self.colors["bg"]), foreground=self.colors["text"])
        p_tree.tag_configure("odd", background=self.colors.get("stripe_odd", self.colors["card"]), foreground=self.colors["text"])
        p_tree.tag_configure("month_header", background=self.colors["border"], foreground=self.colors["text"], font=("Segoe UI", 10, "bold"))
        p_tree.tag_configure("green_text", foreground=self.colors.get("accent_green", "#10b981"), font=("Segoe UI", 10, "bold"))
        p_tree.tag_configure("red_text", foreground=self.colors.get("error", "#ef4444"), font=("Segoe UI", 10, "bold"))
        p_tree.tag_configure("blue_text", foreground=self.colors.get("accent_blue", "#3b82f6"), font=("Segoe UI", 10, "bold"))
        # --------------------------------------------------------
        
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y": p_tree.yview_moveto(p_tree.yview()[0] + (delta * 0.008))
            else: p_tree.xview_moveto(p_tree.xview()[0] + (delta * 0.02))

        p_tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        p_tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        # --- THE FIX: The missing click handler to toggle checkboxes! ---
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
                    
                    # We just flip the checkbox and leave the colors completely alone
                    if str(iid) in selected_items:
                        selected_items.remove(str(iid))
                        vals[0] = "☐"
                        p_tree.item(iid, values=vals)
                    else:
                        selected_items.add(str(iid))
                        vals[0] = "☑"
                        p_tree.item(iid, values=vals)
                        
                    update_bulk_btns()

        # Blocks the ugly default blue highlight
        def prevent_native_selection(event):
            if is_bulk_mode[0]:
                for iid in p_tree.selection():
                    p_tree.selection_remove(iid)
            else:
                for iid in p_tree.selection():
                    if 'month_header' in p_tree.item(iid, 'tags') or 'empty' in p_tree.item(iid, 'tags'):
                        p_tree.selection_remove(iid)

        p_tree.bind("<ButtonRelease-1>", on_tree_click)
        p_tree.bind("<<TreeviewSelect>>", prevent_native_selection)
        # ----------------------------------------------------------------

        def delete_selected_payments():
            selected = p_tree.selection()
            valid_ids = [iid for iid in selected if not str(iid).startswith("month_") and not str(iid).startswith("empty_")]
            if not valid_ids: return
            
            conn = database.get_connection()
            c = conn.cursor()

            # 1. Pre-check for GST Locked Invoices
            for pid in valid_ids:
                c.execute("SELECT ref FROM party_payments WHERE id=?", (pid,))
                ref_row = c.fetchone()
                if ref_row and ref_row[0]:
                    for part in ref_row[0].split(" | "):
                        b_num = part.split(" (")[0].strip()
                        c.execute("SELECT ca_submitted FROM invoices WHERE invoice_number=? AND company_id=?", (b_num, self.comp_id))
                        inv_row = c.fetchone()
                        if inv_row and inv_row[0] == 1:
                            import tkinter.messagebox as messagebox
                            messagebox.showwarning("Locked", f"Payment deletion blocked.\n\nThis payment is linked to Invoice {b_num}, which is already GST Filed.", parent=pop)
                            conn.close()
                            return
                        c.execute("SELECT ca_submitted FROM purchases WHERE bill_number=? AND company_id=?", (b_num, self.comp_id))
                        purch_row = c.fetchone()
                        if purch_row and purch_row[0] == 1:
                            import tkinter.messagebox as messagebox
                            messagebox.showwarning("Locked", f"Payment deletion blocked.\n\nThis payment is linked to Purchase {b_num}, which is already GST Filed.", parent=pop)
                            conn.close()
                            return
            conn.close()
            
            import tkinter.messagebox as messagebox
            msg = "Are you sure you want to delete this payment record?\n\nThis will permanently reverse the payment, restoring the invoice/purchase balance and adjusting the advance wallet accordingly."
            if len(valid_ids) > 1:
                msg = f"Are you sure you want to bulk delete {len(valid_ids)} payment records?\n\nThis will permanently reverse the payments, restoring balances and advance wallets accordingly."
                
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
                            "Parties", "Payment Deleted", p_row[0] or "Party",
                            f"Reversed payment ({p_row[3]}) • Ref: {p_row[1]}",
                            abs(float(p_row[2] or 0.0)), company_id=self.comp_id
                        )
                    
                load_payments()
                if hasattr(self, 'load_data'): self.load_data()
            except Exception as e:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Database Error", str(e), parent=pop)

        ctx_menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=self.colors["card"], fg=self.colors["text"], activebackground=self.colors["accent_blue"], activeforeground="#ffffff")
        def show_ctx_menu(event):
            iid = p_tree.identify_row(event.y)
            if iid and not str(iid).startswith("month_") and not str(iid).startswith("empty_"):
                if iid not in p_tree.selection(): p_tree.selection_set(iid)
                ctx_menu.delete(0, "end")
                sel_count = len(p_tree.selection())
                
                if sel_count == 1:
                    ctx_menu.add_command(label="⭳ Export Record (CSV)", command=lambda: export_recent_csv(selected_only=True, override_id=iid))
                    ctx_menu.add_command(label="🖨️ Export Record (PDF)", command=lambda: export_recent_pdf(selected_only=True, override_id=iid))
                    ctx_menu.add_separator()
                    # --- THE FIX: Add Bulk Export trigger to Right-Click Menu ---
                    ctx_menu.add_command(label="📄 Bulk Select / Export", command=lambda: toggle_bulk_mode(initial_id=iid))
                    ctx_menu.add_separator()
                    # ------------------------------------------------------------
                    ctx_menu.add_command(label="❌ Delete Record", foreground=self.colors["error"], command=delete_selected_payments)
                else:
                    ctx_menu.add_command(label=f"⭳ Bulk Export {sel_count} Items (CSV)", command=lambda: export_recent_csv(selected_only=True))
                    ctx_menu.add_command(label=f"🖨️ Bulk Export {sel_count} Items (PDF)", command=lambda: export_recent_pdf(selected_only=True))
                    ctx_menu.add_separator()
                    ctx_menu.add_command(label=f"🗑 Bulk Delete {sel_count} Items", foreground=self.colors["error"], command=delete_selected_payments)
                
                ctx_menu.tk_popup(event.x_root, event.y_root)
                
        p_tree.bind("<Button-3>", show_ctx_menu)

        pag_frame = tk.Frame(pop, bg=self.colors["bg"])
        pag_frame.pack(side="bottom", fill="x", pady=(5, 15))
        center_pag = tk.Frame(pag_frame, bg=self.colors["bg"])
        center_pag.pack(anchor="center") 
        
        btn_prev = tk.Button(center_pag, text="< Previous", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=10, pady=2)
        btn_prev.pack(side="left", padx=5)
        lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Segoe UI", 9, "bold"), bg=self.colors["bg"], fg=self.colors["text_sec"])
        lbl_page.pack(side="left", padx=15)
        btn_next = tk.Button(center_pag, text="Next >", font=("Segoe UI", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="flat", cursor="hand2", padx=10, pady=2)
        btn_next.pack(side="left", padx=5)

        def load_payments(*args):
            for i in p_tree.get_children(): p_tree.delete(i)
            
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT id, pay_date, party_name, mode, ref, amount, notes, pay_type FROM party_payments WHERE company_id=? ORDER BY id DESC", (self.comp_id,))
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
                    try: 
                        to_dt = datetime.strptime(to_str, self.date_fmt_code)
                        to_dt = datetime.combine(to_dt, datetime.max.time())
                    except: pass

            filtered_rows.clear()
            
            parsed_rows = []
            for r in rows:
                p_id, p_date, p_party, p_mode, p_ref, p_amt, p_notes, p_type = r
                
                dt = datetime.min
                for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        dt = datetime.strptime(p_date, fmt)
                        break
                    except: pass
                parsed_rows.append((dt, r))
                
            parsed_rows.sort(key=lambda x: x[0], reverse=True)

            from views.invoice_parts.helpers import smart_date_formatter, format_currency
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
                
                m_group = dt.strftime("%B %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
                if m_group != current_month_group:
                    current_month_group = m_group
                    bg_tag = "even" if row_counter % 2 == 0 else "odd"
                    p_tree.insert("", "end", iid=f"month_{m_group}_{index}", values=("", f"📅  {m_group}", "", "", "", "", "", ""), tags=(bg_tag, "month_header"))
                    row_counter += 1
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                
                if "Contra / Bill Offset" in str(p_mode) or "Offset" in str(p_ref):
                    amt_str = f"⚖️ {format_currency(abs(p_amt), self.curr_fmt)}"
                    color_tag = "blue_text"
                    dir_str = "Contra / Offset"
                elif p_type == "receive":
                    if "Refunded from Vendor" in str(p_ref):
                        amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                        color_tag = "green_text"
                        dir_str = "In (Vendor Refund)"
                    else:
                        amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                        color_tag = "green_text"
                        dir_str = "In (Received)"
                else: 
                    if "Refunded to Customer" in str(p_ref):
                        amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                        color_tag = "red_text"
                        dir_str = "Out (Cust Refund)"
                    else:
                        amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                        color_tag = "red_text"
                        dir_str = "Out (Paid)"
                    
                tag = "even" if row_counter % 2 == 0 else "odd"
                
                col1 = ("☑" if str(p_id) in selected_items else "☐") if is_bulk_mode[0] else (start_idx + index + 1)
                
                # --- THE FIX: Keep original stripe colors and red/green text intact ---
                tag_tup = (tag, color_tag)
                # ----------------------------------------------------------------------
                    
                import re
                clean_ref = re.sub(r'\s*\([^)]*\)', '', str(p_ref)).strip()
                    
                p_tree.insert("", "end", iid=str(p_id), values=(col1, fmt_date, p_party, dir_str, clean_ref, p_mode, p_notes, amt_str, ""), tags=tag_tup)
                row_counter += 1
                
            for i in range(row_counter, items_per_page + 2):
                tag = "even" if i % 2 == 0 else "odd"
                p_tree.insert("", "end", iid=f"empty_{i}", values=("", "", "", "", "", "", "", "", ""), tags=(tag, "empty"))

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
            from views.invoice_parts.helpers import smart_date_formatter, format_currency
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
                    data.append(["", f"--- {current_month} ---", "", "", "", "", "", ""]) 
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
                import re
                clean_ref = re.sub(r'\s*\([^)]*\)', '', str(p_ref)).strip()
                
                if p_mode == "Contra / Bill Offset" or "Offset" in str(p_ref):
                    amt_str = f"Contra: {format_currency(abs(p_amt), self.curr_fmt)}"
                    dir_str = "Contra / Offset"
                elif p_type == "receive":
                    if "Refunded from Vendor" in str(p_ref):
                        amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                        dir_str = "In (Vendor Refund)"
                    else:
                        amt_str = f"+ {format_currency(abs(p_amt), self.curr_fmt)}"
                        dir_str = "In (Received)"
                else: 
                    if "Refunded to Customer" in str(p_ref):
                        amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                        dir_str = "Out (Cust Refund)"
                    else:
                        amt_str = f"- {format_currency(abs(p_amt), self.curr_fmt)}"
                        dir_str = "Out (Paid)"
                    
                data.append([str(sno), fmt_date, p_party, dir_str, clean_ref, p_mode, p_notes, amt_str])
                sno += 1
            return data

        def export_recent_csv(selected_only=False, override_id=None):
            import tkinter.messagebox as messagebox
            data = get_export_data(selected_only, override_id)
            if not data:
                messagebox.showinfo("Empty", "No data to export.", parent=pop)
                return
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Export Master Timeline CSV", parent=pop)
            if not file_path: return
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                    writer = csv.writer(file)
                    writer.writerow(["S.NO", "Date", "Party", "Direction", "Reference", "Mode", "Notes", "Amount"]) 
                    writer.writerows(data)
                messagebox.showinfo("Export Successful", f"Master Timeline exported to:\n{file_path}", parent=pop)
            except Exception as e: messagebox.showerror("Export Failed", str(e), parent=pop)

        def export_recent_pdf(selected_only=False, override_id=None):
            import tkinter.messagebox as messagebox
            data = get_export_data(selected_only, override_id)
            if not data:
                messagebox.showinfo("Empty", "No data to export.", parent=pop)
                return
            html_content = f"""
            <html>
            <head><meta charset="utf-8"><title>Master Timeline Export</title>
            <style>
                @media print {{ @page {{ margin: 0; size: landscape; }} body {{ margin: 1.5cm; }} }}
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                th, td {{ padding: 8px 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
                th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                .month-header td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; text-decoration: underline; border-bottom: 1px solid #cbd5e1; color: #1e293b; }}
            </style>
            </head>
            <body><h2>Master Timeline (All Parties)</h2>
            <table><thead><tr><th style="width:5%">S.NO</th><th style="width:10%">Date</th><th style="width:20%">Party Name</th><th style="width:12%">Direction</th><th style="width:15%">Reference</th><th style="width:12%">Mode</th><th style="width:13%">Notes</th><th style="width:13%; text-align:right;">Amount</th></tr></thead><tbody>
            """
            for r in data:
                if r[0] == "":
                    html_content += f'<tr class="month-header"><td colspan="8">{r[1]}</td></tr>'
                else:
                    html_content += f'<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td>{r[6]}</td><td style="text-align:right;">{r[7]}</td></tr>'
            html_content += "</tbody></table><script>window.onload=function(){window.print();}</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="Master_Timeline_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
            webbrowser.open('file://' + os.path.realpath(path))

        load_payments()