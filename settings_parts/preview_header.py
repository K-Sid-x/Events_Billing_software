import os
try:
    from PIL import Image, ImageTk, ImageDraw, ImageOps
except ImportError:
    pass

def draw_header(ctx, cy):
    sv = ctx["sv"]
    s = ctx["s"]
    c_txt = ctx["c_txt"]
    pad = ctx["pad"]
    x_off = ctx["x_off"]
    paper_w = ctx["paper_w"]
    
    c_name = ctx["c_name"]
    c_sec = ctx["c_sec"]
    c_addr = ctx["c_addr"]
    c_gst_val = ctx["c_gst_val"]
    c_cont = ctx["c_cont"]

    try: l_sz = s(int(float(sv.logo_size_var.get() or 120)))
    except: l_sz = s(120)

    try: resamp = Image.Resampling.LANCZOS
    except AttributeError: resamp = Image.LANCZOS

    layout = sv.layout_var.get()
    t_y_start = cy
    
    tk_logo = None
    draw_w = 0
    try:
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
                new_w = l_sz
                new_h = int(l_sz / ratio)
                if new_h > l_sz:
                    new_h = l_sz
                    new_w = int(l_sz * ratio)
                img = img.resize((new_w, new_h), resamp)

            tk_logo = ImageTk.PhotoImage(img)
            sv.tk_logo = tk_logo 
            draw_w = img.width
    except: pass

    max_header_y = t_y_start
    
    try: spacing = s(int(float(sv.header_spacing_var.get())))
    except: spacing = s(20)

    if layout != "Custom (Drag & Drop)":
        logo_y_end = t_y_start
        if tk_logo:
            if layout in ["Split Header (Left-Center-Right)", "Left-Aligned", "Classic"]:
                lx = x_off + pad
            elif layout == "Right-Aligned":
                lx = x_off + paper_w - pad - draw_w
            else:
                lx = x_off + pad
                
            ctx["cvs"].create_image(lx, t_y_start, image=tk_logo, anchor="nw")
            logo_y_end = t_y_start + tk_logo.height()

        if layout == "Split Header (Left-Center-Right)":
            center_x = x_off + paper_w / 2
            center_y = t_y_start
            right_x = x_off + paper_w - pad
            right_y = t_y_start
            
            if hasattr(sv, 'swap_title_order_var') and sv.swap_title_order_var.get() == 1:
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
            if layout == "Left-Aligned":
                offset = (draw_w + pad) if tk_logo else 0
                t_x = x_off + pad + offset
                t_anc = "nw"
            elif layout == "Right-Aligned":
                offset = (draw_w + pad) if tk_logo else 0
                t_x = x_off + paper_w - pad - offset
                t_anc = "ne"
            elif layout == "Classic":
                t_x = x_off + paper_w - pad
                t_anc = "ne"

            t_y = t_y_start
            if hasattr(sv, 'swap_title_order_var') and sv.swap_title_order_var.get() == 1:
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc)
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc)
            else:
                t_y = c_txt(t_x, t_y, c_name, "name", anchor=t_anc)
                if c_sec: t_y = c_txt(t_x, t_y, c_sec, "sec", anchor=t_anc)
                
            t_y = c_txt(t_x, t_y, c_addr, "addr", max_w=s(300), anchor=t_anc)
            t_y = c_txt(t_x, t_y, c_cont, "contact", anchor=t_anc)
            if c_gst_val: t_y = c_txt(t_x, t_y, f"GSTIN: {c_gst_val}", "gst", anchor=t_anc)

            max_header_y = max(logo_y_end, t_y)
            
        return max_header_y + spacing, tk_logo
    else:
        return t_y_start, tk_logo