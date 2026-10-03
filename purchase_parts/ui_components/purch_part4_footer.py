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

def build_part_4(parent, sv):
    CARD_BG = sv.CARD_BG
    TEXT_PRIMARY = sv.TEXT_PRIMARY
    BORDER_COLOR = sv.BORDER_COLOR
    TEXT_SECONDARY = sv.TEXT_SECONDARY
    
    # --- THE FIX: Safely read the isolated company ID directly from the Settings View! ---
    comp_id = getattr(sv, "comp_id", 1)
    comp = database.get_company(comp_id)
    has_gst = (comp and comp[8] == 1)
    # -----------------------------------------------------------------------------------

    tk.Label(parent, text="Footer Modules & Fonts", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))
    
    if has_gst:
        f_bg = tk.Frame(parent, bg=CARD_BG)
        f_bg.pack(fill="x", pady=(0, 15))
        
        tk.Label(f_bg, text="Tax Title BG Color:", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, width=15, anchor="w").pack(side="left")
        btn_tax_title_bg = tk.Button(f_bg, width=4, bg=sv.colors["tax_title_bg"].get(), relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2")
        btn_tax_title_bg.config(command=lambda k="tax_title_bg", b=btn_tax_title_bg: sv.pick_color(k, b))
        btn_tax_title_bg.pack(side="left", padx=5)
        sv.color_btns["tax_title_bg"] = btn_tax_title_bg

        tk.Label(f_bg, text="Tax Header BG Color:", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, width=18, anchor="w").pack(side="left", padx=(15,0))
        btn_tax_bg = tk.Button(f_bg, width=4, bg=sv.colors["tax_head_bg"].get(), relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2")
        btn_tax_bg.config(command=lambda k="tax_head_bg", b=btn_tax_bg: sv.pick_color(k, b))
        btn_tax_bg.pack(side="left", padx=5)
        sv.color_btns["tax_head_bg"] = btn_tax_bg

    tk.Label(parent, text="Footer Fonts (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    
    f_f = tk.Frame(parent, bg=CARD_BG); f_f.pack(fill="x", pady=5)
    
    sv._create_full_font_row(f_f, "Amount Word (Label)", "amt_w_l", 0)
    sv._create_full_font_row(f_f, "Amount Word (Data)", "amt_w_v", 1)
    
    sv._create_full_font_row(f_f, "Subtotal (Label)", "subtotal_lbl", 2)
    sv._create_full_font_row(f_f, "Subtotal (Value)", "subtotal_val", 3)
    
    if has_gst:
        sv._create_full_font_row(f_f, "CGST/SGST (Label)", "tax_totals_lbl", 4)
        sv._create_full_font_row(f_f, "CGST/SGST (Value)", "tax_totals_val", 5)
        sv._create_full_font_row(f_f, "Round Off (Label)", "round_off_lbl", 6)
        sv._create_full_font_row(f_f, "Round Off (Value)", "round_off_val", 7)
    
    sv._create_full_font_row(f_f, "Grand Total (Label)", "g_total_lbl", 8)
    sv._create_full_font_row(f_f, "Grand Total (Value)", "g_total_val", 9)
    
    if has_gst:
        tk.Label(f_f, text="--- Tax Summary Table Fonts ---", font=("Arial", 9, "italic"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=10, column=0, columnspan=5, pady=(15,5), sticky="w")
        sv._create_full_font_row(f_f, "Tax Summary Title", "tax_title", 11)
        sv._create_full_font_row(f_f, "Tax Table Headers", "tax_lbl", 12)
        sv._create_full_font_row(f_f, "Tax Table Values", "tax_val", 13)
        sv._create_full_font_row(f_f, "Tax Totals (Label)", "tax_sum_tot_lbl", 14)
        sv._create_full_font_row(f_f, "Tax Totals (Value)", "tax_sum_tot_val", 15)
    
    tk.Label(f_f, text="--- Signatures ---", font=("Arial", 9, "italic"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=16, column=0, columnspan=5, pady=(15,5), sticky="w")
    sv._create_full_font_row(f_f, "Signature", "signature", 17)
    sv._create_full_font_row(f_f, "Page Numbers", "page_num", 18)
    
    tk.Button(parent, text="⟲ Reset Footer Defaults", font=("Arial", 8), bg=sv.BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(5)).pack(pady=20)