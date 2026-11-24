# Interfaz V1.4

import tkinter as tk
import threading
import serial
import serial.tools.list_ports
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import qrcode
from PIL import ImageTk
from datetime import datetime
import os
import time
import webbrowser
import numpy as np
import statistics
#from scipy.signal import savitzky_golay
from scipy.signal import savgol_filter

# ======================================================================================== ventana principal

root = tk.Tk()
root.title("OPNSpec V1.3")
root.geometry("1116x690")
root.minsize(650, 625)
root.configure(bg="#333333")

# ======================================================================================== icono de aplicación

try:
    root.iconphoto(False, tk.PhotoImage(file="Quiah.ico"))
except Exception:
    pass

# ======================================================================================== variables globales

ser = None
grabando = False
datos_x = []
datos_y = []
archivo_actual = None
datos_x_orig = []
datos_y_orig = []
curvas_cargadas = []
PALETA = ["#e74c3c", "#3498db", "#9b59b6", "#f39c12", "#1abc9c", "#e67e22", "#2ecc71"]
filtros = ["Ninguno", "Mediana", "Media", "Mínimos", "Máximos", "Volatilidad", "Suma móvil", "Savitzky-Golay"]
curvas_suavizadas = []
ventana_var = tk.IntVar(value=5)   # antes de crear el slider
orden_var   = tk.IntVar(value=2)
tamano_fuente_comentarios = 8
tipo_grafico = "line" 
tipos_grafico = [
    ("Línea", "line"),
    ("Dispersión", "scatter"),
    ("Escalones", "step"),
    ("Barras", "bar"),
    ("Área rellena", "fill"),
    ("Línea + marcadores", "line_markers"),
    ("Histograma", "hist"),  # 👈 NUEVO
]

# ======================================================================================== conección serial

def list_ports():
    puertos = [p.device for p in serial.tools.list_ports.comports()]
    combo_puertos["values"] = puertos
    if puertos:
        combo_puertos.current(0)
    else:
        combo_puertos.set("Conecte ESP32")

def conectar():
    casilla_comentarios.insert(tk.END, "# Conectado" + " " + datetime.now().strftime('%Y_%m_%d-%H_%M_%S') + "\n")
    global ser
    puerto = combo_puertos.get()
    if not puerto:
        messagebox.showwarning("Aviso", "Selecciona un puerto.")
        return
    try:
        ser = serial.Serial(puerto, 115200, timeout=1)
        ser.dtr = True
        ser.rts = True
        ser.reset_input_buffer()

        lbl_estado.config(text=f" 📡 Conectado a {puerto}", foreground="green", font=("Arial", 11, "bold") )
        btn_conectar.config(state="disabled")
        btn_desconectar.config(state="normal")
        btn_play.config(state="normal")

        threading.Thread(target=leer_serial, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo conectar:\n{e}")

def leer_serial():
    global ser
    while ser and ser.is_open:
        try:
            if ser.in_waiting:
                linea = ser.readline().decode(errors="ignore").strip()
                if linea:
                    root.after(0, procesar_linea, linea)
        except serial.SerialException as e:
            print("Desconexión detectada:", e)
            root.after(0, desconexion_detectada)
            break
        except Exception as e:
            print("Error lectura:", e)
            break

def desconectar():
    casilla_comentarios.insert(tk.END, "# Desconectado" + " " + datetime.now().strftime('%Y_%m_%d-%H_%M_%S') + "\n")
    global ser, grabando
    if grabando:
        toggle_grabacion()
    else:
        pass
    if ser and ser.is_open:
        ser.close()
    grabando = False
    ser = None
    lbl_estado.config(text=" 🛸 Desconectado", foreground="red", font=("Arial", 11 , "bold"))
    btn_conectar.config(state="normal")
    btn_desconectar.config(state="disabled")
    btn_play.config(text="▶ Play", bg="#2ecc71", activebackground="#27ae60", state="disabled")
    btn_play.config(state="disabled")

def desconexion_detectada():
    global ser, grabando, led_encendido
    if ser:
        try:
            ser.close()
        except Exception:
            pass
    ser = None
    grabando = False
    led_encendido = False    
    lbl_estado.config(text=" Desconectado (USB)", foreground="red")
    btn_conectar.config(state="normal")
    btn_desconectar.config(state="disabled")
    btn_play.config(state="disabled", text="▶ Iniciar", bg="#2ecc71")

# ======================================================================================== Obtención de datos

def toggle_grabacion():
    global grabando
    if ser is None or not ser.is_open:
        messagebox.showwarning("Aviso", "Conecta ESP32.")
        return
    grabando = not grabando
    if grabando:
        try:
            intervalo = int(spin_intervalo.get())
            if intervalo < 1 or intervalo > 600000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Intervalo = [1,600000]")
            grabando = False
            return
    if grabando:
        try:
            prom = int(spin_prom.get())
            if prom < 1 or prom > 1000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Observaciones = [1,1000]")
            grabando = False
            return
    if grabando:
        try:
            prtadc = int(spin_portadc.get())
            if prtadc < 32 or prtadc > 39:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "ADC = [32,39]")
            grabando = False
            return
    if grabando:
        try:
            prtdac = int(spin_portdac.get())
            if prtdac < 25 or prtdac > 26:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "DAC = [25,26]")
            grabando = False
            return
    if grabando:
        try:
            potdac = int(spin_powdac.get())
            if potdac < 0 or potdac > 255:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Pot.DAC = [0,255]")
            grabando = False
            return
        datos_x, datos_y = [], []
        replot()
        sndcmd(f"INTERVAL:{intervalo}")
        sndcmd(f"PROMEDIO:{prom}")
        sndcmd(f"PINADC:{prtadc}")
        sndcmd(f"PINDAC:{prtdac}")
        sndcmd(f"VOLDAC:{potdac}")
        sndcmd("START")
        btn_play.config(text="⏹ Alto", bg="#d74c3c", activebackground="#c0392b" )
    else:
        sndcmd("STOP")
        btn_play.config(text="▶ Play", bg="#2ecc71", activebackground="#27ae60" )

