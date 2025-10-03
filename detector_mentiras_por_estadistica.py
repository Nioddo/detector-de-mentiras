# VERSIÓN 1: LÓGICA DE CALIBRACIÓN ESTADÍSTICA
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import serial
import cv2
from deepface import DeepFace
from collections import deque, Counter
import mysql.connector
from datetime import datetime
from PIL import Image, ImageTk
import numpy as np

# === CONFIGURACIÓN ===
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
CAM_INDEX = 1

EMOCIONES = ['happy', 'neutral', 'sad', 'angry', 'fear', 'surprise']
NEGATIVAS = ['sad', 'angry', 'fear', 'surprise']

DB_CONFIG = { 'host': 'localhost', 'user': 'alumno', 'password': 'alumnoipm', 'database': 'lie2' }

# === LÓGICA DE APRENDIZAJE Y PREDICCIÓN (ESTADÍSTICA) ===

def obtener_datos_calibracion(id_persona=None):
    conn = conectar_db()
    cursor = conn.cursor(dictionary=True)
    query = """
    SELECT d.emocion, d.pulsaciones, d.humedadcorporal, m.respuesta
    FROM datos d JOIN medicion m ON d.medicion_idmedicion = m.idmedicion
    WHERE m.tipo = 'calibracion' AND m.respuesta IS NOT NULL
    """
    if id_persona:
        query += " AND m.personas_idpersona = %s"
        cursor.execute(query, (id_persona,))
    else:
        cursor.execute(query)
    resultados = cursor.fetchall()
    conn.close()
    return resultados

def calcular_perfil_biometrico(datos_calibracion):
    perfil = {'verdad': {'pulsaciones': [], 'humedad': [], 'emociones': []}, 'mentira': {'pulsaciones': [], 'humedad': [], 'emociones': []}}
    for dato in datos_calibracion:
        tipo_respuesta = dato['respuesta']
        if tipo_respuesta in perfil:
            perfil[tipo_respuesta]['pulsaciones'].append(dato['pulsaciones'])
            perfil[tipo_respuesta]['humedad'].append(dato['humedadcorporal'])
            perfil[tipo_respuesta]['emociones'].append(dato['emocion'])
            
    perfil_calculado = {}
    for tipo in ['verdad', 'mentira']:
        puls, hum, emo = perfil[tipo]['pulsaciones'], perfil[tipo]['humedad'], perfil[tipo]['emociones']
        if not puls: continue
        total_emo = len(emo)
        neg_emo = sum(1 for e in emo if e in NEGATIVAS)
        perfil_calculado[tipo] = {
            'avg_pulsaciones': np.mean(puls), 'avg_humedad': np.mean(hum),
            'porc_negativas': neg_emo / total_emo if total_emo > 0 else 0
        }
    return perfil_calculado

def predecir_respuesta(datos_medicion_actual, perfil):
    if 'verdad' not in perfil or 'mentira' not in perfil:
        return "indeterminado (faltan datos de calibración)"

    puls_actual = np.mean([d[1] for d in datos_medicion_actual])
    hum_actual = np.mean([d[2] for d in datos_medicion_actual])
    neg_actual = sum(1 for d in datos_medicion_actual if d[0] in NEGATIVAS) / len(datos_medicion_actual)

    # Vector de la medición actual
    vec_actual = np.array([puls_actual, hum_actual, neg_actual * 100]) # Multiplicamos % para darle más peso
    
    # Vectores de los perfiles
    vec_verdad = np.array([perfil['verdad']['avg_pulsaciones'], perfil['verdad']['avg_humedad'], perfil['verdad']['porc_negativas'] * 100])
    vec_mentira = np.array([perfil['mentira']['avg_pulsaciones'], perfil['mentira']['avg_humedad'], perfil['mentira']['porc_negativas'] * 100])
    
    # Calcular distancia euclidiana (norma L2)
    distancia_a_verdad = np.linalg.norm(vec_actual - vec_verdad)
    distancia_a_mentira = np.linalg.norm(vec_actual - vec_mentira)
    
    return "verdad" if distancia_a_verdad < distancia_a_mentira else "mentira"

