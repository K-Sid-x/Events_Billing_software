# --- THE FIX: Corrected import path to prevent a PyInstaller crash! ---
from views.invoice_parts.helpers import number_to_words, format_currency
import os
# ----------------------------------------------------------------------

def draw_footer(ctx, f_y, page_count, y_off_final):
    sv = ctx["sv"]
    s = ctx["s"]
    c_txt = ctx["c_txt"]
    pad = ctx["pad"]
    x_off = ctx["x_off"]
    paper_w = ctx["paper_w"]
    paper_h = ctx["paper_h"]
    c_name = ctx["c_name"]

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

    has_gst = getattr(sv, 'has_gst', True)

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

    curr_format = sv.currency_var.get()
    amt_col_w = int(paper_w * 0.55) 
    term_col_w = int(paper_w * 0.40)
    
    cw_amt = sv.w_amt.get() / 100.0 if hasattr(sv, 'w_amt') else 0.15
    line_start_x = (x_off + paper_w - pad) - (cw_amt * (paper_w - 2 * pad))
    
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
    round_off = grand_tot - raw_tot
    adv_val = 200000.00 if show_advance else 0.0
    bal_val = grand_tot - adv_val
    
    words_val = ctx.get("words_val", "")

    left_y = f_y + s(5)
    left_y = c_txt(x_off + pad, left_y, "Amount in Words:", "amt_words_lbl")
    c_txt(x_off + pad, left_y + s(2), words_val, "amt_words_val", width=amt_col_w)
    
    tx = x_off + paper_w - pad
    lbl_x = tx - s(120)
    right_y = f_y + s(5)
    
    c_txt(lbl_x, right_y, "Sub Total :", "totals", anchor="ne")
    right_y = c_txt(tx, right_y, safe_fc(sub_val, curr_format), "totals", anchor="ne")
    
    if show_discount:
        c_txt(lbl_x, right_y, "Discount (2%) :", "totals", anchor="ne")
        right_y = c_txt(tx, right_y, "- " + safe_fc(disc_val, curr_format), "totals", anchor="ne")
        
    if has_gst:
        c_txt(lbl_x, right_y, "Taxable Amt :", "totals", anchor="ne")
        right_y = c_txt(tx, right_y, safe_fc(taxable_val, curr_format), "totals", anchor="ne")
        
        if is_igst:
            c_txt(lbl_x, right_y, "IGST @ 18% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, safe_fc(igst_val, curr_format), "totals", anchor="ne")
        else:
            c_txt(lbl_x, right_y, "CGST @ 9% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, safe_fc(cgst_val, curr_format), "totals", anchor="ne")
            c_txt(lbl_x, right_y, "SGST @ 9% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, safe_fc(sgst_val, curr_format), "totals", anchor="ne")
        
    c_txt(lbl_x, right_y, "Round Off +/- :", "totals", anchor="ne")
    right_y = c_txt(tx, right_y, safe_fc(round_off, curr_format), "totals", anchor="ne")
    
    line_y = right_y + s(4)

    # THE FIX: Removed the `tx + s(25)` overhang bug. All lines draw perfectly flush to `tx`!
    if show_advance:
        ctx["cvs"].create_rectangle(line_start_x, line_y, tx, line_y + max(1, s(1)), fill="#000000", outline="")
        gt_y = line_y + s(6)
        c_txt(lbl_x, gt_y, "Total Amount :", "totals", anchor="ne")
        gt_y = c_txt(tx, gt_y, safe_fc(grand_tot, curr_format), "totals", anchor="ne")
        
        c_txt(lbl_x, gt_y, "Advance Paid :", "totals", anchor="ne")
        gt_y = c_txt(tx, gt_y, "- " + safe_fc(adv_val, curr_format), "totals", anchor="ne")
        
        line_y2 = gt_y + s(4)
        ctx["cvs"].create_rectangle(line_start_x, line_y2, tx, line_y2 + max(1, s(1)), fill="#000000", outline="")
        bal_y = line_y2 + s(6)
        c_txt(lbl_x, bal_y, "Balance Due :", "totals", bold=True, anchor="ne")
        c_txt(tx, bal_y, safe_fc(bal_val, curr_format), "totals", bold=True, anchor="ne")
    else:
        ctx["cvs"].create_rectangle(line_start_x, line_y, tx, line_y + max(1, s(1)), fill="#000000", outline="")
        gt_y = line_y + s(6)
        c_txt(lbl_x, gt_y, "Grand Total :", "totals", bold=True, anchor="ne")
        gt_y = c_txt(tx, gt_y, safe_fc(grand_tot, curr_format), "totals", bold=True, anchor="ne")
        line_y2 = gt_y + s(4)
        ctx["cvs"].create_rectangle(line_start_x, line_y2, tx, line_y2 + max(1, s(1)), fill="#000000", outline="")

    BOTTOM_MARGIN = s(15)
    bottom_limit = y_off_final + paper_h - BOTTOM_MARGIN

    c_txt(x_off + paper_w/2, bottom_limit, f"Page {page_count}", "page_no", anchor="s")

    # =================================================================================
    # THE FIX: Mathematically Centered Signature Stack mapped exactly to the vertical line
    # =================================================================================
    tag_sig = "footer_sig"
    sig_y = -5000
    
    sig_data = None
    if hasattr(sv, 'signatures_list') and sv.signatures_list:
        for s_obj in sv.signatures_list:
            if s_obj.get("is_default"):
                sig_data = s_obj
                break
        if not sig_data: sig_data = sv.signatures_list[0]
        
    sig_path = sig_data.get("path", "") if sig_data else ""
    sig_role = sig_data.get("role", "Authorized Signatory") if sig_data else "Authorized Signatory"
    show_esign = hasattr(sv, 'show_esign_var') and sv.show_esign_var.get() == 1
    
    # 1. We measure the exact bounding box of all text to find the widest element
    ctx["cvs"].delete("dummy_sig_meas")
    c_txt(-5000, -5000, f"For {c_name}", "signature", tags=("dummy_sig_meas",))
    c_txt(-5000, -5000, sig_role, "signature", tags=("dummy_sig_meas",))
    bbox_meas = ctx["cvs"].bbox("dummy_sig_meas")
    max_w = (bbox_meas[2] - bbox_meas[0]) if bbox_meas else 0
    ctx["cvs"].delete("dummy_sig_meas")

    img_h = 0
    img_w = 0
    sig_nudge = sv.sig_nudge_var.get() if hasattr(sv, 'sig_nudge_var') else 0
    
    if show_esign and sig_path and os.path.exists(sig_path):
        try:
            from PIL import Image
            img = Image.open(sig_path)
            sig_scale = sv.sig_scale_var.get() / 100.0 if hasattr(sv, 'sig_scale_var') else 1.0
            base_h = s(45)
            img_h = int(base_h * sig_scale)
            img_w = int(img_h * (img.width / img.height))
            max_w = max(max_w, img_w) # Ensure the stack bounds cover the image if it's huge
        except: pass

    # 2. Perfect Center Point: By subtracting half the widest element, the right edge perfectly kisses `tx`!
    sig_center_x = tx - (max_w / 2)

    if show_esign:
        # 1. Draw "For Company" first at the top
        sig_y = c_txt(sig_center_x, sig_y, f"For {c_name}", "signature", anchor="n", tags=(tag_sig,))
        
        # 2. Draw the signature image directly underneath (incorporating the vertical nudge)
        if img_w > 0 and img_h > 0:
            try:
                from PIL import Image, ImageTk
                img = Image.open(sig_path)
                img = img.resize((img_w, img_h), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS)
                sv.invoice_sig_img = ImageTk.PhotoImage(img) 
                
                img_y = sig_y + s(sig_nudge)
                ctx["cvs"].create_image(sig_center_x, img_y, image=sv.invoice_sig_img, anchor="n", tags=(tag_sig,))
                sig_y += img_h + s(5)
            except Exception as e:
                sig_y += s(45) + s(5) # Keep gap if image fails
        else:
            # --- THE FIX: Force a 45px gap (100% scale) for manual pen signatures! ---
            sig_y += s(45) + s(5)
            # -------------------------------------------------------------------------
                
        # 3. Draw the Role at the very bottom
        c_txt(sig_center_x, sig_y, sig_role, "signature", anchor="n", tags=(tag_sig,))
        
        # Teleport entire stack just above the bottom margin
        bbox_sig = ctx["cvs"].bbox(tag_sig)
        if bbox_sig:
            target_bottom = bottom_limit - s(5) 
            ctx["cvs"].move(tag_sig, 0, target_bottom - bbox_sig[3])
            
    else:
        # e-sign UNCHECKED: Stack anchors directly to the Page No baseline (no teleportation needed)
        c_txt(sig_center_x, bottom_limit, sig_role, "signature", anchor="s", tags=(tag_sig,))
        # --- THE FIX: Pushes 'For Company Name' up by 60px to leave room for a physical pen signature ---
        c_txt(sig_center_x, bottom_limit - s(60), f"For {c_name}", "signature", anchor="s", tags=(tag_sig,))
        # ------------------------------------------------------------------------------------------------

    tag_bot_left = "footer_bot_left"
    curr_y = -5000
    drawn_bot_left = False
    
    if show_bank_toggle or show_terms_toggle:
        ctx["cvs"].create_line(x_off + pad, curr_y, x_off + pad + term_col_w, curr_y, fill="#000000", tags=(tag_bot_left,))
        curr_y += s(8)
        
    if show_bank_toggle:
        qr_top_y = curr_y 
        curr_y = c_txt(x_off + pad, curr_y, "Bank Details:", "bank_lbl", tags=(tag_bot_left,))
        
        bank_data = None
        if hasattr(sv, 'banks_list') and sv.banks_list:
            for b in sv.banks_list:
                if b.get("is_default"): 
                    bank_data = b
                    break
            if not bank_data: bank_data = sv.banks_list[0]
            
        bank_str = "(Add a bank account in settings configuration layout profile)"
        qr_path = ""
        
        qr_path = ""
        if bank_data:
            bank_str = f"Bank: {bank_data.get('name', '')}\nA/C Name: {bank_data.get('ac_name', c_name)}\nA/C No: {bank_data.get('ac', '')}\nIFSC: {bank_data.get('ifsc', '')}\nBranch: {bank_data.get('branch', '')}"
            if bank_data.get('pan'): bank_str += f"\nPAN: {bank_data.get('pan', '')}"
            qr_path = bank_data.get("qr_path", "")
            
        has_qr = bool(qr_path and os.path.exists(qr_path))
        
        # --- THE FIX: Hard-squeeze the text boundary by 100 pixels ---
        text_w = term_col_w - s(110) if has_qr else term_col_w
        curr_y = c_txt(x_off + pad, curr_y + s(2), bank_str, "bank_val", width=text_w, tags=(tag_bot_left,))
        
        if has_qr:
            try:
                from PIL import Image, ImageTk
                img = Image.open(qr_path)
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                
                # --- THE FIX: Lock the QR size to exactly 85px ---
                qr_size = s(110)
                # -------------------------------------------------
                
                img = img.resize((qr_size, qr_size), resample_filter)
                sv.invoice_qr_preview_img = ImageTk.PhotoImage(img) 
                ctx["cvs"].create_image(x_off + pad + term_col_w - s(5), qr_top_y, image=sv.invoice_qr_preview_img, anchor="ne", tags=(tag_bot_left,))
            except Exception as e:
                pass
                
        curr_y += s(10)
        drawn_bot_left = True
        
    if show_terms_toggle:
        valid_terms = [t.get().strip() for t in sv.terms_vars if t.get().strip()]
        if valid_terms:
            if show_bank_toggle:
                ctx["cvs"].create_line(x_off + pad, curr_y, x_off + pad + term_col_w, curr_y, fill="#000000", tags=(tag_bot_left,))
                curr_y += s(8)
            curr_y = c_txt(x_off + pad, curr_y, "Terms & Conditions:", "terms_lbl", tags=(tag_bot_left,))
            curr_y += s(4)
            
            for i, val in enumerate(valid_terms):
                c_txt(x_off + pad, curr_y, f"{i+1}.", "terms_val", tags=(tag_bot_left,))
                curr_y = c_txt(x_off + pad + s(18), curr_y, val, "terms_val", width=term_col_w - s(18), tags=(tag_bot_left,))
                curr_y += s(2)
            drawn_bot_left = True

    if drawn_bot_left:
        bbox_bot_left = ctx["cvs"].bbox(tag_bot_left)
        if bbox_bot_left:
            ctx["cvs"].move(tag_bot_left, 0, bottom_limit - bbox_bot_left[3])