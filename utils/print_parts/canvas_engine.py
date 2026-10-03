import tkinter as tk
from utils.print_parts.helpers import safe_color, number_to_words, fetch_global_settings
from utils.print_parts.canvas_header import draw_header
from utils.print_parts.canvas_table import draw_table
from utils.print_parts.canvas_footer import draw_footer

def parse_f(val):
    try: return float(str(val).replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "").strip() or 0)
    except: return 0.0

def draw_pages(studio):
    studio.canvas.delete("all")
    studio.page_wrappers.clear()
    studio.canvas.images = []
    if hasattr(studio, '_canvas_img_cache'):
        studio._canvas_img_cache.clear()

    paper_size_name = "A4 (210*297mm)"
    if hasattr(studio, 'cb_paper'): paper_size_name = studio.cb_paper.get()
    elif hasattr(studio, 'cb_s3'): paper_size_name = studio.cb_s3.get()

    base_w, base_h = studio.sizes.get(paper_size_name, studio.sizes["A4 (210*297mm)"])["px"]
    z = studio.zoom_var.get() / 100.0

    cvs_w = studio.canvas.winfo_width()
    if cvs_w < 50: cvs_w = 900

    sf = (cvs_w - 40) / base_w if z == 1.0 else z
    if sf > 1 and z == 1.0: sf = 1.0

    paper_w = int(base_w * sf)
    paper_h = int(base_h * sf)
    x_off = max(20, (cvs_w - paper_w) // 2)

    def s(val): return int(val * sf)

    settings = studio.settings
    def get_col(key): return safe_color(settings.get("colors", {}).get(key, "#000000"))
    
    def get_f(key, def_sz=10):
        try: return max(1, int(float(settings.get("fonts", {}).get(key, def_sz)) * sf))
        except: return max(1, int(def_sz * sf))

    def c_txt(x, y, text, key, bold=False, italic=False, underline=False, anchor="nw", width=0, max_w=None, max_h=None, tags=(), bg_solid=False):
        if not text: return y
        is_bold = bold or str(settings.get("bolds", {}).get(key, False)).lower() == 'true' or settings.get("bolds", {}).get(key) == 1
        is_under = underline or str(settings.get("underlines", {}).get(key, False)).lower() == 'true' or settings.get("underlines", {}).get(key) == 1

        font_mod = " ".join([m for m, cond in zip(["bold", "italic", "underline"], [is_bold, italic, is_under]) if cond])
        actual_f = get_f(key)

        just = tk.RIGHT if "e" in anchor else tk.CENTER if "center" in anchor or anchor in ["n", "s"] else tk.LEFT
        font_tup = ("Arial", actual_f, font_mod) if font_mod else ("Arial", actual_f)

        t_id = studio.canvas.create_text(x, y, text=text, font=font_tup, fill=get_col(key), anchor=anchor, width=width, justify=just, tags=tags)

        if (max_w and width == 0) or max_h:
            min_f = max(1, int(4 * sf))
            while actual_f > min_f:
                bbox = studio.canvas.bbox(t_id)
                if not bbox: break
                if ((max_w and width == 0) and (bbox[2] - bbox[0]) > max_w) or (max_h and (bbox[3] - bbox[1]) > max_h):
                    actual_f -= 1
                    font_tup = ("Arial", actual_f, font_mod) if font_mod else ("Arial", actual_f)
                    studio.canvas.itemconfig(t_id, font=font_tup)
                else: break

        bbox = studio.canvas.bbox(t_id)
        if bbox: return bbox[3] + s(2)
        return y + int(actual_f * 1.5)

    try: start_page_num = int(studio.inv_data.get("page_num", 1))
    except: start_page_num = 1

    # --- THE FIX: Fetch global settings for preview ---
    global_curr, global_date_fmt = fetch_global_settings()

    ctx = {
        "studio": studio, "cvs": studio.canvas, "s": s, "c_txt": c_txt,
        "get_col": get_col, "get_f": get_f, "parse_f": parse_f,
        "w": paper_w, "h": paper_h, "x_off": x_off, "pad": s(20),
        "sf": sf, 
        "curr_format": global_curr,
        "date_fmt": global_date_fmt,
        "state": {
            "cy": 40 + s(20),
            "y_off": 40,
            "page_count": start_page_num,
            "running_total": 0.0,
            "t_start": 0,
            "cxs": []
        }
    }

    words_val = studio.inv_data.get('words', '') or number_to_words(parse_f(studio.inv_data.get("total", 0)), ctx["curr_format"])
    for c_name_str in ["Pounds", "Dollars", "Euros", "Rupees", "Dirhams", "Dinars"]:
        if words_val.startswith(f"{c_name_str} ") and words_val.endswith(" Only"):
            words_val = words_val[len(c_name_str)+1:-5] + f" {c_name_str} Only"
            break
    ctx["words_val"] = words_val

    draw_header(ctx)
    draw_table(ctx)
    draw_footer(ctx)

    studio.total_pages = ctx["state"]["page_count"] - start_page_num + 1
    if hasattr(studio, "lbl_total"): studio.lbl_total.config(text=f"of {studio.total_pages}")
    elif hasattr(studio, "lbl_p"): studio.lbl_p.config(text=f"of {studio.total_pages}")
    if hasattr(studio, "e_to"):
        studio.e_to.delete(0, "end")
        studio.e_to.insert(0, str(studio.total_pages))
    studio.canvas.configure(scrollregion=(0, 0, cvs_w, ctx["state"]["y_off"] + paper_h + 40))