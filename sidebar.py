import tkinter as tk
from tkinter import ttk
import os
import time
import database
import json

class Sidebar(tk.Frame):
    def __init__(self, parent, switch_callback):
        super().__init__(parent, width=250)
        self.pack_propagate(False) 
        
        self.switch_callback = switch_callback
        self.buttons = {}
        self.separators = {}
        self.containers = {}
        self.active_tab = None 
        self.last_click = 0 
        
        self.colors = self.get_theme_colors()
        
        # --- TIER 1: TOP FIXED FRAME (Title) ---
        self.top_f = tk.Frame(self, bg=self.colors["bg"])
        self.top_f.pack(side="top", fill="x", padx=(0, 15))
        self.title_lbl = tk.Label(self.top_f, text="LEDGER.EVENTS", font=("Arial", 15, "bold"))
        self.title_lbl.pack(pady=(30, 25), padx=20, anchor="w")

        # --- THE FIX: Thicker Top Boundary Line ---
        self.top_border = tk.Frame(self, height=2, bg=self.colors["border"])
        self.top_border.pack(side="top", fill="x")

        # --- TIER 3: BOTTOM FIXED FRAME (Active User Profile Dock) ---
        self.bottom_f = tk.Frame(self, bg=self.colors["bg"], height=62)
        self.bottom_f.pack(side="bottom", fill="x")
        self.bottom_f.pack_propagate(False) 

        # --- THE FIX: Thicker Bottom Boundary Line ---
        self.bottom_border = tk.Frame(self, height=2, bg=self.colors["border"])
        self.bottom_border.pack(side="bottom", fill="x") 
        
        # --- TIER 2: MIDDLE SCROLLABLE CANVAS (Navigation) ---
        self.mid_f = tk.Frame(self, bg=self.colors["bg"])
        self.mid_f.pack(side="top", fill="both", expand=True)
        
        # --- THE FIX: Exact color mapping and geometry from stock.py ---
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Side.Vertical.TScrollbar", background=self.colors["sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.map("Side.Vertical.TScrollbar", background=[("active", self.colors["active_bg"])])
        # ---------------------------------------------------------------

        self.canvas = tk.Canvas(self.mid_f, bg=self.colors["bg"], highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self.mid_f, orient="vertical", command=self.canvas.yview, style="Side.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scroll_frame = tk.Frame(self.canvas, bg=self.colors["bg"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        
        # --- THE FIX: Block the mousewheel from pushing the menu into the void! ---
        def _sync_scroll_region(event=None):
            bbox = self.canvas.bbox("all")
            if bbox:
                canvas_h = self.canvas.winfo_height()
                # If buttons are shorter than the screen, set the limit to the screen height.
                final_h = max(bbox[3], canvas_h)
                self.canvas.configure(scrollregion=(0, 0, bbox[2], final_h))

        def _on_canvas_resize(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
            _sync_scroll_region()

        self.scroll_frame.bind("<Configure>", _sync_scroll_region)
        self.canvas.bind("<Configure>", _on_canvas_resize)
        # --------------------------------------------------------------------------
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.nav_items = [
            "Home", "Dashboard", "Parties", "Invoices", "Purchases", "Catalog", 
            "Stock", "Balance Sheet", "Profit & Loss", "GST Report", "Expenses", "Employees", "Labours", "Settings"
        ]

        for item in self.nav_items:
            target_parent = self.scroll_frame
            
            container = tk.Frame(target_parent, bg=self.colors["bg"])
            self.containers[item] = container
            
            btn = tk.Button(container, text=f"   {item}", font=("Arial", 11, "bold"), relief="flat", anchor="w", padx=10, pady=12, cursor="hand2", bd=0, command=lambda name=item: self.on_click(name))
            sep = tk.Frame(container, height=1, bg=self.colors["border"])
            
            btn.pack(fill="x", padx=10, pady=0)
            sep.pack(side="bottom", fill="x", padx=15)
            
            btn.bind("<Enter>", lambda e, b=btn, n=item: self.on_enter(b, n))
            btn.bind("<Leave>", lambda e, b=btn, n=item: self.on_leave(b, n))
            
            self.buttons[item] = btn
            self.separators[item] = sep

        try:
            self.winfo_toplevel().bind("<<CompanyChanged>>", self.handle_company_change, add="+")
        except: pass

        # --- THE FIX: Deleted the rogue mouse-hover reload bug here! ---
        self.apply_theme()
        
        self._bind_mouse_scroll()
        self.bind("<Enter>", self._on_sidebar_enter, add="+")
        self.bind("<Leave>", self._on_sidebar_leave, add="+")

    def _scroll_canvas(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _bind_mouse_scroll(self):
        self.canvas.bind("<MouseWheel>", self._scroll_canvas)
        self.scroll_frame.bind("<MouseWheel>", self._scroll_canvas)
        for widget in self.scroll_frame.winfo_children():
            widget.bind("<MouseWheel>", self._scroll_canvas)
            for child in widget.winfo_children():
                child.bind("<MouseWheel>", self._scroll_canvas)

    def _on_sidebar_enter(self, event):
        self.winfo_toplevel().bind_all("<MouseWheel>", self._scroll_canvas)

    def _on_sidebar_leave(self, event):
        app = self.winfo_toplevel()
        app.unbind_all("<MouseWheel>")
        if hasattr(app, "_on_mousewheel"):
            app.bind_all("<MouseWheel>", app._on_mousewheel)

    def get_theme_colors(self):
        from views.home_parts.ui_components import get_theme
        t = get_theme()
        # --- THE FIX: Added "sec" color so we can use the grey thumb ---
        return {"bg": t["bg"], "card": t["card"], "active_bg": t["accent_blue"], "text": t["text"], "sec": t["sec"], "active_text": "#ffffff", "border": t["border"]}

    def apply_theme(self, forced_colors=None):
        self.colors = forced_colors if forced_colors else self.get_theme_colors()
        self.configure(bg=self.colors["bg"])
        
        for f in [self.top_f, self.bottom_f, self.mid_f, self.scroll_frame, self.canvas]:
            try: f.configure(bg=self.colors["bg"])
            except: pass
            
        self.title_lbl.configure(bg=self.colors["bg"], fg=self.colors["active_text"] if self.colors["bg"] == "#0f172a" else "#0f172a")

        # --- THE FIX: Update boundary lines on theme change ---
        try:
            self.top_border.configure(bg=self.colors["border"])
            self.bottom_border.configure(bg=self.colors["border"])
        except: pass

        for name, container in self.containers.items():
            container.configure(bg=self.colors["bg"])
            
        for name, sep in self.separators.items():
            sep.configure(bg=self.colors["border"])

        # --- THE FIX: Re-apply exact match on Theme Change ---
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Side.Vertical.TScrollbar", background=self.colors["sec"], troughcolor=self.colors["bg"], bordercolor=self.colors["bg"], arrowcolor=self.colors["text"], relief="flat")
        style.map("Side.Vertical.TScrollbar", background=[("active", self.colors["active_bg"])])
        # -----------------------------------------------------

        self.sync_visibility() 

        for name, btn in self.buttons.items():
            if name == self.active_tab:
                btn.configure(bg=self.colors["active_bg"], fg=self.colors["active_text"], activebackground=self.colors["active_bg"], activeforeground=self.colors["active_text"])
            else:
                btn.configure(bg=self.colors["bg"], fg=self.colors["text"], activebackground=self.colors["card"], activeforeground=self.colors["active_text"] if self.colors["bg"]=="#0f172a" else "#0f172a")

    def handle_company_change(self, event=None):
        self.sync_visibility()
        try:
            app = self.winfo_toplevel()
            tab = getattr(app, "pending_sidebar_tab", None)
            if tab:
                self.sync_active_button(tab)
        except: pass

    def refresh_user_badge(self):
        for w in self.bottom_f.winfo_children():
            w.destroy()
        try:
            app = self.winfo_toplevel()
            uid = getattr(app, "current_user_id", 1) or 1
            uname = getattr(app, "current_user", "Admin") or "Admin"
            urole = getattr(app, "current_role", "Admin") or "Admin"
        except Exception:
            uid, uname, urole = 1, "Admin", "Admin"

        u_row = database.get_user_by_id(uid)
        pic_path = ""
        if u_row:
            uname = u_row[1] or uname
            urole = u_row[3] or urole
            pic_path = u_row[4] if len(u_row) > 4 and u_row[4] else ""

        row_f = tk.Frame(self.bottom_f, bg=self.colors["bg"], padx=12, pady=10)
        row_f.pack(fill="both", expand=True)

        # Circular Avatar Canvas (36x36)
        cvs = tk.Canvas(row_f, width=36, height=36, bg=self.colors["bg"], highlightthickness=0)
        cvs.pack(side="left", padx=(0, 10))
        self._badge_avatar_ref = None
        has_img = False
        try:
            from PIL import Image, ImageTk, ImageDraw
            scale = 4
            sz = 34
            resamp = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            if pic_path and os.path.exists(pic_path):
                img = Image.open(pic_path).convert("RGBA").resize((sz, sz), resamp)
                mask = Image.new("L", (sz * scale, sz * scale), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, sz * scale - 1, sz * scale - 1), fill=255)
                mask = mask.resize((sz, sz), resamp)
                out = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
                out.paste(img, (0, 0), mask)
                self._badge_avatar_ref = ImageTk.PhotoImage(out)
                cvs.create_image(18, 18, image=self._badge_avatar_ref, anchor="center")
                has_img = True
            else:
                circ = Image.new("RGBA", (sz * scale, sz * scale), (0, 0, 0, 0))
                ImageDraw.Draw(circ).ellipse((0, 0, sz * scale - 1, sz * scale - 1), fill=self.colors["active_bg"])
                circ = circ.resize((sz, sz), resamp)
                self._badge_avatar_ref = ImageTk.PhotoImage(circ)
                cvs.create_image(18, 18, image=self._badge_avatar_ref, anchor="center")
                cvs.create_text(18, 18, text=uname[0].upper(), font=("Segoe UI", 11, "bold"), fill="#ffffff")
                has_img = True
        except Exception:
            pass
        if not has_img:
            cvs.create_oval(2, 2, 34, 34, fill=self.colors["active_bg"], outline="")
            cvs.create_text(18, 18, text=uname[0].upper(), font=("Segoe UI", 11, "bold"), fill="#ffffff")

        # Quick Lock Button (Ctrl+L) on the right
        btn_lock = tk.Button(
            row_f, text="🔒", font=("Segoe UI", 11),
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["active_bg"], activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=8, pady=2,
            command=lambda: self.winfo_toplevel().lock_screen()
        )
        btn_lock.pack(side="right", padx=(4, 0))

        # Username & ID/Role Labels in the middle (Read-Only)
        info_f = tk.Frame(row_f, bg=self.colors["bg"])
        info_f.pack(side="left", fill="both", expand=True)

        disp_name = uname if len(uname) <= 15 else uname[:14] + "…"
        lbl_u = tk.Label(info_f, text=disp_name, font=("Segoe UI", 10, "bold"), bg=self.colors["bg"], fg=self.colors["text"], anchor="w")
        lbl_u.pack(fill="x", anchor="w")

        lbl_r = tk.Label(info_f, text=f"USR-{int(uid):03d} • {urole}", font=("Segoe UI", 8, "bold"), bg=self.colors["bg"], fg=self.colors["sec"], anchor="w")
        lbl_r.pack(fill="x", anchor="w")

    def sync_visibility(self):
        self.refresh_user_badge()
        try:
            app = self.winfo_toplevel()
            cid = getattr(app, "active_company_id", None)
        except:
            cid = None
            
        if not cid:
            for item in self.nav_items:
                self.containers[item].pack_forget()
            self.update_idletasks()
            return
            
        gst_toggle = 0
        b_type = "Service"
        
        comp = database.get_company(cid)
        if comp:
            gst_toggle = comp[8] if len(comp) > 8 else 0
            if len(comp) > 14 and comp[14]:
                try: b_type = json.loads(comp[14]).get("business_type", "Service")
                except: pass
                
        for item in self.nav_items:
            self.containers[item].pack_forget()
            
        # --- THE FIX: Check Logged-In User's Sidebar Access Permissions ---
        allowed_sidebars = "all"
        try:
            uid = getattr(app, "current_user_id", 1)
            if str(uid) != "1":
                perms = database.get_user_permissions(uid)
                allowed_sidebars = perms.get("sidebars", "all")
        except Exception:
            allowed_sidebars = "all"

        for item in self.nav_items:
            should_show = True
            if item == "GST Report" and gst_toggle == 0: should_show = False
            if item == "Inventory" and b_type == "Sales": should_show = False
            if allowed_sidebars != "all" and item != "Home" and item not in allowed_sidebars:
                should_show = False
            
            if should_show:
                self.containers[item].pack(fill="x", pady=0)

        self.update_idletasks()
        
        # --- THE FIX: Instantly snap to the top when loading a new menu ---
        self.canvas.yview_moveto(0.0)
        # ------------------------------------------------------------------
        
        self._bind_mouse_scroll()

    def on_enter(self, btn, name):
        if self.active_tab != name:
            btn.configure(bg=self.colors["card"], fg=self.colors["active_text"] if self.colors["bg"] == "#0f172a" else "#0f172a") 

    def on_leave(self, btn, name):
        if self.active_tab != name:
            btn.configure(bg=self.colors["bg"], fg=self.colors["text"]) 

    def sync_active_button(self, name):
        self.active_tab = name
        
        for btn_name, btn in self.buttons.items():
            if btn_name == self.active_tab:
                btn.configure(bg=self.colors["active_bg"], fg=self.colors["active_text"], activebackground=self.colors["active_bg"], activeforeground=self.colors["active_text"])
            else:
                btn.configure(bg=self.colors["bg"], fg=self.colors["text"], activebackground=self.colors["card"], activeforeground=self.colors["active_text"] if self.colors["bg"]=="#0f172a" else "#0f172a")
        
        self.update_idletasks()

    def on_click(self, name):
        now = time.time()
        if now - self.last_click < 0.2:
            return
        self.last_click = now
        self.sync_active_button(name)
        self.switch_callback(name)