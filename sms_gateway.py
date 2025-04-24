import os
import sys
import time
import serial
import json
import tkinter as tk
from tkinter import filedialog, messagebox
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def resource_path(relative_path):
    """ Get absolute path to resource for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_FILE = resource_path("config.json")

class GSMModem:
    def __init__(self):
        self.ser = None
        self.find_modem_port()

    def find_modem_port(self):
        ports = ['COM3', 'COM4', 'COM5', '/dev/ttyUSB0', '/dev/ttyACM0']
        for port in ports:
            try:
                ser = serial.Serial(port, 9600, timeout=1)
                ser.write(b'AT\r')
                response = ser.read(100)
                if b'OK' in response:
                    self.ser = ser
                    print(f"تم الكشف عن المودم على المنفذ {port}")
                    return
                ser.close()
            except (serial.SerialException, OSError):
                continue
        raise Exception("لم يتم العثور على مودم GSM")

    def send_sms(self, number, message):
        try:
            cleaned_number = ''.join(filter(str.isdigit, number))
            if len(cleaned_number) == 9:
                intl_number = f"+966{cleaned_number}"
            elif len(cleaned_number) == 12 and cleaned_number.startswith('966'):
                intl_number = f"+{cleaned_number}"
            else:
                raise ValueError("رقم غير صحيح")
            
            self.ser.write(b'AT+CMGF=1\r')
            time.sleep(0.5)
            
            self.ser.write(f'AT+CMGS="{intl_number}"\r'.encode())
            time.sleep(0.5)
            
            self.ser.write(message.encode() + b"\x1A")
            time.sleep(2)
            
            response = self.ser.read_all().decode()
            return 'OK' in response
        except Exception as e:
            print(f"خطأ في الإرسال: {e}")
            return False

class SMSHandler(FileSystemEventHandler):
    def __init__(self, modem):
        self.modem = modem

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.txt'):
            return

        try:
            with open(event.src_path, 'r', encoding='utf-8') as f:
                content = f.read().split('\n')
                if len(content) < 2:
                    return
                number = content[0].strip()
                message = '\n'.join(content[1:]).strip()

            if self.validate_number(number):
                if self.modem.send_sms(number, message):
                    os.remove(event.src_path)
                    print(f"تم الإرسال إلى {number}")
                else:
                    print("فشل الإرسال")
        except Exception as e:
            print(f"خطأ في المعالجة: {e}")

    def validate_number(self, number):
        cleaned = ''.join(filter(str.isdigit, number))
        return len(cleaned) in (9, 12) and cleaned.isdigit()

class ConfigManager:
    @staticmethod
    def load():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"monitor_folder": ""}

    @staticmethod
    def save(config):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False)

class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SMS Gateway Config")
        self.geometry("500x300")
        self.config = ConfigManager.load()
        self.modem = None
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="مسار مجلد المراقبة:").pack(pady=5)
        
        self.entry = tk.Entry(self, width=40)
        self.entry.pack(pady=5)
        self.entry.insert(0, self.config.get("monitor_folder", ""))
        
        tk.Button(self, text="استعراض", command=self.browse_folder).pack(pady=5)
        tk.Button(self, text="اختبار الاتصال بالمودم", command=self.test_modem).pack(pady=10)
        tk.Button(self, text="بدء المراقبة", command=self.start_monitoring).pack(pady=15)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, folder)

    def test_modem(self):
        try:
            self.modem = GSMModem()
            messagebox.showinfo("نجاح", "تم الاتصال بنجاح بالمودم GSM")
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل الاتصال: {str(e)}")

    def start_monitoring(self):
        folder = self.entry.get()
        if not folder:
            messagebox.showerror("خطأ", "الرجاء تحديد مسار المجلد")
            return
        
        ConfigManager.save({"monitor_folder": folder})
        self.destroy()
        start_monitoring(folder)

def start_monitoring(folder_path):
    try:
        modem = GSMModem()
        event_handler = SMSHandler(modem)
        observer = Observer()
        observer.schedule(event_handler, folder_path, recursive=True)
        observer.start()
        print(f"بدأت المراقبة في: {folder_path}")

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    except Exception as e:
        print(f"خطأ: {str(e)}")
    observer.join()

if __name__ == "__main__":
    config = ConfigManager.load()
    if config.get("monitor_folder"):
        start_monitoring(config["monitor_folder"])
    else:
        app = AppGUI()
        app.mainloop()