# === FUNCIONES BASE DE DATOS (CON PEQUEÑOS CAMBIOS) ===
def conectar_db():
    return mysql.connector.connect(**DB_CONFIG, charset='utf8mb4', use_unicode=True)

def finalizar_medicion(id_medicion, tipo='prediccion'):
    conn = conectar_db()
    cursor = conn.cursor()
    fin = datetime.now()
    sql = "UPDATE medicion SET tiempofin = %s, tipo = %s WHERE idmedicion = %s"
    cursor.execute(sql, (fin, tipo, id_medicion))
    conn.commit()
    conn.close()
# (Aquí irían el resto de funciones de la base de datos: insertar_persona, obtener_personas, etc. Las omito por brevedad pero deben estar en tu código)
# ... Código de funciones de BD de la respuesta anterior ...
# OK, las añadiré todas para que sea totalmente funcional
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

def guardar_dato(medicion_id, emocion, pulsaciones, humedad):
    conn = conectar_db()
    cursor = conn.cursor()
    now = datetime.now()
    sql = "INSERT INTO datos (emocion, pulsaciones, humedadcorporal, `fecha/tiempo`, medicion_idmedicion) VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(sql, (emocion, pulsaciones, humedad, now, medicion_id))
    conn.commit()
    conn.close()

def guardar_resultado(id_medicion, resultado_maquina):
    valor_resultado = None if resultado_maquina.startswith("indeterminado") else (1 if resultado_maquina == "verdad" else 0)
    conn = conectar_db()
    cursor = conn.cursor()
    sql = "UPDATE medicion SET resultado = %s WHERE idmedicion = %s"
    cursor.execute(sql, (valor_resultado, id_medicion))
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

def determinar_rango_etario(edad):
    if edad <= 11: return 'niño'
    elif edad <= 17: return 'teen'
    elif edad <= 64: return 'adulto'
    else: return 'anciano'
# === INTERFAZ PRINCIPAL (Modificada para la nueva lógica) ===

class DetectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Detector de Mentiras v1.0 (Calibración Estadística)")
        self.persona_id, self.medicion_id, self.genero, self.serial_data = None, None, None, None
        self.contador, self.emocion_actual = 0, "iniciando..."
        self.running, self.cam_ok = False, False
        self.latest_frame = None

        self.build_ui()
        threading.Thread(target=self.leer_emocion_cam, daemon=True).start()
        
        try:
            self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE)
        except serial.SerialException as e:
            messagebox.showerror("Error de Arduino", f"No se pudo conectar al Arduino en {SERIAL_PORT}.\n\nError: {e}")
            self.root.destroy()
            return
        self.actualizar_video()

    # --- Métodos principales ---
    def leer_sensores(self):
        while self.running:
            try:
                if self.serial.in_waiting > 0:
                    linea = self.serial.readline().decode('utf-8').strip()
                    if "|" in linea:
                        pulsaciones, humedad = map(int, linea.split("|"))
                        if pulsaciones > 0 and humedad > 0:
                            guardar_dato(self.medicion_id, self.emocion_actual, pulsaciones, humedad)
                            self.tabla.insert("", "end", values=(self.emocion_actual, pulsaciones, humedad))
            except Exception as e:
                print(f"Error leyendo el puerto serial: {e}")
            time.sleep(0.25) # 4 muestras por segundo

    def leer_emocion_cam(self):
        cap = cv2.VideoCapture(CAM_INDEX)
        if not cap.isOpened(): self.cam_ok = False; return
        self.cam_ok = True
        emotion_buffer = deque(maxlen=5)
        while True:
            ret, frame = cap.read()
            if not ret: self.cam_ok = False; time.sleep(1); continue
            self.latest_frame = frame.copy()
            if self.running:
                try:
                    result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False, silent=True)
                    emotion = result[0]['dominant_emotion']
                    emotion_buffer.append(emotion)
                    self.emocion_actual = Counter(emotion_buffer).most_common(1)[0][0]
                except Exception: pass
            time.sleep(0.25) # 4 muestras por segundo

    def finalizar(self):
        self.running = False
        self.boton_finalizar.config(state="disabled")
        self.boton_iniciar.config(state="normal")
        self.emocion_actual = "finalizado"

        popup = tk.Toplevel(self.root)
        popup.title("Finalizar Medición"); popup.geometry("400x350"); popup.grab_set()
        is_calibracion_var = tk.BooleanVar()

        def on_calibracion_toggle():
            if is_calibracion_var.get():
                respuesta_label.pack(pady=5); combo_respuesta_real.pack(pady=5); btn_guardar.config(text="Guardar Calibración")
            else:
                respuesta_label.pack_forget(); combo_respuesta_real.pack_forget(); btn_guardar.config(text="Calcular y Guardar")

        tk.Checkbutton(popup, text="Es una medición de CALIBRACIÓN", variable=is_calibracion_var, command=on_calibracion_toggle).pack(pady=10)
        respuesta_label = tk.Label(popup, text="La respuesta real del sujeto fue:")
        combo_respuesta_real = ttk.Combobox(popup, state="readonly", values=["verdad", "mentira"])
        tk.Label(popup, text="Comentario (opcional):").pack(pady=5)
        comentario_box = tk.Text(popup, height=5, width=40); comentario_box.pack(pady=5)
        
        def guardar_y_cerrar():
            comentario = comentario_box.get("1.0", tk.END).strip()
            if is_calibracion_var.get():
                respuesta_real = combo_respuesta_real.get()
                if not respuesta_real: messagebox.showerror("Error", "Debes seleccionar 'verdad' o 'mentira' para calibrar."); return
                finalizar_medicion(self.medicion_id, "calibracion")
                guardar_respuesta_real(self.medicion_id, respuesta_real)
                if comentario: guardar_comentario_medicion(self.medicion_id, comentario)
                messagebox.showinfo("Calibración Guardada", "Los datos de calibración se guardaron exitosamente.")
                popup.destroy()
            else:
                finalizar_medicion(self.medicion_id, "prediccion")
                datos_cal_persona = obtener_datos_calibracion(self.persona_id)
                perfil = calcular_perfil_biometrico(datos_cal_persona); fuente_datos = "el perfil PERSONAL"
                if 'verdad' not in perfil or 'mentira' not in perfil:
                    datos_cal_general = obtener_datos_calibracion()
                    perfil = calcular_perfil_biometrico(datos_cal_general); fuente_datos = "el perfil GENERAL"
                
                datos_actuales = [self.tabla.item(i)["values"] for i in self.tabla.get_children()]
                resultado = predecir_respuesta(datos_actuales, perfil)
                guardar_resultado(self.medicion_id, resultado)
                if comentario: guardar_comentario_medicion(self.medicion_id, comentario)
                messagebox.showinfo("Predicción Completa", f"Basado en {fuente_datos},\nla predicción de la máquina es: {resultado.upper()}")
                popup.destroy()

        btn_guardar = tk.Button(popup, text="Calcular y Guardar", command=guardar_y_cerrar); btn_guardar.pack(pady=10)
        self.root.wait_window(popup)

    # --- Métodos de UI (sin cambios lógicos) ---
    def build_ui(self):
        # (Este código es el mismo que la respuesta anterior, lo incluyo para que sea completo)
        main_frame = tk.Frame(self.root); main_frame.grid(row=0, column=0, padx=10, pady=10)
        frame = tk.LabelFrame(main_frame, text="Datos Persona"); frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        for i, label in enumerate(["Nombre", "Apellido", "Edad", "DNI", "Comentario"]):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
        self.nombre, self.apellido, self.edad, self.dni, self.comentario = (tk.Entry(frame, width=30) for _ in range(5))
        for i, entry in enumerate([self.nombre, self.apellido, self.edad, self.dni, self.comentario]): entry.grid(row=i, column=1, padx=5, pady=2)
        tk.Button(frame, text="Hombre", command=lambda: self.set_genero("hombre")).grid(row=5, column=0, pady=5)
        tk.Button(frame, text="Mujer", command=lambda: self.set_genero("mujer")).grid(row=5, column=1, pady=5)
        tk.Button(frame, text="Registrar", command=self.registrar_persona).grid(row=6, column=0, columnspan=2, pady=5)
        self.combo = ttk.Combobox(frame, state="readonly", width=40); self.combo.grid(row=7, column=0, columnspan=2, pady=5, padx=5)
        self.combo.bind("<<ComboboxSelected>>", self.seleccionar_persona); self.cargar_personas()
        frame2 = tk.LabelFrame(main_frame, text="Medición"); frame2.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.boton_iniciar = tk.Button(frame2, text="Iniciar", command=self.iniciar, state="disabled"); self.boton_iniciar.pack(side="left", padx=10, pady=10)
        self.boton_finalizar = tk.Button(frame2, text="Finalizar", command=self.finalizar, state="disabled"); self.boton_finalizar.pack(side="left", padx=10, pady=10)
        self.tiempo_label = tk.Label(frame2, text="Tiempo: 0s"); self.tiempo_label.pack(side="right", padx=10, pady=10)
        self.tabla = ttk.Treeview(main_frame, columns=("emocion", "pulsaciones", "humedad"), show="headings")
        for col in self.tabla["columns"]: self.tabla.heading(col, text=col.capitalize()); self.tabla.column(col, width=100, anchor="center")
        self.tabla.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        video_frame = tk.LabelFrame(self.root, text="Señal de Video"); video_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ns")
        self.video_label = tk.Label(video_frame); self.video_label.pack()
    def set_genero(self, g): self.genero = g; messagebox.showinfo("Género", f"Género seleccionado: {g.capitalize()}")
    def cargar_personas(self): personas = obtener_personas(); self.personas_dict = {f"{p[1]} {p[2]}  — DNI: {p[3]}": p[0] for p in personas}; self.combo["values"] = list(self.personas_dict.keys())
    def seleccionar_persona(self, event): seleccion = self.combo.get(); self.persona_id = self.personas_dict.get(seleccion); self.boton_iniciar.config(state="normal")
    def registrar_persona(self):
        n, a, e, d, c = self.nombre.get(), self.apellido.get(), self.edad.get(), self.dni.get(), self.comentario.get()
        if not n or not a or not e or not d or not self.genero: messagebox.showerror("Faltan datos", "Nombre, Apellido, Edad, DNI y Género son obligatorios."); return
        try: edad = int(e); dni = int(d)
        except ValueError: messagebox.showerror("Datos inválidos", "Edad y DNI deben ser números."); return
        self.rango = determinar_rango_etario(edad)
        try:
            self.persona_id = insertar_persona(n, a, edad, dni, c, self.genero, self.rango); messagebox.showinfo("Registro Exitoso", f"Persona '{n} {a}' registrada correctamente."); self.boton_iniciar.config(state="normal"); self.cargar_personas()
            for entry in [self.nombre, self.apellido, self.edad, self.dni, self.comentario]: entry.delete(0, tk.END)
        except ValueError as e: messagebox.showerror("Error de Registro", str(e))
    def iniciar(self):
        if not self.cam_ok: messagebox.showerror("Error de Cámara", "No se puede iniciar la medición porque la cámara no está funcionando."); return
        self.tabla.delete(*self.tabla.get_children()); self.contador = 0; self.emocion_actual = "neutral"; self.medicion_id = crear_medicion(self.persona_id); self.running = True; self.boton_finalizar.config(state="normal"); self.boton_iniciar.config(state="disabled")
        threading.Thread(target=self.leer_sensores).start(); self.actualizar_tiempo()
    def actualizar_video(self):
        if self.latest_frame is not None:
            img = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2RGB); img_pil = Image.fromarray(img)
            img_pil.thumbnail((400, 300)); img_tk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.imgtk = img_tk; self.video_label.configure(image=img_tk)
        self.root.after(30, self.actualizar_video)
    def actualizar_tiempo(self):
        if self.running: self.contador += 0.25; self.tiempo_label.config(text=f"Tiempo: {self.contador:.1f}s"); self.root.after(250, self.actualizar_tiempo)

if __name__ == "__main__":
    root = tk.Tk()
    app = DetectorApp(root)
    root.mainloop()