# Interfaz V 1.3

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

# ======================================================================================== ventana principal

root = tk.Tk()
root.title("OPNSpec V1.0")
root.geometry("1150x680")
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
    archivo_actual = {
        "nombre": nombre,
        "ruta": ruta,
        "comentarios": comentarios,
        "x": [p[0] for p in datos],
        "y": [p[1] for p in datos]
    }
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
#    replot()
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
    if datos_x and datos_y:
        ax.plot(datos_x, datos_y, color="#2ecc71", linewidth=2, alpha=0.4, label="raw")
    for c in curvas_cargadas:
        ax.plot(c["x"], c["y"], color=c["color"], linewidth=2, label=c["nombre"])
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Voltaje (V)")
    ax.set_title("Lectura actual")
    ax.grid(True, linestyle="--", alpha=0.5, linewidth=2)
    canvas.draw_idle()

# ======================================================================================== limpiar

def cmd_limpiar():
    global datos_x, datos_y, datos_x_orig, datos_y_orig, curvas_cargadas, archivo_actual    
    hay_datos = (datos_x or datos_y or curvas_cargadas or curvas_suavizadas or archivo_actual)
    if hay_datos:
        confirmar = messagebox.askyesno("Limpiar", "¿Estás seguro de que quieres limpiar todo?\n\n",
            icon=messagebox.WARNING, default=messagebox.NO)
        if not confirmar:
            return  # Usuario canceló
    datos_x, datos_y = [], []
    datos_x_orig, datos_y_orig = [], []
    curvas_cargadas = []
#    curvas_suavizadas = []
    archivo_actual = None
    casilla_comentarios.delete("1.0", tk.END)
    casilla_datos.delete("1.0", tk.END)
    replot()

# ======================================================================================== layout

frame_puertos = ttk.LabelFrame(root, text="Puerto Serial")
frame_puertos.pack(fill="x", padx=(4,4), pady=(4, 2))

frame_params = ttk.LabelFrame(root, text="Parámetros")
frame_params.pack(fill="x", padx=(4,4), pady=(2,2))

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

main = tk.Frame(root, bg="#333333")
main.pack(fill="both", expand=True, padx=(0,2), pady=(2,4))

frame_botones = ttk.LabelFrame(main, text="Botones Comando")
frame_botones.pack(side="left", fill="both", expand=False, padx=(4,2), pady=(2,4))

frame_plot = ttk.LabelFrame(main, text="Plots")
frame_plot.pack(side="left", fill="both", expand=True, padx=(4,4), pady=(2,2))

fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot(111)
ax.set_xlabel("Tiempo (s)", c="#333333")
ax.set_ylabel("Voltaje (V)", c="#333333")
ax.grid(True, linestyle="--", alpha=0.5, linewidth=1.5)

canvas = FigureCanvasTkAgg(fig, master=frame_plot)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

# monitor

frame_monitor = tk.Frame(main, bg="#333333", width=300)
frame_monitor.pack(side="right", fill="y", padx=(2, 4), pady=(2,4))
frame_monitor.pack_propagate(False)

marco_coment = ttk.LabelFrame(frame_monitor, text="Comentarios")
marco_coment.pack(fill="both", expand=False, pady=(0, 2) )

scroll_comentarios = tk.Scrollbar(marco_coment)
scroll_comentarios.pack(side="right", fill="y")

casilla_comentarios = tk.Text(marco_coment, font=("Arial", 11), wrap=tk.WORD, yscrollcommand=scroll_comentarios.set, bg="#eeeeee", width=34, height=10)
casilla_comentarios.pack(side="left", fill="both", expand=True, padx=(2,4), pady=(2,0))
scroll_comentarios.config(command=casilla_comentarios.yview)

frame_datos = ttk.LabelFrame(frame_monitor, text="Datos (tiempo, voltaje)")          # Datos
frame_datos.pack(fill="both", expand=True, padx=(0,0), pady=(2, 4))

scroll_datos = tk.Scrollbar(frame_datos)
scroll_datos.pack(side="right", fill="y")

casilla_datos = tk.Text(frame_datos, font=("Courier New", 10), wrap="none", yscrollcommand=scroll_datos.set, bg="#dddddd", width=34, height=15)
casilla_datos.pack(side="left", fill="both", expand=True, padx=4, pady=4)

scroll_datos.config(command=casilla_datos.yview)

# ======================================================================================== botones

# serial

combo_puertos = ttk.Combobox(frame_puertos, state="readonly", width=25)
combo_puertos.pack(side="left", padx=4, pady=4)

ttk.Button(frame_puertos, text="⟳", width=5, command=list_ports).pack(side="left", padx=4)

btn_conectar = ttk.Button(frame_puertos, text="Conectar", command=conectar)
btn_conectar.pack(side="left", padx=4)

btn_desconectar = ttk.Button(frame_puertos, text="Desconectar", command=desconectar, state="disabled")
btn_desconectar.pack(side="left", padx=4)

lbl_estado = ttk.Label(frame_puertos, text=" 🛸 Desconectado", font=("Arial", 11 , "bold"), foreground="red" )
lbl_estado.pack(side="right", padx=4)

# medición

btn_play = tk.Button(frame_botones, text=" ▶ Play ", bg="#2ecc71", activebackground="#27ae60", command=toggle_grabacion, state="disabled")
btn_play.pack(pady=(4, 2), padx=4, fill="x")

btn_dona = tk.Button(frame_botones, text=" Ayudar ", width=17, anchor="w", font=("Arial", 10, "bold"),
                     command=lambda: mostrar_qr(contenido="DA3Q9SGF7QYk8LQtSTxBTeKYRy3Jp9mJgt", titulo=" DOGE Coin :"),)
btn_dona.pack(pady=2, padx=4, fill="x")

btn_save = tk.Button(frame_botones, text=" Guardar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_guardar)
btn_save.pack(pady=2, padx=4, fill="x")

btn_open = tk.Button(frame_botones, text=" Abrir ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_abrir_espectro)
btn_open.pack(pady=2, padx=4, fill="x")

btn_clea = tk.Button(frame_botones, text=" Limpiar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_limpiar)
btn_clea.pack(pady=2, padx=5, fill="x")

btn_suavizado = tk.Menubutton(frame_botones, text=" Filtros ", width=17, anchor="w", font=("Arial", 10, "bold"), bg="#ecf0f1", relief="raised")
btn_suavizado.pack(pady=2, padx=5, fill="x")
# ======================================================================================== ejecución de aplicación

list_ports()
root.mainloop()
