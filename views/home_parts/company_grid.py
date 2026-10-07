import tkinter as tk
from tkinter import messagebox
import os
import time
import database

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image, ImageTk, ImageDraw = None, None, None

from views.home_parts.security import prompt_company_pin
from views.home_parts.company_forms import open_edit_popup

class CompanyGridManager:
    def __init__(self, home_view):
        self.home = home_view
        self.app = home_view.app
        self.company_cards_ref = []
        self.selected_grid_idx = -1
        self.saved_idx = -1
        self.tile_images = []
        self.last_click_time = 0 

    def load_companies(self):
        for widget in self.home.grid_frame.winfo_children(): widget.destroy()
        self.tile_images.clear() 
        self.company_cards_ref.clear()
        
        for c in range(3):
            self.home.grid_frame.grid_columnconfigure(c, weight=1, uniform="equal_cols")
        
        sort_map = {"Alphabetical (A-Z)": "name ASC", "Recently Added": "id DESC"}
        db_sort = sort_map.get(self.home.sort_var.get(), "name ASC")
        
        companies = database.get_all_companies(sort_by=db_sort)
        if not companies:
            tk.Label(self.home.grid_frame, text="No companies found. Press Ctrl+N to create one!", font=("Segoe UI", 12), bg=self.home.colors["bg"], fg=self.home.colors["text_sec"]).pack(pady=50)
            return

        row, col = 0, 0
        for i, comp in enumerate(companies):
            comp_id = comp[0]; name = comp[1]; gst_toggle = comp[8]; gstin = comp[9]
            logo_path = comp[10] if len(comp) > 10 else ""
            comp_pin = comp[15] if len(comp) > 15 else ""
            logo_shape = comp[13] if len(comp) > 13 and comp[13] else "Square"
            
            is_active = hasattr(self.app, "active_company_id") and str(self.app.active_company_id) == str(comp_id)
            card_bg = self.home.colors["bg"] if is_active else self.home.colors["card"]
            border_color = "#10b981" if is_active else self.home.colors["border"]
            
            card = tk.Frame(self.home.grid_frame, bg=card_bg, highlightbackground=border_color, highlightthickness=2, padx=20, pady=20, cursor="hand2", height=170)
            card.pack_propagate(False)
            card.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
            
            card_top = tk.Frame(card, bg=card_bg, highlightthickness=0)
            card_top.pack(fill="x", anchor="n")
            
            hover_elements = [card_top]

            if logo_path and Image and os.path.exists(logo_path):
                try:
                    img = Image.open(logo_path).convert("RGBA")
                    try: resamp = Image.Resampling.LANCZOS
                    except: resamp = Image.LANCZOS
                    img.thumbnail((45, 45), resamp)
                    
                    if logo_shape == "Circle" and ImageDraw:
                        scale = 4
                        mask = Image.new("L", (img.size[0] * scale, img.size[1] * scale), 0)
                        draw = ImageDraw.Draw(mask)
                        draw.ellipse((0, 0, img.size[0] * scale, img.size[1] * scale), fill=255)
                        mask = mask.resize(img.size, resamp)
                        
                        circular_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
                        circular_img.paste(img, (0, 0), mask=mask)
                        img = circular_img
                        
                    photo = ImageTk.PhotoImage(img)
                    self.tile_images.append(photo)
                    lbl_logo = tk.Label(card_top, image=photo, bg=card_bg)
                    lbl_logo.pack(side="left", padx=(0, 15))
                    hover_elements.append(lbl_logo)
                except Exception: pass
            
            if comp_pin:
                lbl_lock = tk.Label(card_top, text="🔒", font=("Segoe UI", 12), bg=card_bg, fg=self.home.colors["text_sec"])
                lbl_lock.pack(side="left", padx=(0, 5))
                hover_elements.append(lbl_lock)

            lbl_name = tk.Label(card_top, text=name, font=("Segoe UI", 14, "bold"), bg=card_bg, fg=self.home.colors["text"])
            lbl_name.pack(side="left", fill="y", expand=True, anchor="w")
            hover_elements.append(lbl_name)
            
            opts_btn = None
            if getattr(self.app, "current_role", "") == "Admin":
                opts_btn = tk.Label(card_top, text="⋮", font=("Segoe UI", 16, "bold"), bg=card_bg, fg=self.home.colors["text_sec"], cursor="hand2", width=2, height=1)
                opts_btn.pack(side="right", anchor="ne")
                
                def on_opts_enter(e, btn=opts_btn):
                    btn.config(bg="#3b82f6", fg="#ffffff")
                    
                def on_opts_leave(e, btn=opts_btn, idx=i):
                    is_sel = (self.selected_grid_idx == idx)
                    target_bg = self.home.colors["card_hover"] if is_sel else card_bg
                    btn.config(bg=target_bg, fg=self.home.colors["text_sec"])

                opts_btn.bind("<Enter>", on_opts_enter)
                opts_btn.bind("<Leave>", on_opts_leave)
                
                def show_menu(e, cid=comp_id, pin=comp_pin):
                    menu = tk.Menu(self.home, tearoff=0, font=("Segoe UI", 10), bg=self.home.colors["card"], fg=self.home.colors["text"], activebackground="#3b82f6", activeforeground="#ffffff")
                    menu.add_command(label="✏️ Edit Basic Info", command=lambda c=cid, p=pin: self.home.edit_company(c, p))
                    menu.add_command(label="❌ Delete Company", command=lambda c=cid, p=pin: self.home.delete_company(c, p), foreground="#ef4444")
                    menu.tk_popup(e.x_root, e.y_root)
                    return "break" 
                
                opts_btn.bind("<Button-1>", show_menu)

            badge_f = tk.Frame(card, bg=card_bg, highlightthickness=0)
            badge_f.pack(anchor="w", pady=(15, 0))
            hover_elements.append(badge_f)
            
            if gst_toggle == 1:
                tk.Label(badge_f, text=f" ✓ GST: {gstin} ", font=("Segoe UI", 9, "bold"), bg="#064e3b", fg="#10b981").pack(side="left")
            else:
                tk.Label(badge_f, text=" Unregistered ", font=("Segoe UI", 9, "bold"), bg=self.home.colors["border"], fg=self.home.colors["text_sec"]).pack(side="left")

            if is_active: 
                lbl_active = tk.Label(card, text="✓ ACTIVE", font=("Segoe UI", 10, "bold"), bg=card_bg, fg="#10b981")
                lbl_active.pack(anchor="w", pady=(10, 0))
                hover_elements.append(lbl_active)
            
            def make_click_fn(c_id, c_pin):
                def _click(e):
                    self.execute_card_click(c_id, c_pin)
                    return "break" 
                return _click

            safe_click = make_click_fn(comp_id, comp_pin)
            card.bind("<Button-1>", safe_click)
            for el in hover_elements:
                if el != opts_btn: el.bind("<Button-1>", safe_click)

            self.company_cards_ref.append({
                'card': card, 'elements': hover_elements, 'bg': card_bg, 
                'hover_bg': self.home.colors["card_hover"], 'cid': comp_id, 'pin': comp_pin, 'opts_btn': opts_btn
            })

            def make_enter(idx):
                def _on_enter(e):
                    if self.home.nav_zone == "grid":
                        self.selected_grid_idx = idx
                        self.update_grid_selection()
                return _on_enter
                
            def make_leave(idx):
                def _on_leave(e):
                    x, y = e.x_root, e.y_root
                    cx, cy = card.winfo_rootx(), card.winfo_rooty()
                    cw, ch = card.winfo_width(), card.winfo_height()
                    if not (cx <= x <= cx + cw and cy <= y <= cy + ch):
                        if self.selected_grid_idx == idx and self.home.nav_zone == "grid":
                            self.selected_grid_idx = -1
                            self.update_grid_selection()
                return _on_leave

            enter_fn = make_enter(i)
            leave_fn = make_leave(i)
            card.bind("<Enter>", enter_fn); card.bind("<Leave>", leave_fn)
            for el in hover_elements: el.bind("<Enter>", enter_fn); el.bind("<Leave>", leave_fn)

            col += 1
            if col > 2: col = 0; row += 1

    def move_grid_focus(self, dx, dy):
        if not self.company_cards_ref: return "break"
        cols = 3
        if self.selected_grid_idx == -1: self.selected_grid_idx = 0
        else:
            if dx != 0: self.selected_grid_idx += dx
            if dy != 0: self.selected_grid_idx += (dy * cols)
        
        if self.selected_grid_idx < 0: self.selected_grid_idx = 0
        if self.selected_grid_idx >= len(self.company_cards_ref):
            self.selected_grid_idx = len(self.company_cards_ref) - 1
            
        self.update_grid_selection()
        return "break"
        
    def enter_grid_focus(self, e=None):
        if not self.company_cards_ref: return
        if 0 <= self.selected_grid_idx < len(self.company_cards_ref):
            c = self.company_cards_ref[self.selected_grid_idx]
            self.execute_card_click(c['cid'], c['pin'])

    def update_grid_selection(self):
        for i, c in enumerate(self.company_cards_ref):
            is_sel = (i == self.selected_grid_idx)
            bg = c['hover_bg'] if is_sel else c['bg']
            c['card'].config(bg=bg)
            for el in c['elements']:
                try: el.config(bg=bg)
                except: pass
                
            try:
                ob = c.get('opts_btn')
                if ob and ob.cget('bg') != "#3b82f6":
                    ob.config(bg=bg)
            except: pass

    def clear_selection(self):
        self.saved_idx = self.selected_grid_idx
        self.selected_grid_idx = -1
        self.update_grid_selection()

    def restore_selection(self):
        if self.saved_idx != -1:
            self.selected_grid_idx = self.saved_idx
        else:
            self.selected_grid_idx = 0
        self.update_grid_selection()

    def execute_card_click(self, cid, pin, target_tab="Dashboard"):
        if time.time() - self.last_click_time < 0.5: 
            return "break"
        self.last_click_time = time.time()

        # Enforce Company & Sidebar permissions on every entry point (Cards, Bell Alerts, Shortcuts)
        uid = getattr(self.app, "current_user_id", 1)
        if str(uid) != "1":
            perms = database.get_user_permissions(uid)
            allowed_comps = perms.get("companies", "all")
            if isinstance(allowed_comps, list) and int(cid) not in {int(x) for x in allowed_comps}:
                messagebox.showerror("Access Denied", "You do not have permission to access this company.", parent=self.home)
                return "break"
            
            # Use per-company overrides if available
            comp_sidebars = perms.get("company_sidebars", {})
            if str(cid) in comp_sidebars:
                allowed_tabs = comp_sidebars[str(cid)]
            else:
                allowed_tabs = perms.get("sidebars", "all")
                
            if isinstance(allowed_tabs, list) and target_tab not in allowed_tabs:
                fallback = None
                for c in ["Dashboard", "Parties", "Invoices", "Purchases", "Catalog", "Stock", "Expenses", "Employees", "Labours", "Settings"]:
                    if c in allowed_tabs:
                        fallback = c
                        break
                target_tab = fallback if fallback else "Home"

        if pin and str(self.app.active_company_id) != str(cid):
            prompt_company_pin(self.home, cid, pin, action="login", target_tab=target_tab)
        else:
            self.app.active_company_id = cid
            database.set_active_company(cid) 
            
            # --- THE FIX: The Global Radio Broadcast ---
            # Instantly tells the entire software that a new company is active!
            self.app.pending_sidebar_tab = target_tab
            self.app.event_generate("<<CompanyChanged>>")
            
            self.home.update_idletasks()
            self.app.after(15, lambda: self.app.switch_view(self.app.pending_sidebar_tab))

    def edit_company(self, comp_id, comp_pin):
        if getattr(self.app, "current_role", "") != "Admin":
            messagebox.showerror("Access Denied", "Only the Master Admin can edit company details.", parent=self.home)
            return
        if comp_pin: prompt_company_pin(self.home, comp_id, comp_pin, action="edit")
        else: self.app.active_company_id = comp_id; open_edit_popup(self.home, comp_id)

    def delete_company(self, comp_id, comp_pin):
        if getattr(self.app, "current_role", "") != "Admin":
            messagebox.showerror("Access Denied", "Only the Master Admin can delete a company.", parent=self.home)
            return
        if comp_pin: prompt_company_pin(self.home, comp_id, comp_pin, action="delete")
        else: self._execute_delete(comp_id)

    def _execute_delete(self, comp_id):
        if getattr(self.app, "current_role", "") != "Admin":
            messagebox.showerror("Access Denied", "Only the Master Admin can delete a company.", parent=self.home)
            return
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this company profile?", parent=self.home):
            # --- THE FIX: Clean up the physical logo file from the hard drive before wiping the database record ---
            try:
                comp = database.get_company(comp_id)
                if comp and len(comp) > 10 and comp[10]:
                    logo_file = comp[10]
                    # --- THE FIX: Strict directory validation to prevent shared logo deletion ---
                    if logo_file and os.path.exists(logo_file):
                        if os.path.basename(os.path.dirname(logo_file)) == "company_logos":
                            os.remove(logo_file)
            except Exception:
                pass
            # ---------------------------------------------------------------------------------------------------

            database.delete_company(comp_id)
            if hasattr(self.app, "active_company_id") and str(self.app.active_company_id) == str(comp_id): 
                self.app.active_company_id = None
            self.load_companies()