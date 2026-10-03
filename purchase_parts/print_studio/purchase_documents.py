import os
import sys
import tempfile
import webbrowser
import json
import sqlite3
import base64
import re
from datetime import datetime

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

def get_img_base64(path):
    if path and os.path.exists(path):
        try:
            with open(path, "rb") as img_f:
                return f"data:image/png;base64,{base64.b64encode(img_f.read()).decode()}"
        except: pass
    return ""

def preview_purchase_voucher(data, comp_id, curr_fmt):
    comp_name = "YOUR COMPANY NAME"
    comp_phone = "N/A"
    comp_email = ""
    comp_address = "N/A"
    comp_gstin = "N/A"
    
    settings = {
        "doc_title": "PURCHASE VOUCHER",
        "show_bank": True,
        "font_family": "Arial",
        "layout": "Split Header (Left-Center-Right)",
        "header_spacing": "20",
        "swap_title_order": 0,
        "logo_size": "120",
        "logo_shape": "Original",
        "fonts": {}, "colors": {}, "bolds": {}, "underlines": {}, "col_widths": {}
    }
    
    curr_fmt_str = curr_fmt if curr_fmt else ""
    c_fmt_type = "Indian"
    c_sym = "₹"
    
    has_gst = True
    b_type = "Sales"
    
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key='currency'")
        res = c.fetchone()
        if res and res[0]:
            curr_val = res[0]
            c_fmt_type = "Indian" if "Indian" in curr_val else "International"
            
            if "(" in curr_val and ")" in curr_val:
                raw_sym = curr_val.split('(')[-1].replace(')','').strip()
                c_sym = raw_sym.split(' ')[0] if ' ' in raw_sym else raw_sym
            elif "$" in curr_val: c_sym = "$"
            elif "€" in curr_val: c_sym = "€"
            elif "£" in curr_val: c_sym = "£"
        conn.close()
    except: pass
    
    try:
        conn = database.get_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM company WHERE id=?", (comp_id,))
        comp_row = c.fetchone()
        conn.close()
        
        if comp_row:
            has_gst = (comp_row["gst_toggle"] == 1)
            
            if "business_type" in comp_row.keys() and comp_row["business_type"]:
                b_type = comp_row["business_type"]
            elif "template_json" in comp_row.keys() and comp_row["template_json"]:
                try: b_type = json.loads(comp_row["template_json"]).get("business_type", "Sales")
                except: pass
                
            comp_name = str(comp_row["name"]) if comp_row["name"] else "YOUR COMPANY NAME"
            comp_phone = str(comp_row["phone"]) if comp_row["phone"] else "N/A"
            comp_email = str(comp_row["email"]) if "email" in comp_row.keys() and comp_row["email"] else ""
            raw_addr = str(comp_row["address"]) if comp_row["address"] else ""
            
            if raw_addr and raw_addr.strip().startswith("{"):
                try:
                    j = json.loads(raw_addr)
                    comp_address = j.get("address", "N/A")
                    comp_gstin = j.get("gstin", "N/A")
                except: comp_address = raw_addr
            else: comp_address = raw_addr if raw_addr else "N/A"
                
            if "purchase_template_json" in comp_row.keys() and comp_row["purchase_template_json"]:
                try: settings.update(json.loads(comp_row["purchase_template_json"]))
                except: pass
    except: pass

    comp_name = settings.get("comp_name", comp_name)
    sec_txt = settings.get("comp_sec", "")
    comp_address = settings.get("comp_addr", comp_address)
    comp_email = settings.get("comp_email", comp_email)
    comp_gstin = settings.get("comp_gst", comp_gstin)
    
    p1 = settings.get("comp_p1", "")
    p2 = settings.get("comp_p2", "")
    p3 = settings.get("comp_p3", "")
    
    def fmt_ph(p):
        p = str(p).strip()
        if len(p) == 10 and p.isdigit(): return f"{p[:5]}-{p[5:]}"
        return p

    phones = [fmt_ph(p) for p in [p1, p2, p3] if p]
    if phones:
        comp_phone_str = "<br>".join(phones)
    else:
        comp_phone_str = comp_phone.replace('\n', '<br>') if comp_phone != "N/A" else ""

    def get_css(key, def_sz=10):
        fonts = settings.get("fonts", {})
        colors = settings.get("colors", {})
        bolds = settings.get("bolds", {})
        unders = settings.get("underlines", {})

        try: sz = int(float(fonts.get(key, def_sz)))
        except: sz = def_sz
        
        col = colors.get(key, "#000000")
        
        is_bold = bolds.get(key, False) or str(bolds.get(key, 'False')).lower() == 'true' or bolds.get(key) in [1, "1"]
        is_under = unders.get(key, False) or str(unders.get(key, 'False')).lower() == 'true' or unders.get(key) in [1, "1"]
        
        b = "bold" if is_bold else "normal"
        u = "text-decoration: underline; text-underline-offset: 3px; text-decoration-skip-ink: none;" if is_under else "text-decoration: none;"
            
        return f"font-size: {sz}pt; color: {col}; font-weight: {b}; {u}"

    prim_col = settings.get('colors', {}).get('primary_color', '#0f172a')
    head_bg = settings.get('colors', {}).get('tab_head_bg', '#475569')
    meta_bg = settings.get('colors', {}).get('meta_head_bg', '#ffffff')
    tax_title_bg = settings.get('colors', {}).get('tax_title_bg', '#ffffff')
    tax_head_bg = settings.get('colors', {}).get('tax_head_bg', '#e2e8f0')

    cw = settings.get("col_widths", {})
    w_sl = cw.get("w_slno", 5)
    w_qty = cw.get("w_qty", 8)
    w_a = cw.get("w_amt", 15)
    
    if has_gst:
        w_hsn = cw.get("w_hsn", 10)
        w_gst = cw.get("w_gst", 6)
        w_r_inc = cw.get("w_rate_inc", 12)
        w_r = cw.get("w_rate", 12)
        w_part = 100 - sum([w_sl, w_hsn, w_qty, w_gst, w_r_inc, w_r, w_a])
    else:
        w_hsn = 0; w_gst = 0; w_r_inc = 0
        w_r = cw.get("w_rate", 12)
        w_part = 100 - sum([w_sl, w_qty, w_r, w_a])

    if w_part < 10: w_part = 10

    lbl_part = "Service Description" if b_type == "Service" else "Particulars"
    lbl_qty = "Hours/<br>Qty" if b_type == "Service" else "Qnty/<br>Units"

    vendor = data.get("vendor", "Unknown Vendor")
    gstin = data.get("gstin", "")
    gstin_str = gstin if gstin else "Unregistered Dealer"
    
    raw_v_phone = str(data.get("vendor_phone", "N/A"))
    v_phone = raw_v_phone.split(',')[0].strip()
    v_phone = re.sub(r'^(mobile|ph|phone)[\s:]*', '', v_phone, flags=re.IGNORECASE).strip()
    if not v_phone: v_phone = "N/A"
    
    v_addr = data.get("vendor_address", "N/A")
    bill_no = data.get("bill", "DRAFT")
    bill_date = data.get("date", datetime.now().strftime("%d-%m-%Y"))
    
    subtotal = data.get("subtotal", 0.0)
    cgst = data.get("cgst", 0.0)
    sgst = data.get("sgst", 0.0)
    igst = data.get("igst", 0.0)
    
    # --- THE FIX: Pull the actual DB total to catch Debit Notes, instead of hard-rounding! ---
    raw_total = subtotal + cgst + sgst + igst
    total = data.get("total", round(raw_total))
    round_off = total - raw_total
    
    r_sign = "+" if round_off >= 0 else "-"
    r_val = abs(round_off)
    r_lbl = "Less: Return / Disc :" if (r_sign == "-" and r_val > 1.0) else "Round Off :"
    
    items = data.get("items", [])
    hsn_summary = data.get("hsn_summary", []) if has_gst else []
    is_interstate = data.get("is_interstate", False)

    logo_b64 = get_img_base64(settings.get("logo_path", ""))
    logo_sz = settings.get("logo_size", "120")
    logo_shape = settings.get("logo_shape", "Original")

    PAGE_H = 1000
    HEADER_H = 340
    CF_FOOTER_H = 60
    
    tax_table_h = (40 + (len(hsn_summary) * 20) + 25) if (has_gst and hsn_summary) else 0
    dynamic_bottom_px = 160 + tax_table_h + 96 if has_gst else 160 + 50
    LAST_FOOTER_H = int(dynamic_bottom_px) + 20
    
    pages_data = []
    current_page_items = []
    current_h = 0
    idx = 0
    total_items = len(items)
    
    if total_items == 0:
        pages_data.append([])
        
    while idx < total_items:
        it = items[idx]
        char_count = len(str(it.get('name', '')))
        lines = max(1, char_count // 35 + (1 if char_count % 35 > 0 else 0))
        item_h = max(28, lines * 16 + 8)
        
        req_footer = CF_FOOTER_H 
        max_allowed_h = PAGE_H - HEADER_H - req_footer
        
        if current_h + item_h > max_allowed_h:
            if len(current_page_items) > 0:
                pages_data.append(current_page_items)
                current_page_items = []
                current_h = 0
                continue
                
        current_page_items.append(it)
        current_h += item_h
        idx += 1
        
    if len(current_page_items) > 0:
        if current_h > (PAGE_H - HEADER_H - LAST_FOOTER_H):
            pages_data.append(current_page_items)
            pages_data.append([]) 
        else:
            pages_data.append(current_page_items)
    elif len(pages_data) > 0:
        pages_data.append([])

    def fmt_num(val):
        try: v = float(val)
        except: v = 0.0
        is_neg = v < 0
        v = abs(v)
        s_val = f"{v:.2f}"
        int_part, dec_part = s_val.split('.')
        if c_fmt_type == "Indian":
            if len(int_part) > 3:
                last_3 = int_part[-3:]
                rem = int_part[:-3]
                rem = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", rem)
                int_part = rem + "," + last_3
        else:
            int_part = f"{int(int_part):,}"
        res = f"{int_part}.{dec_part}"
        return f"-{res}" if is_neg else res

    # --- THE FIX: Delete duplicate get_num_words and use the global helper! ---
    from views.invoice_parts.helpers import number_to_words
    word_str = number_to_words(total, curr_fmt_str)
    # --------------------------------------------------------------------------
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{settings.get("doc_title", "PURCHASE VOUCHER")}</title>
        <style>
            *, *::before, *::after {{ 
                box-sizing: border-box; 
                -webkit-print-color-adjust: exact !important; 
                color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: '{settings.get('font_family', 'Arial')}', sans-serif; margin: 0; padding: 0; background: #525659; }}
            
            .page {{ 
                width: 210mm; 
                height: 297mm; 
                padding: 20px; 
                margin: 10px auto; 
                background: white; 
                box-sizing: border-box; 
                box-shadow: 0 0 10px rgba(0,0,0,0.5); 
                page-break-after: always; 
                display: flex;
                flex-direction: column;
                position: relative; 
                overflow: hidden; 
            }}
            
            @media print {{ body {{ background: white; }} .page {{ margin: 0; box-shadow: none; border: none; }} }}
            
            .header-table {{ width: 100%; border-collapse: collapse; flex-shrink: 0; }}
            
            .meta-table {{ width: 100%; border-collapse: collapse; border: 0.5pt solid {prim_col}; flex-shrink: 0; table-layout: fixed; margin-bottom: 15px; }}
            .meta-table > tbody > tr > td {{ border: 0.5pt solid {prim_col}; vertical-align: top; padding: 0; }}
            
            .invoice-table {{ 
                width: 100%; 
                border-collapse: collapse; 
                table-layout: fixed; 
                flex-grow: 1; 
                height: 10px; 
                border: 0.5pt solid {prim_col}; 
                border-bottom: 0.5pt solid {prim_col}; 
            }}
            
            .invoice-table th {{ 
                border: 0.5pt solid {prim_col}; 
                padding: 0; 
                height: 35px;
                vertical-align: middle;
                text-align: center; 
                background-color: {head_bg} !important; 
                white-space: nowrap; 
            }}
            
            .invoice-table td {{ 
                border-left: 0.5pt solid {prim_col}; 
                border-right: 0.5pt solid {prim_col}; 
                border-bottom: none; 
                padding: 4px 5px; 
                vertical-align: top; 
                line-height: 1.2;
            }}
            
            .tax-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; border: 0.5pt solid {prim_col}; margin-top: 15px; }}
            
            .tax-table th {{ 
                border: 0.5pt solid {prim_col}; 
                padding: 0; 
                height: 35px;
                vertical-align: middle;
                text-align: center; 
                white-space: nowrap; 
            }}
            
            .tax-table td {{ border: 0.5pt solid {prim_col}; padding: 4px; line-height: 1.1; white-space: pre-wrap; word-wrap: break-word; }}
        </style>
    </head>
    <body>
    """

    global_item_idx = 1
    running_total = 0.0

    for pg_num, page_items in enumerate(pages_data):
        is_last = (pg_num == len(pages_data) - 1)
        
        bottom_pad = dynamic_bottom_px if is_last else 60
        html_content += f'<div class="page" style="padding-bottom: calc(20px + {int(bottom_pad)}px);">'

        layout = settings.get("layout", "Split Header (Left-Center-Right)")
        swap_title = int(settings.get('swap_title_order', 0)) == 1
        
        logo_html = ""
        if logo_b64:
            l_sz = int(float(logo_sz))
            br = "50%" if logo_shape == "Circle" else "0"
            logo_html = f'<img src="{logo_b64}" style="max-width: {l_sz}px; max-height: {l_sz}px; border-radius: {br}; object-fit: contain;">'

        contact_html = ""
        if comp_phone_str: contact_html += f"<div style='line-height: 1.2;'>Ph: {comp_phone_str}</div>"
        if comp_email: contact_html += f"<div style='line-height: 1.2;'>Email: {comp_email}</div>"

        title_order_html = f"""
            <div style="{get_css('sec')} line-height: 1.0; margin-bottom: 2px;">{sec_txt}</div>
            <div style="{get_css('name')} line-height: 1.0; margin-bottom: 2px;">{comp_name}</div>
        """ if swap_title else f"""
            <div style="{get_css('name')} line-height: 1.0; margin-bottom: 2px;">{comp_name}</div>
            <div style="{get_css('sec')} line-height: 1.0; margin-bottom: 2px;">{sec_txt}</div>
        """

        gst_html = f'<div style="{get_css("gst")} margin-top: 2px; line-height: 1.0;">GSTIN: {comp_gstin}</div>' if has_gst and comp_gstin and comp_gstin != "N/A" else ""
        header_spacing = settings.get("header_spacing", "20")

        if layout == "Split Header (Left-Center-Right)":
            html_content += f"""
            <table class="header-table" style="margin-bottom: {header_spacing}px;">
                <tr>
                    <td style="width: 25%; text-align: left; vertical-align: middle;">{logo_html}</td>
                    <td style="width: 50%; text-align: center; vertical-align: middle;">
                        {title_order_html}
                        <div style="{get_css('addr')} line-height: 1.2;">{comp_address}</div>
                        {gst_html}
                    </td>
                    <td style="width: 25%; text-align: right; vertical-align: middle; white-space: nowrap;">
                        <div style="{get_css('contact')}">{contact_html}</div>
                    </td>
                </tr>
            </table>
            """
        else:
            ta = "left" if layout == "Left-Aligned" else "right"
            html_content += f"""
            <table class="header-table" style="margin-bottom: {header_spacing}px;">
                <tr>
                    {"<td style='width: 1%; white-space: nowrap; vertical-align: middle; padding-right: 15px;'>" + logo_html + "</td>" if logo_html and layout == "Left-Aligned" else ""}
                    <td style="text-align: {ta}; vertical-align: middle;">
                        {title_order_html}
                        <div style="{get_css('addr')} line-height: 1.2; max-width: 400px; {'margin-left: auto;' if ta=='right' else ''}">{comp_address}</div>
                        <div style="{get_css('contact')} margin-top: 4px; white-space: nowrap;">{contact_html}</div>
                        {gst_html}
                    </td>
                    {"<td style='width: 1%; white-space: nowrap; vertical-align: middle; padding-left: 15px;'>" + logo_html + "</td>" if logo_html and layout != "Left-Aligned" else ""}
                </tr>
            </table>
            """

        html_content += f'<div style="border-bottom: 0.5pt solid {prim_col}; margin-bottom: 15px; flex-shrink: 0;"></div>'
        html_content += f'<div style="text-align: center; {get_css("doc_title")} margin-bottom: 15px; flex-shrink: 0;">{settings.get("doc_title", "PURCHASE VOUCHER").upper()}</div>'

        # --- THE FIX: Replaced {head_bg} with {meta_bg} for all three meta header blocks! ---
        html_content += f"""
        <table class="meta-table">
            <tbody>
                <tr>
                    <td style="width: 33.33%;">
                        <div style="display: flex; flex-direction: column; height: 100%;">
                            <div style="{get_css('vend_title')} background-color: {meta_bg} !important; border-bottom: 0.5pt solid {prim_col}; height: 35px; display: flex; align-items: center; padding: 0 6px; box-sizing: border-box;">CONSIGNEE (BILL TO)</div>
                            <div style="padding: 6px; overflow: hidden;">
                                <div style="{get_css('vend_name')} margin-bottom: 4px;">{comp_name}</div>
                                <div style="{get_css('vend_addr')} line-height: 1.2;">{comp_address}</div>
                                <div style="{get_css('vend_addr')} margin-top: 4px;">Ph: {comp_phone_str}</div>
                                {f'<div style="{get_css("vend_gst")} margin-top: 4px;">GSTIN: {comp_gstin}</div>' if has_gst and comp_gstin and comp_gstin != "N/A" else ''}
                            </div>
                        </div>
                    </td>
                    
                    <td style="width: 33.33%;">
                        <div style="display: flex; flex-direction: column; height: 100%;">
                            <div style="{get_css('buyer_title')} background-color: {meta_bg} !important; border-bottom: 0.5pt solid {prim_col}; height: 35px; display: flex; align-items: center; padding: 0 6px; box-sizing: border-box;">SUPPLIER (BILL FROM)</div>
                            <div style="padding: 6px; overflow: hidden;">
                                <div style="{get_css('buyer_name')} margin-bottom: 4px;">{vendor}</div>
                                <div style="{get_css('buyer_addr')} line-height: 1.2;">{v_addr}</div>
                                <div style="{get_css('buyer_addr')} margin-top: 4px;">Ph: {v_phone}</div>
                                {f'<div style="{get_css("buyer_gst")} margin-top: 4px;">GSTIN: {gstin_str}</div>' if has_gst and gstin_str and gstin_str != "N/A" else ''}
                            </div>
                        </div>
                    </td>
                    
                    <td style="width: 33.33%; vertical-align: top;">
                        <div style="display: flex; flex-direction: column; height: 100%;">
                            <div style="{get_css('meta_title')} background-color: {meta_bg} !important; border-bottom: 0.5pt solid {prim_col}; height: 35px; display: flex; align-items: center; padding: 0 6px; box-sizing: border-box;">VOUCHER DETAILS</div>
                            <div style="flex-grow: 1; display: flex; flex-direction: column; justify-content: center; padding: 0;">
                                <table style="width: 100%; border-collapse: collapse; border: none; table-layout: fixed;">
                                    <tr>
                                        <td style="width: 90px; border: none; padding: 4px 6px; {get_css('vno_l')} white-space: nowrap;">Voucher No</td>
                                        <td style="width: 15px; border: none; padding: 4px 0;">:</td>
                                        <td style="border: none; padding: 4px 6px; {get_css('vno_v')} text-align: right; white-space: nowrap;">{data.get("voucher_no", "AUTO")}</td>
                                    </tr>
                                    <tr>
                                        <td style="border: none; padding: 4px 6px; {get_css('vdt_l')} white-space: nowrap;">Voucher Date</td>
                                        <td style="border: none; padding: 4px 0;">:</td>
                                        <td style="border: none; padding: 4px 6px; {get_css('vdt_v')} text-align: right; white-space: nowrap;">{data.get("voucher_date", bill_date)}</td>
                                    </tr>
                                    <tr><td colspan="3" style="border-top: 0.5pt solid {prim_col}; padding: 0;"></td></tr>
                                    <tr>
                                        <td style="border: none; padding: 4px 6px; {get_css('sbl_l')} white-space: nowrap;">Supplier Bill</td>
                                        <td style="border: none; padding: 4px 0;">:</td>
                                        <td style="border: none; padding: 4px 6px; {get_css('sbl_v')} text-align: right; white-space: nowrap;">{bill_no}</td>
                                    </tr>
                                    <tr>
                                        <td style="border: none; padding: 4px 6px; {get_css('sdt_l')} white-space: nowrap;">Bill Date</td>
                                        <td style="border: none; padding: 4px 0;">:</td>
                                        <td style="border: none; padding: 4px 6px; {get_css('sdt_v')} text-align: right; white-space: nowrap;">{bill_date}</td>
                                    </tr>
                                    <tr><td colspan="3" style="border-top: 0.5pt solid {prim_col}; padding: 0;"></td></tr>
                                    <tr>
                                        <td style="border: none; padding: 4px 6px; {get_css('ewy_l')} white-space: nowrap;">E-Way Bill</td>
                                        <td style="border: none; padding: 4px 0;">:</td>
                                        <td style="border: none; padding: 4px 6px; {get_css('ewy_v')} text-align: right; white-space: nowrap;">{data.get("eway_bill", "")}</td>
                                    </tr>
                                </table>
                            </div>
                        </div>
                    </td>
                </tr>
            </tbody>
        </table>
        """

        html_content += f"""
        <table class="invoice-table">
            <thead>
                <tr>
                    <th style="width: {w_sl}%; {get_css('th_slno')}"><span style="margin: 0 4px; display: inline-block;">SI No</span></th>
                    <th style="width: {w_part}%; {get_css('th_part')}"><span style="margin: 0 4px; display: inline-block;">{lbl_part}</span></th>
                    {f'<th style="width: {w_hsn}%; {get_css("th_hsn")}"><span style="margin: 0 4px; display: inline-block;">HSN/SAC</span></th>' if has_gst else ''}
                    <th style="width: {w_qty}%; {get_css('th_qty')}"><span style="margin: 0 4px; display: inline-block;">{lbl_qty}</span></th>
                    {f'<th style="width: {w_gst}%; {get_css("th_gst")}"><span style="margin: 0 4px; display: inline-block;">GST %</span></th>' if has_gst else ''}
                    {f'<th style="width: {w_r_inc}%; {get_css("th_rate_inc")}"><span style="margin: 0 4px; display: inline-block;">Rate<br>(Inc Tax)</span></th>' if has_gst else ''}
                    <th style="width: {w_r}%; {get_css('th_rate')}"><span style="margin: 0 4px; display: inline-block;">{'Base Rate' if has_gst else 'Rate'}</span></th>
                    <th style="width: {w_a}%; {get_css('th_amt')}"><span style="margin: 0 4px; display: inline-block;">Amount</span></th>
                </tr>
            </thead>
            <tbody>
        """

        if pg_num > 0:
            empty_tds = "".join(["<td></td>" for _ in range(5 if has_gst else 3)])
            html_content += f"""
            <tr style="height: 25px;">
                <td></td>
                <td style="{get_css('tr_part')} font-weight: bold; white-space: nowrap;">B/F</td>
                {empty_tds}
                <td style="{get_css('tr_amt')} font-weight: bold; text-align: right; white-space: nowrap;">{c_sym} {fmt_num(running_total)}</td>
            </tr>
            """

        for it in page_items:
            try: q = float(it['qty'])
            except: q = 0.0
            try: r_inc = float(it.get('rate_inc', 0))
            except: r_inc = 0.0
            try: r_base = float(it['rate'])
            except: r_base = 0.0
            try: gst = float(it.get('gst', 0))
            except: gst = 0.0
            try: amt = float(it['amt'])
            except: amt = 0.0
            
            running_total += amt
            gst_str = str(int(gst)) if gst.is_integer() else str(gst)

            html_content += f"""
            <tr>
                <td style="{get_css('tr_slno')} text-align: center; white-space: nowrap;">{global_item_idx}</td>
                <td style="{get_css('tr_part')} word-wrap: break-word; white-space: pre-wrap;">{it['name']}</td>
                {f'<td style="{get_css("tr_hsn")} text-align: center; white-space: nowrap;">{it.get("hsn", "")}</td>' if has_gst else ''}
                <td style="{get_css('tr_qty')} text-align: center; white-space: nowrap;">{q:g} {it['unit']}</td>
                {f'<td style="{get_css("tr_gst")} text-align: center; white-space: nowrap;">{gst_str}%</td>' if has_gst else ''}
                {f'<td style="{get_css("tr_rate_inc")} text-align: right; white-space: nowrap;">{c_sym} {fmt_num(r_inc)}</td>' if has_gst else ''}
                <td style="{get_css('tr_rate')} text-align: right; white-space: nowrap;">{c_sym} {fmt_num(r_base)}</td>
                <td style="{get_css('tr_amt')} text-align: right; white-space: nowrap;">{c_sym} {fmt_num(amt)}</td>
            </tr>
            """
            global_item_idx += 1
            
        td_blanks = "<td></td>" * (8 if has_gst else 5)
        html_content += f"""
                        <tr style="height: 100%;">
                            {td_blanks}
                        </tr>
        """
        
        if not is_last:
            empty_cells = "".join(["<td></td>" for _ in range(6 if has_gst else 3)])
            html_content += f"""
            <tr style="border-top: 0.5pt solid {prim_col};">
                {empty_cells}
                <td style="text-align: right; {get_css('tr_part')} font-weight: bold; padding-right: 15px; border-right: 0.5pt solid {prim_col}; white-space: nowrap;">Total C/F:</td>
                <td style="{get_css('tr_amt')} font-weight: bold; text-align: right; white-space: nowrap;">{c_sym} {fmt_num(running_total)}</td>
            </tr>
            """
            
            html_content += """
                    </tbody>
                </table>
            """
            
            html_content += f"""
            <div style="position: absolute; bottom: 0; left: 20px; right: 20px; height: 60px; background-color: #ffffff !important;">
                <div style="position: absolute; top: 10px; right: 5px; text-align: right; {get_css('g_total_lbl')}">Contd...</div>
                <div style="position: absolute; bottom: 15px; left: 0; right: 0; text-align: center; {get_css('page_no')} line-height: 1.0;">Page {pg_num+1}</div>
            </div>
            """
            
        else:
            td_bot_borders = f'<td style="border-bottom: 0.5pt solid {prim_col};"></td>' * (8 if has_gst else 5)
            html_content += f"""
                <tr style="height: 100%;">
                    {td_bot_borders}
                </tr>
                </tbody>
            </table>
            """
            
            html_content += f"""
            <div style="position: absolute; bottom: 0; left: 20px; right: 20px; height: calc(20px + {int(dynamic_bottom_px)}px); background-color: #ffffff !important; box-sizing: border-box;">
                
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 5px;">
                    <div style="width: 55%;">
                        <div style="{get_css('amt_w_l')} margin-bottom: 4px;">Amount (in words)</div>
                        <div style="{get_css('amt_w_v')} font-weight: bold; word-break: break-word; overflow-wrap: break-word;">{word_str}</div>
                    </div>
                    
                    <div style="width: 45%;">
                        <table style="width: 100%; border-collapse: collapse; border: none;">
                            <tr><td style="border: none; {get_css('subtotal_lbl')} text-align: right; padding-right: 15px; padding-bottom: 4px; white-space: nowrap;">{'Taxable Subtotal :' if has_gst else 'Subtotal :'}</td><td style="border: none; {get_css('subtotal_val')} text-align: right; width: 120px; padding-bottom: 4px; white-space: nowrap;">{c_sym} {fmt_num(subtotal)}</td></tr>
            """
            
            if has_gst:
                if is_interstate:
                    html_content += f'<tr><td style="border: none; {get_css("tax_totals_lbl")} text-align: right; padding-right: 15px; padding-bottom: 4px; white-space: nowrap;">Total IGST :</td><td style="border: none; {get_css("tax_totals_val")} text-align: right; padding-bottom: 4px; white-space: nowrap;">{c_sym} {fmt_num(igst)}</td></tr>'
                else:
                    html_content += f'<tr><td style="border: none; {get_css("tax_totals_lbl")} text-align: right; padding-right: 15px; padding-bottom: 4px; white-space: nowrap;">Total CGST :</td><td style="border: none; {get_css("tax_totals_val")} text-align: right; padding-bottom: 4px; white-space: nowrap;">{c_sym} {fmt_num(cgst)}</td></tr>'
                    html_content += f'<tr><td style="border: none; {get_css("tax_totals_lbl")} text-align: right; padding-right: 15px; padding-bottom: 4px; white-space: nowrap;">Total SGST :</td><td style="border: none; {get_css("tax_totals_val")} text-align: right; padding-bottom: 4px; white-space: nowrap;">{c_sym} {fmt_num(sgst)}</td></tr>'

                # --- THE FIX: Injecting the smart label here too! ---
                html_content += f"""
                                <tr><td style="border: none; {get_css('round_off_lbl')} text-align: right; padding-right: 15px; padding-bottom: 4px; white-space: nowrap;">{r_lbl}</td><td style="border: none; {get_css('round_off_val')} text-align: right; padding-bottom: 4px; white-space: nowrap;">{r_sign} {c_sym} {fmt_num(r_val)}</td></tr>
                """

            html_content += f"""
                            <tr><td colspan="2" style="border: none; padding: 0;"><div style="border-top: 0.5pt solid {prim_col}; margin: 4px 0 6px 30%;"></div></td></tr>
                            <tr><td style="border: none; {get_css('g_total_lbl')} text-align: right; padding-right: 15px; white-space: nowrap;">GRAND TOTAL :</td><td style="border: none; {get_css('g_total_val')} text-align: right; white-space: nowrap;">{c_sym} {fmt_num(total)}</td></tr>
                        </table>
                    </div>
                </div>
            """

            if has_gst and hsn_summary:
                html_content += f"""
                    <table class="tax-table">
                        <thead>
                            <tr>
                                <th colspan="{ '6' if is_interstate else '8' }" style="{get_css('tax_title')} background-color: {tax_title_bg} !important; text-align: left; padding: 0 8px; border-bottom: 0.5pt solid {prim_col};"><span style="margin: 0; display: inline-block;">TAX SUMMARY</span></th>
                            </tr>
                            <tr>
                                <th style="width:5%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">SI No</span></th>
                """
                
                if is_interstate:
                    html_content += f"""
                                <th style="width:15%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">HSN/SAC</span></th>
                                <th style="width:16%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Taxable Val</span></th>
                                <th style="width:10%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">IGST %</span></th>
                                <th style="width:12%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Amount</span></th>
                                <th style="width:22%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Total Tax</span></th>
                    """
                else:
                    html_content += f"""
                                <th style="width:15%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">HSN/SAC</span></th>
                                <th style="width:16%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Taxable Val</span></th>
                                <th style="width:9%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">CGST %</span></th>
                                <th style="width:12%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Amount</span></th>
                                <th style="width:9%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">SGST %</span></th>
                                <th style="width:12%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Amount</span></th>
                                <th style="width:22%; {get_css('tax_lbl')} background-color: {tax_head_bg} !important;"><span style="margin: 0 4px; display: inline-block;">Total Tax</span></th>
                    """
                    
                html_content += "</tr></thead><tbody>"
                
                tot_taxable = sum([float(r['taxable']) for r in hsn_summary])
                tot_total_tax = sum([float(r['total_tax']) for r in hsn_summary])
                
                for idx, row in enumerate(hsn_summary, 1):
                    html_content += "<tr>"
                    html_content += f"<td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{idx}</td>"
                    if is_interstate:
                        html_content += f"<td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{row['hsn']}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['taxable'])}</td><td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{row['igst_rate']}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['igst_amt'])}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['total_tax'])}</td>"
                    else:
                        html_content += f"<td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{row['hsn']}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['taxable'])}</td><td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{row['cgst_rate']}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['cgst_amt'])}</td><td style='text-align: center; {get_css('tax_val')} white-space: nowrap;'>{row['sgst_rate']}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['sgst_amt'])}</td><td style='text-align: right; {get_css('tax_val')} white-space: nowrap;'>{c_sym} {fmt_num(row['total_tax'])}</td>"
                    html_content += "</tr>"
                    
                if is_interstate:
                    tot_igst_amt = sum([float(r.get('igst_amt', 0)) for r in hsn_summary])
                    html_content += f"""
                    <tr>
                        <td colspan="2" style="text-align: right; {get_css('tax_sum_tot_lbl')} padding-right:10px; white-space: nowrap;">Total</td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_taxable)}</td>
                        <td></td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_igst_amt)}</td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_total_tax)}</td>
                    </tr>
                    """
                else:
                    tot_cgst_amt = sum([float(r.get('cgst_amt', 0)) for r in hsn_summary])
                    tot_sgst_amt = sum([float(r.get('sgst_amt', 0)) for r in hsn_summary])
                    html_content += f"""
                    <tr>
                        <td colspan="2" style="text-align: right; {get_css('tax_sum_tot_lbl')} padding-right:10px; white-space: nowrap;">Total</td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_taxable)}</td>
                        <td></td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_cgst_amt)}</td>
                        <td></td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_sgst_amt)}</td>
                        <td style="text-align: right; {get_css('tax_sum_tot_val')} white-space: nowrap;">{c_sym} {fmt_num(tot_total_tax)}</td>
                    </tr>
                    """
                    
                html_content += """
                                </tbody>
                            </table>
                """

            html_content += f"""
                    <div style="position: absolute; bottom: 15px; left: 0; right: 0; text-align: center; pointer-events: none;">
                        <span style="{get_css('page_no')} line-height: 1.0;">Page {pg_num+1}</span>
                    </div>
                    
                    <div style="position: absolute; bottom: 15px; right: 0; text-align: right;">
                        <div style="{get_css('signature')} font-weight: bold; margin-bottom: 4px;">For {comp_name.upper()}</div>
                        <div style="{get_css('signature')} line-height: 1.0;">Authorized Signatory</div>
                    </div>
                    
                </div>
            """
            
        html_content += "</div>" 

    html_content += """
        <script>
            window.onload = function() { 
                setTimeout(function() { window.print(); }, 500); 
            }
        </script>
    </body>
    </html>
    """
    
    # --- THE FIX: Tagged prefix for the Sweeper (Collision-Proof) ---
    safe_bill = re.sub(r'[\\/*?:"<>|]', "_", bill_no).strip()
    fd, path = tempfile.mkstemp(suffix=".html", prefix=f"Purch_Print_Studio_{safe_bill}_")
    # ----------------------------------------------
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
    webbrowser.open('file://' + os.path.realpath(path))