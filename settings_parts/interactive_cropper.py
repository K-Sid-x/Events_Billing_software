import tkinter as tk
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

import database

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

class InteractiveCropper(tk.Toplevel):
    def __init__(self, parent, image_path, on_crop_done):
        super().__init__(parent)
        
        _is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        BG_COLOR = "#0f172a" if _is_dark else "#f0f9ff"
        CARD_BG = "#1e293b" if _is_dark else "#ffffff"
        BORDER_COLOR = "#334155" if _is_dark else "#bae6fd"
        TEXT_PRIMARY = "#f8fafc" if _is_dark else "#0f172a"
        ACCENT_BLUE = "#3b82f6" if _is_dark else "#0ea5e9"
        
        self.title("Adjust Logo Crop")
        self.geometry("700x650")
        self.configure(bg=BG_COLOR)
        self.grab_set() 
        
        self.on_crop_done = on_crop_done
        self.image_path = image_path
        self.orig_img = Image.open(image_path).convert("RGBA")
        
        self.disp_w, self.disp_h = 600, 450
        self.disp_img = self.orig_img.copy()
        
        try: resamp = Image.Resampling.LANCZOS
        except AttributeError: resamp = Image.LANCZOS
            
        self.disp_img.thumbnail((self.disp_w, self.disp_h), resamp)
        
        self.ratio_x = self.orig_img.width / self.disp_img.width
        self.ratio_y = self.orig_img.height / self.disp_img.height
        
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        
        tk.Label(self, text="Drag any edge or corner to crop independently:", font=("Arial", 11, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(pady=10)
        
        self.canvas = tk.Canvas(self, width=self.disp_img.width, height=self.disp_img.height, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER_COLOR, cursor="crosshair")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        
        pad = 20
        self.box_coords = [pad, pad, self.disp_img.width-pad, self.disp_img.height-pad]
        
        self.rect_id = self.canvas.create_rectangle(*self.box_coords, outline=ACCENT_BLUE, width=2, dash=(6, 4))
        self.markers = [self.canvas.create_line(0,0,0,0, fill="#D32F2F", width=4) for _ in range(4)]
        self.redraw_box()
        
        self.mode = "idle"
        self.start_x = self.start_y = 0
        self.orig_box = []
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Motion>", self.on_hover)
        
        btn_f = tk.Frame(self, bg=BG_COLOR)
        btn_f.pack(fill="x", pady=15)
        tk.Button(btn_f, text="✂️ Apply Crop", font=("Arial", 10, "bold"), bg=ACCENT_BLUE, fg="#ffffff", cursor="hand2", relief="flat", padx=15, command=self.do_crop).pack(side="left", padx=(150, 10))
        tk.Button(btn_f, text="Skip (Use Original)", font=("Arial", 10), bg=CARD_BG, fg=TEXT_PRIMARY, cursor="hand2", relief="solid", bd=1, highlightbackground=BORDER_COLOR, padx=10, command=self.skip).pack(side="left")

        # --- THE FIX: Catch the 'X' window close button to prevent memory leaks ---
        self.protocol("WM_DELETE_WINDOW", self.skip)
        # --------------------------------------------------------------------------

    def redraw_box(self):
        bx1, by1, bx2, by2 = self.box_coords
        self.canvas.coords(self.rect_id, bx1, by1, bx2, by2)
        
        l = 20
        self.canvas.coords(self.markers[0], bx1, by1+l, bx1, by1, bx1+l, by1) 
        self.canvas.coords(self.markers[1], bx2-l, by1, bx2, by1, bx2, by1+l) 
        self.canvas.coords(self.markers[2], bx2, by2-l, bx2, by2, bx2-l, by2) 
        self.canvas.coords(self.markers[3], bx1+l, by2, bx1, by2, bx1, by2-l) 

    def on_hover(self, event):
        x, y = event.x, event.y
        x1, y1, x2, y2 = self.box_coords
        m = 15 
        if abs(x-x1)<m and abs(y-y1)<m: self.canvas.config(cursor="sizing")
        elif abs(x-x2)<m and abs(y-y1)<m: self.canvas.config(cursor="sizing")
        elif abs(x-x1)<m and abs(y-y2)<m: self.canvas.config(cursor="sizing")
        elif abs(x-x2)<m and abs(y-y2)<m: self.canvas.config(cursor="sizing")
        elif abs(y-y1)<m and x1 < x < x2: self.canvas.config(cursor="sb_v_double_arrow")
        elif abs(y-y2)<m and x1 < x < x2: self.canvas.config(cursor="sb_v_double_arrow")
        elif abs(x-x1)<m and y1 < y < y2: self.canvas.config(cursor="sb_h_double_arrow")
        elif abs(x-x2)<m and y1 < y < y2: self.canvas.config(cursor="sb_h_double_arrow")
        elif x1 < x < x2 and y1 < y < y2: self.canvas.config(cursor="fleur")
        else: self.canvas.config(cursor="crosshair")

    def on_press(self, event):
        x, y = event.x, event.y
        x1, y1, x2, y2 = self.box_coords
        m = 15
        self.start_x, self.start_y = x, y
        self.orig_box = list(self.box_coords)
        if abs(x-x1)<m and abs(y-y1)<m: self.mode = "tl"
        elif abs(x-x2)<m and abs(y-y1)<m: self.mode = "tr"
        elif abs(x-x1)<m and abs(y-y2)<m: self.mode = "bl"
        elif abs(x-x2)<m and abs(y-y2)<m: self.mode = "br"
        elif abs(y-y1)<m and x1 < x < x2: self.mode = "t"
        elif abs(y-y2)<m and x1 < x < x2: self.mode = "b"
        elif abs(x-x1)<m and y1 < y < y2: self.mode = "l"
        elif abs(x-x2)<m and y1 < y < y2: self.mode = "r"
        elif x1 < x < x2 and y1 < y < y2: self.mode = "move"
        else: self.mode = "draw"

    def on_drag(self, event):
        dx, dy = event.x - self.start_x, event.y - self.start_y
        x1, y1, x2, y2 = self.orig_box
        
        if self.mode == "move": self.box_coords = [x1+dx, y1+dy, x2+dx, y2+dy]
        elif self.mode == "draw": self.box_coords = [self.start_x, self.start_y, event.x, event.y]
        elif self.mode == "tl": self.box_coords = [x1+dx, y1+dy, x2, y2]
        elif self.mode == "tr": self.box_coords = [x1, y1+dy, x2+dx, y2]
        elif self.mode == "bl": self.box_coords = [x1+dx, y1, x2, y2+dy]
        elif self.mode == "br": self.box_coords = [x1, y1, x2+dx, y2+dy]
        elif self.mode == "t": self.box_coords = [x1, y1+dy, x2, y2]
        elif self.mode == "b": self.box_coords = [x1, y1, x2, y2+dy]
        elif self.mode == "l": self.box_coords = [x1+dx, y1, x2, y2]
        elif self.mode == "r": self.box_coords = [x1, y1, x2+dx, y2]

        bx1, by1 = min(self.box_coords[0], self.box_coords[2]), min(self.box_coords[1], self.box_coords[3])
        bx2, by2 = max(self.box_coords[0], self.box_coords[2]), max(self.box_coords[1], self.box_coords[3])
        
        if bx2 - bx1 < 20: bx2 = bx1 + 20
        if by2 - by1 < 20: by2 = by1 + 20
        
        bx1, by1 = max(0, bx1), max(0, by1)
        bx2, by2 = min(self.disp_img.width, bx2), min(self.disp_img.height, by2)
        
        self.box_coords = [bx1, by1, bx2, by2]
        self.redraw_box()

    def do_crop(self):
        x1, y1, x2, y2 = self.box_coords
        if abs(x1 - x2) < 10: return self.skip()
        
        ox1, oy1 = int(min(x1, x2) * self.ratio_x), int(min(y1, y2) * self.ratio_y)
        ox2, oy2 = int(max(x1, x2) * self.ratio_x), int(max(y1, y2) * self.ratio_y)
        
        ox1, oy1 = max(0, ox1), max(0, oy1)
        ox2, oy2 = min(self.orig_img.width, ox2), min(self.orig_img.height, oy2)
        
        cropped = self.orig_img.crop((ox1, oy1, ox2, oy2))
        
        # --- THE FIX: Stop the cropped logo from vanishing into the _internal void! ---
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        
        # We renamed the file slightly so the main.py Sweeper catches it perfectly!
        save_path = os.path.join(base_dir, "cropped_temp_logo.png")
        # ------------------------------------------------------------------------------
        
        cropped.save(save_path, "PNG")
        self.on_crop_done(save_path)
        
        # --- THE FIX: Dump image from RAM before destroying! ---
        try: self.orig_img.close(); self.disp_img.close(); cropped.close()
        except: pass
        # -------------------------------------------------------
        
        self.destroy()

    def skip(self):
        self.on_crop_done(self.image_path)
        
        # --- THE FIX: Dump image from RAM before destroying! ---
        try: self.orig_img.close(); self.disp_img.close()
        except: pass
        # -------------------------------------------------------
        
        self.destroy()