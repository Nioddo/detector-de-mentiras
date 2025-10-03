import tkinter as tk
from tkinter import messagebox, ttk
import threading
import random
import time
import mysql.connector
from datetime import datetime

# === Configuración DB ===
DB_CONFIG = {
    'host': 'localhost',
    'user': 'alumno',
    'password': 'alumnoipm',
    'database': 'lie2'
}

# === Funciones de base de datos ===
def conectar_db():
    return mysql.connector.connect(
        **DB_CONFIG,
        charset='utf8mb4',
        use_unicode=True
    )

def insertar_persona(nombre, apellido, edad, dni, comentario, genero, rango):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT idpersona FROM personas WHERE dni = %s", (dni,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("DNI ya registrado")

    sql = "INSERT INTO personas (nombre, apellido, edad, dni, comentario, genero, etario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(sql, (nombre, apellido, edad, dni, comentario or None, genero, rango))
    conn.commit()
    id_persona = cursor.lastrowid
    conn.close()
    return id_persona

def obtener_personas():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT idpersona, nombre, apellido, dni FROM personas")
    personas = cursor.fetchall()
    conn.close()
    return personas

def crear_medicion(id_persona):
    conn = conectar_db()
    cursor = conn.cursor()
    inicio = datetime.now()
    sql = "INSERT INTO medicion (tiempoinicio, personas_idpersona) VALUES (%s, %s)"
    cursor.execute(sql, (inicio, id_persona))
    conn.commit()
    id_medicion = cursor.lastrowid
    conn.close()
    return id_medicion

def finalizar_medicion(id_medicion):
    conn = conectar_db()
    cursor = conn.cursor()
    fin = datetime.now()
    sql = "UPDATE medicion SET tiempofin = %s WHERE idmedicion = %s"
    cursor.execute(sql, (fin, id_medicion))
    conn.commit()
    conn.close()

def guardar_dato(medicion_id, emocion, pulsaciones, humedad):
    conn = conectar_db()
    cursor = conn.cursor()
    now = datetime.now()
    sql = "INSERT INTO datos (emocion, pulsaciones, humedadcorporal, `fecha/tiempo`, medicion_idmedicion) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(sql, (emocion, pulsaciones, humedad, now, medicion_id))
    conn.commit()
    conn.close()

def guardar_resultado(id_medicion, resultado_maquina):
    conn = conectar_db()
    cursor = conn.cursor()
    valor = 1 if resultado_maquina == "verdad" else 0
    sql = "UPDATE medicion SET resultado = %s WHERE idmedicion = %s"
    cursor.execute(sql, (valor, id_medicion))
    conn.commit()
    conn.close()

def guardar_respuesta_real(id_medicion, respuesta_real):
    conn = conectar_db()
    cursor = conn.cursor()
    sql = "UPDATE medicion SET respuesta = %s WHERE idmedicion = %s"
    cursor.execute(sql, (respuesta_real, id_medicion))
    conn.commit()
    conn.close()

def guardar_comentario_medicion(id_medicion, comentario):
    conn = conectar_db()
    cursor = conn.cursor()
    sql = "UPDATE medicion SET comentario = %s WHERE idmedicion = %s"
    cursor.execute(sql, (comentario, id_medicion))
    conn.commit()
    conn.close()

def obtener_calibracion_usuario(id_persona):
    conn = conectar_db()
    cursor = conn.cursor()
    sql = "SELECT resultado, respuesta FROM medicion WHERE personas_idpersona = %s AND respuesta != 'indeterminado' AND resultado IS NOT NULL"
    cursor.execute(sql, (id_persona,))
    resultados = cursor.fetchall()
    conn.close()
    if not resultados:
        return obtener_calibracion_global()
    aciertos = sum(1 for sistema, real in resultados if (sistema == 1 and real == 'verdad') or (sistema == 0 and real == 'mentira'))
    total = len(resultados)
    return aciertos / total if total else 0.5

