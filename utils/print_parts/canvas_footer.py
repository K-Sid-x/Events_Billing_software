import os
import database
try:
    from PIL import Image, ImageTk
except ImportError:
    pass

from utils.print_parts.helpers import format_currency

def draw_footer(ctx):
    st = ctx["state"]; s = ctx["s"]; c_txt = ctx["c_txt"]; cxs = st["cxs"]
    h = ctx["h"]; pad = ctx["pad"]; x_off = ctx["x_off"]; w = ctx["w"]
    inv = ctx["studio"].inv_data
    
    f_y = st["y_off"] + h - ctx["final_footer_res"]
    
    for cx in cxs: ctx["cvs"].create_line(cx, st["t_start"] - s(30), cx, f_y, fill="#000000")
    ctx["cvs"].create_line(x_off + pad, f_y, x_off + w - pad, f_y, fill="#000000")

    left_y = f_y + s(5)
    left_y = c_txt(x_off + pad, left_y, "Amount in Words:", "amt_words_lbl")
    left_y = c_txt(x_off + pad, left_y + s(2), ctx["words_val"], "amt_words_val", width=int(w * 0.55))
    
    term_col_w = int(w * 0.40)
    has_banks = bool(ctx["studio"].banks_data)
    
    if has_banks:
        left_y += s(8)
        ctx["cvs"].create_line(x_off + pad, left_y, x_off + pad + term_col_w, left_y, fill="#000000")
        left_y += s(8)
        
        qr_top_y = left_y
        left_y = c_txt(x_off + pad, left_y, "Bank Details:", "bank_lbl")
        
        b_data = ctx["studio"].banks_data[0]
        c_name_val = ctx["studio"].comp_dict.get('name', '').upper()
        bank_str = f"Bank: {b_data.get('name', '')}\nA/C Name: {b_data.get('ac_name') or c_name_val}\nA/C No: {b_data.get('ac', '')}\nIFSC: {b_data.get('ifsc', '')}\nBranch: {b_data.get('branch', '')}"
        if b_data.get('pan'): bank_str += f"\nPAN: {b_data.get('pan', '')}"
        
        qr_path = b_data.get("qr_path", "")
        has_qr = bool(qr_path and os.path.exists(qr_path))
        
        # --- THE FIX: Hard-squeeze the text boundary by 100 pixels ---
        text_w = term_col_w - s(110) if has_qr else term_col_w
        left_y = c_txt(x_off + pad, left_y + s(2), bank_str, "bank_val", width=text_w)
        
        if has_qr:
            try:
                from PIL import Image, ImageTk
                img = Image.open(qr_path)
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                
                # --- THE FIX: Lock the QR size to exactly 85px to stop the dynamic overlap! ---
                qr_size = s(110)
                # ------------------------------------------------------------------------------
                
                img = img.resize((qr_size, qr_size), resample_filter)
                tk_qr_img = ImageTk.PhotoImage(img)
                if not hasattr(ctx["studio"], '_canvas_img_cache'):
                    ctx["studio"]._canvas_img_cache = []
                ctx["studio"]._canvas_img_cache.append(tk_qr_img)
                ctx["cvs"].create_image(x_off + pad + term_col_w - s(5), qr_top_y, image=tk_qr_img, anchor="ne")
            except Exception: pass

    # --- THE FIX: Securely read GST status from memory! ---
    has_gst = bool(ctx["studio"].comp_dict.get('gst', ''))
    # ------------------------------------------------------

    tx = x_off + w - pad
    lbl_x = tx - s(120)
    right_y = f_y + s(5)
    
    show_discount = int(inv.get("inc_discount", 0)) == 1
    show_advance = int(inv.get("inc_advance", 0)) == 1
    sub_val = ctx["parse_f"](inv.get("subtotal", 0))
    disc_val = ctx["parse_f"](inv.get("discount_amt", 0))
    taxable_val = sub_val - disc_val if show_discount else sub_val
    cgst_val = ctx["parse_f"](inv.get("cgst", 0))
    sgst_val = ctx["parse_f"](inv.get("sgst", 0))
    igst_val = ctx["parse_f"](inv.get("igst", 0))
    grand_tot = ctx["parse_f"](inv.get("total", 0))
    raw_tot = taxable_val + (igst_val if hasattr(ctx["studio"], 'gst_type') and ctx["studio"].gst_type.get() == "IGST" else cgst_val + sgst_val)
    is_igst = hasattr(ctx["studio"], 'gst_type') and ctx["studio"].gst_type.get() == "IGST"
    
    c_txt(lbl_x, right_y, "Sub Total :", "totals", anchor="ne")
    right_y = c_txt(tx, right_y, format_currency(sub_val, ctx["curr_format"]), "totals", anchor="ne")
    
    if show_discount:
        c_txt(lbl_x, right_y, "Discount :", "totals", anchor="ne")
        right_y = c_txt(tx, right_y, "- " + format_currency(disc_val, ctx["curr_format"]), "totals", anchor="ne")
        c_txt(lbl_x, right_y, "Taxable Amt :", "totals", anchor="ne")
        right_y = c_txt(tx, right_y, format_currency(taxable_val, ctx["curr_format"]), "totals", anchor="ne")
        
    if has_gst:
        if is_igst:
            ig_r = inv.get("igst_rate", "18")
            c_txt(lbl_x, right_y, f"IGST @ {ig_r}% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, format_currency(igst_val, ctx["curr_format"]), "totals", anchor="ne")
        else:
            cg_r = inv.get("cgst_rate", "9")
            sg_r = inv.get("sgst_rate", "9")
            c_txt(lbl_x, right_y, f"CGST @ {cg_r}% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, format_currency(cgst_val, ctx["curr_format"]), "totals", anchor="ne")
            c_txt(lbl_x, right_y, f"SGST @ {sg_r}% :", "totals", anchor="ne")
            right_y = c_txt(tx, right_y, format_currency(sgst_val, ctx["curr_format"]), "totals", anchor="ne")
        
    c_txt(lbl_x, right_y, "Round Off +/- :", "totals", anchor="ne")
    right_y = c_txt(tx, right_y, format_currency(grand_tot - raw_tot, ctx["curr_format"]), "totals", anchor="ne")
    
    line_y = right_y + s(4)
    if show_advance:
        adv_val = ctx["parse_f"](inv.get("advance_val", 0))
        ctx["cvs"].create_rectangle(tx - s(200), line_y, tx, line_y + max(1, s(1)), fill="#000000", outline="")
        gt_y = line_y + s(6)
        c_txt(lbl_x, gt_y, "Total Amount :", "totals", anchor="ne")
        gt_y = c_txt(tx, gt_y, format_currency(grand_tot, ctx["curr_format"]), "totals", anchor="ne")
        c_txt(lbl_x, gt_y, "Advance Paid :", "totals", anchor="ne")
        gt_y = c_txt(tx, gt_y, "- " + format_currency(adv_val, ctx["curr_format"]), "totals", anchor="ne")
        
        line_y2 = gt_y + s(4)
        ctx["cvs"].create_rectangle(tx - s(200), line_y2, tx, line_y2 + max(1, s(1)), fill="#000000", outline="")
        bal_y = line_y2 + s(6)
        c_txt(lbl_x, bal_y, "Balance Due :", "totals", bold=True, anchor="ne")
        c_txt(tx, bal_y, format_currency(grand_tot - adv_val, ctx["curr_format"]), "totals", bold=True, anchor="ne")
    else:
        ctx["cvs"].create_rectangle(tx - s(200), line_y, tx, line_y + max(1, s(1)), fill="#000000", outline="")
        gt_y = line_y + s(6)
        c_txt(lbl_x, gt_y, "Grand Total :", "totals", bold=True, anchor="ne")
        gt_y = c_txt(tx, gt_y, format_currency(grand_tot, ctx["curr_format"]), "totals", bold=True, anchor="ne")
        line_y2 = gt_y + s(4)
        ctx["cvs"].create_rectangle(tx - s(200), line_y2, tx, line_y2 + max(1, s(1)), fill="#000000", outline="")

    bottom_limit = st["y_off"] + h - s(15)
    c_txt(x_off + w/2, bottom_limit, f"Page {st['page_count']}", "page_no", anchor="s")

    c_name = ctx["studio"].comp_dict.get('name', '').upper()
    sel_sig = str(inv.get("selected_sig", "")).strip()
    sigs = ctx["studio"].settings.get("signatures", [])
    sig_data = None
    if sel_sig:
        for s_obj in sigs:
            if str(s_obj.get("role", "")).strip() == sel_sig:
                sig_data = s_obj
                break

    sig_path = str(sig_data.get("path", "")).strip() if sig_data else ""
    sig_role = str(sig_data.get("role", "")).strip() if sig_data else ""
    if not sig_role or sig_role == "--Select--": sig_role = "Authorised Signatory"
    show_esign = int(ctx["studio"].settings.get("show_esign", 1)) == 1

    tag_sig = "footer_sig"
    sig_y = -5000
    
    ctx["cvs"].delete("dummy_sig_meas")
    c_txt(-5000, -5000, f"For {c_name}", "signature", tags=("dummy_sig_meas",))
    c_txt(-5000, -5000, sig_role, "signature", tags=("dummy_sig_meas",))
    bbox_meas = ctx["cvs"].bbox("dummy_sig_meas")
    max_w = (bbox_meas[2] - bbox_meas[0]) if bbox_meas else 0
    ctx["cvs"].delete("dummy_sig_meas")

    img_h, img_w = 0, 0
    if show_esign and sig_path and os.path.exists(sig_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(sig_path)
            try: sig_scale = float(ctx["studio"].settings.get("sig_scale", 100)) / 100.0
            except: sig_scale = 1.0
            
            base_h = s(45)
            img_h = int(base_h * sig_scale)
            img_w = int(img_h * (img.width / img.height))
            max_w = max(max_w, img_w)
        except Exception: pass

    sig_center_x = tx - (max_w / 2)

    if show_esign:
        # 1. Draw "For Company" first at the top
        sig_y = c_txt(sig_center_x, -5000, f"For {c_name}", "signature", anchor="n", tags=(tag_sig,))
        
        # --- THE FIX: Fetch the Nudge from settings! ---
        try: sig_nudge = int(ctx["studio"].settings.get("sig_nudge", 0))
        except: sig_nudge = 0
        # -----------------------------------------------
        
        # 2. Draw the signature image directly underneath
        if img_w > 0 and img_h > 0:
            try:
                from PIL import Image, ImageTk
                img = Image.open(sig_path)
                resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                img = img.resize((img_w, img_h), resample)
                tk_img = ImageTk.PhotoImage(img)
                if not hasattr(ctx["studio"], '_canvas_img_cache'): ctx["studio"]._canvas_img_cache = []
                ctx["studio"]._canvas_img_cache.append(tk_img) 
                
                # --- THE FIX: Apply the Nudge to the Y-axis! ---
                img_y = sig_y + s(sig_nudge)
                ctx["cvs"].create_image(sig_center_x, img_y, image=tk_img, anchor="n", tags=(tag_sig,))
                # -----------------------------------------------
                
                sig_y += img_h + s(2)
            except Exception:
                sig_y += s(45) + s(2) # Keep gap if image fails
        else:
            # --- THE FIX: Force a 45px gap (100% scale) for manual pen signatures! ---
            sig_y += s(45) + s(2) 
            # -------------------------------------------------------------------------
                
        # 3. Draw the Role at the very bottom
        if sig_role: c_txt(sig_center_x, sig_y, sig_role, "signature", anchor="n", tags=(tag_sig,))
        
        bbox_sig = ctx["cvs"].bbox(tag_sig)
        if bbox_sig:
            target_bottom = bottom_limit - s(5) if (img_w > 0 and img_h > 0) else bottom_limit
            ctx["cvs"].move(tag_sig, 0, target_bottom - bbox_sig[3])
    else:
        if sig_role: c_txt(sig_center_x, bottom_limit, sig_role, "signature", anchor="s", tags=(tag_sig,))
        # --- THE FIX: Pushes 'For Company Name' up by 60px to leave room for a physical pen signature ---
        c_txt(sig_center_x, bottom_limit - s(60), f"For {c_name}", "signature", anchor="s", tags=(tag_sig,))
        # ------------------------------------------------------------------------------------------------

    tag_bot_left = "footer_terms"
    curr_y = -5000
    drawn_bot_left = False
    
    inc_terms = int(inv.get("inc_terms", 1))
    valid_terms = []
    if inc_terms == 1:
        valid_terms = [t.strip() for t in ctx["studio"].settings.get("terms_list", []) if t.strip()]
        if not valid_terms and ctx["studio"].settings.get("term1"): valid_terms.append(ctx["studio"].settings.get("term1"))

    if valid_terms:
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
        if bbox_bot_left: ctx["cvs"].move(tag_bot_left, 0, bottom_limit - bbox_bot_left[3])