def sndcmd(cmd):                                                                                                             # send command
    global ser
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\n").encode())
            print("→ ESP32:", cmd)
        except Exception as e:
            print("Error enviando comando:", e)
    else:
        messagebox.showwarning("Error", "Conecte ESP32.")

def procesar_linea(linea):
    if linea.startswith("#"):
        if   "tem" in linea:
            casilla_comentarios.insert(tk.END, linea + "\n")
        elif "pem" in linea:
            casilla_comentarios.insert(tk.END, linea + "\n")
        elif "padc" in linea:
            casilla_comentarios.insert(tk.END, linea + "\n")
        elif "pdac" in linea:
            casilla_comentarios.insert(tk.END, linea + "\n")
        elif "potdac" in linea:
            casilla_comentarios.insert(tk.END, linea + "\n")
        else:
            casilla_comentarios.insert(tk.END, linea + " " + datetime.now().strftime('%Y_%m_%d-%H_%M_%S') + "\n")
            casilla_comentarios.see(tk.END)
        return
    try:
        partes = linea.replace(";", ",").split(",")
        x = float(partes[0])
        y = float(partes[1])
    except (ValueError, IndexError):
        return
    datos_x.append(x)
    datos_y.append(y)
    casilla_datos.insert(tk.END, f"{x:8.3f}   {y:8.3f}\n")
    casilla_datos.see(tk.END)
    replot()

# ======================================================================================== donar

def mostrar_qr(contenido, titulo="Código QR"):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4, )
    qr.add_data(contenido)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").resize((300, 300))

    # Ventana emergente
    windoge = tk.Toplevel(root)
    try:
        windoge.iconphoto(False, tk.PhotoImage(file="Doge.png"))
    except Exception:
        pass

    windoge.title(titulo)
    windoge.resizable(False, False)
    windoge.configure(bg="white")
    windoge.transient(root)
    windoge.grab_set()
    
    # Mostrar imagen
    photo = ImageTk.PhotoImage(img)
    lbl_img = tk.Label(windoge, image=photo, bg="white")
    lbl_img.image = photo
    lbl_img.pack(padx=20, pady=(20, 10))

    # Texto del contenido (seleccionable)
    lbl_contenido = tk.Label(windoge, text=contenido, bg="white", fg="#333", font=("Courier", 10), wraplength=280, justify="center")
    lbl_contenido.pack(padx=20, pady=(0, 5))

    # Botón para copiar al portapapeles
    btn_copiar = tk.Button(windoge, text="📋 Copiar dirección DOGE", font=("Arial", 10, "bold"), bg="#bb9840", fg="white",
                           command=lambda: copiar_al_portapapeles(contenido, btn_copiar))
    btn_copiar.pack(pady=5, padx=20, fill="x")
    
    btn_APTC = tk.Button(windoge, text="Arduino Para el Trabajo Científico", font=("Arial", 10, "bold"), bg="#356565", fg="white",
                           command=lambda: web_APTC())
    btn_APTC.pack(pady=5, padx=20, fill="x")
    
    btn_TeX = tk.Button(windoge, text="El LaTeXnomicón", font=("Arial", 10, "bold"), bg="#000000", fg="white", command=lambda: web_TeX())
    btn_TeX.pack(pady=5, padx=20, fill="x")

    btn_python = tk.Button(windoge, text="Python_0", font=("Arial", 10, "bold"), bg="#000000", fg="white", command=lambda: web_python())
    btn_python.pack(pady=5, padx=20, fill="x")

    # Botón cerrar
    tk.Button(windoge, text="Cerrar", command=windoge.destroy, font=("Arial", 10, "bold")).pack(pady=(5, 15), padx=20, fill="x")

def copiar_al_portapapeles(texto, boton):
    root.clipboard_clear()
    root.clipboard_append(texto)
    texto_original = boton.cget("text")
    boton.config(text=" ¡ Gracias por tu apoyo, eres lo máximo ! ", bg="#2ecc71")

def web_APTC():
    webbrowser.open("https://www.amazon.com.mx/dp/B0GJG5RVNJ")
def web_TeX():
    webbrowser.open("https://www.amazon.com.mx/dp/B0GJLMB43C")
def web_python():
    webbrowser.open("https://www.amazon.com.mx/dp/B0HKYZQWF7")
def down_driver():
    webbrowser.open("https://www.pololu.com/docs/0j7/all")

# ======================================================================================== guardar datos

