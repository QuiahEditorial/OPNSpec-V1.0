import machine
import time
import sys
import select
#import math
from machine import Pin, ADC

PIN_ADC = 34
INTERVALO_MS = 200
VREF = 3.3
RESOLUCION = 4095
PROMED = 10

# ADC
adc = machine.ADC(machine.Pin(PIN_ADC))
adc.atten(machine.ADC.ATTN_11DB)
adc.width(machine.ADC.WIDTH_12BIT)

# stdin no bloqueante
poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

# Estado de medición
grabando = False
t0 = 0
ultimo_envio = 0

def enviar(comentario):
    try:
        sys.stdout.write(comentario + "\n")
    except OSError:
        pass

def procesar_comando(cmd):
    global grabando, t0, INTERVALO_MS, PROMED, PIN_ADC
    cmd = cmd.strip().upper()
    if not cmd:
        return
    if ":" in cmd:
        verbo, param = cmd.split(":", 1)
    else:
        verbo, param = cmd, None

    if verbo == "INTERVAL":
        try:
            tem = int(param)             # tiempo entre mediciones
            if 0 <= tem <= 60000:
                INTERVALO_MS = tem
                enviar("# tem = {}\tms".format(tem))
            else:
                enviar("# ERROR: Tiempo fuera de rango")
        except (TypeError, ValueError):
            enviar("# ERROR: Valor inválido '{}'".format(param))
        return

    elif verbo == "PROMEDIO":
        try:
            pem = int(param)             # promedio entre mediciones
            if 1 <= pem <= 1000:
                PROMED = pem
                enviar("# pem = {}\tobs.".format(pem))
            else:
                enviar("# ERROR: Observaciones fuera de rango")
        except (TypeError, ValueError):
            enviar("# ERROR: Valor inválido '{}'".format(pem))
        return

    elif verbo == "PINADC":
        try:
            pad = int(param)
            if 32 <= pad <= 39:
                PIN_ADC = pad
                adc = machine.ADC(machine.Pin(PIN_ADC))
                adc.atten(machine.ADC.ATTN_11DB)
                adc.width(machine.ADC.WIDTH_12BIT)
                enviar("# padc = {}".format(pad))
            else:
                enviar("# ERROR: Puerto ADC fuera de rango")
        except (TypeError, ValueError):
            enviar("# ERROR: Valor inválido '{}'".format(param))
        return

    if verbo == "START":
        grabando = True
        t0 = time.ticks_ms()
        ultimo_envio = time.ticks_ms()   # reset para que no dispare de inmediato
        enviar("# Play ")
    elif verbo == "STOP":
        grabando = False
        enviar("# Stop ")
    else:
        enviar("# ERROR: comando desconocido '{}'".format(cmd))

while True:
    # Atender comandos sin bloquear
    if poll.poll(0):
        cmd = sys.stdin.readline().strip()
        if cmd:
            procesar_comando(cmd)

    # Medir si toca (sin sleep bloqueante)
    if grabando:
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, ultimo_envio) >= INTERVALO_MS:
            ultimo_envio = ahora
            raw = 0
            for i in range(PROMED):
                raw += adc.read()
            raw /= PROMED
            voltaje = raw * (VREF / RESOLUCION)
            tiempo = time.ticks_diff(ahora, t0) / 1000.0
            enviar("{:.4f},{:.4f}".format(tiempo, voltaje))

    # Sleep corto fijo: NO usar INTERVALO_MS aquí
    time.sleep_ms(1)



