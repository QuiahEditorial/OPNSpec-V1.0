# Interfaz V1.0

import tkinter as tk
import threading
import serial
import serial.tools.list_ports
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ======================================================================================== ventana principal

root = tk.Tk()
root.title("OPN Spec")
root.geometry("1150x680")
root.minsize(650, 625)
root.configure(bg="#333333")

# ======================================================================================== icono de aplicación

try:
    root.iconphoto(False, tk.PhotoImage(file="logo.ico"))
except Exception:
    pass

# ======================================================================================== variables globales

ser = None
grabando = False
datos_x = []
datos_y = []

# ======================================================================================== conección serial

def list_ports():
    puertos = [p.device for p in serial.tools.list_ports.comports()]
    combo_puertos["values"] = puertos
    if puertos:
        combo_puertos.current(0)
    else:
        combo_puertos.set("Conecte ESP32")

def conectar():
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
    global ser
    if ser and ser.is_open:
        try:
            ser.write(b"STOP\n")                                 # Se envían los comandos a ESP32
            ser.write(b"LED:OFF\n")
        except Exception:
            pass
        ser.close()
    ser = None
    grabando = False
    
    lbl_estado.config(text=" 🛸 Desconectado", foreground="red", font=("Arial", 11 , "bold"))
    btn_conectar.config(state="normal")
    btn_desconectar.config(state="disabled")

    btn_play.config(state="disabled")

# ======================================================================================== Obtención de datos

def toggle_grabacion():
    global grabando#, datos_x, datos_y, curvas_cargadas
    if ser is None or not ser.is_open:
        messagebox.showwarning("Aviso", "Conecta ESP32.")
        return

    grabando = not grabando
    if grabando:
        datos_x, datos_y = [], []            # Nuevo barrido: limpiamos la curva en vivo (no las cargadas)
        replot()

        sndcmd("START")
        btn_play.config(text="⏹ Detener", bg="#d74c3c", activebackground="#c0392b" )
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
    try:
        partes = linea.replace(";", ",").split(",")
        x = float(partes[0])
        y = float(partes[1])
    except (ValueError, IndexError):
        return
    datos_x.append(x)
    datos_y.append(y)
    casilla_monitor.insert(tk.END, f"{x:8.3f}   {y:8.3f}\n")
    casilla_monitor.see(tk.END)
    replot()

def replot():
    ax.clear()
    if datos_x and datos_y:
        ax.plot(datos_x, datos_y, color="#2ecc71", linewidth=2, alpha=0.4, label="raw")
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Voltaje (V)")
    ax.set_title("Lectura actual")
    ax.grid(True, linestyle="--", alpha=0.5, linewidth=2)
    canvas.draw_idle()

# ======================================================================================== guardar datos

def cmd_guardar():
    dat = casilla_monitor.get("1.0", tk.END).strip()
    if not dat:
        messagebox.showwarning("Aviso", "No hay datos para guardar.")
        return
    ruta = filedialog.asksaveasfilename(defaultextension=".dat", filetypes=[("Archivo de texto", "*.dat"), ("Todos", "*.*")])
    if not ruta:
        return
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            if dat:
                for linea in dat.splitlines():
                    f.write(f"{linea}\n")
            else:
                f.write("# (sin comentarios)\n")
        messagebox.showinfo("Éxito", f"Archivo guardado en:\n{ruta}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

def cmd_abrir():
    global archivo_actual#, datos_x_orig, datos_y_orig
    
    ruta = filedialog.askopenfilename(filetypes=[("Archivo de texto", "*.txt"), ("Todos", "*.*")])
    if not ruta:
        return      
    if not datos:
        messagebox.showwarning("Aviso", "El archivo no contiene datos numéricos.")
        return
    nombre = os.path.basename(ruta)
    archivo_actual = {"nombre": nombre, "ruta": ruta, "comentarios": comentarios, "x": [p[0] for p in datos], "y": [p[1] for p in datos]}

    casilla_datos.delete("1.0", tk.END)
    for x, y in datos:
        casilla_datos.insert(tk.END, f"{x:8.3f}   {y:8.3f}\n")
    graficar_archivo_cargado()    
    messagebox.showinfo("Éxito", f"Archivo '{nombre}' cargado correctamente.")

# ======================================================================================== limpiar

def cmd_clear():
    global datos_x, datos_y
    datos_x, datos_y = [], []
    casilla_monitor.delete("1.0", tk.END)
    replot()

# ======================================================================================== layout

frame_puertos = ttk.LabelFrame(root, text="Puerto Serial")
frame_puertos.pack(fill="x", padx=(5,5), pady=(5, 5))

main = tk.Frame(root, bg="#333333")
main.pack(fill="both", expand=True, padx=4, pady=4)

frame_botones = ttk.LabelFrame(main, text="Botones Comando")
frame_botones.pack(side="left", fill="both", expand=False, padx=4, pady=4)

frame_plot = ttk.LabelFrame(main, text="Plots")
frame_plot.pack(side="left", fill="both", expand=True, padx=(4,4), pady=(4,4))

fig = Figure(figsize=(5, 4), dpi=100)
ax = fig.add_subplot(111)
ax.set_xlabel("Tiempo (s)", c="#333333")
ax.set_ylabel("Voltaje (V)", c="#333333")
ax.grid(True, linestyle="--", alpha=0.5, linewidth=1.5)

canvas = FigureCanvasTkAgg(fig, master=frame_plot)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

frame_monitor = ttk.LabelFrame(main, text="Monitor", width=200)
frame_monitor.pack(side="right", fill="y", expand=False, padx=(4,4), pady=(4,4))
frame_monitor.pack_propagate(False)

scroll_monitor = tk.Scrollbar(frame_monitor)
scroll_monitor.pack(side="right", fill="y", expand=False)

casilla_monitor = tk.Text(frame_monitor, font=("Arial", 11), wrap=tk.WORD, yscrollcommand=scroll_monitor.set, bg="#eeeeee")
casilla_monitor.pack(side="left", fill="both", expand=True, padx=4, pady=4)
scroll_monitor.config(command=casilla_monitor.yview)

# ======================================================================================== botones serial

combo_puertos = ttk.Combobox(frame_puertos, state="readonly", width=25)
combo_puertos.pack(side="left", padx=4, pady=4)

ttk.Button(frame_puertos, text="⟳", width=5, command=list_ports).pack(side="left", padx=4)

btn_conectar = ttk.Button(frame_puertos, text="Conectar", command=conectar)
btn_conectar.pack(side="left", padx=4)

btn_desconectar = ttk.Button(frame_puertos, text="Desconectar", command=desconectar, state="disabled")
btn_desconectar.pack(side="left", padx=4)

lbl_estado = ttk.Label(frame_puertos, text=" 🛸 Desconectado", font=("Arial", 11 , "bold"), foreground="red" )
lbl_estado.pack(side="right", padx=4)

# ======================================================================================== botones medición

btn_play = tk.Button(frame_botones, text="▶ Play", bg="#2ecc71", activebackground="#27ae60", command=toggle_grabacion, state="disabled")
btn_play.pack(pady=(4, 2), padx=4, fill="x")

btn_save = tk.Button(frame_botones, text=" Guardar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_guardar)
btn_save.pack(pady=2, padx=4, fill="x")

btn_clear = tk.Button(frame_botones, text=" Limpiar ", width=17, anchor="w", font=("Arial", 10, "bold"), command=cmd_clear)
btn_clear.pack(pady=2, padx=5, fill="x")

# ======================================================================================== ejecución de aplicación

list_ports()
root.mainloop()
