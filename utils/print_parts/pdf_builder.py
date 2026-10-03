import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    utils_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(utils_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

from utils.print_parts.helpers import safe_color
from utils.print_parts.pdf_header import build_header
from utils.print_parts.pdf_table import build_table
from utils.print_parts.pdf_footer import build_footer

def build_html(ctx):
    studio = ctx["studio"]
    inv = studio.inv_data
    pages_data = ctx["pages_data"]
    
    def get_css(key, def_sz=10):
        fonts = studio.settings.get("fonts", {})
        colors = studio.settings.get("colors", {})
        bolds = studio.settings.get("bolds", {})
        unders = studio.settings.get("underlines", {})

        try: sz = int(float(fonts.get(key, def_sz)))
        except: sz = def_sz
        
        col = safe_color(colors.get(key, "#000000"))
        is_bold = bolds.get(key, False) or str(bolds.get(key, 'False')).lower() == 'true' or bolds.get(key) in [1, "1"]
        is_under = unders.get(key, False) or str(unders.get(key, 'False')).lower() == 'true' or unders.get(key) in [1, "1"]
        
        b = "bold" if is_bold else "normal"
        u = "text-decoration: underline; text-underline-offset: 3px; text-decoration-skip-ink: none;" if is_under else "text-decoration: none;"
        return f"font-size: {sz}pt; color: {col}; font-weight: {b}; {u}"

    main_html = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Invoice {ctx['inv_num']}</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;700&family=Arial:wght@400;700&display=swap" rel="stylesheet">
        <style>
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                box-sizing: border-box;
            }}
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Arial', 'Noto Sans Bengali', sans-serif; margin: 0; padding: 0; background: #525659; }}
            
            /* THE FIX: Rigid Flexbox column to stretch the middle space naturally */
            .page {{ 
                width: 210mm; 
                height: 297mm !important; 
                min-height: 297mm !important;
                max-height: 297mm !important;
                padding: 20px 20px 25px 20px; 
                margin: 10px auto; 
                background: white; 
                box-sizing: border-box; 
                box-shadow: 0 0 10px rgba(0,0,0,0.5); 
                page-break-after: always; 
                display: flex;
                flex-direction: column;
                overflow: hidden; 
            }}
            
            @media print {{ 
                body {{ background: white; }} 
                .page {{ 
                    margin: 0 !important; 
                    box-shadow: none !important; 
                    border: none !important; 
                }} 
            }}
            
            .header-section {{ width: 100%; flex-shrink: 0; }}
            .footer-section {{ width: 100%; flex-shrink: 0; }}
            
            .table-wrapper {{ 
                flex-grow: 1; 
                display: flex; 
                flex-direction: column; 
                border-left: 0.75pt solid #000; 
                border-right: 0.75pt solid #000; 
            }}
            
            .filler-lines {{
                flex-grow: 1;
                display: flex;
                width: 100%;
            }}
            
            .filler-col {{
                border-right: 0.75pt solid #000;
                box-sizing: border-box;
            }}
            
            table {{ box-sizing: border-box; max-width: 100%; }}
            .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; flex-shrink: 0; }}
            
            .meta-table {{ width: 100%; border-collapse: collapse; border: 0.75pt solid #000; flex-shrink: 0; table-layout: fixed; }}
            .meta-table > .meta-body > tr > td {{ border: none; vertical-align: top; padding: 0; }}
            
            .invoice-table {{ 
                width: 100%; 
                border-collapse: collapse; 
                table-layout: fixed; 
            }}
            .invoice-table th {{ 
                border-bottom: 0.75pt solid #000; 
                border-right: 0.75pt solid #000; 
                padding: 5px; 
                text-align: center; 
                background-color: {studio.settings.get("colors", {}).get("tab_head_bg", "#ffffff")}; 
            }}
            
            .invoice-table td {{ 
                border-right: 0.75pt solid #000; 
                padding: 1px 5px; 
                vertical-align: top; 
                line-height: 1.2; 
            }}
            
            .invoice-table th:last-child, .invoice-table td:last-child {{
                border-right: none;
            }}
            
            .invoice-table tr {{
                page-break-inside: avoid !important;
                break-inside: avoid !important;
            }}
            
            .shrink-fit {{
                white-space: nowrap;
                overflow: hidden;
            }}
        </style>
    </head>
    <body>
    '''

    running_total = 0.0
    try: start_page_num = int(inv.get("page_num", 1))
    except: start_page_num = 1

    for pg_num, page_items in enumerate(pages_data):
        is_last = (pg_num == len(pages_data) - 1)
        curr_page_disp = start_page_num + pg_num
        
        main_html += f'<div class="page">'
        
        main_html += f'<div class="header-section">'
        main_html += build_header(ctx, get_css)
        main_html += f'</div>'
        
        # The wrapper is opened inside pdf_table.py and closed in pdf_footer.py!
        table_html, running_total = build_table(ctx, get_css, page_items, pg_num, running_total)
        main_html += table_html
        main_html += build_footer(ctx, get_css, pg_num, is_last, curr_page_disp, running_total)
        
        main_html += "</div>"

    main_html += '''
        <script>
            window.onload = function() { 
                const shrinkFits = document.querySelectorAll('.shrink-fit');
                shrinkFits.forEach(td => {
                    let fontSize = parseFloat(window.getComputedStyle(td).fontSize);
                    const minFontSize = 5;
                    let safety = 50; 
                    while(td.scrollWidth > td.clientWidth && fontSize > minFontSize && safety > 0) {
                        fontSize -= 0.5;
                        td.style.fontSize = fontSize + 'px';
                        safety--;
                    }
                });
                setTimeout(function() { window.print(); }, 500); 
            }
        </script>
    </body>
    </html>
    '''
    return main_html