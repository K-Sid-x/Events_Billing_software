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

def build_part_2(parent, sv):
    CARD_BG = sv.CARD_BG
    TEXT_PRIMARY = sv.TEXT_PRIMARY
    BG_COLOR = sv.BG_COLOR
    BORDER_COLOR = sv.BORDER_COLOR

    # --- THE FIX: Safely read the isolated company ID directly from the Settings View! ---
    comp_id = getattr(sv, "comp_id", 1)
    comp = database.get_company(comp_id)
    has_gst = (comp and comp[8] == 1)
    # -----------------------------------------------------------------------------------

    tk.Label(parent, text="Voucher Billing Details", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    f_bg = tk.Frame(parent, bg=CARD_BG)
    f_bg.pack(fill="x", pady=(0, 10))
    tk.Label(f_bg, text="Header Background Color:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold")).pack(side="left")
    btn_bg = tk.Button(f_bg, width=4, bg=sv.colors["meta_head_bg"].get(), relief="solid", bd=1)
    btn_bg.config(command=lambda: sv.pick_color("meta_head_bg", btn_bg))
    btn_bg.pack(side="left", padx=10)
    sv.color_btns["meta_head_bg"] = btn_bg

    def make_btn(p, text, cmd, r):
        tk.Button(p, text=text, font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=cmd).grid(row=r, column=0, columnspan=5, pady=10)

    f1 = tk.LabelFrame(parent, text="1. Consignee / Billed To (Left Box)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f1.pack(fill="x", pady=5)
    sv._create_full_font_row(f1, "Box Title", "vend_title", 0)
    sv._create_full_font_row(f1, "Name", "vend_name", 1)
    sv._create_full_font_row(f1, "Address / Contact", "vend_addr", 2)
    if has_gst:
        sv._create_full_font_row(f1, "GSTIN", "vend_gst", 3)
    make_btn(f1, "⟲ Reset Consignee Defaults", lambda: sv.reset_fonts_colors("vendor"), 4)
    
    f2 = tk.LabelFrame(parent, text="2. Supplier / Billed From (Middle Box)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f2.pack(fill="x", pady=5)
    sv._create_full_font_row(f2, "Box Title", "buyer_title", 0)
    sv._create_full_font_row(f2, "Name", "buyer_name", 1)
    sv._create_full_font_row(f2, "Address / Contact", "buyer_addr", 2)
    if has_gst:
        sv._create_full_font_row(f2, "GSTIN", "buyer_gst", 3)
    make_btn(f2, "⟲ Reset Supplier Defaults", lambda: sv.reset_fonts_colors("buyer"), 4)
    
    f3 = tk.LabelFrame(parent, text="3. Voucher & Meta Data (Right Box)", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f3.pack(fill="x", pady=5)
    sv._create_full_font_row(f3, "Box Title", "meta_title", 0)
    sv._create_full_font_row(f3, "Voucher No Lbl", "vno_l", 1)
    sv._create_full_font_row(f3, "Voucher No Val", "vno_v", 2)
    sv._create_full_font_row(f3, "Voucher Date Lbl", "vdt_l", 3)
    sv._create_full_font_row(f3, "Voucher Date Val", "vdt_v", 4)
    sv._create_full_font_row(f3, "Supplier Bill Lbl", "sbl_l", 5)
    sv._create_full_font_row(f3, "Supplier Bill Val", "sbl_v", 6)
    sv._create_full_font_row(f3, "Bill Date Lbl", "sdt_l", 7)
    sv._create_full_font_row(f3, "Bill Date Val", "sdt_v", 8)
    sv._create_full_font_row(f3, "E-Way Lbl", "ewy_l", 9)
    sv._create_full_font_row(f3, "E-Way Val", "ewy_v", 10)
    make_btn(f3, "⟲ Reset Meta Defaults", lambda: sv.reset_fonts_colors("meta"), 11)