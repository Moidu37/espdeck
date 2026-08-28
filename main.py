import asyncio
import threading
import psutil
from bleak import BleakClient, BleakScanner
from pyadl import ADLManager
import customtkinter
import keyboard
import pyautogui
import time
import os
from windows_toasts import WindowsToaster, Toast, ToastDisplayImage

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
app = customtkinter.CTk()
app.geometry("800x600")

# Ajout de l'icône dans l'interface
app.iconbitmap("icon.ico")

bouton1 = ""
bouton2 = ""

def checkbox_event():
    print("checkbox toggled, current value:", check_var.get())

def optionmenu_callback(choice):
    print("optionmenu dropdown clicked:", choice)

def bouton_valider():
    global bouton1, bouton2
    if optionmenu_bouton.get() == "Bouton 1":
        bouton1 = ""
        if checkbox_ctrl.get() == "ctrl":
            bouton1 = "ctrl"
        if checkbox_maj.get() == "maj":
            bouton1 = bouton1 + "+shift"
        if checkbox_alt.get() == "alt":
            bouton1 = bouton1 + "+alt"
        if checkbox_space.get() == "space":
            bouton1 = bouton1 + "+space"
        if optionmenu_lettre.get() is not None:
            bouton1 = bouton1 + "+" + optionmenu_lettre.get()
        print("Bouton 1 :", bouton1)
        keyboard.send(bouton1)
    elif optionmenu_bouton.get() == "Bouton 2":
        bouton2 = ""
        if checkbox_ctrl.get() == "ctrl":
            bouton2 = "ctrl"
        if checkbox_maj.get() == "maj":
            bouton2 = bouton2 + "+shift"
        if checkbox_alt.get() == "alt":
            bouton2 = bouton2 + "+alt"
        if checkbox_space.get() == "space":
            bouton2 = bouton2 + "+space"
        if optionmenu_lettre.get() is not None:
            bouton2 = bouton2 + "+" + optionmenu_lettre.get()
        print("Bouton 2 :", bouton2)
        keyboard.send(bouton2)

optionmenu_bouton_name = customtkinter.StringVar(value="Bouton")
optionmenu_bouton = customtkinter.CTkOptionMenu(app, values=["Bouton 1", "Bouton 2"], command=optionmenu_callback, variable=optionmenu_bouton_name)
optionmenu_bouton.pack(padx=20, pady=10)

check_var = customtkinter.StringVar(value="off")

checkbox_ctrl = customtkinter.CTkCheckBox(app, text="Contrôle", command=checkbox_event, variable=check_var, onvalue="ctrl", offvalue=None, checkbox_width=16, checkbox_height=16, border_width=2)
checkbox_ctrl.pack(padx=20, pady=10)

checkbox_maj = customtkinter.CTkCheckBox(app, text="Majuscule", command=checkbox_event, variable=check_var, onvalue="maj", offvalue=None, checkbox_width=16, checkbox_height=16, border_width=2)
checkbox_maj.pack(padx=20, pady=10)

checkbox_alt = customtkinter.CTkCheckBox(app, text="Alt", command=checkbox_event, variable=check_var, onvalue="alt", offvalue=None, checkbox_width=16, checkbox_height=16, border_width=2)
checkbox_alt.pack(padx=20, pady=10)

checkbox_space = customtkinter.CTkCheckBox(app, text="Space", command=checkbox_event, variable=check_var, onvalue="space", offvalue=None, checkbox_width=16, checkbox_height=16, border_width=2)
checkbox_space.pack(padx=20, pady=10)

optionmenu_lettre_name = customtkinter.StringVar(value="Lettres")
optionmenu_lettre = customtkinter.CTkOptionMenu(app, values=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"], command=optionmenu_callback, variable=optionmenu_lettre_name)
optionmenu_lettre.pack(padx=20, pady=10)

valider = customtkinter.CTkButton(app, text="Valider", command=bouton_valider)
valider.pack(padx=20, pady=10)

# ---------------------------------------------------------------------------
# BLE & CLIC MUTE
# ---------------------------------------------------------------------------
SERVICE_UUID = "0000181a-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "00002a6e-0000-1000-8000-00805f9b34fb"

def notification_handler(sender, data):
    message = data.decode('utf-8').strip()
    print(f"[REÇU DU BOUTON] : {message}")
    
    if message == "MUTE":
        # 1. Sauvegarde la position initiale du curseur
        pos_initiale = pyautogui.position()
        
        # 2. Déplace vers les coordonnées cibles et clique
        pyautogui.click(-2064, 820)
        time.sleep(0.05)
        
        # 3. Replacer immédiatement le curseur à sa position de départ
        pyautogui.moveTo(pos_initiale)
        pyautogui.click(pos_initiale)
        print(f"[ACTION] Clic Mute exécuté en (-2064, 820), curseur remis en {pos_initiale}")

# ---------------------------------------------------------------------------
# Métriques système (CPU / RAM / GPU / Batterie)
# ---------------------------------------------------------------------------
_nvidia_handle = None
_nvidia_available = False
try:
    import pynvml
    pynvml.nvmlInit()
    _nvidia_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    _nvidia_available = True
except Exception:
    _nvidia_available = False

def get_gpu_usage():
    try:
        devices = ADLManager.getInstance().getDevices()
        if devices:
            return int(devices[0].getCurrentUsage())
    except Exception as e:
        print("Erreur GPU (AMD/pyadl) :", e)

    if _nvidia_available:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_nvidia_handle)
            return int(util.gpu)
        except Exception as e:
            print("Erreur GPU (NVIDIA/pynvml) :", e)

    print("Aucun GPU compatible détecté (ni AMD, ni NVIDIA).")
    return 0

def get_battery_usage():
    batt = psutil.sensors_battery()
    if batt is None:
        return 100
    percent = int(batt.percent)
    if percent <= 1 and batt.power_plugged:
        return 100
    return percent

def get_stats():
    cpu = int(psutil.cpu_percent())
    ram = int(psutil.virtual_memory().percent)
    gpu = get_gpu_usage()
    bat = get_battery_usage()
    return f"{cpu},{ram},{gpu},{bat}"

async def get_stats_loop(client):
    print("Envoi continu des métriques...")
    while client.is_connected:
        data_str = get_stats()
        await client.write_gatt_char(CHARACTERISTIC_UUID, data_str.encode('utf-8'))
        print("Envoyé :", data_str)
        await asyncio.sleep(10)

async def main():
    device = None
    while device is None:
        print("Recherche de l'ESP32-S3...")
        device = await BleakScanner.find_device_by_name("ESP32-S3", timeout=5.0)
        if not device:
            await asyncio.sleep(2)

    print(f"Connecté à {device.name}")

    async with BleakClient(device) as client:
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)

        # Notification de connexion
        toaster = WindowsToaster("ESPDeck")
        toast = Toast()
        toast.text_fields = ["Connecté à l'ESPDeck"]
        if os.path.exists("logo.png"):
            toast.AddImage(ToastDisplayImage.fromPath("logo.png"))
        toaster.show_toast(toast)

        await get_stats_loop(client)

# ---------------------------------------------------------------------------
# Lancement
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ble_thread = threading.Thread(target=lambda: asyncio.run(main()), daemon=True)
    ble_thread.start()

    app.mainloop()