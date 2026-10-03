import tkinter as tk

def draw_purch_meta(ctx, cy):
    sv = ctx["sv"]
    s = ctx["s"]
    c_txt = ctx["c_txt"]
    x_off = ctx["x_off"]
    draw_w = ctx["paper_w"]
    pad = s(20)

    box_w = (draw_w - pad*2) / 3
    prim = sv.colors.get("primary_color", tk.StringVar(value="#0f172a")).get()
    
    # --- THE FIX: Intercept the Master GST Flag ---
    has_gst = ctx.get("has_gst", True)
    
    v_y1 = c_txt(-5000, cy + s(5), "CONSIGNEE (BILL TO)", "vend_title")
    b_y1 = c_txt(-5000, cy + s(5), "SUPPLIER (BILL FROM)", "buyer_title")
    m_y1 = c_txt(-5000, cy + s(5), "VOUCHER DETAILS", "meta_title")
    
    line_y = max(v_y1, b_y1, m_y1) + s(2)
    
    head_bg_col = sv.colors.get("meta_head_bg", tk.StringVar(value="#ffffff")).get()
    ctx["cvs"].create_rectangle(x_off + pad, cy, x_off + draw_w - pad, line_y, fill=head_bg_col, outline="")
    
    ctx["cvs"].create_line(x_off + pad, line_y, x_off + draw_w - pad, line_y, fill="#000000", width=1)

    c_txt(x_off + pad + s(10), cy + s(5), "CONSIGNEE (BILL TO)", "vend_title")
    c_txt(x_off + pad + box_w + s(10), cy + s(5), "SUPPLIER (BILL FROM)", "buyer_title")
    c_txt(x_off + draw_w - pad - box_w + s(10), cy + s(5), "VOUCHER DETAILS", "meta_title")

    # The Company (Bill To)
    v_start = line_y + s(5)
    v_y = v_start
    v_y = c_txt(x_off + pad + s(10), v_y, ctx["c_name"], "vend_name")
    v_y = c_txt(x_off + pad + s(10), v_y, ctx["c_addr"], "vend_addr", max_w=box_w-s(20))
    if ctx.get("c_phone"):
        v_y = c_txt(x_off + pad + s(10), v_y, f"Ph: {ctx['c_phone']}", "vend_addr", max_w=box_w-s(20))
        
    # Only render Consignee GSTIN if company has GST active
    if has_gst:
        c_gst = sv.gst_var.get()
        if c_gst: 
            v_y = c_txt(x_off + pad + s(10), v_y, f"GSTIN: {c_gst}", "vend_gst")

    # --- THE FIX: Strip out default Dummy GST values for non-GST profiles ---
    b_name = "Sample Supplier Ltd."
    b_addr = "456 Industrial Park\nPh: 00000-00000"
    b_gst = "22AAAAA0000A1Z5" if has_gst else ""
    vno_v = "PV-26-0001"
    
    fmt_dt = getattr(sv, "date_format", "DD-MM-YYYY")
    v_date = fmt_dt.replace("DD", "25").replace("MM", "06").replace("YYYY", "2026")
    b_date = fmt_dt.replace("DD", "20").replace("MM", "06").replace("YYYY", "2026")
    sbl_v = "12345/PO"
    ewy_v = ""
    
    if hasattr(sv, 'actual_bill_data') and sv.actual_bill_data:
        b_name = sv.actual_bill_data.get('vendor_name', 'Unknown')
        b_addr = sv.actual_bill_data.get('vendor_addr', 'N/A')
        b_phone = sv.actual_bill_data.get('vendor_phone', 'N/A')
        if b_phone and b_phone != "N/A": b_addr += f"\nPh: {b_phone}"
        b_gst = sv.actual_bill_data.get('vendor_gst', 'N/A') if has_gst else ""
        
        vno_v = sv.actual_bill_data.get('voucher_no', 'AUTO')
        v_date = sv.actual_bill_data.get('voucher_date', '')
        sbl_v = sv.actual_bill_data.get('supplier_bill', '')
        b_date = sv.actual_bill_data.get('supplier_date', '')
        ewy_v = sv.actual_bill_data.get('eway_bill', '')

    b_start = line_y + s(5)
    b_y = b_start
    b_x = x_off + pad + box_w + s(10)
    b_y = c_txt(b_x, b_y, b_name, "buyer_name")
    b_y = c_txt(b_x, b_y, b_addr, "buyer_addr", max_w=box_w-s(20))
    
    # Only render Supplier GSTIN if company has GST active
    if has_gst and b_gst and b_gst != "N/A":
        b_y = c_txt(b_x, b_y, f"GSTIN: {b_gst}", "buyer_gst")

    m_start = line_y + s(5)
    m_y = m_start
    m_x_right = x_off + draw_w - pad - s(10)
    m_x_left = x_off + draw_w - pad - box_w + s(10)
    line_l_x = x_off + draw_w - pad - box_w
    line_r_x = x_off + draw_w - pad
    colon_x = m_x_left + s(95)
    
    def meta_row(y, lbl, val, l_key, v_key):
        clean_lbl = lbl.replace(":", "")
        c_txt(m_x_left, y, clean_lbl, l_key)
        c_txt(colon_x, y, ":", l_key)
        ny = c_txt(m_x_right, y, val, v_key, anchor="ne")
        return max(y + s(15), ny)
        
    m_y = meta_row(m_y, "Voucher No:", vno_v, "vno_l", "vno_v")
    m_y = meta_row(m_y, "Voucher Date:", v_date, "vdt_l", "vdt_v")
    
    m_y += s(4)
    ctx["cvs"].create_line(line_l_x, m_y, line_r_x, m_y, fill=prim)
    m_y += s(8)
    
    m_y = meta_row(m_y, "Supplier Bill:", sbl_v, "sbl_l", "sbl_v")
    m_y = meta_row(m_y, "Bill Date:", b_date, "sdt_l", "sdt_v")
    
    m_y += s(4)
    ctx["cvs"].create_line(line_l_x, m_y, line_r_x, m_y, fill=prim)
    m_y += s(8)
    
    m_y = meta_row(m_y, "E-Way Bill:", ewy_v, "ewy_l", "ewy_v")

    max_h = max(v_y, b_y, m_y) + s(10)
    
    ctx["cvs"].create_rectangle(x_off + pad, cy, x_off + draw_w - pad, max_h, outline=prim, width=1) 
    ctx["cvs"].create_line(x_off + pad + box_w, cy, x_off + pad + box_w, max_h, fill=prim, width=1) 
    ctx["cvs"].create_line(x_off + draw_w - pad - box_w, cy, x_off + draw_w - pad - box_w, max_h, fill=prim, width=1) 
    
    return max_h