def cmd_guardar():
    comentarios = casilla_comentarios.get("1.0", tk.END).strip()
    datos_dat = casilla_datos.get("1.0", tk.END).strip()
    if not datos_dat:
        messagebox.showwarning("Aviso", "No hay datos para guardar.")
        return
    ruta = filedialog.asksaveasfilename(
        defaultextension=".dat",
        filetypes=[("Archivo de texto", "*.dat"), ("Todos", "*.*")],
        initialfile=f"{datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}.dat"
    )
    if not ruta:
        return
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("# 🎁🎁🎁🎁\n#    OPNSpec   \n# 🚀🚀🚀🚀\n")
            f.write(f"#📅 {datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}\n")
            f.write("# -------------------------------------------\n")
            if comentarios:
                for linea in comentarios.splitlines():
                    f.write(f"# {linea}\n")
            else:
                f.write("# (sin comentarios)\n")
            f.write("# -------------------------------------------\n")
            f.write("# Tiempo(s)    Voltaje(V)\n")
            f.write(datos_dat + "\n")
        messagebox.showinfo("Éxito", f"Archivo guardado en:\n{ruta}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

def cmd_abrir_espectro():
    global archivo_actual, datos_x_orig, datos_y_orig
    ruta = filedialog.askopenfilename(filetypes=[("Archivo de texto", "*.dat"), ("Todos", "*.*")])
    if not ruta:
        return
    try:
        comentarios, datos = leer_espectro(ruta)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}")
        return
    if not datos:
        messagebox.showwarning("Aviso", "El archivo no contiene datos numéricos.")
        return
    nombre = os.path.basename(ruta)
    archivo_actual = {"nombre": nombre, "ruta": ruta, "comentarios": comentarios, "x": [p[0] for p in datos], "y": [p[1] for p in datos]}
    datos_x_orig = [p[0] for p in datos]
    datos_y_orig = [p[1] for p in datos]
    casilla_comentarios.delete("1.0", tk.END)
    casilla_datos.delete("1.0", tk.END)
    for x, y in datos:
        casilla_datos.insert(tk.END, f"{x:8.3f}   {y:8.4f}\n")
    casilla_comentarios.insert(tk.END, f"\n# 🪃 {nombre} \n")
    for c in comentarios:
        casilla_comentarios.insert(tk.END, f"# {c}\n")
    casilla_comentarios.see(tk.END)
    graficar_espectro_cargado()
    lbl_archivo_actual.config(text= nombre, font=("Arial",8))
    messagebox.showinfo("Éxito", f"Archivo '{nombre}' cargado.")

def leer_espectro(ruta):
    comentarios = []
    datos = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            if linea.startswith("#"):
                comentarios.append(linea.lstrip("# ").rstrip())
                continue
            try:
                #split() #sin argumentos divide por cualquier espacio en blanco
                partes = linea.split()
                if len(partes) >= 2:
                    x = float(partes[0])
                    y = float(partes[1])
                    datos.append((x, y))
            except (ValueError, IndexError):
                continue
    return comentarios, datos

def graficar_espectro_cargado():
    if archivo_actual is None:
        messagebox.showwarning("Aviso", "Abre un archivo.")
        return
    if any(c["nombre"] == archivo_actual["nombre"] for c in curvas_cargadas):
        messagebox.showinfo("Aviso", f"'{archivo_actual['nombre']}' ya está graficado.")
        return
    color = PALETA[len(curvas_cargadas) % len(PALETA)]
    curvas_cargadas.append({"nombre": archivo_actual["nombre"], "x": archivo_actual["x"], "y": archivo_actual["y"], "color": color})
    replot()

# ======================================================================================== replot

def replot():
    ax.clear()

    def plot_data(x, y, color, label, linewidth=1.5, linestyle="-", alpha=0.75):
        if tipo_grafico == "line":
            ax.plot(x, y, color=color, linewidth=linewidth, linestyle=linestyle, alpha=alpha, label=label)
        elif tipo_grafico == "scatter":
            ax.scatter(x, y, color=color, s=10, alpha=alpha, label=label)
        elif tipo_grafico == "step":
            ax.step(x, y, color=color, linewidth=linewidth, where='post', alpha=alpha, label=label)
        elif tipo_grafico == "bar":
            if len(x) > 100:
                step = len(x) // 100
                x_plot, y_plot = x[::step], y[::step]
            else:
                x_plot, y_plot = x, y
            width = (x_plot[1] - x_plot[0]) * 0.8 if len(x_plot) > 1 else 0.1
            ax.bar(x_plot, y_plot, width=width, color=color, alpha=alpha, label=label)
        elif tipo_grafico == "fill":
            ax.fill_between(x, y, color=color, alpha=0.3, label=label)
            ax.plot(x, y, color=color, linewidth=linewidth, linestyle=linestyle, alpha=alpha)
        elif tipo_grafico == "line_markers":
            ax.plot(x, y, color=color, linewidth=linewidth, linestyle=linestyle, alpha=alpha, marker='o', markersize=3, label=label)
        elif tipo_grafico == "hist":
            ax.hist(y, bins=25, color=color, alpha=alpha, edgecolor='gray', linewidth=0.5, label=label)

    if datos_x and datos_y:
        plot_data(datos_x, datos_y, "#2ecc71", "raw", linewidth=1.5, alpha=0.75)

    for c in curvas_cargadas:
        plot_data(c["x"], c["y"], c["color"], c["nombre"], linewidth=2, alpha=0.75)

    for c in curvas_suavizadas:
        plot_data(c["x"], c["y"], c["color"], c["nombre"], linewidth=1.0, linestyle="--", alpha=0.5)

    if tipo_grafico == "hist":
        ax.set_xlabel("Voltaje (V)")
        ax.set_ylabel("Frecuencia")
        ax.set_title("Distribución")
    else:
        ax.set_xlabel("Tiempo (s)")
        ax.set_ylabel("Voltaje (V)")
        ax.set_title("Observaciones")

    ax.grid(True, linestyle="--", alpha=0.5)

    if datos_x or curvas_cargadas or curvas_suavizadas:
        ax.legend(loc="upper left", fontsize=7)

    canvas.draw_idle()

