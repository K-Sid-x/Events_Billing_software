import tkinter as tk

def build_part_4(parent, sv):
    BG_COLOR = sv.theme["BG_COLOR"]
    CARD_BG = sv.theme["CARD_BG"]
    BORDER_COLOR = sv.theme["BORDER_COLOR"]
    TEXT_PRIMARY = sv.theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = sv.theme["TEXT_SECONDARY"]
    ACCENT_BLUE = sv.theme["ACCENT_BLUE"]

    new_keys = ["terms_lbl", "terms_val", "bank_lbl", "bank_val", "amt_words_lbl", "amt_words_val", "totals", "signature", "page_no"]
    
    for k in new_keys:
        if k not in sv.fonts:
            sv.fonts[k] = tk.StringVar(value="10")
            sv.fonts[k].trace_add("write", lambda *args: sv.schedule_preview())
        if k not in sv.colors:
            sv.colors[k] = tk.StringVar(value="#000000")
            sv.colors[k].trace_add("write", lambda *args: sv.schedule_preview())
        if k not in sv.bolds:
            sv.bolds[k] = tk.BooleanVar(value=False)
            sv.bolds[k].trace_add("write", lambda *args: sv.schedule_preview())
        if k not in sv.underlines:
            sv.underlines[k] = tk.BooleanVar(value=False)
            sv.underlines[k].trace_add("write", lambda *args: sv.schedule_preview())

    tk.Label(parent, text="Footer & Terms Customization", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

    if not hasattr(sv, 'show_esign_var'):
        sv.show_esign_var = tk.IntVar(value=1)
        sv.show_esign_var.trace_add("write", lambda *args: sv.schedule_preview())
        
    tk.Checkbutton(parent, text="Show e-sign (Digital Signature Image)", variable=sv.show_esign_var, font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, selectcolor=BG_COLOR, cursor="hand2").pack(anchor="w", pady=(0, 5))

    # THE FIX: Sliders stacked vertically to completely eliminate horizontal scrollbar clipping
    ctrl_f = tk.Frame(parent, bg=CARD_BG)
    ctrl_f.pack(fill="x", pady=(0, 15), padx=20)
    
    r1 = tk.Frame(ctrl_f, bg=CARD_BG)
    r1.pack(fill="x", pady=2)
    tk.Label(r1, text="Image Scale (%):", bg=CARD_BG, fg=TEXT_SECONDARY, font=("Arial", 9, "bold"), width=16, anchor="w").pack(side="left")
    scl = tk.Scale(r1, from_=10, to=300, orient="horizontal", variable=sv.sig_scale_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=150, sliderlength=15)
    scl.pack(side="left", padx=10)
    sv.protect_scroll(scl)
    
    r2 = tk.Frame(ctrl_f, bg=CARD_BG)
    r2.pack(fill="x", pady=2)
    tk.Label(r2, text="Vertical Nudge (px):", bg=CARD_BG, fg=TEXT_SECONDARY, font=("Arial", 9, "bold"), width=16, anchor="w").pack(side="left")
    nud = tk.Scale(r2, from_=-100, to=100, orient="horizontal", variable=sv.sig_nudge_var, bg=CARD_BG, fg=TEXT_PRIMARY, bd=0, highlightthickness=0, length=150, sliderlength=15)
    nud.pack(side="left", padx=10)
    sv.protect_scroll(nud)
    
    # --- THE FIX: A dedicated button to snap the slider perfectly back to zero ---
    tk.Button(r2, text="↺ 0", font=("Arial", 8, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.sig_nudge_var.set(0)).pack(side="left", padx=5)
    # -----------------------------------------------------------------------------

    f_terms = tk.LabelFrame(parent, text="Terms & Conditions Text", bg=CARD_BG, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), padx=5, pady=5)
    f_terms.pack(fill="x", pady=5)
    
    terms_container = tk.Frame(f_terms, bg=CARD_BG)
    terms_container.pack(fill="x", pady=5)
    
    def render_terms():
        for widget in terms_container.winfo_children(): widget.destroy()
        
        for i, t_var in enumerate(sv.terms_vars):
            row_f = tk.Frame(terms_container, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
            row_f.pack(fill="x", pady=6, padx=2)
            
            head_f = tk.Frame(row_f, bg=CARD_BG)
            head_f.pack(fill="x")
            
            tk.Label(head_f, text=f"Term {i+1}:", bg=CARD_BG, fg=TEXT_SECONDARY, font=("Arial", 9, "bold")).pack(side="left", padx=5, pady=2)
            tk.Button(head_f, text="❌", bg=CARD_BG, fg="#ef4444", font=("Arial", 10, "bold"), bd=0, cursor="hand2", command=lambda idx=i: remove_term(idx)).pack(side="right", padx=5, pady=2)

            t_box = tk.Text(row_f, height=2, width=40, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, bd=0, highlightthickness=0, font=("Arial", 10), wrap="word")
            t_box.pack(fill="x", padx=8, pady=(4, 8)) 
            t_box.insert("1.0", t_var.get())
            
            def on_change(event=None, tb=t_box, var=t_var):
                content = tb.get("1.0", "end-1c")
                if var.get() != content:
                    var.set(content)
                lines = content.count('\n') + 1 + (len(content) // 40)
                tb.config(height=min(max(2, lines), 8))
                sv.schedule_preview()

            t_box.bind("<KeyRelease>", on_change)
            on_change(None, t_box, t_var)
                
    def add_term():
        new_var = tk.StringVar(value="")
        new_var.trace_add("write", lambda *args: sv.schedule_preview())
        sv.terms_vars.append(new_var)
        render_terms()
        sv.schedule_preview()
        
    def remove_term(idx):
        del sv.terms_vars[idx]
        render_terms()
        sv.schedule_preview()
        
    sv.refresh_terms_ui = render_terms
    render_terms()
    
    tk.Button(f_terms, text="+ Add New Term", font=("Arial", 9, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", command=add_term).pack(pady=10)

    tk.Frame(parent, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    tk.Label(parent, text="Footer Fonts (Size | Color | Bold | Underline)", font=("Arial", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w")
    
    f_fonts = tk.Frame(parent, bg=CARD_BG)
    f_fonts.pack(fill="x", pady=5)

    sv._create_full_font_row(f_fonts, "Terms (Label)", "terms_lbl", 0)
    sv._create_full_font_row(f_fonts, "Terms (Data)", "terms_val", 1)
    sv._create_full_font_row(f_fonts, "Bank Details (Label)", "bank_lbl", 2)
    sv._create_full_font_row(f_fonts, "Bank Details (Data)", "bank_val", 3)
    sv._create_full_font_row(f_fonts, "Amount Word (Label)", "amt_words_lbl", 4)
    sv._create_full_font_row(f_fonts, "Amount Word (Data)", "amt_words_val", 5)
    sv._create_full_font_row(f_fonts, "Totals (Sub/Tax)", "totals", 6)
    sv._create_full_font_row(f_fonts, "Signature", "signature", 7)
    sv._create_full_font_row(f_fonts, "Page Numbers", "page_no", 8)

    tk.Button(parent, text="⟲ Reset Footer Defaults", font=("Arial", 8), bg=BG_COLOR, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", command=lambda: sv.reset_fonts_colors(9)).pack(pady=20)