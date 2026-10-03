import tkinter as tk
from tkinter import ttk
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

def build_part_1(parent, sv):
    CARD_BG = sv.CARD_BG
    TEXT_PRIMARY = sv.TEXT_PRIMARY
    TEXT_SECONDARY = sv.TEXT_SECONDARY
    BG_COLOR = sv.BG_COLOR
    BORDER_COLOR = sv.BORDER_COLOR

    # --- THE FIX: Safely read the isolated company ID directly from the Settings View! ---
    comp_id = getattr(sv, "comp_id", 1)
    comp = database.get_company(comp_id)
    has_gst = (comp and comp[8] == 1)
    # -----------------------------------------------------------------------------------

    tk.Label(parent, text="Header & Company Details", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    def make_entry(f, v):
        return tk.Entry(f, textvariable=v, font=("Arial", 10), bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)

    f_inputs = tk.Frame(parent, bg=CARD_BG)
    f_inputs.pack(fill="x", pady=5)

    tk.Label(f_inputs, text="Company Name:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.name_var).grid(row=0, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Secondary Name:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.sec_var).grid(row=1, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Address:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.addr_var).grid(row=2, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Phone 1:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=3, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.p1_var).grid(row=3, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Phone 2:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=4, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.p2_var).grid(row=4, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Phone 3:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=5, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.p3_var).grid(row=5, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    tk.Label(f_inputs, text="Email:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=6, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.email_var).grid(row=6, column=1, sticky="ew", padx=10, pady=4, ipady=2)

    if has_gst:
        tk.Label(f_inputs, text="GSTIN:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=7, column=0, sticky="w", pady=4)
        make_entry(f_inputs, sv.gst_var).grid(row=7, column=1, sticky="ew", padx=10, pady=4, ipady=2)
    
    msg_row = 8 if has_gst else 7
    tk.Label(f_inputs, text="Document Title:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=msg_row, column=0, sticky="w", pady=4)
    make_entry(f_inputs, sv.doc_title_var).grid(row=msg_row, column=1, sticky="ew", padx=10, pady=4, ipady=2)
    
    f_inputs.columnconfigure(1, weight=1)

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=15)

    tk.Label(parent, text="Layout & Logo", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_layout = tk.Frame(parent, bg=CARD_BG)
    f_layout.pack(fill="x", pady=5)

    tk.Label(f_layout, text="Paper Size:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", pady=4)
    cb_paper = ttk.Combobox(f_layout, textvariable=sv.paper_size_var, values=["A4 (210*297mm)"], state="readonly", width=30)
    cb_paper.grid(row=0, column=1, sticky="w", padx=10, pady=4)

    tk.Label(f_layout, text="Layout Style:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", pady=4)
    cb_layout = ttk.Combobox(f_layout, textvariable=sv.layout_var, values=["Classic", "Left-Aligned", "Right-Aligned", "Split Header (Left-Center-Right)"], state="readonly", width=30)
    cb_layout.grid(row=1, column=1, sticky="w", padx=10, pady=4)

    tk.Label(f_layout, text="Logo Shape:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=4)
    cb_shape = ttk.Combobox(f_layout, textvariable=sv.logo_shape_var, values=["Original", "Square", "Circle"], state="readonly", width=30)
    cb_shape.grid(row=2, column=1, sticky="w", padx=10, pady=4)

    tk.Button(f_layout, text="Browse New Logo", font=("Arial", 9, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=sv.browse_logo, padx=10, pady=3).grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Spacing & Sizing", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_sliders = tk.Frame(parent, bg=CARD_BG)
    f_sliders.pack(fill="x", pady=5)

    tk.Label(f_sliders, text="Header Spacing:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", pady=4)
    tk.Scale(f_sliders, from_=0, to=150, orient="horizontal", variable=sv.header_spacing_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=200).grid(row=0, column=1, padx=10)

    tk.Label(f_sliders, text="Logo Size:", bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=1, column=0, sticky="w", pady=4)
    tk.Scale(f_sliders, from_=30, to=300, orient="horizontal", variable=sv.logo_size_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=200).grid(row=1, column=1, padx=10)

    chk_swap = tk.Checkbutton(f_sliders, text="Swap Name / Secondary Order", variable=sv.swap_title_order_var, bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=BG_COLOR, activebackground=CARD_BG, activeforeground=TEXT_PRIMARY, cursor="hand2")
    chk_swap.grid(row=2, column=0, columnspan=2, sticky="w", pady=10)

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Header Fonts (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    f_fonts = tk.Frame(parent, bg=CARD_BG)
    f_fonts.pack(fill="x", pady=5)

    sv._create_full_font_row(f_fonts, "Company Name", "name", 0)
    sv._create_full_font_row(f_fonts, "Secondary Name", "sec", 1)
    sv._create_full_font_row(f_fonts, "Address", "addr", 2)
    sv._create_full_font_row(f_fonts, "Contact Info", "contact", 3)
    if has_gst:
        sv._create_full_font_row(f_fonts, "GSTIN", "gst", 4)
        sv._create_full_font_row(f_fonts, "Doc Title", "doc_title", 5)
    else:
        sv._create_full_font_row(f_fonts, "Doc Title", "doc_title", 4)

    tk.Button(parent, text="⟲ Reset Header Defaults", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(1)).pack(pady=20)