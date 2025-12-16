 
import serial, time, tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime, date
import json
import os
import re
import matplotlib
import tkinter.messagebox as messagebox
import pyttsx3
import hashlib  # para hash de contraseñas
import threading




# ---------------- CONFIG ----------------
COM_PORT, BAUD_RATE = 'COM9', 9600
temperaturas, humedades, tiempos = [], [], []
monitoreando = tiempo_pausado = False
ultima_temperatura = ultima_humedad = tiempo_inicio = None
ultimo_tiempo_dato = -2
# Radar
distancias, angulos = [], []
radar_monitoreando = False
iAngle = 0
iDistance = 0
# Orbital
orbital_monitoreando = False
window_closed = False
x_vals = []
y_vals = []
z_vals = []
R_EARTH = 6371000  # Radius of Earth in meters
regex_orbital = re.compile(
    r"Position:\s*\(X:\s*([\d\.-]+)\s*m,\s*Y:\s*([\d\.-]+)\s*m,\s*Z:\s*([\d\.-]+)\s*m\).*"
)


modo_actual = "menu"
orbital_window = None


# ---------- VOZ ----------
voz = pyttsx3.init()
voz.setProperty('rate', 150)




alarma_radar_activa = False




modo_actual = "menu"




# --------- SISTEMA DE REGISTRO DE EVENTOS -----------
ARCHIVO_EVENTOS = "eventos_registrados.json"




def cargar_eventos():
    """Carga los eventos desde el archivo JSON"""
    if os.path.exists(ARCHIVO_EVENTOS):
        try:
            with open(ARCHIVO_EVENTOS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []




def guardar_eventos(eventos):
    """Guarda los eventos en el archivo JSON"""
    with open(ARCHIVO_EVENTOS, 'w', encoding='utf-8') as f:
        json.dump(eventos, f, ensure_ascii=False, indent=2)




def registrar_evento(tipo, descripcion):
    """Registra un nuevo evento"""
    eventos = cargar_eventos()
    nuevo_evento = {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "hora": datetime.now().strftime("%H:%M:%S"),
        "timestamp": datetime.now().isoformat(),
        "tipo": tipo,
        "descripcion": descripcion
    }
    eventos.append(nuevo_evento)
    guardar_eventos(eventos)
    print(f"📝 Evento registrado: {tipo} - {descripcion}")




def registrar_comando(comando):
    """Registra un comando ejecutado"""
    registrar_evento("COMANDO", f"Ejecutado: {comando}")




def registrar_alarma(mensaje):
    """Registra una alarma"""
    registrar_evento("ALARMA", mensaje)




def registrar_observacion(observacion):
    """Registra una observación del usuario"""
    registrar_evento("OBSERVACION", observacion)




def registrar_orbital(posicion):
    """Registra una posición orbital"""
    registrar_evento("ORBITAL", f"Posición satelital: {posicion}")




# --------- ALARMA POR TEMPERATURA -----------
contador_alarmas = 0
alarma_mostrada = False




def mostrar_alarma_temp():
    global alarma_mostrada
    if alarma_mostrada:
        return




    alarma_mostrada = True




    # Registrar la alarma en el sistema
    registrar_alarma("Temperatura alta - Media superó 30°C")




    ventana_alarma = tk.Toplevel()
    ventana_alarma.title("⚠️ ALARMA DE TEMPERATURA ⚠️")
    ventana_alarma.geometry("320x160")
    ventana_alarma.configure(bg="#aa0000")
    tk.Label(
        ventana_alarma,
        text="¡TEMPERATURA ALTA!\nLa media superó 30°C",
        font=("Arial", 15, "bold"),
        bg="#aa0000",
        fg="white"
    ).pack(pady=20)




    def cerrar():
        global alarma_mostrada
        alarma_mostrada = False
        ventana_alarma.destroy()




    tk.Button(
        ventana_alarma,
        text="ENTENDIDO",
        font=("Arial", 13),
        bg="white",
        fg="black",
        command=cerrar
    ).pack(pady=10)




# --------- ALERTA RADAR POR OBJETO CERCANO -----------
def hablar_alerta_radar():
    voz.say("Alerta, objeto detectado a menos de diez centímetros")
    voz.runAndWait()




# ---------------- Arduino ----------------
try:
    arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)
    print("📡 Conectado al Arduino Tierra...")
    registrar_comando("Conexión Arduino establecida")
except Exception as e:
    arduino = None
    print(f"❌ Error al conectar al Arduino: {e}")




# ---------------- Monitor funciones ----------------
def obtener_tiempo_actual():
    return 0.0 if tiempo_inicio is None else round(time.time() - tiempo_inicio, 1)




def leer_datos():
    """
    Lee una línea del puerto serie y:
    - Si contiene IR_STOP ... fuerza STOP y menú.
    - Si empieza por IR_ ... actúa sobre la GUI (mando IR).
    - Si es h,t ... actualiza monitor de T/H.
    """
    global ultima_temperatura, ultima_humedad, ultimo_tiempo_dato
    t_actual = obtener_tiempo_actual()


    if arduino and arduino.in_waiting:
        try:
            linea = arduino.readline().decode(errors="ignore").strip()
            if not linea:
                return


            print("📡 Recibido:", linea)


            # 1) Prioridad máxima: cualquier aparición de IR_STOP
            if linea == "IR_STOP":
                print("FORZANDO STOP Y MENU POR IR_STOP (comparación exacta)")
                # Si estamos en radar, parar radar
                if modo_actual == "radar":
                    radar_detener()
                # Detener monitor T/H por si estuviera activo
                detener_monitoreo()
                mostrar("menu")
                return


            # 2) Comandos IR normales
            if linea.startswith("IR_"):
                print("COMANDO IR RECIBIDO:", linea)
                if linea == "IR_TEMP":
                    mostrar("monitor")
                    iniciar_monitoreo()
                elif linea == "IR_RADAR":
                    mostrar("radar")
                    radar_iniciar()
                elif linea == "IR_ORBITAL":
                    abrir_orbital()
                    orbital_iniciar()
                elif linea == "IR_PAUSA":
                    if modo_actual == "radar" and radar_monitoreando:
                        radar_detener()
                    elif monitoreando:
                        pausar_monitoreo()
                    elif tiempo_pausado:
                        reanudar_monitoreo()
                return  # ya gestionado


            # 3) Filtros varios
            if linea in ("FALLO_ULTRASONICO", "IR", "RADAR_INICIADO", "MODO_RADAR"):
                return
            if linea in ("ERROR_SENSOR", "FALLO_SENSOR"):
                label_temp.config(text="Error Sensor")
                label_hum.config(text="Error Sensor")
                return
            if ',' not in linea:
                return


            # 4) Datos h,t
            h, t = map(float, linea.split(','))
            temperaturas.append(t)
            humedades.append(h)
            tiempos.append(t_actual)
            ultima_temperatura = t
            ultima_humedad = h
            ultimo_tiempo_dato = t_actual
            label_temp.config(text=f"Temp: {t:.1f} °C")
            label_hum.config(text=f"Hum: {h:.1f} %")


        except Exception as e:
            print(f"Error leyendo datos: {e}")
            return




