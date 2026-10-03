import os
import json
import ast
import database
try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
except ImportError:
    pass

from utils.print_parts.helpers import smart_date_formatter
import sys

def extract_address(addr_str):
    if not addr_str: return ""
    s_val = str(addr_str).strip()
    if s_val.startswith("{"):
        try:
            d = json.loads(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
        try:
            d = ast.literal_eval(s_val)
            if isinstance(d, dict) and "address" in d: return d["address"]
        except: pass
    return s_val

def draw_paper_bg(ctx, curr_y_off):
    ctx["studio"].page_wrappers.append(curr_y_off)
    ctx["cvs"].create_rectangle(ctx["x_off"]+5, curr_y_off+5, ctx["x_off"]+ctx["w"]+5, curr_y_off+ctx["h"]+5, fill="#333333", outline="")
    ctx["cvs"].create_rectangle(ctx["x_off"], curr_y_off, ctx["x_off"]+ctx["w"], curr_y_off+ctx["h"], fill="#ffffff", outline="#cccccc")

def draw_header(ctx):
    studio = ctx["studio"]; s = ctx["s"]; c_txt = ctx["c_txt"]
    pad = ctx["pad"]; x_off = ctx["x_off"]; w = ctx["w"]; st = ctx["state"]

    draw_paper_bg(ctx, st["y_off"])
    
    c_name = studio.comp_dict.get('name', '').upper()
    c_sec = studio.comp_dict.get('name_sec', '')
    c_addr = extract_address(studio.comp_dict.get('addr', ''))
    c_gst_val = studio.comp_dict.get('gst', '')
    
    phone_raw = studio.comp_dict.get('phone', '').strip()
    c_cont = ""
    if phone_raw:
        lbl_ph = studio.settings.get("lbl_phone", "Ph. No:")
        c_cont = f"{lbl_ph} {phone_raw}"
    
    email_raw = studio.comp_dict.get('email', '').strip()
    if email_raw:
        if c_cont: c_cont += f"\nEmail: {email_raw}"
        else: c_cont = f"Email: {email_raw}"

    try: l_sz = s(int(float(studio.settings.get("logo_size", 120))))
    except: l_sz = s(120)
    layout = studio.settings.get("layout", "Classic")
    
    tk_logo = None; draw_w = 0; logo_y_end = st["cy"]
    logo_path = studio.settings.get("logo_path", "")
    
    if logo_path and os.path.exists(logo_path):
        try:
            img = Image.open(logo_path).convert("RGBA")
            if studio.settings.get("logo_shape", "Original") in ["Square", "Circle"]:
                img = ImageOps.fit(img, (l_sz, l_sz), method=Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
                if studio.settings.get("logo_shape") == "Circle":
                    mask = Image.new('L', (l_sz*3, l_sz*3), 0)
                    ImageDraw.Draw(mask).ellipse((0,0,l_sz*3,l_sz*3), fill=255)
                    mask = mask.resize((l_sz, l_sz), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
                    img_circle = Image.new('RGBA', (l_sz, l_sz), (0,0,0,0))
                    img_circle.paste(img, (0,0), mask=mask)
                    img = img_circle
            else:
                ratio = img.width / img.height
                new_w = l_sz; new_h = int(l_sz / ratio)
                if new_h > l_sz: new_h = l_sz; new_w = int(l_sz * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)
            
            tk_logo = ImageTk.PhotoImage(img)
            studio.canvas.images.append(tk_logo)
            draw_w = img.width
        except: pass

    if layout != "Custom (Drag & Drop)":
        if tk_logo:
            lx = x_off + pad if layout in ["Split Header (Left-Center-Right)", "Left-Aligned", "Classic"] else x_off + w - pad - draw_w
            studio.canvas.create_image(lx, st["cy"], image=tk_logo, anchor="nw")
            logo_y_end = st["cy"] + tk_logo.height()

        if layout == "Split Header (Left-Center-Right)":
            center_x = x_off + w / 2; center_y = st["cy"]
            right_x = x_off + w - pad; right_y = st["cy"]
            
            if int(studio.settings.get('swap_title_order', 0)) == 1:
                if c_sec: center_y = c_txt(center_x, center_y, c_sec, "sec", anchor="n")
                center_y = c_txt(center_x, center_y, c_name, "name", anchor="n")
            else:
                center_y = c_txt(center_x, center_y, c_name, "name", anchor="n")
                if c_sec: center_y = c_txt(center_x, center_y, c_sec, "sec", anchor="n")
                
            center_y = c_txt(center_x, center_y, c_addr, "addr", max_w=s(300), anchor="n")
            if c_gst_val: center_y = c_txt(center_x, center_y, f"GSTIN: {c_gst_val}", "gst", anchor="n")
            right_y = c_txt(right_x, right_y, c_cont, "contact", anchor="ne")
            max_header_y = max(logo_y_end, center_y, right_y)
        else:
            t_x = x_off + pad + (draw_w + pad if tk_logo else 0) if layout == "Left-Aligned" else x_off + w - pad - (draw_w + pad if tk_logo else 0) if layout == "Right-Aligned" else x_off + w - pad
            t_anc = "nw" if layout == "Left-Aligned" else "ne"
            t_y = st["cy"]
            
            if int(studio.settings.get('swap_title_order', 0)) == 1:
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc)
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc)
            else:
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc)
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc)
                
            t_y = c_txt(t_x, t_y, c_addr, "addr", width=s(300), anchor=t_anc)
            t_y = c_txt(t_x, t_y, c_cont, "contact", anchor=t_anc)
            if c_gst_val: t_y = c_txt(t_x, t_y, f"GSTIN: {c_gst_val}", "gst", anchor=t_anc)
            max_header_y = max(logo_y_end, t_y)
            
        try: spacing = s(int(float(studio.settings.get("header_spacing", 20))))
        except: spacing = s(20)
        st["cy"] = max_header_y + spacing
    else:
        pos = studio.settings.get("pos", {})
        def get_dy(key, def_y):
            v = pos.get(key)
            return st["y_off"] + (v - 20) if v is not None else def_y

        if tk_logo: 
            lx = pos.get("drag_logo_x", x_off + pad)
            ly = get_dy("drag_logo_y", st["cy"])
            studio.canvas.create_image(lx, ly, image=tk_logo, anchor="nw")
        
        base_x = x_off + w / 2; curr_y = st["cy"]
        nx = pos.get("drag_name_x", base_x)
        ny = get_dy("drag_name_y", curr_y)
        curr_y = c_txt(nx, ny, c_name, "name", anchor="n", bg_solid=True)
        
        if c_sec: 
            sx = pos.get("drag_sec_x", base_x)
            sy = get_dy("drag_sec_y", curr_y)
            curr_y = c_txt(sx, sy, c_sec, "sec", anchor="n", bg_solid=True)
            
        ax = pos.get("drag_addr_x", base_x)
        ay = get_dy("drag_addr_y", curr_y)
        curr_y = c_txt(ax, ay, c_addr, "addr", width=s(300), anchor="n", bg_solid=True)
        
        cx_pos = pos.get("drag_cont_x", base_x)
        cy_txt = get_dy("drag_cont_y", curr_y)
        curr_y = c_txt(cx_pos, cy_txt, c_cont, "contact", anchor="n", bg_solid=True)
        
        if c_gst_val: 
            gx = pos.get("drag_gst_x", base_x)
            gy = get_dy("drag_gst_y", curr_y)
            curr_y = c_txt(gx, gy, f"GSTIN: {c_gst_val}", "gst", anchor="n", bg_solid=True)
            
        st["cy"] += s(50)

    studio.canvas.create_rectangle(x_off + pad, st["cy"], x_off + w - pad, st["cy"] + max(1, s(2)), fill="#000000", outline="")
    st["cy"] += s(15)
    
    # --- THE FIX: Securely read GST status from memory! ---
    has_gst = bool(ctx["studio"].comp_dict.get('gst', ''))
    # ------------------------------------------------------
    
    # Dynamically change the title based on GST status
    doc_title = "TAX INVOICE" if has_gst else "INVOICE"
    c_txt(x_off + w/2, st["cy"], doc_title, "doc_title", anchor="n")
    
    st["cy"] += s(25)

    inv = studio.inv_data
    cust_name = inv.get('cust_name', '')
    cust_addr = extract_address(inv.get('cust_addr', ''))
    cust_phone = inv.get('cust_phone', '')
    cust_gst = inv.get('cust_gst', '')
    
    # --- THE FIX: Customer Data is already packed securely in memory! ---
    # (Database connection completely removed to prevent lag and crashes)
    pass
    # --------------------------------------------------------------------
        
    if not cust_phone or str(cust_phone).strip().lower() in ["not provided", "none", "null", "not available", "not provided written in it", "na", "n/a", ""]: cust_phone = ""
    if not cust_gst or str(cust_gst).strip().lower() in ["not provided", "none", "null", "not available", "not provided written in it", "na", "n/a", ""]: cust_gst = ""

    serv_addr = extract_address(inv.get('serv_addr', ''))
    
    date_fmt = ctx.get("date_fmt", "%d.%m.%Y")
    
    serv_del_raw = inv.get('serv_del_date', '')
    serv_del = smart_date_formatter(serv_del_raw, date_fmt) if serv_del_raw else ''
    
    serv_bill_raw = inv.get('serv_bill_date', '')
    if serv_bill_raw and "to" in str(serv_bill_raw).lower():
        parts = str(serv_bill_raw).lower().split("to")
        p1 = smart_date_formatter(parts[0].strip(), date_fmt)
        p2 = smart_date_formatter(parts[1].strip(), date_fmt)
        serv_bill = f"{p1} to {p2}"
    else:
        serv_bill = smart_date_formatter(serv_bill_raw, date_fmt) if serv_bill_raw else ''
    
    inv_num = inv.get('inv_num', '')
    inv_date_raw = inv.get('inv_date', '')
    inv_date = smart_date_formatter(inv_date_raw, date_fmt) if inv_date_raw else ''
    
    eway_bill = inv.get('eway_bill', '')
    inc_eway = int(inv.get('inc_eway', 1)) == 1

    w3 = (w - 2*pad) * 0.24; w1 = (w - 2*pad - w3) / 2; w2 = w1
    subject_text = str(inv.get("subject_text", "") or inv.get("subject", "")).strip()
    box_h = s(165)

    if int(studio.settings.get('swap_boxes_var', 0)) == 1:
        meta_x = x_off + pad; serv_x = meta_x + w3; cust_x = serv_x + w2
    else:
        cust_x = x_off + pad; serv_x = cust_x + w1; meta_x = serv_x + w2

    meta_inner_w = w3 - s(20)
    meta_pairs = [("Invoice No:", inv_num), ("Invoice Date:", inv_date)]
    if inc_eway: meta_pairs.append(("E-Way Bill:", eway_bill))
        
    for m_key, m_lbl in [("challan_no", "Challan No:"), ("challan_date", "Challan Date:"), ("lr_no", "L.R. No:"), ("lr_date", "L.R. Date:"), ("veh_no", "Vehicle No:")]:
        if inv.get(m_key): meta_pairs.append((m_lbl, inv.get(m_key)))

    row_h = box_h / len(meta_pairs) if meta_pairs else box_h
    lbl_h = s(26)
    meta_bg = studio.settings.get("colors", {}).get("meta_head_bg", "#ffffff")

    if meta_bg != "#ffffff":
        studio.canvas.create_rectangle(cust_x, st["cy"], cust_x + w1, st["cy"] + lbl_h, fill=meta_bg, outline="")
        studio.canvas.create_rectangle(serv_x, st["cy"], serv_x + w2, st["cy"] + lbl_h, fill=meta_bg, outline="")
        for i in range(len(meta_pairs)):
            y_base = st["cy"] + (i * row_h)
            studio.canvas.create_rectangle(meta_x, y_base, meta_x + w3, y_base + lbl_h, fill=meta_bg, outline="")

    studio.canvas.create_line(x_off + pad, st["cy"] + lbl_h, meta_x, st["cy"] + lbl_h, fill="#000000")
    for i in range(len(meta_pairs)):
        y_base = st["cy"] + (i * row_h)
        if i > 0: studio.canvas.create_line(meta_x, y_base, meta_x + w3, y_base, fill="#000000")
        studio.canvas.create_line(meta_x, y_base + lbl_h, meta_x + w3, y_base + lbl_h, fill="#000000")

    studio.canvas.create_rectangle(x_off + pad, st["cy"], x_off + w - pad, st["cy"] + box_h, outline="#000000")
    studio.canvas.create_line(x_off + pad, st["cy"], x_off + w - pad, st["cy"], fill="#000000") 
    
    studio.canvas.create_line(serv_x, st["cy"], serv_x, st["cy"] + box_h, fill="#000000")
    studio.canvas.create_line(meta_x, st["cy"], meta_x, st["cy"] + box_h, fill="#000000")

    pref_col_w = s(85)
    title_y = st["cy"] + s(6)
    
    c_txt(cust_x + s(10), title_y, studio.settings.get("lbl_billed_to", "BILLED TO:"), "bill_title", max_w=w1-s(20))
    c_txt(serv_x + s(10), title_y, "PLACE OF SERVICE:", "serv_title", max_w=w2-s(20))
    
    pref_x = cust_x + pref_col_w
    val_x = pref_x + s(6)
    t_lim = w1 - pref_col_w - s(16)
    
    name_y = st["cy"] + s(34) 
    
    if has_gst:
        contact_y = st["cy"] + box_h - s(48)
        tax_y = st["cy"] + box_h - s(26)
    else:
        contact_y = st["cy"] + box_h - s(26)
        tax_y = -1000

    lbl_name = studio.settings.get("lbl_name", "Name:")
    lbl_addr = studio.settings.get("lbl_addr", "Address:")
    lbl_phone = studio.settings.get("lbl_phone", "Ph. No:")
    lbl_gst = studio.settings.get("lbl_gst", "GSTIN:")

    c_txt(pref_x, name_y, lbl_name, "bill_prefix", anchor="ne", max_w=pref_col_w)
    
    # --- THE FIX: Pass a blank space if empty so the Canvas reserves physical height! ---
    safe_cust_name = cust_name if cust_name else " "
    bottom_of_name = c_txt(val_x, name_y, safe_cust_name, "bill_name", width=t_lim, max_w=t_lim)
    # ----------------------------------------------------------------------------------
    
    # --- THE FIX: Dynamically push the Address down so it sits perfectly below the wrapped name! ---
    addr_y = bottom_of_name + s(2)
    
    c_txt(pref_x, addr_y, lbl_addr, "bill_prefix", anchor="ne", max_w=pref_col_w)
    c_txt(val_x, addr_y, cust_addr, "bill_addr", width=t_lim, max_w=t_lim, max_h=s(48))
    
    c_txt(pref_x, contact_y, lbl_phone, "bill_prefix", anchor="ne", max_w=pref_col_w)
    c_txt(val_x, contact_y, cust_phone, "bill_phone", max_w=t_lim)

    if has_gst:
        c_txt(pref_x, tax_y, lbl_gst, "bill_prefix", anchor="ne", max_w=pref_col_w)
        c_txt(val_x, tax_y, cust_gst, "bill_gst", max_w=t_lim)

    pref_sx = serv_x + pref_col_w
    val_sx = pref_sx + s(6)
    t_lim_s = w2 - pref_col_w - s(16)
    
    serv_addr_y = st["cy"] + s(34)
    serv_del_y = st["cy"] + box_h - s(48)
    serv_bill_y = st["cy"] + box_h - s(26)

    c_txt(pref_sx, serv_addr_y, lbl_addr, "serv_prefix", anchor="ne", max_w=pref_col_w)
    c_txt(val_sx, serv_addr_y, serv_addr, "serv_addr", width=t_lim_s, max_w=t_lim_s, max_h=s(48))
    
    c_txt(pref_sx, serv_del_y, "Del. Date:", "serv_prefix", anchor="ne", max_w=pref_col_w)
    c_txt(val_sx, serv_del_y, serv_del, "serv_del", max_w=t_lim_s)
    
    bill_val = serv_bill if (serv_bill and serv_bill.strip() != "to") else ""
    c_txt(pref_sx, serv_bill_y, "Bill Date:", "serv_prefix", anchor="ne", max_w=pref_col_w)
    c_txt(val_sx, serv_bill_y, bill_val, "serv_bill", max_w=t_lim_s)

    for i, (lbl, val) in enumerate(meta_pairs):
        y_base = st["cy"] + (i*row_h)
        lbl_key = "inv_no_lbl"; val_key = "inv_no_val"
        if "Date" in lbl and "Invoice" in lbl: 
            lbl_key = "inv_dt_lbl"; val_key = "inv_dt_val"
        elif "E-Way" in lbl:
            lbl_key = "eway_lbl"; val_key = "eway_val"

        c_txt(meta_x + s(5), y_base + s(4), lbl, lbl_key, max_w=meta_inner_w)
        c_txt(meta_x + s(5), y_base + lbl_h + s(8), val, val_key, max_w=meta_inner_w)

    if subject_text:
        subj_y = st["cy"] + box_h + s(8)
        
        lbl_bot = c_txt(x_off + pad + s(10), subj_y, "Subject:", "subj_label", tags=("subj_lbl_tag",))
        
        bbox_subj = ctx["cvs"].bbox("subj_lbl_tag")
        subj_val_x_left = bbox_subj[2] + s(5) if bbox_subj else x_off + pad + s(75)
        
        align = str(inv.get('subj_align', 'center')).lower().strip()
        if not align: align = "center" 
        
        has_b = "@@B@@" in subject_text
        has_u = "@@U@@" in subject_text
        clean_subj = subject_text.replace("@@B@@", "").replace("@@U@@", "")
        
        right_margin = x_off + w - pad
        avail_w = right_margin - subj_val_x_left
        
        if align == "center":
            center_x = x_off + w/2
            label_w = subj_val_x_left - (x_off + pad)
            safe_width = (w - 2*pad) - (2 * label_w) 
            val_bot = c_txt(center_x, subj_y, clean_subj, "subj_val", anchor="n", width=max(s(100), safe_width), bold=has_b, underline=has_u)
        elif align == "right":
            val_bot = c_txt(right_margin, subj_y, clean_subj, "subj_val", anchor="ne", width=avail_w, bold=has_b, underline=has_u)
        else: 
            val_bot = c_txt(subj_val_x_left, subj_y, clean_subj, "subj_val", anchor="nw", width=avail_w, bold=has_b, underline=has_u)

        final_subj_bottom = max(lbl_bot, val_bot) + s(8)
        
        studio.canvas.create_line(x_off + pad, st["cy"] + box_h, x_off + pad, final_subj_bottom, fill="#000000")
        studio.canvas.create_line(x_off + w - pad, st["cy"] + box_h, x_off + w - pad, final_subj_bottom, fill="#000000")
        studio.canvas.create_line(x_off + pad, final_subj_bottom, x_off + w - pad, final_subj_bottom, fill="#000000")
        
        st["cy"] = final_subj_bottom
    else:
        st["cy"] += box_h
        
    # --- THE FIX: Securely read GST status from memory! ---
    has_gst = bool(ctx["studio"].comp_dict.get('gst', ''))
    # ------------------------------------------------------
    
    cw_slno = float(studio.settings.get("col_widths", {}).get("slno", 6)) / 100.0
    cw_qty = float(studio.settings.get("col_widths", {}).get("qty", 8)) / 100.0
    cw_hsn = float(studio.settings.get("col_widths", {}).get("hsn", 12)) / 100.0
    cw_rate = float(studio.settings.get("col_widths", {}).get("rate", 12)) / 100.0
    cw_days = float(studio.settings.get("col_widths", {}).get("days", 8)) / 100.0
    cw_amt = float(studio.settings.get("col_widths", {}).get("amt", 14)) / 100.0
    
    if not has_gst:
        cw_part = max(0.05, 1.0 - sum([cw_slno, cw_qty, cw_rate, cw_days, cw_amt]))
        st["cxs"] = [x_off + pad]
        for cw in [cw_slno, cw_qty, cw_part, cw_rate, cw_days, cw_amt]:
            st["cxs"].append(st["cxs"][-1] + cw * (w - 2*pad))
    else:
        cw_part = max(0.05, 1.0 - sum([cw_slno, cw_qty, cw_hsn, cw_rate, cw_days, cw_amt]))
        st["cxs"] = [x_off + pad]
        for cw in [cw_slno, cw_qty, cw_part, cw_hsn, cw_rate, cw_days, cw_amt]:
            st["cxs"].append(st["cxs"][-1] + cw * (w - 2*pad))