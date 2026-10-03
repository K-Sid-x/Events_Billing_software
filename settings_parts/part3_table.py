import tkinter as tk

def build_part_3(parent, sv):
    BG_COLOR = sv.theme["BG_COLOR"]
    CARD_BG = sv.theme["CARD_BG"]
    BORDER_COLOR = sv.theme["BORDER_COLOR"]
    TEXT_PRIMARY = sv.theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = sv.theme["TEXT_SECONDARY"]
    ACCENT_BLUE = sv.theme["ACCENT_BLUE"]

    tk.Label(parent, text="Table Formatting & Widths", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    f_bg = tk.Frame(parent, bg=CARD_BG)
    f_bg.pack(fill="x", pady=5)
    
    tk.Label(f_bg, text="Header Background Color:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold")).pack(side="left", pady=2)
    btn_bg = tk.Button(f_bg, width=4, bg=sv.colors["tab_head_bg"].get(), relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2")
    btn_bg.config(command=lambda: sv.pick_color("tab_head_bg", btn_bg))
    btn_bg.pack(side="left", padx=15)
    
    sv.color_btns["tab_head_bg"] = btn_bg

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Column Width Adjustments (%)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_w = tk.Frame(parent, bg=CARD_BG)
    f_w.pack(fill="x", pady=5)
    
    has_gst = getattr(sv, 'has_gst', True)
    
    # --- THE FIX: Smart 2-Column Grid Wrapper for Sliders ---
    # This prevents the 3rd column from bleeding into the scrollbar
    sliders = [
        ("Sl No:", sv.w_slno, 2, 20),
        ("Qnty:", sv.w_qty, 4, 25)
    ]
    if has_gst:
        sliders.append(("HSN:", sv.w_hsn, 5, 30))
        
    sliders.extend([
        ("Rate:", sv.w_rate, 5, 30),
        ("Days:", sv.w_days, 4, 25),
        ("Amt:", sv.w_amt, 5, 30)
    ])
    
    r, c = 0, 0
    for label_text, var, min_v, max_v in sliders:
        tk.Label(f_w, text=label_text, bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=r, column=c, sticky="w", pady=2)
        # Length slightly reduced to 110 to guarantee a perfect fit in 400px width
        tk.Scale(f_w, from_=min_v, to=max_v, orient="horizontal", variable=var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=110).grid(row=r, column=c+1, padx=(0, 15))
        c += 2
        if c >= 4: # Wrap to the next row after 2 sliders
            c = 0
            r += 1
            
    tk.Button(f_w, text="⟲ Reset Widths", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(4)).grid(row=r+1, column=0, columnspan=4, pady=(10,0))

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Header Fonts (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_head = tk.Frame(parent, bg=CARD_BG)
    f_head.pack(fill="x", pady=5)
    
    sv._create_full_font_row(f_head, "Sl No", "th_slno", 0)
    sv._create_full_font_row(f_head, "Particulars", "th_part", 1)
    sv._create_full_font_row(f_head, "Quantity", "th_qty", 2)
    
    if has_gst:
        sv._create_full_font_row(f_head, "HSN/SAC", "th_hsn", 3)
        
    sv._create_full_font_row(f_head, "Rate", "th_rate", 4)
    sv._create_full_font_row(f_head, "Days", "th_days", 5)
    sv._create_full_font_row(f_head, "Amount", "th_amt", 6)
    tk.Button(f_head, text="⟲ Reset Header Fonts & BG", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(5)).grid(row=7, column=0, columnspan=5, pady=10)

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=5)

    tk.Label(parent, text="Row Data Fonts (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_row = tk.Frame(parent, bg=CARD_BG)
    f_row.pack(fill="x", pady=5)

    f_master = tk.Frame(f_row, bg=CARD_BG)
    f_master.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 15))
    
    tk.Label(f_master, text="Master Row Scaler:", font=("Arial", 9, "bold"), fg=ACCENT_BLUE, bg=CARD_BG).pack(side="left")
    
    def on_master_scale(*args):
        val = sv.master_scale_var.get()
        delta = val - getattr(sv, 'last_master_scale', 0)
        if delta == 0: return
        
        keys = ["tr_slno", "tr_part", "tr_hsn", "tr_qty", "tr_rate", "tr_days", "tr_amt"]
        for k in keys:
            try:
                curr = int(float(sv.fonts[k].get()))
                sv.fonts[k].set(str(curr + delta))
            except: pass
        
        sv.last_master_scale = val
        sv.schedule_preview() 

    scale_master = tk.Scale(f_master, from_=-10, to=10, orient="horizontal", variable=sv.master_scale_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=150, sliderlength=15)
    scale_master.pack(side="left", padx=15)
    scale_master.config(command=on_master_scale)
    
    tk.Label(f_master, text="(Shifts all data fonts proportionally)", font=("Arial", 8, "italic"), fg=TEXT_SECONDARY, bg=CARD_BG).pack(side="left")

    sv._create_full_font_row(f_row, "Sl No", "tr_slno", 1)
    sv._create_full_font_row(f_row, "Particulars", "tr_part", 2)
    sv._create_full_font_row(f_row, "Quantity", "tr_qty", 3)
    
    if has_gst:
        sv._create_full_font_row(f_row, "HSN/SAC", "tr_hsn", 4)
        
    sv._create_full_font_row(f_row, "Rate", "tr_rate", 5)
    sv._create_full_font_row(f_row, "Days", "tr_days", 6)
    sv._create_full_font_row(f_row, "Amount", "tr_amt", 7)
    tk.Button(f_row, text="⟲ Reset Row Fonts", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(6)).grid(row=8, column=0, columnspan=5, pady=10)