def actualizar_datos_pausados():
    global ultimo_tiempo_dato
    if not monitoreando and tiempo_pausado and ultima_temperatura is not None:
        t_actual = obtener_tiempo_actual()
        if t_actual - ultimo_tiempo_dato >= 2:
            temperaturas.append(ultima_temperatura)
            humedades.append(ultima_humedad)
            tiempos.append(t_actual)
            ultimo_tiempo_dato = t_actual
            label_temp.config(text=f"Temp: {ultima_temperatura:.1f} °C")
            label_hum.config(text=f"Hum: {ultima_humedad:.1f} %")




def actualizar_graficos():
    global contador_alarmas, alarma_mostrada
    try:
        for ax, datos, c, lbl, ylab, ylim in [
            (ax1, temperaturas, 'r', 'Temperatura', 'Temperatura (°C)', (15, 50)),
            (ax2, humedades, 'b', 'Humedad', 'Humedad (%)', (0, 100))
        ]:
            ax.clear()
            ax.set_ylim(*ylim)
            ax.set_ylabel(ylab, fontsize=10)
            x_max = max(tiempos) if tiempos else 10
            ax.set_xlim(0, max(10, x_max + 1))
            if datos and tiempos:
                if monitoreando and len(datos) > 1:
                    ax.plot(tiempos, datos, c + '-', marker='o', markersize=4, linewidth=1.5, label=lbl)
                else:
                    ax.plot(tiempos, datos, c + 'o-', markersize=4, linewidth=1.5, label=lbl)
            ax.legend(loc="upper left", fontsize=8)
            ax.grid(True, linestyle='--', alpha=0.6)
        ax2.set_xlabel('Tiempo (s)', fontsize=10)




        # -------- MEDIA --------
        if temperaturas:
            media_temp = sum(temperaturas[-10:]) / min(10, len(temperaturas))
            label_media_temp.config(text=f"Media 10 últimas Temp: {media_temp:.1f} °C")
        else:
            label_media_temp.config(text="Media 10 últimas Temp: -- °C")
        if humedades:
            media_hum = sum(humedades[-10:]) / min(10, len(humedades))
            label_media_hum.config(text=f"Media 10 últimas Hum: {media_hum:.1f} %")
        else:
            label_media_hum.config(text="Media 10 últimas Hum: -- %")




        # ---------- ALARMA ----------
        if temperaturas and len(temperaturas) >= 3:
            if media_temp > 30:
                contador_alarmas += 1
            else:
                contador_alarmas = 0
            if contador_alarmas >= 3 and not alarma_mostrada:
                mostrar_alarma_temp()
                contador_alarmas = 0




        fig.tight_layout()
        canvas.draw()
    except Exception as e:
        print(f"Error actualizando gráficos: {e}")




def forzar_primer_dato():
    global ultima_temperatura, ultima_humedad, ultimo_tiempo_dato, tiempo_inicio
    if arduino:
        for _ in range(10):
            if arduino.in_waiting:
                try:
                    linea = arduino.readline().decode().strip()
                    if linea and linea not in ("ERROR_SENSOR", "FALLO_SENSOR"):
                        h, t = map(float, linea.split(','))
                        tiempo_inicio = time.time()
                        temperaturas.append(t)
                        humedades.append(h)
                        tiempos.append(0.0)
                        ultima_temperatura, ultima_humedad, ultimo_tiempo_dato = t, h, 0.0
                        label_temp.config(text=f"Temp: {t:.1f} °C")
                        label_hum.config(text=f"Hum: {h:.1f} %")
                        break
                except:
                    pass
            time.sleep(0.1)




def iniciar_monitoreo():
    global monitoreando, tiempo_inicio, tiempo_pausado, ultima_temperatura, ultima_humedad, ultimo_tiempo_dato, contador_alarmas
    if radar_monitoreando:
        radar_detener()
    if orbital_monitoreando:
        orbital_detener()
    if arduino:
        arduino.reset_input_buffer()
    temperaturas.clear()
    humedades.clear()
    tiempos.clear()
    ultima_temperatura = ultima_humedad = None
    ultimo_tiempo_dato = -2
    tiempo_pausado = False
    monitoreando = True
    contador_alarmas = 0
    tiempo_inicio = time.time()
    actualizar_estado_botones()
    label_tiempo.config(text="Tiempo: 0.0 s")
    label_temp.config(text="Temp: --.- °C")
    label_hum.config(text="Hum: --.- %")
    registrar_comando("Iniciar monitoreo de temperatura/humedad")
    ventana.after(500, forzar_primer_dato)




def pausar_monitoreo():
    global monitoreando, tiempo_pausado
    monitoreando = False
    tiempo_pausado = True
    actualizar_estado_botones()
    registrar_comando("Pausar monitoreo")




def reanudar_monitoreo():
    global monitoreando, tiempo_pausado
    monitoreando = True
    tiempo_pausado = False
    actualizar_estado_botones()
    registrar_comando("Reanudar monitoreo")