# ======================================================================================== limpiar

def cmd_limpiar():
    global datos_x, datos_y, datos_x_orig, datos_y_orig, curvas_cargadas, archivo_actual, curvas_suavizadas    
    hay_datos = (datos_x or datos_y or curvas_cargadas or curvas_suavizadas or archivo_actual)
    if hay_datos:
        confirmar = messagebox.askyesno("Limpiar", "¿Estás seguro de que quieres limpiar todo?\n\n",
            icon=messagebox.WARNING, default=messagebox.NO)
        if not confirmar:
            return  # Usuario canceló
    datos_x, datos_y = [], []
    archivo_actual = None
    lbl_archivo_actual.config(text=" 📂 ", font=("Arial", 10, "bold"))
    datos_x_orig, datos_y_orig = [], []
    curvas_cargadas = []
    filtro = ["Ninguno"]    
    curvas_suavizadas = []
    casilla_comentarios.delete("1.0", tk.END)
    casilla_datos.delete("1.0", tk.END)
    tipo_grafico = "line"
    replot()

# ======================================================================================== funciones filtros

def aplicarplot():
    nombre = combo_tiplot.get()
    mapa = dict(tipos_grafico)          # {"Línea": "line", ...}
    tipo = mapa.get(nombre)
    if tipo is None:
        messagebox.showinfo("Aviso", "Selecciona un tipo de gráfico.")
        return
    cambiar_tipo_grafico(tipo)

def cambiar_tipo_grafico(tipo):
    global tipo_grafico
    tipo_grafico = tipo
    # Sincroniza el combobox con el nombre legible
    for nombre, clave in tipos_grafico:
        if clave == tipo:
            combo_tiplot.set(nombre)
            break
    replot()

def rolling(datos, w, funcs):
    """Aplica una función de ventana deslizante sobre los datos."""
    n = len(datos)
    mitad = w // 2
    salida = []
    for i in range(n):
        ini = max(0, i - mitad)
        fin = min(n, i + mitad + 1)
        ventana_actual = datos[ini:fin]
        salida.append(funcs(ventana_actual))
    return salida

def aplicar():
    filtro = combo_filtros.get()
    if filtro == "Ninguno":
        messagebox.showinfo("Aviso", "Selecciona un filtro.")
        return 
    if not datos_x_orig or not datos_y_orig:
        messagebox.showwarning("Aviso", "Para filtrar, guarda tus datos. Después abre el archivo.")
        return

    y_array = np.array(datos_y_orig, dtype=float)
    if len(y_array) < 10:
        messagebox.showwarning("Aviso", "Se necesitan al menos 10 puntos de datos.")
        return

    w = ventana_var.get()      # 👈 lee el slider de ventana
    o = orden_var.get()        # 👈 lee el slider de orden

    # Savitzky-Golay exige ventana impar y > orden
    if filtro == "Savitzky-Golay":
        w_sg = w if w % 2 == 1 else w + 1
        if w_sg <= o:
            w_sg = o + 2 if (o + 2) % 2 == 1 else o + 3
        try:
            y_suavizado = savgol_filter(y_array, w_sg, o)
            params = {"window": w_sg, "order": o}
        except Exception as e:
            messagebox.showerror("Error", f"Savitzky-Golay falló:\n{e}")
            return
        nombre = f"SG (w={w_sg}, o={o})"

    elif filtro == "Mediana":
        y_suavizado = rolling(datos_y_orig, w, statistics.median)
        params = {"window": w}
        nombre = f"Mediana (w={w})"

    elif filtro == "Media":
        y_suavizado = rolling(datos_y_orig, w, lambda v: sum(v) / len(v))
        params = {"window": w}
        nombre = f"Media (w={w})"

    elif filtro == "Mínimos":
        y_suavizado = rolling(datos_y_orig, w, min)
        params = {"window": w}
        nombre = f"Mínimos (w={w})"

    elif filtro == "Máximos":
        y_suavizado = rolling(datos_y_orig, w, max)
        params = {"window": w}
        nombre = f"Máximos (w={w})"

    elif filtro == "Volatilidad":
        y_suavizado = rolling(datos_y_orig, w,
                              lambda v: statistics.stdev(v) if len(v) > 1 else 0.0)
        params = {"window": w}
        nombre = f"Volatilidad (w={w})"

    elif filtro == "Suma móvil":
        y_suavizado = rolling(datos_y_orig, w, sum)
        params = {"window": w}
        nombre = f"Suma móvil (w={w})"

    else:
        messagebox.showinfo("Aviso", "Selecciona un filtro válido.")
        return

    color = PALETA[len(curvas_suavizadas) % len(PALETA)]
    curvas_suavizadas.append({"nombre": nombre, "x": list(datos_x_orig), "y": list(y_suavizado), "color": color, "params": params})
    replot()

