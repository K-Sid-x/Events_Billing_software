import tkinter as tk
import database
from views.home_parts.ui_components import get_theme

def prompt_company_pin(home_view, cid, correct_pin, action="login", target_tab="Dashboard"):
    """Validates the PIN and then routes to the requested action or tab."""
    t = get_theme()  # Dynamically fetch the current theme colors

    pop = tk.Toplevel(home_view)
    pop.title("Company Locked")
    pop.geometry("350x450")
    pop.configure(bg=t["card"])
    pop.grab_set()

    tk.Label(pop, text="🔒", font=("Arial", 40), bg=t["card"], fg=t["sec"]).pack(pady=(40, 10))
    tk.Label(pop, text="Company Locked", font=("Arial", 16, "bold"), bg=t["card"], fg=t["text"]).pack()
    tk.Label(pop, text="Enter PIN to access", font=("Arial", 10), bg=t["card"], fg=t["sec"]).pack(pady=(0, 20))

    pin_var = tk.StringVar()
    entry = tk.Entry(pop, textvariable=pin_var, font=("Arial", 24, "bold"), width=6, justify="center", bg=t["bg"], fg=t["text"], show="●", insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    entry.pack(pady=10)
    
    # Force focus after a tiny delay so it overrides the destruction of the alert window
    def grab_focus():
        pop.focus_force()
        entry.focus_set()
    pop.after(50, grab_focus)
    
    lbl_error = tk.Label(pop, text="", font=("Arial", 10), bg=t["card"], fg=t["error"])
    lbl_error.pack()

    def verify(*args):
        if pin_var.get() == correct_pin:
            pop.destroy()
            if action == "login":
                home_view.app.active_company_id = cid
                database.set_active_company(cid) 
                
                # --- THE FIX: Send the Global Radio Broadcast on PIN Login ---
                home_view.app.pending_sidebar_tab = target_tab
                home_view.app.event_generate("<<CompanyChanged>>")
                
                home_view.load_companies()
                home_view.app.update_idletasks()
                home_view.app.after(15, lambda: home_view.app.switch_view(target_tab))
                # -------------------------------------------------------------
            elif action == "edit":
                from views.home_parts.company_forms import open_edit_popup
                home_view.app.active_company_id = cid
                open_edit_popup(home_view, cid)
            elif action == "delete":
                home_view._execute_delete(cid)
        else:
            pin_var.set("")
            lbl_error.config(text="Incorrect PIN. Access Denied.")
            
    entry.bind("<Return>", verify)
    tk.Button(pop, text="Unlock", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=verify).pack(pady=20)