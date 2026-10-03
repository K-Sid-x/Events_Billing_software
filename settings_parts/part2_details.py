import tkinter as tk

def build_part_2(parent, sv):
    BG_COLOR = sv.theme["BG_COLOR"]
    CARD_BG = sv.theme["CARD_BG"]
    BORDER_COLOR = sv.theme["BORDER_COLOR"]
    TEXT_PRIMARY = sv.theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = sv.theme["TEXT_SECONDARY"]

    tk.Label(parent, text="Customer & Invoice Details", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    f_labels = tk.Frame(parent, bg=CARD_BG)
    f_labels.pack(fill="x", pady=5)
    
    tk.Label(f_labels, text="Customer Box Title:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", pady=2)
    tk.Entry(f_labels, textvariable=sv.lbl_billed_to_var, width=25, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1).grid(row=0, column=1, sticky="w", padx=5, ipady=3)

    tk.Checkbutton(f_labels, text="Reverse Box Order", variable=sv.swap_boxes_var, bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=BG_COLOR, activebackground=CARD_BG, activeforeground=TEXT_PRIMARY, font=("Arial", 9, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(15, 0))

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    f_bg = tk.Frame(parent, bg=CARD_BG)
    f_bg.pack(fill="x", pady=5)
    
    tk.Label(f_bg, text="Meta Headers Background Color:", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold")).pack(side="left", pady=2)
    btn_m_bg = tk.Button(f_bg, width=4, bg=sv.colors["meta_head_bg"].get(), relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2")
    btn_m_bg.config(command=lambda: sv.pick_color("meta_head_bg", btn_m_bg))
    btn_m_bg.pack(side="left", padx=15)
    sv.color_btns["meta_head_bg"] = btn_m_bg

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Fonts & Formats (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    
    f_fonts = tk.Frame(parent, bg=CARD_BG)
    f_fonts.pack(fill="x")

    def make_btn(p, text, cmd, r):
        tk.Button(p, text=text, font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=cmd).grid(row=r, column=0, columnspan=5, pady=10)

    col1 = tk.LabelFrame(f_fonts, text="1. Billing Details", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    col1.pack(fill="x", pady=5)
    sv._create_full_font_row(col1, "Box Title", "bill_title", 0)
    sv._create_full_font_row(col1, "Prefixes", "bill_prefix", 1)
    sv._create_full_font_row(col1, "Name", "bill_name", 2)
    sv._create_full_font_row(col1, "Address", "bill_addr", 3)
    sv._create_full_font_row(col1, "Phone", "bill_phone", 4)
    
    # --- THE FIX: Conditionally display GSTIN based on company profile ---
    row_idx = 5
    if getattr(sv, 'has_gst', True):
        sv._create_full_font_row(col1, "GSTIN", "bill_gst", row_idx)
        row_idx += 1
    make_btn(col1, "⟲ Reset Billing Defaults", lambda: sv.reset_fonts_colors(1), row_idx)
    # ---------------------------------------------------------------------

    col2 = tk.LabelFrame(f_fonts, text="2. Place of Service", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    col2.pack(fill="x", pady=5)
    sv._create_full_font_row(col2, "Box Title", "serv_title", 0)
    sv._create_full_font_row(col2, "Prefixes", "serv_prefix", 1)
    sv._create_full_font_row(col2, "Name", "serv_name", 2)
    sv._create_full_font_row(col2, "Address", "serv_addr", 3)
    sv._create_full_font_row(col2, "Del. Date", "serv_del", 4)
    sv._create_full_font_row(col2, "Bill Date", "serv_bill", 5)
    make_btn(col2, "⟲ Reset Service Defaults", lambda: sv.reset_fonts_colors(2), 6)

    col3 = tk.LabelFrame(f_fonts, text="3. Invoice Details & Subject", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    col3.pack(fill="x", pady=5)
    sv._create_full_font_row(col3, "Inv No Lbl", "inv_no_lbl", 0)
    sv._create_full_font_row(col3, "Inv No Val", "inv_no_val", 1)
    sv._create_full_font_row(col3, "Inv Date Lbl", "inv_dt_lbl", 2)
    sv._create_full_font_row(col3, "Inv Date Val", "inv_dt_val", 3)
    sv._create_full_font_row(col3, "Eway Lbl", "eway_lbl", 4)
    sv._create_full_font_row(col3, "Eway Val", "eway_val", 5)
    sv._create_full_font_row(col3, "Subject Lbl", "subj_label", 6)
    sv._create_full_font_row(col3, "Subject Val", "subj_val", 7)
    make_btn(col3, "⟲ Reset Meta/Subj Defaults", lambda: sv.reset_fonts_colors(3), 8)