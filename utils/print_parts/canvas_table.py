import database
from utils.print_parts.helpers import format_currency

def parse_f(val):
    try: return float(str(val).replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "").strip() or 0)
    except: return 0.0

def draw_table_headers(ctx):
    st = ctx["state"]; s = ctx["s"]; c_txt = ctx["c_txt"]; cxs = st["cxs"]
    head_h = s(30)
    ctx["cvs"].create_rectangle(ctx["x_off"] + ctx["pad"], st["cy"], ctx["x_off"] + ctx["w"] - ctx["pad"], st["cy"] + head_h, fill=ctx["studio"].settings.get("colors", {}).get("tab_head_bg", "#ffffff"), outline="#000000")
    
    if len(cxs) == 8:
        headers = ["Sl No.", "Qnty", "Particulars", "HSN/SAC", "Rate", "Days", "Amount"]
        head_keys = ["th_slno", "th_qty", "th_part", "th_hsn", "th_rate", "th_days", "th_amt"]
    else:
        headers = ["Sl No.", "Qnty", "Particulars", "Rate", "Days", "Amount"]
        head_keys = ["th_slno", "th_qty", "th_part", "th_rate", "th_days", "th_amt"]
        
    for i, h_text in enumerate(headers):
        c_txt(cxs[i] + (cxs[i+1]-cxs[i])/2, st["cy"] + head_h/2, h_text, head_keys[i], anchor="center", max_w=(cxs[i+1]-cxs[i])-s(4))
    
    st["cy"] += head_h
    st["t_start"] = st["cy"]