def detener_monitoreo():
    global monitoreando, tiempo_inicio, tiempo_pausado
    global ultima_temperatura, ultima_humedad, ultimo_tiempo_dato
    global contador_alarmas, orbital_window


    monitoreando = False
    tiempo_pausado = False
    tiempo_inicio = None
    ultima_temperatura = None
    ultima_humedad = None
    ultimo_tiempo_dato = -2
    contador_alarmas = 0


    temperaturas.clear()
    humedades.clear()
    tiempos.clear()


    label_tiempo.config(text="Tiempo: 0.0 s")
    label_temp.config(text="Temp: --.- °C")
    label_hum.config(text="Hum: --.- %")
    label_media_temp.config(text="Media 10 últimas Temp: -- °C")
    label_media_hum.config(text="Media 10 últimas Hum: -- %")


    actualizar_estado_botones()
    actualizar_graficos()
    registrar_comando("Detener monitoreo")


    # cerrar ventana orbital si existe
    if orbital_window is not None:
        print("CERRANDO VENTANA ORBITAL DESDE detener_monitoreo()")
        orbital_window.destroy()
        orbital_window = None




def actualizar_estado_botones():
    if monitoreando:
        estados = ('disabled', 'normal', 'disabled', 'normal')
    elif tiempo_pausado:
        estados = ('disabled', 'disabled', 'normal', 'normal')
    else:
        estados = ('normal', 'disabled', 'disabled', 'disabled')
    botones = (boton_iniciar, boton_pausar, boton_reanudar, boton_detener)
    for boton, estado in zip(botones, estados):
        boton.config(state=estado)




# ---------------- Radar funciones ----------------
def radar_iniciar():
    global radar_monitoreando
    if monitoreando:
        detener_monitoreo()
    if orbital_monitoreando:
        orbital_detener()
    radar_monitoreando = True
    distancias.clear()
    angulos.clear()
    if arduino:
        try:
            arduino.reset_input_buffer()
            arduino.write(b'U')
            time.sleep(0.5)
            if arduino.in_waiting:
                arduino.readline()
        except:
            pass
    registrar_comando("Iniciar radar de distancias")




def radar_detener():
    global radar_monitoreando
    radar_monitoreando = False
    if arduino:
        try:
            arduino.write(b'T')
            time.sleep(0.1)
        except:
            pass
    registrar_comando("Detener radar")




def actualizar_radar():
    global distancias, angulos, iAngle, iDistance, alarma_radar_activa




    if radar_monitoreando and arduino and arduino.in_waiting:
        try:
            linea = arduino.readline().decode().strip()
            if (linea and linea not in ("FALLO_ULTRASONICO", "IR", "RADAR_INICIADO", "MODO_RADAR")
                and ',' in linea):
                a, d = map(int, linea.split(','))




                # SIEMPRE actualizar ángulo
                iAngle = a
                iDistance = d




                # Nuevo barrido
                if a == 0:
                    angulos.clear()
                    distancias.clear()




                # Solo guardar puntos si hay objeto
                if 0 < d <= 40 and 0 <= a <= 180:
                    angulos.append(np.radians(a))
                    distancias.append(d)




        except:
            pass




    ax_radar.clear()
    ax_radar.set_facecolor('black')
    fig_radar.patch.set_facecolor('black')




    ax_radar.set_theta_zero_location('W')
    ax_radar.set_theta_direction(-1)
    ax_radar.set_thetalim(0, np.pi)
    ax_radar.set_rmax(40)
    ax_radar.grid(True, color='lime', linewidth=0.8)
    ax_radar.set_yticklabels([])
    ax_radar.spines['polar'].set_color('lime')
    ax_radar.tick_params(colors='lime')




    # 🔥 BARRIDO (SIEMPRE)
    ax_radar.plot(
        [np.radians(iAngle), np.radians(iAngle)],
        [0, 40],
        color='lime',
        linewidth=1.5
    )




    # Objetos detectados
    if angulos and distancias:
        ax_radar.plot(angulos, distancias, 'ro')




    canvas_radar.draw()




    # 🔊 Alarma
    if 0 < iDistance < 10:
        if not alarma_radar_activa:
            alarma_radar_activa = True
            registrar_alarma("Alerta: objeto a menos de 10 cm")
            hablar_alerta_radar()
    else:
        alarma_radar_activa = False




    if radar_monitoreando:
        ventana.after(60, actualizar_radar)




# ---------------- Funciones Orbitales ----------------
def orbital_iniciar():
    global orbital_monitoreando, x_vals, y_vals, z_vals




    if monitoreando:
        detener_monitoreo()
    if radar_monitoreando:
        radar_detener()




    orbital_monitoreando = True
    x_vals.clear()
    y_vals.clear()
    z_vals.clear()




    if arduino:
        try:
            arduino.reset_input_buffer()
            arduino.write(b'O')
            time.sleep(0.5)




            # Leer respuesta inicial
            if arduino.in_waiting:
                response = arduino.readline().decode().strip()
                print(f"Respuesta Arduino: {response}")




        except Exception as e:
            print(f"Error enviando comando O: {e}")




    registrar_comando("Iniciar monitoreo orbital")
   




    # Iniciar actualización
    actualizar_orbital()




def orbital_detener():
    """Detiene el monitoreo orbital"""
    global orbital_monitoreando




    orbital_monitoreando = False




    if arduino:
        try:
            arduino.write(b'T')
            time.sleep(0.1)
        except:
            pass




    registrar_comando("Detener monitoreo orbital")




def actualizar_orbital():
    global orbital_monitoreando, x_vals, y_vals, z_vals, window_closed, earth_slice




    if orbital_monitoreando and arduino:
        try:
            # Leer toda la línea disponible
            if arduino.in_waiting:
                line = arduino.readline()
                if line:
                    line_str = line.decode(errors="ignore").strip()
                    print(f"📡 Recibido: {line_str}")  # DEBUG




                    # Buscar posición orbital
                    match = regex_orbital.search(line_str)
                    if match:
                        x = float(match.group(1))
                        y = float(match.group(2))
                        z = float(match.group(3))




                        print(f"🛰️ Posición orbital procesada: X={x}, Y={y}, Z={z}")




                        # Actualizar datos y gráfico
                        x_vals.append(x)
                        y_vals.append(y)
                        z_vals.append(z)




                        # Limitar tamaño de listas
                        max_points = 100
                        if len(x_vals) > max_points:
                            x_vals = x_vals[-max_points:]
                            y_vals = y_vals[-max_points:]
                            z_vals = z_vals[-max_points:]




                        # Actualizar gráfico
                        update_orbital_plot(x, y)




                        # Registrar evento
                        registrar_orbital(f"X={x:.0f}, Y={y:.0f}, Z={z:.0f}")
        except Exception as e:
            print(f"❌ Error en lectura orbital: {e}")




    # Reprogramar si sigue monitoreando
    if orbital_monitoreando:
        ventana.after(100, actualizar_orbital)




