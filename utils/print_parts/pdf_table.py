from utils.print_parts.helpers import format_currency

def parse_f(val):
    try: return float(str(val).replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "").strip() or 0)
    except: return 0.0

def build_table(ctx, get_css, page_items, pg_num, running_total):
    studio = ctx["studio"]
    curr_format = studio.settings.get("currency_format", "Indian Rupees (₹)")
    
    has_gst = ctx.get("has_gst", True)
    
    cw_slno = float(studio.settings.get("col_widths", {}).get("slno", 6))
    cw_qty = float(studio.settings.get("col_widths", {}).get("qty", 8))
    cw_hsn = float(studio.settings.get("col_widths", {}).get("hsn", 12))
    cw_rate = float(studio.settings.get("col_widths", {}).get("rate", 12))
    cw_days = float(studio.settings.get("col_widths", {}).get("days", 8))
    cw_amt = float(studio.settings.get("col_widths", {}).get("amt", 14))
    
    # --- THE FIX: Re-allocate the HSN width directly into the Particulars column if Non-GST! ---
    if not has_gst:
        cw_part = max(5.0, 100.0 - sum([cw_slno, cw_qty, cw_rate, cw_days, cw_amt]))
    else:
        cw_part = max(5.0, 100.0 - sum([cw_slno, cw_qty, cw_hsn, cw_rate, cw_days, cw_amt]))
    
    css_th_slno = get_css('th_slno'); css_th_qty = get_css('th_qty'); css_th_part = get_css('th_part')
    css_th_hsn = get_css('th_hsn'); css_th_rate = get_css('th_rate'); css_th_days = get_css('th_days')
    css_th_amt = get_css('th_amt')
    
    css_tr_part = get_css('tr_part'); css_tr_amt = get_css('tr_amt'); css_tr_slno = get_css('tr_slno')
    css_tr_qty = get_css('tr_qty'); css_tr_hsn = get_css('tr_hsn'); css_tr_rate = get_css('tr_rate')
    css_tr_days = get_css('tr_days')

    hsn_th = f'<th class="shrink-fit" style="width: {cw_hsn}%; {css_th_hsn}">HSN/SAC</th>' if has_gst else ""
    
    # THE FIX: Open the flex-growing wrapper here
    html = f"""
    <div class="table-wrapper">
        <table class="invoice-table">
            <thead>
                <tr>
                    <th class="shrink-fit" style="width: {cw_slno}%; {css_th_slno}">Sl No.</th>
                    <th class="shrink-fit" style="width: {cw_qty}%; {css_th_qty}">Qnty</th>
                    <th style="width: {cw_part}%; {css_th_part}">Particulars</th>
                    {hsn_th}
                    <th class="shrink-fit" style="width: {cw_rate}%; {css_th_rate}">Rate</th>
                    <th class="shrink-fit" style="width: {cw_days}%; {css_th_days}">Days</th>
                    <th class="shrink-fit" style="width: {cw_amt}%; {css_th_amt}">Amount</th>
                </tr>
            </thead>
            <tbody>
    """
    if pg_num > 0:
        f_tot = format_currency(running_total, curr_format)
        hsn_td = "<td></td>" if has_gst else ""
        html += f"""
        <tr><td></td><td></td><td style="{css_tr_part} font-weight: bold;">B / F</td>{hsn_td}<td></td><td></td><td class="shrink-fit" style="{css_tr_amt} font-weight: bold; text-align: right;">{f_tot}</td></tr>
        """

    for item in page_items:
        it = item.get("data", {})
        
        # --- THE FIX: Line-by-Line HTML Rendering ---
        raw_name = str(it.get("name", ""))
        html_lines = []
        for line in raw_name.split('\n'):
            l_b = "@@B@@" in line
            l_u = "@@U@@" in line
            c_line = line.replace("@@B@@", "").replace("@@U@@", "")
            
            # 1. Convert consecutive spaces (2, 3, or 4+) into HTML non-breaking spaces
            c_line = c_line.replace("    ", "&nbsp;&nbsp;&nbsp;&nbsp;").replace("   ", "&nbsp;&nbsp;&nbsp;").replace("  ", "&nbsp;&nbsp;")
            
            f_w = "font-weight: bold;" if l_b else ""
            t_d = "text-decoration: underline; text-underline-offset: 3px; text-decoration-skip-ink: none;" if l_u else ""
            
            if f_w or t_d:
                # 2. Break the underline formatting ONLY on the huge gaps! 
                # Single spaces (like "Total (sq.ft)") will stay underlined as one continuous block.
                safe_line = c_line.replace("&nbsp;", f'</span>&nbsp;<span style="{f_w} {t_d}">')
                html_lines.append(f'<span style="{f_w} {t_d}">{safe_line}</span>')
            else:
                html_lines.append(c_line)
                
        final_name_html = "<br>".join(html_lines)
        # --------------------------------------------

        sl_val = str(item.get("idx", it.get("sl", ""))).strip()
        if sl_val in ["0", "0.0", "None"]: sl_val = ""
        
        qty_val = str(it.get("qty", "")).strip()
        unit_val = str(it.get("unit", "")).strip()
        if qty_val and unit_val:
            qty_val = f"{qty_val} {unit_val}"
        elif unit_val and not qty_val:
            qty_val = unit_val
            
        hsn_val = str(it.get("hsn", "")).strip()
        rate_str = str(it.get("rate", "")).strip()
        amt_str = str(it.get("amt", "")).strip()
        
        r_f = parse_f(rate_str); a_f = parse_f(amt_str)
        running_total += a_f
        r_disp = format_currency(r_f, curr_format) if r_f != 0 else ""
        a_disp = format_currency(a_f, curr_format) if a_f != 0 else ""
        days_val = str(it.get("days", "")).strip()
        
        # --- THE FIX: Erased the fallback logic that forces '1' ---
        if days_val in ["0", "0.0", "None"]: days_val = ""
            
        if not sl_val and r_f == 0.0 and a_f == 0.0:
            sl_val = ""; qty_val = ""; hsn_val = ""; r_disp = ""; days_val = ""; a_disp = ""

        hsn_td_html = f'<td class="shrink-fit" style="{css_tr_hsn} text-align: center;">{hsn_val}</td>' if has_gst else ""

        html += f"""
        <tr>
            <td class="shrink-fit" style="{css_tr_slno} text-align: center;">{sl_val}</td>
            <td class="shrink-fit" style="{css_tr_qty} text-align: center;">{qty_val}</td>
            <td style="{css_tr_part} word-break: break-word; overflow-wrap: break-word;">{final_name_html}</td>
            {hsn_td_html}
            <td class="shrink-fit" style="{css_tr_rate} text-align: right;">{r_disp}</td>
            <td class="shrink-fit" style="{css_tr_days} text-align: center;">{days_val}</td>
            <td class="shrink-fit" style="{css_tr_amt} text-align: right;">{a_disp}</td>
        </tr>
        """
        
    hsn_filler = f'<td style="width: {cw_hsn}%; border-bottom: none;"></td>' if has_gst else ""
    
    # THE FIX: Add the filler-lines to securely extend borders down to the footer
    html += f"""
            </tbody>
        </table>
        
        <table class="invoice-table" style="flex-grow: 1; height: 100%; border-top: none;">
            <tr>
                <td style="width: {cw_slno}%; border-bottom: none;"></td>
                <td style="width: {cw_qty}%; border-bottom: none;"></td>
                <td style="width: {cw_part}%; border-bottom: none;"></td>
                {hsn_filler}
                <td style="width: {cw_rate}%; border-bottom: none;"></td>
                <td style="width: {cw_days}%; border-bottom: none;"></td>
                <td style="width: {cw_amt}%; border-bottom: none; border-right: none;"></td>
            </tr>
        </table>
    """
    
    return html, running_total