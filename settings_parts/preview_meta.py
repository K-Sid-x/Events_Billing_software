import tkinter as tk
import os
import sys
import json

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

import database

def draw_meta(ctx, cy):
    sv = ctx["sv"]
    s = ctx["s"]
    c_txt = ctx["c_txt"]
    pad = ctx["pad"]
    x_off = ctx["x_off"]
    paper_w = ctx["paper_w"]
    d_str = ctx["d_str"]
    d2 = ctx["d2"]
    dbill = ctx["dbill"]

    cust_name = "Sample Customer"
    cust_addr = "1234 Enterprise Blvd, Corporate Business Park Phase 2, Metro City, 000000"
    cust_phone = "+91 98765-43210"
    cust_gst = "22AAAAA0000A1Z5"
    
    has_gst = getattr(sv, 'has_gst', True)
    if not has_gst:
        cust_gst = ""

    if hasattr(sv, 'cust_var') and sv.cust_var.get().strip():
        cust_name = sv.cust_var.get().strip()
        try:
            # --- THE FIX: Eliminate Cross-Company Data Leak and pull live data ---
            c_row = database.get_customer_by_name(cust_name)
                
            if c_row:
                # Correct indices: 2=Phone, 3=GSTIN, 5=Address
                raw_addr = str(c_row[5]).strip() if len(c_row) > 5 and c_row[5] else ""
                
                # Protect against JSON Garbage if customer has a Wallet Balance
                if raw_addr.startswith("{"):
                    try:
                        j_data = json.loads(raw_addr)
                        cust_addr = j_data.get("address", "")
                    except:
                        cust_addr = raw_addr
                else:
                    cust_addr = raw_addr

                cust_phone = str(c_row[2]).strip() if len(c_row) > 2 and c_row[2] else ""
                
                if has_gst:
                    cust_gst = str(c_row[3]).strip() if len(c_row) > 3 and c_row[3] else ""
        except Exception: pass

    if cust_phone.lower() in ["not provided", "none", "null", "not available", "not provided written in it"]: cust_phone = ""
    if cust_gst.lower() in ["not provided", "none", "null", "not available", "not provided written in it"]: cust_gst = ""

    serv_addr_val = sv.serv_addr_var.get() if hasattr(sv, 'serv_addr_var') else "1234 Enterprise Blvd, Corporate Business Park Phase 2, Metro City, 000000"
    serv_del_val = sv.serv_del_var.get() if hasattr(sv, 'serv_del_var') and sv.serv_del_var.get() else d2
    
    if hasattr(sv, 'serv_bill_from_var') and hasattr(sv, 'serv_bill_to_var') and sv.serv_bill_from_var.get():
        serv_bill_val = f"{sv.serv_bill_from_var.get()} to {sv.serv_bill_to_var.get()}"
    else:
        serv_bill_val = dbill

    inv_num_val = sv.inv_num_var.get() if hasattr(sv, 'inv_num_var') else "INV-0001"
    inv_date_val = sv.inv_date_var.get() if hasattr(sv, 'inv_date_var') and sv.inv_date_var.get() else d_str
    eway_val = sv.eway_var.get() if hasattr(sv, 'eway_var') else "123456789012"
    
    show_eway = sv.inc_eway_var.get() == 1 if hasattr(sv, 'inc_eway_var') else True
    show_subject = sv.show_subject_var.get() == 1 if hasattr(sv, 'show_subject_var') else True
    subject_text = sv.subj_var.get().strip() if hasattr(sv, 'subj_var') else "Provision of Comprehensive Software Customization Layout Integration Services."
    if not show_subject: subject_text = ""

    ctx["cvs"].create_rectangle(x_off + pad, cy, x_off + paper_w - pad, cy + max(1, s(2)), fill="#000000", outline="")
    cy += s(15)
    
    # Dynamically change the title based on GST status
    title_text = "TAX INVOICE" if has_gst else "INVOICE"
    c_txt(x_off + paper_w/2, cy, title_text, "doc_title", anchor="n")
    
    cy += s(25)

    total_w = paper_w - 2 * pad
    w3 = total_w * 0.26 
    w1 = (total_w - w3) / 2 
    w2 = w1
    
    box_h = s(165) 
    subj_h = s(45) if subject_text else 0
    total_box_h = box_h + subj_h

    box_right = x_off + paper_w - pad

    swap = sv.swap_boxes_var.get() == 1 if hasattr(sv, 'swap_boxes_var') else False
    if swap:
        meta_x = x_off + pad; serv_x = meta_x + w3; cust_x = serv_x + w2
    else:
        cust_x = x_off + pad; serv_x = cust_x + w1; meta_x = serv_x + w2

    m_bg = sv.colors.get("meta_head_bg", tk.StringVar(value="#ffffff")).get()
    
    title_h = s(26) 
    meta_title_h = s(26)
    row_h = box_h / 3 if show_eway else box_h / 2

    if m_bg != "#ffffff" and m_bg != "":
        ctx["cvs"].create_rectangle(cust_x, cy, serv_x, cy + title_h, fill=m_bg, outline="")
        if swap:
            ctx["cvs"].create_rectangle(serv_x, cy, box_right, cy + title_h, fill=m_bg, outline="")
        else:
            ctx["cvs"].create_rectangle(serv_x, cy, meta_x, cy + title_h, fill=m_bg, outline="")
        
        ctx["cvs"].create_rectangle(meta_x, cy, box_right, cy + meta_title_h, fill=m_bg, outline="")
        ctx["cvs"].create_rectangle(meta_x, cy + row_h, box_right, cy + row_h + meta_title_h, fill=m_bg, outline="")
        if show_eway:
            ctx["cvs"].create_rectangle(meta_x, cy + 2*row_h, box_right, cy + 2*row_h + meta_title_h, fill=m_bg, outline="")

    ctx["cvs"].create_rectangle(x_off + pad, cy, box_right, cy + total_box_h, outline="#000000")
    if subject_text:
        ctx["cvs"].create_line(x_off + pad, cy + box_h, box_right, cy + box_h, fill="#000000")

    ctx["cvs"].create_line(serv_x, cy, serv_x, cy + box_h, fill="#000000")
    if swap:
        ctx["cvs"].create_line(cust_x, cy, cust_x, cy + box_h, fill="#000000")
    else:
        ctx["cvs"].create_line(meta_x, cy, meta_x, cy + box_h, fill="#000000")

    ctx["cvs"].create_line(cust_x, cy + title_h, serv_x, cy + title_h, fill="#000000")
    if swap:
        ctx["cvs"].create_line(serv_x, cy + title_h, box_right, cy + title_h, fill="#000000")
    else:
        ctx["cvs"].create_line(serv_x, cy + title_h, meta_x, cy + title_h, fill="#000000")
    
    ctx["cvs"].create_line(meta_x, cy + meta_title_h, box_right, cy + meta_title_h, fill="#000000")
    ctx["cvs"].create_line(meta_x, cy + row_h, box_right, cy + row_h, fill="#000000")
    ctx["cvs"].create_line(meta_x, cy + row_h + meta_title_h, box_right, cy + row_h + meta_title_h, fill="#000000")
    
    if show_eway:
        ctx["cvs"].create_line(meta_x, cy + 2*row_h, box_right, cy + 2*row_h, fill="#000000")
        ctx["cvs"].create_line(meta_x, cy + 2*row_h + meta_title_h, box_right, cy + 2*row_h + meta_title_h, fill="#000000")

    pref_col_w = s(85) 
    
    title_y = cy + s(6) 
    c_txt(cust_x + s(10), title_y, sv.lbl_billed_to_var.get() if hasattr(sv, 'lbl_billed_to_var') else "BILLED TO:", "bill_title", max_w=w1-s(20))
    
    pref_x = cust_x + pref_col_w
    val_x = pref_x + s(6)
    t_lim = w1 - pref_col_w - s(16)
    
    name_y = cy + title_h + s(8)
    addr_y = cy + title_h + s(28)
    
    # THE FIX: If no GST, Phone Number drops down to anchor the bottom!
    if cust_gst:
        tax_y = cy + box_h - s(26)
        contact_y = cy + box_h - s(48)
    else:
        tax_y = -1000
        contact_y = cy + box_h - s(26)
    
    c_txt(pref_x, name_y, "Name :", "bill_prefix", anchor="ne")
    c_txt(val_x, name_y, cust_name, "bill_name", max_w=t_lim)
    
    c_txt(pref_x, addr_y, "Address :", "bill_prefix", anchor="ne")
    c_txt(val_x, addr_y, cust_addr, "bill_addr", width=t_lim, max_w=t_lim, max_h=s(48))
    
    if cust_phone:
        c_txt(pref_x, contact_y, "Ph. No :", "bill_prefix", anchor="ne")
        c_txt(val_x, contact_y, cust_phone, "bill_phone", max_w=t_lim)
    
    if cust_gst:
        c_txt(pref_x, tax_y, "GSTIN :", "bill_prefix", anchor="ne")
        c_txt(val_x, tax_y, cust_gst, "bill_gst", max_w=t_lim)

    c_txt(serv_x + s(10), title_y, "PLACE OF SERVICE:", "serv_title", max_w=w2-s(20))
    pref_sx = serv_x + pref_col_w
    val_sx = pref_sx + s(6)
    t_lim_s = w2 - pref_col_w - s(16)

    serv_addr_y = cy + title_h + s(8)
    
    serv_bill_y = cy + box_h - s(26)
    serv_del_y = cy + box_h - s(48)
    
    c_txt(pref_sx, serv_addr_y, "Address :", "serv_prefix", anchor="ne")
    c_txt(val_sx, serv_addr_y, serv_addr_val, "serv_addr", width=t_lim_s, max_w=t_lim_s, max_h=s(48))
    if serv_del_val:
        c_txt(pref_sx, serv_del_y, "Del. Date :", "serv_prefix", anchor="ne")
        c_txt(val_sx, serv_del_y, serv_del_val, "serv_del", max_w=t_lim_s)
    if serv_bill_val and serv_bill_val.strip() != "to":
        c_txt(pref_sx, serv_bill_y, "Bill Date :", "serv_prefix", anchor="ne") 
        c_txt(val_sx, serv_bill_y, serv_bill_val, "serv_bill", max_w=t_lim_s)

    meta_inner_w = (box_right - meta_x) - s(20)

    c_txt(meta_x + s(10), cy + s(6), "Invoice No :", "inv_no_lbl", max_w=meta_inner_w)
    c_txt(meta_x + s(10), cy + meta_title_h + s(8), inv_num_val, "inv_no_val", max_w=meta_inner_w)
    
    c_txt(meta_x + s(10), cy + row_h + s(6), "Invoice Date :", "inv_dt_lbl", max_w=meta_inner_w)
    c_txt(meta_x + s(10), cy + row_h + meta_title_h + s(8), inv_date_val, "inv_dt_val", max_w=meta_inner_w)
    
    if show_eway:
        c_txt(meta_x + s(10), cy + 2*row_h + s(6), "E-Way Bill :", "eway_lbl", max_w=meta_inner_w)
        c_txt(meta_x + s(10), cy + 2*row_h + meta_title_h + s(8), eway_val, "eway_val", max_w=meta_inner_w)

    if subject_text:
        subj_y = cy + box_h + s(12)
        c_txt(x_off + pad + s(10), subj_y, "Subject :", "subj_label", tags=("subj_lbl_tag",))
        bbox_subj = ctx["cvs"].bbox("subj_lbl_tag")
        subj_val_x = bbox_subj[2] + s(5) if bbox_subj else x_off + pad + s(75)
        c_txt(subj_val_x, subj_y, subject_text, "subj_val", width=(x_off + paper_w - pad) - subj_val_x)

    return cy + total_box_h