def update_orbital_plot(x, y):
    """Actualiza el gráfico orbital con nuevos datos"""
    global orbit_plot, last_point_plot




    try:
        # Actualizar línea de la órbita
        orbit_plot.set_data(x_vals, y_vals)




        # Actualizar punto actual
        if last_point_plot:
            last_point_plot.remove()
        last_point_plot = ax_orbital.scatter([x], [y], color='red', s=50, label='Posición Actual', zorder=5)




        # Ajustar límites si es necesario
        ax_orbital.relim()
        ax_orbital.autoscale_view()




        # Forzar actualización
        fig_orbital.canvas.draw_idle()




    except Exception as e:
        print(f"❌ Error actualizando gráfico: {e}")




    # Programar próxima actualización si sigue monitoreando
    if orbital_monitoreando:
        ventana.after(100, actualizar_orbital)




def draw_earth_slice(z):
    """Draw the Earth's slice at a given Z coordinate"""
    slice_radius = (R_EARTH**2 - z**2)**0.5 if abs(z) <= R_EARTH else 0
    earth_slice = plt.Circle((0, 0), slice_radius, color='orange', fill=False, linestyle='--', label='Earth Slice at Z')
    return earth_slice




def abrir_orbital():
    global fig_orbital, ax_orbital, orbit_plot, last_point_plot, earth_slice, orbital_window


    orbital_window = tk.Toplevel()
    ventana_orbital = orbital_window
    ventana_orbital.title("🛰️ Monitor Orbital Satelital")
    ventana_orbital.geometry("800x800")


    ventana_orbital.attributes('-topmost', True)
    ventana_orbital.focus_force()
    ventana_orbital.grab_set()


    def quitar_topmost():
        ventana_orbital.attributes('-topmost', False)


    ventana_orbital.after(100, quitar_topmost)


    frame_botones_orbital = tk.Frame(ventana_orbital)
    frame_botones_orbital.pack(pady=10)


    boton_orbital_iniciar = tk.Button(frame_botones_orbital, text="INICIAR MONITOREO",
                                      bg="green", fg="white", width=20,
                                      command=orbital_iniciar)
    boton_orbital_detener = tk.Button(frame_botones_orbital, text="DETENER",
                                      bg="red", fg="white", width=15,
                                      command=orbital_detener)
    boton_volver_orbital = tk.Button(frame_botones_orbital, text="VOLVER AL MENÚ",
                                     bg="gray", fg="white", width=15,
                                     command=lambda: [detener_monitoreo(), mostrar("menu")])


    boton_orbital_iniciar.pack(side=tk.LEFT, padx=5)
    boton_orbital_detener.pack(side=tk.LEFT, padx=5)
    boton_volver_orbital.pack(side=tk.LEFT, padx=5)


    frame_info = tk.Frame(ventana_orbital)
    frame_info.pack(pady=5)


    label_info = tk.Label(frame_info, text="Esperando datos orbitales...",
                          font=("Arial", 11), fg="blue")
    label_info.pack()


    matplotlib.use('TkAgg')


    fig_orbital, ax_orbital = plt.subplots(figsize=(7, 7))
    canvas_orbital = FigureCanvasTkAgg(fig_orbital, master=ventana_orbital)
    canvas_orbital.get_tk_widget().pack(fill=tk.BOTH, expand=True)


    orbit_plot, = ax_orbital.plot([], [], 'bo-', label='Órbita Satelital', markersize=2)
    last_point_plot = ax_orbital.scatter([], [], color='red', s=50, label='Posición Actual')


    earth_circle = plt.Circle((0, 0), R_EARTH, color='orange', fill=False, label='Superficie Terrestre')
    ax_orbital.add_artist(earth_circle)


    ax_orbital.set_xlim(-7e6, 7e6)
    ax_orbital.set_ylim(-7e6, 7e6)
    ax_orbital.set_aspect('equal', 'box')
    ax_orbital.set_xlabel('X (metros)')
    ax_orbital.set_ylabel('Y (metros)')
    ax_orbital.set_title('Órbita Satelital Ecuatorial (Vista desde el Polo Norte)')
    ax_orbital.grid(True)
    ax_orbital.legend()


    earth_slice = draw_earth_slice(0)
    ax_orbital.add_artist(earth_slice)


    def on_close_orbital():
        global orbital_monitoreando, orbital_window
        orbital_detener()
        if orbital_window is not None:
            orbital_window.destroy()
            orbital_window = None
       
   


    ventana_orbital.protocol("WM_DELETE_WINDOW", on_close_orbital)


    actualizar_orbital()




# ---------------- Actualización general ----------------
def actualizar():
    if tiempo_inicio is not None:
        label_tiempo.config(text=f"Tiempo: {obtener_tiempo_actual():.1f} s")
    leer_datos()  # siempre, para no perder IR_...
    if tiempo_pausado:
        actualizar_datos_pausados()
    if modo_actual == "monitor":
        actualizar_graficos()
    ventana.after(1000, actualizar)




# ============================================================
# VENTANA CON Termómetro
# ============================================================
def abrir_termometro():
    ventana_gauge = tk.Toplevel()
    ventana_gauge.title("Termómetro")
    ventana_gauge.geometry("430x430")
    fig_g, ax_g = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(5, 5))
    canvas_g = FigureCanvasTkAgg(fig_g, master=ventana_gauge)
    canvas_g.get_tk_widget().pack(fill=tk.BOTH, expand=True)




    def actualizar_gauge():
        ax_g.clear()
        t_min, t_max = 0, 50
        if temperaturas:
            media = sum(temperaturas[-10:]) / min(10, len(temperaturas))
        else:
            media = 0
        ang = np.interp(media, [t_min, t_max], [0, np.pi])
        if media <= 15:
            color = "cyan"
        elif media <= 25:
            color = "green"
        elif media <= 32:
            color = "yellow"
        elif media <= 40:
            color = "orange"
        else:
            color = "red"
        ax_g.set_theta_zero_location('W')
        ax_g.set_theta_direction(-1)
        ax_g.set_thetalim(0, np.pi)
        ax_g.set_rmax(1)
        ax_g.grid(True, alpha=0.4)
        ax_g.set_yticklabels([])
        ax_g.set_xticklabels([])
        ax_g.plot([0, ang], [0, 1], color=color, linewidth=4)
        ax_g.text(
            np.pi/2, 1.2, f"{media:.1f} °C",
            ha='center', va='center', fontsize=18,
            color=color, weight='bold'
        )
        canvas_g.draw()
        ventana_gauge.after(500, actualizar_gauge)




    actualizar_gauge()




