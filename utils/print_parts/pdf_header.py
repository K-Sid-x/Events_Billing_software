import database

def build_header(ctx, get_css):
    studio = ctx["studio"]
    inv = studio.inv_data
    
    c_sec = get_css('sec'); c_name = get_css('name')
    c_addr = get_css('addr'); c_gst = get_css('gst')
    c_contact = get_css('contact'); c_title = get_css('doc_title')
    
    c_bill_title = get_css('bill_title'); c_bill_prefix = get_css('bill_prefix')
    c_bill_name = get_css('bill_name'); c_bill_addr = get_css('bill_addr')
    c_bill_phone = get_css('bill_phone'); c_bill_gst = get_css('bill_gst')
    
    c_serv_title = get_css('serv_title'); c_serv_prefix = get_css('serv_prefix')
    c_serv_addr = get_css('serv_addr'); c_serv_del = get_css('serv_del')
    c_serv_bill = get_css('serv_bill')

    layout = studio.settings.get("layout", "Classic")
    swap_title = int(studio.settings.get('swap_title_order', 0)) == 1
    
    logo_html = ""
    if ctx.get("logo_b64"):
        l_sz = int(float(studio.settings.get("logo_size", 120)))
        br = "50%" if studio.settings.get("logo_shape") == "Circle" else "0"
        logo_html = f'<img src="{ctx["logo_b64"]}" style="max-width: {l_sz}px; max-height: {l_sz}px; border-radius: {br}; object-fit: contain;">'

    contact_html = ""
    if ctx["c_phone"]: 
        formatted_phone = ctx['c_phone'].replace('\n', '<br>')
        contact_html += f"<div style='line-height: 1.2;'>{studio.settings.get('lbl_phone', 'Ph. No:')} {formatted_phone}</div>"
    if ctx["c_email"]: contact_html += f"<div style='line-height: 1.2;'>Email: {ctx['c_email']}</div>"

    title_order_html = f"""
        <div style="{c_sec} line-height: 1.0; margin-bottom: 2px;">{ctx['c_sec']}</div>
        <div style="{c_name} line-height: 1.0; margin-bottom: 2px;">{ctx['c_name'].upper()}</div>
    """ if swap_title else f"""
        <div style="{c_name} line-height: 1.0; margin-bottom: 2px;">{ctx['c_name'].upper()}</div>
        <div style="{c_sec} line-height: 1.0; margin-bottom: 2px;">{ctx['c_sec']}</div>
    """

    gst_html = f'<div style="{c_gst} margin-top: 2px; line-height: 1.0;">GSTIN: {ctx["c_gst"]}</div>' if ctx["c_gst"] else ""

    html = ""
    if layout == "Split Header (Left-Center-Right)":
        html += f"""
        <table class="header-table">
            <tr>
                <td style="width: 25%; text-align: left; vertical-align: top;">{logo_html}</td>
                <td style="width: 50%; text-align: center; vertical-align: top;">
                    {title_order_html}
                    <div style="{c_addr} line-height: 1.1;">{ctx['c_addr']}</div>
                    {gst_html}
                </td>
                <td style="width: 25%; text-align: right; vertical-align: top; white-space: nowrap;">
                    <div style="{c_contact}">{contact_html}</div>
                </td>
            </tr>
        </table>
        """
    else:
        ta = "left" if layout == "Left-Aligned" else "right"
        html += f"""
        <table class="header-table">
            <tr>
                {"<td style='width: 1%; white-space: nowrap; vertical-align: top; padding-right: 15px;'>" + logo_html + "</td>" if logo_html and layout == "Left-Aligned" else ""}
                <td style="text-align: {ta}; vertical-align: top;">
                    {title_order_html}
                    <div style="{c_addr} line-height: 1.1; max-width: 400px; {'margin-left: auto;' if ta=='right' else ''}">{ctx['c_addr']}</div>
                    <div style="{c_contact} margin-top: 4px; white-space: nowrap;">{contact_html}</div>
                    {gst_html}
                </td>
                {"<td style='width: 1%; white-space: nowrap; vertical-align: top; padding-left: 15px;'>" + logo_html + "</td>" if logo_html and layout != "Left-Aligned" else ""}
            </tr>
        </table>
        """

    html += f'<div style="border-bottom: 2px solid #000; margin-bottom: 10px; flex-shrink: 0;"></div>'
    
    # --- THE FIX: Securely read GST status from memory (Prevents cross-company data leaks!) ---
    has_gst = ctx.get("has_gst", True)
    # ------------------------------------------------------------------------------------------
    
    doc_title = "TAX INVOICE" if has_gst else "INVOICE"
    html += f'<div style="text-align: center; {c_title} margin-bottom: 10px; flex-shrink: 0;">{doc_title}</div>'

    cust_name = ctx.get('cust_name', '')
    cust_addr = ctx.get('cust_addr', '')
    cust_phone = ctx.get('cust_phone', '')
    cust_gst = ctx.get('cust_gst', '')
    
    if not cust_phone or str(cust_phone).strip().lower() in ["not provided", "none", "null", "not available", "na", "n/a", ""]: cust_phone = ""
    if not cust_gst or str(cust_gst).strip().lower() in ["not provided", "none", "null", "not available", "na", "n/a", ""]: cust_gst = ""

    meta_pairs = [("Invoice No:", ctx['inv_num']), ("Invoice Date:", ctx['inv_date'])]
    if ctx.get('show_eway'): meta_pairs.append(("E-Way Bill:", ctx.get('eway_bill', '')))
    for m_key, m_lbl in [("challan_no", "Challan No:"), ("challan_date", "Challan Date:"), ("lr_no", "L.R. No:"), ("lr_date", "L.R. Date:"), ("veh_no", "Vehicle No:")]:
        if inv.get(m_key): meta_pairs.append((m_lbl, inv.get(m_key)))

    meta_bg = studio.settings.get("colors", {}).get("meta_head_bg", "#ffffff")
    
    meta_html = "<div style='height: 165px; display: flex; flex-direction: column; box-sizing: border-box; overflow: hidden;'>"
    for idx, (m_lbl, m_val) in enumerate(meta_pairs):
        lbl_key = "inv_no_lbl"; val_key = "inv_no_val"
        if "Date" in m_lbl and "Invoice" in m_lbl: lbl_key = "inv_dt_lbl"; val_key = "inv_dt_val"
        elif "E-Way" in m_lbl: lbl_key = "eway_lbl"; val_key = "eway_val"
        dyn_lbl_css = get_css(lbl_key); dyn_val_css = get_css(val_key)
        b_top = "border-top: 0.75pt solid #000;" if idx > 0 else ""
        meta_html += f"<div style='flex-grow: 1; box-sizing: border-box; {b_top} display: flex; flex-direction: column;'>"
        meta_html += f"<table style='width: 100%; border-collapse: collapse; margin: 0; padding: 0;'><tr><td style='background-color: {meta_bg}; border-bottom: 0.75pt solid #000; padding: 4px 5px; height: 26px; {dyn_lbl_css}'>{m_lbl}</td></tr></table>"
        meta_html += f"<div style='padding: 8px 5px 4px 5px; flex-grow: 1; {dyn_val_css} word-break: break-word; overflow-wrap: break-word;'>{m_val}</div>"
        meta_html += "</div>"
    meta_html += "</div>"

    lbl_phone_str = studio.settings.get("lbl_phone", "Ph. No:")
    lbl_gst_str = studio.settings.get("lbl_gst", "GSTIN:")
    lbl_name_str = studio.settings.get("lbl_name", "Name:")
    lbl_addr_str = studio.settings.get("lbl_addr", "Address:")
    lbl_billed_to = studio.settings.get('lbl_billed_to', 'BILLED TO:')

    if has_gst:
        bottom_bill_html = f"""
            <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_bill_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_phone_str}</td><td style="border: none; padding: 1px 0; {c_bill_phone} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{cust_phone}</td></tr>
            <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_bill_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_gst_str}</td><td style="border: none; padding: 1px 0; {c_bill_gst} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{cust_gst}</td></tr>
        """
    else:
        bottom_bill_html = f"""
            <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_bill_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_phone_str}</td><td style="border: none; padding: 1px 0; {c_bill_phone} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{cust_phone}</td></tr>
        """

    cust_html = f"""
        <div style="height: 165px; padding: 0; position: relative; box-sizing: border-box; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; margin: 0; padding: 0;"><tr><td style="background-color: {meta_bg}; {c_bill_title} padding: 3px 5px; height: 26px; border-bottom: 0.75pt solid #000;">{lbl_billed_to}</td></tr></table>
            <div style="position: absolute; top: 34px; left: 0; right: 0; padding: 0 2px;">
                <table style="width: 100%; border-collapse: collapse; border: none; table-layout: fixed;">
                    <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_bill_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_name_str}</td><td style="border: none; padding: 1px 0; {c_bill_name} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{cust_name}</td></tr>
                    <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_bill_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_addr_str}</td><td style="border: none; padding: 1px 0; {c_bill_addr} vertical-align: top; word-break: break-word; overflow-wrap: break-word; max-height: 65px; overflow: hidden;">{cust_addr}</td></tr>
                </table>
            </div>
            <div style="position: absolute; bottom: 5px; left: 0; right: 0; padding: 0 2px;">
                <table style="width: 100%; border-collapse: collapse; border: none; table-layout: fixed;">
                    {bottom_bill_html}
                </table>
            </div>
        </div>
    """

    s_bill_val = ctx['serv_bill_date'] if (ctx['serv_bill_date'] and ctx['serv_bill_date'].strip() != "to") else ""
    bottom_serv_html = f"""
        <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_serv_prefix} text-align: right; vertical-align: top; white-space: nowrap;">Del. Date:</td><td style="border: none; padding: 1px 0; {c_serv_del} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{ctx["serv_del_date"]}</td></tr>
        <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_serv_prefix} text-align: right; vertical-align: top; white-space: nowrap;">Bill Date:</td><td style="border: none; padding: 1px 0; {c_serv_bill} vertical-align: top; word-break: break-word; overflow-wrap: break-word;">{s_bill_val}</td></tr>
    """

    serv_html = f"""
        <div style="height: 165px; padding: 0; position: relative; box-sizing: border-box; overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse; margin: 0; padding: 0;"><tr><td style="background-color: {meta_bg}; {c_serv_title} padding: 3px 5px; height: 26px; border-bottom: 0.75pt solid #000;">PLACE OF SERVICE:</td></tr></table>
            <div style="position: absolute; top: 34px; left: 0; right: 0; padding: 0 2px;">
                <table style="width: 100%; border-collapse: collapse; border: none; table-layout: fixed;">
                    <tr><td style="width: 85px; border: none; padding: 1px 5px 1px 0; {c_serv_prefix} text-align: right; vertical-align: top; white-space: nowrap;">{lbl_addr_str}</td><td style="border: none; padding: 1px 0; {c_serv_addr} vertical-align: top; word-break: break-word; overflow-wrap: break-word; max-height: 65px; overflow: hidden;">{ctx['serv_addr']}</td></tr>
                </table>
            </div>
            <div style="position: absolute; bottom: 5px; left: 0; right: 0; padding: 0 2px;">
                <table style="width: 100%; border-collapse: collapse; border: none; table-layout: fixed;">
                    {bottom_serv_html}
                </table>
            </div>
        </div>
    """

    if int(studio.settings.get('swap_boxes_var', 0)) == 1: boxes = [(24, meta_html), (38, serv_html), (38, cust_html)]
    else: boxes = [(38, cust_html), (38, serv_html), (24, meta_html)]

    html += f"""
    <table class="meta-table" style="border-collapse: separate; border-spacing: 0;">
        <tbody class="meta-body">
            <tr>
                <td style="width: {boxes[0][0]}%; padding: 0; border-right: 0.5pt solid #000;">{boxes[0][1]}</td>
                <td style="padding: 0; border-right: 0.5pt solid #000;">{boxes[1][1]}</td>
                <td style="width: {boxes[2][0]}%; padding: 0;">{boxes[2][1]}</td>
            </tr>
        </tbody>
    </table>
    """

    # --- SUBJECT IS RENDERED HERE IN PART 1 FLOW ---
    if ctx['show_subject'] and ctx['subject_text']:
        align = str(inv.get('subj_align', 'center')).lower().strip()
        ta = "center" if align == "center" else "right" if align == "right" else "left"
        subject_text = ctx['subject_text']
        css_subj = get_css('subj_val')
        css_subj_lbl = get_css('subj_label')
        
        if "@@B@@" in subject_text: css_subj += " font-weight: bold;"
        if "@@U@@" in subject_text: css_subj += " text-decoration: underline; text-underline-offset: 3px; text-decoration-skip-ink: none;"
        clean_subj = subject_text.replace('@@B@@', '').replace('@@U@@', '').replace('\n', '<br>')
        
        html += f"""
        <div style="border: 1px solid #000; border-top: none; padding: 8px 5px; position: relative; min-height: 20px; box-sizing: border-box; flex-shrink: 0;">
            <div style="{css_subj_lbl} position: absolute; left: 5px; top: 8px; z-index: 2;">Subject:</div>
            <div style="width: 100%; text-align: {ta}; {css_subj} z-index: 1; padding: 0 75px; box-sizing: border-box; word-break: break-word;">{clean_subj}</div>
        </div>
        """
    return html