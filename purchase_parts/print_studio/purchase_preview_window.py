import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import json
import os
import sys
import urllib.parse
import webbrowser
import re

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
from views.invoice_parts.helpers import format_currency, smart_date_formatter, fetch_global_settings, grab_global_scroll
from views.purchase_parts.print_studio.purch_preview_renderer import render_purch_preview
from views.purchase_parts.print_studio.purchase_documents import preview_purchase_voucher

class MockVar:
    def __init__(self, val): self.val = val
    def get(self): return self.val

class MockSettingsView:
    def __init__(self, view, p_id, cvs):
        self.cvs = cvs
        self.view = view  
        
        # --- THE FIX: Safely read the isolated company ID directly from the View! ---
        self.comp_id = getattr(view, "comp_id", 1)
        # ----------------------------------------------------------------------------

        curr_fmt, date_fmt = fetch_global_settings(self.comp_id)
        
        self.currency_format = "Indian" if "Indian" in curr_fmt else "International"
        
        if "(" in curr_fmt:
            raw_sym = curr_fmt.split('(')[-1].replace(')','').strip()
            self.currency_sym = raw_sym.split(' ')[0] if ' ' in raw_sym else raw_sym
        else:
            self.currency_sym = "₹"
            
        self.date_format = "DD.MM.YYYY" 
        
        self.zoom_var = tk.IntVar(value=100)
        self.current_page_var = tk.StringVar(value="1")
        self.total_pages = 1
        self.page_wrappers = []

        self.name_var = MockVar("COMPANY NAME")
        self.sec_var = MockVar("")
        self.addr_var = MockVar("")
        self.p1_var = MockVar("")
        self.p2_var = MockVar("")
        self.p3_var = MockVar("")
        self.email_var = MockVar("")
        self.gst_var = MockVar("")
        self.doc_title_var = MockVar("PURCHASE VOUCHER")
        self.font_family = MockVar("Arial")
        self.swap_title_order_var = MockVar(0)
        self.logo_size_var = MockVar("120")
        self.logo_shape_var = MockVar("Original")
        self.logo_path_var = MockVar("")
        self.layout_var = MockVar("Split Header (Left-Center-Right)")
        self.header_spacing_var = MockVar("20")
        self.prev_split_var = MockVar(0)
        
        self.fonts = {}; self.colors = {}; self.bolds = {}; self.underlines = {}
        
        self.w_slno = MockVar(5); self.w_hsn = MockVar(10); self.w_qty = MockVar(8)
        self.w_gst = MockVar(6); self.w_rate_inc = MockVar(12); self.w_rate = MockVar(12)
        self.w_amt = MockVar(15)

        self.load_company_settings()
        self.load_actual_bill(p_id, date_fmt)

    def set_zoom(self, val):
        z = self.zoom_var.get() + val
        if 25 <= z <= 300:
            self.zoom_var.set(z)
            if hasattr(self, 'lbl_z'): self.lbl_z.config(text=f"{z}%")
            render_purch_preview(self)

    def change_page(self, delta):
        try: p = int(self.current_page_var.get())
        except: p = 1
        new_p = p + delta
        if 1 <= new_p <= self.total_pages:
            self.current_page_var.set(str(new_p))
            self.scroll_to_current_page()

    def scroll_to_current_page(self, *args):
        try:
            p = int(self.current_page_var.get())
            if 1 <= p <= self.total_pages and self.page_wrappers:
                y_target = self.page_wrappers[p-1] - 40 
                scrollregion = self.cvs.cget("scrollregion")
                if scrollregion:
                    scroll_h = float(scrollregion.split()[3])
                    self.cvs.yview_moveto(y_target / scroll_h)
        except: pass

    def load_company_settings(self):
        try:
            conn = database.get_connection()
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM company WHERE id=?", (self.comp_id,))
            comp = c.fetchone()
            conn.close()
            
            if comp:
                keys = comp.keys()
                
                self.name_var = MockVar(str(comp["name"]) if "name" in keys and comp["name"] else "COMPANY NAME")
                self.sec_var = MockVar(str(comp["name_secondary"]) if "name_secondary" in keys and comp["name_secondary"] else "")
                self.addr_var = MockVar(str(comp["address"]) if "address" in keys and comp["address"] else "")
                self.p1_var = MockVar(str(comp["phone"]) if "phone" in keys and comp["phone"] else "")
                self.p2_var = MockVar(str(comp["phone2"]) if "phone2" in keys and comp["phone2"] else "")
                self.p3_var = MockVar(str(comp["phone3"]) if "phone3" in keys and comp["phone3"] else "")
                self.email_var = MockVar(str(comp["email"]) if "email" in keys and comp["email"] else "")
                self.gst_var = MockVar(str(comp["gstin"]) if "gstin" in keys and comp["gstin"] else "")
                self.logo_path_var = MockVar(str(comp["logo_path"]) if "logo_path" in keys and comp["logo_path"] else "")
                
                if "template_json" in keys and comp["template_json"] and comp["template_json"].strip():
                    try: self.date_format = json.loads(comp["template_json"]).get("date_format", "DD.MM.YYYY")
                    except: pass
                    
                if "purchase_template_json" in keys and comp["purchase_template_json"] and comp["purchase_template_json"].strip():
                    try: 
                        data = json.loads(comp["purchase_template_json"])
                        self.doc_title_var = MockVar(data.get("doc_title", "PURCHASE VOUCHER"))
                        self.logo_shape_var = MockVar(data.get("logo_shape", "Original"))
                        self.logo_size_var = MockVar(data.get("logo_size", "120"))
                        self.swap_title_order_var = MockVar(data.get("swap_title_order", 0))
                        self.layout_var = MockVar(data.get("layout", "Split Header (Left-Center-Right)"))
                        self.header_spacing_var = MockVar(data.get("header_spacing", "20"))
                        
                        for k, v in data.get("fonts", {}).items(): self.fonts[k] = MockVar(str(v))
                        for k, v in data.get("colors", {}).items(): self.colors[k] = MockVar(v)
                        for k, v in data.get("bolds", {}).items(): self.bolds[k] = MockVar(v)
                        for k, v in data.get("underlines", {}).items(): self.underlines[k] = MockVar(v)
                        
                        w_db = data.get("col_widths", {})
                        self.w_slno = MockVar(w_db.get("w_slno", 5)); self.w_hsn = MockVar(w_db.get("w_hsn", 10))
                        self.w_qty = MockVar(w_db.get("w_qty", 8)); self.w_gst = MockVar(w_db.get("w_gst", 6))
                        self.w_rate_inc = MockVar(w_db.get("w_rate_inc", 12)); self.w_rate = MockVar(w_db.get("w_rate", 12))
                        self.w_amt = MockVar(w_db.get("w_amt", 15))
                    except: pass
                    
        except Exception as e: print("Mock SV Load Error:", e)

    def load_actual_bill(self, p_id, date_fmt):
        if p_id == "LIVE":
            self.actual_bill_data = getattr(self.view, "live_preview_data", None)
            self.export_payload = getattr(self.view, "live_export_payload", None)
            self.receipt_path = getattr(self.view, "receipt_var", MockVar("")).get()
            return
            
        try:
            conn = database.get_connection()
            conn.row_factory = sqlite3.Row 
            c = conn.cursor()
            
            # --- THE FIX: Added company_id lock for strict isolation ---
            c.execute("SELECT * FROM purchases WHERE id=? AND company_id=?", (p_id, self.comp_id))
            p_row = c.fetchone()
            if not p_row:
                conn.close()
                return
            
            p_keys = p_row.keys()
            v_name = (p_row["vendor_name"] if "vendor_name" in p_keys else p_row[4]) or "Unknown"
            b_num = (p_row["bill_number"] if "bill_number" in p_keys else p_row[3]) or "N/A"
            date_str = (p_row["purchase_date"] if "purchase_date" in p_keys else p_row[2]) or ""
            
            self.receipt_path = p_row["receipt_path"] if "receipt_path" in p_keys else None
            
            sub = float(p_row["subtotal"] if "subtotal" in p_keys and p_row["subtotal"] is not None else (p_row[5] or 0.0))
            cgst = float(p_row["cgst"] if "cgst" in p_keys and p_row["cgst"] is not None else (p_row[6] or 0.0))
            sgst = float(p_row["sgst"] if "sgst" in p_keys and p_row["sgst"] is not None else (p_row[7] or 0.0))
            igst = float(p_row["igst"] if "igst" in p_keys and p_row["igst"] is not None else (p_row[8] or 0.0))
            tot = float(p_row["total"] if "total" in p_keys and p_row["total"] is not None else (p_row[9] or 0.0))
            
            int_voucher = p_row["internal_voucher"] if "internal_voucher" in p_keys and p_row["internal_voucher"] else "AUTO"
            int_date_str = p_row["internal_date"] if ("internal_date" in p_keys and p_row["internal_date"]) else date_str
            eway_str = p_row["eway_bill"] if ("eway_bill" in p_keys and p_row["eway_bill"]) else ""
            
            # --- THE FIX: Use native vendor_id first, then receipt_path fallback, then name ---
            c_row = None
            raw_vid = p_row["vendor_id"] if "vendor_id" in p_keys else None
            if raw_vid is not None and str(raw_vid).isdigit():
                c.execute("SELECT address, phone, gstin FROM customers WHERE id=? AND company_id=?", (int(raw_vid), self.comp_id))
                c_row = c.fetchone()

            if not c_row and self.receipt_path:
                m = re.search(r'_ID_(\d+)', self.receipt_path)
                if m:
                    c.execute("SELECT address, phone, gstin FROM customers WHERE id=? AND company_id=?", (int(m.group(1)), self.comp_id))
                    c_row = c.fetchone()
            
            if not c_row:
                c.execute("SELECT address, phone, gstin FROM customers WHERE name=? AND company_id=?", (v_name, self.comp_id))
                c_row = c.fetchone()
                
            v_addr = "N/A"; v_phone = "N/A"; v_gst = "N/A"
            if c_row:
                c_keys = c_row.keys()
                raw_addr = c_row["address"] if "address" in c_keys else c_row[0]
                if raw_addr and str(raw_addr).startswith("{"):
                    try:
                        j = json.loads(raw_addr)
                        v_addr = j.get("address", "N/A")
                        v_gst = j.get("gstin", "N/A")
                    except: v_addr = raw_addr
                else: v_addr = raw_addr if raw_addr else "N/A"
                
                raw_phone = str(c_row["phone"] if "phone" in c_keys else c_row[1]).strip()
                if raw_phone and raw_phone.lower() not in ["none", "n/a", "", "null"]:
                    primary_phone = raw_phone.split(",")[0].strip()
                    primary_phone = re.sub(r'^(mobile|ph|phone)[\s:]*', '', primary_phone, flags=re.IGNORECASE).strip()
                    v_phone = primary_phone if primary_phone else "N/A"

                if v_gst == "N/A":
                    raw_gst = c_row["gstin"] if "gstin" in c_keys else c_row[2]
                    if raw_gst: v_gst = str(raw_gst).strip()

            c.execute("SELECT item_name, hsn, rate, quantity, amount, unit, gst_rate, rate_inc_tax FROM purchase_items WHERE purchase_id=?", (p_id,))
            items = []
            hsn_dict = {}
            for it in c.fetchall():
                i_keys = it.keys()
                i_name = (it["item_name"] if "item_name" in i_keys else it[0]) or "Item"
                i_hsn = (it["hsn"] if "hsn" in i_keys else it[1]) or ""
                i_rate = float(it["rate"] if "rate" in i_keys and it["rate"] is not None else (it[2] or 0.0))
                i_qty = float(it["quantity"] if "quantity" in i_keys and it["quantity"] is not None else (it[3] or 0.0))
                i_amt = float(it["amount"] if "amount" in i_keys and it["amount"] is not None else (it[4] or 0.0))
                i_unit = (it["unit"] if "unit" in i_keys else it[5]) or "Nos"
                i_gst = float(it["gst_rate"] if "gst_rate" in i_keys and it["gst_rate"] is not None else (it[6] or 0.0))
                i_rate_inc = float(it["rate_inc_tax"] if "rate_inc_tax" in i_keys and it["rate_inc_tax"] is not None else (it[7] or 0.0))
                
                items.append({"name": i_name, "hsn": i_hsn, "rate": i_rate, "qty": i_qty, "amt": i_amt, "unit": i_unit, "gst": i_gst, "rate_inc": i_rate_inc})
                k = (i_hsn, i_gst)
                if k not in hsn_dict: hsn_dict[k] = 0.0
                hsn_dict[k] += i_amt
                
            is_interstate = igst > 0
            hsn_summary = []
            for (h, g_pct), taxable in hsn_dict.items():
                t_tax = taxable * (g_pct/100)
                if is_interstate: hsn_summary.append({"hsn": h, "taxable": taxable, "igst_rate": g_pct, "igst_amt": t_tax, "total_tax": t_tax})
                else: hsn_summary.append({"hsn": h, "taxable": taxable, "cgst_rate": g_pct/2, "cgst_amt": t_tax/2, "sgst_rate": g_pct/2, "sgst_amt": t_tax/2, "total_tax": t_tax})
            conn.close()

            raw_tot = sub + cgst + sgst + igst
            rnd = tot - raw_tot

            self.actual_bill_data = {
                "vendor_name": v_name, "vendor_addr": v_addr, "vendor_phone": v_phone, "vendor_gst": v_gst,
                "voucher_no": int_voucher, "voucher_date": smart_date_formatter(int_date_str, date_fmt),
                "supplier_bill": b_num, "supplier_date": smart_date_formatter(date_str, date_fmt),
                "eway_bill": eway_str,
                "subtotal": sub, "cgst": cgst, "sgst": sgst, "igst": igst, "total": tot, "round_off": rnd,
                "is_interstate": is_interstate, "items": items, "hsn_summary": hsn_summary
            }
            
            self.export_payload = {
                "vendor": v_name, "gstin": v_gst, "bill": b_num, "date": self.actual_bill_data["supplier_date"],
                "voucher_no": int_voucher, "voucher_date": self.actual_bill_data["voucher_date"],
                "eway_bill": eway_str,
                "vendor_phone": v_phone, "vendor_address": v_addr, "tax_type": "Inter-State (IGST)" if is_interstate else "Local (CGST + SGST)",
                "subtotal": sub, "cgst": cgst, "sgst": sgst, "igst": igst, "total": tot,
                "hsn_summary": hsn_summary, "is_interstate": is_interstate, "items": items
            }

        except Exception as e: print("Actual Bill Load Error:", e)