# ============================================================
# SISTEMA DE OBSERVACIONES Y EVENTOS
# ============================================================
def abrir_observaciones():
    """Ventana para agregar observaciones"""
    ventana_obs = tk.Toplevel()
    ventana_obs.title("Agregar Observación")
    ventana_obs.geometry("500x300")
    ventana_obs.configure(bg="#2c3e50")




    tk.Label(
        ventana_obs, text="📝 AGREGAR OBSERVACIÓN",
        font=("Arial", 16, "bold"), bg="#2c3e50", fg="white"
    ).pack(pady=15)




    tk.Label(
        ventana_obs, text="Escribe tu observación:",
        font=("Arial", 12), bg="#2c3e50", fg="white"
    ).pack(pady=5)




    texto_obs = tk.Text(ventana_obs, height=8, width=50, font=("Arial", 11))
    texto_obs.pack(pady=10, padx=20)




    def guardar_observacion():
        observacion = texto_obs.get("1.0", tk.END).strip()
        if observacion:
            registrar_observacion(observacion)
            texto_obs.delete("1.0", tk.END)
            messagebox.showinfo("Éxito", "✅ Observación registrada correctamente")
            ventana_obs.destroy()
        else:
            messagebox.showwarning("Advertencia", "⚠️ Escribe una observación antes de guardar")




    frame_botones = tk.Frame(ventana_obs, bg="#2c3e50")
    frame_botones.pack(pady=10)




    tk.Button(
        frame_botones, text="💾 GUARDAR", font=("Arial", 12),
        bg="#27ae60", fg="white", command=guardar_observacion
    ).pack(side=tk.LEFT, padx=10)




    tk.Button(
        frame_botones, text="❌ CANCELAR", font=("Arial", 12),
        bg="#e74c3c", fg="white", command=ventana_obs.destroy
    ).pack(side=tk.LEFT, padx=10)




def abrir_consulta_eventos():
    """Ventana para consultar eventos registrados"""
    ventana_consulta = tk.Toplevel()
    ventana_consulta.title("Consulta de Eventos")
    ventana_consulta.geometry("800x600")
    ventana_consulta.configure(bg="#34495e")




    tk.Label(
        ventana_consulta, text="📊 CONSULTA DE EVENTOS",
        font=("Arial", 18, "bold"), bg="#34495e", fg="white"
    ).pack(pady=20)




    frame_filtros = tk.Frame(ventana_consulta, bg="#34495e")
    frame_filtros.pack(pady=10)




    tk.Label(
        frame_filtros, text="Fecha:",
        font=("Arial", 11), bg="#34495e", fg="white"
    ).pack(side=tk.LEFT, padx=5)




    entry_fecha = tk.Entry(frame_filtros, font=("Arial", 11), width=12)
    entry_fecha.insert(0, date.today().strftime("%Y-%m-%d"))
    entry_fecha.pack(side=tk.LEFT, padx=5)




    tk.Label(
        frame_filtros, text="Tipo:",
        font=("Arial", 11), bg="#34495e", fg="white"
    ).pack(side=tk.LEFT, padx=5)




    combo_tipo = tk.StringVar(value="TODOS")
    opciones_tipo = ["TODOS", "ALARMA", "COMANDO", "OBSERVACION", "ORBITAL"]
    menu_tipo = tk.OptionMenu(frame_filtros, combo_tipo, *opciones_tipo)
    menu_tipo.config(font=("Arial", 10))
    menu_tipo.pack(side=tk.LEFT, padx=5)




    frame_texto = tk.Frame(ventana_consulta)
    frame_texto.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)




    texto_eventos = tk.Text(frame_texto, height=20, width=80, font=("Consolas", 10))
    scrollbar = tk.Scrollbar(frame_texto, command=texto_eventos.yview)
    texto_eventos.configure(yscrollcommand=scrollbar.set)




    texto_eventos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)




    def cargar_eventos_filtrados():
        fecha_filtro = entry_fecha.get()
        tipo_filtro = combo_tipo.get()




        eventos = cargar_eventos()
        texto_eventos.delete("1.0", tk.END)




        eventos_filtrados = []
        for evento in eventos:
            if fecha_filtro and evento["fecha"] != fecha_filtro:
                continue
            if tipo_filtro != "TODOS" and evento["tipo"] != tipo_filtro:
                continue
            eventos_filtrados.append(evento)




        if not eventos_filtrados:
            texto_eventos.insert(tk.END, "No se encontraron eventos con los filtros aplicados.")
            return




        for evento in eventos_filtrados:
            texto_eventos.insert(
                tk.END,
                f"[{evento['fecha']} {evento['hora']}] {evento['tipo']}:\n"
                f"   {evento['descripcion']}\n"
                f"{'-'*60}\n"
            )




    def exportar_eventos():
        eventos = cargar_eventos()
        if not eventos:
            messagebox.showwarning("Advertencia", "No hay eventos para exportar")
            return




        archivo_export = f"eventos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(archivo_export, 'w', encoding='utf-8') as f:
            f.write("EVENTOS REGISTRADOS - SISTEMA ARDUINO TIERRA\n")
            f.write("=" * 50 + "\n\n")
            for evento in eventos:
                f.write(f"[{evento['fecha']} {evento['hora']}] {evento['tipo']}:\n")
                f.write(f"   {evento['descripcion']}\n")
                f.write("-" * 50 + "\n")




        messagebox.showinfo("Éxito", f"✅ Eventos exportados a: {archivo_export}")




    frame_botones = tk.Frame(ventana_consulta, bg="#34495e")
    frame_botones.pack(pady=15)




    tk.Button(
        frame_botones, text="🔍 CONSULTAR", font=("Arial", 12),
        bg="#3498db", fg="white", command=cargar_eventos_filtrados
    ).pack(side=tk.LEFT, padx=10)




    tk.Button(
        frame_botones, text="📄 EXPORTAR", font=("Arial", 12),
        bg="#9b59b6", fg="white", command=exportar_eventos
    ).pack(side=tk.LEFT, padx=10)




    tk.Button(
        frame_botones, text="🗑️ LIMPIAR REGISTROS", font=("Arial", 12),
        bg="#e74c3c", fg="white",
        command=lambda: [guardar_eventos([]), cargar_eventos_filtrados()]
    ).pack(side=tk.LEFT, padx=10)




    tk.Button(
        frame_botones, text="❌ CERRAR", font=("Arial", 12),
        bg="#7f8c8d", fg="white", command=ventana_consulta.destroy
    ).pack(side=tk.LEFT, padx=10)




    cargar_eventos_filtrados()




