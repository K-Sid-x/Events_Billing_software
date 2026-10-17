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
        for i, col_id in enumerate(valid_cols):
            val = row[i] if i < len(row) else ""
            # --- THE FIX: Align by column ID so both GST and Non-GST layouts align accurately ---
            align = 'class="right"' if col_id in ("subtotal", "gst", "total", "tds") else 'class="center"' if col_id in ("sl_no", "status") else ""
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
    
    # --- THE FIX: Decouple the Subject and Place of Service! ---
    raw_place = inv[5]
    final_place = ""
    final_subj = ""
    
    # --- THE FIX: Explicitly extract Discount and Advance for Saved Previews! ---
    inc_disc = 0
    disc_val = "0"
    disc_typ = "%"
    inc_adv = 0
    adv_val = "0"

    if raw_place:
        import re
        m_serv = re.search(r'@@SERV@@(.*?)@@', raw_place + "@@", re.DOTALL)
        if m_serv:
            parts = m_serv.group(1).split('||')
            if len(parts) > 1: final_place = parts[1].strip()
        elif not raw_place.startswith("@@"):
            final_place = raw_place.strip()

        m_subj = re.search(r'@@SUBJ@@(.*?)@@', raw_place + "@@", re.DOTALL)
        if m_subj:
            subj_parts = m_subj.group(1).split('||')
            if len(subj_parts) > 0: final_subj = subj_parts[0].strip()
            if len(subj_parts) > 1: final_subj_align = subj_parts[1].strip()
            
        m_disc = re.search(r'@@DISC@@(.*?)@@', raw_place + "@@")
        if m_disc:
            d_parts = m_disc.group(1).split('||')
            if len(d_parts) > 0 and d_parts[0].strip().isdigit(): inc_disc = int(d_parts[0].strip())
            if len(d_parts) > 1: disc_val = d_parts[1].strip()
            if len(d_parts) > 2: disc_typ = d_parts[2].strip()
            
        m_adv = re.search(r'@@ADV@@(.*?)@@', raw_place + "@@")
        if m_adv:
            a_parts = m_adv.group(1).split('||')
            if len(a_parts) > 0 and a_parts[0].strip().isdigit(): inc_adv = int(a_parts[0].strip())
            if len(a_parts) > 1: adv_val = a_parts[1].strip()

    inv_data = {
        "date": inv[1], "inv_date": inv[1], "del_date": inv[2], "inv_num": inv[3], "cust_name": inv[4],
        "place": final_place, "subject": final_subj, "subtotal": inv[6], "cgst": inv[7], "sgst": inv[8], 
        "igst": inv[9], "total": inv[10],
        "cust_id": inv[17] if len(inv) > 17 else None,
        "inc_discount": inc_disc,
        "discount_val": disc_val,
        "discount_type": disc_typ,
        "inc_advance": inc_adv,
        "advance_val": adv_val,
        "raw_place_full": inv[5]
    }
    # ----------------------------------------------------------------------------
    
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

    # --- THE FIX: We MUST use the fully intact packed string to extract Banks and Terms! ---
    raw_place = inv_data.get("raw_place_full", inv_data.get("place", ""))
    # ---------------------------------------------------------------------------------------
    
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
        
    # --- THE FIX: Calculate missing absolute discount amount for Saved Invoices! ---
    try:
        if str(inv_data.get("inc_discount", "0")) == "1":
            sub_t = float(inv_data.get("subtotal", 0.0))
            d_val = float(inv_data.get("discount_val", 0.0))
            if "%" in str(inv_data.get("discount_type", "%")):
                inv_data["discount_amt"] = sub_t * (d_val / 100.0)
            else:
                inv_data["discount_amt"] = d_val
        else:
            inv_data["discount_amt"] = 0.0
    except Exception:
        inv_data["discount_amt"] = 0.0
    # -------------------------------------------------------------------------------
        
    # --- THE FIX: Bulletproof Tax Rate Snapping ---
    try:
        sub = float(inv_data.get("subtotal", 0.0))
        disc = float(inv_data.get("discount_amt", 0.0))
        taxable = sub - disc
        
        cgst_amt = float(inv_data.get("cgst", 0.0))
        igst_amt = float(inv_data.get("igst", 0.0))
        
        def snap_rate(calculated_rate, is_igst=False):
            # Indian GST standard rates
            valid_rates = [0, 5, 12, 18, 28] if is_igst else [0, 2.5, 6, 9, 14]
            return min(valid_rates, key=lambda x: abs(x - calculated_rate))

        if taxable > 0:
            if igst_amt > 0:
                raw_r = (igst_amt / taxable) * 100
                r = snap_rate(raw_r, is_igst=True)
                inv_data["igst_rate"] = str(int(r) if float(r).is_integer() else r)
                inv_data["cgst_rate"] = "0"
                inv_data["sgst_rate"] = "0"
            else:
                raw_r = (cgst_amt / taxable) * 100
                r = snap_rate(raw_r, is_igst=False)
                val = str(int(r) if float(r).is_integer() else r)
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


