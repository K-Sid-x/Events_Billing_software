import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import sys
import tempfile
import webbrowser
import re
import json

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import number_to_words, unpack_db_place_string

def export_to_csv(view):
    # --- THE FIX: Filter out the dummy padding rows ---
    valid_items = [item for item in view.tree.get_children() if 'dummy' not in view.tree.item(item, 'tags')]
    
    if not valid_items:
        messagebox.showinfo("Empty", "No data to export.", parent=view)
        return
        
    file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export Invoices")
    if not file_path: return
    
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # --- THE FIX: Dynamically fetch real headers & strip the ghost column! ---
            real_cols = [c for c in view.tree["columns"] if c != "ghost"]
            headers = [view.tree.heading(c)["text"] for c in real_cols]
            writer.writerow(headers)
            
            for item in valid_items:
                row = view.tree.item(item)['values']
                clean_row = row[:len(real_cols)]
                writer.writerow(clean_row) 
            # -------------------------------------------------------------------------
            
        messagebox.showinfo("Success", f"Data exported successfully to:\n{file_path}", parent=view)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export data:\n{str(e)}", parent=view)

def export_to_pdf(view):
    # --- THE FIX: Filter out the dummy padding rows ---
    valid_items = [item for item in view.tree.get_children() if 'dummy' not in view.tree.item(item, 'tags')]
    
    if not valid_items:
        messagebox.showinfo("Empty", "No data to export.", parent=view)
        return

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            /* --- THE FIX: Added landscape mode and white-space: nowrap --- */
            @page { size: landscape; }
            body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
            h2 { color: #1e3a8a; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #cbd5e1; padding: 10px; text-align: left; white-space: nowrap; }
            th { background-color: #f1f5f9; font-weight: bold; color: #0f172a; }
            .right { text-align: right; }
            .center { text-align: center; }
        </style>
    </head>
    <body>
        <h2>Invoice Report</h2>
        <table>
            <thead>
                <tr>
    """
    # --- THE FIX: Strip the ghost column out of the PDF Headers and Data Rows! ---
    valid_cols = [c for c in view.tree["columns"] if c != "ghost"]
    for col in valid_cols: 
        html += f"<th>{view.tree.heading(col)['text']}</th>"
    html += "</tr></thead><tbody>"
    
    for item in valid_items:
        row = view.tree.item(item)['values']
        html += "<tr>"
        for i in range(len(valid_cols)):
            val = row[i] if i < len(row) else ""
            # --- THE FIX: Aligned Subtotal(4), GST(5), Total(6), TDS(7) to Right, and Status(8) to Center ---
            align = 'class="right"' if i in [4,5,6,7] else 'class="center"' if i in [0,8] else ""
            html += f"<td {align}>{val}</td>"
        html += "</tr>"
    # -----------------------------------------------------------------------------
        
    html += "</tbody></table><script>window.onload=function(){window.print();}</script></body></html>"
    
    # --- THE FIX: Tagged prefix so the Main.py Sweeper can delete it ---
    fd, path = tempfile.mkstemp(suffix=".html", prefix="Invoice_Report_")
    # -------------------------------------------------------------------
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
    webbrowser.open('file://' + os.path.realpath(path))

def show_preview_from_db(view, inv_id):
    inv, items = database.get_invoice_by_id(inv_id)
    if not inv: return
    
    comp_id = getattr(view.winfo_toplevel(), "active_company_id", 1)
    
    inv_data = {
        "date": inv[1], "inv_date": inv[1], "del_date": inv[2], "inv_num": inv[3], "cust_name": inv[4],
        "place": inv[5], "subtotal": inv[6], "cgst": inv[7], "sgst": inv[8], 
        "igst": inv[9], "total": inv[10],
        "cust_id": inv[17] if len(inv) > 17 else None  # --- THE FIX: Pass customer_id to preview ---
    }
    
    # --- THE FIX: Direct secure SQL replacing database.get_all_inventory() ---
    inv_dict = {}
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT item_name, unit FROM inventory WHERE company_id=?", (comp_id,))
        for i_row in c.fetchall():
            name = i_row[0] if len(i_row) > 0 else ""
            raw_unit = str(i_row[1]) if len(i_row) > 1 and i_row[1] else ""
            
            # --- THE FIX: Extract short format and obliterate '--Select--' for Live Preview ---
            short_unit = raw_unit.split("(")[-1].replace(")", "").strip() if "(" in raw_unit else raw_unit
            if short_unit.lower() in ["--select--", "none", "null"]:
                short_unit = ""
            inv_dict[name] = short_unit
        conn.close()
    except: pass
    # -------------------------------------------------------------------------

    def _clean_num(val):
        try:
            v = float(val)
            return str(int(v)) if v.is_integer() else str(v)
        except: return str(val)
    
    items_d = []
    current_sl = 1
    for i in items:
        raw_days = str(i[4]).strip()
        if not raw_days or raw_days in ["0.0", "0", "None"]:
            raw_days = ""
            
        item_name = str(i[0])
        
        # --- THE TRICK: Detect the invisible marker for voided rows! ---
        is_voided = False
        if item_name.startswith("\u200b"):
            is_voided = True
            item_name = item_name.replace("\u200b", "")
        # ---------------------------------------------------------------
        
        raw_qty = str(i[3]).strip()
        if not raw_qty or raw_qty in ["0.0", "0", "None"]:
            clean_qty = ""
        else:
            clean_qty = _clean_num(raw_qty)
            
        # Pass a blank space " " so the print template leaves the cell empty instead of forcing a 1
        clean_days = _clean_num(raw_days) if raw_days else " "
        
        # --- THE FIX: Strictly trust the Database unit (even if user left it completely blank) ---
        if len(i) > 6:
            unit_val = str(i[6]).strip() if i[6] is not None else ""
        else:
            unit_val = inv_dict.get(item_name, "")
            
        if unit_val.lower() in ["none", "--select--", "null"]: unit_val = ""
        
        display_qty = f"{clean_qty} {unit_val}".strip() if f"{clean_qty} {unit_val}".strip() else " "
            
        # --- THE FIX: Upgraded Regex to flawlessly capture negative rates for Print Previews ---
        try: r_val = float(re.search(r'[-+]?\d*\.?\d+', str(i[2])).group())
        except: r_val = 0.0
        
        try: 
            q_val = float(re.search(r'[-+]?\d*\.?\d+', str(i[3])).group()) if str(i[3]).strip() and str(i[3]).strip() not in ["0.0", "0", "None"] else 1.0
        except: q_val = 1.0
        
        try: 
            d_val = float(re.search(r'[-+]?\d*\.?\d+', raw_days).group()) if raw_days else 1.0
        except: d_val = 1.0
        
        correct_amt = r_val * q_val * d_val
        
        # --- THE FIX: Assign blank Sl. No. to voided rows, sequential to valid rows ---
        if is_voided:
            display_sl = ""
        else:
            display_sl = str(current_sl)
            current_sl += 1
        # ------------------------------------------------------------------------------
        
        items_d.append({
            "idx": display_sl,
            "data": {
                "name": item_name, 
                "hsn": i[1], 
                "rate": i[2], 
                "qty": display_qty, 
                "days": clean_days, 
                "amt": f"{correct_amt:.2f}"
            }
        })
        
    render_preview_window(view, inv_data, items_d)

def render_preview_window(view, inv_data, items_data):
    app = view.winfo_toplevel()
    comp_id = getattr(app, "active_company_id", 1)
    
    if not comp_id: comp_id = 1
    comp = database.get_company(comp_id)
    if not comp: comp = database.get_company(1)
    
    c_name = comp[1] if comp else "COMPANY NAME"
    c_name_sec = comp[2] if comp else ""
    c_addr = comp[3] if comp else "Address"
    p1 = comp[4] if comp else ""
    p2 = comp[5] if comp and len(comp) > 5 else ""
    p3 = comp[6] if comp and len(comp) > 6 else ""
    c_email = comp[7] if comp else ""
    c_gst = comp[9] if comp else ""
    logo_path = comp[10] if comp else ""
    layout = comp[11] if comp else "Classic"
    logo_size = comp[12] if comp else 120
    logo_shape = comp[13] if comp and len(comp) > 13 else "Square"

    # --- THE FIX: Use a newline character instead of a pipe so phones stack vertically! ---
    valid_phones = [str(p) for p in [p1, p2, p3] if p and str(p).strip()]
    c_phone = "\n".join(valid_phones) if valid_phones else "Phone"
    # ------------------------------------------------------------------------------------

    # --- THE FIX: Fetch print details strictly by ID to prevent crossover! ---
    cust = None
    try:
        conn = database.get_connection()
        c = conn.cursor()
        if inv_data.get("cust_id"):
            c.execute("SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE company_id=? AND id=?", (comp_id, inv_data.get("cust_id")))
        else:
            c.execute("SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE company_id=? AND name=?", (comp_id, inv_data.get("cust_name", "")))
        cust = c.fetchone()
        conn.close()
    except: pass
    # -------------------------------------------------------------------------
    
    c_a = ""
    c_p = ""
    
    if cust:
        raw_addr = str(cust[5]) if len(cust) > 5 and cust[5] else ""
        if raw_addr.strip().startswith("{"):
            try:
                j_addr = json.loads(raw_addr)
                c_a = j_addr.get("address", "") or ""
            except: c_a = raw_addr
        else:
            c_a = raw_addr or ""
            
        raw_p = str(cust[2]) if cust[2] and str(cust[2]) != "None" else ""
        c_p = re.sub(r'Mobile:\s*', '', raw_p, flags=re.IGNORECASE).split(',')[0].strip()
        
        cust_id_str = str(cust[0])
        prefs = getattr(app, 'customer_phone_prefs', {})
        if cust_id_str in prefs:
            c_p = prefs[cust_id_str]

    inv_data["cust_addr"] = c_a
    
    # --- THE FIX: Leave GST blank instead of injecting a placeholder ---
    raw_gst = cust[3] if cust else ""
    inv_data["cust_gst"] = raw_gst if raw_gst and str(raw_gst).lower() not in ["none", "null", "n/a", "na"] else ""
    # -----------------------------------------------------------------
    inv_data["cust_phone"] = c_p 
    inv_data["words"] = number_to_words(inv_data.get("total", 0))

    raw_place = inv_data.get("place", "")
    
    if "@@SERV@@" in raw_place or "@@BANK@@" in raw_place:
        banks_data = unpack_db_place_string(raw_place, inv_data)
    else:
        banks_data = []
        inv_data["serv_name"] = inv_data.get("cust_name", "")
        inv_data["serv_addr"] = inv_data.get("cust_addr", "")
        inv_data["serv_del_date"] = inv_data.get("del_date", "")
        inv_data["serv_bill_date"] = inv_data.get("date", "")
        inv_data["eway_bill"] = "-"
        inv_data["subject_text"] = ""
        
    # --- THE FIX: Reverse Engineer Tax Rates for Live Preview ---
    try:
        sub = float(inv_data.get("subtotal", 0.0))
        disc = float(inv_data.get("discount_amt", 0.0))
        taxable = sub - disc
        
        cgst_amt = float(inv_data.get("cgst", 0.0))
        igst_amt = float(inv_data.get("igst", 0.0))
        
        if taxable > 0:
            if igst_amt > 0:
                r = round((igst_amt / taxable) * 100, 2)
                inv_data["igst_rate"] = str(int(r) if r.is_integer() else r)
                inv_data["cgst_rate"] = "0"
                inv_data["sgst_rate"] = "0"
            else:
                r = round((cgst_amt / taxable) * 100, 2)
                val = str(int(r) if r.is_integer() else r)
                inv_data["cgst_rate"] = val
                inv_data["sgst_rate"] = val
                inv_data["igst_rate"] = "0"
        else:
            inv_data["cgst_rate"] = "9"
            inv_data["sgst_rate"] = "9"
            inv_data["igst_rate"] = "18"
    except:
        pass
    # ------------------------------------------------------------

    comp_dict = {"name": c_name, "name_sec": c_name_sec, "addr": c_addr, "phone": c_phone, "email": c_email, "gst": c_gst}
    
    try: full_settings = json.loads(comp[14]) if comp and len(comp) > 14 and comp[14] else {}
    except: full_settings = {}
        
    for k in ["fonts", "colors", "bolds", "col_widths"]:
        if k not in full_settings: full_settings[k] = {}

    full_settings["logo_path"] = logo_path
    full_settings["logo_size"] = logo_size
    full_settings["logo_shape"] = logo_shape
    full_settings["layout"] = layout

    try: 
        from utils.print_studio import PrintStudio
        PrintStudio(view.winfo_toplevel(), inv_data, items_data, comp_dict, banks_data, full_settings)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load Print Studio:\n{e}")