def open_purchase_preview(view, p_id):
    if hasattr(view, 'pop'):
        parent_win = view.pop
    elif hasattr(view, 'winfo_toplevel'):
        parent_win = view.winfo_toplevel()
    else:
        parent_win = view

    pop = tk.Toplevel(parent_win)
    pop.title("Print Studio: Purchase Voucher")
    pop.state('zoomed')
    pop.configure(bg="#525659")
    pop.grab_set()

    def on_close():
        pop.destroy()
        if hasattr(view, 'pop') and hasattr(view, 'master_canvas'):
            grab_global_scroll(view.pop, view.master_canvas)
            
    pop.protocol("WM_DELETE_WINDOW", on_close)

    left_panel = tk.Frame(pop, bg="#323232", width=280)
    left_panel.pack(side="left", fill="y")
    left_panel.pack_propagate(False)

    btn_back = tk.Button(left_panel, text="← Back", font=("Segoe UI", 10), bg="#323232", fg="#ffffff", relief="flat", cursor="hand2", anchor="w", activebackground="#323232", activeforeground="#10b981", command=on_close)
    btn_back.pack(fill="x", padx=15, pady=(20, 10))

    tk.Label(left_panel, text="Print Studio", font=("Segoe UI", 22, "bold"), bg="#323232", fg="#ffffff", anchor="w").pack(fill="x", padx=15, pady=(0, 25))

    print_f = tk.Frame(left_panel, bg="#323232")
    print_f.pack(fill="x", padx=15, pady=5)
    
    cvs = tk.Canvas(pop) 
    sv = MockSettingsView(view, p_id, cvs)

    def trigger_print():
        if hasattr(sv, 'export_payload'):
            curr_fmt, _ = fetch_global_settings(sv.comp_id)
            preview_purchase_voucher(sv.export_payload, sv.comp_id, curr_fmt)
            
    btn_print = tk.Button(print_f, text="⎙\nPrint", font=("Segoe UI", 12, "bold"), bg="#10b981", fg="#ffffff", relief="flat", cursor="hand2", width=8, height=2, command=trigger_print)
    btn_print.pack(side="left")

    copies_f = tk.Frame(print_f, bg="#323232")
    copies_f.pack(side="left", padx=(15, 0), anchor="center")
    tk.Label(copies_f, text="Copies:", font=("Segoe UI", 9), bg="#323232", fg="#cccccc").pack(anchor="w", pady=(0, 2))
    tk.Spinbox(copies_f, from_=1, to=10, width=5, font=("Segoe UI", 11), justify="center").pack(anchor="w")

    def trigger_whatsapp():
        phone = "N/A"
        if hasattr(sv, 'actual_bill_data') and sv.actual_bill_data:
            phone = sv.actual_bill_data.get('vendor_phone', 'N/A')
        
        # --- THE FIX: Retain the '+' symbol so international country codes aren't stripped! ---
        phone_clean = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
        
        vno = "Voucher"
        amt = "0.00"
        if hasattr(sv, 'actual_bill_data') and sv.actual_bill_data:
            vno = sv.actual_bill_data.get('voucher_no', 'AUTO')
            amt = sv.actual_bill_data.get('total', 0)
            
        c_name = sv.name_var.get()
        
        msg = f"Hello!\n\nHere are the details for your recent Purchase Voucher from {c_name}:\n*Voucher No:* {vno}\n*Amount:* {amt}\n\nPlease let us know if you have any questions.\n\nThank you!"
        safe_msg = urllib.parse.quote(msg)
        
        if phone_clean and len(phone_clean) >= 10:
            webbrowser.open(f"https://web.whatsapp.com/send?phone={phone_clean}&text={safe_msg}")
        else:
            webbrowser.open(f"https://api.whatsapp.com/send?text={safe_msg}")

    btn_wa = tk.Button(left_panel, text="✆ Send to WhatsApp", font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#ffffff", relief="flat", cursor="hand2", pady=8, command=trigger_whatsapp)
    btn_wa.pack(fill="x", padx=15, pady=(20, 10))
    
    if hasattr(sv, 'receipt_path') and sv.receipt_path and os.path.exists(sv.receipt_path):
        def open_rec():
            try: os.startfile(sv.receipt_path)
            except: webbrowser.open(sv.receipt_path)
        btn_rec = tk.Button(left_panel, text="📎 Open Attachment", font=("Segoe UI", 10, "bold"), bg="#475569", fg="#ffffff", relief="flat", cursor="hand2", pady=8, command=open_rec)
        btn_rec.pack(fill="x", padx=15, pady=(0, 25))
    else:
        tk.Frame(left_panel, bg="#323232", height=15).pack()

    tk.Label(left_panel, text="Pages to Print", font=("Segoe UI", 9, "bold"), bg="#323232", fg="#cccccc", anchor="w").pack(fill="x", padx=15, pady=(5, 5))
    pg_f = tk.Frame(left_panel, bg="#323232")
    pg_f.pack(fill="x", padx=15, pady=(0, 20))
    
    sv.page_from_var = tk.StringVar(value="1")
    sv.page_to_var = tk.StringVar(value="1")
    
    tk.Entry(pg_f, textvariable=sv.page_from_var, width=4, font=("Segoe UI", 11), justify="center", bg="#444444", fg="white", relief="solid", bd=1).pack(side="left")
    tk.Label(pg_f, text="to", bg="#323232", fg="#cccccc", font=("Segoe UI", 9)).pack(side="left", padx=10)
    tk.Entry(pg_f, textvariable=sv.page_to_var, width=4, font=("Segoe UI", 11), justify="center", bg="#444444", fg="white", relief="solid", bd=1).pack(side="left")

    tk.Label(left_panel, text="Print Destination", font=("Segoe UI", 9, "bold"), bg="#323232", fg="#cccccc", anchor="w").pack(fill="x", padx=15, pady=(5, 5))
    cb_dest = ttk.Combobox(left_panel, values=["Web Browser (HTML Auto-Print)"], state="readonly", font=("Segoe UI", 10))
    cb_dest.set("Web Browser (HTML Auto-Print)")
    cb_dest.pack(fill="x", padx=15, pady=(0, 20), ipady=3)

    tk.Label(left_panel, text="Paper Configuration", font=("Segoe UI", 9, "bold"), bg="#323232", fg="#cccccc", anchor="w").pack(fill="x", padx=15, pady=(5, 5))
    cb_paper = ttk.Combobox(left_panel, values=["A4 (210*297mm)"], state="readonly", font=("Segoe UI", 10))
    cb_paper.set("A4 (210*297mm)")
    cb_paper.pack(fill="x", padx=15, pady=(0, 20), ipady=3)

    right_panel = tk.Frame(pop, bg="#525659")
    right_panel.pack(side="right", fill="both", expand=True)

    zoom_bar = tk.Frame(right_panel, bg="#333333", height=40)
    zoom_bar.pack(side="bottom", fill="x")

    cvs_frame = tk.Frame(right_panel, bg="#525659")
    cvs_frame.pack(fill="both", expand=True, padx=40, pady=(40, 10))

    cvs = tk.Canvas(cvs_frame, bg="#525659", highlightthickness=0)
    sv.cvs = cvs  
    
    scroll_y = ttk.Scrollbar(cvs_frame, orient="vertical", command=cvs.yview)
    scroll_x = ttk.Scrollbar(right_panel, orient="horizontal", command=cvs.xview)
    
    cvs.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    
    scroll_y.pack(side="right", fill="y")
    cvs.pack(side="left", fill="both", expand=True)
    scroll_x.pack(side="bottom", fill="x", padx=(40, 55))

    page_ctrl = tk.Frame(zoom_bar, bg="#333333")
    page_ctrl.pack(side="left", padx=20, pady=5)
    
    tk.Button(page_ctrl, text=" ◀ ", font=("Segoe UI", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: sv.change_page(-1)).pack(side="left", padx=5)
    sv.ent_page = tk.Entry(page_ctrl, textvariable=sv.current_page_var, font=("Segoe UI", 10, "bold"), width=4, justify="center", bg="#4a4a4a", fg="white", relief="flat", bd=0, insertbackground="white")
    sv.ent_page.pack(side="left", ipady=3)
    sv.ent_page.bind("<Return>", sv.scroll_to_current_page)
    
    sv.lbl_total = tk.Label(page_ctrl, text="of 1", font=("Segoe UI", 10, "bold"), bg="#333333", fg="#aaaaaa")
    sv.lbl_total.pack(side="left", padx=8)
    tk.Button(page_ctrl, text=" ▶ ", font=("Segoe UI", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: sv.change_page(1)).pack(side="left", padx=5)
    
    z_ctrl = tk.Frame(zoom_bar, bg="#333333")
    z_ctrl.pack(side="right", padx=20, pady=5)
    
    tk.Button(z_ctrl, text="  -  ", font=("Segoe UI", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: sv.set_zoom(-25)).pack(side="left", padx=5)
    sv.lbl_z = tk.Label(z_ctrl, text="100%", font=("Segoe UI", 10, "bold"), bg="#333333", fg="white", width=6)
    sv.lbl_z.pack(side="left")
    tk.Button(z_ctrl, text="  +  ", font=("Segoe UI", 10, "bold"), bg="#4a4a4a", fg="white", relief="flat", cursor="hand2", bd=0, activebackground="#5a5a5a", command=lambda: sv.set_zoom(25)).pack(side="left", padx=5)
    
    def on_resize(e):
        def _delayed():
            render_purch_preview(sv)
            if hasattr(sv, 'total_pages'):
                sv.page_to_var.set(str(sv.total_pages))
        pop.after(100, _delayed)
        
    cvs.bind("<Configure>", on_resize)
    
    def safe_scroll(e):
        if cvs.winfo_exists():
            cvs.yview_scroll(int(-1*(e.delta/120)), "units")
            
    cvs.bind_all("<MouseWheel>", safe_scroll)