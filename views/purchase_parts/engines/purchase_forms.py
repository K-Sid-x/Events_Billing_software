import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import webbrowser
from datetime import datetime
import re
from views.home_parts.ui_components import get_theme

# --- THE FIX: Bulletproof Executable Pathing for Attachments ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# ---------------------------------------------------------------

import database
from views.invoice_parts.calendar_widget import NativeCalendar
from views.invoice_parts.helpers import grab_global_scroll, format_currency, enable_copy_paste
from views.purchase_parts.ui_components.purchase_grid import PurchaseGridEngine
from views.purchase_parts.engines.purchase_save_engine import PurchaseSaveEngine
from views.purchase_parts.ui_components.purchase_hsn import HSNSummaryTable

from views.purchase_parts.modals.add_party_modal import open_add_party_modal
from views.purchase_parts.modals.format_settings_modal import open_format_settings_modal

GST_STATES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra", "28": "Andhra Pradesh",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh",
    "38": "Ladakh"
}

class PurchaseForm:
    def __init__(self, parent_view, comp_id, curr_fmt, date_fmt_code, refresh_cb, purchase_id=None, clone_id=None):
        self.parent_view = parent_view
        self.comp_id = comp_id
        self.curr_fmt = curr_fmt
        self.date_fmt_code = date_fmt_code
        self.refresh_cb = refresh_cb
        self.undo_cb = getattr(parent_view, "add_to_undo_stack", None)
        
        self.purchase_id = int(purchase_id) if purchase_id else None
        self.clone_id = int(clone_id) if clone_id else None
        
        self.patch_database_for_vouchers()
        
        c = database.get_company(self.comp_id)
        self.has_gst = (c and c[8] == 1)

        t = get_theme()
        self.BG_COLOR = t["bg"]; self.CARD_BG = t["card"]; self.BORDER_COLOR = t["border"]
        self.TEXT_PRIMARY = t["text"]; self.TEXT_SECONDARY = t["sec"]
        self.ACCENT_BLUE = t["accent_blue"]; self.ACCENT_GREEN = t["accent_green"]; self.ERROR_COLOR = t["error"]
        self.HEADER_BG = t["card"]; self.HOVER_BG = t["card_hover"]
        self.BTN_HOVER = t["border"]; self.SAVE_HOVER = "#059669" if t["bg"] == "#0f172a" else "#047857"
        self.BLUE_HOVER = "#2563eb" if t["bg"] == "#0f172a" else "#0284c7"
        self.LIST_SEL = t["bulk_sel"]

        self.pop = tk.Toplevel(parent_view)
        
        if self.purchase_id: self.pop.title("Edit Purchase Voucher")
        else: self.pop.title("New Purchase Voucher")
            
        self.pop.state('zoomed')
        self.pop.configure(bg=self.BG_COLOR)
        self.pop.grab_set()

        self.all_vendors = []
        self.vendor_var = tk.StringVar()
        self.bill_var = tk.StringVar()
        self.date_var = tk.StringVar(value=datetime.now().strftime(self.date_fmt_code))
        self.eway_var = tk.StringVar()
        
        self.internal_voucher_var = tk.StringVar()
        self.internal_date_var = tk.StringVar(value=datetime.now().strftime(self.date_fmt_code))
        
        self.subtotal_var = tk.StringVar(value="0.00")
        self.subtotal_disp = tk.StringVar(value="0.00")
        self.cgst_var = tk.StringVar(value="0.00")
        self.cgst_disp = tk.StringVar(value="0.00")
        self.sgst_var = tk.StringVar(value="0.00")
        self.sgst_disp = tk.StringVar(value="0.00")
        self.igst_var = tk.StringVar(value="0.00")
        self.igst_disp = tk.StringVar(value="0.00")
        self.total_var = tk.StringVar(value="0.00")
        self.total_disp = tk.StringVar(value="0.00")
        self.receipt_var = tk.StringVar()

        self.build_ui()
        self.load_vendors()
        
        if self.purchase_id or self.clone_id:
            self.preload_existing_data()
            if self.clone_id:
                self.internal_voucher_var.set(self.generate_internal_voucher())
        else:
            self.internal_voucher_var.set(self.generate_internal_voucher())
        
        self.vendor_var.trace_add("write", self.on_vendor_type)
        self.bill_var.trace_add("write", self.check_supplier_bill)
        self.internal_voucher_var.trace_add("write", self.check_internal_voucher)

        self.grid_engine.update_totals()

        # --- THE FIX: Bulletproof Unsaved Changes Tracker for Purchases ---
        self.is_dirty = False
        def mark_dirty(e=None, *args):
            if e and getattr(e, 'keysym', '') in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Tab', 'Return', 'Escape', 'Up', 'Down', 'Left', 'Right', 'MouseWheel'):
                return
            self.is_dirty = True

        self.pop.bind("<Key>", mark_dirty, add="+")
        self.pop.bind("<<ComboboxSelected>>", mark_dirty, add="+")
        
        # Track main input fields
        self.vendor_var.trace_add("write", mark_dirty)
        self.bill_var.trace_add("write", mark_dirty)
        self.date_var.trace_add("write", mark_dirty)
        self.internal_voucher_var.trace_add("write", mark_dirty)
        self.internal_date_var.trace_add("write", mark_dirty)
        self.subtotal_var.trace_add("write", mark_dirty)

        def on_closing():
            if getattr(self, 'is_dirty', False):
                if messagebox.askyesno("Unsaved Changes", "You have unsaved changes.\n\nAre you sure you want to close without saving?", parent=self.pop):
                    self.pop.destroy()
            else:
                self.pop.destroy()

        self.pop.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Wipe the dirty flag clean AFTER the purchase bill finishes loading!
        # (Using 600ms to safely bypass the 300ms delayed refresh in preload)
        self.pop.after(600, lambda: setattr(self, "is_dirty", False))
        # ------------------------------------------------------------------

    def preload_existing_data(self):
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            source_id = self.purchase_id if self.purchase_id else self.clone_id
            
            # --- THE FIX: Added company_id lock, vendor_id, internal_date, and eway_bill fetch ---
            c.execute("SELECT purchase_date, bill_number, vendor_name, internal_voucher, receipt_path, is_draft, vendor_id, internal_date, eway_bill FROM purchases WHERE id=? AND company_id=?", (source_id, self.comp_id))
            row = c.fetchone()
            if row:
                # --- THE FIX: Only fetch old dates and bills if Editing. Clones get fresh ones! ---
                if self.purchase_id:
                    self.date_var.set(row[0] if row[0] else "")
                    self.bill_var.set(row[1] if row[1] else "")
                    self.internal_date_var.set(row[7] if (len(row) > 7 and row[7]) else (row[0] if row[0] else ""))
                    self.eway_var.set(row[8] if (len(row) > 8 and row[8]) else "")
                # ----------------------------------------------------------------------------------
                
                raw_vid = row[6] if len(row) > 6 else None
                self.target_vend_id = int(raw_vid) if (raw_vid is not None and str(raw_vid).isdigit()) else None
                self.vendor_var.set(row[2] if row[2] else "")
                self.on_vendor_select()
                
                is_draft = row[5] == 1 if row[5] else False
                
                if self.purchase_id and row[3]: 
                    draft_voucher = row[3].strip()
                    if is_draft:
                        # --- THE FIX: Check if the draft's voucher is already taken by a finalized bill ---
                        conn_chk = database.get_connection()
                        c_chk = conn_chk.cursor()
                        c_chk.execute("SELECT id FROM purchases WHERE LOWER(internal_voucher)=LOWER(?) AND is_deleted=0 AND is_draft=0 AND company_id=?", (draft_voucher, self.comp_id))
                        is_taken = c_chk.fetchone()
                        conn_chk.close()
                        
                        if is_taken:
                            self.internal_voucher_var.set(self.generate_internal_voucher())
                        else:
                            self.internal_voucher_var.set(draft_voucher)
                        # ----------------------------------------------------------------------------------
                    else:
                        self.internal_voucher_var.set(draft_voucher)
                        self.original_voucher_lower = draft_voucher.lower() 
                
                if self.purchase_id and row[4]: self.receipt_var.set(row[4])
            
            c.execute("SELECT item_name, hsn, rate, quantity, amount, unit, gst_rate, rate_inc_tax FROM purchase_items WHERE purchase_id=?", (source_id,))
            items = c.fetchall()
            conn.close()

            def _clean_num(val):
                try:
                    v = float(val)
                    return str(int(v)) if v.is_integer() else str(v)
                except: return str(val)

            if items:
                for i, it in enumerate(items):
                    if i >= len(self.grid_engine.rows_data):
                        if hasattr(self.grid_engine, 'add_row'):
                            self.grid_engine.add_row()
                        else:
                            break
                    r = self.grid_engine.rows_data[i]
                    if 'item' in r: r['item'].set(it[0])
                    if 'hsn' in r: r['hsn'].set(it[1])
                    if 'rate' in r: r['rate'].set(_clean_num(it[2]))
                    if 'qty' in r: r['qty'].set(_clean_num(it[3]))
                    if 'unit' in r: r['unit'].set(it[5])
                    if 'gst' in r: r['gst'].set(_clean_num(it[6]))
                    if 'rate_inc' in r: r['rate_inc'].set(_clean_num(it[7]))
                    
                    r['raw_amt'] = float(it[4])
                    
                    for key in ['amt', 'amount', 'amt_var', 'amt_disp']:
                        if key in r and isinstance(r[key], tk.StringVar):
                            r[key].set(format_currency(float(it[4]), self.curr_fmt))
                
                def _delayed_refresh():
                    for row_data in self.grid_engine.rows_data:
                        if hasattr(self.grid_engine, 'calculate_row'):
                            self.grid_engine.calculate_row(row_data)
                        elif hasattr(self.grid_engine, '_calc_row'):
                            self.grid_engine._calc_row(row_data)
                            
                    if hasattr(self.grid_engine, 'update_totals'):
                        self.grid_engine.update_totals()
                        
                    if self.has_gst and getattr(self, "hsn_table", None) and hasattr(self.hsn_table, "update_summary"):
                        self.hsn_table.update_summary()
                
                self.pop.after(150, _delayed_refresh)
                self.pop.after(300, _delayed_refresh) 
                
        except Exception as e:
            print("Preload Error:", e)

    def add_hover(self, widget, default_bg, hover_bg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

    def patch_database_for_vouchers(self):
        conn = None
        try:
            conn = database.get_connection()
            c = conn.cursor()
            for sql in (
                "ALTER TABLE purchases ADD COLUMN internal_voucher TEXT",
                "ALTER TABLE purchases ADD COLUMN internal_date TEXT DEFAULT ''",
                "ALTER TABLE purchases ADD COLUMN eway_bill TEXT DEFAULT ''",
                "ALTER TABLE company ADD COLUMN purchase_voucher_format TEXT DEFAULT 'PV-[YYYY]-[SEQ]'"
            ):
                try:
                    c.execute(sql)
                except Exception:
                    pass
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                try: conn.close()
                except Exception: pass

    def get_financial_year(self):
        now = datetime.now()
        if now.month >= 4: return f"{str(now.year)[-2:]}-{str(now.year+1)[-2:]}"
        else: return f"{str(now.year-1)[-2:]}-{str(now.year)[-2:]}"

    def generate_internal_voucher(self, preview_mode=False, custom_fmt=None):
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            if not custom_fmt:
                c.execute("SELECT purchase_voucher_format FROM company WHERE id=?", (self.comp_id,))
                row = c.fetchone()
                fmt = row[0] if row and row[0] else "PV-[YYYY]-[SEQ]"
            else:
                fmt = custom_fmt
            
            self.current_raw_format = fmt
            
            now = datetime.now()
            fmt = fmt.replace("[YYYY]", str(now.year))
            fmt = fmt.replace("[YY]", str(now.year)[-2:])
            fmt = fmt.replace("[MM]", f"{now.month:02d}")
            fmt = fmt.replace("[FY]", self.get_financial_year())
            
            # --- THE FIX: Isolate the Prefix and Suffix just like Invoices does to prevent sequence crashes! ---
            if "[SEQ]" not in fmt: fmt += "[SEQ]"
            
            parts = fmt.split("[SEQ]")
            prefix = parts[0]
            suffix = parts[1] if len(parts) > 1 else ""
            
            c.execute("SELECT internal_voucher FROM purchases WHERE company_id=? AND is_deleted=0 AND internal_voucher LIKE ?", (self.comp_id, f"{prefix}%"))
            rows = c.fetchall()
            conn.close()
            
            max_seq = 0
            for r in rows:
                if r[0]:
                    try:
                        seq_part = r[0]
                        # Safely strip the prefix and suffix to isolate JUST the number
                        if prefix and seq_part.startswith(prefix):
                            seq_part = seq_part[len(prefix):]
                        if suffix and seq_part.endswith(suffix):
                            seq_part = seq_part[:-len(suffix)]
                            
                        seq_str = "".join(filter(str.isdigit, seq_part))
                        if seq_str:
                            seq = int(seq_str)
                            if seq > max_seq: max_seq = seq
                    except: pass
            
            self.current_inv_count = max_seq + 1
            # -------------------------------------------------------------------------------------------------
            # --- THE FIX: We added :02d so '1' becomes '01' ---
            return fmt.replace("[SEQ]", f"{max_seq + 1:02d}")
        except:
            return "PV-AUTO"
            
    def get_formatted_voucher_num(self, fmt, count):
        now = datetime.now()
        fmt = fmt.replace("[YYYY]", str(now.year))
        fmt = fmt.replace("[YY]", str(now.year)[-2:])
        fmt = fmt.replace("[MM]", f"{now.month:02d}")
        fmt = fmt.replace("[FY]", self.get_financial_year())
        if "[SEQ]" not in fmt: fmt += "[SEQ]"
        # --- THE FIX: We added :02d so '1' becomes '01' ---
        return fmt.replace("[SEQ]", f"{int(count):02d}")

    def focus_next(self, event):
        event.widget.tk_focusNext().focus()
        return "break"

    def build_ui(self):
        # --- THE FIX: This click listener clears the blinking cursor when you click on the background ---
        def drop_focus(event):
            try:
                w_class = event.widget.winfo_class()
                if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button'):
                    self.pop.focus_set()
            except: pass
        self.pop.bind("<Button-1>", drop_focus, add="+")

        style = ttk.Style(self.pop)
        style.theme_use('default')
        style.configure("TCombobox", fieldbackground=self.BG_COLOR, background=self.CARD_BG, foreground=self.TEXT_PRIMARY, bordercolor=self.BORDER_COLOR, arrowcolor=self.TEXT_PRIMARY)
        style.map('TCombobox', fieldbackground=[('readonly', self.BG_COLOR)], selectbackground=[('readonly', self.ACCENT_BLUE)], selectforeground=[('readonly', '#ffffff')])

        pinned_header = tk.Frame(self.pop, bg=self.BG_COLOR)
        pinned_header.pack(side="top", fill="x", padx=20, pady=(15, 0))
        
        title_txt = "🛒 Edit Purchase Voucher" if self.purchase_id else "🛒 Purchase Voucher"
        tk.Label(pinned_header, text=title_txt, font=("Segoe UI", 20, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(side="left")

        self.fixed_footer = tk.Frame(self.pop, bg=self.BG_COLOR)
        self.fixed_footer.pack(side="bottom", fill="x", padx=20, pady=(0, 20))

        canvas_wrapper = tk.Frame(self.pop, bg=self.BG_COLOR)
        canvas_wrapper.pack(side="top", fill="both", expand=True, padx=(20, 0), pady=(15, 15))

        self.master_canvas = tk.Canvas(canvas_wrapper, bg=self.BG_COLOR, highlightthickness=0)
        self.master_scroll = ttk.Scrollbar(canvas_wrapper, orient="vertical", command=self.master_canvas.yview)
        
        main_f = tk.Frame(self.master_canvas, bg=self.BG_COLOR)
        
        def _lock_scrollregion(e):
            bbox = self.master_canvas.bbox("all")
            if bbox:
                self.master_canvas.configure(scrollregion=(0, 0, bbox[2], max(bbox[3], self.master_canvas.winfo_height())))

        main_f.bind("<Configure>", _lock_scrollregion)
        self.master_canvas.create_window((0, 0), window=main_f, anchor="nw")
        self.master_canvas.bind("<Configure>", lambda e: self.master_canvas.itemconfig(self.master_canvas.find_withtag("all")[0], width=e.width))
        
        self.master_canvas.pack(side="left", fill="both", expand=True)
        self.master_scroll.pack(side="right", fill="y")
        self.master_canvas.configure(yscrollcommand=self.master_scroll.set)
        
        grab_global_scroll(self.pop, self.master_canvas)

        top_dash = tk.Frame(main_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=20, pady=15)
        top_dash.pack(fill="x", pady=(0, 15))
        
        top_dash.columnconfigure(0, weight=1, uniform="group1")
        top_dash.columnconfigure(1, weight=1, uniform="group1")
        top_dash.columnconfigure(2, weight=1, uniform="group1")
        
        col1 = tk.Frame(top_dash, bg=self.CARD_BG)
        col1.grid(row=0, column=0, sticky="nwse", padx=(0, 10))
        tk.Label(col1, text="Vendor / Party *", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        v_f = tk.Frame(col1, bg=self.CARD_BG)
        v_f.pack(fill="x", pady=(2, 5))
        self.ent_vendor = tk.Entry(v_f, textvariable=self.vendor_var, font=("Segoe UI", 11), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR)
        self.ent_vendor.pack(side="left", fill="x", expand=True, ipady=3)
        self.lst_vendor = tk.Listbox(self.pop, font=("Segoe UI", 11), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, selectbackground=self.LIST_SEL, selectforeground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR, cursor="hand2")
        
        def hide_listbox(*args): self.pop.after(150, lambda: self.lst_vendor.place_forget())
        self.ent_vendor.bind("<FocusOut>", hide_listbox)
        
        def move_up(e):
            if self.lst_vendor.winfo_ismapped():
                sel = self.lst_vendor.curselection()
                if not sel: self.lst_vendor.selection_set(0)
                elif sel[0] > 0:
                    self.lst_vendor.selection_clear(sel[0])
                    self.lst_vendor.selection_set(sel[0]-1)
                    self.lst_vendor.see(sel[0]-1)
                return "break"
        def move_down(e):
            if self.lst_vendor.winfo_ismapped():
                sel = self.lst_vendor.curselection()
                if not sel: self.lst_vendor.selection_set(0)
                elif sel[0] < self.lst_vendor.size()-1:
                    self.lst_vendor.selection_clear(sel[0])
                    self.lst_vendor.selection_set(sel[0]+1)
                    self.lst_vendor.see(sel[0]+1)
                return "break"
        # --- THE FIX: Extract clean name and ID back out of the map ---
        def select_item(e=None):
            if self.lst_vendor.winfo_ismapped() and self.lst_vendor.curselection():
                chosen_disp = self.lst_vendor.get(self.lst_vendor.curselection())
                map_data = self.cust_display_map.get(chosen_disp)
                
                if map_data:
                    actual_name = map_data["name"]
                    self.target_vend_id = map_data["id"]
                else:
                    actual_name = chosen_disp
                    self.target_vend_id = None
                
                self.vendor_var.set(actual_name)
                self.lst_vendor.place_forget()
                self.ent_vendor.icursor("end")
                self.on_vendor_select()
                return "break"
        # -------------------------------------------------------

        self.ent_vendor.bind("<Up>", move_up)
        self.ent_vendor.bind("<Down>", move_down)
        self.ent_vendor.bind("<Return>", select_item)
        self.lst_vendor.bind("<<ListboxSelect>>", select_item)
        
        btn_add_party = tk.Button(v_f, text="➕ Add Party", font=("Segoe UI", 9, "bold"), bg=self.HOVER_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10, command=lambda: open_add_party_modal(self))
        btn_add_party.pack(side="left", padx=(5, 0), ipady=2)
        self.add_hover(btn_add_party, self.HOVER_BG, self.BTN_HOVER)
        
        self.prof_f = tk.Frame(col1, bg=self.CARD_BG, padx=0, pady=8)
        self.prof_f.pack(fill="x", pady=(5, 0))
        
        def lbl(p, t): return tk.Label(p, text=t, font=("Segoe UI", 10), bg=self.CARD_BG, fg=self.TEXT_SECONDARY)
        def val(p): return tk.Label(p, text="N/A", font=("Segoe UI", 11, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY)
        
        r_addr = tk.Frame(self.prof_f, bg=self.CARD_BG)
        r_addr.pack(fill="x", pady=(0, 3))
        lbl_addr = lbl(r_addr, "Address: ")
        lbl_addr.pack(side="left", anchor="nw") 
        self.lbl_v_addr = val(r_addr)
        self.lbl_v_addr.config(wraplength=280, justify="left", anchor="nw") 
        self.lbl_v_addr.pack(side="left", anchor="nw", fill="x", expand=True)

        r1 = tk.Frame(self.prof_f, bg=self.CARD_BG)
        r1.pack(fill="x")
        lbl(r1, "Phone: ").pack(side="left"); self.lbl_v_phone = val(r1); self.lbl_v_phone.pack(side="left")
        
        self.lbl_v_gst = val(r1)
        
        r2 = tk.Frame(self.prof_f, bg=self.CARD_BG)
        self.lbl_v_state = val(r2)
        self.lbl_v_scode = val(r2)

        if self.has_gst:
            lbl(r1, "  GSTIN: ").pack(side="left")
            self.lbl_v_gst.pack(side="left")
            
            r2.pack(fill="x", pady=(3,0))
            lbl(r2, "State: ").pack(side="left")
            self.lbl_v_state.pack(side="left")
            
            lbl(r2, "  Code: ").pack(side="left")
            self.lbl_v_scode.pack(side="left")

        col2 = tk.Frame(top_dash, bg=self.CARD_BG)
        col2.grid(row=0, column=1, sticky="nwse", padx=10)
        tk.Label(col2, text="Supplier Bill No. *", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        ent_bill = tk.Entry(col2, textvariable=self.bill_var, font=("Segoe UI", 11), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR)
        ent_bill.pack(fill="x", pady=(2, 2), ipady=3)
        self.lbl_warn_bill = tk.Label(col2, text="", font=("Segoe UI", 8, "bold"), bg=self.CARD_BG, fg=self.ERROR_COLOR)
        self.lbl_warn_bill.pack(anchor="w", pady=(0, 5))
        
        tk.Label(col2, text="Supplier Bill Date", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        d_f1 = tk.Frame(col2, bg=self.CARD_BG)
        d_f1.pack(fill="x", pady=(2, 10))
        d_ent1 = tk.Entry(d_f1, textvariable=self.date_var, font=("Segoe UI", 11), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR)
        d_ent1.pack(side="left", fill="x", expand=True, ipady=3)
        btn_cal1 = tk.Button(d_f1, text="📅", bg=self.HOVER_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2")
        btn_cal1.pack(side="left", padx=(5,0))
        btn_cal1.config(command=lambda b=btn_cal1: NativeCalendar(self.pop, self.date_var, anchor_widget=b))
        self.add_hover(btn_cal1, self.HOVER_BG, self.BTN_HOVER)
        
        tk.Label(col2, text="E-Way Bill No.", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        tk.Entry(col2, textvariable=self.eway_var, font=("Segoe UI", 11), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR).pack(fill="x", pady=(2, 0), ipady=3)

        col3 = tk.Frame(top_dash, bg=self.CARD_BG)
        col3.grid(row=0, column=2, sticky="nwse", padx=(10, 0))
        lbl_f = tk.Frame(col3, bg=self.CARD_BG)
        lbl_f.pack(fill="x", anchor="w")
        tk.Label(lbl_f, text="Internal Voucher No.", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(side="left")
        
        btn_fmt = tk.Button(lbl_f, text="⚙ Format", font=("Segoe UI", 8, "bold"), bg=self.HOVER_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=5, pady=0, command=lambda: open_format_settings_modal(self))
        btn_fmt.pack(side="right")
        self.add_hover(btn_fmt, self.HOVER_BG, self.BTN_HOVER)
        
        ent_int_v = tk.Entry(col3, textvariable=self.internal_voucher_var, font=("Segoe UI", 13, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_BLUE, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR, state="normal")
        ent_int_v.pack(fill="x", pady=(2, 2), ipady=3)
        self.lbl_warn_int = tk.Label(col3, text="", font=("Segoe UI", 8, "bold"), bg=self.CARD_BG, fg=self.ERROR_COLOR)
        self.lbl_warn_int.pack(anchor="w", pady=(0, 5))
        enable_copy_paste(ent_int_v)
        
        self.current_int_val = self.internal_voucher_var.get()
        def on_int_focus_in(e):
            self.current_int_val = self.internal_voucher_var.get()
            ent_int_v.delete(0, 'end') 
            
        def on_int_focus_out(e):
            val = self.internal_voucher_var.get().strip()
            if not val: 
                self.internal_voucher_var.set(self.current_int_val) 
            elif val.isdigit(): 
                # --- THE FIX: Disabled auto-formatting during edit mode to protect manual overrides ---
                if not self.purchase_id:
                    self.internal_voucher_var.set(self.get_formatted_voucher_num(getattr(self, "current_raw_format", "PV-[YYYY]-[SEQ]"), int(val)))
                # --------------------------------------------------------------------------------------
                
        ent_int_v.bind("<FocusIn>", on_int_focus_in)
        ent_int_v.bind("<FocusOut>", on_int_focus_out)
        ent_int_v.bind("<Return>", lambda e: [on_int_focus_out(e), self.focus_next(e)])
        
        tk.Label(col3, text="Internal Entry Date", font=("Segoe UI", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY).pack(anchor="w")
        d_f2 = tk.Frame(col3, bg=self.CARD_BG)
        d_f2.pack(fill="x", pady=(2, 0))
        d_ent2 = tk.Entry(d_f2, textvariable=self.internal_date_var, font=("Segoe UI", 11), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.BORDER_COLOR)
        d_ent2.pack(side="left", fill="x", expand=True, ipady=3)
        btn_cal2 = tk.Button(d_f2, text="📅", bg=self.HOVER_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2")
        btn_cal2.pack(side="left", padx=(5,0))
        btn_cal2.config(command=lambda b=btn_cal2: NativeCalendar(self.pop, self.internal_date_var, anchor_widget=b))
        self.add_hover(btn_cal2, self.HOVER_BG, self.BTN_HOVER)
        
        grid_f = tk.Frame(main_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        grid_f.pack(fill="both", expand=True, pady=(0, 5))
        
        self.grid_engine = PurchaseGridEngine(self, grid_f)

        mid_bot_f = tk.Frame(self.fixed_footer, bg=self.BG_COLOR)
        mid_bot_f.pack(fill="x", pady=(0, 15))

        tot_f = tk.Frame(mid_bot_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1, padx=20, pady=15)
        tot_f.pack(side="right", fill="y")

        def make_tot_row(parent, lbl_txt, disp_var, is_bold=False, fg_color=self.TEXT_PRIMARY):
            f = tk.Frame(parent, bg=self.CARD_BG)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=lbl_txt, font=("Segoe UI", 11, "bold" if is_bold else "normal"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, width=16, anchor="w").pack(side="left")
            tk.Label(f, textvariable=disp_var, font=("Segoe UI", 12, "bold" if is_bold else "normal"), bg=self.CARD_BG, fg=fg_color, width=18, anchor="e").pack(side="right")
            return f

        make_tot_row(tot_f, "Taxable Subtotal :" if self.has_gst else "Subtotal :", self.subtotal_disp)
        
        if self.has_gst:
            self.row_cgst = make_tot_row(tot_f, "Total CGST :", self.cgst_disp)
            self.row_sgst = make_tot_row(tot_f, "Total SGST :", self.sgst_disp)
            self.row_igst = make_tot_row(tot_f, "Total IGST :", self.igst_disp)
        
        self.grand_line = tk.Frame(tot_f, height=1, bg=self.BORDER_COLOR)
        self.grand_line.pack(fill="x", pady=6)
        make_tot_row(tot_f, "GRAND TOTAL :", self.total_disp, is_bold=True, fg_color=self.ACCENT_GREEN)

        tax_f = tk.Frame(mid_bot_f, bg=self.BG_COLOR)
        tax_f.pack(side="left", fill="both", expand=True, padx=(0, 20))
        
        if self.has_gst:
            self.hsn_table = HSNSummaryTable(tax_f, self)
        else:
            self.hsn_table = None

        bot_f = tk.Frame(self.fixed_footer, bg=self.BG_COLOR)
        bot_f.pack(fill="x") 
        
        status_f = tk.Frame(bot_f, bg=self.BG_COLOR)
        status_f.pack(side="left")

        def attach_receipt():
            path = filedialog.askopenfilename(parent=self.pop, title="Select Receipt", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
            if path: self.receipt_var.set(path)
            
        btn_attach = tk.Button(status_f, text="📎 Attach Receipt", font=("Segoe UI", 10), bg=self.HOVER_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=15, command=attach_receipt)
        btn_attach.pack(side="left", padx=(20, 5))
        self.add_hover(btn_attach, self.HOVER_BG, self.BTN_HOVER)
        
        self.btn_view_rec = tk.Button(status_f, text="👁 View", font=("Segoe UI", 9, "bold"), bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10)
        
        def view_attached_receipt():
            path = self.receipt_var.get()
            if path and os.path.exists(path):
                try: os.startfile(path)
                except: webbrowser.open(path)
                
        self.btn_view_rec.config(command=view_attached_receipt)
        self.add_hover(self.btn_view_rec, self.BORDER_COLOR, self.HOVER_BG)
        
        def toggle_view_btn(*args):
            if self.receipt_var.get() and os.path.exists(self.receipt_var.get()):
                self.btn_view_rec.pack(side="left", padx=5)
            else:
                self.btn_view_rec.pack_forget()
                
        self.receipt_var.trace_add("write", toggle_view_btn)
        tk.Label(status_f, textvariable=self.receipt_var, bg=self.BG_COLOR, fg=self.TEXT_SECONDARY, font=("Segoe UI", 8)).pack(side="left", padx=5)

        self.btn_post = tk.Button(bot_f, text="💾 Save Voucher", font=("Segoe UI", 12, "bold"), bg=self.ACCENT_GREEN, fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8)
        self.btn_post.pack(side="right")
        self.add_hover(self.btn_post, self.ACCENT_GREEN, getattr(self, "SAVE_HOVER", "#047857"))
        
        self.btn_draft = tk.Button(bot_f, text="📝 Save as Draft", font=("Segoe UI", 12, "bold"), bg="#f59e0b", fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8)
        self.btn_draft.pack(side="right", padx=(0, 10))
        self.add_hover(self.btn_draft, "#f59e0b", "#d97706") 
        
        self.btn_preview = tk.Button(bot_f, text="👁 Live Preview", font=("Segoe UI", 12, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8)
        self.btn_preview.pack(side="right", padx=(0, 10))
        self.add_hover(self.btn_preview, self.ACCENT_BLUE, getattr(self, "BLUE_HOVER", "#2563eb"))
        self.btn_preview.config(command=self.show_live_preview)
        
        self.save_engine = PurchaseSaveEngine(self)
        self.btn_post.config(command=lambda: self.save_engine.initiate_save(is_draft=False))
        self.btn_draft.config(command=lambda: self.save_engine.initiate_save(is_draft=True))

    def show_live_preview(self):
        try:
            from views.purchase_parts.print_studio.purchase_preview_window import open_purchase_preview
            
            items = []
            hsn_dict = {}
            is_interstate = False
            if self.grid_engine.vendor_state_code:
                 comp_c = database.get_company(self.comp_id)
                 c_code = ""
                 if len(comp_c) > 18 and comp_c[18]:
                     c_code = str(comp_c[18]).strip()
                 if not c_code and len(comp_c) > 9 and comp_c[9]:
                     comp_gstin = str(comp_c[9]).strip()
                     if len(comp_gstin) >= 2:
                         c_code = comp_gstin[:2]
                         
                 v_code = str(self.grid_engine.vendor_state_code).strip()
                 if c_code and c_code != "N/A" and v_code and v_code != "N/A":
                     is_interstate = (c_code != v_code)

            for r in self.grid_engine.rows_data:
                item_name = r["item"].get()
                if not item_name: continue
                qty = float(str(r["qty"].get() or 0).replace(",", ""))
                rate = float(str(r["rate"].get() or 0).replace(",", ""))
                amt = float(r.get("raw_amt", 0.0))
                gst = float(str(r["gst"].get() or 0).replace(",", ""))
                rate_inc = float(str(r["rate_inc"].get() or 0).replace(",", ""))
                
                hsn = r["hsn"].get(); unit = r["unit"].get()
                items.append({"name": item_name, "hsn": hsn, "rate": rate, "qty": qty, "amt": amt, "unit": unit, "gst": gst, "rate_inc": rate_inc})
                
                k = (hsn, gst)
                hsn_dict[k] = hsn_dict.get(k, 0.0) + amt
                
            hsn_summary = []
            for (h, g_pct), taxable in hsn_dict.items():
                t_tax = taxable * (g_pct/100)
                if is_interstate: hsn_summary.append({"hsn": h, "taxable": taxable, "igst_rate": g_pct, "igst_amt": t_tax, "total_tax": t_tax})
                else: hsn_summary.append({"hsn": h, "taxable": taxable, "cgst_rate": g_pct/2, "cgst_amt": t_tax/2, "sgst_rate": g_pct/2, "sgst_amt": t_tax/2, "total_tax": t_tax})
            
            sub = float(self.subtotal_var.get())
            cgst = float(self.cgst_var.get())
            sgst = float(self.sgst_var.get())
            igst = float(self.igst_var.get())
            tot = float(self.total_var.get())
            rnd = tot - (sub + cgst + sgst + igst)
            
            self.live_preview_data = {
                "vendor_name": self.vendor_var.get() or "DRAFT VENDOR",
                "vendor_addr": self.lbl_v_addr.cget("text"),
                "vendor_phone": self.lbl_v_phone.cget("text"),
                "vendor_gst": self.lbl_v_gst.cget("text") if self.has_gst else "N/A",
                "voucher_no": self.internal_voucher_var.get() or "DRAFT",
                "voucher_date": self.internal_date_var.get(),
                "supplier_bill": self.bill_var.get() or "DRAFT",
                "supplier_date": self.date_var.get(),
                "eway_bill": self.eway_var.get().strip(),
                "subtotal": sub, "cgst": cgst, "sgst": sgst, "igst": igst, "total": tot, "round_off": rnd,
                "is_interstate": is_interstate, "items": items, "hsn_summary": hsn_summary
            }
            
            self.live_export_payload = {
                "vendor": self.live_preview_data["vendor_name"], "gstin": self.live_preview_data["vendor_gst"],
                "bill": self.live_preview_data["supplier_bill"], "date": self.live_preview_data["supplier_date"],
                "voucher_no": self.live_preview_data["voucher_no"], "voucher_date": self.live_preview_data["voucher_date"],
                "eway_bill": self.live_preview_data["eway_bill"],
                "vendor_phone": self.live_preview_data["vendor_phone"], "vendor_address": self.live_preview_data["vendor_addr"],
                "tax_type": "Inter-State (IGST)" if is_interstate else "Local (CGST + SGST)",
                "subtotal": sub, "cgst": cgst, "sgst": sgst, "igst": igst, "total": tot,
                "hsn_summary": hsn_summary, "is_interstate": is_interstate, "items": items
            }
            open_purchase_preview(self, "LIVE")
        except Exception as e:
            messagebox.showerror("Preview Error", str(e), parent=self.pop)

    def check_internal_voucher(self, *args):
        val = self.internal_voucher_var.get().strip()
        if not val: 
            self.lbl_warn_int.config(text=""); return True
        try:
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Restricted to main posted bills only (ignoring drafts) ---
            if self.purchase_id:
                c.execute("SELECT id FROM purchases WHERE LOWER(internal_voucher)=LOWER(?) AND is_deleted=0 AND is_draft=0 AND company_id=? AND id!=?", (val, self.comp_id, self.purchase_id))
            else:
                c.execute("SELECT id FROM purchases WHERE LOWER(internal_voucher)=LOWER(?) AND is_deleted=0 AND is_draft=0 AND company_id=?", (val, self.comp_id))
            row = c.fetchone()
            conn.close()
            
            if row and val.lower() != getattr(self, "original_voucher_lower", ""):
                self.lbl_warn_int.config(text="⚠️ Voucher Number already exists!")
                return False
            self.lbl_warn_int.config(text="")
            return True
        except Exception as e: 
            self.lbl_warn_int.config(text="⚠️ Database validation error!")
            return False

    def check_supplier_bill(self, *args):
        v = self.vendor_var.get().strip()
        b = self.bill_var.get().strip()
        if not v or not b: 
            self.lbl_warn_bill.config(text=""); return True
        try:
            conn = database.get_connection()
            c = conn.cursor()
            if self.purchase_id:
                c.execute("SELECT id FROM purchases WHERE LOWER(vendor_name)=LOWER(?) AND LOWER(bill_number)=LOWER(?) AND is_deleted=0 AND company_id=? AND id!=?", (v, b, self.comp_id, self.purchase_id))
            else:
                c.execute("SELECT id FROM purchases WHERE LOWER(vendor_name)=LOWER(?) AND LOWER(bill_number)=LOWER(?) AND is_deleted=0 AND company_id=?", (v, b, self.comp_id))
            row = c.fetchone()
            conn.close()
            if row:
                self.lbl_warn_bill.config(text="⚠️ Bill already exists for this vendor!")
                return False
            self.lbl_warn_bill.config(text="")
            return True
        except Exception as e: 
            self.lbl_warn_bill.config(text="⚠️ Database validation error!")
            return False

    def on_vendor_type(self, *args):
        val = self.vendor_var.get().lower()
        self.lst_vendor.delete(0, tk.END)
        
        if not val:
            for v in self.all_vendors: self.lst_vendor.insert(tk.END, v)
        else:
            for v in self.all_vendors:
                if val in v.lower(): self.lst_vendor.insert(tk.END, v)
                
        if self.lst_vendor.size() > 0:
            x = self.ent_vendor.winfo_rootx() - self.pop.winfo_rootx()
            y = self.ent_vendor.winfo_rooty() - self.pop.winfo_rooty() + self.ent_vendor.winfo_height()
            self.lst_vendor.place(x=x, y=y, width=self.ent_vendor.winfo_width(), height=150)
            self.lst_vendor.lift()
        else:
            self.lst_vendor.place_forget()
            
        self.check_supplier_bill()
        self.on_vendor_select()

    # --- THE FIX: Build Display Map for Alias in Purchase Billing ---
    def load_vendors(self):
        try:
            conn = database.get_connection()
            c = conn.cursor()
            # Auto-heal any older purchase bills where vendor_id accidentally stored the vendor's text name
            try:
                c.execute(
                    "UPDATE purchases SET vendor_id = ("
                    "SELECT id FROM customers WHERE LOWER(customers.name) = LOWER(purchases.vendor_name) "
                    "AND customers.company_id = purchases.company_id LIMIT 1"
                    ") WHERE company_id=? AND (vendor_id IS NULL OR typeof(vendor_id) = 'text')",
                    (self.comp_id,)
                )
                conn.commit()
            except Exception:
                pass

            c.execute("SELECT id, name, alias FROM customers WHERE company_id=? ORDER BY name", (self.comp_id,))
            rows = c.fetchall()
            conn.close()
            
            self.all_vendors = []
            self.cust_display_map = {}
                
            for r in rows:
                c_id = int(r[0])
                db_name = str(r[1]).strip()
                alias = str(r[2]).strip() if len(r) > 2 and r[2] else ""
                
                if alias and f"({alias})" not in db_name:
                    disp_name = f"{db_name} ({alias})"
                else:
                    disp_name = db_name
                    
                self.all_vendors.append(disp_name)
                # --- THE FIX: Map the display name directly to its true integer Database ID! ---
                self.cust_display_map[disp_name] = {"name": db_name, "id": c_id}
                # -------------------------------------------------------------------------------
        except: pass
    # ----------------------------------------------------------------

    # --- THE FIX: Prioritize the target ID to fetch the correct data ---
    def on_vendor_select(self, *args):
        v = self.vendor_var.get().strip()
        target_id = getattr(self, "target_vend_id", None)
        
        if not v:
            self.target_vend_id = None
            self.lbl_v_addr.config(text="N/A")
            self.lbl_v_phone.config(text="N/A")
            if self.has_gst:
                self.lbl_v_gst.config(text="N/A")
                self.lbl_v_state.config(text="N/A"); self.lbl_v_scode.config(text="N/A")
            return
            
        try:
            conn = database.get_connection()
            c = conn.cursor()
            row = None
            if target_id and str(target_id).isdigit():
                c.execute("SELECT phone, gstin, state, state_code, address, name, id FROM customers WHERE id=? AND company_id=?", (int(target_id), self.comp_id))
                cand = c.fetchone()
                # Verify the user didn't manually type a different vendor name after picking from the list
                if cand and str(cand[5]).strip().lower() == v.lower():
                    row = cand
                else:
                    self.target_vend_id = None

            if not row:
                c.execute("SELECT phone, gstin, state, state_code, address, name, id FROM customers WHERE LOWER(name)=LOWER(?) AND company_id=?", (v, self.comp_id))
                row = c.fetchone()
                if row:
                    self.target_vend_id = int(row[6])
    # -------------------------------------------------------------------
            conn.close()
            
            if row:
                raw_phone = row[0] if row[0] else "N/A"
                primary_phone = raw_phone.split(',')[0].strip() if raw_phone != "N/A" else "N/A"
                if ":" in primary_phone: primary_phone = primary_phone.split(":")[-1].strip()
                self.lbl_v_phone.config(text=primary_phone)
                
                gstin = row[1] if row[1] else "N/A"
                st = row[2] if row[2] else "N/A"
                scode = row[3] if row[3] else "N/A"
                
                if (st == "N/A" or scode == "N/A") and gstin != "N/A" and len(gstin) >= 2:
                    sc = gstin[:2]
                    if sc in GST_STATES:
                        st = GST_STATES[sc]
                        scode = sc
                        
                if self.has_gst:
                    self.lbl_v_gst.config(text=gstin)
                    self.lbl_v_state.config(text=st)
                    self.lbl_v_scode.config(text=scode)

                raw_addr = row[4] if len(row) > 4 and row[4] else "N/A"
                v_addr = "N/A"
                if raw_addr and str(raw_addr).startswith("{"):
                    try:
                        j = json.loads(raw_addr)
                        v_addr = j.get("address", "N/A")
                    except: v_addr = raw_addr
                else: 
                    v_addr = raw_addr if raw_addr else "N/A"

                v_addr = str(v_addr).replace("\n", ", ").strip()
                self.lbl_v_addr.config(text=v_addr)
                
                if self.grid_engine and scode != "N/A":
                    self.grid_engine.vendor_state_code = scode
                    self.grid_engine.check_interstate()
        except: pass

def open_purchase_form(view, comp_id, curr_fmt, date_fmt_code, refresh_cb, purchase_id=None, clone_id=None):
    if purchase_id and not clone_id:
        allowed, err_msg = database.check_purchase_permission(int(purchase_id), action="edit", company_id=comp_id)
        if not allowed:
            from tkinter import messagebox
            messagebox.showerror("Access Denied", err_msg, parent=view)
            return
    PurchaseForm(view, comp_id, curr_fmt, date_fmt_code, refresh_cb, purchase_id, clone_id)