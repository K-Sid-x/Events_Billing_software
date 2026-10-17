from utils.print_parts.helpers import format_currency

def parse_f(val):
    try: return float(str(val).replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "").strip() or 0)
    except: return 0.0

def build_table(ctx, get_css, page_items, pg_num, running_total):
    studio = ctx["studio"]
    curr_format = ctx.get("curr_format") or studio.settings.get("currency_format", "Indian Rupees (₹)")
    
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
        
        # --- THE FIX: Smart Splitter (Respects UI Underline & Bold) ---
        import re
        raw_name = str(it.get("name", ""))
        
        left_lines = []
        right_text = ""
        has_equals = False
        gap_is_underlined = False
        gap_is_bold = False
        
        for line in raw_name.split('\n'):
            # THE FIX: Parenthesis Tracker. Only split on '=' if it's outside brackets!
            valid_eq_idx = -1
            p_count = 0
            for i, char in enumerate(line):
                if char == '(': p_count += 1
                elif char == ')': p_count = max(0, p_count - 1)
                elif char == '=' and p_count == 0:
                    valid_eq_idx = i
                    break
                    
            if valid_eq_idx != -1 and not has_equals:
                left_raw = line[:valid_eq_idx]
                
                # Detect if the UI underline or bold tag was left OPEN before the '=' sign
                u_open = left_raw.count("@@U@@") + left_raw.count("[U]")
                u_close = left_raw.count("@@/U@@") + left_raw.count("[/U]")
                gap_is_underlined = (u_open > u_close)
                
                b_open = left_raw.count("@@B@@") + left_raw.count("[B]")
                b_close = left_raw.count("@@/B@@") + left_raw.count("[/B]")
                gap_is_bold = (b_open > b_close)
                
                # Strip trailing spaces so the CSS stretching line seamlessly connects to the last letter!
                left_str = left_raw.rstrip()
                
                left_lines.append(left_str)
                # THE FIX: Slice the right text perfectly using our new tracker
                right_text = line[valid_eq_idx+1:].strip()
                has_equals = True
            else:
                left_lines.append(line)
                
        def apply_html_tags(text_block):
            t = text_block.replace("@@B@@", "[B]").replace("@@/B@@", "[/B]")
            t = t.replace("@@U@@", "[U]").replace("@@/U@@", "[/U]")
            
            if "[B]" in t and "[/B]" not in t: t += "[/B]"
            if "[U]" in t and "[/U]" not in t: t += "[/U]"
            
            t = t.replace("[B]", "<span style='font-weight: bold;'>").replace("[/B]", "</span>")
            t = t.replace("[U]", "<span style='text-decoration: underline; text-underline-offset: 3px; text-decoration-skip-ink: none;'>").replace("[/U]", "</span>")
            return t.replace("  ", "&nbsp;&nbsp;")
            
        if has_equals:
            clean_right = re.sub(r'(\[B\]|\[/B\]|\[U\]|\[/U\]|@@B@@|@@/B@@|@@U@@|@@/U@@)', '', right_text).strip()
            html_left = apply_html_tags("<br>".join(left_lines))
            
            if gap_is_underlined:
                # THE FIX: Fuse the '=' and text into ONE single underlined string. Zero gaps allowed!
                right_combined = f"=&nbsp;&nbsp;{clean_right}"
                if gap_is_bold: right_combined = f"[B]{right_combined}[/B]"
                right_combined = f"[U]{right_combined}[/U]"
                html_right_combined = apply_html_tags(right_combined)
                
                final_name_html = f"""
                <div style="display: flex; align-items: flex-end; width: 100%; height: 100%;">
                    <div style="word-break: break-word; overflow-wrap: break-word; flex-shrink: 0;">{html_left}</div>
                    <div style="flex-grow: 1; border-bottom: 1px solid #000; margin: 0 0 0px 0; min-width: 15px;"></div>
                    <div style="flex-shrink: 0; width: 85px; text-align: left; word-break: break-all; overflow-wrap: anywhere;">
                        {html_right_combined}
                    </div>
                </div>
                """
            else:
                right_formatted = clean_right
                if gap_is_bold: right_formatted = f"[B]{right_formatted}[/B]"
                html_right = apply_html_tags(right_formatted)
                
                final_name_html = f"""
                <div style="display: flex; align-items: flex-end; justify-content: space-between; width: 100%; height: 100%;">
                    <div style="flex-grow: 1; padding-right: 15px; word-break: break-word; overflow-wrap: break-word;">{html_left}</div>
                    <div style="flex-shrink: 0; width: 85px; display: flex; text-align: left;">
                        <span style="margin-right: 5px;">=</span>
                        <span style="flex-grow: 1; word-break: break-all; overflow-wrap: anywhere;">{html_right}</span>
                    </div>
                </div>
                """
        else:
            final_name_html = f'<div style="word-break: break-word; overflow-wrap: break-word;">{apply_html_tags(raw_name.replace(chr(10), "<br>"))}</div>'
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