def bulk_print_full_invoices(view, selected_ids):
    from utils.print_parts.pdf_calculator import build_pdf_context
    from utils.print_parts.pdf_builder import build_html
    
    comp_id = getattr(view.winfo_toplevel(), "active_company_id", 1)
    comp = database.get_company(comp_id)
    if not comp:
        comp = database.get_company(1)
        
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

    valid_phones = [str(p) for p in [p1, p2, p3] if p and str(p).strip()]
    c_phone = "\n".join(valid_phones) if valid_phones else "Phone"
    comp_dict = {"name": c_name, "name_sec": c_name_sec, "addr": c_addr, "phone": c_phone, "email": c_email, "gst": c_gst}
    
    try:
        full_settings = json.loads(comp[14]) if comp and len(comp) > 14 and comp[14] else {}
    except Exception:
        full_settings = {}
        
    for k in ["fonts", "colors", "bolds", "col_widths"]:
        if k not in full_settings:
            full_settings[k] = {}
            
    full_settings["logo_path"] = logo_path
    full_settings["logo_size"] = logo_size
    full_settings["logo_shape"] = logo_shape
    full_settings["layout"] = layout

    # Pre-fetch inventory mapping
    inv_dict = {}
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT item_name, unit FROM inventory WHERE company_id=?", (comp_id,))
        for i_row in c.fetchall():
            name = i_row[0] if len(i_row) > 0 else ""
            raw_unit = str(i_row[1]) if len(i_row) > 1 and i_row[1] else ""
            short_unit = raw_unit.split("(")[-1].replace(")", "").strip() if "(" in raw_unit else raw_unit
            if short_unit.lower() in ["--select--", "none", "null"]:
                short_unit = ""
            inv_dict[name] = short_unit
        conn.close()
    except Exception:
        pass

    # A fake Studio object to trick the PDF Calculator into running headless
    class MockStudio:
        def __init__(self, inv_data, items_data, banks_data):
            self.active_company_id = comp_id
            self.master = None
            self.inv_data = inv_data
            self.items_data = items_data
            self.comp_dict = comp_dict
            self.banks_data = banks_data
            self.settings = full_settings
            
            # THE FIX: A proper dummy class safely handles the 'self' argument
            class DummyVar:
                def get(self):
                    return "Inter" if float(inv_data.get("igst", 0)) > 0 else "Local"
                    
            self.tax_type_var = DummyVar()

    combined_html = ""
    base_head = ""
    base_script = ""

    # --- THE FIX: Sort explicitly by the physical Invoice Number string, NOT the database ID! ---
    try:
        clean_ids = [int(x) for x in selected_ids if str(x).isdigit()]
        if clean_ids:
            conn = database.get_connection()
            c = conn.cursor()
            placeholders = ",".join("?" for _ in clean_ids)
            c.execute(f"SELECT id, invoice_number FROM invoices WHERE id IN ({placeholders})", tuple(clean_ids))
            id_mapping = c.fetchall()
            conn.close()

            import re
            def extract_num(val_str):
                nums = re.findall(r'\d+', str(val_str))
                return int(nums[-1]) if nums else 0

            id_mapping.sort(key=lambda x: extract_num(x[1]))
            sorted_ids = [row[0] for row in id_mapping]
        else:
            sorted_ids = list(selected_ids)
    except Exception:
        sorted_ids = list(selected_ids)

    for idx, inv_id in enumerate(sorted_ids):
        inv, items = database.get_invoice_by_id(inv_id)
        if not inv:
            continue
        
        raw_place = inv[5]
        final_place, final_subj = "", ""
        inc_disc, disc_val, disc_typ = 0, "0", "%"
        inc_adv, adv_val = 0, "0"

        if raw_place:
            m_serv = re.search(r'@@SERV@@(.*?)@@', raw_place + "@@", re.DOTALL)
            if m_serv:
                parts = m_serv.group(1).split('||')
                if len(parts) > 1:
                    final_place = parts[1].strip()
            elif not raw_place.startswith("@@"):
                final_place = raw_place.strip()

            m_subj = re.search(r'@@SUBJ@@(.*?)@@', raw_place + "@@", re.DOTALL)
            if m_subj:
                subj_parts = m_subj.group(1).split('||')
                if len(subj_parts) > 0:
                    final_subj = subj_parts[0].strip()
                
            m_disc = re.search(r'@@DISC@@(.*?)@@', raw_place + "@@")
            if m_disc:
                d_parts = m_disc.group(1).split('||')
                if len(d_parts) > 0 and d_parts[0].strip().isdigit():
                    inc_disc = int(d_parts[0].strip())
                if len(d_parts) > 1:
                    disc_val = d_parts[1].strip()
                if len(d_parts) > 2:
                    disc_typ = d_parts[2].strip()
                
            m_adv = re.search(r'@@ADV@@(.*?)@@', raw_place + "@@")
            if m_adv:
                a_parts = m_adv.group(1).split('||')
                if len(a_parts) > 0 and a_parts[0].strip().isdigit():
                    inc_adv = int(a_parts[0].strip())
                if len(a_parts) > 1:
                    adv_val = a_parts[1].strip()

        inv_data = {
            "date": inv[1], "inv_date": inv[1], "del_date": inv[2], "inv_num": inv[3], "cust_name": inv[4],
            "place": final_place, "subject": final_subj, "subtotal": inv[6], "cgst": inv[7], "sgst": inv[8], 
            "igst": inv[9], "total": inv[10], "cust_id": inv[17] if len(inv) > 17 else None,
            "inc_discount": inc_disc, "discount_val": disc_val, "discount_type": disc_typ,
            "inc_advance": inc_adv, "advance_val": adv_val, "raw_place_full": inv[5]
        }

        def _clean_num(val):
            try:
                v = float(val)
                return str(int(v)) if v.is_integer() else str(v)
            except Exception:
                return str(val)

        items_d = []
        current_sl = 1
        for i in items:
            raw_days = str(i[4]).strip()
            if not raw_days or raw_days in ["0.0", "0", "None"]:
                raw_days = ""
            item_name = str(i[0])
            
            is_voided = False
            if item_name.startswith("\u200b"):
                is_voided = True
                item_name = item_name.replace("\u200b", "")
                
            raw_qty = str(i[3]).strip()
            clean_qty = "" if not raw_qty or raw_qty in ["0.0", "0", "None"] else _clean_num(raw_qty)
            clean_days = _clean_num(raw_days) if raw_days else " "
            
            if len(i) > 6:
                unit_val = str(i[6]).strip() if i[6] is not None else ""
            else:
                unit_val = inv_dict.get(item_name, "")
                
            if unit_val.lower() in ["none", "--select--", "null"]:
                unit_val = ""
                
            display_qty = f"{clean_qty} {unit_val}".strip() if f"{clean_qty} {unit_val}".strip() else " "
                
            try:
                r_val = float(re.search(r'[-+]?\d*\.?\d+', str(i[2])).group())
            except Exception:
                r_val = 0.0
                
            try:
                q_val = float(re.search(r'[-+]?\d*\.?\d+', str(i[3])).group()) if str(i[3]).strip() and str(i[3]).strip() not in ["0.0", "0", "None"] else 1.0
            except Exception:
                q_val = 1.0
                
            try:
                d_val = float(re.search(r'[-+]?\d*\.?\d+', raw_days).group()) if raw_days else 1.0
            except Exception:
                d_val = 1.0
            
            correct_amt = r_val * q_val * d_val
            display_sl = "" if is_voided else str(current_sl)
            if not is_voided:
                current_sl += 1
            
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
        except Exception:
            pass
        
        c_a = ""
        c_p = ""
        if cust:
            raw_addr = str(cust[5]) if len(cust) > 5 and cust[5] else ""
            if raw_addr.strip().startswith("{"):
                try:
                    c_a = json.loads(raw_addr).get("address", "") or ""
                except Exception:
                    c_a = raw_addr
            else:
                c_a = raw_addr or ""
                
            raw_p = str(cust[2]) if cust[2] and str(cust[2]) != "None" else ""
            c_p = re.sub(r'Mobile:\s*', '', raw_p, flags=re.IGNORECASE).split(',')[0].strip()
            
            prefs = getattr(view.winfo_toplevel(), 'customer_phone_prefs', {})
            if str(cust[0]) in prefs:
                c_p = prefs[str(cust[0])]

        inv_data["cust_addr"] = c_a
        raw_gst = cust[3] if cust else ""
        inv_data["cust_gst"] = raw_gst if raw_gst and str(raw_gst).lower() not in ["none", "null", "n/a", "na"] else ""
        inv_data["cust_phone"] = c_p 
        inv_data["words"] = number_to_words(inv_data.get("total", 0))

        if "@@SERV@@" in inv[5] or "@@BANK@@" in inv[5]:
            banks_data = unpack_db_place_string(inv[5], inv_data)
        else:
            banks_data = []
            inv_data["serv_name"] = inv_data.get("cust_name", "")
            inv_data["serv_addr"] = inv_data.get("cust_addr", "")
            inv_data["serv_del_date"] = inv_data.get("del_date", "")
            inv_data["serv_bill_date"] = inv_data.get("date", "")
            inv_data["eway_bill"] = "-"
            inv_data["subject_text"] = ""

        try:
            if str(inv_data.get("inc_discount", "0")) == "1":
                sub_t = float(inv_data.get("subtotal", 0.0))
                d_val = float(inv_data.get("discount_val", 0.0))
                if "%" in str(inv_data.get("discount_type", "%")):
                    inv_data["discount_amt"] = sub_t * (d_val / 100.0)
                else:
                    inv_data["discount_amt"] = d_val
            else:
                inv_data["discount_amt"] = 0.0
        except Exception:
            inv_data["discount_amt"] = 0.0
        
        try:
            sub_calc = float(inv_data.get("subtotal", 0.0))
            disc_calc = float(inv_data.get("discount_amt", 0.0))
            taxable = sub_calc - disc_calc
            cgst_amt = float(inv_data.get("cgst", 0.0))
            igst_amt = float(inv_data.get("igst", 0.0))
            
            def snap_rate(calculated_rate, is_igst=False):
                valid_rates = [0, 5, 12, 18, 28] if is_igst else [0, 2.5, 6, 9, 14]
                return min(valid_rates, key=lambda x: abs(x - calculated_rate))
                
            if taxable > 0:
                if igst_amt > 0:
                    r = snap_rate((igst_amt / taxable) * 100, is_igst=True)
                    inv_data["igst_rate"] = str(int(r) if float(r).is_integer() else r)
                    inv_data["cgst_rate"], inv_data["sgst_rate"] = "0", "0"
                else:
                    r = snap_rate((cgst_amt / taxable) * 100, is_igst=False)
                    val = str(int(r) if float(r).is_integer() else r)
                    inv_data["cgst_rate"], inv_data["sgst_rate"] = val, val
                    inv_data["igst_rate"] = "0"
            else:
                inv_data["cgst_rate"], inv_data["sgst_rate"], inv_data["igst_rate"] = "9", "9", "18"
        except Exception:
            pass
        
        # This executes the Python math natively!
        mock_studio = MockStudio(inv_data, items_d, banks_data)
        ctx = build_pdf_context(mock_studio, 1, 999)
        single_html = build_html(ctx)

        # Slice the generated document apart to merge all pages seamlessly
        if idx == 0:
            head_split = single_html.split("<body>")
            base_head = head_split[0] + "<body>\n"
            body_content = head_split[1]
            script_split = body_content.split("<script>")
            base_script = "\n<script>" + script_split[1]
            combined_html += script_split[0]
        else:
            head_split = single_html.split("<body>")
            body_content = head_split[1]
            script_split = body_content.split("<script>")
            combined_html += script_split[0]

    if not combined_html:
        messagebox.showinfo("Error", "No valid invoices could be generated.", parent=view)
        return

    # Stitch the single master document together
    final_doc = base_head + combined_html + base_script
    
    # Save & Open directly in the browser!
    fd, path = tempfile.mkstemp(suffix=".html", prefix="Bulk_Print_Invoices_")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(final_doc)
    webbrowser.open('file://' + os.path.realpath(path))