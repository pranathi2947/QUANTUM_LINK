import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
from PIL import Image, ImageTk
import qrcode
import qrcode.constants
import cv2
import json
import os
import threading
import webbrowser
from pyzxing import BarCodeReader
from datetime import datetime
import csv
from typing import Optional, Dict, Any

# --- Constants ---
DATA_FILE = "products_database.json"
QRS_FOLDER = "QRCodes"
CONFIG_FILE = "app_config.json"

class SplashScreen(ttk.Toplevel):
    """A professional splash screen that shows on app startup."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Splash")
        self.geometry("400x250")
        self.overrideredirect(True)
        parent.eval(f'tk::PlaceWindow {str(self)} center')

        splash_frame = ttk.Frame(self, bootstyle=PRIMARY, padding=2)
        splash_frame.pack(expand=True, fill=BOTH)
        inner_frame = ttk.Frame(splash_frame, bootstyle=DARK)
        inner_frame.pack(expand=True, fill=BOTH, padx=2, pady=2)

        ttk.Label(inner_frame, text="QuantumLink", font=("Segoe UI Black", 32)).pack(pady=(40, 10))
        ttk.Label(inner_frame, text="Connecting Digital and Physical Worlds", font=("Segoe UI", 11)).pack()
        self.progress = ttk.Progressbar(inner_frame, mode='indeterminate', bootstyle=SUCCESS)
        self.progress.pack(pady=20, padx=40, fill=X)
        self.progress.start()

class QuantumLinkApp:
    """
    QuantumLink: An advanced QR and barcode utility for generation,
    styling, batch processing, and intelligent scanning.
    """
    def __init__(self, root: ttk.Window):
        self.root = root
        self.root.withdraw()
        SplashScreen(self.root)
        self.root.after(2500, self.initialize_main_app)

    def initialize_main_app(self):
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Toplevel): widget.destroy()
        self.root.deiconify()
        self.root.title("QuantumLink")
        self.config = self.load_app_config()
        self.root.geometry(self.config.get("geometry", "1200x850"))
        
        # --- State Variables ---
        self.products: Dict[str, Dict[str, Any]] = self.load_products()
        self.scan_history = []
        self.last_generated_qr_img: Optional[Image.Image] = None
        self.logo_path: Optional[str] = None
        self.qr_fill_color_hex = "#000000"
        self.qr_bg_color_hex = "#FFFFFF"
        
        # --- Webcam and Scanning Control ---
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_scanning_webcam = False
        self.webcam_thread: Optional[threading.Thread] = None
        self.barcode_reader = BarCodeReader()
        self.webcam_available = self.check_webcam()

        # --- UI Setup ---
        self.create_menu()
        self.create_widgets()
        self.populate_database_view()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_status("Welcome to QuantumLink!")

    def check_webcam(self) -> bool:
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if cap.isOpened():
                cap.release()
                return True
        except Exception: pass
        return False
        
    # --- Configuration and Data Handling ---
    def load_app_config(self) -> Dict[str, Any]:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return json.load(f)
            except (json.JSONDecodeError, IOError): return {}
        return {"theme": "cyborg"}

    def save_app_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                self.config["geometry"] = self.root.winfo_geometry()
                self.config["theme"] = self.root.style.theme_use()
                json.dump(self.config, f, indent=4)
        except IOError: print("Warning: Could not save app configuration.")

    def load_products(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f: return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                messagebox.showerror("Database Error", f"Could not read '{DATA_FILE}'.\nError: {e}")
                return {}
        return {}

    def save_products(self):
        try:
            with open(DATA_FILE, "w") as f: json.dump(self.products, f, indent=4)
        except IOError as e: messagebox.showerror("Database Error", f"Could not save data to '{DATA_FILE}'.\nError: {e}")

    # --- Main UI Creation ---
    def create_menu(self):
        menu_bar = ttk.Menu(self.root)
        self.root.config(menu=menu_bar)
        file_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Database to CSV", command=self.export_to_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        settings_menu = ttk.Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        self.theme_var = tk.StringVar(value=self.root.style.theme_use())
        for theme in sorted(self.root.style.theme_names()):
             settings_menu.add_radiobutton(label=theme, variable=self.theme_var, command=self.change_theme)

    def create_widgets(self):
        main_title = ttk.Label(self.root, text="◇ QuantumLink ◇", font=("Segoe UI Black", 28))
        main_title.pack(pady=(15, 20))
        notebook = ttk.Notebook(self.root)
        notebook.pack(pady=10, padx=20, expand=True, fill='both')
        self.setup_tab(notebook, ' 🖌️ QR Generator & Styler ', self.setup_generator_tab)
        self.setup_tab(notebook, ' 🖨️ Batch Generator ', self.setup_batch_tab)
        self.setup_tab(notebook, ' 📷 Code Scanner ', self.setup_scanner_tab)
        self.setup_tab(notebook, ' 💾 Product Database ', self.setup_database_tab)
        self.setup_tab(notebook, ' 📜 Scan History ', self.setup_history_tab)
        self.status_bar = ttk.Label(self.root, text="Ready", relief=SUNKEN, anchor=W, padding=5)
        self.status_bar.pack(side=BOTTOM, fill=X)

    def setup_tab(self, notebook, text, setup_function):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text=text)
        setup_function(tab)

    def setup_generator_tab(self, parent):
        paned_window = ttk.PanedWindow(parent, orient=HORIZONTAL)
        paned_window.pack(expand=True, fill='both', padx=5, pady=5)
        
        form_container = ttk.Frame(paned_window)
        paned_window.add(form_container, weight=2)
        
        preview_container = ttk.Frame(paned_window)
        paned_window.add(preview_container, weight=1)

        qr_type_notebook = ttk.Notebook(form_container)
        qr_type_notebook.pack(expand=True, fill=BOTH, pady=5)
        self._create_product_qr_tab(qr_type_notebook)
        self._create_wifi_qr_tab(qr_type_notebook)
        self._create_styling_options(form_container)

        preview_frame = ttk.LabelFrame(preview_container, text="QR Preview", padding=15)
        preview_frame.pack(expand=True, fill=BOTH)
        self.qr_preview_label = ttk.Label(preview_frame, text="QR code will be shown here", anchor=CENTER)
        self.qr_preview_label.pack(expand=True, fill='both')
        
        self.save_qr_button = ttk.Button(preview_container, text="Save Image As...", command=self.save_qr_image, state=DISABLED)
        self.save_qr_button.pack(pady=10)
        ToolTip(self.save_qr_button, "Save the current QR code preview as a PNG image file.")
        
    def _create_product_qr_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="Product ID")
        form_frame = ttk.LabelFrame(tab, text="Product Details", padding=15)
        form_frame.pack(expand=True, fill=BOTH)
        form_frame.columnconfigure(1, weight=1)
        ttk.Label(form_frame, text="Product ID:").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.entry_id = ttk.Entry(form_frame)
        self.entry_id.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        ttk.Label(form_frame, text="Product Name:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.entry_name = ttk.Entry(form_frame)
        self.entry_name.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        ttk.Label(form_frame, text="Price (₹):").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.entry_price = ttk.Entry(form_frame)
        self.entry_price.grid(row=2, column=1, padx=10, pady=8, sticky="ew")
        btn = ttk.Button(form_frame, text="Generate Product QR", bootstyle=SUCCESS, command=self.generate_product_qr)
        btn.grid(row=3, columnspan=2, pady=20)
        ToolTip(btn, "Generates a styled QR code for the product and saves it to the database.")

    def _create_wifi_qr_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="Wi-Fi Login")
        form_frame = ttk.LabelFrame(tab, text="Network Details", padding=15)
        form_frame.pack(expand=True, fill=BOTH)
        form_frame.columnconfigure(1, weight=1)
        ttk.Label(form_frame, text="Network Name (SSID):").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.wifi_ssid_entry = ttk.Entry(form_frame)
        self.wifi_ssid_entry.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        ttk.Label(form_frame, text="Password:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.wifi_pass_entry = ttk.Entry(form_frame, show="*")
        self.wifi_pass_entry.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        ttk.Label(form_frame, text="Encryption:").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.wifi_enc_var = tk.StringVar(value="WPA")
        enc_combo = ttk.Combobox(form_frame, textvariable=self.wifi_enc_var, values=["WPA", "WEP", "nopass"], state="readonly")
        enc_combo.grid(row=2, column=1, padx=10, pady=8, sticky="ew")
        btn = ttk.Button(form_frame, text="Generate Wi-Fi QR", bootstyle=INFO, command=self.generate_wifi_qr)
        btn.grid(row=3, columnspan=2, pady=20)
        ToolTip(btn, "Creates a styled QR code for Wi-Fi login.")
        
    def _create_styling_options(self, parent):
        style_frame = ttk.LabelFrame(parent, text="Styling Options", padding=15)
        style_frame.pack(fill=X, pady=(10,0))
        style_frame.columnconfigure(1, weight=1)
        
        # Logo Selection
        ttk.Label(style_frame, text="Logo (Optional):").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        logo_frame = ttk.Frame(style_frame)
        logo_frame.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        logo_btn = ttk.Button(logo_frame, text="Select Logo", command=self.select_logo)
        logo_btn.pack(side=LEFT)
        ToolTip(logo_btn, "Select a logo image to embed in the QR code (PNG, JPG).")
        self.logo_label = ttk.Label(logo_frame, text="No logo selected.", bootstyle=SECONDARY)
        self.logo_label.pack(side=LEFT, padx=10)
        
        # Fill Color
        ttk.Label(style_frame, text="Fill Color:").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        fill_color_frame = ttk.Frame(style_frame)
        fill_color_frame.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        fill_btn = ttk.Button(fill_color_frame, text="Choose", command=self._choose_fill_color)
        fill_btn.pack(side=LEFT)
        self.fill_color_label = ttk.Label(fill_color_frame, text=self.qr_fill_color_hex, width=10)
        self.fill_color_label.pack(side=LEFT, padx=10)
        ToolTip(fill_btn, "Select the color of the QR code's data modules.")
        
        # Background Color
        ttk.Label(style_frame, text="Background Color:").grid(row=2, column=0, padx=10, pady=8, sticky="w")
        bg_color_frame = ttk.Frame(style_frame)
        bg_color_frame.grid(row=2, column=1, padx=10, pady=8, sticky="ew")
        bg_btn = ttk.Button(bg_color_frame, text="Choose", command=self._choose_bg_color)
        bg_btn.pack(side=LEFT)
        self.bg_color_label = ttk.Label(bg_color_frame, text=self.qr_bg_color_hex, width=10)
        self.bg_color_label.pack(side=LEFT, padx=10)
        ToolTip(bg_btn, "Select the color of the QR code's background.")

    def _choose_fill_color(self):
        color_code = colorchooser.askcolor(title="Choose QR Fill Color", initialcolor=self.qr_fill_color_hex)
        if color_code and color_code[1]:
            self.qr_fill_color_hex = color_code[1]
            self.fill_color_label.config(text=self.qr_fill_color_hex)
            
    def _choose_bg_color(self):
        color_code = colorchooser.askcolor(title="Choose QR Background Color", initialcolor=self.qr_bg_color_hex)
        if color_code and color_code[1]:
            self.qr_bg_color_hex = color_code[1]
            self.bg_color_label.config(text=self.qr_bg_color_hex)

    def select_logo(self):
        file_path = filedialog.askopenfilename(title="Select a Logo File", filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if file_path:
            self.logo_path = file_path
            self.logo_label.config(text=os.path.basename(file_path), bootstyle=DEFAULT)
            self.update_status(f"Logo selected: {os.path.basename(file_path)}")
        else:
            self.logo_path = None
            self.logo_label.config(text="No logo selected.", bootstyle=SECONDARY)
            
    def setup_batch_tab(self, parent):
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        ttk.Label(main_frame, text="Enter data for each QR code on a new line.", font="-size 10").grid(row=0, column=0, sticky="w", padx=5)
        self.batch_text = ttk.Text(main_frame, height=10, wrap="word", font=("Courier", 11))
        self.batch_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        btn = ttk.Button(main_frame, text="Generate Batch of QR Codes", command=self.generate_batch_qrs)
        btn.grid(row=2, column=0, pady=10)
        ToolTip(btn, "Generates a QR code for each line of text and saves them to a selected folder.")

    def setup_database_tab(self, parent):
        db_frame = ttk.Frame(parent)
        db_frame.pack(fill='both', expand=True)
        self.db_tree = self.setup_treeview_tab(db_frame, cols=("Product ID", "Product Name", "Price"))
        
        button_frame = ttk.Frame(db_frame)
        button_frame.pack(pady=10, fill=X)
        edit_btn = ttk.Button(button_frame, text="Edit Selected", bootstyle=INFO, command=self.edit_product)
        edit_btn.pack(side=LEFT, expand=True, padx=5)
        ToolTip(edit_btn, "Edit the name and price of the selected product.")
        delete_btn = ttk.Button(button_frame, text="Delete Selected", bootstyle=DANGER, command=self.delete_product)
        delete_btn.pack(side=LEFT, expand=True, padx=5)
        ToolTip(delete_btn, "Permanently deletes the selected product from the database.")
    
    def setup_history_tab(self, parent):
        history_frame = ttk.Frame(parent)
        history_frame.pack(fill='both', expand=True)
        self.history_tree = self.setup_treeview_tab(history_frame, cols=("Timestamp", "Data Type", "Scanned Data"))
        button_frame = ttk.Frame(history_frame)
        button_frame.pack(pady=10, fill=X)
        copy_btn = ttk.Button(button_frame, text="Copy Data", command=self.copy_history_selection)
        copy_btn.pack(side=LEFT, expand=True)
        delete_btn = ttk.Button(button_frame, text="Delete Selected", bootstyle=DANGER, command=self.delete_history_item)
        delete_btn.pack(side=LEFT, expand=True, padx=10)

    # --- UI Components and Updaters ---
    def setup_treeview_tab(self, parent, cols):
        tree = ttk.Treeview(parent, columns=cols, show='headings', bootstyle=PRIMARY)
        for col in cols: tree.heading(col, text=col); tree.column(col, width=150, anchor=W)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set); tree.pack(side=LEFT, fill='both', expand=True); vsb.pack(side=RIGHT, fill='y')
        return tree
    def populate_database_view(self):
        for i in self.db_tree.get_children(): self.db_tree.delete(i)
        for pid, data in self.products.items():
            self.db_tree.insert("", "end", values=(pid, data['name'], data['price']))
        self.update_status(f"Database loaded with {len(self.products)} products.")
    def populate_history_view(self):
        if hasattr(self, 'history_tree'):
            for i in self.history_tree.get_children(): self.history_tree.delete(i)
            for item in self.scan_history:
                self.history_tree.insert("", "end", values=(item['timestamp'], item['type'], item['data']))
    def display_qr_preview(self, img: Image.Image):
        self.last_generated_qr_img = img 
        self.save_qr_button.config(state=NORMAL)
        try:
            w, h = img.size
            max_size = 300
            aspect_ratio = w / h
            if w > h: new_w, new_h = max_size, int(max_size / aspect_ratio)
            else: new_h, new_w = max_size, int(max_size * aspect_ratio)
            resized_img = img.resize((new_w, new_h), Image.LANCZOS)
            self.qr_image_preview = ImageTk.PhotoImage(resized_img)
            self.qr_preview_label.config(image=self.qr_image_preview, text="")
        except Exception as e:
            self.qr_preview_label.config(text=f"Preview Error:\n{e}")
            self.update_status(f"Could not display QR preview: {e}", is_error=True)

    # --- Core Functionality ---
    def _generate_qr_image(self, data: str, logo_path: Optional[str]) -> Optional[Image.Image]:
        try:
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color=self.qr_fill_color_hex, back_color=self.qr_bg_color_hex).convert('RGB')
            if logo_path and os.path.exists(logo_path):
                logo = Image.open(logo_path)
                basewidth = int(img.size[0] * 0.25)
                wpercent = (basewidth/float(logo.size[0]))
                hsize = int((float(logo.size[1])*float(wpercent)))
                logo = logo.resize((basewidth, hsize), Image.LANCZOS)
                pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
                img.paste(logo, pos)
            return img
        except Exception as e: self.update_status(f"QR Generation Error: {e}", is_error=True); return None

    def generate_product_qr(self):
        pid, name, price_str = self.entry_id.get().strip(), self.entry_name.get().strip(), self.entry_price.get().strip()
        if not all([pid, name, price_str]): self.update_status("All product fields are required.", is_error=True); return
        try: price_val = float(price_str)
        except ValueError: self.update_status("Price must be a valid number.", is_error=True); return
        img = self._generate_qr_image(pid, self.logo_path)
        if img:
            os.makedirs(QRS_FOLDER, exist_ok=True)
            safe_filename = "".join(c for c in pid if c.isalnum() or c in ('-', '_')).rstrip()
            filename = os.path.join(QRS_FOLDER, f"{safe_filename}.png")
            img.save(filename)
            self.products[pid] = {"name": name, "price": f"₹{price_val:.2f}"}
            self.save_products()
            self.populate_database_view()
            self.display_qr_preview(img)
            self.update_status(f"Successfully generated QR for '{name}'.")
    def generate_wifi_qr(self):
        ssid, password, enc = self.wifi_ssid_entry.get().strip(), self.wifi_pass_entry.get().strip(), self.wifi_enc_var.get()
        if not ssid: self.update_status("Network Name (SSID) is required.", is_error=True); return
        wifi_string = f"WIFI:S:{ssid};T:{enc};P:{password};;"
        img = self._generate_qr_image(wifi_string, self.logo_path)
        if img: self.display_qr_preview(img); self.update_status(f"Wi-Fi QR for '{ssid}' generated for preview.")
    def generate_batch_qrs(self):
        data_lines = self.batch_text.get("1.0", "end-1c").strip().split('\n')
        if not any(data_lines): self.update_status("No data for batch generation.", is_error=True); return
        output_folder = filedialog.askdirectory(title="Select Folder to Save Batch QR Codes")
        if not output_folder: self.update_status("Batch generation cancelled."); return
        log_data = []
        for i, line in enumerate(data_lines):
            data = line.strip()
            if not data: continue
            img = self._generate_qr_image(data, logo_path=None)
            if img:
                safe_filename = f"qr_{i+1}_{''.join(c for c in data if c.isalnum())[:20]}.png"
                img.save(os.path.join(output_folder, safe_filename))
                log_data.append([data, safe_filename])
        with open(os.path.join(output_folder, 'batch_log.csv'), 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f); writer.writerow(['InputData', 'Filename']); writer.writerows(log_data)
        messagebox.showinfo("Batch Complete", f"{len(log_data)} QR codes generated in '{output_folder}'.")
        self.update_status("Batch generation complete.")

    def process_scanned_data(self, data: str):
        self.root.bell()
        if isinstance(data, bytes): data = data.decode("utf-8", errors="ignore")
        analysis = self._analyze_scanned_data(data)
        self.add_to_history(data, analysis['type'])
        self.show_scan_result_window(data, analysis)
    
    def setup_scanner_tab(self, parent):
        scanner_frame = ttk.Frame(parent)
        scanner_frame.pack(fill=BOTH, expand=True)
        self.webcam_label = ttk.Label(scanner_frame, text="\n\nWebcam feed will appear here.\n\n", anchor=CENTER, relief=SOLID, borderwidth=1)
        self.webcam_label.pack(pady=10, padx=10, fill=BOTH, expand=True)
        button_container = ttk.Frame(scanner_frame)
        button_container.pack(pady=10)
        self.scan_toggle_button = ttk.Button(button_container, text="📹 Start Live Scan", bootstyle=WARNING, command=self.toggle_webcam_scan)
        self.scan_toggle_button.pack(side=LEFT, padx=5)
        ToolTip(self.scan_toggle_button, "Starts scanning live from your webcam.")
        scan_image_btn = ttk.Button(button_container, text="🖼️ Scan from Image", bootstyle=(INFO, OUTLINE), command=self.scan_from_image)
        scan_image_btn.pack(side=LEFT, padx=5)
        ToolTip(scan_image_btn, "Opens a file dialog to scan a saved image.")
        if not self.webcam_available:
            self.scan_toggle_button.config(state=DISABLED)
            self.webcam_label.config(text="\n\nNo webcam detected.\n\nLive scanning is disabled.")
            ToolTip(self.scan_toggle_button, "No webcam detected on this system.")
    def toggle_webcam_scan(self):
        if self.is_scanning_webcam: self.stop_webcam_scan()
        else: self.start_webcam_scan()
    def start_webcam_scan(self):
        self.is_scanning_webcam = True
        self.scan_toggle_button.config(text="🛑 Stop Live Scan", bootstyle=DANGER)
        self.update_status("Starting webcam...")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.update_status("Webcam Error: Could not open camera.", is_error=True)
            self.is_scanning_webcam = False; self.scan_toggle_button.config(text="📹 Start Live Scan", bootstyle=WARNING)
            return
        self.webcam_thread = threading.Thread(target=self._scan_webcam_loop, daemon=True)
        self.webcam_thread.start()
    def stop_webcam_scan(self):
        self.is_scanning_webcam = False
        if self.webcam_thread and self.webcam_thread.is_alive(): self.webcam_thread.join(timeout=1)
        if self.cap: self.cap.release(); self.cap = None
        self.scan_toggle_button.config(text="📹 Start Live Scan", bootstyle=WARNING)
        self.webcam_label.config(image='', text="\n\nWebcam feed stopped.\n\n")
        self.update_status("Webcam scanning turned off.")
    def _scan_webcam_loop(self):
        self.root.after(0, self.update_status, "Live scanning active. Show code to camera.")
        scan_interval, frame_count = 5, 0
        while self.is_scanning_webcam and self.cap:
            ret, frame = self.cap.read()
            if not ret: self.root.after(0, self.update_status, "Webcam feed lost.", is_error=True); break
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            frame_count += 1
            if frame_count % scan_interval == 0:
                try:
                    results = self.barcode_reader.decode(pil_img)
                    if results and results[0].get('parsed'):
                        data = results[0]['parsed']
                        self.root.after(0, self.process_scanned_data, data)
                        self.root.after(100, self.stop_webcam_scan)
                        return
                except Exception: pass
            img_tk = ImageTk.PhotoImage(image=pil_img)
            self.webcam_label.imgtk = img_tk
            self.webcam_label.config(image=img_tk)
        self.root.after(0, self.stop_webcam_scan)
    def scan_from_image(self):
        file_path = filedialog.askopenfilename(title="Select an Image File", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if not file_path: self.update_status("Image scan cancelled."); return
        self.update_status(f"Scanning image: {os.path.basename(file_path)}...")
        try:
            results = self.barcode_reader.decode(file_path)
            if results and results[0].get('parsed'):
                self.root.after(100, lambda: self.process_scanned_data(results[0]['parsed']))
            else: self.update_status("Scan failed: No valid code found in image.", is_error=True)
        except Exception as e: self.update_status(f"Scanning Error: {e}", is_error=True)
    def _analyze_scanned_data(self, data: str) -> Dict[str, str]:
        if data in self.products: return {"type": "Product ID", "info": f"Name: {self.products[data]['name']}\nPrice: {self.products[data]['price']}"}
        if data.startswith("WIFI:"): return {"type": "Wi-Fi Network"}
        if data.startswith(("http://", "https://")): return {"type": "URL"}
        if data.startswith("mailto:"): return {"type": "Email Address"}
        if data.startswith("tel:"): return {"type": "Phone Number"}
        return {"type": "Plain Text"}
    def show_scan_result_window(self, data: str, analysis: Dict[str, str]):
        result_window = ttk.Toplevel(self.root, title="Scan Analysis")
        result_window.transient(self.root)
        result_window.geometry("500x350")
        ttk.Label(result_window, text="✅ Scan Successful", font="-size 16 -weight bold", bootstyle=SUCCESS).pack(pady=10)
        content_frame = ttk.Frame(result_window, padding=10); content_frame.pack(expand=True, fill=BOTH)
        ttk.Label(content_frame, text=f"Data Type: {analysis['type']}", font="-size 12").pack(anchor=W, pady=2)
        ttk.Separator(content_frame).pack(fill=X, pady=5)
        text_widget = ttk.Text(content_frame, height=5, wrap="word", font=("Courier", 11))
        text_widget.insert("1.0", data)
        if analysis.get('info'): text_widget.insert("end", f"\n\n---\n{analysis['info']}")
        text_widget.config(state="disabled"); text_widget.pack(expand=True, fill=BOTH, padx=10, pady=5)
        button_frame = ttk.Frame(result_window); button_frame.pack(pady=10)
        if analysis['type'] == 'URL':
            ttk.Button(button_frame, text="Open in Browser", command=lambda: webbrowser.open(data)).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Copy Data", command=lambda: self.copy_to_clipboard(data)).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=result_window.destroy, bootstyle=(SECONDARY, OUTLINE)).pack(side=LEFT, padx=5)

    def edit_product(self):
        try:
            selected_item_id = self.db_tree.selection()[0]
            product_id = self.db_tree.item(selected_item_id, 'values')[0]
            product_name = self.products[product_id]['name']
            product_price = self.products[product_id]['price'].replace('₹', '')
            edit_window = ttk.Toplevel(self.root, title="Edit Product")
            edit_window.transient(self.root); edit_window.geometry("400x200")
            form_frame = ttk.Frame(edit_window, padding=20)
            form_frame.pack(expand=True, fill=BOTH); form_frame.columnconfigure(1, weight=1)
            ttk.Label(form_frame, text="Product ID:").grid(row=0, column=0, sticky='w', pady=5)
            ttk.Label(form_frame, text=product_id).grid(row=0, column=1, sticky='w', pady=5)
            ttk.Label(form_frame, text="Product Name:").grid(row=1, column=0, sticky='w', pady=5)
            name_entry = ttk.Entry(form_frame); name_entry.insert(0, product_name)
            name_entry.grid(row=1, column=1, sticky='ew', pady=5)
            ttk.Label(form_frame, text="Price (₹):").grid(row=2, column=0, sticky='w', pady=5)
            price_entry = ttk.Entry(form_frame); price_entry.insert(0, product_price)
            price_entry.grid(row=2, column=1, sticky='ew', pady=5)
            def save_changes():
                new_name, new_price_str = name_entry.get().strip(), price_entry.get().strip()
                if not new_name or not new_price_str:
                    messagebox.showerror("Error", "All fields are required.", parent=edit_window); return
                try:
                    new_price_val = float(new_price_str)
                    self.products[product_id]['name'] = new_name
                    self.products[product_id]['price'] = f"₹{new_price_val:.2f}"
                    self.save_products(); self.populate_database_view()
                    self.update_status(f"Product '{product_id}' updated."); edit_window.destroy()
                except ValueError: messagebox.showerror("Error", "Price must be a valid number.", parent=edit_window)
            save_btn = ttk.Button(form_frame, text="Save Changes", command=save_changes)
            save_btn.grid(row=3, columnspan=2, pady=15)
        except IndexError: self.update_status("No product selected to edit.", is_error=True)

    def delete_product(self):
        try:
            selected_item = self.db_tree.selection()[0]
            product_id = self.db_tree.item(selected_item, 'values')[0]
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete product '{product_id}'?"):
                del self.products[product_id]; self.save_products(); self.populate_database_view()
                self.update_status(f"Product '{product_id}' deleted.")
        except IndexError: self.update_status("No product selected.", is_error=True)
    def delete_history_item(self):
        try:
            selected_items = self.history_tree.selection()
            if not selected_items: raise IndexError
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete {len(selected_items)} history item(s)?"):
                indices_to_delete = sorted([self.history_tree.index(i) for i in selected_items], reverse=True)
                for index in indices_to_delete: del self.scan_history[index]
                self.populate_history_view(); self.update_status(f"{len(selected_items)} history item(s) deleted.")
        except IndexError: self.update_status("No history item selected.", is_error=True)
    def add_to_history(self, data: str, data_type: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.scan_history.insert(0, {"timestamp": timestamp, "data": data, "type": data_type})
        self.populate_history_view()
    def copy_to_clipboard(self, text: str):
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.update_status(f"Copied to clipboard: '{text[:30]}...'")
    def copy_history_selection(self):
        try:
            selected_item = self.history_tree.selection()[0]
            item_data = self.history_tree.item(selected_item, 'values')[2]
            self.copy_to_clipboard(item_data)
        except IndexError: self.update_status("No item selected in history.", is_error=True)
    def update_status(self, message: str, is_error: bool = False):
        if is_error:
            self.status_bar.config(text=f"⚠️ {message}", bootstyle=DANGER); messagebox.showerror("Error", message)
        else: self.status_bar.config(text=f"✔️ {message}", bootstyle=DEFAULT)
        self.root.update_idletasks()
    def export_to_csv(self):
        if not self.products: messagebox.showwarning("Export Failed", "The product database is empty."); return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save Database as CSV")
        if not file_path: return
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f); writer.writerow(['product_id', 'name', 'price'])
                for pid, data in self.products.items(): writer.writerow([pid, data['name'], data['price']])
            self.update_status(f"Database exported successfully.")
        except IOError as e: self.update_status(f"Failed to export CSV: {e}", is_error=True)
    def change_theme(self):
        self.root.style.theme_use(self.theme_var.get()); self.update_status(f"Theme changed to '{self.theme_var.get()}'.")
    def save_qr_image(self):
        if self.last_generated_qr_img:
            file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")], title="Save QR Code As...")
            if file_path:
                try:
                    self.last_generated_qr_img.save(file_path)
                    self.update_status(f"QR code saved to {os.path.basename(file_path)}")
                except IOError as e: self.update_status(f"Failed to save image: {e}", is_error=True)
    def on_closing(self):
        self.stop_webcam_scan(); self.save_app_config(); self.root.destroy()
        
# --- Main Execution Block ---
if __name__ == "__main__":
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f: config = json.load(f)
        except json.JSONDecodeError: pass
    app_theme = config.get("theme", "cyborg") 
    root = ttk.Window(themename=app_theme)
    QuantumLinkApp(root)
    root.mainloop()