def obtener_calibracion_global():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT resultado, respuesta FROM medicion WHERE respuesta != 'indeterminado' AND resultado IS NOT NULL")
    resultados = cursor.fetchall()
    conn.close()
    aciertos = sum(1 for sistema, real in resultados if (sistema == 1 and real == 'verdad') or (sistema == 0 and real == 'mentira'))
    total = len(resultados)
    return aciertos / total if total else 0.5

def determinar_rango_etario(edad):
    if edad <= 11:
        return 'niño'
    elif edad <= 17:
        return 'teen'
    elif edad <= 64:
        return 'adulto'
    else:
        return 'anciano'

EMOCIONES = ['happy', 'neutral', 'sad', 'angry', 'fear', 'surprise']
NEGATIVAS = ['sad', 'angry', 'fear', 'surprise']

# === Clase Principal ===
class SimuladorDetector:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador Detector de Mentiras")
        self.persona_id = None
        self.medicion_id = None
        self.genero = None
        self.rango = None
        self.running = False
        self.contador = 0
        self.build_ui()

    def build_ui(self):
        frame = tk.LabelFrame(self.root, text="Datos Persona")
        frame.grid(row=0, column=0, padx=10, pady=5)

        for i, label in enumerate(["Nombre", "Apellido", "Edad", "DNI", "Comentario"]):
            tk.Label(frame, text=label).grid(row=i, column=0)
        self.nombre, self.apellido, self.edad, self.dni, self.comentario = (tk.Entry(frame) for _ in range(5))
        for i, entry in enumerate([self.nombre, self.apellido, self.edad, self.dni, self.comentario]):
            entry.grid(row=i, column=1)

        tk.Button(frame, text="Hombre", command=lambda: self.set_genero("hombre")).grid(row=5, column=0)
        tk.Button(frame, text="Mujer", command=lambda: self.set_genero("mujer")).grid(row=5, column=1)
        tk.Button(frame, text="Registrar", command=self.registrar_persona).grid(row=6, column=0, columnspan=2)

        self.combo = ttk.Combobox(frame, state="readonly", width=45)
        self.combo.grid(row=7, column=0, columnspan=2)
        self.combo.bind("<<ComboboxSelected>>", self.seleccionar_persona)
        self.cargar_personas()

        frame2 = tk.LabelFrame(self.root, text="Medición")
        frame2.grid(row=1, column=0, padx=10, pady=5)

        self.boton_iniciar = tk.Button(frame2, text="Iniciar", command=self.iniciar, state="disabled")
        self.boton_iniciar.grid(row=0, column=0)

        self.boton_finalizar = tk.Button(frame2, text="Finalizar", command=self.finalizar, state="disabled")
        self.boton_finalizar.grid(row=0, column=1)

        self.tiempo_label = tk.Label(frame2, text="Tiempo: 0s")
        self.tiempo_label.grid(row=1, column=0, columnspan=2)

        self.tabla = ttk.Treeview(frame2, columns=("emocion", "pulsaciones", "humedad"), show="headings")
        for col in self.tabla["columns"]:
            self.tabla.heading(col, text=col.capitalize())
        self.tabla.grid(row=2, column=0, columnspan=2)

        tk.Button(frame2, text="Ver resultado", command=self.ver_resultado).grid(row=3, column=0, columnspan=2)

    def set_genero(self, g):
        self.genero = g
        messagebox.showinfo("Género", f"Seleccionado: {g}")

    def cargar_personas(self):
        personas = obtener_personas()
        self.personas_dict = {f"{p[1]} {p[2]}  — DNI: {p[3]}": p[0] for p in personas}
        self.combo["values"] = list(self.personas_dict.keys())

    def seleccionar_persona(self, event):
        seleccion = self.combo.get()
        self.persona_id = self.personas_dict.get(seleccion)
        self.boton_iniciar.config(state="normal")

    def registrar_persona(self):
        n, a, e, d, c = self.nombre.get(), self.apellido.get(), self.edad.get(), self.dni.get(), self.comentario.get()
        if not n or not a or not e or not d or not self.genero:
            messagebox.showerror("Faltan datos", "Completá todos los campos.")
            return
        try:
            edad = int(e)
            dni = int(d)
        except:
            messagebox.showerror("Datos inválidos", "Edad y DNI deben ser números válidos.")
            return

        self.rango = determinar_rango_etario(edad)
        try:
            self.persona_id = insertar_persona(n, a, edad, dni, c, self.genero, self.rango)
            messagebox.showinfo("Registro", "Persona registrada correctamente.")
            self.boton_iniciar.config(state="normal")
            self.cargar_personas()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def iniciar(self):
        self.tabla.delete(*self.tabla.get_children())
        self.contador = 0
        self.medicion_id = crear_medicion(self.persona_id)
        self.running = True
        self.boton_finalizar.config(state="normal")
        self.boton_iniciar.config(state="disabled")
        threading.Thread(target=self.simular_datos).start()
        self.actualizar_tiempo()

    def simular_datos(self):
        while self.running:
            emocion = random.choice(EMOCIONES)
            pulsaciones = random.randint(65, 110)
            humedad = random.randint(20, 80)
            guardar_dato(self.medicion_id, emocion, pulsaciones, humedad)
            self.tabla.insert("", "end", values=(emocion, pulsaciones, humedad))
            time.sleep(1)

    def finalizar(self):
        self.running = False
        finalizar_medicion(self.medicion_id)
        self.boton_finalizar.config(state="disabled")
        self.boton_iniciar.config(state="normal")

        def guardar_y_cerrar():
            seleccion = combo.get()
            comentario = comentario_box.get("1.0", tk.END).strip()
            if seleccion not in ["verdad", "mentira", "indeterminado"]:
                messagebox.showerror("Error", "Debes seleccionar una opción válida.")
            else:
                guardar_respuesta_real(self.medicion_id, seleccion)
                guardar_comentario_medicion(self.medicion_id, comentario)
                popup.destroy()

        popup = tk.Toplevel(self.root)
        popup.title("Respuesta real y comentario")
        popup.geometry("350x250")
        popup.grab_set()

        tk.Label(popup, text="Seleccioná la respuesta real:").pack(pady=5)
        combo = ttk.Combobox(popup, state="readonly", values=["verdad", "mentira", "indeterminado"])
        combo.pack(pady=5)

        tk.Label(popup, text="Comentario (opcional):").pack(pady=5)
        comentario_box = tk.Text(popup, height=5, width=40)
        comentario_box.pack(pady=5)

        tk.Button(popup, text="Guardar", command=guardar_y_cerrar).pack(pady=5)
        popup.protocol("WM_DELETE_WINDOW", lambda: messagebox.showwarning("Aviso", "Debes seleccionar una respuesta real."))
        popup.wait_window()

    def actualizar_tiempo(self):
        if self.running:
            self.contador += 1
            self.tiempo_label.config(text=f"Tiempo: {self.contador}s")
            self.root.after(1000, self.actualizar_tiempo)

    def ver_resultado(self):
        emociones = [self.tabla.item(i)["values"][0] for i in self.tabla.get_children()]
        total = len(emociones)
        negativas = sum(1 for e in emociones if e in NEGATIVAS)
        ratio = negativas / total if total else 0
        resultado = "mentira" if ratio > 0.3 else "verdad"
        guardar_resultado(self.medicion_id, resultado)

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT respuesta FROM medicion WHERE idmedicion = %s", (self.medicion_id,))
        respuesta_real = cursor.fetchone()[0]
        conn.close()

        acierto = "CORRECTO" if (
            (resultado == "verdad" and respuesta_real == "verdad") or
            (resultado == "mentira" and respuesta_real == "mentira")
        ) else "INCORRECTO"

        messagebox.showinfo("Resultado", f"Sistema: {resultado.upper()} — ({acierto})")

# === Main ===
if __name__ == "__main__":
    root = tk.Tk()
    app = SimuladorDetector(root)
    root.mainloop()
