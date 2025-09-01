import tkinter as Tk
from tkinter import messagebox
from main import scan_wifi

def actualizar_escaneo():
    lista.delete(0, Tk.END)
    try:
        redes = scan_wifi()
        for r in redes:
            lista.insert(
                Tk.END,
                f"SSID: {r['SSID']} | Señal: {r['Señal']} dBm | Canal: {r['Canal']} | Banda: {r['Banda']} | Seguridad: {r['Seguridad']}"
            )
    except Exception as e:
        lista.insert(Tk.END, f"Error: {e}")
    finally:
        # Volver a ejecutar la función después de 1000 ms (1 segundo)
        root.after(1000, actualizar_escaneo)

# --- Ventana principal ---
root = Tk.Tk()
root.title("Escáner WiFi")
root.geometry("800x800")

Tk.Label(root, text="Escáner WiFi", font=("Arial", 16)).pack(pady=10)

# Crea la lista con estilo
lista = Tk.Listbox(
    root,
    width=80,
    bg="black",          # Fondo
    fg="white",          # Texto
    font=("Consolas", 10) # Fuente
)

# Empaca la lista SIN estilos
lista.pack(pady=10, fill=Tk.BOTH, expand=True)

# Llamar automáticamente al iniciar
actualizar_escaneo()

root.mainloop()