# ============================================================
#  SISTEMA DE LOGIN / REGISTRO
# ============================================================
ARCHIVO_USUARIOS = "usuarios.json"
USUARIO_ACTUAL = None
intentos_fallidos = 0
bloqueado_hasta = None  # timestamp hasta el que está bloqueado




def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()  # hash SHA-256 sencillo.[web:24][web:30]




def cargar_usuarios():
    if os.path.exists(ARCHIVO_USUARIOS):
        try:
            with open(ARCHIVO_USUARIOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []




def guardar_usuarios(usuarios):
    with open(ARCHIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)




def registrar_usuario(entry_email, entry_usuario, entry_pass, entry_fecha, entry_lugar, label_info):
    email = entry_email.get().strip()
    usuario = entry_usuario.get().strip()
    pwd = entry_pass.get().strip()
    fecha_nac = entry_fecha.get().strip()
    lugar = entry_lugar.get().strip()




    if not (email and usuario and pwd and fecha_nac and lugar):
        label_info.config(text="Todos los campos son obligatorios.", fg="#ff5555")
        return




    usuarios = cargar_usuarios()
    for u in usuarios:
        if u["usuario"].lower() == usuario.lower():
            label_info.config(text="Usuario ya existente.", fg="#ff5555")
            return




    nuevo = {
        "email": email,
        "usuario": usuario,
        "password_hash": hash_password(pwd),
        "fecha_nacimiento": fecha_nac,
        "lugar_residencia": lugar
    }
    usuarios.append(nuevo)
    guardar_usuarios(usuarios)
    label_info.config(text="Cuenta creada correctamente.", fg="#00ff00")




    entry_email.delete(0, tk.END)
    entry_usuario.delete(0, tk.END)
    entry_pass.delete(0, tk.END)
    entry_fecha.delete(0, tk.END)
    entry_lugar.delete(0, tk.END)




def intentar_login(login_win, entry_usuario, entry_pass, label_info):
    global intentos_fallidos, bloqueado_hasta, USUARIO_ACTUAL




    ahora = time.time()
    if bloqueado_hasta and ahora < bloqueado_hasta:
        restantes = int(bloqueado_hasta - ahora)
        label_info.config(text=f"Acceso bloqueado {restantes} s.", fg="#ff5555")
        return




    usuario = entry_usuario.get().strip()
    pwd = entry_pass.get().strip()




    if not (usuario and pwd):
        label_info.config(text="Introduce usuario y contraseña.", fg="#ff5555")
        return




    usuarios = cargar_usuarios()
    encontrado = None
    for u in usuarios:
        if u["usuario"].lower() == usuario.lower():
            encontrado = u
            break




    if not encontrado:
        intentos_fallidos += 1
        label_info.config(text="Credenciales incorrectas.", fg="#ff5555")
    else:
        if hash_password(pwd) == encontrado["password_hash"]:
            intentos_fallidos = 0
            bloqueado_hasta = None
            USUARIO_ACTUAL = usuario
            label_info.config(text="Acceso concedido. Abriendo sistema...", fg="#00ff00")
            login_win.destroy()
            lanzar_app_principal()
            return
        else:
            intentos_fallidos += 1
            label_info.config(text="Credenciales incorrectas.", fg="#ff5555")




    if intentos_fallidos >= 3:
        bloqueado_hasta = time.time() + 60
        intentos_fallidos = 0
        label_info.config(text="Demasiados intentos. Bloqueo 60 s.", fg="#ff5555")




def mostrar_login():
    login_win = tk.Tk()
    login_win.title("ACCESS CONTROL CENTER")
    login_win.geometry("500x420")
    login_win.configure(bg="#020814")




    titulo = tk.Label(
        login_win,
        text="NASA SECURE GATEWAY",
        font=("Consolas", 20, "bold"),
        bg="#020814",
        fg="#00ffff"
    )
    titulo.pack(pady=20)




    subtitulo = tk.Label(
        login_win,
        text="USER AUTHENTICATION REQUIRED",
        font=("Consolas", 11),
        bg="#020814",
        fg="#00bfff"
    )
    subtitulo.pack()




    marco = tk.Frame(login_win, bg="#050b1e", bd=2, relief="ridge")
    marco.pack(pady=15, padx=20, fill="both", expand=True)




    modo = tk.StringVar(value="login")




    frame_tabs = tk.Frame(marco, bg="#050b1e")
    frame_tabs.pack(pady=5)




    frame_form = tk.Frame(marco, bg="#050b1e")
    frame_form.pack(pady=10, padx=10, fill="both", expand=True)




    label_info = tk.Label(frame_form, text="", font=("Consolas", 10), bg="#050b1e", fg="#ff5555")
    label_info.pack(side=tk.BOTTOM, pady=5)




    def actualizar_formulario():
        # Eliminar todos los widgets menos label_info
        for w in frame_form.winfo_children():
            if w is not label_info:
                w.destroy()




        if modo.get() == "login":
            # Crear entradas NUEVAS para login
            entry_usuario = tk.Entry(frame_form, font=("Consolas", 11),
                                     bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
            entry_pass = tk.Entry(frame_form, show="*", font=("Consolas", 11),
                                  bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")




            tk.Label(
                frame_form, text="USER ID",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=5)
            entry_usuario.pack(pady=5, fill="x")




            tk.Label(
                frame_form, text="ACCESS KEY",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=5)
            entry_pass.pack(pady=5, fill="x")




            tk.Button(
                frame_form, text="ENTER ORBIT",
                font=("Consolas", 11, "bold"),
                bg="#00ffff", fg="#000000",
                activebackground="#00bfff",
                command=lambda: intentar_login(login_win, entry_usuario, entry_pass, label_info)
            ).pack(pady=15)




        else:
            # Crear entradas NUEVAS para registro
            entry_email = tk.Entry(frame_form, font=("Consolas", 11),
                                   bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
            entry_usuario = tk.Entry(frame_form, font=("Consolas", 11),
                                     bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
            entry_pass = tk.Entry(frame_form, show="*", font=("Consolas", 11),
                                  bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
            entry_fecha = tk.Entry(frame_form, font=("Consolas", 11),
                                   bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
            entry_lugar = tk.Entry(frame_form, font=("Consolas", 11),
                                   bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")




            tk.Label(
                frame_form, text="E-MAIL",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_email.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="USERNAME",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_usuario.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="PASSWORD",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_pass.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="BIRTHDATE (YYYY-MM-DD)",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_fecha.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="RESIDENCE",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_lugar.pack(pady=3, fill="x")




            tk.Button(
                frame_form, text="CREATE ACCOUNT",
                font=("Consolas", 11, "bold"),
                bg="#00ffff", fg="#000000",
                activebackground="#00bfff",
                command=lambda: registrar_usuario(
                    entry_email, entry_usuario, entry_pass,
                    entry_fecha, entry_lugar, label_info
                )
            ).pack(pady=15)




        label_info.pack(side=tk.BOTTOM, pady=5)




    def cambiar_modo(nuevo):
        modo.set(nuevo)
        actualizar_formulario()




    btn_login_tab = tk.Button(
        frame_tabs, text="LOGIN", width=12,
        command=lambda: cambiar_modo("login"),
        bg="#0b1a33", fg="#00ffff", relief="flat", activebackground="#102749"
    )
    btn_reg_tab = tk.Button(
        frame_tabs, text="REGISTER", width=12,
        command=lambda: cambiar_modo("register"),
        bg="#0b1a33", fg="#00ffff", relief="flat", activebackground="#102749"
    )
    btn_login_tab.pack(side=tk.LEFT, padx=5, pady=5)
    btn_reg_tab.pack(side=tk.LEFT, padx=5, pady=5)




    actualizar_formulario()
    login_win.mainloop()








    btn_login_tab = tk.Button(
        frame_tabs, text="LOGIN", width=12,
        command=lambda: cambiar_modo("login"),
        bg="#0b1a33", fg="#00ffff", relief="flat", activebackground="#102749"
    )
    btn_reg_tab = tk.Button(
        frame_tabs, text="REGISTER", width=12,
        command=lambda: cambiar_modo("register"),
        bg="#0b1a33", fg="#00ffff", relief="flat", activebackground="#102749"
    )
    btn_login_tab.pack(side=tk.LEFT, padx=5, pady=5)
    btn_reg_tab.pack(side=tk.LEFT, padx=5, pady=5)




    frame_form = tk.Frame(marco, bg="#050b1e")
    frame_form.pack(pady=10, padx=10, fill="both", expand=True)




    entry_usuario = tk.Entry(frame_form, font=("Consolas", 11), bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
    entry_pass = tk.Entry(frame_form, show="*", font=("Consolas", 11), bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")




    entry_email = tk.Entry(frame_form, font=("Consolas", 11), bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
    entry_fecha = tk.Entry(frame_form, font=("Consolas", 11), bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")
    entry_lugar = tk.Entry(frame_form, font=("Consolas", 11), bg="#0b1a33", fg="#00ffff", insertbackground="#00ffff")




    label_info = tk.Label(frame_form, text="", font=("Consolas", 10), bg="#050b1e", fg="#ff5555")
    label_info.pack(side=tk.BOTTOM, pady=5)




    def actualizar_formulario():
        for w in frame_form.winfo_children():
            if w is not label_info:
                w.destroy()




        if modo.get() == "login":
            tk.Label(
                frame_form, text="USER ID",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=5)
            entry_usuario.pack(pady=5, fill="x")




            tk.Label(
                frame_form, text="ACCESS KEY",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=5)
            entry_pass.pack(pady=5, fill="x")




            tk.Button(
                frame_form, text="ENTER ORBIT",
                font=("Consolas", 11, "bold"),
                bg="#00ffff", fg="#000000",
                activebackground="#00bfff",
                command=lambda: intentar_login(login_win, entry_usuario, entry_pass, label_info)
            ).pack(pady=15)




        else:
            tk.Label(
                frame_form, text="E-MAIL",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_email.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="USERNAME",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_usuario.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="PASSWORD",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_pass.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="BIRTHDATE (YYYY-MM-DD)",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_fecha.pack(pady=3, fill="x")




            tk.Label(
                frame_form, text="RESIDENCE",
                font=("Consolas", 11),
                bg="#050b1e", fg="#00ffff"
            ).pack(pady=3)
            entry_lugar.pack(pady=3, fill="x")




            tk.Button(
                frame_form, text="CREATE ACCOUNT",
                font=("Consolas", 11, "bold"),
                bg="#00ffff", fg="#000000",
                activebackground="#00bfff",
                command=lambda: registrar_usuario(
                    entry_email, entry_usuario, entry_pass,
                    entry_fecha, entry_lugar, label_info
                )
            ).pack(pady=15)




        label_info.pack(side=tk.BOTTOM, pady=5)




    actualizar_formulario()
    login_win.mainloop()




# ============================================================
#  VENTANA PRINCIPAL (se lanza tras login)
# ============================================================
def lanzar_app_principal():
    global ventana
    global frame_menu, frame_monitor, frame_radar
    global boton_iniciar, boton_pausar, boton_reanudar, boton_detener
    global label_tiempo, label_temp, label_hum
    global label_media_temp, label_media_hum
    global fig, ax1, ax2, canvas
    global fig_radar, ax_radar, canvas_radar




    ventana = tk.Tk()
    ventana.title("Monitor Arduino Tierra")
    ventana.state('zoomed')
    ventana.geometry("700x650")




    frame_menu = tk.Frame(ventana, bg="#1e1e1e")
    frame_menu.pack(fill="both", expand=True)




    tk.Label(
        frame_menu, text="🌍 MENÚ PRINCIPAL",
        font=("Arial", 18, "bold"), bg="#1e1e1e", fg="white"
    ).pack(pady=30)




    tk.Button(
        frame_menu, text="A - Temperatura y Humedad",
        font=("Arial", 14), width=25, bg="#2e8b57", fg="white",
        command=lambda: mostrar("monitor")
    ).pack(pady=8)




    tk.Button(
        frame_menu, text="B - Radar de distancias",
        font=("Arial", 14), width=25, bg="#2e8b57", fg="white",
        command=lambda: mostrar("radar")
    ).pack(pady=8)




    tk.Button(
        frame_menu, text="C - Agregar Observación",
        font=("Arial", 14), width=25, bg="#2e8b57", fg="white",
        command=abrir_observaciones
    ).pack(pady=8)




    tk.Button(
        frame_menu, text="D - Consultar Eventos",
        font=("Arial", 14), width=25, bg="#2e8b57", fg="white",
        command=abrir_consulta_eventos
    ).pack(pady=8)




    tk.Button(
        frame_menu, text="E - Monitor Orbital",
        font=("Arial", 14), width=25, bg="#2e8b57", fg="white",
        command=abrir_orbital
    ).pack(pady=8)




    frame_monitor = tk.Frame(ventana)
    frame_botones = tk.Frame(frame_monitor)
    frame_botones.pack(pady=10)




    boton_iniciar = tk.Button(
        frame_botones, text="INICIAR",
        bg="green", fg="white", width=8,
        command=iniciar_monitoreo
    )
    boton_pausar = tk.Button(
        frame_botones, text="PAUSAR",
        bg="orange", fg="white", width=8,
        command=pausar_monitoreo, state='disabled'
    )
    boton_reanudar = tk.Button(
        frame_botones, text="REANUDAR",
        bg="blue", fg="white", width=8,
        command=reanudar_monitoreo, state='disabled'
    )
    boton_detener = tk.Button(
        frame_botones, text="DETENER",
        bg="red", fg="white", width=8,
        command=detener_monitoreo, state='disabled'
    )
    boton_volver = tk.Button(
        frame_botones, text="VOLVER",
        bg="gray", fg="white", width=8,
        command=lambda: mostrar("menu")
    )




    for b in (boton_iniciar, boton_pausar, boton_reanudar, boton_detener, boton_volver):
        b.pack(side=tk.LEFT, padx=3)




    frame_datos = tk.Frame(frame_monitor)
    frame_datos.pack(pady=5)
    label_tiempo = tk.Label(frame_datos, text="Tiempo: 0.0 s", font=("Arial", 12), fg="green")
    label_temp = tk.Label(frame_datos, text="Temp: --.- °C", font=("Arial", 12), fg="red")
    label_hum = tk.Label(frame_datos, text="Hum: --.- %", font=("Arial", 12), fg="blue")
    for lbl in (label_tiempo, label_temp, label_hum):
        lbl.pack(side=tk.LEFT, padx=10)




    frame_medias = tk.Frame(frame_monitor)
    frame_medias.pack(pady=5)
    label_media_temp = tk.Label(
        frame_medias, text="Media 10 últimas Temp: -- °C",
        font=("Arial", 11), fg="darkred"
    )
    label_media_hum = tk.Label(
        frame_medias, text="Media 10 últimas Hum: -- %",
        font=("Arial", 11), fg="darkblue"
    )
    label_media_temp.pack(side=tk.LEFT, padx=15)
    label_media_hum.pack(side=tk.LEFT, padx=15)




    boton_termometro = tk.Button(
        frame_monitor, text="Ver termómetro",
        font=("Arial", 12), bg="#444", fg="white",
        command=abrir_termometro
    )
    boton_termometro.pack(pady=5)




    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6))
    canvas = FigureCanvasTkAgg(fig, master=frame_monitor)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    fig.tight_layout()




    frame_radar = tk.Frame(ventana)
    frame_botones_radar = tk.Frame(frame_radar)
    frame_botones_radar.pack(pady=10)
    boton_radar_iniciar = tk.Button(
        frame_botones_radar, text="INICIAR/REANUDAR",
        bg="green", fg="white", width=15,
        command=radar_iniciar
    )
    boton_radar_detener = tk.Button(
        frame_botones_radar, text="DETENER",
        bg="red", fg="white", width=15,
        command=radar_detener
    )
    boton_volver_radar = tk.Button(
        frame_botones_radar, text="VOLVER",
        bg="gray", fg="white", width=8,
        command=lambda: [radar_detener(), mostrar("menu")]
    )
    boton_radar_iniciar.pack(side=tk.LEFT, padx=5)
    boton_radar_detener.pack(side=tk.LEFT, padx=5)
    boton_volver_radar.pack(side=tk.LEFT, padx=5)




    fig_radar, ax_radar = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(6, 6))
    canvas_radar = FigureCanvasTkAgg(fig_radar, master=frame_radar)
    canvas_radar.get_tk_widget().pack(fill=tk.BOTH, expand=True)




    def mostrar(modo):
        global modo_actual
        modo_actual = modo
        frame_menu.pack_forget()
        frame_monitor.pack_forget()
        frame_radar.pack_forget()
        if modo == "menu":
            frame_menu.pack(fill="both", expand=True)
        elif modo == "monitor":
            frame_monitor.pack(fill="both", expand=True)
            actualizar_graficos()
        elif modo == "radar":
            frame_radar.pack(fill="both", expand=True)
            if not radar_monitoreando:
                radar_iniciar()
            actualizar_radar()




    globals()['mostrar'] = mostrar




    def on_closing():
        if arduino and arduino.is_open:
            if radar_monitoreando:
                radar_detener()
            if orbital_monitoreando:
                orbital_detener()
            arduino.close()
        ventana.destroy()




    ventana.protocol("WM_DELETE_WINDOW", on_closing)
    actualizar()
    mostrar("menu")
    ventana.mainloop()




# ---------------- Punto de entrada ----------------
if __name__ == "__main__":
    mostrar_login()









