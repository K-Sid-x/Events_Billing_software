import tkinter as tk
from tkinter import ttk, messagebox
import json
import re
import os
import sys
from datetime import date, datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    views_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import get_date_format_str, unpack_place_data
from views.invoice_parts.new_inv_components.part1_billing import build_part_1
from views.invoice_parts.new_inv_components.part2_items import build_part_2
from views.invoice_parts.new_inv_components.part3_totals import build_part_3

def get_theme_colors():
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    if is_dark:
        return {
            "bg": "#0f172a", "card": "#1e293b", "border": "#334155", 
            "text": "#f8fafc", "sec": "#94a3b8", "accent_green": "#10b981", 
            "error": "#ef4444", "accent_blue": "#3b82f6"
        }
    else:
        return {
            "bg": "#f0f9ff", "card": "#ffffff", "border": "#bae6fd", 
            "text": "#0f172a", "sec": "#0284c7", "accent_green": "#10b981", 
            "error": "#ef4444", "accent_blue": "#0ea5e9"
        }

class InvoiceState:
    def __init__(self, view, popup):
        self.view = view
        self.popup = popup
        self.theme = get_theme_colors()
        self.is_edit_mode = False
        self.edit_inv_id = None
        
        self.inv_num_var = tk.StringVar()
        self.cust_var = tk.StringVar()
        self.cust_phone_var = tk.StringVar()
        self.cust_gst_var = tk.StringVar()
        self.inv_date_var = tk.StringVar()
        self.subj_var = tk.StringVar()
        self.serv_name_var = tk.StringVar() 
        self.serv_addr_var = tk.StringVar()
        self.serv_del_var = tk.StringVar()
        self.serv_bill_from_var = tk.StringVar()
        self.serv_bill_to_var = tk.StringVar()
        self.inc_eway_var = tk.IntVar(value=0)
        self.eway_var = tk.StringVar(value="")
        self.inc_subj_var = tk.IntVar(value=1) 
        self.subj_align_var = tk.StringVar(value="center")
        
        self.item_rows = []
        self.subtotal_var = tk.StringVar(value="0.00")
        
        self.inc_discount_var = tk.IntVar(value=0)
        self.discount_val_var = tk.StringVar(value="")
        self.discount_type_var = tk.StringVar(value="Flat (₹)")
        self.discount_amt_var = tk.StringVar(value="0.00")
        
        self.inc_adv_var = tk.IntVar(value=0)
        self.adv_val_var = tk.StringVar(value="")
        self.is_saved = False
        self.is_swapping = False
        
        self.cgst_var = tk.StringVar(value="0.00")
        self.sgst_var = tk.StringVar(value="0.00")
        self.igst_var = tk.StringVar(value="0.00")
        self.roundoff_var = tk.StringVar(value="0.00")
        self.grand_total_var = tk.StringVar(value="0.00")
        
        # --- THE FIX: Load GST rates from Memory and Sync CGST/SGST ---
        comp_id_mem = getattr(view.winfo_toplevel(), "active_company_id", 1)
        last_cgst = database.get_ui_setting(f"last_cgst_{comp_id_mem}", "9")
        last_igst = database.get_ui_setting(f"last_igst_{comp_id_mem}", "18")
        
        self.cgst_rate_var = tk.StringVar(value=last_cgst)
        self.sgst_rate_var = tk.StringVar(value=last_cgst)
        self.igst_rate_var = tk.StringVar(value=last_igst)
        
        self._syncing_gst = False
        def sync_cgst(*args):
            if getattr(self, '_syncing_gst', False): return
            self._syncing_gst = True
            self.sgst_rate_var.set(self.cgst_rate_var.get())
            self._syncing_gst = False

        def sync_sgst(*args):
            if getattr(self, '_syncing_gst', False): return
            self._syncing_gst = True
            self.cgst_rate_var.set(self.sgst_rate_var.get())
            self._syncing_gst = False
            
        self.cgst_rate_var.trace_add("write", sync_cgst)
        self.sgst_rate_var.trace_add("write", sync_sgst)
        # --------------------------------------------------------------
        
        self.gst_type = tk.StringVar(value="GST")
        self.has_gst = True 
        
        self.inc_bank_var = tk.IntVar(value=0)
        self.selected_bank_var = tk.StringVar()
        
        self.comp = None
        self.company_banks = []
        
        comp_id = getattr(view.winfo_toplevel(), "active_company_id", 1)
        
        # --- THE FIX: Explicit columns & Build Display Map for Alias ---
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE company_id=?", (comp_id,))
            self.full_customers = c.fetchall()
            
            self.customers = []
            self.cust_display_map = {}
            for row in self.full_customers:
                if len(row) > 1 and row[1]:
                    db_name = str(row[1]).strip()
                    alias = str(row[8]).strip() if len(row) > 8 and row[8] else ""
                    
                    if alias and f"({alias})" not in db_name:
                        disp_name = f"{db_name} ({alias})"
                    else:
                        disp_name = db_name
                        
                    self.customers.append(disp_name)
                    self.cust_display_map[disp_name] = db_name
            conn.close()
        except:
            self.full_customers = []
            self.customers = []
            self.cust_display_map = {}
        # ---------------------------------------------------------------

        self.inventory_data = {}
        
        self.inv_format = "INV-000"
        self.saved_custom_format = "MSE/<FY>/000"
        
        self.all_historical_inv_nums = []
        try:
            conn = database.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT invoice_number FROM invoices WHERE is_deleted=0 AND status != 'Draft' AND company_id=?", (comp_id,))
            self.all_historical_inv_nums = [str(r[0]).strip().lower() for r in cur.fetchall() if r[0]]
            conn.close()
        except: pass
        
        self.current_inv_count = 1
        self.inv_number = ""
        self.current_inv_val = ""
        self.curr_fmt = "Indian Rupees (₹)"
        
        self.date_fmt_code = "%d/%m/%Y" 
        self.update_totals_display_callback = None
        self.add_row_func = None

    def focus_next(self, event):
        event.widget.tk_focusNext().focus()
        return "break"

    def get_format_count(self, fmt):
        # 1. Resolve <FY> BEFORE splitting, so we search the exact current year!
        if "<FY>" in fmt:
            now = datetime.now()
            fy_start_month = 4 
            if self.comp and len(self.comp) > 14 and self.comp[14]:
                try:
                    c_data = json.loads(self.comp[14])
                    fy_val = c_data.get("fy_start", "April")
                    if fy_val == "January": fy_start_month = 1
                    elif fy_val == "July": fy_start_month = 7
                except: pass
            
            if now.month >= fy_start_month:
                fy_str = f"{str(now.year)[-2:]}-{str(now.year + 1)[-2:]}"
            else:
                fy_str = f"{str(now.year - 1)[-2:]}-{str(now.year)[-2:]}"
            
            fmt = fmt.replace("<FY>", fy_str)

        # 2. Extract the actual prefix before the zeros
        zeros = re.findall(r'0+', fmt)
        if zeros:
            target_zeros = zeros[-1]
            parts = fmt.rsplit(target_zeros, 1)
            resolved_prefix = parts[0].lower()
        else:
            resolved_prefix = fmt.lower()
            
        max_num = 0
        
        # --- THE FIX: Let the counter understand <B50> wildcards! ---
        
        if "<b50>" in resolved_prefix:
            pat_str = "^" + re.escape(resolved_prefix).replace(r"\<b50\>", r"\d+")
            search_pattern = re.compile(pat_str)
        else:
            search_pattern = None
        # ------------------------------------------------------------
            
        for num in self.all_historical_inv_nums:
            if resolved_prefix:
                # --- THE FIX: Smart Pattern Matching ---
                is_match = False
                if search_pattern:
                    if search_pattern.match(num): is_match = True
                else:
                    if num.startswith(resolved_prefix): is_match = True
                    
                if is_match:
                    digits = re.findall(r'\d+', num)
                    if digits:
                        val = int(digits[-1])
                        if val > max_num:
                            max_num = val
                # ---------------------------------------
            else:
                if num.isdigit():
                    val = int(num)
                    if val > max_num:
                        max_num = val
                        
        return max_num + 1

    def get_formatted_inv_num(self, fmt, count):
        if "<FY>" in fmt:
            now = datetime.now()
            fy_start_month = 4 
            if self.comp and len(self.comp) > 14 and self.comp[14]:
                try:
                    c_data = json.loads(self.comp[14])
                    fy_val = c_data.get("fy_start", "April")
                    if fy_val == "January": fy_start_month = 1
                    elif fy_val == "July": fy_start_month = 7
                except: pass
            
            if now.month >= fy_start_month:
                fy_str = f"{str(now.year)[-2:]}-{str(now.year + 1)[-2:]}"
            else:
                fy_str = f"{str(now.year - 1)[-2:]}-{str(now.year)[-2:]}"
            
            fmt = fmt.replace("<FY>", fy_str)

        if "<B50>" in fmt:
            batch_num = ((count - 1) // 50) + 1
            fmt = fmt.replace("<B50>", str(batch_num))

        zeros = re.findall(r'0+', fmt)
        if zeros:
            target_zeros = zeros[-1]
            padded_num = str(count).zfill(len(target_zeros))
            parts = fmt.rsplit(target_zeros, 1)
            return padded_num.join(parts)
        return fmt + str(count)

    def calculate_totals(self, *args):
        sub = 0.0
        for r in self.item_rows:
            if "widgets" in r and len(r["widgets"]) > 1:
                item_text = r["widgets"][1].get("1.0", "end-1c").strip()
                if item_text:
                    try: sub += float(r["amt"].get())
                    except ValueError: pass
                    
        disc_amt = 0.0
        if self.inc_discount_var.get() == 1:
            try: d_val = float(self.discount_val_var.get() or 0)
            except: d_val = 0.0
            
            if self.discount_type_var.get() == "%": disc_amt = sub * (d_val / 100.0)
            else: disc_amt = d_val
                
        self.discount_amt_var.set(f"{disc_amt:.2f}")
        taxable_sub = sub - disc_amt
        self.subtotal_var.set(f"{sub:.2f}")
        
        c, s, i = 0.0, 0.0, 0.0
        
        if getattr(self, 'has_gst', True):
            try: c_rate = float(self.cgst_rate_var.get()) / 100.0
            except: c_rate = 0.09
            try: s_rate = float(self.sgst_rate_var.get()) / 100.0
            except: s_rate = 0.09
            try: i_rate = float(self.igst_rate_var.get()) / 100.0
            except: i_rate = 0.18
            
            if self.gst_type.get() == "GST": 
                c = taxable_sub * c_rate
                s = taxable_sub * s_rate
            elif self.gst_type.get() == "IGST": 
                i = taxable_sub * i_rate
        
        self.cgst_var.set(f"{c:.2f}"); self.sgst_var.set(f"{s:.2f}"); self.igst_var.set(f"{i:.2f}")
        raw_total = taxable_sub + c + s + i
        rounded = round(raw_total)
        self.roundoff_var.set(f"{rounded - raw_total:+.2f}")
        self.grand_total_var.set(f"{rounded:.2f}")
        
        if self.update_totals_display_callback:
            self.update_totals_display_callback()

def extract_address_safe(addr_str):
    if not addr_str: return ""
    s_val = str(addr_str).strip()
    if s_val.startswith("{"):
        try:
            import ast
            d = ast.literal_eval(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
        try:
            d = json.loads(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
    return s_val


def open_new_invoice(view, edit_inv_id=None, clone_id=None):
    if edit_inv_id:
        comp_id_chk = getattr(view.winfo_toplevel(), "active_company_id", 1)
        allowed, reason = database.check_invoice_permission(edit_inv_id, action="edit", company_id=comp_id_chk)
        if not allowed:
            messagebox.showwarning("Access Restricted", reason, parent=view)
            return

    popup = tk.Toplevel(view)
    title_str = "Create Tax Invoice" if not edit_inv_id else f"Edit Invoice"
    if clone_id: title_str = "Clone Invoice"
    popup.title(title_str)
    
    state = InvoiceState(view, popup)
    theme = state.theme
    
    popup.configure(bg=theme["bg"])
    popup.minsize(900, 600)

    # --- THE FIX: Bulletproof Unsaved Changes Tracker ---
    state.is_dirty = False
    def mark_dirty(e=None, *args):
        if e and getattr(e, 'keysym', '') in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Tab', 'Return', 'Escape', 'Up', 'Down', 'Left', 'Right', 'MouseWheel'):
            return
        state.is_dirty = True

    popup.bind("<Key>", mark_dirty, add="+")
    popup.bind("<<ComboboxSelected>>", mark_dirty, add="+")
    
    # Force tracker to watch the core math variables, dates, and checkboxes
    state.subtotal_var.trace_add("write", mark_dirty)
    state.cust_var.trace_add("write", mark_dirty)
    state.inv_date_var.trace_add("write", mark_dirty)
    state.inv_num_var.trace_add("write", mark_dirty)
    state.inc_eway_var.trace_add("write", mark_dirty)
    state.inc_subj_var.trace_add("write", mark_dirty)
    state.inc_discount_var.trace_add("write", mark_dirty)
    state.inc_adv_var.trace_add("write", mark_dirty)

    def on_closing():
        if getattr(state, 'is_dirty', False) and not getattr(state, 'is_saved', False):
            if messagebox.askyesno("Unsaved Changes", "You have unsaved changes.\n\nAre you sure you want to close without saving?", parent=popup):
                popup.destroy()
        else:
            popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_closing)
    # ----------------------------------------------------
    
    try: popup.state('zoomed')
    except: popup.attributes('-zoomed', True)
    popup.grab_set()

    style = ttk.Style(popup)
    style.theme_use("default")
    
    # --- THE FIX: Thick Solid Scrollbar Style for the Main Invoice Canvas ---
    style.configure("NewInv.Vertical.TScrollbar", background=theme.get("sec", "#94a3b8"), troughcolor=theme["bg"], bordercolor=theme["bg"], arrowcolor=theme["text"], relief="flat")
    style.map("NewInv.Vertical.TScrollbar", background=[("active", theme.get("accent_blue", "#3b82f6"))])
    # ------------------------------------------------------------------------

    popup.option_add("*TCombobox*Listbox.background", theme["card"])
    popup.option_add("*TCombobox*Listbox.foreground", theme["text"])
    popup.option_add("*TCombobox*Listbox.selectBackground", theme["accent_blue"])
    popup.option_add("*TCombobox*Listbox.selectForeground", theme["text"])
    style.configure("Dark.TCombobox", fieldbackground=theme["bg"], background=theme["card"], foreground=theme["text"], arrowcolor=theme["text"], bordercolor=theme["border"], lightcolor=theme["border"], darkcolor=theme["border"], insertcolor=theme["text"])
    style.map("Dark.TCombobox", fieldbackground=[("readonly", theme["bg"])], selectbackground=[("readonly", theme["bg"])], selectforeground=[("readonly", theme["text"])])

    if edit_inv_id:
        state.is_edit_mode = True
        state.edit_inv_id = edit_inv_id
    if clone_id:
        state.clone_id = clone_id
        
    comp_id = getattr(view.winfo_toplevel(), "active_company_id", 1)
    state.comp = database.get_company(comp_id)
    
    if state.comp and len(state.comp) > 8:
        state.has_gst = (state.comp[8] == 1)
        
    date_fmt = "DD.MM.YYYY"
    
    if state.comp and len(state.comp) > 14 and state.comp[14]:
        try: 
            comp_data = json.loads(state.comp[14])
            state.company_banks = comp_data.get("banks", [])
            state.inv_format = comp_data.get("invoice_format", "INV-000")
            state.saved_custom_format = comp_data.get("custom_inv_format", "MSE/<FY>/000")
            date_fmt = comp_data.get("date_format", "DD.MM.YYYY")
            state.curr_fmt = comp_data.get("currency_format", "Indian Rupees (₹)")
        except: pass

    dt_str_code = get_date_format_str(date_fmt)
    state.date_fmt_code = dt_str_code 
    today_str = date.today().strftime(dt_str_code)
    state.inv_date_var.set(today_str)       

    # --- THE FIX: Direct SQL to grab strictly active company's inventory ---
    try:
        conn = database.get_connection()
        c = conn.cursor()
        
        # --- THE FIX: Explicitly request columns so the .exe doesn't shift them! ---
        c.execute("SELECT id, item_name, unit, rate, description, company_id FROM inventory WHERE company_id=?", (comp_id,))
        # ----------------------------------------------------------------------------
        
        for i in c.fetchall():
            name = i[1] if len(i) > 1 else ""
            
            # --- THE FIX: Extract short unit format and completely vaporize '--Select--' ---
            raw_unit_val = str(i[2]) if len(i) > 2 and i[2] else ""
            unit_val = raw_unit_val.split("(")[-1].replace(")", "").strip() if "(" in raw_unit_val else raw_unit_val
            if unit_val.lower() in ["--select--", "none", "null"]:
                unit_val = ""
            # -------------------------------------------------------------------------------
            
            try: rate_val = float(i[3]) if len(i) > 3 else 0.0
            except: rate_val = 0.0
            
            raw_desc = str(i[4]) if len(i) > 4 else ""
            if len(i) == 4: 
                unit_val = ""
                try: rate_val = float(i[2]); raw_desc = str(i[3])
                except: pass

            hsn_val = ""
            if raw_desc and raw_desc.strip().startswith("{") and '"desc"' in raw_desc:
                try: hsn_val = json.loads(raw_desc).get("hsn", "")
                except: pass
                
            state.inventory_data[name] = {"rate": rate_val, "hsn": hsn_val, "unit": unit_val}
        conn.close()
    except: pass
    # -----------------------------------------------------------------------

    state.current_inv_count = state.get_format_count(state.inv_format)
    state.inv_number = state.get_formatted_inv_num(state.inv_format, state.current_inv_count)
    state.inv_num_var.set(state.inv_number)

    bottom_fixed_frame = tk.Frame(popup, bg=theme["bg"])
    bottom_fixed_frame.pack(side="bottom", fill="x")
    
    canvas_container = tk.Frame(popup, bg=theme["bg"])
    canvas_container.pack(side="top", fill="both", expand=True)

    form_canvas = tk.Canvas(canvas_container, bg=theme["bg"], highlightthickness=0)
    
    # --- THE FIX: Apply the custom thick scrollbar style ---
    scrollbar_y = ttk.Scrollbar(canvas_container, orient="vertical", command=form_canvas.yview, style="NewInv.Vertical.TScrollbar")
    # -------------------------------------------------------
    scrollable_frame = tk.Frame(form_canvas, bg=theme["bg"])

    frame_window_id = form_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    def on_canvas_configure(event):
        form_canvas.itemconfig(frame_window_id, width=event.width)
    form_canvas.bind("<Configure>", on_canvas_configure)
    form_canvas.configure(yscrollcommand=scrollbar_y.set)
    
    def _on_mousewheel(event):
        try:
            widget = popup.winfo_containing(event.x_root, event.y_root)
            if not widget or not str(widget).startswith(str(popup)): return
            if isinstance(widget, (tk.Listbox, ttk.Combobox)): return
            if event.delta: form_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except: pass
        
    def _restore_scroll(e=None): popup.bind_all("<MouseWheel>", _on_mousewheel)
    popup.bind("<Enter>", _restore_scroll)
    popup.bind("<FocusIn>", _restore_scroll)
    popup.bind("<Destroy>", lambda e: popup.unbind_all("<MouseWheel>") if e.widget == popup else None)

    scrollbar_y.pack(side="right", fill="y")
    form_canvas.pack(side="left", fill="both", expand=True)

    build_part_1(scrollable_frame, state)
    build_part_2(scrollable_frame, state)
    
    if state.is_edit_mode or hasattr(state, "clone_id"):
        source_id = state.edit_inv_id if state.is_edit_mode else state.clone_id
        inv, items = database.get_invoice_by_id(source_id)
        if inv:
            # --- THE FIX: Capture the old customer_id during edits and clones! ---
            if len(inv) > 17:
                state.cust_id = inv[17]
            # ---------------------------------------------------------------------
            # --- THE FIX: Only set old dates and old invoice numbers if we are EDITING. Clones get fresh ones! ---
            if state.is_edit_mode:
                state.inv_date_var.set(inv[1])
                
                inv_status = ""
                try:
                    conn = database.get_connection()
                    cur = conn.cursor()
                    # --- THE FIX: Added company_id lock ---
                    cur.execute("SELECT status FROM invoices WHERE id=? AND company_id=?", (state.edit_inv_id, comp_id))
                    status_row = cur.fetchone()
                    conn.close()
                    if status_row: inv_status = status_row[0]
                except: pass
                
                if inv_status == 'Draft':
                    draft_num = str(inv[3]).strip()
                    if draft_num.lower() in getattr(state, "existing_inv_nums", []):
                        state.inv_num_var.set(state.inv_number)
                    else:
                        state.inv_num_var.set(draft_num)
                else:
                    state.inv_num_var.set(inv[3])
            else:
                # --- THE BUG FIX: Force Clones to grab the properly calculated Custom Sequence! ---
                state.inv_num_var.set(state.inv_number)
            # ---------------------------------------------------------------------------------------------------
                
            state.cust_var.set(inv[4])
            
            if hasattr(state, 'lookup_customer_cb'):
                state.lookup_customer_cb(inv[4])
            
            unpack_place_data(inv[5], state)
            
            disc_amt = 0.0
            if state.inc_discount_var.get() == 1:
                try: d_val = float(state.discount_val_var.get() or 0)
                except: d_val = 0.0
                if state.discount_type_var.get() == "%":
                    disc_amt = float(inv[6]) * (d_val / 100.0)
                else:
                    disc_amt = d_val
            
            taxable_sub = float(inv[6]) - disc_amt
            
            if float(inv[9]) > 0: 
                state.gst_type.set("IGST")
                try:
                    inv_igst = float(inv[9])
                    if taxable_sub > 0:
                        r = round((inv_igst / taxable_sub) * 100, 2)
                        state.igst_rate_var.set(str(int(r) if r.is_integer() else r))
                except: pass
            else: 
                state.gst_type.set("GST")
                try:
                    inv_cgst = float(inv[7])
                    if taxable_sub > 0:
                        r = round((inv_cgst / taxable_sub) * 100, 2)
                        state.cgst_rate_var.set(str(int(r) if r.is_integer() else r))
                        state.sgst_rate_var.set(str(int(r) if r.is_integer() else r))
                except: pass
            
            for r in state.item_rows:
                r["item"].set("")
                if "widgets" in r and len(r["widgets"])>1: r["widgets"][1].set_text("")
                r["sac"].set(""); r["rate"].set(""); r["qty"].set(""); r["days"].set("1"); r["amt"].set("0.00")
            
            while len(state.item_rows) < len(items):
                state.add_row_func()
                
            def _clean_num(val):
                try:
                    v = float(val)
                    return str(int(v)) if v.is_integer() else str(v)
                except: return str(val)

            state.is_swapping = True
            for idx, it in enumerate(items):
                r = state.item_rows[idx]
                item_name = str(it[0])
                
                # --- THE TRICK: Detect the invisible marker and strip it ---
                is_voided = False
                if item_name.startswith("\u200b"):
                    is_voided = True
                    item_name = item_name.replace("\u200b", "")
                # -----------------------------------------------------------
                
                r["item"].set(item_name)
                if "widgets" in r and len(r["widgets"])>1: r["widgets"][1].set_text(item_name)
                
                # --- THE FIX: Strictly trust the Database HSN and Unit (even if user left them blank) ---
                hsn_val = str(it[1]).strip() if it[1] is not None and str(it[1]) != "None" else ""
                
                if len(it) > 6:
                    unit_val = str(it[6]).strip() if it[6] is not None else ""
                else:
                    unit_val = state.inventory_data.get(item_name, {}).get("unit", "") if item_name in state.inventory_data else ""
                
                if unit_val.strip().lower() in ["none", "--select--", "null"]:
                    unit_val = ""
                # -----------------------------------------------------------------------------------------
                
                r["sac"].set(hsn_val)
                if "unit" in r: r["unit"].set(unit_val)
                
                # --- THE FIX: Leave Rate blank if it was saved as 0 ---
                saved_rate = str(it[2]).strip()
                if not saved_rate or saved_rate in ["0.0", "0", "None"]:
                    saved_rate = ""
                r["rate"].set(_clean_num(saved_rate) if saved_rate else "")
                # ------------------------------------------------------
                
                # --- THE FIX: Leave boxes blank when editing an existing invoice ---
                saved_qty = str(it[3]).strip()
                if not saved_qty or saved_qty in ["0.0", "0", "None"]:
                    saved_qty = ""
                r["qty"].set(_clean_num(saved_qty) if saved_qty else "")
                
                saved_days = str(it[4]).strip()
                if not saved_days or saved_days == "0.0" or saved_days == "0" or saved_days == "None": 
                    saved_days = ""
                r["days"].set(_clean_num(saved_days) if saved_days else "")
                
                # --- THE FIX: Upgraded Regex to flawlessly capture negative rates when editing bills ---
                try: r_val = float(re.search(r'[-+]?\d*\.?\d+', str(it[2])).group())
                except: r_val = 0.0
                try: q_val = float(re.search(r'[-+]?\d*\.?\d+', str(it[3])).group())
                except: q_val = 1.0
                try: d_val = float(re.search(r'[-+]?\d*\.?\d+', saved_days).group())
                except: d_val = 1.0
                
                r["amt"].set(f"{r_val * q_val * d_val:.2f}")
                
                # --- THE TRICK: Apply voided Sl No based on our invisible marker ---
                if is_voided:
                    if "sl_var" in r: r["sl_var"].set("")
                # -------------------------------------------------------------------

            # --- THE FIX: Re-index the remaining valid Sl Nos. automatically ---
            current_num = 1
            for r in state.item_rows:
                if "sl_var" in r and r["sl_var"].get().strip() != "":
                    r["sl_var"].set(str(current_num))
                    current_num += 1
            # -------------------------------------------------------------------
            
            state.is_swapping = False
            state.calculate_totals()
            
            if hasattr(state, 'subj_text_widget'):
                state.subj_text_widget.set_text(state.subj_var.get())

    build_part_3(bottom_fixed_frame, state)

    form_canvas.update_idletasks()
    bbox = form_canvas.bbox("all")
    if bbox: form_canvas.configure(scrollregion=(0, 0, bbox[2] + 40, bbox[3] + 40))
    state.view.popup = popup

    # --- THE FIX: Wipe the dirty flag clean AFTER the invoice finishes loading! ---
    popup.after(500, lambda: setattr(state, "is_dirty", False))
    # ------------------------------------------------------------------------------