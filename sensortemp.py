import serial, time, tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------- CONFIGURACIÓN ----------------
COM_PORT, BAUD_RATE = 'COM3', 9600        # Puerto y velocidad del puerto serie
temperaturas, humedades, monitoreando = [], [], False  # Variables globales

# ---------------- CONEXIÓN CON ARDUINO ----------------
try:
    arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print("📡 Conectado al Arduino Tierra...")
except:
    arduino = None
    print("❌ Error al conectar al Arduino")

# ---------------- FUNCIONES PRINCIPALES ----------------
def leer_datos():
    """Lee los datos enviados por el Arduino Tierra."""
    if arduino and arduino.in_waiting > 0:
        linea = arduino.readline().decode().strip()  # Leer y limpiar línea
        if linea and linea != "ERROR_SENSOR":
            try:
                h, t = map(float, linea.split(','))  # Separar humedad y temperatura
                temperaturas.append(t)
                humedades.append(h)
                label_temp.config(text=f"Temp: {t:.1f} °C")
                label_hum.config(text=f"Hum: {h:.1f} %")
                actualizar_graficos()
            except:
                pass 
        else:
            # Si el sensor envía un error
            label_temp.config(text="Error Sensor")
            label_hum.config(text="Error Sensor")

def actualizar_graficos():
    """Actualiza las gráficas con las últimas lecturas."""
    for ax, datos, color, lbl, ylab, ylim in [
        (ax1, temperaturas, 'r', 'Temperatura', 'Temperatura (°C)', (15, 50)),
        (ax2, humedades, 'b', 'Humedad', 'Humedad (%)', (0, 100))
    ]:
        ax.clear()
        ax.set_ylim(*ylim)
        ax.set_ylabel(ylab, fontsize=10)
        ax.plot(datos, color+'-', marker='o', markersize=4, linewidth=1.5, label=lbl)
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.6)

    ax2.set_xlabel('Tiempo (s)', fontsize=10)
    fig.tight_layout()
    canvas.draw()

def cambiar_estado(nuevo):
    """Activa o pausa la lectura de datos."""
    global monitoreando
    monitoreando = nuevo
    boton_iniciar.config(state=('disabled' if nuevo else 'normal'))
    boton_detener.config(state=('normal' if nuevo else 'disabled'))
    if not nuevo:
        boton_pausar.config(state='normal')

def detener():
    """Detiene la lectura y limpia los datos."""
    cambiar_estado(False)
    temperaturas.clear()
    humedades.clear()
    label_temp.config(text="Temp: --.- °C")
    label_hum.config(text="Hum: --.- %")
    actualizar_graficos()

def actualizar():
    """Función que se ejecuta cada segundo para leer datos."""
    if monitoreando:
        leer_datos()
    ventana.after(1000, actualizar)  # Se vuelve a llamar cada 1 segundo

# ---------------- CAMBIO DE PANTALLAS ----------------
def mostrar(frame):
    """Muestra un frame y oculta el otro (menú o monitor)."""
    [f.pack_forget() for f in (frame_menu, frame_monitor)]
    frame.pack(fill="both", expand=True)

# ---------------- INTERFAZ GRÁFICA ----------------
ventana = tk.Tk()
ventana.title("Monitor Arduino Tierra")
ventana.geometry("650x550")

# ======== MENÚ PRINCIPAL ========
frame_menu = tk.Frame(ventana, bg="#1e1e1e")
frame_menu.pack(fill="both", expand=True)

# Título del menú
tk.Label(frame_menu, text="🌍 MENÚ PRINCIPAL", font=("Arial", 18, "bold"),
         bg="#1e1e1e", fg="white").pack(pady=30)

# Botones del menú
for txt, cmd in [("A - Temperatura y Humedad", lambda: mostrar(frame_monitor))] + \
                [(f"{c} - Opción {c}", lambda c=c: print(f"Seleccionaste {c}")) for c in "BCDE"]:
    tk.Button(frame_menu, text=txt, font=("Arial", 14), width=25,
              bg="#2e8b57", fg="white", command=cmd).pack(pady=8)

# ======== MONITOR TEMPERATURA Y HUMEDAD ========
frame_monitor = tk.Frame(ventana)

# --- Botones de control ---
frame_botones = tk.Frame(frame_monitor)
frame_botones.pack(pady=10)

boton_iniciar = tk.Button(frame_botones, text="INICIAR", bg="green", fg="white", width=10,
                          command=lambda: cambiar_estado(True))
boton_pausar = tk.Button(frame_botones, text="PAUSAR", bg="yellow", fg="black", width=10,
                         command=lambda: cambiar_estado(False))
boton_detener = tk.Button(frame_botones, text="DETENER", bg="red", fg="white", width=10,
                          state='disabled', command=detener)
boton_volver = tk.Button(frame_botones, text="VOLVER", bg="gray", fg="white", width=10,
                         command=lambda: mostrar(frame_menu))


for b in (boton_iniciar, boton_pausar, boton_detener, boton_volver):
    b.pack(side=tk.LEFT, padx=5)

# --- Etiquetas de los datos ---
frame_datos = tk.Frame(frame_monitor)
frame_datos.pack(pady=5)

label_temp = tk.Label(frame_datos, text="Temp: --.- °C", font=("Arial", 12), fg="red")
label_hum = tk.Label(frame_datos, text="Hum: --.- %", font=("Arial", 12), fg="blue")
label_temp.pack(side=tk.LEFT, padx=10)
label_hum.pack(side=tk.LEFT, padx=10)

# --- Gráficas ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 5))
canvas = FigureCanvasTkAgg(fig, master=frame_monitor)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
fig.tight_layout()

# ---------------- INICIO DE LA APP ----------------
actualizar()            
mostrar(frame_menu)     # Muestra el menú principal al arrancar
ventana.mainloop()      # Ejecuta la interfaz gráfica

# ---------------- CIERRE SERIAL ----------------
if arduino and arduino.is_open:
    arduino.close()
