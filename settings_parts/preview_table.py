import math
# --- THE FIX: Corrected import path to prevent a PyInstaller crash! ---
from views.invoice_parts.helpers import format_currency, number_to_words
# ----------------------------------------------------------------------

def draw_table(ctx, cy):
    sv = ctx["sv"]
    sf = ctx["sf"]
    s = ctx["s"]
    c_txt = ctx["c_txt"]
    pad = ctx["pad"]
    x_off = ctx["x_off"]
    paper_w = ctx["paper_w"]
    paper_h = ctx["paper_h"]
    y_off = ctx["y_off"]
    curr_sym = ctx["curr_sym"]
    draw_paper_bg = ctx["draw_paper_bg"]
    get_f = ctx["get_f"]
    c_name = ctx.get("c_name", "")

    def get_actual_fmt(curr_fmt):
        mapping = {
            "Indian Rupees (₹ 10,00,000.00)": "Indian Rupees (₹)",
            "US Dollar ($ 1,000,000.00)": "US Dollar ($)",
            "Euro (€ 1.000.000,00)": "Euro (€)",
            "British Pound (£ 1,000,000.00)": "British Pound (£)",
            "Generic Number (1,000,000.00)": "Generic Number"
        }
        return mapping.get(curr_fmt, curr_fmt)

    def safe_fc(val, curr_fmt):
        actual_fmt = get_actual_fmt(curr_fmt)
        res = format_currency(val, actual_fmt)
        if len(res) >= 3 and res[-3] == ",":
            res = res[:-3] + "." + res[-2:]
        return res

    is_split = ctx["is_split"]
    show_bank_toggle = ctx["show_bank_toggle"]
    show_terms_toggle = ctx["show_terms_toggle"]

    show_discount = True
    if hasattr(sv, 'show_discount_var'): show_discount = sv.show_discount_var.get()
    elif "show_discount_toggle" in ctx: show_discount = ctx["show_discount_toggle"]
    elif "show_extras" in ctx: show_discount = ctx["show_extras"]

    show_advance = True
    if hasattr(sv, 'show_advance_var'): show_advance = sv.show_advance_var.get()
    elif "show_advance_toggle" in ctx: show_advance = ctx["show_advance_toggle"]
    elif "show_extras" in ctx: show_advance = ctx["show_extras"]

    cw_slno = sv.w_slno.get() / 100.0 if hasattr(sv, 'w_slno') else 0.07
    cw_qty = sv.w_qty.get() / 100.0 if hasattr(sv, 'w_qty') else 0.10
    cw_hsn = sv.w_hsn.get() / 100.0 if hasattr(sv, 'w_hsn') else 0.12
    cw_rate = sv.w_rate.get() / 100.0 if hasattr(sv, 'w_rate') else 0.12
    cw_days = sv.w_days.get() / 100.0 if hasattr(sv, 'w_days') else 0.10
    cw_amt = sv.w_amt.get() / 100.0 if hasattr(sv, 'w_amt') else 0.15
    cw_part = max(0.05, 1.0 - (cw_slno + cw_qty + cw_hsn + cw_rate + cw_days + cw_amt))
    
    has_gst = getattr(sv, 'has_gst', True)
    
    if has_gst:
        col_w = [cw_slno, cw_qty, cw_part, cw_hsn, cw_rate, cw_days, cw_amt]
        headers = ["Sl No.", "Qnty", "Particulars", "HSN/SAC", "Rate", "Days", "Amount"]
        head_keys = ["th_slno", "th_qty", "th_part", "th_hsn", "th_rate", "th_days", "th_amt"]
    else:
        cw_part += cw_hsn 
        col_w = [cw_slno, cw_qty, cw_part, cw_rate, cw_days, cw_amt]
        headers = ["Sl No.", "Qnty", "Particulars", "Rate", "Days", "Amount"]
        head_keys = ["th_slno", "th_qty", "th_part", "th_rate", "th_days", "th_amt"]
    
    cxs = [x_off + pad]
    for cw in col_w: cxs.append(cxs[-1] + cw * (paper_w - 2*pad))
    
    head_h = s(30)
    ctx["cvs"].create_rectangle(x_off + pad, cy, x_off + paper_w - pad, cy + head_h, fill=sv.colors["tab_head_bg"].get() if "tab_head_bg" in sv.colors else "#ffffff", outline="#000000")
    
    for i, h_text in enumerate(headers):
        c_txt(cxs[i] + (cxs[i+1]-cxs[i])/2, cy + head_h/2, h_text, head_keys[i], anchor="center", max_w=(cxs[i+1]-cxs[i])-s(4))
    
    cy += head_h; t_start = cy

    sub_val = 88888888.00
    disc_val = round(sub_val * 0.02, 2) if show_discount else 0.0
    taxable_val = sub_val - disc_val
    cgst_val = round(taxable_val * 0.09, 2)
    sgst_val = round(taxable_val * 0.09, 2)
    igst_val = round(taxable_val * 0.18, 2)
    is_igst = hasattr(sv, 'gst_type') and sv.gst_type.get() == "IGST"
    
    if has_gst:
        raw_tot = taxable_val + (igst_val if is_igst else cgst_val + sgst_val)
    else:
        raw_tot = taxable_val
        
    grand_tot = round(raw_tot)

    curr_format = sv.currency_var.get()
    amt_col_w = int(paper_w * 0.55)  
    term_col_w = int(paper_w * 0.40) 

    # Passes the extracted format so number_to_words doesn't crash on "10,00,000.00"
    words_val = number_to_words(grand_tot, get_actual_fmt(curr_format))

    ctx["cvs"].delete("dummy_measure") 
    
    tag_tl = "meas_tl"
    my_y = -5000
    my_y = c_txt(-5000, my_y, "Amount in Words:", "amt_words_lbl", tags=(tag_tl,))
    my_y = c_txt(-5000, my_y + s(2), words_val, "amt_words_val", width=amt_col_w, tags=(tag_tl,))
    bbox_tl = ctx["cvs"].bbox(tag_tl)
    top_left_h = (bbox_tl[3] - bbox_tl[1]) if bbox_tl else 0
    ctx["cvs"].delete(tag_tl)

    tag_bl = "meas_bl"
    my_y = -5000
    
    if show_bank_toggle or show_terms_toggle:
        ctx["cvs"].create_line(-5000, my_y, -5000 + term_col_w, my_y, tags=(tag_bl,))
        my_y += s(8)
        
        if show_bank_toggle:
            my_y = c_txt(-5000, my_y, "Bank Details:", "bank_lbl", tags=(tag_bl,))
            bank_str = "(Add a bank account in settings configuration layout profile)"
            if hasattr(sv, 'inc_bank_var') and sv.inc_bank_var.get() == 1:
                try:
                    chosen_alias = sv.selected_bank_var.get()
                    for b_data in sv.company_banks:
                        ac_num = str(b_data.get('ac', ''))
                        last4 = ac_num[-4:] if len(ac_num) >= 4 else ac_num
                        alias = b_data.get('alias', b_data.get('name', 'Bank'))
                        if f"{alias} (**** {last4})" == chosen_alias:
                            bank_str = f"Bank: {b_data.get('name', '')}\nA/C Name: {b_data.get('ac_name', c_name)}\nA/C No: {b_data.get('ac', '')}\nIFSC: {b_data.get('ifsc', '')}\nBranch: {b_data.get('branch', '')}"
                            if b_data.get('pan'): bank_str += f"\nPAN: {b_data.get('pan', '')}"
                            break
                except Exception: pass
            elif hasattr(sv, 'banks_list') and sv.banks_list:
                b_data = sv.banks_list[0]
                bank_str = f"Bank: {b_data.get('name', '')}\nA/C Name: {b_data.get('ac_name', c_name)}\nA/C No: {b_data.get('ac', '')}\nIFSC: {b_data.get('ifsc', '')}\nBranch: {b_data.get('branch', '')}"
                if b_data.get('pan'): bank_str += f"\nPAN: {b_data.get('pan', '')}"
            
            my_y = c_txt(-5000, my_y + s(2), bank_str, "bank_val", width=term_col_w, tags=(tag_bl,))
            my_y += s(10)

        if show_terms_toggle:
            valid_terms = [t.get().strip() for t in sv.terms_vars if t.get().strip()]
            if valid_terms:
                ctx["cvs"].create_line(-5000, my_y, -5000 + term_col_w, my_y, tags=(tag_bl,))
                my_y += s(8)
                my_y = c_txt(-5000, my_y, "Terms & Conditions:", "terms_lbl", tags=(tag_bl,))
                my_y += s(4)
                for i, val in enumerate(valid_terms):
                    c_txt(-5000, my_y, f"{i+1}.", "terms_val", tags=(tag_bl,))
                    my_y = c_txt(-5000 + s(18), my_y, val, "terms_val", width=term_col_w - s(18), tags=(tag_bl,))
                    my_y += s(2)
                
    bbox_bl = ctx["cvs"].bbox(tag_bl)
    bot_left_h = (bbox_bl[3] - bbox_bl[1]) if bbox_bl else 0
    ctx["cvs"].delete(tag_bl)

    tag_tr = "meas_tr"
    my_y = -5000
    my_y = c_txt(-5000, my_y, "Sub Total :", "totals", tags=(tag_tr,))
    if show_discount:
        my_y = c_txt(-5000, my_y, "Discount (2%) :", "totals", tags=(tag_tr,))
        
    if has_gst:
        my_y = c_txt(-5000, my_y, "Taxable Amt :", "totals", tags=(tag_tr,))
        if is_igst:
            my_y = c_txt(-5000, my_y, "IGST @ 18% :", "totals", tags=(tag_tr,))
        else:
            my_y = c_txt(-5000, my_y, "CGST @ 9% :", "totals", tags=(tag_tr,))
            my_y = c_txt(-5000, my_y, "SGST @ 9% :", "totals", tags=(tag_tr,))
            
    my_y = c_txt(-5000, my_y, "Round Off +/- :", "totals", tags=(tag_tr,))
    my_y += s(4)
    if show_advance:
        my_y += s(6)
        my_y = c_txt(-5000, my_y, "Total Amount :", "totals", tags=(tag_tr,))
        my_y = c_txt(-5000, my_y, "Advance Paid :", "totals", tags=(tag_tr,))
        my_y += s(10)
        my_y = c_txt(-5000, my_y, "Balance Due :", "totals", bold=True, tags=(tag_tr,))
    else:
        my_y += s(6)
        my_y = c_txt(-5000, my_y, "Grand Total :", "totals", bold=True, tags=(tag_tr,))
    
    bbox_tr = ctx["cvs"].bbox(tag_tr)
    top_right_h = (bbox_tr[3] - bbox_tr[1]) if bbox_tr else 0
    ctx["cvs"].delete(tag_tr)

    tag_br = "meas_br"
    my_y = -5000
    my_y = c_txt(-5000, my_y, f"For {c_name}", "signature", tags=(tag_br,))
    my_y = c_txt(-5000, my_y, "Authorized Signatory", "signature", tags=(tag_br,))
    bbox_br = ctx["cvs"].bbox(tag_br)
    sig_h = (bbox_br[3] - bbox_br[1]) if bbox_br else 0
    ctx["cvs"].delete(tag_br)
    
    BOTTOM_MARGIN = s(15)
    bot_right_h = s(75) + sig_h 
    ctx["bot_left_h"] = bot_left_h
    ctx["sig_h"] = sig_h
    ctx["words_val"] = words_val
    
    total_footer_reserve = max(top_left_h + bot_left_h, top_right_h + bot_right_h) + s(10) + BOTTOM_MARGIN
    
    available_h = paper_h - cy - total_footer_reserve
    font_sz_test = get_f("tr_part")
    
    single_item_h = max(s(14), (1 * font_sz_test * 1.2) + s(2)) + s(2) 
    
    max_items_fit = max(1, int(available_h / single_item_h))
    
    if is_split: num_items = max_items_fit + 25 
    else: num_items = max_items_fit 
    
    items_to_render = []
    for i in range(1, num_items + 1): 
        items_to_render.append({"sl": f"{i:02d}", "name": f"Premium Customization Service {i}", "hsn": "999999", "qty": "1 Nos.", "rate": safe_fc(5000, curr_format), "days": "1", "amt": safe_fc(5000, curr_format)})
    
    page_count = 1

    for idx, row_data in enumerate(items_to_render):
        font_sz = get_f("tr_part")
        part_px_w = (cw_part * (paper_w - 2 * pad)) - s(10)
        chars_per_line = max(1, int(part_px_w / (font_sz * 0.55)))
        lines = max(1, len(row_data["name"]) // chars_per_line + (1 if len(row_data["name"]) % chars_per_line > 0 else 0))
        
        item_h = max(s(14), (lines * font_sz * 1.2) + s(2))

        is_last_item = (idx == len(items_to_render) - 1)
        
        if not is_split:
            current_reserve = total_footer_reserve
        else:
            current_reserve = total_footer_reserve if is_last_item else s(75) 
        
        item_bottom = cy + item_h + s(4)
                
        if item_bottom > (y_off + paper_h - current_reserve): 
            if not is_split: break 
                
            tot_y = max(cy + s(5), y_off + paper_h - s(70))
            if tot_y < cy + s(5): tot_y = cy + s(5)
            f_y_page = tot_y + s(28)
            
            ctx["cvs"].create_line(cxs[0], tot_y, cxs[-1], tot_y, fill="#000000")
            
            if has_gst:
                c_txt(cxs[6] - s(12), tot_y + s(5), "Total :", "tr_part", bold=True, anchor="ne")
                f_total_val = safe_fc(idx * 5000, curr_format) 
                c_txt(cxs[7] - s(4), tot_y + s(5), f_total_val, "tr_amt", bold=True, anchor="ne", max_w=(cxs[7]-cxs[6])-s(8))
                
                for cx in cxs: ctx["cvs"].create_line(cx, t_start - head_h, cx, tot_y, fill="#000000")
                ctx["cvs"].create_line(cxs[0], tot_y, cxs[0], f_y_page, fill="#000000")
                ctx["cvs"].create_line(cxs[6], tot_y, cxs[6], f_y_page, fill="#000000")
                ctx["cvs"].create_line(cxs[7], tot_y, cxs[7], f_y_page, fill="#000000")
            else:
                c_txt(cxs[5] - s(12), tot_y + s(5), "Total :", "tr_part", bold=True, anchor="ne")
                f_total_val = safe_fc(idx * 5000, curr_format) 
                c_txt(cxs[6] - s(4), tot_y + s(5), f_total_val, "tr_amt", bold=True, anchor="ne", max_w=(cxs[6]-cxs[5])-s(8))
                
                for cx in cxs: ctx["cvs"].create_line(cx, t_start - head_h, cx, tot_y, fill="#000000")
                ctx["cvs"].create_line(cxs[0], tot_y, cxs[0], f_y_page, fill="#000000")
                ctx["cvs"].create_line(cxs[5], tot_y, cxs[5], f_y_page, fill="#000000")
                ctx["cvs"].create_line(cxs[6], tot_y, cxs[6], f_y_page, fill="#000000")
            
            ctx["cvs"].create_line(x_off + pad, f_y_page, x_off + paper_w - pad, f_y_page, fill="#000000")
            
            c_txt(cxs[-1] - s(12), f_y_page + s(6), "continued ...", "tr_part", italic=True, anchor="ne")
            c_txt(x_off + paper_w/2, y_off + paper_h - s(10), f"Page {page_count}", "page_no", anchor="s")
            
            page_count += 1
            y_off += paper_h + 40
            draw_paper_bg(y_off)
            
            cy = y_off + pad
            t_start = cy + head_h
            
            ctx["cvs"].create_rectangle(x_off + pad, cy, x_off + paper_w - pad, cy + head_h, fill=sv.colors["tab_head_bg"].get() if "tab_head_bg" in sv.colors else "#ffffff", outline="#000000")
            for i, h_text in enumerate(headers):
                c_txt(cxs[i] + (cxs[i+1]-cxs[i])/2, cy + head_h/2, h_text, head_keys[i], anchor="center", max_w=(cxs[i+1]-cxs[i])-s(4))
            cy += head_h
            
            c_txt(cxs[2] + s(5), cy + s(10), "B / F", "tr_part", bold=True, anchor="nw")
            
            if has_gst:
                c_txt(cxs[7] - s(2), cy + s(10), f_total_val, "tr_amt", bold=True, anchor="ne")
            else:
                c_txt(cxs[6] - s(2), cy + s(10), f_total_val, "tr_amt", bold=True, anchor="ne")
                
            cy += s(35)

        top_y = cy + s(2) 
        part_bottom = c_txt(cxs[2] + s(5), top_y, row_data["name"], "tr_part", width=int((cxs[3]-cxs[2])-s(10)), max_w=(cxs[3]-cxs[2])-s(10))
        
        c_txt(cxs[0] + (cxs[1]-cxs[0])/2, top_y, row_data["sl"], "tr_slno", anchor="n", max_w=(cxs[1]-cxs[0])-s(4))
        c_txt(cxs[1] + (cxs[2]-cxs[1])/2, top_y, row_data["qty"], "tr_qty", anchor="n", max_w=(cxs[2]-cxs[1])-s(4))
        
        if has_gst:
            c_txt(cxs[3] + (cxs[4]-cxs[3])/2, top_y, row_data["hsn"], "tr_hsn", anchor="n", max_w=(cxs[4]-cxs[3])-s(4))
            c_txt(cxs[5] - s(2), top_y, row_data["rate"], "tr_rate", anchor="ne", max_w=(cxs[5]-cxs[4])-s(2))
            c_txt(cxs[5] + (cxs[6]-cxs[5])/2, top_y, row_data["days"], "tr_days", anchor="n", max_w=(cxs[6]-cxs[5])-s(4))
            c_txt(cxs[7] - s(2), top_y, row_data["amt"], "tr_amt", anchor="ne", max_w=(cxs[7]-cxs[6])-s(2))
        else:
            c_txt(cxs[4] - s(2), top_y, row_data["rate"], "tr_rate", anchor="ne", max_w=(cxs[4]-cxs[3])-s(2))
            c_txt(cxs[4] + (cxs[5]-cxs[4])/2, top_y, row_data["days"], "tr_days", anchor="n", max_w=(cxs[5]-cxs[4])-s(4))
            c_txt(cxs[6] - s(2), top_y, row_data["amt"], "tr_amt", anchor="ne", max_w=(cxs[6]-cxs[5])-s(2))
        
        cy = part_bottom + s(2)

    f_y = y_off + paper_h - total_footer_reserve
    
    for cx in cxs: ctx["cvs"].create_line(cx, t_start - head_h, cx, f_y, fill="#000000")
    ctx["cvs"].create_line(x_off + pad, f_y, x_off + paper_w - pad, f_y, fill="#000000")

    return f_y, page_count, y_off