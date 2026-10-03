import os
import sys
import math
import json
import ast
import base64
import database

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    utils_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(utils_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

from utils.print_parts.helpers import number_to_words, fetch_global_settings, smart_date_formatter

def extract_address(addr_str):
    if not addr_str: return ""
    s_val = str(addr_str).strip()
    if s_val.startswith("{"):
        try:
            d = ast.literal_eval(s_val)
            if isinstance(d, dict): return d.get("address", s_val)
        except: pass
        try:
            d = json.loads(s_val)
            if isinstance(d, dict): return d.get("address", s_val)
        except: pass
    return s_val

def get_image_base64(path):
    if not path or not os.path.exists(path): return ""
    try:
        import mimetypes
        mime = mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as img_file:
            b64_str = base64.b64encode(img_file.read()).decode('utf-8')
        return f"data:{mime};base64,{b64_str}"
    except: return ""

def build_pdf_context(studio, p_from, p_to):
    def get_f(key, def_sz=10):
        fonts = studio.settings.get("fonts", {})
        try: return max(1, int(float(fonts.get(key, def_sz))))
        except: return max(1, int(def_sz))

    # --- THE BULLETPROOF FIX: Guaranteed Root Window Traversal ---
    comp_id = 1
    widget = studio
    while widget:
        if hasattr(widget, "active_company_id"):
            comp_id = getattr(widget, "active_company_id")
            break
        widget = widget.master
        
    has_gst = True
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT gst_toggle FROM company WHERE id=?", (comp_id,))
        row = c.fetchone()
        if row: has_gst = (row[0] == 1)
        conn.close()
    except: pass
    # -------------------------------------------------------------

    global_curr, global_date_fmt = fetch_global_settings(comp_id)
    curr_format = global_curr

    c_name = studio.comp_dict.get('name', '').upper()
    c_sec = studio.comp_dict.get('name_sec', '')
    c_addr = extract_address(studio.comp_dict.get('addr', ''))
    c_phone = studio.comp_dict.get('phone', '')
    c_email = studio.comp_dict.get('email', '')
    c_gst = studio.comp_dict.get('gst', '')

    serv_addr = extract_address(str(studio.inv_data.get("serv_addr", "") or studio.inv_data.get("serv_addr_var", "") or studio.inv_data.get("place_of_supply", "")).strip())
    
    serv_del_raw = str(studio.inv_data.get("serv_del_date", "") or studio.inv_data.get("serv_del_var", "") or studio.inv_data.get("serv_del", "") or studio.inv_data.get("del_date", "") or studio.inv_data.get("delivery_date", "")).strip()
    serv_del_date = smart_date_formatter(serv_del_raw, global_date_fmt) if serv_del_raw else ''

    b_main = str(studio.inv_data.get("serv_bill_from_var", "") or studio.inv_data.get("serv_bill_date", "") or studio.inv_data.get("serv_bill_var", "") or studio.inv_data.get("serv_bill", "") or studio.inv_data.get("bill_date", "") or studio.inv_data.get("bill_date_var", "") or studio.inv_data.get("bill_period", "") or studio.inv_data.get("bill_from", "") or studio.inv_data.get("bill_start", "")).strip()
    b_to = str(studio.inv_data.get("serv_bill_to_var", "") or studio.inv_data.get("serv_bill_to", "") or studio.inv_data.get("bill_to", "") or studio.inv_data.get("bill_date_to", "") or studio.inv_data.get("bill_end", "")).strip()

    if b_main and b_to and "to" not in b_main.lower():
        serv_bill_date = f"{smart_date_formatter(b_main, global_date_fmt)} to {smart_date_formatter(b_to, global_date_fmt)}"
    else:
        serv_bill_date = smart_date_formatter(b_main, global_date_fmt) if b_main else ''

    eway_bill = str(studio.inv_data.get("eway_bill", "") or studio.inv_data.get("eway_var", "") or studio.inv_data.get("eway", "")).strip()
    subject_text = str(studio.inv_data.get("subject_text", "") or studio.inv_data.get("subject", "") or studio.inv_data.get("subj_var", "") or studio.inv_data.get("subj", "")).strip()

    inc_discount = int(studio.inv_data.get("inc_discount", 0))
    discount_val = studio.inv_data.get("discount_val", "0")
    discount_type = studio.inv_data.get("discount_type", "%")
    try: discount_amt = float(studio.inv_data.get("discount_amt", 0.0))
    except: discount_amt = 0.0

    inc_advance = int(studio.inv_data.get("inc_advance", 0))
    try: advance_val = float(studio.inv_data.get("advance_val", 0))
    except: advance_val = 0.0

    cust_name = studio.inv_data.get('cust_name', '')
    cust_addr = extract_address(studio.inv_data.get('cust_addr', ''))
    cust_phone = studio.inv_data.get('cust_phone', '')
    cust_gst = studio.inv_data.get('cust_gst', '')

    inv_num = studio.inv_data.get('inv_num', '')
    
    inv_date_raw = studio.inv_data.get('date', '')
    inv_date = smart_date_formatter(inv_date_raw, global_date_fmt) if inv_date_raw else ''
    
    is_igst = hasattr(studio, 'gst_type') and studio.gst_type.get() == "IGST"

    # --- THE FIX: STRICT SQL ISOLATION TO PREVENT DATA LEAKS ---
    if cust_name and cust_name != "[CUSTOMER NOT SELECTED]":
        try:
            import sqlite3
            conn = database.get_connection()
            c = conn.cursor()
            
            c.execute("SELECT id, name, phone, gstin, email, address FROM customers WHERE company_id=? AND LOWER(name)=?", (comp_id, str(cust_name).strip().lower()))
            row = c.fetchone()
            if row:
                if not cust_phone:
                    raw_phone = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                    if raw_phone and raw_phone != "None": cust_phone = raw_phone.split(",")[0].split(":")[-1].strip()
                if not cust_gst: cust_gst = str(row[3]).strip() if len(row) > 3 and row[3] else ""
                if not cust_addr: cust_addr = extract_address(str(row[5]).strip() if len(row) > 5 and row[5] else "")
            conn.close()
        except Exception: pass
    # -----------------------------------------------------------

    if not cust_phone or str(cust_phone).strip().lower() in ["not provided", "none", "null", "not available", "not provided written in it", "na", "n/a", ""]: cust_phone = ""
    if not cust_gst or str(cust_gst).strip().lower() in ["not provided", "none", "null", "not available", "not provided written in it", "na", "n/a", ""]: cust_gst = ""

    if eway_bill.lower() in ["none", "null", "not available", "-", ""]: eway_bill = ""
    show_eway = bool(eway_bill.strip())

    inc_subj_flag = studio.inv_data.get("inc_subj_var", studio.inv_data.get("inc_subject", 1))
    if hasattr(inc_subj_flag, "get"): inc_subj_flag = inc_subj_flag.get()
    show_subject = bool(subject_text) and (int(inc_subj_flag) != 0)

    logo_b64 = get_image_base64(studio.settings.get("logo_path", ""))

    cw = studio.settings.get("col_widths", {})
    w_slno = cw.get("slno", 6); w_qty = cw.get("qty", 8)
    w_hsn = cw.get("hsn", 12); w_rate = cw.get("rate", 12)
    w_days = cw.get("days", 8); w_amt = cw.get("amt", 14)
    w_part = max(5, 100 - sum([w_slno, w_qty, w_hsn, w_rate, w_days, w_amt]))

    try: sub = float(studio.inv_data.get("subtotal", 0) or 0)
    except: sub = 0.0
    try: cg = float(studio.inv_data.get("cgst", 0) or 0)
    except: cg = 0.0
    try: sg = float(studio.inv_data.get("sgst", 0) or 0)
    except: sg = 0.0
    try: ig = float(studio.inv_data.get("igst", 0) or 0)
    except: ig = 0.0
    try: tot = float(studio.inv_data.get("total", 0) or 0)
    except: tot = 0.0

    taxable_amt = sub - discount_amt if inc_discount == 1 else sub
    round_off = tot - (taxable_amt + cg + sg + ig)
    
    words_val = studio.inv_data.get('words', '') or number_to_words(tot, curr_format)
    for c_name_str in ["Pounds", "Dollars", "Euros", "Rupees", "Dirhams", "Dinars"]:
        if words_val.startswith(f"{c_name_str} ") and words_val.endswith(" Only"):
            words_val = words_val[len(c_name_str)+1:-5] + f" {c_name_str} Only"
            break

    amt_col_w_pct = 55; term_col_w_pct = 40
    f_amt_lbl = get_f("amt_words_lbl"); f_amt_val = get_f("amt_words_val")
    f_bank_lbl = get_f("bank_lbl"); f_bank_val = get_f("bank_val")
    f_term_lbl = get_f("terms_lbl"); f_term_val = get_f("terms_val")
    f_tot = get_f("totals"); f_sig = get_f("signature")
    f_bold_tot = max(14, f_tot)

    amt_lines = max(1, math.ceil(len(words_val) / max(1, int(794 * (amt_col_w_pct / 100.0) / (f_amt_val * 0.55)))))
    top_left_h = int(f_amt_lbl * 1.5) + (amt_lines * int(f_amt_val * 1.5)) + 2

    inc_terms = int(studio.inv_data.get("inc_terms", 1))
    terms_list = studio.settings.get("terms_list", [])
    if not terms_list:
        if studio.settings.get("term1"): terms_list.append(studio.settings.get("term1"))
        if studio.settings.get("term2"): terms_list.append(studio.settings.get("term2"))
        
    valid_terms = []
    if inc_terms == 1:
        valid_terms = [t.strip() for t in terms_list if t.strip()]

    bot_left_h = 0
    if studio.banks_data or valid_terms:
        bot_left_h += 8
    if studio.banks_data:
        bot_left_h += int(f_bank_lbl * 1.5) + 2 + (4 * int(f_bank_val * 1.5)) + 10
    if valid_terms:
        if studio.banks_data: bot_left_h += 8
        term_lines = sum(math.ceil(len(t) / max(1, int((794 * (term_col_w_pct / 100.0)) / max(1, f_term_val * 0.55)))) for t in valid_terms)
        bot_left_h += int(f_term_lbl * 1.5) + 4 + (term_lines * int(f_term_val * 1.5)) + (len(valid_terms) * 2)

    tot_rows = 1
    if inc_discount == 1 and discount_amt > 0: tot_rows += 2
    if cg > 0: tot_rows += 1
    if sg > 0: tot_rows += 1
    if ig > 0: tot_rows += 1
    tot_rows += 1
    
    top_right_h = (tot_rows * int(f_tot * 1.5)) + 4
    if inc_advance == 1 and advance_val > 0: top_right_h += 6 + (2 * int(f_tot * 1.5)) + 10 + int(f_bold_tot * 1.5)
    else: top_right_h += 6 + int(f_bold_tot * 1.5)

    sig_h = int(f_sig * 1.5 * 2)
    
    dynamic_bottom_px = max(180, max(top_left_h + bot_left_h, top_right_h + sig_h) + 10)

    def tk_precise_pagination():
        w = 794; h = 1123; pad = 20
        
        if show_subject:
            clean_subj = subject_text.replace("@@B@@", "").replace("@@U@@", "")
            f_subj = get_f("subj_val", 10)
            lines = 0
            for seg in clean_subj.split('\n'):
                seg_len = len(seg)
                if seg_len == 0: lines += 1
                else: lines += max(1, seg_len // 85 + (1 if seg_len % 85 > 0 else 0))
            
            subj_h = max(55, 35 + (lines * 20))
        else:
            subj_h = 20
            
        header_h = 325 + subj_h 
        
        font_sz = get_f("tr_part", 10)
        
        cw_pct = max(0.05, 1.0 - sum([w_slno/100.0, w_qty/100.0, w_hsn/100.0, w_rate/100.0, w_days/100.0, w_amt/100.0]))
        part_px_w = (cw_pct * (w - 2 * pad)) - 10
        chars_per_line = max(1, int(part_px_w / (font_sz * 0.55)))
        
        pages = []
        current_page = []
        cy = header_h + 30 
        
        for idx, item in enumerate(studio.items_data):
            it = item.get("data", {})
            raw_name = str(it.get("name", ""))
            clean_name = raw_name.replace("@@B@@", "").replace("@@U@@", "")
            
            lines = 0
            for seg in clean_name.split('\n'):
                seg_len = len(seg)
                if seg_len == 0: lines += 1
                else: lines += max(1, seg_len // chars_per_line + (1 if seg_len % chars_per_line > 0 else 0))
                
            item_h = max(19, int(lines * font_sz * 1.2) + 4)
            
            if cy + item_h > (h - 75):
                pages.append(current_page)
                current_page = []
                cy = header_h + 30 + 35 
                
            current_page.append(item)
            cy += item_h
            
        if cy + dynamic_bottom_px > (h - 90):
            pages.append(current_page)
            pages.append([]) 
        elif current_page or not pages:
            pages.append(current_page)
            
        return pages

    pages_data = tk_precise_pagination()
    
    qr_b64 = ""
    if studio.banks_data:
        qr_path = studio.banks_data[0].get("qr_path", "")
        if qr_path:
            qr_b64 = get_image_base64(qr_path)

    sel_sig = str(studio.inv_data.get("selected_sig", "")).strip()
    sigs = studio.settings.get("signatures", [])
    sig_data = None
    if sel_sig:
        for s_obj in sigs:
            if str(s_obj.get("role", "")).strip() == sel_sig:
                sig_data = s_obj
                break
    
    sig_path = str(sig_data.get("path", "")).strip() if sig_data else ""
    sig_role = str(sig_data.get("role", "")).strip() if sig_data else ""
    
    if not sig_role or sig_role == "--Select--":
        sig_role = "Authorised Signatory"
        
    sig_b64 = get_image_base64(sig_path)

    return {
        "studio": studio, "p_from": p_from, "p_to": p_to, "pages_data": pages_data,
        "c_name": c_name, "c_sec": c_sec, "c_addr": c_addr, "c_phone": c_phone, "c_email": c_email, "c_gst": c_gst,
        "serv_addr": serv_addr, "serv_del_date": serv_del_date, "serv_bill_date": serv_bill_date,
        "eway_bill": eway_bill, "show_eway": show_eway,
        "subject_text": subject_text, "show_subject": show_subject,
        "cust_name": cust_name, "cust_addr": cust_addr, "cust_phone": cust_phone, "cust_gst": cust_gst,
        "inv_num": inv_num, "inv_date": inv_date, "logo_b64": logo_b64,
        "w_slno": w_slno, "w_qty": w_qty, "w_part": w_part, "w_hsn": w_hsn, "w_rate": w_rate, "w_days": w_days, "w_amt": w_amt,
        "amt_col_w_pct": amt_col_w_pct, "term_col_w_pct": term_col_w_pct,
        "words_val": words_val, "terms_list": valid_terms,
        "inc_discount": inc_discount, "discount_val": discount_val, "discount_type": discount_type, "discount_amt": discount_amt,
        "inc_advance": inc_advance, "advance_val": advance_val,
        "sub": sub, "cg": cg, "sg": sg, "ig": ig, "tot": tot, "taxable_amt": taxable_amt, "round_off": round_off,
        "curr_format": curr_format,
        "dynamic_bottom_px": dynamic_bottom_px,
        "is_igst": is_igst,
        "qr_b64": qr_b64,
        "sig_role": sig_role,
        "sig_b64": sig_b64,
        "has_gst": has_gst
    }