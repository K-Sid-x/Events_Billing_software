import tkinter as tk
from tkinter import ttk, messagebox
import hashlib
import database
import os

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image, ImageTk, ImageDraw = None, None, None

from views.home_parts.tab_users import open_user_form_popup

SALT = "LedgerEvents_Secure_Salt_2026!"

def hash_password(password):
    return hashlib.sha256((password + SALT).encode('utf-8')).hexdigest()

def build_admin_setup_screen(parent, colors, on_success):
    tk.Label(parent, text="🛡️ Secure Your Software", font=("Arial", 28, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(60, 10))
    tk.Label(parent, text="Create your Master Admin profile and set a recovery question.", font=("Arial", 12), bg=colors["bg"], fg=colors["text"]).pack(pady=(0, 30))

    form_f = tk.Frame(parent, bg=colors["bg"])
    form_f.pack()

    tk.Label(form_f, text="Admin Username:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=0, column=0, sticky="e", pady=10)
    user_var = tk.StringVar(value="Admin")
    tk.Entry(form_f, textvariable=user_var, font=("Arial", 14), width=25, bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat").grid(row=0, column=1, padx=15, pady=10, ipady=5)

    tk.Label(form_f, text="Master Password:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=1, column=0, sticky="e", pady=10)
    pass_var = tk.StringVar()
    tk.Entry(form_f, textvariable=pass_var, font=("Arial", 14), width=25, show="●", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat").grid(row=1, column=1, padx=15, pady=10, ipady=5)

    tk.Label(form_f, text="Security Question:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=2, column=0, sticky="e", pady=10)
    q_var = tk.StringVar()
    q_cb = ttk.Combobox(form_f, textvariable=q_var, values=["What was the name of your first pet?", "What is your mother's maiden name?", "What city were you born in?", "What is the name of your favorite teacher?", "What was your childhood nickname?"], state="readonly", font=("Arial", 12), width=28)
    q_cb.grid(row=2, column=1, padx=15, pady=10, ipady=5)
    q_cb.current(0)

    tk.Label(form_f, text="Your Answer:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=3, column=0, sticky="e", pady=10)
    ans_var = tk.StringVar()
    tk.Entry(form_f, textvariable=ans_var, font=("Arial", 14), width=25, bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat").grid(row=3, column=1, padx=15, pady=10, ipady=5)

    def create_admin():
        u = user_var.get().strip()
        p = pass_var.get().strip()
        q = q_var.get().strip()
        a = ans_var.get().strip()

        if not u or not p or not q or not a:
            messagebox.showerror("Required", "All fields are required.", parent=parent)
            return
        
        new_id = database.add_user(u, hash_password(p), "Admin", "")
        
        # Save Q&A securely in global settings
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("REPLACE INTO ui_settings (setting_key, setting_value, company_id) VALUES (?, ?, ?)", ('admin_sec_q', q, 0))
        c.execute("REPLACE INTO ui_settings (setting_key, setting_value, company_id) VALUES (?, ?, ?)", ('admin_sec_a', hash_password(a.lower().strip()), 0))
        conn.commit()
        conn.close()

        parent.winfo_toplevel().current_user_id = new_id
        database.set_active_user(new_id)
        messagebox.showinfo("Success", "Master Admin profile and Security Question created!", parent=parent)
        on_success(u, "Admin")

    tk.Button(parent, text="Create Admin & Secure Data", font=("Arial", 12, "bold"), bg="#10b981", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=10, command=create_admin).pack(pady=30)

def build_login_screen(parent, colors, on_success):
    for widget in parent.winfo_children():
        widget.destroy()

    tk.Label(parent, text="Who's using Ledger Events?", font=("Arial", 28, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(120, 50))

    profiles_frame = tk.Frame(parent, bg=colors["bg"])
    profiles_frame.pack()

    users = database.get_all_users()
    avatar_colors = ["#3b82f6", "#8b5cf6", "#ec4899", "#10b981", "#f59e0b", "#ef4444"]

    def show_password_screen(user_id, username, role):
        for widget in parent.winfo_children():
            widget.destroy()

        tk.Label(parent, text=f"Welcome back, {username}", font=("Arial", 24, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(120, 5))
        tk.Label(parent, text=f"Unique ID: USR-{int(user_id):03d}  •  {role}", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors.get("sec", "#94a3b8")).pack(pady=(0, 25))
        tk.Label(parent, text="Please enter your PIN / Password", font=("Arial", 12), bg=colors["bg"], fg=colors["text"]).pack(pady=(0, 20))

        pass_var = tk.StringVar()
        pass_entry = tk.Entry(parent, textvariable=pass_var, font=("Arial", 18), width=15, show="●", justify="center", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
        pass_entry.pack(pady=10, ipady=8)
        pass_entry.focus()

        err_lbl = tk.Label(parent, text="", font=("Arial", 11, "bold"), bg=colors["bg"], fg="#ef4444")
        err_lbl.pack(pady=5)

        def attempt_login(event=None):
            p = pass_var.get().strip()
            user_data = database.get_user_by_id(user_id)
            if user_data and hash_password(p) == user_data[2]:
                err_lbl.config(text="")
                parent.winfo_toplevel().current_user_id = user_id
                database.set_active_user(user_id)
                on_success(username, role)
            else:
                err_lbl.config(text="Incorrect Password.")
                pass_var.set("")

        pass_entry.bind("<Return>", attempt_login)
        tk.Button(parent, text="Unlock", font=("Arial", 12, "bold"), bg="#3b82f6", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=8, command=attempt_login).pack(pady=10)

        # --- THE FIX: Q&A Password Recovery System ---
        def show_new_password_screen():
            for widget in parent.winfo_children(): widget.destroy()
            tk.Label(parent, text="Reset Admin Password", font=("Arial", 24, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(120, 5))
            tk.Label(parent, text="Enter your new master password below.", font=("Arial", 12), bg=colors["bg"], fg=colors.get("sec", "#94a3b8")).pack(pady=(0, 25))

            new_pass_var = tk.StringVar()
            new_pass_entry = tk.Entry(parent, textvariable=new_pass_var, font=("Arial", 18), width=15, show="●", justify="center", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
            new_pass_entry.pack(pady=10, ipady=8)
            new_pass_entry.focus()

            def save_new_password(event=None):
                p = new_pass_var.get().strip()
                if not p: return
                u_row = database.get_user_by_id(user_id)
                u_pic = u_row[4] if u_row and len(u_row) > 4 else ""
                u_perms = u_row[5] if u_row and len(u_row) > 5 else "{}"
                database.update_user_details(user_id, username, role, u_pic, hash_password(p), u_perms)
                messagebox.showinfo("Success", "Password reset successfully!", parent=parent)
                show_password_screen(user_id, username, role)

            new_pass_entry.bind("<Return>", save_new_password)
            tk.Button(parent, text="Save Password", font=("Arial", 12, "bold"), bg="#3b82f6", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=8, command=save_new_password).pack(pady=10)

        def show_recovery_screen():
            for widget in parent.winfo_children(): widget.destroy()
            tk.Label(parent, text="Password Recovery", font=("Arial", 24, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(120, 5))

            if role != "Admin":
                tk.Label(parent, text=f"Account '{username}' is a {role} profile.", font=("Arial", 12, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(0, 10))
                tk.Label(parent, text="Please contact your Master Admin. They can reset your password\nfrom the 'Settings > Users' tab.", font=("Arial", 12), bg=colors["bg"], fg=colors.get("sec", "#94a3b8"), justify="center").pack(pady=(0, 20))
                tk.Button(parent, text="← Back to Login", font=("Arial", 10), bg=colors["bg"], fg=colors["text"], cursor="hand2", relief="flat", command=lambda: show_password_screen(user_id, username, role)).pack(pady=20)
                return

            # Check Database for a Security Question
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key='admin_sec_q'")
            q_row = c.fetchone()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key='admin_sec_a'")
            a_row = c.fetchone()
            conn.close()

            if q_row and a_row:
                # Security Question Mode
                sec_q = q_row[0]
                tk.Label(parent, text="Security Question:", font=("Arial", 10, "bold"), bg=colors["bg"], fg=colors.get("sec", "#94a3b8")).pack(pady=(0, 5))
                tk.Label(parent, text=sec_q, font=("Arial", 14, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(0, 25))

                ans_var = tk.StringVar()
                ans_entry = tk.Entry(parent, textvariable=ans_var, font=("Arial", 16), width=20, justify="center", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
                ans_entry.pack(pady=10, ipady=6)
                ans_entry.focus()

                err_lbl_reset = tk.Label(parent, text="", font=("Arial", 11, "bold"), bg=colors["bg"], fg="#ef4444")
                err_lbl_reset.pack(pady=5)

                def verify_answer(event=None):
                    ans = ans_var.get().lower().strip()
                    if hash_password(ans) == a_row[0]:
                        show_new_password_screen()
                    else:
                        err_lbl_reset.config(text="Incorrect answer. Please try again.")
                        ans_var.set("")

                ans_entry.bind("<Return>", verify_answer)
                tk.Button(parent, text="Verify Answer", font=("Arial", 12, "bold"), bg="#10b981", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=8, command=verify_answer).pack(pady=10)
                tk.Button(parent, text="← Cancel", font=("Arial", 10), bg=colors["bg"], fg=colors["text"], cursor="hand2", relief="flat", command=lambda: show_password_screen(user_id, username, role)).pack(pady=20)
            
            else:
                # Fallback: Legacy Admin without a Security Question uses Company PIN
                tk.Label(parent, text="No Security Question was found for your profile.", font=("Arial", 12, "bold"), bg=colors["bg"], fg="#ef4444").pack(pady=(0, 10))
                tk.Label(parent, text="Enter the Master Company Security PIN to verify your identity.", font=("Arial", 12), bg=colors["bg"], fg=colors.get("sec", "#94a3b8")).pack(pady=(0, 25))

                pin_var = tk.StringVar()
                pin_entry = tk.Entry(parent, textvariable=pin_var, font=("Arial", 18), width=15, show="●", justify="center", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
                pin_entry.pack(pady=10, ipady=8)
                pin_entry.focus()

                err_lbl_pin = tk.Label(parent, text="", font=("Arial", 11, "bold"), bg=colors["bg"], fg="#ef4444")
                err_lbl_pin.pack(pady=5)

                def verify_pin(event=None):
                    comp_data = database.get_company(1)
                    actual_pin = str(comp_data[15]).strip() if comp_data and len(comp_data) > 15 and comp_data[15] else ""
                    if not actual_pin:
                        err_lbl_pin.config(text="No Security PIN is configured for the company.\nPlease contact the developer.")
                        return
                    if pin_var.get().strip() == actual_pin:
                        show_new_password_screen()
                    else:
                        err_lbl_pin.config(text="Incorrect Security PIN.")
                        pin_var.set("")

                pin_entry.bind("<Return>", verify_pin)
                tk.Button(parent, text="Verify PIN", font=("Arial", 12, "bold"), bg="#10b981", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=8, command=verify_pin).pack(pady=10)
                tk.Button(parent, text="← Cancel", font=("Arial", 10), bg=colors["bg"], fg=colors["text"], cursor="hand2", relief="flat", command=lambda: show_password_screen(user_id, username, role)).pack(pady=20)

        btn_forgot = tk.Button(parent, text="Forgot Password?", font=("Arial", 10, "underline"), bg=colors["bg"], fg=colors.get("sec", "#94a3b8"), cursor="hand2", relief="flat", activebackground=colors["bg"], activeforeground=colors["text"], bd=0, command=show_recovery_screen)
        btn_forgot.pack(pady=(5, 5))

        tk.Button(parent, text="← Back to Profiles", font=("Arial", 10), bg=colors["bg"], fg=colors["text"], cursor="hand2", relief="flat", command=lambda: build_login_screen(parent, colors, on_success)).pack(pady=20)

    def prompt_admin_auth():
        for widget in parent.winfo_children():
            widget.destroy()
        
        admin_users = [u for u in database.get_all_users() if u[2] == "Admin"]
        admin_map = {f"{u[1]} (USR-{int(u[0]):03d})": u[0] for u in admin_users}
        
        tk.Label(parent, text="🛡️ Admin Authorization", font=("Arial", 24, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=(120, 10))
        tk.Label(parent, text="Enter an Admin password to authorize creating a new profile.", font=("Arial", 12), bg=colors["bg"], fg=colors.get("sec", "#94a3b8")).pack(pady=(0, 30))
        
        f = tk.Frame(parent, bg=colors["bg"])
        f.pack()
        
        tk.Label(f, text="Admin User:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=0, column=0, sticky="e", pady=10, padx=10)
        admin_var = tk.StringVar()
        admin_cb = ttk.Combobox(f, textvariable=admin_var, values=list(admin_map.keys()), state="readonly", font=("Arial", 12), width=22)
        admin_cb.grid(row=0, column=1, pady=10, padx=10, ipady=4)
        if admin_map:
            admin_cb.current(0)
        
        tk.Label(f, text="Password:", font=("Arial", 11, "bold"), bg=colors["bg"], fg=colors["text"]).grid(row=1, column=0, sticky="e", pady=10, padx=10)
        pass_var = tk.StringVar()
        pass_entry = tk.Entry(f, textvariable=pass_var, font=("Arial", 14), width=23, show="●", bg=colors["border"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
        pass_entry.grid(row=1, column=1, pady=10, padx=10, ipady=5)
        pass_entry.focus()
        
        err_lbl = tk.Label(parent, text="", font=("Arial", 11, "bold"), bg=colors["bg"], fg="#ef4444")
        err_lbl.pack(pady=5)
        
        def verify_admin(e=None):
             target_admin_id = admin_map.get(admin_var.get())
             p = pass_var.get().strip()
             user_data = database.get_user_by_id(target_admin_id)
             if user_data and hash_password(p) == user_data[2]:
                 build_login_screen(parent, colors, on_success)
                 open_user_form_popup(parent, colors, lambda: build_login_screen(parent, colors, on_success))
             else:
                 err_lbl.config(text="Incorrect Admin Password.")
                 pass_var.set("")
                
        pass_entry.bind("<Return>", verify_admin)
        tk.Button(parent, text="Authorize", font=("Arial", 12, "bold"), bg="#3b82f6", fg="#ffffff", cursor="hand2", relief="flat", padx=30, pady=8, command=verify_admin).pack(pady=10)
        tk.Button(parent, text="← Cancel", font=("Arial", 10), bg=colors["bg"], fg=colors["text"], cursor="hand2", relief="flat", command=lambda: build_login_screen(parent, colors, on_success)).pack(pady=20)

    def draw_avatar(parent_f, user_id, name, role, color, pic_path="", is_add_btn=False):
        f = tk.Frame(parent_f, bg=colors["bg"], cursor="hand2")
        f.pack(side="left", padx=20)

        if not is_add_btn and role:
            lbl_role = tk.Label(f, text=role, font=("Arial", 12, "bold"), bg=colors["bg"], fg=colors.get("sec", "#94a3b8"), cursor="hand2")
            lbl_role.pack(pady=(0, 8))
        else:
            lbl_role = tk.Label(f, text="", font=("Arial", 12, "bold"), bg=colors["bg"])
            lbl_role.pack(pady=(0, 8))

        c = tk.Canvas(f, width=120, height=120, bg=colors["bg"], highlightthickness=0)
        c.pack()
        
        has_img = False
        if pic_path and os.path.exists(pic_path) and Image:
            try:
                img = Image.open(pic_path).convert("RGBA")
                resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                img = img.resize((100, 100), resamp)
                
                mask = Image.new("L", (100, 100), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, 100, 100), fill=255)
                
                output = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
                output.paste(img, (0, 0), mask)
                
                tk_img = ImageTk.PhotoImage(output)
                if not hasattr(parent_f, 'img_cache'): parent_f.img_cache = []
                parent_f.img_cache.append(tk_img)
                c.create_image(60, 60, image=tk_img, anchor="center")
                has_img = True
            except Exception:
                pass
            
        if not has_img and Image:
            try:
                scale = 4
                smooth_circ = Image.new("RGBA", (100 * scale, 100 * scale), (0, 0, 0, 0))
                draw = ImageDraw.Draw(smooth_circ)
                draw.ellipse((0, 0, 100 * scale, 100 * scale), fill=color)
                
                resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                smooth_circ = smooth_circ.resize((100, 100), resamp)
                
                tk_circ = ImageTk.PhotoImage(smooth_circ)
                if not hasattr(parent_f, 'img_cache'): parent_f.img_cache = []
                parent_f.img_cache.append(tk_circ)
                c.create_image(60, 60, image=tk_circ, anchor="center")
            except Exception:
                c.create_oval(10, 10, 110, 110, fill=color, outline="")
        elif not has_img:
            c.create_oval(10, 10, 110, 110, fill=color, outline="")

        if is_add_btn:
            c.create_text(60, 60, text="+", font=("Arial", 48, "normal"), fill="#ffffff")
            lbl_name = "Add Profile"
        elif not has_img:
            initial = name[0].upper()
            c.create_text(60, 60, text=initial, font=("Arial", 36, "bold"), fill="#ffffff")
            lbl_name = name
        else:
            lbl_name = name

        lbl = tk.Label(f, text=lbl_name, font=("Arial", 14, "bold"), bg=colors["bg"], fg=colors["text"], cursor="hand2")
        lbl.pack(pady=(10, 0))

        def on_click(e):
            if is_add_btn:
                prompt_admin_auth()
            else:
                show_password_screen(user_id, name, role)

        f.bind("<Button-1>", on_click)
        c.bind("<Button-1>", on_click)
        lbl.bind("<Button-1>", on_click)
        if not is_add_btn and role:
            lbl_role.bind("<Button-1>", on_click)
        for item in c.find_all():
            c.tag_bind(item, "<Button-1>", on_click)

    for idx, u in enumerate(users):
        u_id, u_name, u_role = u[0], u[1], u[2]
        u_pic = u[3] if len(u) > 3 else ""
        c_idx = idx % len(avatar_colors)
        draw_avatar(profiles_frame, u_id, u_name, u_role, avatar_colors[c_idx], pic_path=u_pic)

    draw_avatar(profiles_frame, None, "Add", "", "#3f3f46", is_add_btn=True)