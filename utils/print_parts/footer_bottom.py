def get_bottom_blocks(ctx, get_css, curr_page_disp):
    studio = ctx["studio"]
    
    css_term_lbl = get_css("terms_lbl")
    css_term_val = get_css("terms_val")
    css_sig = get_css("signature")
    css_page_no = get_css("page_no")

    # --- TERMS ---
    terms_html = ""
    terms_list = ctx.get("terms_list", [])
    if terms_list:
        terms_html += f'<div style="border-top: 1px solid #000; width: 320px; margin-bottom: 4px;"></div>'
        terms_html += f'<div style="{css_term_lbl} margin-bottom: 4px; line-height: 1.1;">Terms & Conditions:</div>'
        terms_html += "<table style='width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0;'>"
        for i, t in enumerate(terms_list):
            mb = "2px" if i < len(terms_list) - 1 else "0"
            lh = "1" if i == len(terms_list) - 1 else "1.1"
            terms_html += f'<tr><td style="{css_term_val} border: none; padding: 0; vertical-align: top; width: 20px;"><div style="margin-bottom: {mb}; line-height: {lh};">{i+1}.</div></td><td style="{css_term_val} border: none; padding: 0; vertical-align: top; word-break: break-word; overflow-wrap: break-word;"><div style="margin-bottom: {mb}; line-height: {lh};">{t}</div></td></tr>'
        terms_html += "</table>"

    # --- PAGE NUMBER ---
    page_html = f'<span style="{css_page_no} line-height: 1; margin: 0; padding: 0; display: block;">Page {curr_page_disp}</span>'

    # --- SIGNATURE ---
    show_esign = int(studio.settings.get("show_esign", 1)) == 1
    sig_role = ctx.get("sig_role", "")
    sig_b64 = ctx.get("sig_b64", "")
    try: sig_scale = float(studio.settings.get("sig_scale", 100)) / 100.0
    except: sig_scale = 1.0

    if show_esign and sig_b64:
        img_h = int(45 * sig_scale)
        
        # --- THE FIX: Fetch the nudge and apply it via CSS relative positioning! ---
        try: sig_nudge = int(studio.settings.get("sig_nudge", 0))
        except: sig_nudge = 0
        
        img_html = f'<img src="{sig_b64}" style="height: {img_h}px; object-fit: contain; position: relative; top: {sig_nudge}px; margin-top: 2px; margin-bottom: 2px;">'
        # ---------------------------------------------------------------------------
        
        sig_html = f"""
        <div style="display: inline-flex; flex-direction: column; align-items: center; text-align: center;">
            <div style="{css_sig} font-weight: bold; margin-bottom: 0px; line-height: 1.1;">For {ctx['c_name'].upper()}</div>
            {img_html}
            <div style="{css_sig} margin-bottom: 2px; line-height: 1.1;">{sig_role}</div>
        </div>
        """
    else:
        # --- THE FIX: Inject an invisible 45px block so the manual pen gap matches exactly! ---
        sig_html = f"""
        <div style="display: inline-flex; flex-direction: column; align-items: center; text-align: center;">
            <div style="{css_sig} font-weight: bold; margin-bottom: 0px; line-height: 1.1;">For {ctx['c_name'].upper()}</div>
            <div style="height: 45px; margin-top: 2px; margin-bottom: 2px;"></div>
            <div style="{css_sig} margin-bottom: 2px; line-height: 1.1;">{sig_role}</div>
        </div>
        """
        # --------------------------------------------------------------------------------------

    return terms_html, page_html, sig_html