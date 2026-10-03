import tkinter as tk
import sys
import os

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

def build_part_3(parent, sv):
    CARD_BG = sv.CARD_BG
    TEXT_PRIMARY = sv.TEXT_PRIMARY
    BORDER_COLOR = sv.BORDER_COLOR
    BG_COLOR = sv.BG_COLOR
    
    # --- THE FIX: Safely read the isolated company ID directly from the Settings View! ---
    comp_id = getattr(sv, "comp_id", 1)
    comp = database.get_company(comp_id)
    has_gst = (comp and comp[8] == 1)
    # -----------------------------------------------------------------------------------

    tk.Label(parent, text="Table Widths & Fonts", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    f_w = tk.LabelFrame(parent, text="Column Widths (%)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=10, pady=10)
    f_w.pack(fill="x", pady=5)
    
    def make_w_slider(p, r, c, lbl, var):
        f = tk.Frame(p, bg=CARD_BG)
        f.grid(row=r, column=c, sticky="w", padx=2, pady=5) 
        tk.Label(f, text=lbl, font=("Arial", 9), bg=CARD_BG, fg=sv.TEXT_SECONDARY, width=10, anchor="w").pack(side="left") 
        
        # --- THE FIX: Forward the scroll events to the master window so it doesn't get paralyzed! ---
        slider = tk.Scale(f, from_=2, to=30, orient="horizontal", variable=var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=65, sliderlength=15)
        slider.pack(side="left")
        slider.bind("<MouseWheel>", sv._on_mousewheel)
        slider.bind("<Button-4>", sv._on_mousewheel)
        slider.bind("<Button-5>", sv._on_mousewheel) 
    
    make_w_slider(f_w, 0, 0, "SI No:", sv.w_slno)
    make_w_slider(f_w, 0, 1, "Qnty/Units:", sv.w_qty)
    
    if has_gst:
        make_w_slider(f_w, 1, 0, "HSN/SAC:", sv.w_hsn)
        make_w_slider(f_w, 1, 1, "GST %:", sv.w_gst)
        make_w_slider(f_w, 2, 0, "Rate Inc Tax:", sv.w_rate_inc)
        make_w_slider(f_w, 2, 1, "Base Rate:", sv.w_rate)
        make_w_slider(f_w, 3, 0, "Amount:", sv.w_amt)
    else:
        make_w_slider(f_w, 1, 0, "Rate:", sv.w_rate)
        make_w_slider(f_w, 1, 1, "Amount:", sv.w_amt)
    
    msg_row = 4 if has_gst else 2
    tk.Label(f_w, text="* 'Particulars' automatically fills the remaining horizontal space.", font=("Arial", 8, "italic"), bg=CARD_BG, fg=sv.TEXT_SECONDARY).grid(row=msg_row, column=0, columnspan=2, pady=(10,0), sticky="w")
    
    def reset_widths():
        sv.w_slno.set(5); sv.w_qty.set(8); sv.w_rate.set(12); sv.w_amt.set(15)
        if has_gst: sv.w_hsn.set(10); sv.w_gst.set(6); sv.w_rate_inc.set(12)
    
    tk.Button(f_w, text="⟲ Reset Column Widths", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=reset_widths).grid(row=msg_row+1, column=0, columnspan=2, pady=10)

    f_h = tk.LabelFrame(parent, text="Header Fonts (Size | Color | Bold | Underline)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f_h.pack(fill="x", pady=5)
    
    f_bg = tk.Frame(f_h, bg=CARD_BG)
    f_bg.pack(fill="x", pady=5)
    tk.Label(f_bg, text="Header Background Color:", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(side="left")
    btn_bg = tk.Button(f_bg, width=3, bg=sv.colors["tab_head_bg"].get(), relief="solid", bd=1)
    btn_bg.config(command=lambda: sv.pick_color("tab_head_bg", btn_bg))
    btn_bg.pack(side="left", padx=10)
    sv.color_btns["tab_head_bg"] = btn_bg
    
    h_list = tk.Frame(f_h, bg=CARD_BG); h_list.pack(fill="x")
    sv._create_full_font_row(h_list, "SI No", "th_slno", 0)
    sv._create_full_font_row(h_list, "Particulars", "th_part", 1)
    sv._create_full_font_row(h_list, "Qnty/Units", "th_qty", 3)
    if has_gst:
        sv._create_full_font_row(h_list, "HSN/SAC", "th_hsn", 2)
        sv._create_full_font_row(h_list, "GST %", "th_gst", 4)
        sv._create_full_font_row(h_list, "Rate Inc Tax", "th_rate_inc", 5)
        sv._create_full_font_row(h_list, "Base Rate", "th_rate", 6)
    else:
        sv._create_full_font_row(h_list, "Rate", "th_rate", 6)
        
    sv._create_full_font_row(h_list, "Amount", "th_amt", 7)
    
    tk.Button(f_h, text="⟲ Reset Header Fonts & BG", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(3)).pack(pady=10)

    f_r = tk.LabelFrame(parent, text="Row Data Fonts (Size | Color | Bold | Underline)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f_r.pack(fill="x", pady=5)
    
    f_master = tk.Frame(f_r, bg=CARD_BG)
    f_master.pack(fill="x", pady=(0, 10))
    tk.Label(f_master, text="Master Row Scaler:", font=("Arial", 9, "bold"), bg=CARD_BG, fg=sv.ACCENT_BLUE, width=17, anchor="w").pack(side="left")
    tk.Scale(f_master, from_=-10, to=10, orient="horizontal", variable=sv.master_row_scale_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=120, sliderlength=15).pack(side="left", padx=5)
    tk.Label(f_master, text="(Shifts all data fonts proportionately)", font=("Arial", 8, "italic"), bg=CARD_BG, fg=sv.TEXT_SECONDARY).pack(side="left", padx=5)
    
    r_list = tk.Frame(f_r, bg=CARD_BG); r_list.pack(fill="x")
    sv._create_full_font_row(r_list, "SI No", "tr_slno", 0)
    sv._create_full_font_row(r_list, "Particulars", "tr_part", 1)
    sv._create_full_font_row(r_list, "Qnty/Units", "tr_qty", 3)
    if has_gst:
        sv._create_full_font_row(r_list, "HSN/SAC", "tr_hsn", 2)
        sv._create_full_font_row(r_list, "GST %", "tr_gst", 4)
        sv._create_full_font_row(r_list, "Rate Inc Tax", "tr_rate_inc", 5)
        sv._create_full_font_row(r_list, "Base Rate", "tr_rate", 6)
    else:
        sv._create_full_font_row(r_list, "Rate", "tr_rate", 6)
        
    sv._create_full_font_row(r_list, "Amount", "tr_amt", 7)
    
    tk.Button(f_r, text="⟲ Reset Row Data Fonts", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(4)).pack(pady=10)

    if has_gst:
        f_tax = tk.LabelFrame(parent, text="Tax Summary Fonts (Size | Color | Bold | Underline)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
        f_tax.pack(fill="x", pady=5)
        
        tax_list = tk.Frame(f_tax, bg=CARD_BG); tax_list.pack(fill="x")
        sv._create_full_font_row(tax_list, "Tax Summary (Title)", "tax_title", 0)
        sv._create_full_font_row(tax_list, "Tax Summary (Label)", "tax_lbl", 1)
        sv._create_full_font_row(tax_list, "Tax Summary (Data)", "tax_val", 2)
        sv._create_full_font_row(tax_list, "Tax Summary (Total Lbl)", "tax_sum_tot_lbl", 3)
        sv._create_full_font_row(tax_list, "Tax Summary (Total Val)", "tax_sum_tot_val", 4)
        
        tk.Button(f_tax, text="⟲ Reset Tax Summary Fonts", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors("tax")).pack(pady=10)