# ui.py
import tkinter as Tk
from tkinter import messagebox
from main import scan_wifi

# --- Función para actualizar ---
def actualizar_escaneo():
    # Limpiar contenido anterior
    for widget in frame_redes.winfo_children():
        widget.destroy()

    try:
        redes = scan_wifi()
        cantidad_label.config(text=f"Cantidad de redes: {len(redes)}")

        for i, r in enumerate(redes):
            # Crear un frame para cada red
            card = Tk.Frame(frame_redes, bg="#8CF5E1", bd=2, relief="groove")
            card.pack(fill="x", padx=5, pady=5)

            Tk.Label(
                card, 
                text=f"SSID: {r['SSID']}", 
                bg="#222", fg="white", anchor="w", font=("Consolas", 10, "bold")
            ).pack(fill="x")

            Tk.Label(
                card, 
                text=f"Señal: {r['Señal']} dBm | Canal: {r['Canal']} | Banda: {r['Banda']} | Seguridad: {r['Seguridad']} | MAC: {r['BSSID']}",
                bg="#222", fg="white", anchor="w", font=("Consolas", 9)
            ).pack(fill="x", padx=5, pady=5)
        if not redes:
            Tk.Label(
                frame_redes,
                text="📡",  # Emoji de antena WiFi
                bg="#111", fg="gray", font=("Arial", 40)
            ).pack(pady=10, anchor="center", expand=True)
            Tk.Label(
                frame_redes,
                text="No se encontraron redes WiFi.",
                bg="#111", fg="white", font=("Consolas", 12, "bold")
            ).pack(anchor="center", expand=True)

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo escanear:\n{e}")
    finally:
        root.after(2000, actualizar_escaneo)  # Actualiza cada 2 segundos

# --- Ventana principal ---
root = Tk.Tk()
root.title("Escáner WiFi")
root.geometry("700x500")
root.minsize(700, 500)  # 🔥 Tamaño mínimo permitido
root.configure(bg="#111")

# Título
Tk.Label(root, text="Escáner WiFi", font=("Arial", 16), bg="#111", fg="white").pack(pady=10)
cantidad_label = Tk.Label(root, text="Cantidad de redes: 0", bg="#111", fg="white")
cantidad_label.pack()

# Frame contenedor con scroll
canvas = Tk.Canvas(root, bg="#111", highlightthickness=0)
canvas.pack(side="left", fill="both", expand=True)

scrollbar = Tk.Scrollbar(root, orient="vertical", command=canvas.yview)
scrollbar.pack(side="right", fill="y")
canvas.configure(yscrollcommand=scrollbar.set)

frame_redes = Tk.Frame(canvas, bg="#111")  # Frame de contenido
frame_window = canvas.create_window((0, 0), window=frame_redes, anchor="nw")

# Ajustar scroll y tamaño dinámico
def on_configure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
    # Ajustar el ancho del frame al ancho del canvas
    canvas.itemconfig(frame_window, width=event.width)

frame_redes.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.bind("<Configure>", on_configure)


# Iniciar actualización
actualizar_escaneo()
root.mainloop()