def draw_table(ctx):
    st = ctx["state"]; s = ctx["s"]; c_txt = ctx["c_txt"]; cxs = st["cxs"]
    h = ctx["h"]; pad = ctx["pad"]; x_off = ctx["x_off"]; w = ctx["w"]
    sf = ctx["sf"]
    inv = ctx["studio"].inv_data
    
    draw_table_headers(ctx)

    show_discount = int(inv.get("inc_discount", 0)) == 1
    show_advance = int(inv.get("inc_advance", 0)) == 1
    is_igst = hasattr(ctx["studio"], 'gst_type') and ctx["studio"].gst_type.get() == "IGST"
    has_banks = bool(ctx["studio"].banks_data)
    
    inc_terms = int(inv.get("inc_terms", 1))
    valid_terms = []
    if inc_terms == 1:
        valid_terms = [t.strip() for t in ctx["studio"].settings.get("terms_list", []) if t.strip()]
        if not valid_terms and ctx["studio"].settings.get("term1"): valid_terms.append(ctx["studio"].settings.get("term1"))

    amt_col_w = int(w * 0.55)
    term_col_w = int(w * 0.40)
    
    ctx["cvs"].delete("dummy_measure") 
    
    # 1. Measure Top Left Block (Amount in Words + Bank Details)
    tag_tl = "meas_tl"
    my_y = -5000
    my_y = c_txt(-5000, my_y, "Amount in Words:", "amt_words_lbl", tags=(tag_tl,))
    my_y = c_txt(-5000, my_y + s(2), ctx["words_val"], "amt_words_val", width=amt_col_w, tags=(tag_tl,))
    
    if has_banks:
        ctx["cvs"].create_line(-5000, my_y, -5000 + term_col_w, my_y, tags=(tag_tl,))
        my_y += s(8)
        my_y = c_txt(-5000, my_y, "Bank Details:", "bank_lbl", tags=(tag_tl,))
        b_data = ctx["studio"].banks_data[0]
        c_name_val = ctx["studio"].comp_dict.get('name', '').upper()
        bank_str = f"Bank: {b_data.get('name', '')}\nA/C Name: {b_data.get('ac_name') or c_name_val}\nA/C No: {b_data.get('ac', '')}\nIFSC: {b_data.get('ifsc', '')}\nBranch: {b_data.get('branch', '')}"
        my_y = c_txt(-5000, my_y + s(2), bank_str, "bank_val", width=term_col_w, tags=(tag_tl,))
        my_y += s(10)

    bbox_tl = ctx["cvs"].bbox(tag_tl)
    top_left_h = (bbox_tl[3] - bbox_tl[1]) if bbox_tl else 0
    ctx["cvs"].delete(tag_tl)

    # 2. Measure Bottom Left Block (Terms ONLY)
    tag_bl = "meas_bl"
    my_y = -5000
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

    # --- THE FIX: Securely read GST status from memory! ---
    has_gst = bool(ctx["studio"].comp_dict.get('gst', ''))
    # ------------------------------------------------------

    # 3. Measure Top Right Block (Totals)
    tag_tr = "meas_tr"
    my_y = -5000
    my_y = c_txt(-5000, my_y, "Sub Total :", "totals", tags=(tag_tr,))
    if show_discount:
        my_y = c_txt(-5000, my_y, "Discount :", "totals", tags=(tag_tr,))
        my_y = c_txt(-5000, my_y, "Taxable Amt :", "totals", tags=(tag_tr,))
    
    if has_gst:
        if is_igst:
            ig_r = inv.get("igst_rate", "18")
            my_y = c_txt(-5000, my_y, f"IGST @ {ig_r}% :", "totals", tags=(tag_tr,))
        else:
            cg_r = inv.get("cgst_rate", "9")
            sg_r = inv.get("sgst_rate", "9")
            my_y = c_txt(-5000, my_y, f"CGST @ {cg_r}% :", "totals", tags=(tag_tr,))
            my_y = c_txt(-5000, my_y, f"SGST @ {sg_r}% :", "totals", tags=(tag_tr,))
            
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

    # 4. Measure Bottom Right Block (Signatures)
    tag_br = "meas_br"
    my_y = -5000
    my_y = c_txt(-5000, my_y, f"For {ctx.get('c_name', '')}", "signature", tags=(tag_br,))
    my_y = c_txt(-5000, my_y, "Authorized Signatory", "signature", tags=(tag_br,))
    bbox_br = ctx["cvs"].bbox(tag_br)
    sig_h = (bbox_br[3] - bbox_br[1]) if bbox_br else 0
    ctx["cvs"].delete(tag_br)
    
    total_left = top_left_h + bot_left_h + s(25)
    total_right = top_right_h + sig_h + s(25)
    total_footer_reserve = max(total_left, total_right) + s(10)
    ctx["final_footer_res"] = max(s(250), total_footer_reserve + s(40))

    font_sz = ctx["get_f"]("tr_part")
    part_px_w = (cxs[3] - cxs[2]) - s(10)

    for item in ctx["studio"].items_data:
        it = item.get("data", {})
        
        raw_name = str(it.get("name", ""))
        has_b = "@@B@@" in raw_name
        has_u = "@@U@@" in raw_name
        clean_name = raw_name.replace("@@B@@", "").replace("@@U@@", "")
        
        # --- THE FIX: Let Tkinter calculate the EXACT pixel height of the wrapped text! ---
        ctx["cvs"].delete("dummy_meas")
        c_txt(-5000, -5000, clean_name, "tr_part", width=int(part_px_w), bold=has_b, underline=has_u, tags=("dummy_meas",))
        bbox_meas = ctx["cvs"].bbox("dummy_meas")
        actual_text_h = (bbox_meas[3] - bbox_meas[1]) if bbox_meas else s(15)
        ctx["cvs"].delete("dummy_meas")

        # --- THE FIX: Tighter padding (4px) for a compact, professional look ---
        item_h = max(s(20), actual_text_h + s(4))
        # ----------------------------------------------------------------------------------

        if st["cy"] + item_h > (st["y_off"] + h - s(75)):
            tot_y = st["y_off"] + h - s(75)
            f_y_page = tot_y + s(28)
            
            ctx["cvs"].create_line(cxs[0], tot_y, cxs[-1], tot_y, fill="#000000")
            c_txt(cxs[-2] - s(12), tot_y + s(5), "Total :", "tr_part", bold=True, anchor="ne")
            f_tot = format_currency(st["running_total"], ctx["curr_format"])
            c_txt(cxs[-1] - s(4), tot_y + s(5), f_tot, "tr_amt", bold=True, anchor="ne", max_w=(cxs[-1]-cxs[-2])-s(8))
            
            for cx in cxs: ctx["cvs"].create_line(cx, st["t_start"] - s(30), cx, tot_y, fill="#000000")
            ctx["cvs"].create_line(cxs[0], tot_y, cxs[0], f_y_page, fill="#000000")
            ctx["cvs"].create_line(cxs[-2], tot_y, cxs[-2], f_y_page, fill="#000000")
            ctx["cvs"].create_line(cxs[-1], tot_y, cxs[-1], f_y_page, fill="#000000")
            ctx["cvs"].create_line(x_off + pad, f_y_page, x_off + w - pad, f_y_page, fill="#000000")
            
            text_y = st["y_off"] + h - s(15)
            c_txt(cxs[-1] - s(12), text_y, "continued ...", "tr_part", italic=True, anchor="se")
            c_txt(x_off + w/2, text_y, f"Page {st['page_count']}", "page_no", anchor="s")
            
            st["page_count"] += 1
            st["y_off"] += h + 40
            
            st["cy"] = st["y_off"] + pad
            from utils.print_parts.canvas_header import draw_header
            draw_header(ctx)
            
            draw_table_headers(ctx)
            
            c_txt(cxs[2] + s(5), st["cy"] + s(10), "B / F", "tr_part", bold=True, anchor="nw")
            c_txt(cxs[-1] - s(2), st["cy"] + s(10), f_tot, "tr_amt", bold=True, anchor="ne", max_w=(cxs[-1]-cxs[-2])-s(4))
            st["cy"] += s(35)

        try: st["running_total"] += ctx["parse_f"](it.get("amt", 0))
        except: pass

        sl_val = str(item.get("idx", it.get("sl", ""))).strip()
        if sl_val in ["0", "0.0", "None"]: sl_val = ""
        
        qty_val = str(it.get("qty", "")).strip()
        unit_val = str(it.get("unit", "")).strip()
        if qty_val and unit_val:
            qty_val = f"{qty_val} {unit_val}"
        elif unit_val and not qty_val:
            qty_val = unit_val
            
        hsn_val = str(it.get("hsn", "")).strip()
        
        rate_str = str(it.get("rate", "")).strip()
        amt_str = str(it.get("amt", "")).strip()
        
        r_f = ctx["parse_f"](rate_str)
        a_f = ctx["parse_f"](amt_str)
        
        r_disp = format_currency(r_f, ctx["curr_format"]) if r_f != 0 else ""
        a_disp = format_currency(a_f, ctx["curr_format"]) if a_f != 0 else ""

        days_val = str(it.get("days", "")).strip()
        # --- THE FIX: Erased the fallback logic that forces '1' ---
        if days_val in ["0", "0.0", "None"]: 
            days_val = ""
            
        if not sl_val and r_f == 0.0 and a_f == 0.0:
            sl_val = ""; qty_val = ""; hsn_val = ""; r_disp = ""; days_val = ""; a_disp = ""

        top_y = st["cy"] + s(3) 
        c_txt(cxs[2] + s(5), top_y, clean_name, "tr_part", width=int((cxs[3]-cxs[2])-s(10)), max_w=(cxs[3]-cxs[2])-s(10), bold=has_b, underline=has_u)
        c_txt(cxs[0] + (cxs[1]-cxs[0])/2, top_y, sl_val, "tr_slno", anchor="n", max_w=(cxs[1]-cxs[0])-s(4))
        c_txt(cxs[1] + (cxs[2]-cxs[1])/2, top_y, qty_val, "tr_qty", anchor="n", max_w=(cxs[2]-cxs[1])-s(4))
        
        if len(cxs) == 8:
            c_txt(cxs[3] + (cxs[4]-cxs[3])/2, top_y, hsn_val, "tr_hsn", anchor="n", max_w=(cxs[4]-cxs[3])-s(4))
            c_txt(cxs[5] - s(2), top_y, r_disp, "tr_rate", anchor="ne", max_w=(cxs[5]-cxs[4])-s(2))
            c_txt(cxs[5] + (cxs[6]-cxs[5])/2, top_y, days_val, "tr_days", anchor="n", max_w=(cxs[6]-cxs[5])-s(4))
            c_txt(cxs[7] - s(2), top_y, a_disp, "tr_amt", anchor="ne", max_w=(cxs[7]-cxs[6])-s(2))
        else:
            c_txt(cxs[4] - s(2), top_y, r_disp, "tr_rate", anchor="ne", max_w=(cxs[4]-cxs[3])-s(2))
            c_txt(cxs[4] + (cxs[5]-cxs[4])/2, top_y, days_val, "tr_days", anchor="n", max_w=(cxs[5]-cxs[4])-s(4))
            c_txt(cxs[6] - s(2), top_y, a_disp, "tr_amt", anchor="ne", max_w=(cxs[6]-cxs[5])-s(2))
        
        st["cy"] += item_h

    if st["cy"] + ctx["final_footer_res"] > (st["y_off"] + h - s(10)):
        tot_y = st["y_off"] + h - s(75)
        f_y_page = tot_y + s(28)
        
        ctx["cvs"].create_line(cxs[0], tot_y, cxs[-1], tot_y, fill="#000000")
        c_txt(cxs[-2] - s(12), tot_y + s(5), "Total :", "tr_part", bold=True, anchor="ne")
        f_tot = format_currency(st["running_total"], ctx["curr_format"])
        c_txt(cxs[-1] - s(4), tot_y + s(5), f_tot, "tr_amt", bold=True, anchor="ne", max_w=(cxs[-1]-cxs[-2])-s(8))
        
        for cx in cxs: ctx["cvs"].create_line(cx, st["t_start"] - s(30), cx, tot_y, fill="#000000")
        ctx["cvs"].create_line(cxs[0], tot_y, cxs[0], f_y_page, fill="#000000")
        ctx["cvs"].create_line(cxs[-2], tot_y, cxs[-2], f_y_page, fill="#000000")
        ctx["cvs"].create_line(cxs[-1], tot_y, cxs[-1], f_y_page, fill="#000000")
        ctx["cvs"].create_line(x_off + pad, f_y_page, x_off + w - pad, f_y_page, fill="#000000")
        
        text_y = st["y_off"] + h - s(15)
        c_txt(cxs[-1] - s(12), text_y, "continued ...", "tr_part", italic=True, anchor="se")
        c_txt(x_off + w/2, text_y, f"Page {st['page_count']}", "page_no", anchor="s")
        
        st["page_count"] += 1
        st["y_off"] += h + 40
        
        st["cy"] = st["y_off"] + pad
        from utils.print_parts.canvas_header import draw_header
        draw_header(ctx)
        
        draw_table_headers(ctx)
        
        c_txt(cxs[2] + s(5), st["cy"] + s(10), "B / F", "tr_part", bold=True, anchor="nw")
        c_txt(cxs[-1] - s(2), st["cy"] + s(10), f_tot, "tr_amt", bold=True, anchor="ne", max_w=(cxs[-1]-cxs[-2])-s(4))
        st["cy"] += s(35)