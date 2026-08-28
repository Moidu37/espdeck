import uasyncio as asyncio
import bluetooth
from machine import Pin, I2C
import ssd1306

# -----------------------------
# I2C + OLED
# -----------------------------
i2c = I2C(0, scl=Pin(2), sda=Pin(1), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

red = Pin(9, Pin.OUT)
green = Pin(10, Pin.OUT)
blue = Pin(11, Pin.OUT)

pc_stats = {"CPU": "0%", "RAM": "0%", "GPU": "0%", "BAT": "0%"}

oled.fill(0)
oled.text("Hello Jules !", 0, 0)
oled.text("OLED OK", 0, 10)
oled.show()

# -----------------------------
# DESIGN OLED
# -----------------------------
def draw_bar_round(oled, x, y, width, height, percent):
    fb = oled.framebuf
    fill_width = int((percent / 100) * width)
    fb.rect(x, y, width, height, 1)
    if fill_width > 4:
        fb.fill_rect(x + 2, y + 2, fill_width - 4, height - 4, 1)

def show_single_stat(oled, label, value):
    oled.fill(0)
    oled.text(label, 48, 0)
    try:
        percent = int(value[:-1])
    except Exception:
        percent = 0
    draw_bar_round(oled, 10, 20, 108, 16, percent)
    oled.text(value, 48, 45)
    oled.show()

async def screen_cycle_task():
    screens = ["CPU", "RAM", "GPU", "BAT"]
    index = 0
    while True:
        show_single_stat(oled, screens[index], pc_stats[screens[index]])
        index = (index + 1) % 4
        await asyncio.sleep(10)


async def verifier_connection():
    while True:
        if conn_handle is not None:
            # Laisse 500ms au PC pour finaliser 'start_notify'
            await asyncio.sleep_ms(500)
            
            # Vérifie que la connexion est toujours active
            if conn_handle is not None:
                ble.gatts_notify(conn_handle, char_handle, b"CONNECTE")
                print("[BLE] Notification 'CONNECTE' envoyée au PC !")
                return  # Sort définitivement de la tâche
            
        await asyncio.sleep_ms(100)

# -----------------------------
# BOUTONS
# -----------------------------
button_mute = Pin(7, Pin.IN, Pin.PULL_UP)
button1 = Pin(15, Pin.IN, Pin.PULL_UP)
button2 = Pin(16, Pin.IN, Pin.PULL_UP)

# -----------------------------
# BLE BAS NIVEAU & ÉVÉNEMENTS
# -----------------------------
ble = bluetooth.BLE()
ble.active(True)

SERVICE_UUID = bluetooth.UUID(0x181A)
CHAR_UUID = bluetooth.UUID(0x2A6E)

services = (
    SERVICE_UUID,
    (
        (CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY),
    ),
)

handles = ble.gatts_register_services((services,))
char_handle = handles[0][-1]

conn_handle = None
notifications_enabled = False

def advertising_payload(name="ESP32-S3"):
    payload = bytearray()
    payload.extend(bytes([len(name) + 1, 0x09]))
    payload.extend(name.encode())
    return payload

def start_advertising():
    adv = advertising_payload("ESP32-S3")
    ble.gap_advertise(100_000, adv)
    print("[BLE] Annonce active")

def ble_irq(event, data):
    global conn_handle
    if event == 1:
        conn_handle, _, _ = data
        print(f"[BLE] Connecté (handle: {conn_handle})")
    elif event == 2:
        conn_handle = None
        print("[BLE] Déconnecté. Relance annonce...")
        start_advertising()

ble.irq(ble_irq)
start_advertising()

# -----------------------------
# TÂCHE BOUTONS → NOTIFY
# -----------------------------

async def button_task():
    is_mute = False
    while True:
        try:
            if conn_handle is not None:
                if button_mute.value() == 0:
                    if is_mute:
                        red.on()
                        is_mute = False
                    if is_mute == False:
                        red.off()
                        is_mute == True
                    print("[HARDWARE] Bouton MUTE détecté !")
                    ble.gatts_notify(conn_handle, char_handle, b"MUTE")
                    print("[BLE] Signal MUTE envoyé !")
                    await asyncio.sleep_ms(250)
                elif button1.value() == 0:
                    print("[HARDWARE] Bouton 1 détecté !")
                    ble.gatts_notify(conn_handle, char_handle, b"BTN1")
                    await asyncio.sleep_ms(250)
                elif button2.value() == 0:
                    print("[HARDWARE] Bouton 2 détecté !")
                    ble.gatts_notify(conn_handle, char_handle, b"BTN2")
                    await asyncio.sleep_ms(250)
        except Exception as e:
            print("[ESP32] Erreur notify :", e)

        await asyncio.sleep_ms(20)


# -----------------------------
# TÂCHE DE RÉCEPTION — POLLING
# -----------------------------
async def receive_task():
    last_value = None

    while True:
        try:
            raw = ble.gatts_read(char_handle)
            if raw != last_value:
                last_value = raw
                try:
                    raw_message = raw.decode().strip()
                    print("[BLE POLL] Reçu :", raw_message)

                    parts = raw_message.split(',')
                    if len(parts) == 4 and all(p.isdigit() for p in parts):
                        cpu, ram, gpu, bat = parts
                        pc_stats["CPU"] = cpu + "%"
                        pc_stats["RAM"] = ram + "%"
                        pc_stats["GPU"] = gpu + "%"
                        pc_stats["BAT"] = bat + "%"
                    else:
                        print("[BLE POLL] Message invalide :", raw_message)

                except Exception as e:
                    print("[BLE POLL] Decode error :", e)

        except Exception as e:
            print("[BLE POLL] Erreur lecture :", e)

        await asyncio.sleep_ms(50)

# -----------------------------
# MAIN
# -----------------------------
async def main():
    await asyncio.gather(
        button_task(),
        screen_cycle_task(),
        receive_task(),
        verifier_connection()
    )

asyncio.run(main())