def guardar_suavizado():
    """Guarda una curva suavizada en un archivo de texto."""
    if not curvas_suavizadas:
        messagebox.showwarning("Aviso", 
            "No hay curvas suavizadas.\nAplica un suavizado primero.")
        return

    # Si hay varias, dejar elegir al usuario
    if len(curvas_suavizadas) == 1:
        curva = curvas_suavizadas[0]
    else:
        curva = elegir_curva_suavizada()
        if curva is None:
            return  # Usuario canceló

    # Diálogo para guardar
    ruta = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Archivo de texto", "*.txt"), ("Todos", "*.*")],
        initialfile=f"{curva['nombre']}_{datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}.txt"
    )
    if not ruta:
        return

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            # Encabezado
            f.write("# ===== OPN Spec - Datos suavizados =====\n")
            f.write(f"# Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Método: {curva['metodo']}\n")
            for k, v in curva['params'].items():
                f.write(f"#   {k}: {v}\n")
            f.write(f"# Puntos: {len(curva['x'])}\n")
            f.write("# -------------------------------------------\n")
            
            # Comentarios del usuario (si los hay)
            comentarios = casilla_comentarios.get("1.0", tk.END).strip()
            if comentarios:
                for linea in comentarios.splitlines():
                    f.write(f"# {linea}\n")
            f.write("# -------------------------------------------\n")
            f.write("# Tiempo(s)    Voltaje(V)_suavizado\n")

            # Datos
            for x, y in zip(curva['x'], curva['y']):
                f.write(f"{x:8.3f}   {y:8.4f}\n")

        messagebox.showinfo("Éxito", 
            f"Suavizado guardado en:\n{ruta}\n\n"
            f"Método: {curva['metodo']}\n"
            f"Puntos: {len(curva['x'])}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

def cmd_guardar_suavizados():
    if not curvas_suavizadas:
        messagebox.showwarning("Aviso", "No hay curvas suavizadas para guardar.\nAplica un filtro primero.")
        return

    # Preguntar si guardar todas en un archivo o una por archivo
    guardar_todas = messagebox.askyesno(
        "Guardar suavizados",
        f"Hay {len(curvas_suavizadas)} curva(s) suavizada(s).\n\n"
        "¿Guardar TODAS en un solo archivo?\n"
        "(Sí = un archivo | No = un archivo por curva)"
    )

    if guardar_todas:
        _guardar_todas_en_uno()
    else:
        _guardar_una_por_archivo()

def _guardar_todas_en_uno():
    ruta = filedialog.asksaveasfilename(
        defaultextension=".dat",
        filetypes=[("Archivo de texto", "*.dat"), ("Todos", "*.*")],
        initialfile=f"suavizados_{datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}.dat"
    )
    if not ruta:
        return

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("# 🎁🎁🎁🎁\n#  OPNSpec - Suavizados\n# 🚀🚀🚀🚀\n")
            f.write(f"#📅 {datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}\n")
            f.write("# -------------------------------------------\n")
            for i, c in enumerate(curvas_suavizadas, start=1):
                params = c.get("params", {})
                params_txt = ", ".join(f"{k}={v}" for k, v in params.items())
                f.write(f"# Curva {i}: {c['nombre']}")
                if params_txt:
                    f.write(f"  [{params_txt}]")
                f.write("\n")
            f.write("# -------------------------------------------\n")

            # Escribir en columnas: tiempo | curva1 | curva2 | ...
            f.write("# Tiempo(s)")
            for c in curvas_suavizadas:
                f.write(f"\t{c['nombre']}")
            f.write("\n")

            # Asumimos que todas comparten la misma x (vienen de datos_x_orig)
            x_ref = curvas_suavizadas[0]["x"]
            n = len(x_ref)
            for i in range(n):
                fila = f"{x_ref[i]:10.4f}"
                for c in curvas_suavizadas:
                    y = c["y"][i] if i < len(c["y"]) else float("nan")
                    fila += f"\t{float(y):10.6f}"
                f.write(fila + "\n")

        messagebox.showinfo("Éxito", f"Suavizados guardados en:\n{ruta}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

def _guardar_una_por_archivo():
    carpeta = filedialog.askdirectory(title="Selecciona carpeta para guardar los suavizados")
    if not carpeta:
        return

    try:
        guardados = 0
        for c in curvas_suavizadas:
            # Nombre seguro: reemplaza caracteres problemáticos
            nombre_limpio = (c["nombre"]
                             .replace(" ", "_")
                             .replace("(", "")
                             .replace(")", "")
                             .replace("=", "")
                             .replace(",", ""))
            nombre_archivo = f"{nombre_limpio}_{datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}.dat"
            ruta = os.path.join(carpeta, nombre_archivo)

            params = c.get("params", {})
            params_txt = ", ".join(f"{k}={v}" for k, v in params.items())

            with open(ruta, "w", encoding="utf-8") as f:
                f.write("# 🎁🎁🎁🎁\n#  OPNSpec - Suavizado\n# 🚀🚀🚀🚀\n")
                f.write(f"#📅 {datetime.now().strftime('%Y_%m_%d-%H_%M_%S')}\n")
                f.write("# -------------------------------------------\n")
                f.write(f"# Filtro: {c['nombre']}\n")
                if params_txt:
                    f.write(f"# Parámetros: {params_txt}\n")
                f.write("# -------------------------------------------\n")
                f.write("# Tiempo(s)    Valor(V)\n")
                for x, y in zip(c["x"], c["y"]):
                    f.write(f"{float(x):10.4f}   {float(y):10.6f}\n")
            guardados += 1

        messagebox.showinfo("Éxito", f"{guardados} archivo(s) guardado(s) en:\n{carpeta}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

def cmd_quitar_ultimo_suavizado():
    if not curvas_suavizadas:
        messagebox.showinfo("Aviso", "No hay curvas suavizadas que quitar.")
        return
    eliminada = curvas_suavizadas.pop()
    replot()
    messagebox.showinfo("Listo", f"Se quitó: {eliminada['nombre']}")

    tamano_fuente_comentarios = 11

def aumentar_fuente():
    global tamano_fuente_comentarios
    tamano_fuente_comentarios = min(13, tamano_fuente_comentarios + 1)
    casilla_comentarios.config(font=("Arial", tamano_fuente_comentarios))
    casilla_datos.config(font=("Arial", tamano_fuente_comentarios))

def disminuir_fuente():
    global tamano_fuente_comentarios
    tamano_fuente_comentarios = max(6, tamano_fuente_comentarios - 1)
    casilla_comentarios.config(font=("Arial", tamano_fuente_comentarios))
    casilla_datos.config(font=("Arial", tamano_fuente_comentarios))

def cmd_estadisticos():
    if not datos_y_orig:
        messagebox.showwarning("Aviso", "No hay datos para analizar.\nPrimero mide o carga un archivo.")
        return

    y = datos_y_orig
    x = datos_x_orig

    n = len(y)
    media = statistics.mean(y)
    mediana = statistics.median(y)
    moda = statistics.mode(y) if len(set(y)) < n else "N/A"
    
    desv_std = statistics.stdev(y) if n > 1 else 0
    varianza = statistics.variance(y) if n > 1 else 0
    coef_var = (desv_std / media * 100) if media != 0 else 0
    
    minimo = min(y)
    maximo = max(y)
    rango = maximo - minimo
    
    y_sorted = sorted(y)
    p25 = y_sorted[n // 4] if n >= 4 else y_sorted[0]
    p50 = y_sorted[n // 2]
    p75 = y_sorted[3 * n // 4] if n >= 4 else y_sorted[-1]
    iqr = p75 - p25  # Rango intercuartílico
    
    error_std = desv_std / (n ** 0.5) if n > 0 else 0
    
    duracion = x[-1] - x[0] if len(x) > 1 else 0
    frecuencia = 1 / intervalo_prom if intervalo_prom > 0 else 0
    
    nombre_archivo = archivo_actual["nombre"] if archivo_actual else "Medición en vivo"
    
    reporte = f"""
# ════════════
# ESTADÍSTICOS
# ════════════
# Archivo: {nombre_archivo}
# Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Puntos: {n}
# ════════════

#   TENDENCIA CENTRAL
#   Media:           {media:.6f}
#   Mediana:         {mediana:.6f}
#   Moda:            {moda if isinstance(moda, str) else f"{moda:.6f}"}

#   VARIABILIDAD
#   Desv. Estándar:  {desv_std:.6f}
#   Varianza:        {varianza:.6f} ²
#   Coef. Var.:      {coef_var:.2f}%
#   E. Estándar:     {error_std:.6f}

#   RANGO Y DISTRIBUCIÓN
#   Mínimo:          {minimo:.6f}
#   Máximo:          {maximo:.6f}
#   Rango:           {rango:.6f}
#   Percentil 25%:   {p25:.6f}
#   Percentil 50%:   {p50:.6f}
#   Percentil 75%:   {p75:.6f}
#   Rango Interc.:   {iqr:.6f}

#   TIEMPO
#   Duración total:  {duracion:.3f} s
#   Frecuencia:      {frecuencia:.2f} Hz
# ════════════
"""
    
    # Mostrar en casilla de comentarios
    casilla_comentarios.insert(tk.END, reporte)
    casilla_comentarios.see(tk.END)
    
    messagebox.showinfo("Análisis completo", 
        f"Estadísticos calculados para {n} puntos.\n"
        f"Revisa la casilla de comentarios.")
# ======================================================================================== layout

frame_puertos = ttk.LabelFrame(root, text="Puerto Serial")
frame_puertos.pack(fill="x", padx=(4,4), pady=(4, 2))

frame_params = ttk.LabelFrame(root, text="Parámetros")
frame_params.pack(fill="x", padx=(4,4), pady=(2,2))

main = tk.Frame(root, bg="#333333")
main.pack(fill="both", expand=True, padx=(2,2), pady=(2,4))

frame_botones = ttk.LabelFrame(main, width=100) #, text="Obervaciones"
frame_botones.pack(side="left", fill="both", expand=False, padx=(2,2), pady=(2,2))

frame_btncmd = ttk.LabelFrame(frame_botones, text="Observar")
frame_btncmd.pack(side="top", fill="both", expand=False, padx=(4,4), pady=(0,4))

frame_filtro = ttk.LabelFrame(frame_botones, text="Filtar")
frame_filtro.pack(fill="x", expand=False, padx=(4,4), pady=(2,2))

frame_file = ttk.Frame(frame_filtro)
frame_file.pack(fill="x", expand=False, padx=(4,4), pady=(1,1))

frame_wincomb = tk.Frame(frame_filtro)
frame_wincomb.pack(fill="x", pady=(4,5), padx=(1,1))

frame_ventana = tk.Frame(frame_filtro)
frame_ventana.pack(fill="x", pady=(5,5), padx=(1,1))

frame_orden = tk.Frame(frame_filtro)
frame_orden.pack(fill="x", pady=(5,5), padx=(1,1))

frame_plot = ttk.LabelFrame(main, text="Plots")
frame_plot.pack(side="left", fill="both", expand=True, padx=(4,4), pady=(2,2))

frame_monitor = tk.Frame(main, bg="#333333", width=250)
frame_monitor.pack(side="left", fill="y", padx=(2, 4), pady=(2,4))
frame_monitor.pack_propagate(False)

frame_coment = ttk.LabelFrame(frame_monitor, text="Comentarios")
frame_coment.pack(fill="both", expand=False, pady=(0, 2) )

frame_datos = ttk.LabelFrame(frame_monitor, text="Datos (tiempo, voltaje)")
frame_datos.pack(fill="both", expand=True, padx=(0,0), pady=(2, 4))

frame_stats = ttk.LabelFrame(frame_botones, text="Estadísticos")
frame_stats.pack(side="top", fill="both", expand=False, padx=(4,4), pady=(4,2))

# ======================================================================================== botones serial

combo_puertos = ttk.Combobox(frame_puertos, state="readonly", width=25)
combo_puertos.pack(side="left", padx=(4,4), pady=4)

ttk.Button(frame_puertos, text="⟳", width=5, command=list_ports).pack(side="left", padx=4)

btn_conectar = ttk.Button(frame_puertos, text="Conectar", command=conectar)
btn_conectar.pack(side="left", padx=(4,4))

btn_desconectar = ttk.Button(frame_puertos, text="Desconectar", command=desconectar, state="disabled")
btn_desconectar.pack(side="left", padx=(4,4))

lbl_estado = ttk.Label(frame_puertos, text=" 🛸 Desconectado", font=("Arial", 11 , "bold"), foreground="red" )
lbl_estado.pack(side="right", padx=(4,4))

btn_driver = ttk.Button(frame_puertos, text="⇓", width=5, command=down_driver, state="normal")
btn_driver.pack(side="left", padx=(4,4))

# ======================================================================================== botones parámetros

lbl_intervalo = tk.Label(frame_params, text="Intervalo : ", font=("Arial", 10))
lbl_intervalo.pack(side="left", padx=(4, 2))

spin_intervalo = tk.Spinbox(frame_params, from_=1, to=60000, increment=500, width=5, font=("Arial", 10), justify="left")
spin_intervalo.delete(0, tk.END)
spin_intervalo.insert(0, "200")
spin_intervalo.pack(side="left", padx=(4,4))
tk.Label(frame_params, text="ms.", font=("Arial", 10)).pack(side="left", padx=(2,4))

lbl_prom = tk.Label(frame_params, text="Promedio : ", font=("Arial", 10))
lbl_prom.pack(side="left", padx=(4, 4))

spin_prom = tk.Spinbox(frame_params, from_=1, to=1000, increment=100, width=4, font=("Arial", 10), justify="left")
spin_prom.delete(0, tk.END)
spin_prom.insert(0, "10")
spin_prom.pack(side="left", padx=(4,4))
tk.Label(frame_params, text="Observaciones.", font=("Arial", 10)).pack(side="left", padx=(2,4))

lbl_portadc = tk.Label(frame_params, text="Prt.ADC : ", font=("Arial", 10))
lbl_portadc.pack(side="left", padx=(4, 4))

spin_portadc = tk.Spinbox(frame_params, from_=34, to=39, increment=1, width=4, font=("Arial", 10), justify="left")
spin_portadc.delete(0, tk.END)
spin_portadc.insert(0, "34")
spin_portadc.pack(side="left", padx=(4,4))
tk.Label(frame_params, text=".", font=("Arial", 10)).pack(side="left", padx=(2,4))

lbl_portdac = tk.Label(frame_params, text="Prt.DAC : ", font=("Arial", 10))
lbl_portdac.pack(side="left", padx=(4, 4))

spin_portdac = tk.Spinbox(frame_params, from_=25, to=26, increment=1, width=4, font=("Arial", 10), justify="left")
spin_portdac.delete(0, tk.END)
spin_portdac.insert(0, "25")
spin_portdac.pack(side="left", padx=(4,4))
tk.Label(frame_params, text=".", font=("Arial", 10)).pack(side="left", padx=(2,4))

lbl_powdac = tk.Label(frame_params, text="I.DAC : ", font=("Arial", 10))
lbl_powdac.pack(side="left", padx=(4, 4))

spin_powdac = tk.Spinbox(frame_params, from_=0, to=255, increment=1, width=4, font=("Arial", 10), justify="left")
spin_powdac.delete(0, tk.END)
spin_powdac.insert(0, "0")
spin_powdac.pack(side="left", padx=(4,4))
tk.Label(frame_params, text="bits", font=("Arial", 10)).pack(side="left", padx=(2,4))

btn_mas = tk.Button(frame_params, text="A+", command=aumentar_fuente, width=15, height=1)
btn_mas.pack(pady=(4, 4), padx=(5,5), side="right")

btn_menos = tk.Button(frame_params, text="A-", command=disminuir_fuente, width=15, height=1)
btn_menos.pack(pady=(4, 4), padx=(5,5), side="right")

root.bind("<Control-plus>", lambda e: aumentar_fuente())                                  # Atajos de teclado
root.bind("<Control-minus>", lambda e: disminuir_fuente())

# ======================================================================================== botones medición

btn_play = tk.Button(frame_btncmd, text="▶ Play", bg="#2ecc71", activebackground="#27ae60", command=toggle_grabacion, state="disabled")
btn_play.pack(padx=(4,2), pady=(4,2), fill="x")

btn_dona = tk.Button(frame_btncmd, text=" Ayudar ", width=17, anchor="w", font=("Arial", 10, "bold"),
                     command=lambda: mostrar_qr(contenido="DA3Q9SGF7QYk8LQtSTxBTeKYRy3Jp9mJgt", titulo=" DOGE Coin :"),)
btn_dona.pack(padx=(4,2), pady=(2,2), fill="x")

btn_save = tk.Button(frame_btncmd, text=" Guardar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_guardar)
btn_save.pack(padx=(4,2), pady=(2,2), fill="x")

btn_open = tk.Button(frame_btncmd, text=" Abrir ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_abrir_espectro)
btn_open.pack(padx=(4,2), pady=(2,2), fill="x")

nombres_grafico = [nombre for nombre, _ in tipos_grafico]
combo_tiplot = ttk.Combobox(frame_btncmd, values= nombres_grafico, state="readonly", font=("Arial", 10))
combo_tiplot.set(" Línea")
combo_tiplot.pack(side="top", fill="x", pady=5, padx=5)

btn_applot = tk.Button(frame_btncmd, text="Aplicar plot", command=aplicarplot, state="normal") #activebackground="white", 
btn_applot.pack(pady=(4, 4), padx=(5,5), fill="x")

btn_clea = tk.Button(frame_btncmd, text=" Limpiar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_limpiar)
btn_clea.pack(padx=(4,2), pady=(2,2), fill="x")

# ======================================================================================== botones filtro

lbl_archivo_actual = tk.Label(frame_file, text="🤖", bg="#34495e", fg="#ecf0f1", font=("Arial", 16), wraplength=150, justify="left")
lbl_archivo_actual.pack(padx=(5,1), pady=(1, 1), fill="x")

combo_filtros = ttk.Combobox(frame_wincomb, values=filtros, state="readonly", font=("Arial", 10))
combo_filtros.set("Filtro")
combo_filtros.pack(side="top",fill="x", padx=(5,1), pady=(1,1) )

lbl_ventana = tk.Label(frame_ventana, text="Ventana:", font=("Arial", 10))
lbl_ventana.pack(side="left", padx=(5, 1), pady=(1,1))

spin_ventana = tk.Spinbox(frame_ventana, from_=1, to=10, increment=1, width=4, font=("Arial", 10), justify="center", textvariable=ventana_var)
spin_ventana.pack(side="right", padx=(5, 1), pady=(1,1), fill="x")

lbl_orden = tk.Label(frame_orden, text="Orden:", font=("Arial", 10))
lbl_orden.pack(side="left", padx=(5,1), pady=(1,1))

spin_orden = tk.Spinbox(frame_orden, from_=1, to=5, increment=1, width=4, font=("Arial", 10), justify="center", textvariable=orden_var)
spin_orden.pack(side="right", padx=(5, 1), pady=(1,1), fill="x")

btn_apfiltro = tk.Button(frame_filtro, text="Aplicar", command=aplicar, state="normal") #activebackground="white", 
btn_apfiltro.pack(padx=(5,1), pady=(1,1), fill="x")

btn_quitar_suav = tk.Button(frame_filtro, text="Quitar suavizado", width=17, anchor="w", font=("Arial", 10), command=cmd_quitar_ultimo_suavizado)
btn_quitar_suav.pack(padx=(5,1), pady=(4,4), fill="x")

btn_save_suav = tk.Button(frame_filtro, text="Guardar suavizado ", width=17, anchor="w", font=("Arial", 10), command=cmd_guardar_suavizados)
btn_save_suav.pack(padx=(5,1), pady=(1,1), fill="x")

# ======================================================================================== botones stats

btn_stats = tk.Button(frame_stats, text="Estadísticos", width=17, anchor="w", font=("Arial", 10), command=cmd_estadisticos)
btn_stats.pack(pady=2, padx=5, fill="x")

# ======================================================================================== plot

fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot(111)
ax.set_xlabel("Tiempo (s)", c="#333333")
ax.set_ylabel("Voltaje (V)", c="#333333")
ax.grid(True, linestyle="--", alpha=0.9, linewidth=1.5)

canvas = FigureCanvasTkAgg(fig, master=frame_plot)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=(1,1), pady=(1,1))

# ======================================================================================== monitor

scroll_comentarios = tk.Scrollbar(frame_coment)
scroll_comentarios.pack(side="right", fill="y")

casilla_comentarios = tk.Text(frame_coment, font=("Arial", tamano_fuente_comentarios), wrap=tk.WORD, yscrollcommand=scroll_comentarios.set, bg="#eeeeee", width=34, height=10)
casilla_comentarios.pack(side="left", fill="both", expand=True, padx=(2,4), pady=(2,0))

scroll_comentarios.config(command=casilla_comentarios.yview)

scroll_datos = tk.Scrollbar(frame_datos)
scroll_datos.pack(side="right", fill="y")

casilla_datos = tk.Text(frame_datos, font=("Courier New", tamano_fuente_comentarios), wrap="none", yscrollcommand=scroll_datos.set, bg="#dddddd", width=34, height=15)
casilla_datos.pack(side="left", fill="both", expand=True, padx=4, pady=4)

scroll_datos.config(command=casilla_datos.yview)

# ======================================================================================== ejecución

list_ports()
root.mainloop()
