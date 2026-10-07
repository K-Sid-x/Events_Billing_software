import tkinter as tk
import os
import re
import sys

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

try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps
except ImportError:
    pass

from views.purchase_parts.print_studio.purch_preview_meta import draw_purch_meta

def render_purch_preview(sv):
    sv.cvs.delete("all")
    cvs_w = sv.cvs.winfo_width()
    if cvs_w < 50: return 
    
    base_w = 794; base_h = 1123
    
    # --- THE FIX: Cache the GST toggle to eliminate Database Lag when scrolling! ---
    if not hasattr(sv, 'cached_has_gst'):
        comp_id = getattr(sv, "comp_id", 1)
        c_db = database.get_company(comp_id)
        sv.cached_has_gst = (c_db and c_db[8] == 1)
    has_gst = sv.cached_has_gst
    # -------------------------------------------------------------------------------
    
    z = sv.zoom_var.get() / 100.0 if hasattr(sv, 'zoom_var') else 1.0
    sf = (cvs_w - 40) / base_w if z == 1.0 else z
    if sf > 1 and z == 1.0: sf = 1.0 
    
    paper_w = int(base_w * sf)
    paper_h = int(base_h * sf)
    
    x_off = (cvs_w - paper_w) // 2
    if x_off < 20: x_off = 20
    
    has_actual_data = hasattr(sv, 'actual_bill_data') and sv.actual_bill_data
    
    is_split = False
    if hasattr(sv, "prev_split_var"):
        is_split = sv.prev_split_var.get() == 1

    def s(val): return int(val * sf)
    
    primary = sv.colors.get("primary_color", tk.StringVar(value="#0f172a")).get()
    head_bg = sv.colors.get("tab_head_bg", tk.StringVar(value="#475569")).get()
    font_fam = sv.font_family.get()

    def c_txt(x, y, text, key, anchor="nw", max_w=None, force_bold=False, force_underline=False, shrink_fit=False, pad_bot=4):
        if not text: return y
        try: f_sz = max(4, int(int(float(sv.fonts[key].get() or 10)) * sf))
        except: f_sz = max(4, int(10 * sf))
        
        mods = []
        if (key in sv.bolds and sv.bolds[key].get()) or force_bold: mods.append("bold")
        if (key in sv.underlines and sv.underlines[key].get()) or force_underline: mods.append("underline")
        f_str = " ".join(mods)
        
        just = tk.LEFT
        if "center" in anchor or anchor in ["n", "s"]: just = tk.CENTER
        elif "e" in anchor: just = tk.RIGHT

        color = sv.colors[key].get() if key in sv.colors else "#000000"

        if shrink_fit and max_w:
            actual_f_sz = f_sz
            f_tup = (font_fam, actual_f_sz, f_str) if f_str else (font_fam, actual_f_sz)
            t_id = sv.cvs.create_text(x, y, text=text, font=f_tup, fill=color, anchor=anchor, justify=just)
            
            bbox = sv.cvs.bbox(t_id)
            while bbox and (bbox[2] - bbox[0]) > max_w and actual_f_sz > 5:
                actual_f_sz -= 1
                f_tup = (font_fam, actual_f_sz, f_str) if f_str else (font_fam, actual_f_sz)
                sv.cvs.itemconfig(t_id, font=f_tup)
                bbox = sv.cvs.bbox(t_id)
        else:
            f_tup = (font_fam, f_sz, f_str) if f_str else (font_fam, f_sz)
            t_id = sv.cvs.create_text(x, y, text=text, font=f_tup, fill=color, anchor=anchor, width=max_w if max_w else 0, justify=just)
            
        bbox = sv.cvs.bbox(t_id)
        return bbox[3] + s(pad_bot) if bbox else y + f_sz + s(pad_bot)

    tk_logo = None
    draw_w = 0
    
    # --- THE FIX: Catch the NameError if PIL failed to load so the Print Studio doesn't crash! ---
    try:
        try: resamp = Image.Resampling.LANCZOS
        except AttributeError: resamp = Image.LANCZOS
    except NameError:
        pass

    try:
        l_sz = s(int(float(sv.logo_size_var.get() or 120)))
        if sv.logo_path_var.get() and os.path.exists(sv.logo_path_var.get()):
            img = Image.open(sv.logo_path_var.get()).convert("RGBA")
            if sv.logo_shape_var.get() in ["Square", "Circle"]:
                img = ImageOps.fit(img, (l_sz, l_sz), method=resamp)
                if sv.logo_shape_var.get() == "Circle":
                    mask_sz = (l_sz * 3, l_sz * 3) 
                    mask = Image.new('L', mask_sz, 0)
                    from PIL import ImageDraw as D
                    draw = D.Draw(mask)
                    draw.ellipse((0, 0) + mask_sz, fill=255)
                    mask = mask.resize((l_sz, l_sz), resamp)
                    img_circle = Image.new('RGBA', (l_sz, l_sz), (0, 0, 0, 0))
                    img_circle.paste(img, (0, 0), mask=mask)
                    img = img_circle
            else:
                ratio = img.width / img.height
                new_w = l_sz; new_h = int(l_sz / ratio)
                if new_h > l_sz: new_h = l_sz; new_w = int(l_sz * ratio)
                img = img.resize((new_w, new_h), resamp)
            tk_logo = ImageTk.PhotoImage(img)
            sv.tk_logo = tk_logo 
            draw_w = img.width
    except Exception as e: pass

    c_name = sv.name_var.get()
    c_sec = sv.sec_var.get()
    c_addr = sv.addr_var.get()
    c_gst = sv.gst_var.get() if has_gst else ""
    swap = sv.swap_title_order_var.get() == 1
    
    def fmt_ph(p):
        p = str(p).strip()
        if len(p) == 10 and p.isdigit(): return f"{p[:5]}-{p[5:]}"
        return p

    phones = [fmt_ph(p) for p in [sv.p1_var.get(), sv.p2_var.get(), sv.p3_var.get()] if p]
    ph_str = "\n".join(phones)
    c_email = sv.email_var.get()
    contact_stack = ""
    if ph_str: contact_stack += f"Ph: {ph_str}"
    if c_email: contact_stack += f"\nEmail: {c_email}"

    c_fmt = getattr(sv, "currency_format", "Indian")
    c_sym = getattr(sv, "currency_sym", "₹")

    def fmt_num(val):
        try: v = float(val)
        except: v = 0.0
        is_neg = v < 0
        v = abs(v)
        s_val = f"{v:.2f}"
        int_part, dec_part = s_val.split('.')
        if "Indian" in c_fmt:
            if len(int_part) > 3:
                last_3 = int_part[-3:]
                rem = int_part[:-3]
                rem = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", rem)
                int_part = rem + "," + last_3
        else:
            int_part = f"{int(int_part):,}"
        res = f"{int_part}.{dec_part}"
        return f"-{res}" if is_neg else res

    all_items = []
    if has_actual_data:
        for i, it in enumerate(sv.actual_bill_data['items'], 1):
            raw_name = str(it.get('name', ''))
            
            # --- THE FIX: Smartly parse quantity so blanks stay blank! ---
            try:
                q_val = float(it.get('qty', 0))
                q_str = f"{q_val:g} " if q_val > 0.001 else ""
            except:
                q_str = ""
                
            u_str = str(it.get('unit', '')).strip()
            display_qty = f"{q_str}{u_str}".strip()
            # -------------------------------------------------------------
            
            if has_gst:
                all_items.append([
                    str(i), raw_name, it['hsn'], display_qty, 
                    f"{it['gst']:g}%", f"{c_sym} {fmt_num(it['rate_inc'])}", 
                    f"{c_sym} {fmt_num(it['rate'])}", f"{c_sym} {fmt_num(it['amt'])}"
                ])
            else:
                all_items.append([
                    str(i), raw_name, display_qty, 
                    f"{c_sym} {fmt_num(it['rate'])}", f"{c_sym} {fmt_num(it['amt'])}"
                ])
    else:
        base_10 = [
            ["1", "Premium Sofa Component With Extended Long Text That Forces A Word Wrap To Prove It Works Perfectly", "12345678", "10 Nos", "18%", f"{c_sym} 1,180.00", f"{c_sym} 1,000.00", f"{c_sym} 10,000.00"],
            ["2", "Standard Chair Leg", "87654321", "40 Pcs", "18%", f"{c_sym} 118.00", f"{c_sym} 100.00", f"{c_sym} 4,000.00"],
            ["3", "Velvet Cushion Fabric", "12345678", "20 Mtr", "18%", f"{c_sym} 590.00", f"{c_sym} 500.00", f"{c_sym} 10,000.00"],
            ["4", "Wooden Table Frame", "44079990", "5 Nos", "12%", f"{c_sym} 2,240.00", f"{c_sym} 2,000.00", f"{c_sym} 10,000.00"],
            ["5", "Steel Screws Box", "73181500", "15 Box", "18%", f"{c_sym} 236.00", f"{c_sym} 200.00", f"{c_sym} 3,000.00"]
        ]
        for i in range(150):
            row = list(base_10[i % 5])
            row[0] = str(i + 1)
            if not has_gst:
                row = [row[0], row[1], row[3], row[6], row[7]]
            all_items.append(row)

    w_sl = sv.w_slno.get() / 100.0; w_qty = sv.w_qty.get() / 100.0
    w_r = sv.w_rate.get() / 100.0; w_a = sv.w_amt.get() / 100.0
    
    if has_gst:
        w_hsn = sv.w_hsn.get() / 100.0; w_gst = sv.w_gst.get() / 100.0; w_r_inc = sv.w_rate_inc.get() / 100.0
        w_part = 1.0 - sum([w_sl, w_hsn, w_qty, w_gst, w_r_inc, w_r, w_a])
        if w_part < 0.1: w_part = 0.1 
        cols = [
            ("SI No", "th_slno", "tr_slno", "1", "center", w_sl),
            ("Particulars", "th_part", "tr_part", "Premium Sofa Component", "w", w_part),
            ("HSN/SAC", "th_hsn", "tr_hsn", "12345678", "center", w_hsn),
            ("Qnty/\nUnits", "th_qty", "tr_qty", "10 Nos", "center", w_qty),
            ("GST %", "th_gst", "tr_gst", "18%", "center", w_gst),
            ("Rate\n(Inc Tax)", "th_rate_inc", "tr_rate_inc", f"{c_sym} 1,180.00", "e", w_r_inc),
            ("Base Rate", "th_rate", "tr_rate", f"{c_sym} 1,000.00", "e", w_r),
            ("Amount", "th_amt", "tr_amt", f"{c_sym} 10,000.00", "e", w_a)
        ]
    else:
        w_part = 1.0 - sum([w_sl, w_qty, w_r, w_a])
        if w_part < 0.1: w_part = 0.1
        cols = [
            ("SI No", "th_slno", "tr_slno", "1", "center", w_sl),
            ("Particulars", "th_part", "tr_part", "Premium Sofa Component", "w", w_part),
            ("Qnty/\nUnits", "th_qty", "tr_qty", "10 Nos", "center", w_qty),
            ("Rate", "th_rate", "tr_rate", f"{c_sym} 1,000.00", "e", w_r),
            ("Amount", "th_amt", "tr_amt", f"{c_sym} 10,000.00", "e", w_a)
        ]
    
    pad = s(20)
    cxs = [x_off + pad]
    for _, _, _, _, _, pct in cols: 
        cxs.append(cxs[-1] + (paper_w - pad*2) * pct)
        
    is_interstate = False
    num_tax_rows = 0
    if has_gst:
        if has_actual_data:
            is_interstate = sv.actual_bill_data['is_interstate']
            h_sum = sv.actual_bill_data['hsn_summary']
            num_tax_rows = len(h_sum)
            
            tax_cols = [
                ("SI No", 0.05, [str(i+1) for i in range(len(h_sum))], "", "center"),
                ("HSN/SAC", 0.15, [r['hsn'] for r in h_sum], "Total", "center"),
                ("TAXABLE VAL", 0.16, [f"{c_sym} {fmt_num(r['taxable'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['taxable'] for r in h_sum))}", "right")
            ]
            if is_interstate:
                tax_cols.extend([
                    ("IGST %", 0.10, [f"{r['igst_rate']:g}%" for r in h_sum], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} {fmt_num(r['igst_amt'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['igst_amt'] for r in h_sum))}", "right"),
                    ("TOTAL TAX", 0.22, [f"{c_sym} {fmt_num(r['total_tax'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['total_tax'] for r in h_sum))}", "right")
                ])
            else:
                tax_cols.extend([
                    ("CGST %", 0.09, [f"{r['cgst_rate']:g}%" for r in h_sum], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} {fmt_num(r['cgst_amt'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['cgst_amt'] for r in h_sum))}", "right"),
                    ("SGST %", 0.09, [f"{r['sgst_rate']:g}%" for r in h_sum], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} {fmt_num(r['sgst_amt'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['sgst_amt'] for r in h_sum))}", "right"),
                    ("TOTAL TAX", 0.22, [f"{c_sym} {fmt_num(r['total_tax'])}" for r in h_sum], f"{c_sym} {fmt_num(sum(r['total_tax'] for r in h_sum))}", "right")
                ])
        else:
            if is_split:
                num_tax_rows = 6
                tax_cols = [
                    ("SI No", 0.05, ["1", "2", "3", "4", "5", "6"], "", "center"),
                    ("HSN/SAC", 0.15, ["12345678", "87654321", "44079990", "11223344", "55667788", "99887766"], "Total", "center"),
                    ("TAXABLE VAL", 0.16, [f"{c_sym} 10,000.00", f"{c_sym} 7,000.00", f"{c_sym} 10,000.00", f"{c_sym} 5,500.00", f"{c_sym} 6,000.00", f"{c_sym} 6,000.00"], f"{c_sym} 44,500.00", "right"),
                    ("CGST %", 0.09, ["9%", "9%", "6%", "9%", "6%", "9%"], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} 900.00", f"{c_sym} 630.00", f"{c_sym} 600.00", f"{c_sym} 495.00", f"{c_sym} 360.00", f"{c_sym} 540.00"], f"{c_sym} 3,525.00", "right"),
                    ("SGST %", 0.09, ["9%", "9%", "6%", "9%", "6%", "9%"], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} 900.00", f"{c_sym} 630.00", f"{c_sym} 600.00", f"{c_sym} 495.00", f"{c_sym} 360.00", f"{c_sym} 540.00"], f"{c_sym} 3,525.00", "right"),
                    ("TOTAL TAX", 0.22, [f"{c_sym} 1,800.00", f"{c_sym} 1,260.00", f"{c_sym} 1,200.00", f"{c_sym} 990.00", f"{c_sym} 720.00", f"{c_sym} 1,080.00"], f"{c_sym} 7,050.00", "right")
                ]
            else:
                num_tax_rows = 3
                tax_cols = [
                    ("SI No", 0.05, ["1", "2", "3"], "", "center"),
                    ("HSN/SAC", 0.15, ["12345678", "87654321", "44079990"], "Total", "center"),
                    ("TAXABLE VAL", 0.16, [f"{c_sym} 27,500.00", f"{c_sym} 7,000.00", f"{c_sym} 10,000.00"], f"{c_sym} 44,500.00", "right"),
                    ("CGST %", 0.09, ["9%", "9%", "6%"], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} 2,475.00", f"{c_sym} 630.00", f"{c_sym} 600.00"], f"{c_sym} 3,705.00", "right"),
                    ("SGST %", 0.09, ["9%", "9%", "6%"], "", "center"),
                    ("AMOUNT", 0.12, [f"{c_sym} 2,475.00", f"{c_sym} 630.00", f"{c_sym} 600.00"], f"{c_sym} 3,705.00", "right"),
                    ("TOTAL TAX", 0.22, [f"{c_sym} 4,950.00", f"{c_sym} 1,260.00", f"{c_sym} 1,200.00"], f"{c_sym} 7,410.00", "right")
                ]

    th_h = s(18); r_h = s(18)
    tax_title_h = s(25)
    tax_block_h = tax_title_h + th_h + (num_tax_rows * r_h) + r_h if num_tax_rows > 0 else 0
    
    footer_footprint = s(220) + tax_block_h 

    sv.page_wrappers = []
    item_index = 0
    running_total = 0.0 
    p = 0
    drawing_complete = False

    while not drawing_complete:
        y_off = 20 + p * (paper_h + 20)
        sv.page_wrappers.append(y_off)
        cy = y_off + pad

        sv.cvs.create_rectangle(x_off+5, y_off+5, x_off+paper_w+5, y_off+paper_h+5, fill="#323232", outline="")
        sv.cvs.create_rectangle(x_off, y_off, x_off+paper_w, y_off+paper_h, fill="#ffffff", outline="#cccccc")

        layout = sv.layout_var.get()
        t_y_start = cy
        logo_y_end = t_y_start

        if tk_logo:
            if layout in ["Split Header (Left-Center-Right)", "Left-Aligned", "Classic"]: lx = x_off + pad
            elif layout == "Right-Aligned": lx = x_off + paper_w - pad - draw_w
            else: lx = x_off + pad
            sv.cvs.create_image(lx, t_y_start, image=tk_logo, anchor="nw")
            logo_y_end = t_y_start + tk_logo.height()

        c_max_w = s(450)
        if layout == "Split Header (Left-Center-Right)":
            center_x = x_off + paper_w / 2
            right_x = x_off + paper_w - pad
            t_y = t_y_start
            
            if swap:
                if c_sec: t_y = c_txt(center_x, t_y, c_sec, "sec", anchor="n", max_w=c_max_w) + s(4)
                t_y = c_txt(center_x, t_y, c_name, "name", anchor="n", max_w=c_max_w) + s(4)
            else:
                t_y = c_txt(center_x, t_y, c_name, "name", anchor="n", max_w=c_max_w) + s(4)
                if c_sec: t_y = c_txt(center_x, t_y, c_sec, "sec", anchor="n", max_w=c_max_w) + s(4)
                
            t_y = c_txt(center_x, t_y, c_addr, "addr", anchor="n", max_w=c_max_w) + s(4)
            if c_gst: t_y = c_txt(center_x, t_y, f"GSTIN: {c_gst}", "gst", anchor="n") + s(4)
            right_y = c_txt(right_x, t_y_start, contact_stack, "contact", anchor="ne")
            max_header_y = max(logo_y_end, t_y, right_y)
        else: 
            if layout == "Left-Aligned":
                t_x = x_off + pad + ((draw_w + pad) if tk_logo else 0); t_anc = "nw"
            else: 
                t_x = x_off + paper_w - pad - ((draw_w + pad) if tk_logo else 0) if layout == "Right-Aligned" else x_off + paper_w - pad; t_anc = "ne"

            t_y = t_y_start
            if swap:
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc, max_w=c_max_w) + s(4)
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc, max_w=c_max_w) + s(4)
            else:
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc, max_w=c_max_w) + s(4)
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc, max_w=c_max_w) + s(4)
                
            t_y = c_txt(t_x, t_y, c_addr, "addr", max_w=c_max_w, anchor=t_anc) + s(4)
            if c_gst: t_y = c_txt(t_x, t_y, f"GSTIN: {c_gst}", "gst", anchor=t_anc) + s(4)
            if contact_stack: 
                inline_contact = contact_stack.replace('\n', ' | ')
                t_y = c_txt(t_x, t_y, inline_contact, "contact", anchor=t_anc, max_w=c_max_w) + s(4)
            max_header_y = max(logo_y_end, t_y)

        try: spacing = s(int(float(sv.header_spacing_var.get())))
        except: spacing = s(20)

        cy = max_header_y + spacing
        sv.cvs.create_line(x_off + pad, cy, x_off + paper_w - pad, cy, fill=primary, width=2)
        cy += s(15)

        doc_title = sv.doc_title_var.get().upper()
        cy = c_txt(x_off + paper_w/2, cy, doc_title, "doc_title", anchor="n") + s(15)

        ctx = {
            "sv": sv, "s": s, "c_txt": c_txt, "x_off": x_off, "y_off": y_off, 
            "paper_w": paper_w, "paper_h": paper_h, "c_name": sv.name_var.get(), 
            "c_addr": sv.addr_var.get(), "c_phone": ph_str, "c_email": c_email, "cvs": sv.cvs,
            "has_gst": has_gst
        }
        cy = draw_purch_meta(ctx, cy)
        cy += s(15) 

        ty = cy
        head_h = s(35) 
        
        sv.cvs.create_rectangle(x_off + pad, ty, x_off + paper_w - pad, ty + head_h, fill=head_bg, outline="")
        for cx in cxs: sv.cvs.create_line(cx, ty, cx, ty + head_h, fill=primary, width=1)
            
        for i, (h, hkey, _, _, _, _) in enumerate(cols):
            tx_head = cxs[i] + (cxs[i+1]-cxs[i])/2
            col_max_w = (cxs[i+1] - cxs[i]) - s(6)
            c_txt(tx_head, ty + head_h/2, h, hkey, anchor="center", max_w=col_max_w, shrink_fit=True)
            
        ry = ty + head_h
        
        if p > 0:
            for i, (_, _, rkey, _, anc, _) in enumerate(cols):
                tx = cxs[i] + (cxs[i+1]-cxs[i])/2 if anc == "center" else (cxs[i+1]-s(5) if anc == "e" else cxs[i]+s(5))
                val = ""
                if i == 1: 
                    val = "B/F"
                    anc = "w"
                    tx = cxs[i] + s(5)
                elif i == (7 if has_gst else 4): 
                    val = f"{c_sym} {running_total:,.2f}"
                    anc = "e"
                    tx = cxs[i+1] - s(5)
                if val:
                    col_max_w = (cxs[i+1] - cxs[i]) - s(8)
                    c_txt(tx, ry + s(4), val, rkey, anchor="nw" if anc=="w" else "ne", force_bold=True, max_w=col_max_w, shrink_fit=(i != 1), pad_bot=2)
            ry += s(20)
        
        ry += s(5) 
        
        is_last_page = False
        items_drawn_this_page = 0
        
        while item_index < len(all_items):
            r_data = all_items[item_index]
            
            col_w = (cxs[2] - cxs[1]) - s(8)
            f_sz = max(4, int(10 * sf))
            chars_per_line = max(1, int(col_w / (f_sz * 0.55)))
            
            # --- THE FIX: Accurately calculate lines supporting explicit newlines (Alt+Enter) ---
            name_text = r_data[1]
            total_lines = 0
            for subline in name_text.split('\n'):
                sub_len = len(subline)
                total_lines += max(1, sub_len // chars_per_line + (1 if sub_len % chars_per_line > 0 else 0))
            lines = max(1, total_lines)
            # -----------------------------------------------------------------------------------
            
            predicted_item_h = max(s(16), int(lines * f_sz * 1.2) + s(2))
            
            safe_pad = s(35)
            
            if not has_actual_data:
                target_pages = 2 if is_split else 1
                is_preview_last_page = (p == target_pages - 1)
                
                if is_preview_last_page:
                    required_space = predicted_item_h + footer_footprint + safe_pad
                else:
                    required_space = predicted_item_h + s(80) + safe_pad
            else:
                required_space = predicted_item_h + s(80) + safe_pad
                
            if ry + required_space > y_off + paper_h:
                if items_drawn_this_page > 0:
                    if not has_actual_data and is_preview_last_page:
                        all_items = all_items[:item_index]
                    break 
                
            row_bottom_y = ry + s(14) 
            
            for i, (_, _, rkey, _, anc, _) in enumerate(cols):
                col_max_w = (cxs[i+1] - cxs[i]) - s(8)
                if col_max_w < 5: col_max_w = 5
                
                if i == 1:
                    curr_line_y = ry + s(2)
                    raw_particulars = str(r_data[1])
                    for line in raw_particulars.split('\n'):
                        l_b = "@@B@@" in line or "[B]" in line
                        l_u = "@@U@@" in line or "[U]" in line
                        c_line = line.replace("@@B@@", "").replace("@@U@@", "")
                        c_line = re.sub(r'\[/?(B|U)\]', '', c_line)
                        
                        if c_line.strip() == "":
                            curr_line_y += s(12)
                        else:
                            curr_line_y = c_txt(cxs[1] + s(5), curr_line_y, c_line, rkey, anchor="nw", max_w=col_max_w, force_bold=l_b, force_underline=l_u, shrink_fit=False, pad_bot=2)
                    if curr_line_y > row_bottom_y:
                        row_bottom_y = curr_line_y
                else:
                    tx = cxs[i] + (cxs[i+1]-cxs[i])/2 if anc == "center" else (cxs[i+1]-s(5) if anc == "e" else cxs[i]+s(5))
                    is_shrink = (i != 1)
                    cell_end_y = c_txt(tx, ry + s(2), r_data[i], rkey, anchor="n" if anc=="center" else ("ne" if anc=="e" else "nw"), max_w=col_max_w, shrink_fit=is_shrink, pad_bot=2)
                    if cell_end_y > row_bottom_y:
                        row_bottom_y = cell_end_y
                    
            amt_str = r_data[7 if has_gst else 4].replace(c_sym, '').replace(',', '').strip()
            try: running_total += float(amt_str)
            except: pass

            ry = row_bottom_y + s(3) 
            items_drawn_this_page += 1
            item_index += 1
            
        if item_index >= len(all_items):
            if ry + footer_footprint > y_off + paper_h:
                is_last_page = False
            else:
                is_last_page = True
                drawing_complete = True
                
        if not is_last_page:
            table_end_y = y_off + paper_h - s(50)
            cf_y = table_end_y - s(20)
            if ry > cf_y:
                cf_y = ry + s(5)
                table_end_y = cf_y + s(20)
        else:
            table_end_y = y_off + paper_h - footer_footprint
            cf_y = table_end_y
            if ry > table_end_y:
                table_end_y = ry + s(5)
                cf_y = table_end_y
            
        sv.cvs.create_line(x_off + pad, ty, x_off + paper_w - pad, ty, fill=primary, width=2) 
        sv.cvs.create_line(x_off + pad, ty + head_h, x_off + paper_w - pad, ty + head_h, fill=primary, width=2) 
        sv.cvs.create_line(x_off + pad, table_end_y, x_off + paper_w - pad, table_end_y, fill=primary, width=2) 
        
        y_start_lines = ty + head_h
        
        for cx in cxs:
            sv.cvs.create_line(cx, y_start_lines, cx, table_end_y, fill=primary, width=1)

        if not is_last_page:
            sv.cvs.create_line(x_off + pad, cf_y, x_off + paper_w - pad, cf_y, fill=primary, width=1)
            for i, (_, _, rkey, _, anc, _) in enumerate(cols):
                val = ""
                if i == (6 if has_gst else 3): 
                    val = "Total C/F:"
                    anc = "e"
                    tx = cxs[i+1] - s(5)
                elif i == (7 if has_gst else 4):
                    val = f"{c_sym} {running_total:,.2f}"
                    tx = cxs[i+1] - s(5)
                    anc = "e"
                    
                if val:
                    col_max_w = (cxs[i+1] - cxs[i]) - s(8)
                    c_txt(tx, cf_y + s(4), val, rkey, anchor="ne" if anc=="e" else "nw", force_bold=True, max_w=col_max_w, shrink_fit=(i != 1), pad_bot=2)

            sig_bottom = y_off + paper_h - s(15)
            c_txt(x_off + paper_w - pad, sig_bottom, "Contd...", "g_total_lbl", anchor="se")
            c_txt(x_off + paper_w/2, sig_bottom, f"Page {p+1}", "page_num", anchor="s")

        else:
            def get_num_words(n, system="Indian", currency="Rupees"):
                ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
                tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
                def convert_under_1000(num):
                    if num == 0: return ""
                    elif num < 20: return ones[num]
                    elif num < 100: return tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")
                    else: return ones[num // 100] + " Hundred" + (" " + convert_under_1000(num % 100) if num % 100 != 0 else "")

                if n == 0: return f"Zero {currency} Only".title()
                n = int(n)
                words = ""
                if system == "Indian":
                    if n >= 10000000: words += convert_under_1000(n // 10000000) + " Crore "; n %= 10000000
                    if n >= 100000: words += convert_under_1000(n // 100000) + " Lakh "; n %= 100000
                    if n >= 1000: words += convert_under_1000(n // 1000) + " Thousand "; n %= 1000
                    words += convert_under_1000(n)
                else: 
                    if n >= 1000000000: words += convert_under_1000(n // 1000000000) + " Billion "; n %= 1000000000
                    if n >= 1000000: words += convert_under_1000(n // 1000000) + " Million "; n %= 1000000
                    if n >= 1000: words += convert_under_1000(n // 1000) + " Thousand "; n %= 1000
                    words += convert_under_1000(n)
                return f"{words.strip()} {currency} Only".title()

            curr_word = "Rupees"
            if "$" in c_sym: curr_word = "Dollars"
            elif "€" in c_sym: curr_word = "Euros"
            elif "£" in c_sym: curr_word = "Pounds"
            elif "¥" in c_sym: curr_word = "Yen"
            elif "د.إ" in c_sym: curr_word = "Dirhams"

            sub = 70000.00; cgst = 6500.25; sgst = 6500.25; igst = 0.0; round_val = 0.50; tot = 83000.0
            r_sign = "-"
            
            if has_actual_data:
                sub = sv.actual_bill_data['subtotal']
                cgst = sv.actual_bill_data['cgst']
                sgst = sv.actual_bill_data['sgst']
                igst = sv.actual_bill_data['igst']
                tot = sv.actual_bill_data['total']
                round_val = abs(sv.actual_bill_data['round_off'])
                r_sign = "+" if sv.actual_bill_data['round_off'] >= 0 else "-"

            # --- THE FIX: Use the global helper to capture decimals (paise/cents) flawlessly! ---
            from views.invoice_parts.helpers import number_to_words
            word_str = number_to_words(tot)
            # ------------------------------------------------------------------------------------

            ry = table_end_y + s(15)
            tx = x_off + paper_w - pad
            lx = tx - s(140) 
            tot_ry = ry
            
            c_txt(x_off + pad, tot_ry, "Amount (in words)", "amt_w_l", anchor="nw")
            c_txt(x_off + pad, tot_ry + s(16), word_str, "amt_w_v", max_w=s(400), anchor="nw")
            
            c_txt(lx, tot_ry, "Taxable Subtotal:" if has_gst else "Subtotal:", "subtotal_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
            c_txt(tx, tot_ry, f"{c_sym} {fmt_num(sub)}", "subtotal_val", anchor="ne", max_w=s(140), shrink_fit=True)
            tot_ry += s(18)
            
            if has_gst:
                if is_interstate:
                    c_txt(lx, tot_ry, "Total IGST:", "tax_totals_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
                    c_txt(tx, tot_ry, f"{c_sym} {fmt_num(igst)}", "tax_totals_val", anchor="ne", max_w=s(140), shrink_fit=True)
                    tot_ry += s(18)
                else:
                    c_txt(lx, tot_ry, "Total CGST:", "tax_totals_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
                    c_txt(tx, tot_ry, f"{c_sym} {fmt_num(cgst)}", "tax_totals_val", anchor="ne", max_w=s(140), shrink_fit=True)
                    tot_ry += s(18)
                    c_txt(lx, tot_ry, "Total SGST:", "tax_totals_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
                    c_txt(tx, tot_ry, f"{c_sym} {fmt_num(sgst)}", "tax_totals_val", anchor="ne", max_w=s(140), shrink_fit=True)
                    tot_ry += s(18)
            
                # --- THE FIX: Smart label for Returns/Discounts vs normal Round Off ---
                r_lbl = "Less: Return / Disc:" if (r_sign == "-" and round_val > 1.0) else "Round Off:"
                c_txt(lx, tot_ry, r_lbl, "round_off_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
                c_txt(tx, tot_ry, f"{r_sign} {c_sym} {fmt_num(round_val)}", "round_off_val", anchor="ne", max_w=s(140), shrink_fit=True)
                tot_ry += s(18)
            
            tot_ry += s(5)
            line_start_x = tx - s(270) 
            sv.cvs.create_line(line_start_x, tot_ry, tx, tot_ry, fill=primary, width=1)
            tot_ry += s(10)
            
            c_txt(lx, tot_ry, "GRAND TOTAL:", "g_total_lbl", anchor="ne", max_w=s(140), shrink_fit=True)
            c_txt(tx, tot_ry, f"{c_sym} {fmt_num(tot)}", "g_total_val", anchor="ne", max_w=s(140), shrink_fit=True)
            
            tax_title_y = tot_ry + s(25)
            
            if num_tax_rows > 0 and has_gst:
                total_tax_w = paper_w - pad*2
                t_cxs = [x_off + pad]
                for _, pct, _, _, _ in tax_cols: t_cxs.append(t_cxs[-1] + total_tax_w * pct) 
                
                tax_title_bg = sv.colors.get("tax_title_bg", tk.StringVar(value="#ffffff")).get()
                tax_head_bg = sv.colors.get("tax_head_bg", tk.StringVar(value="#e2e8f0")).get()
                
                sv.cvs.create_rectangle(t_cxs[0], tax_title_y, t_cxs[-1], tax_title_y + tax_title_h, fill=tax_title_bg, outline="")
                sv.cvs.create_rectangle(t_cxs[0], tax_title_y + tax_title_h, t_cxs[-1], tax_title_y + tax_title_h + th_h, fill=tax_head_bg, outline="")
                
                c_txt(t_cxs[0] + s(5), tax_title_y + tax_title_h/2, "TAX SUMMARY", "tax_title", anchor="w")
                
                tax_y = tax_title_y + tax_title_h
                
                for i, (h, _, _, _, _) in enumerate(tax_cols):
                    tx_head = t_cxs[i] + (t_cxs[i+1]-t_cxs[i])/2
                    c_txt(tx_head, tax_y + th_h/2, h, "tax_lbl", anchor="center", max_w=(t_cxs[i+1]-t_cxs[i])-s(4), shrink_fit=True)
                    
                for r_idx in range(num_tax_rows):
                    curr_y = tax_y + th_h + (r_idx * r_h)
                    for i, (_, _, vals, _, align) in enumerate(tax_cols):
                        if align == "left": tx_val = t_cxs[i] + s(5); anc = "w"
                        elif align == "right": tx_val = t_cxs[i+1] - s(5); anc = "e"
                        else: tx_val = t_cxs[i] + (t_cxs[i+1]-t_cxs[i])/2; anc = "center"
                        c_txt(tx_val, curr_y + r_h/2, vals[r_idx], "tax_val", anchor=anc, max_w=(t_cxs[i+1]-t_cxs[i])-s(4), shrink_fit=True)
                        
                tot_y = tax_y + th_h + (num_tax_rows * r_h)
                
                for i, (_, _, _, tot_val, align) in enumerate(tax_cols):
                    if tot_val:
                        font_key = "tax_sum_tot_lbl" if tot_val == "Total" else "tax_sum_tot_val"
                        if tot_val == "Total": tx_draw = t_cxs[i+1] - s(5); anc = "e"
                        else:
                            if align == "left": tx_draw = t_cxs[i] + s(5); anc = "w"
                            elif align == "right": tx_draw = t_cxs[i+1] - s(5); anc = "e"
                            else: tx_draw = t_cxs[i] + (t_cxs[i+1]-t_cxs[i])/2; anc = "center"
                        c_txt(tx_draw, tot_y + r_h/2, tot_val, font_key, anchor=anc, max_w=(t_cxs[i+1]-t_cxs[i])-s(4), shrink_fit=True)

                sv.cvs.create_line(t_cxs[0], tax_title_y, t_cxs[-1], tax_title_y, fill=primary, width=1) 
                sv.cvs.create_line(t_cxs[0], tax_title_y, t_cxs[0], tax_title_y + tax_block_h, fill=primary, width=1) 
                sv.cvs.create_line(t_cxs[-1], tax_title_y, t_cxs[-1], tax_title_y + tax_block_h, fill=primary, width=1) 
                sv.cvs.create_line(t_cxs[0], tax_title_y + tax_block_h, t_cxs[-1], tax_title_y + tax_block_h, fill=primary, width=1) 
                sv.cvs.create_line(t_cxs[0], tax_y, t_cxs[-1], tax_y, fill=primary, width=1)
                sv.cvs.create_line(t_cxs[0], tax_y + th_h, t_cxs[-1], tax_y + th_h, fill=primary, width=1)
                for r_idx in range(1, num_tax_rows):
                    curr_y = tax_y + th_h + (r_idx * r_h)
                    sv.cvs.create_line(t_cxs[0], curr_y, t_cxs[-1], curr_y, fill=primary, width=1)
                sv.cvs.create_line(t_cxs[0], tot_y, t_cxs[-1], tot_y, fill=primary, width=1)

                for i in range(1, len(t_cxs)-1):
                    if i == 1: sv.cvs.create_line(t_cxs[i], tax_y, t_cxs[i], tot_y, fill=primary, width=1)
                    else: sv.cvs.create_line(t_cxs[i], tax_y, t_cxs[i], tax_title_y + tax_block_h, fill=primary, width=1)

            sig_bottom = y_off + paper_h - s(15)
            
            c_txt(x_off + paper_w/2, sig_bottom, f"Page {p+1}", "page_num", anchor="s")
            
            c_txt(tx, sig_bottom, "Authorized Signatory", "signature", anchor="se")
            c_txt(tx, sig_bottom - s(18), f"For {sv.name_var.get()}", "signature", anchor="se")

        p += 1 
        
    sv.total_pages = p
    if hasattr(sv, 'lbl_total'): sv.lbl_total.config(text=f"of {sv.total_pages}")
    sv.cvs.configure(scrollregion=(0, 0, max(cvs_w, paper_w + 40), sv.total_pages * (paper_h + 20) + 40))