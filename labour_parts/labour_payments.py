import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import csv
import tempfile
import webbrowser
from datetime import date, datetime, timedelta

# --- Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)

import database
from views.invoice_parts.helpers import format_currency, smart_date_formatter, fetch_global_settings
from views.invoice_parts.calendar_widget import NativeCalendar

class LabourPaymentsDashboard(tk.Toplevel):
    def __init__(self, parent_tab, initial_filter=""):
        super().__init__(parent_tab)
        self.parent_tab = parent_tab
        self.transient(parent_tab.winfo_toplevel())
        
        self.title("Recent Labour Payments")
        self.geometry("1100x700")
        self.configure(bg=parent_tab.colors["bg"])
        self.grab_set()

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = int((sw/2) - (1100/2)), int((sh/2) - (700/2))
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

        self.pay_current_page = 1
        self.pay_items_per_page = 50
        self.pay_is_bulk_mode = False
        self.pay_selected_items = set()
        self.pay_filtered_rows = []
        self.pay_type_filter = initial_filter

        self.pay_search_var = tk.StringVar()
        self.pay_filter_var = tk.StringVar(value="All Time")
        self.pay_from_var = tk.StringVar(value="")
        self.pay_to_var = tk.StringVar(value="")

        self.pay_search_timer = None
        def trigger_pay_search(*args):
            if self.pay_search_timer: self.after_cancel(self.pay_search_timer)
            self.pay_search_timer = self.after(300, lambda: [self.reset_pay_page(), self.load_payments()])
        self.pay_search_var.trace_add("write", trigger_pay_search)

        self.pay_from_var.trace_add("write", lambda *args: [self.reset_pay_page(), self.load_payments()])
        self.pay_to_var.trace_add("write", lambda *args: [self.reset_pay_page(), self.load_payments()])

        def clear_focus(event):
            # --- THE FIX: Stop if the window is already closed! ---
            if not self.winfo_exists(): return
            # ------------------------------------------------------
            if str(event.widget).startswith(str(self)):
                if hasattr(event.widget, 'winfo_class'):
                    w_class = event.widget.winfo_class()
                    if w_class not in ('Entry', 'TCombobox', 'Text', 'Treeview', 'Button'):
                        self.focus_set()
                        if hasattr(self, 'tree_pay') and self.tree_pay.selection() and not getattr(self, 'pay_is_bulk_mode', False):
                            self.tree_pay.selection_remove(self.tree_pay.selection())
        self.bind_all("<ButtonPress-1>", clear_focus, add="+")

        self.comp_id = getattr(parent_tab.app, "active_company_id", 1)
        try: _, self.date_fmt_code = fetch_global_settings(self.comp_id)
        except: self.date_fmt_code = "%d.%m.%Y"

        self.build_ui()
        self.load_payments()

    def build_ui(self):
        t = self.parent_tab.colors
        style = ttk.Style(self)
        style.theme_use("default")
        
        # --- THE FIX: Adaptive Combobox Styling for Labour Payments ---
        style.configure("Pay.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], bordercolor=t["border"], arrowcolor=t["text"])
        style.map("Pay.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["text"])])
        self.option_add("*TCombobox*Listbox.background", t["card"])
        self.option_add("*TCombobox*Listbox.foreground", t["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", t["accent_blue"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        # --------------------------------------------------------------

        p_head = tk.Frame(self, bg=t["card"])
        p_head.pack(fill="x", pady=(20, 10), padx=20)
        
        # --- ROW 1: Title & Bulk Status Label ---
        row1 = tk.Frame(p_head, bg=t["card"])
        row1.pack(fill="x", padx=15, pady=(10, 5))
        
        tk.Label(row1, text=("TOTAL LABOUR " + self.pay_type_filter.upper() + "S" if self.pay_type_filter else "RECENT LABOUR PAYMENTS"), font=("Segoe UI", 12, "bold"), fg=t["text"], bg=t["card"]).pack(side="left")
        
        self.lbl_bulk_active = tk.Label(row1, text="Selection Mode Active", font=("Segoe UI", 11, "bold"), bg=t["card"], fg=t["error"])

        # --- ROW 2: Search, Filters, and Actions ---
        row2 = tk.Frame(p_head, bg=t["card"])
        row2.pack(fill="x", padx=15, pady=(5, 10))

        # 1. Search Box
        search_f = tk.Frame(row2, bg=t["card"])
        search_f.pack(side="left", padx=(0, 15))
        
        tk.Label(search_f, text="🔍 Search:", bg=t["card"], font=("Segoe UI", 9, "bold"), fg=t["text_sec"]).pack(side="left", padx=(0, 5))
        tk.Entry(search_f, textvariable=self.pay_search_var, font=("Segoe UI", 10), width=18, bg=t["bg"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1).pack(side="left", ipady=3)
        btn_clear_search = tk.Button(search_f, text="✖", font=("Arial", 9), bg=t["border"], fg=t["error"], activebackground=t["border"], activeforeground=t["error"], relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=lambda: self.pay_search_var.set(""))
        btn_clear_search.pack(side="left", padx=(2, 0), ipady=1, ipadx=3)

        # 2. Filters
        filter_f = tk.Frame(row2, bg=t["card"])
        filter_f.pack(side="left")

        tk.Label(filter_f, text="Filter:", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text_sec"]).pack(side="left", padx=(5, 5))
        date_cb = ttk.Combobox(filter_f, textvariable=self.pay_filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=12, font=("Segoe UI", 10), cursor="hand2", style="Pay.TCombobox")
        date_cb.pack(side="left", ipady=3)

        self.custom_date_f = tk.Frame(filter_f, bg=t["card"])
        tk.Label(self.custom_date_f, text="📅 From:", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text_sec"]).pack(side="left", padx=(10, 5))
        
        from_f = tk.Frame(self.custom_date_f, bg=t["bg"], highlightbackground=t["border"], highlightthickness=1)
        from_f.pack(side="left")
        tk.Entry(from_f, textvariable=self.pay_from_var, font=("Segoe UI", 10), width=10, bg=t["bg"], fg=t["text"], bd=0, insertbackground=t["text"]).pack(side="left", ipady=4, padx=5)
        from_btn = tk.Button(from_f, text="▼", bg=t["card"], fg=t["text"], relief="flat", cursor="hand2")
        from_btn.pack(side="left", ipadx=4, ipady=3)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(self, self.pay_from_var, anchor_widget=b))
        
        tk.Label(self.custom_date_f, text="To:", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text_sec"]).pack(side="left", padx=(10, 5))
        
        to_f = tk.Frame(self.custom_date_f, bg=t["bg"], highlightbackground=t["border"], highlightthickness=1)
        to_f.pack(side="left")
        tk.Entry(to_f, textvariable=self.pay_to_var, font=("Segoe UI", 10), width=10, bg=t["bg"], fg=t["text"], bd=0, insertbackground=t["text"]).pack(side="left", ipady=4, padx=5)
        to_btn = tk.Button(to_f, text="▼", bg=t["card"], fg=t["text"], relief="flat", cursor="hand2")
        to_btn.pack(side="left", ipadx=4, ipady=3)
        to_btn.config(command=lambda b=to_btn: NativeCalendar(self, self.pay_to_var, anchor_widget=b))

        btn_clear_filter = tk.Button(filter_f, text="✖", font=("Arial", 9), bg=t["border"], fg=t["error"], activebackground=t["border"], activeforeground=t["error"], relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=self.clear_pay_filters)
        
        def toggle_custom_date(*args):
            if self.pay_filter_var.get() == "Custom Range": self.custom_date_f.pack(side="left", before=btn_clear_filter)
            else: self.custom_date_f.pack_forget()
            self.reset_pay_page()
            self.load_payments()

        btn_clear_filter.pack(side="left", padx=(5, 0), ipady=1, ipadx=3)
        date_cb.bind("<<ComboboxSelected>>", toggle_custom_date)
        self.custom_date_f.pack_forget()

        # 4. Action Buttons
        self.action_f = tk.Frame(row2, bg=t["card"])
        self.action_f.pack(side="right")

        self.p_std_tools = tk.Frame(self.action_f, bg=t["card"])
        self.p_std_tools.pack(side="right")

        self.btn_export_pay = tk.Button(self.p_std_tools, text="📥 Export ▼", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", highlightbackground=t["border"], bd=1, cursor="hand2", padx=8, pady=2)
        self.btn_export_pay.pack(side="right", padx=(10, 0))

        export_menu = tk.Menu(self.btn_export_pay, tearoff=0, font=("Segoe UI", 10), bg=t["card"], fg=t["text"])
        export_menu.add_command(label="⭳ Export as CSV", command=lambda: self.export_payroll_csv(bulk=False))
        export_menu.add_command(label="🖨️ Export as PDF", command=lambda: self.export_payroll_pdf(bulk=False))
        self.btn_export_pay.config(command=lambda: export_menu.tk_popup(self.btn_export_pay.winfo_rootx(), self.btn_export_pay.winfo_rooty() + self.btn_export_pay.winfo_height()))
        
        btn_bulk_toggle = tk.Button(self.p_std_tools, text="☑ Select Mode", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", highlightbackground=t["border"], bd=1, cursor="hand2", padx=8, pady=2, command=self.enable_pay_bulk_mode)
        btn_bulk_toggle.pack(side="right", padx=(0, 0))

        self.p_bulk_tools = tk.Frame(self.action_f, bg=t["card"])
        
        btn_cancel_bulk = tk.Button(self.p_bulk_tools, text="Cancel", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", padx=10, pady=2, command=self.cancel_pay_bulk_mode)
        btn_cancel_bulk.pack(side="right", padx=(10, 0))
        
        self.btn_bulk_pay_del = tk.Button(self.p_bulk_tools, text="🗑 Delete Selected", font=("Segoe UI", 9, "bold"), bg=t["error"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=2, command=self.bulk_delete_pays)
        self.btn_bulk_pay_del.pack(side="right", padx=(10, 0))
        
        self.btn_bulk_export = tk.Button(self.p_bulk_tools, text="📥 Export ▼", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", highlightbackground=t["border"], bd=1, cursor="hand2", padx=8, pady=2)
        self.btn_bulk_export.pack(side="right", padx=(10, 0))

        btn_select_all_pay = tk.Button(self.p_bulk_tools, text="☑ Select All", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", highlightbackground=t["border"], bd=1, cursor="hand2", padx=8, pady=2, command=self.select_all_pay_bulk)
        btn_select_all_pay.pack(side="right", padx=(0, 0))

        bulk_export_menu = tk.Menu(self.btn_bulk_export, tearoff=0, font=("Segoe UI", 10), bg=t["card"], fg=t["text"])
        bulk_export_menu.add_command(label="⭳ Export as CSV", command=lambda: self.export_payroll_csv(bulk=True))
        bulk_export_menu.add_command(label="🖨️ Export as PDF", command=lambda: self.export_payroll_pdf(bulk=True))
        self.btn_bulk_export.config(command=lambda: bulk_export_menu.tk_popup(self.btn_bulk_export.winfo_rootx(), self.btn_bulk_export.winfo_rooty() + self.btn_bulk_export.winfo_height()))

        self.pay_pag_frame = tk.Frame(self, bg=t["bg"])
        self.pay_pag_frame.pack(side="bottom", fill="x", pady=(10, 15))
        center_pay_pag = tk.Frame(self.pay_pag_frame, bg=t["bg"])
        center_pay_pag.pack(anchor="center") 
        self.btn_pay_prev = tk.Button(center_pay_pag, text="< Previous", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", command=self.pay_prev_page, padx=10, pady=2)
        self.btn_pay_prev.pack(side="left", padx=5)
        self.lbl_pay_page = tk.Label(center_pay_pag, text="Page 1 of 1", font=("Segoe UI", 9, "bold"), bg=t["bg"], fg=t["text_sec"])
        self.lbl_pay_page.pack(side="left", padx=15)
        self.btn_pay_next = tk.Button(center_pay_pag, text="Next >", font=("Segoe UI", 9, "bold"), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", command=self.pay_next_page, padx=10, pady=2)
        self.btn_pay_next.pack(side="left", padx=5)

        # --- THE FIX: Isolated Styles & Ghost Column ---
        style.configure("LabourPay.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
        style.configure("LabourPay.Horizontal.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
        style.map("LabourPay.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
        style.map("LabourPay.Horizontal.TScrollbar", background=[("active", t["accent_blue"])])

        style.configure("Pay.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=t["header"], foreground=t["text"], relief="raised", borderwidth=3)
        style.map("Pay.Treeview.Heading", background=[('active', t["border"])])
        style.configure("Pay.Treeview", font=("Segoe UI", 10), rowheight=35, background=t["bg"], fieldbackground=t["bg"], foreground=t["text"], borderwidth=0)
        style.map("Pay.Treeview", background=[("selected", t["border"])], foreground=[("selected", t["text"])])

        tree_container_p = tk.Frame(self, bg=t["card"])
        tree_container_p.pack(side="top", fill="both", expand=True, padx=20)

        scroll_p_y = ttk.Scrollbar(tree_container_p, orient="vertical", style="LabourPay.Vertical.TScrollbar")
        scroll_p_y.pack(side="right", fill="y")
        scroll_p_x = ttk.Scrollbar(tree_container_p, orient="horizontal", style="LabourPay.Horizontal.TScrollbar")
        scroll_p_x.pack(side="bottom", fill="x")

        cols_p = ("sno_sel", "date", "labour", "type", "amount", "notes", "actions", "ghost")
        self.tree_pay = ttk.Treeview(tree_container_p, columns=cols_p, show="headings", style="Pay.Treeview", height=12, yscrollcommand=scroll_p_y.set, xscrollcommand=scroll_p_x.set)
        self.tree_pay.pack(side="left", fill="both", expand=True)
        scroll_p_y.config(command=self.tree_pay.yview)
        scroll_p_x.config(command=self.tree_pay.xview)
        # -----------------------------------------------

        # --- THE FIX: Buttery Scrolling, Locked Columns, Ghost Column, Misfire Block ---
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                self.tree_pay.yview_moveto(self.tree_pay.yview()[0] + (delta * 0.008))
            else:
                self.tree_pay.xview_moveto(self.tree_pay.xview()[0] + (delta * 0.02))
                
        self.tree_pay.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        self.tree_pay.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        self.tree_pay.heading("sno_sel", text="S.NO", anchor="center")
        self.tree_pay.heading("date", text="LOGGED DATE", anchor="center")
        self.tree_pay.heading("labour", text="WORKER / LABOUR", anchor="center")
        self.tree_pay.heading("type", text="TYPE", anchor="center")
        self.tree_pay.heading("amount", text="AMOUNT OUT", anchor="center")
        
        # --- THE FIX: Renamed Header ---
        self.tree_pay.heading("notes", text="NOTES", anchor="center")
        # -------------------------------
        
        self.tree_pay.heading("actions", text="ACTION", anchor="center")
        self.tree_pay.heading("ghost", text="")

        # --- THE FIX: Excel-Style Widths + Inventory Real-Time Saving Engine ---
        try:
            import json
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"labour_pay_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            w_dict = json.loads(res[0]) if res and res[0] else {}
        except:
            w_dict = {}

        self.tree_pay.column("sno_sel", width=w_dict.get("sno_sel", 60), minwidth=30, anchor="center", stretch=False)
        self.tree_pay.column("date", width=w_dict.get("date", 120), minwidth=60, anchor="center", stretch=False)
        self.tree_pay.column("labour", width=w_dict.get("labour", 250), minwidth=100, anchor="w", stretch=False)
        self.tree_pay.column("type", width=w_dict.get("type", 120), minwidth=60, anchor="center", stretch=False)
        self.tree_pay.column("amount", width=w_dict.get("amount", 150), minwidth=80, anchor="center", stretch=False)
        self.tree_pay.column("notes", width=w_dict.get("notes", 250), minwidth=100, anchor="w", stretch=False)
        self.tree_pay.column("actions", width=w_dict.get("actions", 120), minwidth=80, anchor="center", stretch=False)
        self.tree_pay.column("ghost", width=10, minwidth=10, stretch=True)

        def save_pay_widths():
            new_w = {c: self.tree_pay.column(c, "width") for c in ("sno_sel", "date", "labour", "type", "amount", "notes", "actions")}
            try:
                import json
                # --- THE FIX: Use safe helper to attach ACTIVE_COMPANY_ID and prevent ghost data! ---
                database.save_ui_setting(f"labour_pay_cols_{self.comp_id}", json.dumps(new_w))
                # ------------------------------------------------------------------------------------
            except: pass

        def on_pay_sep_drag(event):
            if self.tree_pay.identify_region(event.x, event.y) == "separator":
                self.after(50, save_pay_widths)
                
        self.tree_pay.bind("<B1-Motion>", on_pay_sep_drag, add="+")
        self.tree_pay.bind("<ButtonRelease-1>", lambda e: self.after(50, save_pay_widths) if self.tree_pay.identify_region(e.x, e.y) == "separator" else None, add="+")
        # -----------------------------------------------------------------------

        self.tree_pay.tag_configure("evenrow", background=t["bg"])
        self.tree_pay.tag_configure("oddrow", background=t["card"])
        
        self.tree_pay.tag_configure('month_header', background=t["border"], foreground=t["text"], font=("Segoe UI", 12, "bold"))
        self.tree_pay.tag_configure('bonus', foreground=t["accent_green"], font=("Segoe UI", 10, "bold"))
        self.tree_pay.tag_configure('advance', foreground=t["error"], font=("Segoe UI", 10, "bold"))
        self.tree_pay.tag_configure('payment', foreground=t["text"])
        self.tree_pay.tag_configure('selected_row', background=t["border"])
        self.tree_pay.tag_configure("empty_row", background=t["card"])

        def on_pay_motion(event):
            region = self.tree_pay.identify("region", event.x, event.y)
            if region == "separator": return
            col = self.tree_pay.identify_column(event.x)
            item = self.tree_pay.identify_row(event.y)
            if str(item).startswith("empty"): 
                self.tree_pay.config(cursor=""); return
            if region == "cell" and col == '#7' and not self.pay_is_bulk_mode: self.tree_pay.config(cursor="hand2")
            else: self.tree_pay.config(cursor="")
        self.tree_pay.bind("<Motion>", on_pay_motion)
        
        def on_pay_press(event):
            self._pay_press_region = self.tree_pay.identify("region", event.x, event.y)
        self.tree_pay.bind("<ButtonPress-1>", on_pay_press, add="+")

        def safe_pay_click(event):
            if getattr(self, "_pay_press_region", "") != "cell": return
            region = self.tree_pay.identify("region", event.x, event.y)
            if region != "cell": return
            self.on_payment_left_click(event)
        self.tree_pay.bind("<ButtonRelease-1>", safe_pay_click, add="+")
        # -----------------------------------------------------------------------------

    def reset_pay_page(self): self.pay_current_page = 1
    def pay_prev_page(self):
        if self.pay_current_page > 1: self.pay_current_page -= 1; self.load_payments()
    def pay_next_page(self):
        if hasattr(self, 'pay_total_pages') and self.pay_current_page < self.pay_total_pages: self.pay_current_page += 1; self.load_payments()

    def clear_pay_filters(self):
        self.pay_search_var.set("")
        self.pay_filter_var.set("All Time")
        self.pay_from_var.set("")
        self.pay_to_var.set("")
        self.pay_type_filter = ""
        if hasattr(self, 'custom_date_f'): self.custom_date_f.pack_forget()
        self.reset_pay_page()
        self.load_payments()
        self.lift()
        self.focus_force()

    def enable_pay_bulk_mode(self):
        self.pay_is_bulk_mode = True
        self.pay_selected_items.clear()
        self.p_std_tools.pack_forget()
        self.p_bulk_tools.pack(side="right")
        self.lbl_bulk_active.pack(side="right", padx=15)
        self.tree_pay.heading("sno_sel", text="☑")
        self.update_pay_bulk_btns()
        self.load_payments()

    def cancel_pay_bulk_mode(self):
        self.pay_is_bulk_mode = False
        self.pay_selected_items.clear()
        self.p_bulk_tools.pack_forget()
        self.lbl_bulk_active.pack_forget()
        self.p_std_tools.pack(side="right")
        self.tree_pay.heading("sno_sel", text="S.NO")
        self.load_payments()

    # --- THE FIX: Select All Logic ---
    def select_all_pay_bulk(self):
        valid_items = []
        for child in self.tree_pay.get_children():
            tags = self.tree_pay.item(child, "tags")
            if "month_header" in tags or "empty_row" in tags or "summary_row" in tags or "divider" in tags:
                continue
            if not str(child).startswith("empty"):
                valid_items.append(str(child))
                
        if not valid_items: return
                
        all_selected = all(item in self.pay_selected_items for item in valid_items)
        
        if all_selected:
            for item in valid_items:
                if item in self.pay_selected_items:
                    self.pay_selected_items.remove(item)
        else:
            for item in valid_items:
                self.pay_selected_items.add(item)
                
        self.update_pay_bulk_btns()
        self.load_payments()

    def update_pay_bulk_btns(self):
        count = len(self.pay_selected_items)
        self.btn_bulk_pay_del.config(text=f"🗑 Delete Selected ({count})")
        self.btn_bulk_export.config(text=f"📥 Export ({count}) ▼")

    def bulk_delete_pays(self):
        if not self.pay_selected_items: return
        
        allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(self.winfo_toplevel(), "active_company_id", 1))
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return
            
        if messagebox.askyesno("Confirm", f"Delete {len(self.pay_selected_items)} selected transaction logs?"):
            database.log_audit("Labours", "Bulk Deleted Payments", record_ref=f"{len(self.pay_selected_items)} Records", details="Bulk deleted labour payment records.", company_id=getattr(self.winfo_toplevel(), "active_company_id", 1))
            # --- THE FIX: Secure Undo/Redo Engine Hook ---
            deleted_rows = []
            for p_id in list(self.pay_selected_items):
                row = database.get_labour_ledger_record(int(p_id))
                if row: deleted_rows.append(row)
                
            try:
                for p_id in list(self.pay_selected_items):
                    database.delete_labour_ledger_and_attendance_rollback(int(p_id))
                    
                if deleted_rows: 
                    self.parent_tab.push_undo("BULK_DELETE_PAY", deleted_rows)
                # ---------------------------------------------
                self.cancel_pay_bulk_mode()
                self.parent_tab.load_data()
            except ValueError as e:
                messagebox.showerror("Database Error", str(e), parent=self)

    def load_payments(self):
        for item in self.tree_pay.get_children(): self.tree_pay.delete(item)
        rows = database.get_all_labour_payments_with_names()

        valid_rows = []
        for r in rows:
            pay_id, p_date, e_name, p_type, p_amount, p_notes = r
            dt = datetime.min
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(str(p_date).strip()[:10], fmt)
                    break
                except: pass
            valid_rows.append((dt, r))
                
        valid_rows.sort(key=lambda x: (x[0], x[1][0]), reverse=True)
        search_term = self.pay_search_var.get().lower()
        val = self.pay_filter_var.get()
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
            from_str = self.pay_from_var.get().strip()
            to_str = self.pay_to_var.get().strip()
            if from_str:
                for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        from_dt = datetime.strptime(from_str, fmt)
                        break
                    except: pass
            if to_str:
                for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        # Force the 'To' date to the very end of the day to capture all records
                        to_dt = datetime.strptime(to_str, fmt).replace(hour=23, minute=59, second=59)
                        break
                    except: pass

        self.pay_filtered_rows = []
        for dt, r in valid_rows:
            pay_id, p_date, e_name, p_type, p_amount, p_notes = r
            if dt != datetime.min:
                if from_dt and dt < from_dt: continue
                if to_dt and dt > to_dt: continue
            if self.pay_type_filter and self.pay_type_filter != p_type: continue
            if search_term:
                full_text = f"{e_name} {p_type} {p_notes} {p_amount}".lower()
                if search_term not in full_text: continue
            self.pay_filtered_rows.append((dt, r))

        self.pay_total_pages = max(1, (len(self.pay_filtered_rows) + self.pay_items_per_page - 1) // self.pay_items_per_page)
        if self.pay_current_page > self.pay_total_pages: self.pay_current_page = max(1, self.pay_total_pages)

        start_idx = (self.pay_current_page - 1) * self.pay_items_per_page
        page_items = self.pay_filtered_rows[start_idx : start_idx + self.pay_items_per_page]

        self.lbl_pay_page.config(text=f"Page {self.pay_current_page} of {self.pay_total_pages}")
        self.btn_pay_prev.config(state="normal" if self.pay_current_page > 1 else "disabled", bg=self.parent_tab.colors["card"] if self.pay_current_page > 1 else self.parent_tab.colors["bg"])
        self.btn_pay_next.config(state="normal" if self.pay_current_page < self.pay_total_pages else "disabled", bg=self.parent_tab.colors["card"] if self.pay_current_page < self.pay_total_pages else self.parent_tab.colors["bg"])

        current_month_group = ""
        row_counter = 0
        
        # --- THE FIX: Fetch DB settings exactly ONCE outside the loop to destroy the micro-stutter! ---
        try: curr_fmt, _ = fetch_global_settings(self.comp_id)
        except: curr_fmt = "Indian Rupees (₹)"
        # ----------------------------------------------------------------------------------------------

        for index, (dt, r) in enumerate(page_items):
            pay_id, p_date, e_name, p_type, p_amount, p_notes = r
            
            # --- THE FIX: Smart Regex Scrubber removes "Payment (Cash) - " prefixes ---
            if p_notes:
                import re
                p_notes = re.sub(rf'^{p_type}\s*\(.*?\)\s*-\s*', '', str(p_notes)).strip()
            # --------------------------------------------------------------------------
            
            m_group = dt.strftime("%B %Y") if dt != datetime.min else "Unknown Date"
            if m_group != current_month_group:
                current_month_group = m_group
                bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
                self.tree_pay.insert("", "end", values=("", f"📅 {m_group}", "", "", "", "", ""), tags=(bg_tag, "month_header"))
                row_counter += 1

            # --- THE FIX: Use cached format instead of hammering the DB 50 times ---
            amt_str = format_currency(abs(p_amount), curr_fmt)
            # -----------------------------------------------------------------------
            
            if p_type == "Bonus": fg_tag = "bonus"
            elif p_type == "Advance": fg_tag = "advance"
            else: fg_tag = "payment"

            formatted_p_date = smart_date_formatter(p_date, self.date_fmt_code)
            
            is_sel = str(pay_id) in self.pay_selected_items
            col1 = ("☑" if is_sel else "☐") if self.pay_is_bulk_mode else (start_idx + index + 1)
            
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            final_tags = ("selected_row", fg_tag) if is_sel and self.pay_is_bulk_mode else (bg_tag, fg_tag)

            self.tree_pay.insert("", "end", iid=str(pay_id), values=(col1, formatted_p_date, e_name if e_name else "Unknown", p_type, amt_str, p_notes, "❌ Delete"), tags=final_tags)
            row_counter += 1

        empty_p = ("", "", "", "", "", "", "")
        for i in range(len(page_items), self.pay_items_per_page + 2):
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            self.tree_pay.insert("", "end", iid=f"empty_p_{i}", values=empty_p, tags=("empty_row", bg_tag))
            row_counter += 1

    def on_payment_left_click(self, event):
        col = self.tree_pay.identify_column(event.x)
        pay_id_str = self.tree_pay.identify_row(event.y)
        if not pay_id_str or not str(pay_id_str).isdigit() or str(pay_id_str).startswith("empty"): return
        
        if self.pay_is_bulk_mode:
            if str(pay_id_str) in self.pay_selected_items: self.pay_selected_items.remove(str(pay_id_str))
            else: self.pay_selected_items.add(str(pay_id_str))
            self.update_pay_bulk_btns()
            self.load_payments()
            return

        if col == '#7':
            allowed, err_msg = database.check_labour_permission(action="delete", company_id=getattr(self.winfo_toplevel(), "active_company_id", 1))
            if not allowed:
                messagebox.showerror("Access Denied", err_msg, parent=self)
                return

            if messagebox.askyesno("Confirm", "Delete this transaction log?"):
                # --- THE FIX: Rollback BOTH Ledger and Attendance ---
                row = database.get_labour_ledger_record(int(pay_id_str))
                try:
                    database.delete_labour_ledger_and_attendance_rollback(int(pay_id_str))
                    
                    # --- THE FIX: Extract exact name and amount from the UI Table ---
                    vals = self.tree_pay.item(pay_id_str, "values")
                    e_name = vals[2] if len(vals) > 2 else "Unknown Worker"
                    p_type = vals[3] if len(vals) > 3 else "Payment"
                    amt_str = vals[4] if len(vals) > 4 else ""
                    
                    database.log_audit("Labours", "Deleted Payment", record_ref=e_name, details=f"Deleted {p_type} of {amt_str}.", company_id=getattr(self.winfo_toplevel(), "active_company_id", 1))
                    # ----------------------------------------------------------------
                    
                    if row: self.parent_tab.push_undo("DELETE_PAY", row)
                    # ----------------------------------------------------
                    self.parent_tab.load_data()
                    self.load_payments()
                except ValueError as e:
                    messagebox.showerror("Database Error", str(e), parent=self)

    def get_pay_export_data(self, bulk=False):
        data = []
        sno = 1
        current_month = ""
        
        # --- THE FIX: Fetch DB settings exactly ONCE outside the loop to destroy the export lag! ---
        try: curr_fmt, _ = fetch_global_settings(self.comp_id)
        except: curr_fmt = "Indian Rupees (₹)"
        # -------------------------------------------------------------------------------------------
        
        for dt, r in self.pay_filtered_rows:
            pay_id, p_date, e_name, p_type, p_amount, p_notes = r
            
            # --- THE FIX: Scrub prefixes for CSV and PDF exports! ---
            if p_notes:
                import re
                p_notes = re.sub(rf'^{p_type}\s*\(.*?\)\s*-\s*', '', str(p_notes)).strip()
            # --------------------------------------------------------
            
            if bulk and str(pay_id) not in self.pay_selected_items: continue
            m_group = dt.strftime("%B %Y") if dt != datetime.min else "Unknown Date"
            if m_group != current_month:
                current_month = m_group
                data.append(["", f"--- {current_month} ---", "", "", "", ""]) 
            
            # --- THE FIX: Use cached format instead of hammering the DB ---
            amt_str = format_currency(abs(p_amount), curr_fmt)
            # --------------------------------------------------------------
            formatted_p_date = smart_date_formatter(p_date, self.date_fmt_code)
            data.append([str(sno), formatted_p_date, e_name if e_name else "Unknown", p_type, amt_str, p_notes])
            sno += 1
        return data

    def export_payroll_csv(self, bulk=False):
        data = self.get_pay_export_data(bulk)
        if not data:
            messagebox.showinfo("Empty", "No data to export.", parent=self)
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Export Labour Payments CSV")
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["S.NO", "Date", "Worker", "Type", "Amount", "Notes"]) 
                writer.writerows(data)
            messagebox.showinfo("Export Successful", f"Records exported to:\n{file_path}", parent=self)
        except Exception as e: messagebox.showerror("Export Failed", str(e), parent=self)
        if bulk: self.cancel_pay_bulk_mode()

    def export_payroll_pdf(self, bulk=False):
        data = self.get_pay_export_data(bulk)
        if not data:
            messagebox.showinfo("Empty", "No data to export.", parent=self)
            return
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Labour Payments Export</title>
            <style>
                @media print {{ @page {{ margin: 0; size: auto; }} body {{ margin: 1.5cm; }} }}
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                th, td {{ padding: 8px 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
                th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                .data-row td {{ color: #000000; }}
                .month-header td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; text-decoration: underline; border-bottom: 1px solid #cbd5e1; color: #1e293b; }}
            </style>
        </head>
        <body>
            <h2>Labour Payments Report</h2>
            <table>
                <thead>
                    <tr><th style="width:5%">S.NO</th><th style="width:15%">Date</th><th style="width:25%">Worker</th><th style="width:15%">Type</th><th style="width:15%">Amount</th><th style="width:25%">Notes</th></tr>
                </thead>
                <tbody>
        """
        for r in data:
            if r[0] == "": html_content += f'<tr class="month-header"><td colspan="6">{r[1]}</td></tr>'
            else: html_content += f'<tr class="data-row"><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td></tr>'
        html_content += """
                </tbody>
            </table>
            <script> window.onload = function() { window.print(); } </script>
        </body>
        </html>
        """
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Labour_Payment_Export_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
        webbrowser.open('file://' + os.path.realpath(path))
        if bulk: self.cancel_pay_bulk_mode()