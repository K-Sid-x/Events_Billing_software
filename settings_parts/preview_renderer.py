import tkinter as tk
import math

from settings_parts.preview_header import draw_header
from settings_parts.preview_meta import draw_meta
from settings_parts.preview_table import draw_table
from settings_parts.preview_footer import draw_footer

TEXT_SECONDARY = "#94a3b8"

def render_preview(sv):
    sv.cvs.delete("all")
    cvs_w = sv.cvs.winfo_width()
    
    if cvs_w < 50: 
        sv.cvs.after(100, lambda: render_preview(sv))
        return 
    
    # THE FIX: Reverted to strict logical dimensions.
    paper_size = sv.paper_size_var.get() if hasattr(sv, 'paper_size_var') else "A4"
    if "A5" in paper_size:
        base_w, base_h = 559, 794
    else:
        base_w, base_h = 794, 1123
        
    sf = 1.0 
    
    paper_w = int(base_w * sf)
    paper_h = int(base_h * sf)
    
    total_w = max(cvs_w, paper_w + 60)
    x_off = (total_w - paper_w) // 2
    y_off = 30

    def draw_paper_bg(curr_y_off):
        is_dark = sv.theme["BG_COLOR"] == "#0f172a"
        shadow_col = "#000000" if is_dark else "#cbd5e1"
        
        shadow = sv.cvs.create_rectangle(x_off+6, curr_y_off+6, x_off+paper_w+6, curr_y_off+paper_h+6, fill=shadow_col, outline="", tags="bg")
        paper = sv.cvs.create_rectangle(x_off, curr_y_off, x_off+paper_w, curr_y_off+paper_h, fill="#ffffff", outline="#cccccc", tags="bg")
        
        sv.cvs.tag_lower(paper)
        sv.cvs.tag_lower(shadow, paper) 

    draw_paper_bg(y_off)

    def s(val): return int(val * sf)
    def get_col(key): return sv.colors[key].get() or "#000000"
    
    def get_f(key):
        try: return max(6, int(int(float(sv.fonts[key].get() or 10)) * sf))
        except: return max(6, int(10 * sf))
    
    def c_txt(x, y, text, key, bold=False, italic=False, underline=False, anchor="nw", width=0, max_w=None, max_h=None, tags=(), bg_solid=False):
        if not text: return y
        
        is_bold = bold or sv.bolds.get(key, tk.BooleanVar(value=False)).get()
        is_under = underline or sv.underlines.get(key, tk.BooleanVar(value=False)).get()
        
        modifiers = []
        if is_bold: modifiers.append("bold")
        if italic: modifiers.append("italic")
        if is_under: modifiers.append("underline")
        
        font_mod = " ".join(modifiers)
        base_f = get_f(key)
        actual_f = base_f
        
        just = tk.LEFT
        if "e" in anchor: just = tk.RIGHT
        elif "center" in anchor or anchor in ["n", "s"]: just = tk.CENTER
        
        font_tup = ("Arial", actual_f, font_mod) if font_mod else ("Arial", actual_f)
        t_id = sv.cvs.create_text(x, y, text=text, font=font_tup, fill=get_col(key), anchor=anchor, width=width, justify=just, tags=tags)
        
        if max_w or max_h:
            sv.cvs.update_idletasks()
            while actual_f > 2: 
                bbox = sv.cvs.bbox(t_id)
                if not bbox: break
                
                w_overflow = (max_w and width == 0) and (bbox[2] - bbox[0]) > max_w
                h_overflow = max_h and (bbox[3] - bbox[1]) > max_h
                
                if w_overflow or h_overflow:
                    actual_f -= 1
                    font_tup = ("Arial", actual_f, font_mod) if font_mod else ("Arial", actual_f)
                    sv.cvs.itemconfig(t_id, font=font_tup)
                    sv.cvs.update_idletasks()
                else:
                    break
        
        bbox = sv.cvs.bbox(t_id)
        if bbox:
            if bg_solid:
                pad_px = s(3)
                bg_id = sv.cvs.create_rectangle(bbox[0]-pad_px, bbox[1]-pad_px, bbox[2]+pad_px, bbox[3]+pad_px, fill="#ffffff", outline="", tags=tags)
                sv.cvs.tag_lower(bg_id, t_id)
            return bbox[3] + s(2) 
        return y + int(actual_f * 1.5)

    def fmt_phone(num_str):
        clean = "".join(filter(str.isdigit, num_str))
        if len(clean) == 10: return f"+91 {clean[:5]}-{clean[5:]}"
        if len(clean) == 12 and clean.startswith("91"): return f"+91 {clean[2:7]}-{clean[7:]}"
        return num_str 

    phones_list = []
    p1_val = sv.p1_var.get().strip() if hasattr(sv, 'p1_var') else ""
    p2_val = sv.p2_var.get().strip() if hasattr(sv, 'p2_var') else ""
    p3_val = sv.p3_var.get().strip() if hasattr(sv, 'p3_var') else ""

    if p1_val: phones_list.append(f"Ph: {fmt_phone(p1_val)}")
    elif not p2_val and not p3_val: phones_list.append("Ph: +91 99999-99999") 
    if p2_val: phones_list.append(f"      {fmt_phone(p2_val)}")
    if p3_val: phones_list.append(f"      {fmt_phone(p3_val)}")

    curr_format = sv.currency_var.get() if hasattr(sv, 'currency_var') else ""
    if "($)" in curr_format: curr_sym = "$"
    elif "(€)" in curr_format: curr_sym = "€"
    elif "(£)" in curr_format: curr_sym = "£"
    elif "(₹)" in curr_format: curr_sym = "₹"
    else: curr_sym = ""
    
    date_format = sv.date_format_var.get() if hasattr(sv, 'date_format_var') else "DD.MM.YYYY"
    if date_format == "DD-MM-YYYY": d_str = "12-05-2026"; d2 = "15-05-2026"; dbill = "01-05-2026 to 12-05-2026"
    elif date_format == "DD/MM/YYYY": d_str = "12/05/2026"; d2 = "15/05/2026"; dbill = "01/05/2026 to 12/05/2026"
    elif date_format == "YYYY-MM-DD": d_str = "2026-05-12"; d2 = "2026-05-15"; dbill = "2026-05-01 to 2026-05-12"
    elif date_format == "MM/DD/YYYY": d_str = "05/12/2026"; d2 = "05/15/2026"; dbill = "05/01/2026 to 05/12/2026"
    else: d_str = "12.05.2026"; d2 = "15.05.2026"; dbill = "01.05.26 to 12.05.26"

    ctx = {
        "sv": sv, "cvs": sv.cvs, "sf": sf, "s": s, "c_txt": c_txt, "get_f": get_f, "get_col": get_col,
        "x_off": x_off, "y_off": y_off, "paper_w": paper_w, "paper_h": paper_h, 
        "draw_paper_bg": draw_paper_bg, "pad": s(20),
        "c_name": sv.name_var.get().upper() or "COMPANY NAME",
        "c_sec": sv.sec_var.get(),
        "c_addr": sv.addr_var.get() or "123 Business Road, City",
        "c_gst_val": sv.gst_var.get(),
        "c_cont": "\n".join(phones_list + [f"Email: {sv.email_var.get().strip() if hasattr(sv, 'email_var') else 'contact@company.com'}"]),
        "curr_sym": curr_sym, "d_str": d_str, "d2": d2, "dbill": dbill,
        "is_split": hasattr(sv, 'prev_split_var') and sv.prev_split_var.get() == 1,
        "show_extras": hasattr(sv, 'prev_extras_var') and sv.prev_extras_var.get() == 1,
        "show_bank_toggle": hasattr(sv, 'prev_bank_var') and sv.prev_bank_var.get() == 1,
        "show_terms_toggle": hasattr(sv, 'prev_terms_var') and sv.prev_terms_var.get() == 1
    }

    cy = y_off + ctx["pad"]
    cy, tk_logo = draw_header(ctx, cy)
    
    if sv.layout_var.get() != "Custom (Drag & Drop)":
        cy = draw_meta(ctx, cy)
    else:
        cy = cy + s(50)

    f_y, page_count, y_off_final = draw_table(ctx, cy)
    draw_footer(ctx, f_y, page_count, y_off_final)

    sv.cvs.configure(scrollregion=(0, 0, total_w, y_off_final + paper_h + 40))

    if sv.layout_var.get() == "Custom (Drag & Drop)":
        sv.cvs.create_text(x_off + paper_w/2, y_off + paper_h/4, text="[ CUSTOM LAYOUT ]\nClick and Drag each element independently!\nUse Header Spacing slider to push invoice details down.", font=("Arial", 12, "bold"), fill=TEXT_SECONDARY, justify="center")
        if tk_logo:
            lx = sv.cached_pos.get("drag_logo_x", x_off + ctx["pad"]); ly = sv.cached_pos.get("drag_logo_y", y_off + ctx["pad"])
            sv.cvs.create_image(lx, ly, image=tk_logo, anchor="nw", tags=("draggable", "drag_logo"))
        base_x = x_off + paper_w / 2; curr_y = y_off + ctx["pad"]
        def get_pos(tag_prefix, default_y): return sv.cached_pos.get(f"{tag_prefix}_x", base_x), sv.cached_pos.get(f"{tag_prefix}_y", default_y)
        
        nx, ny = get_pos("drag_name", curr_y); curr_y = c_txt(nx, ny, ctx["c_name"], "name", anchor="n", tags=("draggable", "drag_name"), bg_solid=True)
        if ctx["c_sec"]:
            sx, sy = get_pos("drag_sec", curr_y); curr_y = c_txt(sx, sy, ctx["c_sec"], "sec", anchor="n", tags=("draggable", "drag_sec"), bg_solid=True)
        ax, ay = get_pos("drag_addr", curr_y); curr_y = c_txt(ax, ay, ctx["c_addr"], max_w=s(300), anchor="n", tags=("draggable", "drag_addr"), bg_solid=True)
        cx_pos, cy_txt = get_pos("drag_cont", curr_y); curr_y = c_txt(cx_pos, cy_txt, ctx["c_cont"], "contact", anchor="n", tags=("draggable", "drag_cont"), bg_solid=True)
        if ctx["c_gst_val"]:
            gx, gy = get_pos("drag_gst", curr_y); curr_y = c_txt(gx, gy, f"GSTIN: {ctx['c_gst_val']}", "gst", anchor="n", tags=("draggable", "drag_gst"), bg_solid=True)
        sv.cvs.tag_raise("draggable")