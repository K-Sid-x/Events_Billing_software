import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import csv
import tempfile
import webbrowser
import re
from datetime import date, datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    main_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    views_dir = os.path.dirname(current_dir)
    main_dir = os.path.dirname(views_dir)

if main_dir not in sys.path:
    sys.path.append(main_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar
from views.home_parts.ui_components import get_theme

def safe_float(val):
    if val is None or str(val).strip() == "": return 0.0
    try: return float(str(val).replace(',', '').replace(' ', '').replace('₹', '').replace('$', '').replace('€', '').replace('£', '').strip())
    except: return 0.0

def parse_date(date_str):
    if not date_str: return None
    date_str = str(date_str).strip()
    formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d"]
    for fmt in formats:
        try: return datetime.strptime(date_str, fmt).date()
        except: pass
    return None

def get_period_key(dt_obj, period_mode_val):
    if dt_obj.month >= 4: fy = dt_obj.year
    else: fy = dt_obj.year - 1
    fy_str = f"{fy}-{fy+1}"
    
    if period_mode_val == "Monthly": 
        return dt_obj.strftime("%Y-%m")
    elif period_mode_val == "Quarterly":
        if dt_obj.month in [4, 5, 6]: q = 1
        elif dt_obj.month in [7, 8, 9]: q = 2
        elif dt_obj.month in [10, 11, 12]: q = 3
        else: q = 4
        return f"Q{q}"
    else: 
        return fy_str

def show_drilldown_window(parent, period_key, comp_id, curr_fmt, date_fmt_code, period_mode_val, on_close_callback):
    t = get_theme() # --- THE FIX: Dynamic UI Theme integration ---
    
    pop = tk.Toplevel(parent)
    pop.title(f"GST Details - {period_key}")
    pop.single_export_iid = None 
    
    saved_geom = "1300x650"
    try:
        val = database.get_ui_setting(f'gst_drilldown_geometry_{comp_id}')
        if val and val != "{}": saved_geom = val
    except: pass
    
    pop.geometry(saved_geom)
    
    # --- THE FIX: Robust Cross-Platform Window Maximize ---
    if os.name == 'nt':
        pop.state('zoomed')
    else:
        try: pop.attributes('-zoomed', True)
        except: pop.attributes('-fullscreen', True)
    # ------------------------------------------------------
        
    pop.configure(bg=t["bg"])
    pop.grab_set()

    style = ttk.Style(pop)
    style.theme_use("default")
    
    pop.option_add('*TCombobox*Listbox.background', t["card"])
    pop.option_add('*TCombobox*Listbox.foreground', t["text"])
    pop.option_add('*TCombobox*Listbox.selectBackground', t["accent_blue"])
    pop.option_add('*TCombobox*Listbox.selectForeground', '#ffffff')
    
    style.configure("GST.TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["text"], arrowcolor=t["text"], bordercolor=t["border"])
    style.map("GST.TCombobox", fieldbackground=[("readonly", t["card"])], selectbackground=[("readonly", t["accent_blue"])], selectforeground=[("readonly", "#ffffff")])

    style.configure("GST.Treeview.Heading", font=("Arial", 10, "bold"), background=t["header"], foreground=t["text"], borderwidth=1, relief="raised")
    style.map("GST.Treeview.Heading", background=[('active', t["border"])])
    style.configure("GST.Treeview", font=("Arial", 11), rowheight=45, background=t["card"], fieldbackground=t["card"], foreground=t["text"], borderwidth=0)
    style.map("GST.Treeview", background=[("selected", t["border"])], foreground=[("selected", "#ffffff")])

    # --- THE FIX: Custom thick, flat scrollbars for GST Drilldown ---
    style.configure("GST.Vertical.TScrollbar", background=t["sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.configure("GST.Horizontal.TScrollbar", background=t["sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("GST.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    style.map("GST.Horizontal.TScrollbar", background=[("active", t["accent_blue"])])
    # ----------------------------------------------------------------

    def on_close():
        try: database.save_ui_setting(f'gst_drilldown_geometry_{comp_id}', pop.geometry())
        except: pass
        pop.destroy()
        if on_close_callback:
            on_close_callback()
            
    pop.protocol("WM_DELETE_WINDOW", on_close)

    is_bulk_mode = tk.BooleanVar(value=False)
    selected_iids = set()
    row_map = {} 

    header_f = tk.Frame(pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1, pady=15, padx=20)
    header_f.pack(fill="x")
    tk.Label(header_f, text=f"Bill-Wise Details: {period_key}", font=("Arial", 16, "bold"), bg=t["card"], fg=t["text"]).pack(side="left")

    toolbar_f = tk.Frame(pop, bg=t["bg"], padx=20)
    toolbar_f.pack(fill="x", pady=(15, 0))

    search_var = tk.StringVar(pop)
    filter_var = tk.StringVar(pop, value="All")

    search_entry = tk.Entry(toolbar_f, textvariable=search_var, font=("Arial", 11), width=35, bg=t["card"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    search_entry.pack(side="left", ipady=4)
    
    def force_clear_search():
        search_var.set("")
        search_entry.focus_set()

    btn_clear = tk.Button(toolbar_f, text="✖", font=("Arial", 10, "bold"), bg=t["card"], fg=t["error"], relief="solid", bd=1, cursor="hand2", command=force_clear_search)
    btn_clear.pack(side="left", padx=(5, 10), ipady=3, ipadx=8)

    tk.Label(toolbar_f, text="Filter:", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["sec"]).pack(side="left", padx=(0, 5))
    
    cb_filter = ttk.Combobox(toolbar_f, textvariable=filter_var, values=["All", "Invoice Voucher", "Purchase Voucher", "Submitted", "Pending"], state="readonly", font=("Arial", 10), width=18, style="GST.TCombobox")
    cb_filter.pack(side="left", ipady=3)
    cb_filter.set("All") 
    
    def clear_highlight(*args):
        cb_filter.selection_clear()
        
    def on_select(*args):
        refresh_table(reset_page=True)
        
    cb_filter.bind("<<ComboboxSelected>>", on_select)
    cb_filter.bind("<FocusIn>", lambda e: pop.after(10, clear_highlight))

    tools_container = tk.Frame(toolbar_f, bg=t["bg"])
    tools_container.pack(side="right", fill="y")

    std_tools = tk.Frame(tools_container, bg=t["bg"])
    std_tools.pack(side="right", fill="y")

    bulk_tools = tk.Frame(tools_container, bg=t["bg"])
    
    lbl_bulk_count = tk.Label(bulk_tools, text="0 Selected", font=("Arial", 11, "bold"), bg=t["bg"], fg=t["accent_blue"])
    lbl_bulk_count.pack(side="left", padx=(0, 15))

    btn_select_all = tk.Button(bulk_tools, text="☑ Select All", font=("Arial", 10, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=3)
    btn_select_all.pack(side="left", padx=(0, 10))

    btn_bulk_cancel = tk.Button(bulk_tools, text="✖ Cancel", font=("Arial", 10, "bold"), bg=t["card"], fg=t["error"], relief="solid", bd=1, cursor="hand2", padx=15, pady=3)
    btn_bulk_cancel.pack(side="left", padx=(0, 10))

    def get_export_items():
        s_term = search_var.get().lower().strip()
        f_val = filter_var.get()
        
        raw_items = []
        for row in master_data_list:
            unique_id = f"{row[8]}_{row[2]}"
            
            if pop.single_export_iid:
                if unique_id != pop.single_export_iid:
                    continue
            else:
                if f_val == "Invoice Voucher" and "OUTPUT" not in row[2]: continue
                if f_val == "Purchase Voucher" and "INPUT" not in row[2]: continue
                if f_val == "Submitted" and row[9] != 1: continue
                if f_val == "Pending" and row[9] == 1: continue
                if s_term:
                    search_string = f"{row[3]} {row[4]}".lower()
                    if s_term not in search_string: continue
                    
                if is_bulk_mode.get() and unique_id not in selected_iids: continue
            
            fmt_date = smart_date_formatter(row[1], date_fmt_code)
            if row[9]:
                sub_date_raw = str(row[10]).strip()
                if sub_date_raw:
                    parts = sub_date_raw.split('||')
                    fmt_sub_date = smart_date_formatter(parts[0], date_fmt_code)
                    ca_text = f"✅ Submitted on {fmt_sub_date}"
                    if len(parts) > 1 and parts[1]: ca_text += f" via {parts[1]}"
                else: ca_text = "✅ Submitted"
            else: ca_text = "📤 Pending"
                
            vals = [0, fmt_date, row[2], row[3], row[4], row[5], format_currency(row[6], curr_fmt), format_currency(row[7], curr_fmt), ca_text]
            raw_items.append((vals, unique_id))
            
        raw_items.sort(key=lambda x: 0 if "OUTPUT" in str(x[0][2]) else 1)
        final_items = []
        for i, (vals, child) in enumerate(raw_items):
            vals[0] = i + 1
            final_items.append((vals, child))
            
        pop.single_export_iid = None 
        return final_items

    def get_decoded_invoice_taxes(inv_id):
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT subtotal, cgst, sgst, igst, place_of_service FROM invoices WHERE id=? AND company_id=?", (inv_id, comp_id))
        inv_row = c.fetchone()
        if not inv_row:
            conn.close()
            return None
            
        sub_t, cg_t, sg_t, ig_t = [safe_float(x) for x in inv_row[:4]]
        place_str = str(inv_row[4])
        
        disc_amt = 0.0
        disc_m = re.search(r'@@DISC@@(.*?)@@', place_str + "@@")
        if disc_m:
            parts = disc_m.group(1).split('||')
            if len(parts) > 2 and str(parts[0]) == '1':
                try:
                    d_val = safe_float(parts[1])
                    if parts[2] == '%': disc_amt = sub_t * (d_val / 100.0)
                    else: disc_amt = d_val
                except: pass
        true_taxable = sub_t - disc_amt if (sub_t - disc_amt) > 0 else 0.0
        
        c.execute("SELECT sac, amount, rate, quantity, days FROM invoice_items WHERE invoice_id=?", (inv_id,))
        i_items = c.fetchall()
        conn.close()
        
        return sub_t, cg_t, sg_t, ig_t, true_taxable, i_items

    def export_drill_pdf():
        items_to_export = get_export_items()
        
        if not items_to_export:
            msg = "Please select at least one bill." if is_bulk_mode.get() else "No bills found matching your current filters."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return

        html = f"<html><head><title>GST Drilldown ({period_key})</title>"
        html += "<style>@page { size: landscape; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-top:20px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space:nowrap;} th{background-color:#f2f2f2;} .sub-table{width:95%; margin:5px auto; margin-bottom:15px; border:2px solid #94a3b8;} .sub-table th{background-color:#e2e8f0; font-size:13px; color:#1e293b;} .sub-table td{font-size:13px; background-color:#f8fafc; color:#334155;}</style></head><body>"
        html += f"<h2>Bill-Wise GST Details: {period_key}</h2>"
        html += f"<p><b>Filter:</b> {filter_var.get()}</p>"
        html += "<table><tr><th>SL. NO.</th><th>DATE</th><th>TRANSACTION TYPE</th><th>INVOICE / BILL NO.</th><th>PARTY NAME</th><th>GSTIN</th><th>TOTAL TAXABLE VALUE</th><th>TOTAL GST AMOUNT</th></tr>"
        
        for vals, child_id in items_to_export:
            html += "<tr>"
            for v in vals[:8]: html += f"<td>{v}</td>" 
            html += "</tr>"
            
            db_id, t_type, _ = row_map.get(child_id, (None, None, None))
            if db_id and "OUTPUT" in str(t_type):
                decoded = get_decoded_invoice_taxes(db_id)
                if decoded:
                    sub_t, cg_t, sg_t, ig_t, true_taxable, i_items = decoded
                    
                    hsn_dict = {}
                    for i_itm in i_items:
                        hsn = str(i_itm[0]).strip() if i_itm[0] else ""
                        if not hsn or hsn.lower() in ["none", "unknown"]: continue 
                        
                        amt = safe_float(i_itm[1])
                        rate = safe_float(i_itm[2]) if len(i_itm) > 2 else 0.0
                        qty = safe_float(i_itm[3]) if len(i_itm) > 3 else 0.0
                        days = safe_float(i_itm[4]) if len(i_itm) > 4 else 0.0
                        
                        phys_qty = qty * (days if days > 0 else 1.0)
                        if phys_qty <= 0: phys_qty = 1.0
                        if amt <= 0 and rate > 0: amt = rate * phys_qty
                        
                        ratio = (amt / sub_t) if sub_t > 0 else 0
                        discounted_amt = true_taxable * ratio
                        
                        if hsn not in hsn_dict: hsn_dict[hsn] = {'tax': 0.0, 'cg': 0.0, 'sg': 0.0, 'ig': 0.0}
                        hsn_dict[hsn]['tax'] += discounted_amt
                        hsn_dict[hsn]['cg'] += cg_t * ratio
                        hsn_dict[hsn]['sg'] += sg_t * ratio
                        hsn_dict[hsn]['ig'] += ig_t * ratio
                        
                    if hsn_dict:
                        html += "<tr><td style='border:none;'></td><td colspan='7' style='padding:0; border:none;'>"
                        html += "<table class='sub-table'><tr><th>HSN/SAC</th><th>TAXABLE VAL</th><th>CGST %</th><th>CGST AMT</th><th>SGST %</th><th>SGST AMT</th><th>IGST %</th><th>IGST AMT</th><th>TOTAL TAX</th></tr>"
                        for h_k, h_v in hsn_dict.items():
                            t_tax = h_v['cg'] + h_v['sg'] + h_v['ig']
                            cg_pct = round((h_v['cg'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                            sg_pct = round((h_v['sg'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                            ig_pct = round((h_v['ig'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                            html += f"<tr><td>{h_k}</td><td>{format_currency(h_v['tax'], curr_fmt)}</td><td>{cg_pct:g}%</td><td>{format_currency(h_v['cg'], curr_fmt)}</td><td>{sg_pct:g}%</td><td>{format_currency(h_v['sg'], curr_fmt)}</td><td>{ig_pct:g}%</td><td>{format_currency(h_v['ig'], curr_fmt)}</td><td><b>{format_currency(t_tax, curr_fmt)}</b></td></tr>"
                        html += "</table></td></tr>"
        
        html += "</table><script>window.onload=function(){window.print();}</script></body></html>"
        
        fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))
        pop.focus_set()

    def export_drill_csv():
        items_to_export = get_export_items()
        if not items_to_export:
            msg = "Please select at least one bill." if is_bulk_mode.get() else "No bills found matching your current filters."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return

        file_path = filedialog.asksaveasfilename(parent=pop, defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title=f"Export GST Details - {period_key}")
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([f"BILL-WISE DETAILS: {period_key}"])
                writer.writerow(["Filter:", filter_var.get(), "Search:", search_var.get() if search_var.get() else "None"])
                writer.writerow([])
                writer.writerow(["SL. NO.", "DATE", "TRANSACTION TYPE", "INVOICE / BILL NO.", "PARTY NAME", "GSTIN", "TOTAL TAXABLE VALUE", "TOTAL GST AMOUNT", "STATUS"])
                
                for vals, child_id in items_to_export:
                    writer.writerow(vals)
                    
                    db_id, t_type, _ = row_map.get(child_id, (None, None, None))
                    if db_id and "OUTPUT" in str(t_type):
                        decoded = get_decoded_invoice_taxes(db_id)
                        if decoded:
                            sub_t, cg_t, sg_t, ig_t, true_taxable, i_items = decoded
                            
                            hsn_dict = {}
                            for i_itm in i_items:
                                hsn = str(i_itm[0]).strip() if i_itm[0] else ""
                                if not hsn or hsn.lower() in ["none", "unknown"]: continue 
                                
                                amt = safe_float(i_itm[1])
                                rate = safe_float(i_itm[2]) if len(i_itm) > 2 else 0.0
                                qty = safe_float(i_itm[3]) if len(i_itm) > 3 else 0.0
                                days = safe_float(i_itm[4]) if len(i_itm) > 4 else 0.0
                                
                                phys_qty = qty * (days if days > 0 else 1.0)
                                if phys_qty <= 0: phys_qty = 1.0
                                if amt <= 0 and rate > 0: amt = rate * phys_qty
                                
                                ratio = (amt / sub_t) if sub_t > 0 else 0
                                discounted_amt = true_taxable * ratio
                                
                                if hsn not in hsn_dict: hsn_dict[hsn] = {'tax': 0.0, 'cg': 0.0, 'sg': 0.0, 'ig': 0.0}
                                hsn_dict[hsn]['tax'] += discounted_amt
                                hsn_dict[hsn]['cg'] += cg_t * ratio
                                hsn_dict[hsn]['sg'] += sg_t * ratio
                                hsn_dict[hsn]['ig'] += ig_t * ratio
                                
                            if hsn_dict:
                                writer.writerow(["", "", "--- TAX SUMMARY ---", "HSN/SAC", "TAXABLE VAL", "CGST %", "CGST AMT", "SGST %", "SGST AMT", "IGST %", "IGST AMT", "TOTAL TAX"])
                                for h_k, h_v in hsn_dict.items():
                                    t_tax = h_v['cg'] + h_v['sg'] + h_v['ig']
                                    cg_pct = round((h_v['cg'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                                    sg_pct = round((h_v['sg'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                                    ig_pct = round((h_v['ig'] / h_v['tax']) * 100, 2) if h_v['tax'] > 0 else 0
                                    writer.writerow(["", "", "", h_k, format_currency(h_v['tax'], curr_fmt), f"{cg_pct:g}%", format_currency(h_v['cg'], curr_fmt), f"{sg_pct:g}%", format_currency(h_v['sg'], curr_fmt), f"{ig_pct:g}%", format_currency(h_v['ig'], curr_fmt), format_currency(t_tax, curr_fmt)])
                                writer.writerow([]) 
            messagebox.showinfo("Export Successful", f"Details exported to:\n{file_path}", parent=pop)
            search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", str(e), parent=pop)

    def export_drill_hsn_pdf():
        items_to_export = get_export_items()
        valid_inv_ids = []
        for vals, unique_id in items_to_export:
            if "OUTPUT" in unique_id:
                try: valid_inv_ids.append(int(unique_id.split('_')[0]))
                except: pass
                
        if not valid_inv_ids:
            msg = "Please select at least one Sales Invoice." if is_bulk_mode.get() else "No Sales Invoices found matching your current filters."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return

        try:
            hsn_data = {} 
            for inv_id in valid_inv_ids:
                decoded = get_decoded_invoice_taxes(inv_id)
                if not decoded: continue
                subtotal, cgst, sgst, igst, true_taxable, items = decoded
                
                for item in items:
                    hsn = str(item[0]).strip() if item[0] else ""
                    if not hsn or hsn.lower() in ["none", "unknown"]: continue 
                    
                    amt = safe_float(item[1])
                    rate = safe_float(item[2]) if len(item) > 2 else 0.0
                    qty = safe_float(item[3]) if len(item) > 3 else 0.0
                    days = safe_float(item[4]) if len(item) > 4 else 0.0
                    
                    total_physical_qty = qty * (days if days > 0 else 1.0)
                    
                    if total_physical_qty <= 0 and amt > 0: 
                        total_physical_qty = 1.0 
                        
                    if amt <= 0 and rate > 0: amt = rate * total_physical_qty
                    
                    ratio = (amt / subtotal) if subtotal > 0 else 0
                    discounted_amt = true_taxable * ratio
                    
                    item_cgst = cgst * ratio
                    item_sgst = sgst * ratio
                    item_igst = igst * ratio
                        
                    if hsn not in hsn_data:
                        hsn_data[hsn] = {'qty': 0.0, 'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                        
                    hsn_data[hsn]['qty'] += total_physical_qty
                    hsn_data[hsn]['taxable'] += discounted_amt
                    hsn_data[hsn]['cgst'] += item_cgst
                    hsn_data[hsn]['sgst'] += item_sgst
                    hsn_data[hsn]['igst'] += item_igst
            
            if not hsn_data:
                msg = "No genuine HSN/SAC items found in the selected bills."
                messagebox.showinfo("Empty Summary", msg, parent=pop)
                return

            html = f"<html><head><title>Tax Summary (GSTR-1) - ({period_key})</title>"
            html += "<style>@page { size: landscape; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-top:20px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space: nowrap;} th{background-color:#f2f2f2;}</style></head><body>"
            html += f"<h2>Tax Summary (GSTR-1) - {period_key}</h2>"
            html += "<table><tr><th>SL. NO.</th><th>HSN/SAC</th><th>TOTAL QTY</th><th>TAXABLE VAL</th><th>CGST %</th><th>CGST AMT</th><th>SGST %</th><th>SGST AMT</th><th>IGST %</th><th>IGST AMT</th><th>TOTAL TAX</th></tr>"
            
            sorted_hsn = sorted(hsn_data.keys())
            g_qty = g_tax = g_cg = g_sg = g_ig = g_tot = 0.0
            
            for index, hsn in enumerate(sorted_hsn, 1):
                d = hsn_data[hsn]
                tot_tax = d['cgst'] + d['sgst'] + d['igst']
                
                g_qty += d['qty']
                g_tax += d['taxable']
                g_cg += d['cgst']
                g_sg += d['sgst']
                g_ig += d['igst']
                g_tot += tot_tax
                
                display_qty = int(d['qty']) if d['qty'] == int(d['qty']) else round(d['qty'], 2)
                
                cg_pct = round((d['cgst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                sg_pct = round((d['sgst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                ig_pct = round((d['igst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                
                html += f"<tr><td>{index}</td><td>{hsn}</td><td>{display_qty}</td><td>{format_currency(d['taxable'], curr_fmt)}</td><td>{cg_pct:g}%</td><td>{format_currency(d['cgst'], curr_fmt)}</td><td>{sg_pct:g}%</td><td>{format_currency(d['sgst'], curr_fmt)}</td><td>{ig_pct:g}%</td><td>{format_currency(d['igst'], curr_fmt)}</td><td>{format_currency(tot_tax, curr_fmt)}</td></tr>"
                
            display_g_qty = int(g_qty) if g_qty == int(g_qty) else round(g_qty, 2)
            html += f"<tr style='background-color:#e2e8f0; font-weight:bold;'><td colspan='2'>TOTAL</td><td>{display_g_qty}</td><td>{format_currency(g_tax, curr_fmt)}</td><td></td><td>{format_currency(g_cg, curr_fmt)}</td><td></td><td>{format_currency(g_sg, curr_fmt)}</td><td></td><td>{format_currency(g_ig, curr_fmt)}</td><td>{format_currency(g_tot, curr_fmt)}</td></tr>"
                
            html += "</table><script>window.onload=function(){window.print();}</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
            webbrowser.open('file://' + os.path.realpath(path))
            pop.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred:\n{str(e)}", parent=pop)

    def export_drill_hsn():
        items_to_export = get_export_items()
        valid_inv_ids = []
        for vals, unique_id in items_to_export:
            if "OUTPUT" in unique_id:
                try: valid_inv_ids.append(int(unique_id.split('_')[0]))
                except: pass
                
        if not valid_inv_ids:
            msg = "Please select at least one Sales Invoice." if is_bulk_mode.get() else "No Sales Invoices found matching your current filters."
            messagebox.showinfo("Empty Export", parent=pop)
            return

        file_path = filedialog.asksaveasfilename(parent=pop, defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title=f"Export HSN Summary - {period_key}")
        if not file_path: return
        
        try:
            hsn_data = {} 
            for inv_id in valid_inv_ids:
                decoded = get_decoded_invoice_taxes(inv_id)
                if not decoded: continue
                subtotal, cgst, sgst, igst, true_taxable, items = decoded
                
                for item in items:
                    hsn = str(item[0]).strip() if item[0] else ""
                    if not hsn or hsn.lower() in ["none", "unknown"]: continue 
                    
                    amt = safe_float(item[1])
                    rate = safe_float(item[2]) if len(item) > 2 else 0.0
                    qty = safe_float(item[3]) if len(item) > 3 else 0.0
                    days = safe_float(item[4]) if len(item) > 4 else 0.0
                    
                    total_physical_qty = qty * (days if days > 0 else 1.0)
                    
                    if total_physical_qty <= 0 and amt > 0: 
                        total_physical_qty = 1.0 
                        
                    if amt <= 0 and rate > 0: amt = rate * total_physical_qty
                    
                    ratio = (amt / subtotal) if subtotal > 0 else 0
                    discounted_amt = true_taxable * ratio
                    
                    item_cgst = cgst * ratio
                    item_sgst = sgst * ratio
                    item_igst = igst * ratio
                        
                    if hsn not in hsn_data:
                        hsn_data[hsn] = {'qty': 0.0, 'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                        
                    hsn_data[hsn]['qty'] += total_physical_qty
                    hsn_data[hsn]['taxable'] += discounted_amt
                    hsn_data[hsn]['cgst'] += item_cgst
                    hsn_data[hsn]['sgst'] += item_sgst
                    hsn_data[hsn]['igst'] += item_igst
            
            if not hsn_data:
                msg = "No genuine HSN/SAC items found in the selected bills."
                messagebox.showinfo("Empty Summary", msg, parent=pop)
                return
            
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow([f"TAX SUMMARY (GSTR-1) ({period_key}) - OUTWARD SUPPLIES"])
                writer.writerow(["Generated on", smart_date_formatter(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), date_fmt_code)])
                writer.writerow([])
                writer.writerow(["SL. NO.", "HSN/SAC", "TOTAL QTY", "TAXABLE VAL", "CGST %", "CGST AMT", "SGST %", "SGST AMT", "IGST %", "IGST AMT", "TOTAL TAX"])
                
                sorted_hsn = sorted(hsn_data.keys())
                g_qty = g_tax = g_cg = g_sg = g_ig = g_tot = 0.0
                
                for index, hsn in enumerate(sorted_hsn, 1):
                    d = hsn_data[hsn]
                    tot_tax = d['cgst'] + d['sgst'] + d['igst']
                    
                    g_qty += d['qty']
                    g_tax += d['taxable']
                    g_cg += d['cgst']
                    g_sg += d['sgst']
                    g_ig += d['igst']
                    g_tot += tot_tax
                    
                    display_qty = int(d['qty']) if d['qty'] == int(d['qty']) else round(d['qty'], 2)
                    
                    cg_pct = round((d['cgst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                    sg_pct = round((d['sgst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                    ig_pct = round((d['igst'] / d['taxable']) * 100, 2) if d['taxable'] > 0 else 0
                    
                    writer.writerow([
                        index, hsn, display_qty, format_currency(d['taxable'], curr_fmt),
                        f"{cg_pct:g}%", format_currency(d['cgst'], curr_fmt),
                        f"{sg_pct:g}%", format_currency(d['sgst'], curr_fmt),
                        f"{ig_pct:g}%", format_currency(d['igst'], curr_fmt),
                        format_currency(tot_tax, curr_fmt)
                    ])
                    
                display_g_qty = int(g_qty) if g_qty == int(g_qty) else round(g_qty, 2)
                writer.writerow(["", "TOTAL", display_g_qty, format_currency(g_tax, curr_fmt), "", format_currency(g_cg, curr_fmt), "", format_currency(g_sg, curr_fmt), "", format_currency(g_ig, curr_fmt), format_currency(g_tot, curr_fmt)])
                    
            messagebox.showinfo("Export Successful", f"Tax Summary (GSTR-1) exported successfully to:\n{file_path}", parent=pop)
            search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred while generating the HSN summary:\n{str(e)}", parent=pop)

    def export_drill_gstr3b_pdf():
        items_to_export = get_export_items()
        if not items_to_export:
            msg = "Please select at least one bill." if is_bulk_mode.get() else "No bills found matching your current filters."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return

        slab_data = {"OUTPUT": {}, "INPUT": {}}
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            for vals, unique_id in items_to_export:
                db_id, t_type, _ = row_map.get(unique_id, (None, None, None))
                if not db_id: continue
                
                is_output = "OUTPUT" in str(t_type)
                category = "OUTPUT" if is_output else "INPUT"
                
                if is_output:
                    decoded = get_decoded_invoice_taxes(db_id)
                    if not decoded: continue
                    subtotal, cgst, sgst, igst, true_taxable, items = decoded
                else:
                    c.execute("SELECT subtotal, cgst, sgst, igst FROM purchases WHERE id=? AND company_id=?", (db_id, comp_id))
                    main_row = c.fetchone()
                    if not main_row: continue
                    subtotal, cgst, sgst, igst = [safe_float(x) for x in main_row]
                    true_taxable = subtotal
                    c.execute("SELECT amount, rate, quantity FROM purchase_items WHERE purchase_id=?", (db_id,))
                    items = c.fetchall()
                
                for item in items:
                    if is_output:
                        amt = safe_float(item[1])
                        rate = safe_float(item[2]) if len(item) > 2 else 0.0
                        qty = safe_float(item[3]) if len(item) > 3 else 0.0
                        days = safe_float(item[4]) if len(item) > 4 else 1.0
                    else:
                        amt = safe_float(item[0])
                        rate = safe_float(item[1]) if len(item) > 1 else 0.0
                        qty = safe_float(item[2]) if len(item) > 2 else 0.0
                        days = 1.0
                    
                    phys_qty = qty * (days if days > 0 else 1.0)
                    if phys_qty <= 0: phys_qty = 1.0
                    if amt <= 0 and rate > 0: amt = rate * phys_qty
                    
                    ratio = (amt / subtotal) if subtotal > 0 else 0
                    discounted_amt = true_taxable * ratio
                    
                    item_cgst = cgst * ratio
                    item_sgst = sgst * ratio
                    item_igst = igst * ratio
                        
                    cg_pct = round((item_cgst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    sg_pct = round((item_sgst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    ig_pct = round((item_igst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    
                    slab = round(cg_pct + sg_pct + ig_pct)
                    slab_str = f"{slab}%"
                    
                    if slab_str not in slab_data[category]:
                        slab_data[category][slab_str] = {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                        
                    slab_data[category][slab_str]['taxable'] += discounted_amt
                    slab_data[category][slab_str]['cgst'] += item_cgst
                    slab_data[category][slab_str]['sgst'] += item_sgst
                    slab_data[category][slab_str]['igst'] += item_igst
                    
            conn.close()
            
            html = f"<html><head><title>Tax Slab Summary (GSTR-3B) - ({period_key})</title>"
            html += "<style>@page { size: portrait; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-top:10px; margin-bottom: 30px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space:nowrap;} th{background-color:#f2f2f2;} h3 {margin-bottom: 5px;}</style></head><body>"
            html += f"<h2>Tax Slab Summary (GSTR-3B) - {period_key}</h2>"
            
            for cat in ["OUTPUT", "INPUT"]:
                if not slab_data[cat]: continue
                
                title = "Outward Supplies (Sales / Output GST)" if cat == "OUTPUT" else "Inward Supplies (Purchases / Input GST)"
                html += f"<h3>{title}</h3>"
                html += "<table><tr><th>GST SLAB</th><th>TOTAL TAXABLE VALUE</th><th>TOTAL CGST</th><th>TOTAL SGST</th><th>TOTAL IGST</th><th>TOTAL TAX</th></tr>"
                
                g_taxable = g_cgst = g_sgst = g_igst = g_tot = 0.0
                sorted_slabs = sorted(slab_data[cat].keys(), key=lambda x: int(x.replace('%', '')))
                
                for slab in sorted_slabs:
                    d = slab_data[cat][slab]
                    tot_tax = d['cgst'] + d['sgst'] + d['igst']
                    
                    g_taxable += d['taxable']
                    g_cgst += d['cgst']
                    g_sgst += d['sgst']
                    g_igst += d['igst']
                    g_tot += tot_tax
                    
                    html += f"<tr><td><b>{slab}</b></td><td>{format_currency(d['taxable'], curr_fmt)}</td><td>{format_currency(d['cgst'], curr_fmt)}</td><td>{format_currency(d['sgst'], curr_fmt)}</td><td>{format_currency(d['igst'], curr_fmt)}</td><td><b>{format_currency(tot_tax, curr_fmt)}</b></td></tr>"
                    
                html += f"<tr style='background-color:#e2e8f0; font-weight:bold;'><td>TOTAL</td><td>{format_currency(g_taxable, curr_fmt)}</td><td>{format_currency(g_cgst, curr_fmt)}</td><td>{format_currency(g_sgst, curr_fmt)}</td><td>{format_currency(g_igst, curr_fmt)}</td><td>{format_currency(g_tot, curr_fmt)}</td></tr>"
                html += "</table>"
                
            html += "<script>window.onload=function(){window.print();}</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
            webbrowser.open('file://' + os.path.realpath(path))
            pop.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred:\n{str(e)}", parent=pop)

    def export_drill_gstr3b_csv():
        items_to_export = get_export_items()
        if not items_to_export:
            msg = "Please select at least one bill." if is_bulk_mode.get() else "No bills found matching your current filters."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return
            
        file_path = filedialog.asksaveasfilename(parent=pop, defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title=f"Export GSTR-3B Summary - {period_key}")
        if not file_path: return

        slab_data = {"OUTPUT": {}, "INPUT": {}}
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            for vals, unique_id in items_to_export:
                db_id, t_type, _ = row_map.get(unique_id, (None, None, None))
                if not db_id: continue
                
                is_output = "OUTPUT" in str(t_type)
                category = "OUTPUT" if is_output else "INPUT"
                
                if is_output:
                    decoded = get_decoded_invoice_taxes(db_id)
                    if not decoded: continue
                    subtotal, cgst, sgst, igst, true_taxable, items = decoded
                else:
                    c.execute("SELECT subtotal, cgst, sgst, igst FROM purchases WHERE id=? AND company_id=?", (db_id, comp_id))
                    main_row = c.fetchone()
                    if not main_row: continue
                    subtotal, cgst, sgst, igst = [safe_float(x) for x in main_row]
                    true_taxable = subtotal
                    c.execute("SELECT amount, rate, quantity FROM purchase_items WHERE purchase_id=?", (db_id,))
                    items = c.fetchall()
                
                for item in items:
                    if is_output:
                        amt = safe_float(item[1])
                        rate = safe_float(item[2]) if len(item) > 2 else 0.0
                        qty = safe_float(item[3]) if len(item) > 3 else 0.0
                        days = safe_float(item[4]) if len(item) > 4 else 1.0
                    else:
                        amt = safe_float(item[0])
                        rate = safe_float(item[1]) if len(item) > 1 else 0.0
                        qty = safe_float(item[2]) if len(item) > 2 else 0.0
                        days = 1.0
                    
                    phys_qty = qty * (days if days > 0 else 1.0)
                    if phys_qty <= 0: phys_qty = 1.0
                    if amt <= 0 and rate > 0: amt = rate * phys_qty
                    
                    ratio = (amt / subtotal) if subtotal > 0 else 0
                    discounted_amt = true_taxable * ratio
                    
                    item_cgst = cgst * ratio
                    item_sgst = sgst * ratio
                    item_igst = igst * ratio
                        
                    cg_pct = round((item_cgst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    sg_pct = round((item_sgst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    ig_pct = round((item_igst / discounted_amt) * 100, 2) if discounted_amt > 0 else 0
                    
                    slab = round(cg_pct + sg_pct + ig_pct)
                    slab_str = f"{slab}%"
                    
                    if slab_str not in slab_data[category]:
                        slab_data[category][slab_str] = {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                        
                    slab_data[category][slab_str]['taxable'] += discounted_amt
                    slab_data[category][slab_str]['cgst'] += item_cgst
                    slab_data[category][slab_str]['sgst'] += item_sgst
                    slab_data[category][slab_str]['igst'] += item_igst
                    
            conn.close()
            
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow([f"TAX SLAB SUMMARY (GSTR-3B) - {period_key}"])
                writer.writerow(["Generated on", smart_date_formatter(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), date_fmt_code)])
                writer.writerow([])
                
                for cat in ["OUTPUT", "INPUT"]:
                    if not slab_data[cat]: continue
                    title = "OUTWARD SUPPLIES (SALES / OUTPUT GST)" if cat == "OUTPUT" else "INWARD SUPPLIES (PURCHASES / INPUT GST)"
                    writer.writerow([title])
                    writer.writerow(["GST SLAB", "TOTAL TAXABLE VALUE", "TOTAL CGST", "TOTAL SGST", "TOTAL IGST", "TOTAL TAX"])
                    
                    g_taxable = g_cgst = g_sgst = g_igst = g_tot = 0.0
                    sorted_slabs = sorted(slab_data[cat].keys(), key=lambda x: int(x.replace('%', '')))
                    
                    for slab in sorted_slabs:
                        d = slab_data[cat][slab]
                        tot_tax = d['cgst'] + d['sgst'] + d['igst']
                        
                        g_taxable += d['taxable']
                        g_cgst += d['cgst']
                        g_sgst += d['sgst']
                        g_igst += d['igst']
                        g_tot += tot_tax
                        
                        writer.writerow([
                            slab, format_currency(d['taxable'], curr_fmt), 
                            format_currency(d['cgst'], curr_fmt), format_currency(d['sgst'], curr_fmt),
                            format_currency(d['igst'], curr_fmt), format_currency(tot_tax, curr_fmt)
                        ])
                        
                    writer.writerow(["TOTAL", format_currency(g_taxable, curr_fmt), format_currency(g_cgst, curr_fmt), format_currency(g_sgst, curr_fmt), format_currency(g_igst, curr_fmt), format_currency(g_tot, curr_fmt)])
                    writer.writerow([])
                    
            messagebox.showinfo("Export Successful", f"GSTR-3B Summary exported successfully to:\n{file_path}", parent=pop)
            search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", f"An error occurred:\n{str(e)}", parent=pop)

    def export_drill_b2b_pdf():
        items_to_export = get_export_items()
        sales_items = [item for item in items_to_export if "OUTPUT" in str(row_map.get(item[1], ("", "", ""))[1])]
        
        if not sales_items:
            msg = "No Sales Invoices found to bifurcate."
            messagebox.showinfo("Empty Export", msg, parent=pop)
            return

        b2b_items, b2c_items = [], []
        for vals, child_id in sales_items:
            gstin = str(vals[5]).strip().upper()
            if gstin and gstin != "UNREGISTERED" and len(gstin) > 5: b2b_items.append(vals)
            else: b2c_items.append(vals)

        html = f"<html><head><title>B2B vs B2C Summary (GSTR-1) - {period_key}</title>"
        html += "<style>@page { size: landscape; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-bottom:30px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space: nowrap;} th{background-color:#f2f2f2;} h3{{color:#1e293b; border-bottom: 2px solid #3b82f6; padding-bottom:5px;}}</style></head><body>"
        html += f"<h2>B2B vs B2C Auto-Bifurcation (GSTR-1) : {period_key}</h2>"
        
        if b2b_items:
            html += "<h3>B2B - Registered Supplies</h3>"
            html += "<table><tr><th>SL. NO.</th><th>DATE</th><th>INVOICE NO.</th><th>PARTY NAME</th><th>GSTIN</th><th>TAXABLE VALUE</th><th>GST AMOUNT</th></tr>"
            for i, v in enumerate(b2b_items, 1): html += f"<tr><td>{i}</td><td>{v[1]}</td><td>{v[3]}</td><td>{v[4]}</td><td>{v[5]}</td><td>{v[6]}</td><td>{v[7]}</td></tr>"
            html += "</table>"
            
        if b2c_items:
            html += "<h3>B2C - Unregistered Supplies</h3>"
            html += "<table><tr><th>SL. NO.</th><th>DATE</th><th>INVOICE NO.</th><th>PARTY NAME</th><th>TAXABLE VALUE</th><th>GST AMOUNT</th></tr>"
            for i, v in enumerate(b2c_items, 1): html += f"<tr><td>{i}</td><td>{v[1]}</td><td>{v[3]}</td><td>{v[4]}</td><td>{v[6]}</td><td>{v[7]}</td></tr>"
            html += "</table>"

        html += "<script>window.onload=function(){window.print();}</script></body></html>"
        fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))
        pop.focus_set()

    def export_drill_b2b_csv():
        items_to_export = get_export_items()
        sales_items = [item for item in items_to_export if "OUTPUT" in str(row_map.get(item[1], ("", "", ""))[1])]
        
        if not sales_items:
            messagebox.showinfo("Empty Export", "No Sales Invoices found to bifurcate.", parent=pop)
            return

        file_path = filedialog.asksaveasfilename(parent=pop, defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title=f"Export B2B/B2C Summary - {period_key}")
        if not file_path: return

        b2b_items, b2c_items = [], []
        for vals, child_id in sales_items:
            gstin = str(vals[5]).strip().upper()
            if gstin and gstin != "UNREGISTERED" and len(gstin) > 5: b2b_items.append(vals)
            else: b2c_items.append(vals)

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([f"B2B vs B2C AUTO-BIFURCATION (GSTR-1) - {period_key}"])
                writer.writerow(["Generated on", smart_date_formatter(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), date_fmt_code)])
                writer.writerow([])
                
                if b2b_items:
                    writer.writerow(["B2B - REGISTERED SUPPLIES"])
                    writer.writerow(["SL. NO.", "DATE", "INVOICE NO.", "PARTY NAME", "GSTIN", "TAXABLE VALUE", "GST AMOUNT"])
                    for i, v in enumerate(b2b_items, 1): writer.writerow([i, v[1], v[3], v[4], v[5], v[6], v[7]])
                    writer.writerow([])
                    
                if b2c_items:
                    writer.writerow(["B2C - UNREGISTERED SUPPLIES"])
                    writer.writerow(["SL. NO.", "DATE", "INVOICE NO.", "PARTY NAME", "TAXABLE VALUE", "GST AMOUNT"])
                    for i, v in enumerate(b2c_items, 1): writer.writerow([i, v[1], v[3], v[4], v[6], v[7]])
                    writer.writerow([])
            messagebox.showinfo("Export Successful", f"B2B/B2C Summary exported to:\n{file_path}", parent=pop)
            search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", str(e), parent=pop)

    def export_drill_itc_pdf():
        items_to_export = get_export_items()
        purch_items = [item for item in items_to_export if "INPUT" in str(row_map.get(item[1], ("", "", ""))[1])]
        
        if not purch_items:
            messagebox.showinfo("Empty Export", "No Purchase Bills found for ITC Ledger.", parent=pop)
            return

        party_data = {}
        try:
            conn = database.get_connection()
            c = conn.cursor()
            for vals, child_id in purch_items:
                db_id = row_map.get(child_id, (None, None, None))[0]
                if not db_id: continue
                
                vendor = str(vals[4]).strip()
                gstin = str(vals[5]).strip()
                pkey = f"{vendor}_{gstin}"
                
                c.execute("SELECT subtotal, cgst, sgst, igst FROM purchases WHERE id=? AND company_id=?", (db_id, comp_id))
                row = c.fetchone()
                if row:
                    sub, cg, sg, ig = [safe_float(x) for x in row]
                    if pkey not in party_data:
                        party_data[pkey] = {'vendor': vendor, 'gstin': gstin, 'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                    party_data[pkey]['taxable'] += sub
                    party_data[pkey]['cgst'] += cg
                    party_data[pkey]['sgst'] += sg
                    party_data[pkey]['igst'] += ig
            conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=pop); return

        html = f"<html><head><title>Party-Wise ITC Ledger (GSTR-2B) - {period_key}</title>"
        html += "<style>@page { size: landscape; } body{font-family:Arial, sans-serif;} table{width:100%; border-collapse:collapse; margin-top:20px;} th,td{border:1px solid #ddd; padding:8px; text-align:center; white-space: nowrap;} th{background-color:#f2f2f2;} h2{margin-bottom:0px;} h4{margin-top:5px; color:#475569;}</style></head><body>"
        html += f"<h2>Party-Wise ITC Ledger (GSTR-2B)</h2><h4>Period: {period_key}</h4>"
        html += "<table><tr><th>SL. NO.</th><th>VENDOR NAME</th><th>GSTIN</th><th>TOTAL TAXABLE</th><th>TOTAL CGST</th><th>TOTAL SGST</th><th>TOTAL IGST</th><th>TOTAL ITC (TAX)</th></tr>"
        
        g_tax = g_cg = g_sg = g_ig = g_tot = 0.0
        for i, (k, d) in enumerate(sorted(party_data.items(), key=lambda x: x[1]['vendor']), 1):
            tot = d['cgst'] + d['sgst'] + d['igst']
            g_tax += d['taxable']; g_cg += d['cgst']; g_sg += d['sgst']; g_ig += d['igst']; g_tot += tot
            html += f"<tr><td>{i}</td><td>{d['vendor']}</td><td>{d['gstin']}</td><td>{format_currency(d['taxable'], curr_fmt)}</td><td>{format_currency(d['cgst'], curr_fmt)}</td><td>{format_currency(d['sgst'], curr_fmt)}</td><td>{format_currency(d['igst'], curr_fmt)}</td><td><b>{format_currency(tot, curr_fmt)}</b></td></tr>"
            
        html += f"<tr style='background-color:#e2e8f0; font-weight:bold;'><td colspan='3'>TOTAL</td><td>{format_currency(g_tax, curr_fmt)}</td><td>{format_currency(g_cg, curr_fmt)}</td><td>{format_currency(g_sg, curr_fmt)}</td><td>{format_currency(g_ig, curr_fmt)}</td><td>{format_currency(g_tot, curr_fmt)}</td></tr>"
        html += "</table><script>window.onload=function(){window.print();}</script></body></html>"

        fd, path = tempfile.mkstemp(suffix=".html", prefix="GST_Report_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + os.path.realpath(path))
        pop.focus_set()

    def export_drill_itc_csv():
        items_to_export = get_export_items()
        purch_items = [item for item in items_to_export if "INPUT" in str(row_map.get(item[1], ("", "", ""))[1])]
        
        if not purch_items:
            messagebox.showinfo("Empty Export", "No Purchase Bills found for ITC Ledger.", parent=pop)
            return

        file_path = filedialog.asksaveasfilename(parent=pop, defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title=f"Export Party-Wise ITC - {period_key}")
        if not file_path: return

        party_data = {}
        try:
            conn = database.get_connection()
            c = conn.cursor()
            for vals, child_id in purch_items:
                db_id = row_map.get(child_id, (None, None, None))[0]
                if not db_id: continue
                
                vendor = str(vals[4]).strip()
                gstin = str(vals[5]).strip()
                pkey = f"{vendor}_{gstin}"
                
                c.execute("SELECT subtotal, cgst, sgst, igst FROM purchases WHERE id=? AND company_id=?", (db_id, comp_id))
                row = c.fetchone()
                if row:
                    sub, cg, sg, ig = [safe_float(x) for x in row]
                    if pkey not in party_data:
                        party_data[pkey] = {'vendor': vendor, 'gstin': gstin, 'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'igst': 0.0}
                    party_data[pkey]['taxable'] += sub
                    party_data[pkey]['cgst'] += cg
                    party_data[pkey]['sgst'] += sg
                    party_data[pkey]['igst'] += ig
            conn.close()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=pop); return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([f"PARTY-WISE ITC LEDGER (GSTR-2B) - {period_key}"])
                writer.writerow(["Generated on", smart_date_formatter(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), date_fmt_code)])
                writer.writerow([])
                writer.writerow(["SL. NO.", "VENDOR NAME", "GSTIN", "TOTAL TAXABLE", "TOTAL CGST", "TOTAL SGST", "TOTAL IGST", "TOTAL ITC (TAX)"])
                
                g_tax = g_cg = g_sg = g_ig = g_tot = 0.0
                for i, (k, d) in enumerate(sorted(party_data.items(), key=lambda x: x[1]['vendor']), 1):
                    tot = d['cgst'] + d['sgst'] + d['igst']
                    g_tax += d['taxable']; g_cg += d['cgst']; g_sg += d['sgst']; g_ig += d['igst']; g_tot += tot
                    writer.writerow([i, d['vendor'], d['gstin'], format_currency(d['taxable'], curr_fmt), format_currency(d['cgst'], curr_fmt), format_currency(d['sgst'], curr_fmt), format_currency(d['igst'], curr_fmt), format_currency(tot, curr_fmt)])
                    
                writer.writerow(["", "TOTAL", "", format_currency(g_tax, curr_fmt), format_currency(g_cg, curr_fmt), format_currency(g_sg, curr_fmt), format_currency(g_ig, curr_fmt), format_currency(g_tot, curr_fmt)])
            messagebox.showinfo("Export Successful", f"Party-Wise ITC exported to:\n{file_path}", parent=pop)
            search_entry.focus_set()
        except Exception as e:
            messagebox.showerror("Export Failed", str(e), parent=pop)

    # --- THE FIX: Enforce Export Lock & Audit Export Actions ---
    def enforce_export(export_func, report_name):
        app = pop.winfo_toplevel()
        uid = int(getattr(app, 'current_user_id', 1))
        is_admin = str(uid) == "1"
        if not is_admin:
            u_row = database.get_user_by_id(uid)
            if u_row and u_row[3] == "Admin": is_admin = True
            
        if not is_admin:
            perms = database.get_user_permissions(uid)
            if perms.get("gst_rules", {}).get("lock_export", False):
                messagebox.showwarning("Access Restricted", "Exporting GST reports is locked for your account.\n\nPlease contact the Admin.", parent=pop)
                return
                
        # Run the actual export
        export_func()
        
        # Log it
        database.log_audit("GST Report", "Compliance Export", period_key, f"Exported {report_name}.", 0.0, company_id=comp_id)

    def build_export_menu(menu_parent, fmt="csv"):
        m = tk.Menu(menu_parent, tearoff=0, font=("Arial", 10), bg=t["card"], fg=t["text"], activebackground=t["accent_blue"])
        if fmt == "csv":
            m.add_command(label="📄 Main Table (Bill-Wise Details)", command=lambda: enforce_export(export_drill_csv, "Bill-Wise Details (CSV)"))
            m.add_command(label="📊 HSN Summary (GSTR-1)", command=lambda: enforce_export(export_drill_hsn, "HSN Summary GSTR-1 (CSV)"))
            m.add_command(label="📈 Tax Slab Summary (GSTR-3B)", command=lambda: enforce_export(export_drill_gstr3b_csv, "Tax Slab Summary GSTR-3B (CSV)"))
            m.add_separator()
            m.add_command(label="🏢 B2B vs B2C Sales (GSTR-1)", command=lambda: enforce_export(export_drill_b2b_csv, "B2B vs B2C Sales GSTR-1 (CSV)"))
            m.add_command(label="📦 Party-Wise ITC (GSTR-2B)", command=lambda: enforce_export(export_drill_itc_csv, "Party-Wise ITC GSTR-2B (CSV)"))
        else:
            m.add_command(label="📄 Main Table (Bill-Wise Details)", command=lambda: enforce_export(export_drill_pdf, "Bill-Wise Details (PDF)"))
            m.add_command(label="📊 HSN Summary (GSTR-1)", command=lambda: enforce_export(export_drill_hsn_pdf, "HSN Summary GSTR-1 (PDF)"))
            m.add_command(label="📈 Tax Slab Summary (GSTR-3B)", command=lambda: enforce_export(export_drill_gstr3b_pdf, "Tax Slab Summary GSTR-3B (PDF)"))
            m.add_separator()
            m.add_command(label="🏢 B2B vs B2C Sales (GSTR-1)", command=lambda: enforce_export(export_drill_b2b_pdf, "B2B vs B2C Sales GSTR-1 (PDF)"))
            m.add_command(label="📦 Party-Wise ITC (GSTR-2B)", command=lambda: enforce_export(export_drill_itc_pdf, "Party-Wise ITC GSTR-2B (PDF)"))
        return m
    # -----------------------------------------------------------

    csv_menu_btn = tk.Menubutton(std_tools, text="📥 Export CSV ▾", font=("Arial", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=3)
    csv_menu_btn.pack(side="right", padx=0)
    csv_menu_btn.config(menu=build_export_menu(csv_menu_btn, "csv"))

    pdf_menu_btn = tk.Menubutton(std_tools, text="🖨 Export PDF ▾", font=("Arial", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=3)
    pdf_menu_btn.pack(side="right", padx=(10, 0))
    pdf_menu_btn.config(menu=build_export_menu(pdf_menu_btn, "pdf"))
    
    bulk_csv_menu_btn = tk.Menubutton(bulk_tools, text="📥 Export CSV ▾", font=("Arial", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=3)
    bulk_csv_menu_btn.pack(side="right", padx=0)
    bulk_csv_menu_btn.config(menu=build_export_menu(bulk_csv_menu_btn, "csv"))

    bulk_pdf_menu_btn = tk.Menubutton(bulk_tools, text="🖨 Export PDF ▾", font=("Arial", 9, "bold"), bg=t["card"], fg=t["text"], relief="solid", bd=1, cursor="hand2", padx=10, pady=3)
    bulk_pdf_menu_btn.pack(side="right", padx=(10, 0))
    bulk_pdf_menu_btn.config(menu=build_export_menu(bulk_pdf_menu_btn, "pdf"))

    def update_bulk_count():
        lbl_bulk_count.config(text=f"{len(selected_iids)} Selected")

    def enable_bulk_mode():
        is_bulk_mode.set(True)
        selected_iids.clear()
        std_tools.pack_forget()
        bulk_tools.pack(side="right", fill="y")
        dtree.heading("sl", text="☑ SELECT")
        update_bulk_count()
        refresh_table(reset_page=False)

    def cancel_bulk_mode():
        is_bulk_mode.set(False)
        selected_iids.clear()
        bulk_tools.pack_forget()
        std_tools.pack(side="right", fill="y")
        dtree.heading("sl", text="SL. NO.")
        refresh_table(reset_page=False)

    def toggle_select_all():
        visible_iids = [child for child in dtree.get_children() if 'empty' not in dtree.item(child, 'tags') and 'header_row' not in dtree.item(child, 'tags')]
        visible_set = set(visible_iids)
        if visible_set.issubset(selected_iids) and visible_set:
            selected_iids -= visible_set
        else:
            selected_iids |= visible_set
        update_bulk_count()
        refresh_table(reset_page=False)
        
    btn_select_all.config(command=toggle_select_all)
    btn_bulk_cancel.config(command=cancel_bulk_mode)

    pag_state = {"current": 1, "total": 1, "per_page": 50}
    
    pag_frame = tk.Frame(pop, bg=t["bg"])
    pag_frame.pack(side="bottom", fill="x", pady=(0, 15))
    
    center_pag = tk.Frame(pag_frame, bg=t["bg"])
    center_pag.pack(anchor="center")
    
    btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", padx=12, pady=3)
    btn_prev.pack(side="left", padx=5)
    
    lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=t["bg"], fg=t["sec"])
    lbl_page.pack(side="left", padx=15)
    
    btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", padx=12, pady=3)
    btn_next.pack(side="left", padx=5)
    
    def go_prev():
        if pag_state["current"] > 1:
            pag_state["current"] -= 1
            refresh_table(reset_page=False)
            
    def go_next():
        if pag_state["current"] < pag_state["total"]:
            pag_state["current"] += 1
            refresh_table(reset_page=False)
            
    btn_prev.config(command=go_prev)
    btn_next.config(command=go_next)

    table_f = tk.Frame(pop, bg=t["bg"], padx=20, pady=15)
    table_f.pack(fill="both", expand=True)

    # --- THE FIX: Custom thick, flat scrollbars for GST Drilldown ---
    scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="GST.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="GST.Horizontal.TScrollbar")
    # ----------------------------------------------------------------
    
    cols = ("sl", "date", "type", "inv_num", "customer", "gstin", "taxable", "gst", "ca_status", "ghost")
    dtree = ttk.Treeview(table_f, columns=cols, show="headings", style="GST.Treeview", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    
    scroll_y.config(command=dtree.yview)
    scroll_x.config(command=dtree.xview)
    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    dtree.pack(side="left", fill="both", expand=True)

    def _drill_scroll_y(event):
        import os
        delta = int(-1 * (event.delta / 120)) if os.name == 'nt' else int(-1 * event.delta)
        dtree.yview_scroll(delta, "units")
        return "break"
        
    def _drill_scroll_x(event):
        import os
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        dtree.xview_moveto(dtree.xview()[0] + (delta * 0.015))
        return "break"

    dtree.bind("<MouseWheel>", _drill_scroll_y)
    dtree.bind("<Shift-MouseWheel>", _drill_scroll_x)

    dtree.heading("sl", text="SL. NO.", anchor="center")
    dtree.heading("date", text="DATE", anchor="w")
    dtree.heading("type", text="TRANSACTION TYPE", anchor="w")
    dtree.heading("inv_num", text="INVOICE / BILL NO.", anchor="w")
    dtree.heading("customer", text="PARTY NAME", anchor="w")
    dtree.heading("gstin", text="GSTIN", anchor="center")
    dtree.heading("taxable", text="TOTAL TAXABLE VALUE", anchor="e")
    dtree.heading("gst", text="TOTAL GST AMOUNT", anchor="e")
    dtree.heading("ca_status", text="STATUS", anchor="center")
    dtree.heading("ghost", text="")

    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"gst_drill_cols_{comp_id}",))
        res = c.fetchone()
        conn.close()
        saved_d_w = json.loads(res[0]) if res and res[0] else {}
    except:
        saved_d_w = {}

    dtree.column("sl", width=saved_d_w.get("sl", 60), minwidth=40, anchor="center", stretch=False)
    dtree.column("date", width=saved_d_w.get("date", 100), minwidth=60, anchor="w", stretch=False)
    dtree.column("type", width=saved_d_w.get("type", 140), minwidth=80, anchor="w", stretch=False)
    dtree.column("inv_num", width=saved_d_w.get("inv_num", 140), minwidth=80, anchor="w", stretch=False)
    dtree.column("customer", width=saved_d_w.get("customer", 180), minwidth=100, anchor="w", stretch=False)
    dtree.column("gstin", width=saved_d_w.get("gstin", 140), minwidth=80, anchor="center", stretch=False)
    dtree.column("taxable", width=saved_d_w.get("taxable", 140), minwidth=80, anchor="e", stretch=False)
    dtree.column("gst", width=saved_d_w.get("gst", 140), minwidth=80, anchor="e", stretch=False)
    dtree.column("ca_status", width=saved_d_w.get("ca_status", 120), minwidth=80, anchor="center", stretch=False)
    dtree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_drill_widths():
        new_w = {c: dtree.column(c, "width") for c in dtree["columns"] if c != "ghost"}
        try:
            database.save_ui_setting(f"gst_drill_cols_{comp_id}", json.dumps(new_w))
        except: pass

    def on_drill_sep_drag(event):
        if dtree.identify_region(event.x, event.y) == "separator":
            pop.after(50, save_drill_widths)

    dtree.bind("<B1-Motion>", on_drill_sep_drag, add="+")
    dtree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_drill_widths) if dtree.identify_region(e.x, e.y) == "separator" else None, add="+")

    dtree.tag_configure("evenrow", background=t["bg"]) 
    dtree.tag_configure("oddrow", background=t["card"])  
    dtree.tag_configure("sale_row", foreground=t["accent_blue"])
    dtree.tag_configure("purch_row", foreground=t["accent_green"])
    # --- THE FIX: Changed foreground to standard text color for high contrast readability ---
    dtree.tag_configure("header_row", background=t["border"], foreground=t["text"], font=("Arial", 11, "bold"))
    # --------------------------------------------------------------------------------------

    master_data_list = []
    
    try:
        conn = database.get_connection()
        c = conn.cursor()
        
        c.execute("""
            SELECT i.invoice_date, i.invoice_number, i.customer_name, i.subtotal, (COALESCE(i.cgst,0) + COALESCE(i.sgst,0) + COALESCE(i.igst,0)) as total_gst, c.gstin, i.id, COALESCE(i.ca_submitted, 0), COALESCE(i.ca_submission_date, ''), i.place_of_service
            FROM invoices i
            LEFT JOIN customers c ON i.customer_name = c.name AND i.company_id = c.company_id
            WHERE i.company_id=? AND COALESCE(i.is_deleted, 0) = 0 AND LOWER(COALESCE(i.status, '')) != 'draft'
        """, (comp_id,))
        
        for row in c.fetchall():
            dt = parse_date(row[0])
            if not dt: dt = date.today()
            if get_period_key(dt, period_mode_val) == period_key:
                gstin = row[5] if row[5] and str(row[5]).strip() else "Unregistered"
                
                sub_t = safe_float(row[3])
                place_str = str(row[9]) if len(row) > 9 else ""
                disc_amt = 0.0
                disc_m = re.search(r'@@DISC@@(.*?)@@', place_str + "@@")
                if disc_m:
                    parts = disc_m.group(1).split('||')
                    if len(parts) > 2 and str(parts[0]) == '1':
                        try:
                            d_val = safe_float(parts[1])
                            if parts[2] == '%': disc_amt = sub_t * (d_val / 100.0)
                            else: disc_amt = d_val
                        except: pass
                true_taxable = sub_t - disc_amt if (sub_t - disc_amt) > 0 else 0.0
                
                master_data_list.append((dt, row[0], "OUTPUT GST (Sale)", row[1], row[2], gstin, true_taxable, safe_float(row[4]), row[6], row[7], row[8]))

        c.execute("""
            SELECT p.purchase_date, p.bill_number, p.vendor_name, p.subtotal, (COALESCE(p.cgst,0) + COALESCE(p.sgst,0) + COALESCE(p.igst,0)) as total_gst, c.gstin, p.id, COALESCE(p.ca_submitted, 0), COALESCE(p.ca_submission_date, '')
            FROM purchases p
            LEFT JOIN customers c ON p.vendor_name = c.name AND p.company_id = c.company_id
            WHERE p.company_id=? AND COALESCE(p.is_deleted, 0) = 0 AND COALESCE(p.is_draft, 0) = 0 AND LOWER(COALESCE(p.status, '')) != 'draft'
        """, (comp_id,))
        
        for row in c.fetchall():
            dt = parse_date(row[0])
            if not dt: dt = date.today()
            if get_period_key(dt, period_mode_val) == period_key:
                gstin = row[5] if row[5] and str(row[5]).strip() else "Unregistered"
                master_data_list.append((dt, row[0], "INPUT GST (Purchase)", row[1], row[2], gstin, safe_float(row[3]), safe_float(row[4]), row[6], row[7], row[8]))

        conn.close()
    except Exception as e:
        print("Drilldown Error:", e)

    master_data_list.sort(key=lambda x: x[0], reverse=True)

    def refresh_table(reset_page=False):
        if reset_page:
            pag_state["current"] = 1
            
        row_map.clear()
        try:
            for item in dtree.get_children(): dtree.delete(item)
            
            s_term = search_var.get().lower().strip()
            f_val = filter_var.get()
            
            filtered_list = []
            for row in master_data_list:
                if f_val == "Invoice Voucher" and "OUTPUT" not in row[2]: continue
                if f_val == "Purchase Voucher" and "INPUT" not in row[2]: continue
                if f_val == "Submitted" and row[9] != 1: continue
                if f_val == "Pending" and row[9] == 1: continue
                
                if s_term:
                    search_string = f"{row[3]} {row[4]}".lower()
                    if s_term not in search_string:
                        continue
                        
                filtered_list.append(row)
                unique_id = f"{row[8]}_{row[2]}" 
                row_map[unique_id] = (row[8], row[2], row[9])

            total_items = len(filtered_list)
            pag_state["total"] = max(1, (total_items + pag_state["per_page"] - 1) // pag_state["per_page"])
            if pag_state["current"] > pag_state["total"]: pag_state["current"] = max(1, pag_state["total"])
            
            lbl_page.config(text=f"Page {pag_state['current']} of {pag_state['total']}")
            btn_prev.config(state="normal" if pag_state["current"] > 1 else "disabled", bg=t["card"] if pag_state["current"] > 1 else t["bg"])
            btn_next.config(state="normal" if pag_state["current"] < pag_state["total"] else "disabled", bg=t["card"] if pag_state["current"] < pag_state["total"] else t["bg"])
            
            start_idx = (pag_state["current"] - 1) * pag_state["per_page"]
            page_items = filtered_list[start_idx : start_idx + pag_state["per_page"]]

            if not page_items:
                dtree.insert("", "end", values=("", "No transactions found matching your filters.", "", "", "", "", "", "", "", ""), tags=("evenrow", "empty"))
                for i in range(1, pag_state["per_page"]):
                    tag = "evenrow" if i % 2 == 0 else "oddrow"
                    dtree.insert("", "end", values=("", "", "", "", "", "", "", "", "", ""), tags=(tag, "empty"))
            else:
                current_month_str = None
                for index, row in enumerate(page_items):
                    if period_mode_val in ["Annual", "Quarterly"]:
                        dt_obj = row[0]
                        month_name = dt_obj.strftime("%B, %Y").upper()
                        if month_name != current_month_str:
                            dtree.insert("", "end", values=("", f"🗓 {month_name}", "", "", "", "", "", "", "", ""), tags=("header_row", "empty"))
                            current_month_str = month_name

                    bg_tag = "evenrow" if index % 2 == 0 else "oddrow"
                    fg_tag = "sale_row" if "Sale" in row[2] else "purch_row"
                    
                    formatted_date = smart_date_formatter(row[1], date_fmt_code)
                    
                    if row[9]:
                        sub_date_raw = str(row[10]).strip()
                        if sub_date_raw:
                            parts = sub_date_raw.split('||')
                            fmt_sub_date = smart_date_formatter(parts[0], date_fmt_code)
                            ca_text = f"✅ Submitted on {fmt_sub_date}"
                            if len(parts) > 1 and parts[1]: ca_text += f" via {parts[1]}"
                        else: ca_text = "✅ Submitted"
                    else: ca_text = "📤 Pending"
                    
                    unique_id = f"{row[8]}_{row[2]}" 
                    
                    if is_bulk_mode.get():
                        sl_val = "[✓]" if unique_id in selected_iids else "[  ]"
                    else:
                        sl_val = start_idx + index + 1
                    
                    dtree.insert("", "end", iid=unique_id, values=(
                        sl_val,
                        formatted_date,
                        row[2],
                        row[3],
                        row[4],
                        row[5],
                        format_currency(row[6], curr_fmt),
                        format_currency(row[7], curr_fmt),
                        ca_text,
                        ""
                    ), tags=(bg_tag, fg_tag))
                    
                for i in range(len(page_items), pag_state["per_page"]):
                    tag = "evenrow" if i % 2 == 0 else "oddrow"
                    dtree.insert("", "end", values=("", "", "", "", "", "", "", "", "", ""), tags=(tag, "empty"))
            
            dtree.yview_moveto(0)
        except Exception as e:
            print("Table Refresh Error:", e)

    search_var.trace_add("write", lambda *args: refresh_table(reset_page=True))
    refresh_table(reset_page=True)

    def on_dtree_click(event):
        region = dtree.identify("region", event.x, event.y)
        if region == "cell":
            col = dtree.identify_column(event.x)
            iid = dtree.identify_row(event.y)
            
            if iid and "empty" not in dtree.item(iid, "tags") and "header_row" not in dtree.item(iid, "tags"):
                if col == "#9":
                    db_id, t_type, current_status = row_map.get(iid, (None, None, None))
                    if db_id is not None:
                        # --- THE FIX: Secure Roles & Auditing ---
                        app = pop.winfo_toplevel()
                        uid = int(getattr(app, 'current_user_id', 1))
                        is_admin = str(uid) == "1"
                        if not is_admin:
                            u_row = database.get_user_by_id(uid)
                            if u_row and u_row[3] == "Admin": is_admin = True
                        
                        perms = database.get_user_permissions(uid)
                        gst_rules = perms.get("gst_rules", {})
                        inv_num_val = str(dtree.item(iid, "values")[3])
                        # ----------------------------------------
                        
                        if current_status:
                            if not is_admin and gst_rules.get("lock_ca_undo", False):
                                messagebox.showwarning("Access Restricted", "Reversing CA submissions is locked for your account.\n\nPlease contact the Admin.", parent=pop)
                                return
                                
                            if not messagebox.askyesno("Confirm Action", "Are you sure you want to Undo this submission?", parent=pop): return
                            try:
                                database.toggle_ca_status(t_type, db_id, 0, "", comp_id)
                                database.log_audit("GST Report", "CA Status Reversed", inv_num_val, f"Unlocked bill (Removed CA Submitted status).", 0.0, company_id=comp_id)
                                for i, r in enumerate(master_data_list):
                                    if r[8] == db_id and r[2] == t_type:
                                        lst = list(r)
                                        lst[9] = 0; lst[10] = ""
                                        master_data_list[i] = tuple(lst)
                                        break
                                refresh_table(reset_page=False)
                            except Exception as e: messagebox.showerror("Database Error", str(e), parent=pop)
                        else:
                            if not is_admin and gst_rules.get("lock_ca_submit", False):
                                messagebox.showwarning("Access Restricted", "Marking bills as 'Submitted to CA' is locked for your account.\n\nPlease contact the Admin.", parent=pop)
                                return
                                
                            sub_pop = tk.Toplevel(pop)
                            sub_pop.title("Submit to CA")
                            sub_pop.geometry("420x360")
                            sub_pop.configure(bg=t["bg"])
                            sub_pop.grab_set()
                            
                            sub_pop.update_idletasks()
                            sw, sh = sub_pop.winfo_screenwidth(), sub_pop.winfo_screenheight()
                            sub_pop.geometry(f"+{int((sw/2)-(420/2))}+{int((sh/2)-(360/2))}")
                            
                            header = tk.Frame(sub_pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
                            header.pack(fill="x", pady=(0, 15))
                            tk.Label(header, text="Mark Bill as Submitted", font=("Arial", 14, "bold"), bg=t["card"], fg=t["text"]).pack(pady=15)
                            
                            scroll_container = tk.Frame(sub_pop, bg=t["bg"])
                            scroll_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
                            
                            canvas = tk.Canvas(scroll_container, bg=t["bg"], highlightthickness=0)
                            scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
                            f = tk.Frame(canvas, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
                            
                            f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                            canvas_window = canvas.create_window((0, 0), window=f, anchor="nw")
                            
                            def configure_canvas(event):
                                canvas.itemconfig(canvas_window, width=event.width)
                            canvas.bind("<Configure>", configure_canvas)
                            
                            canvas.configure(yscrollcommand=scrollbar.set)
                            canvas.pack(side="left", fill="both", expand=True)
                            scrollbar.pack(side="right", fill="y")
                            
                            def _on_mousewheel(event):
                                if not canvas.winfo_exists(): return
                                w_class = event.widget.winfo_class()
                                if w_class == 'TCombobox': return
                                delta = int(-1 * (event.delta / 120)) if os.name == 'nt' else int(-1 * event.delta)
                                canvas.yview_scroll(delta, "units")
                                
                            canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
                            canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
                            sub_pop.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"), add="+")
                            
                            tk.Label(f, text="Submission Date:", font=("Arial", 9, "bold"), bg=t["card"], fg=t["sec"]).pack(anchor="w", padx=15, pady=(15, 2))
                            
                            date_frame = tk.Frame(f, bg=t["card"])
                            date_frame.pack(fill="x", padx=15)
                            
                            default_date = smart_date_formatter(str(date.today()), date_fmt_code)
                            date_var = tk.StringVar(value=default_date)
                            e_date = tk.Entry(date_frame, textvariable=date_var, font=("Arial", 11), bg=t["bg"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
                            e_date.pack(side="left", fill="x", expand=True, ipady=4)
                            
                            btn_cal = tk.Button(date_frame, text="📅", font=("Arial", 11), bg=t["card"], fg=t["text"], cursor="hand2", relief="flat", command=lambda: NativeCalendar(sub_pop, date_var, anchor_widget=e_date))
                            btn_cal.pack(side="left", padx=(5, 0))
                            
                            tk.Label(f, text="Submission Mode:", font=("Arial", 9, "bold"), bg=t["card"], fg=t["sec"]).pack(anchor="w", padx=15, pady=(15, 2))
                            mode_var = tk.StringVar(value="WhatsApp")
                            cb_mode = ttk.Combobox(f, textvariable=mode_var, values=["WhatsApp", "Email", "Portal Upload", "Physical Copy", "Other"], state="readonly", font=("Arial", 11), style="GST.TCombobox")
                            cb_mode.pack(fill="x", padx=15, ipady=4)
                            cb_mode.bind("<MouseWheel>", lambda e: "break")
                            
                            def confirm_submission():
                                d_val = date_var.get().strip()
                                m_val = mode_var.get().strip()
                                if not d_val: return
                                
                                combo_str = f"{d_val}||{m_val}"
                                try:
                                    database.toggle_ca_status(t_type, db_id, 1, combo_str, comp_id)
                                    database.log_audit("GST Report", "CA Status Locked", inv_num_val, f"Marked bill as 'Submitted to CA' via {m_val}.", 0.0, company_id=comp_id)
                                    for i, r in enumerate(master_data_list):
                                        if r[8] == db_id and r[2] == t_type:
                                            lst = list(r)
                                            lst[9] = 1; lst[10] = combo_str
                                            master_data_list[i] = tuple(lst)
                                            break
                                    refresh_table(reset_page=False)
                                    sub_pop.destroy()
                                except Exception as e: messagebox.showerror("Database Error", str(e), parent=sub_pop)
                                    
                            btn_submit = tk.Button(f, text="Save & Mark Submitted", font=("Arial", 10, "bold"), bg=t["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", command=confirm_submission)
                            btn_submit.pack(fill="x", padx=15, pady=(20, 15), ipady=4)
                            cb_mode.bind("<FocusIn>", lambda e: sub_pop.after(10, cb_mode.selection_clear))
                            e_date.focus_set()
                            
                elif is_bulk_mode.get():
                    if iid in selected_iids:
                        selected_iids.remove(iid)
                    else:
                        selected_iids.add(iid)
                        
                    vals = list(dtree.item(iid, "values"))
                    vals[0] = "[✓]" if iid in selected_iids else "[  ]"
                    dtree.item(iid, values=vals)
                    update_bulk_count()
                
    dtree.bind("<ButtonRelease-1>", on_dtree_click, add="+")

    def trigger_single_export(iid, event):
        pop.single_export_iid = iid
        menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=t["card"], fg=t["text"])
        
        menu.add_cascade(label="🖨 Export as PDF", menu=build_export_menu(menu, "pdf"))
        menu.add_cascade(label="📥 Export as CSV", menu=build_export_menu(menu, "csv"))
        
        menu.tk_popup(event.x_root, event.y_root)

    def on_right_click(event):
        iid = dtree.identify_row(event.y)
        if not iid or 'empty' in dtree.item(iid, 'tags') or 'header_row' in dtree.item(iid, 'tags'): return
        
        dtree.selection_set(iid)
        menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=t["card"], fg=t["text"])
        
        if not is_bulk_mode.get():
            menu.add_command(label="📄 Export This Bill", command=lambda: trigger_single_export(iid, event))
            menu.add_separator()
            menu.add_command(label="☑️ Bulk Export", command=enable_bulk_mode)
        else:
            menu.add_command(label="❌ Cancel Bulk Selection", command=cancel_bulk_mode)
            
        menu.tk_popup(event.x_root, event.y_root)

    dtree.bind("<Button-3>", on_right_click)

    def prevent_empty_select_drill(event):
        for iid in dtree.selection():
            if 'empty' in dtree.item(iid, 'tags') or 'header_row' in dtree.item(iid, 'tags'):
                dtree.selection_remove(iid)
    dtree.bind("<<TreeviewSelect>>", prevent_empty_select_drill)
    
    def on_drill_motion(event):
        region = dtree.identify("region", event.x, event.y)
        if region == "cell": 
            iid = dtree.identify_row(event.y)
            col = dtree.identify_column(event.x)
            if iid and 'empty' not in dtree.item(iid, 'tags') and 'header_row' not in dtree.item(iid, 'tags'):
                if col == "#9" or (is_bulk_mode.get() and col == "#1"):
                    dtree.config(cursor="hand2")
                else: dtree.config(cursor="")
            else: dtree.config(cursor="")
        else: dtree.config(cursor="")
            
    dtree.bind("<Motion>", on_drill_motion, add="+")