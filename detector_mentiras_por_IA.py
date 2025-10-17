import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import serial
import cv2
from deepface import DeepFace
from collections import Counter
import mysql.connector
from datetime import datetime
from PIL import Image, ImageTk
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

# === CONFIGURACIÓN ===
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
CAM_INDEX = 1
MODEL_FILE = 'modelo_detector.joblib'
EMOCIONES = ['happy', 'neutral', 'sad', 'angry', 'fear', 'surprise']
NEGATIVAS = ['sad', 'angry', 'fear', 'surprise']
# CORREGIDO: Configuración de la base de datos correcta
DB_CONFIG = {'host': 'localhost', 
             'user': 'alumno26.oddo.nicolas', 
             'password': 'uxqH1g2ImJPBAVzcHAnclg==', 
             'database': 'Db_detectormentiras'}


# === LÓGICA DE MACHINE LEARNING ===
def preparar_datos_para_modelo():
    conn = conectar_db()
    query = "SELECT m.idmedicion, m.respuesta, d.pulsaciones, d.humedadcorporal, d.emocion FROM medicion m JOIN datos d ON m.idmedicion = d.medicion_idmedicion WHERE m.tipo = 'calibracion' AND m.respuesta IS NOT NULL"
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    if df.empty:
        return None, None
    features = []
    for medicion_id, group in df.groupby('idmedicion'):
        features.append([
            group['pulsaciones'].mean(), group['pulsaciones'].std(),
            group['humedadcorporal'].mean(), group['humedadcorporal'].std(),
            sum(1 for e in group['emocion'] if e in NEGATIVAS) / len(group['emocion']) if len(group['emocion']) > 0 else 0,
            1 if group['respuesta'].iloc[0] == 'mentira' else 0
        ])
    feature_df = pd.DataFrame(features, columns=['puls_mean', 'puls_std', 'hum_mean', 'hum_std', 'neg_emo_perc', 'target']).fillna(0)
    X = feature_df.drop('target', axis=1)
    y = feature_df['target']
    return X, y

def entrenar_y_guardar_modelo():
    X, y = preparar_datos_para_modelo()
    if X is None or len(X) < 4 or len(y.unique()) < 2:
        messagebox.showwarning("Faltan Datos", "No hay suficientes datos de calibración (se necesitan al menos 2 verdades y 2 mentiras) para entrenar.")
        return
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model.fit(X, y)
    joblib.dump(model, MODEL_FILE)
    messagebox.showinfo("Modelo Entrenado", f"Modelo de IA guardado como '{MODEL_FILE}'.")

def cargar_modelo():
    if os.path.exists(MODEL_FILE):
        return joblib.load(MODEL_FILE)
    return None

def predecir_con_modelo(datos_medicion_actual, model):
    if not datos_medicion_actual:
        return "indeterminado"
    df_actual = pd.DataFrame(datos_medicion_actual, columns=['emocion', 'pulsaciones', 'humedad'])
    features_actuales = [
        df_actual['pulsaciones'].mean(), df_actual['pulsaciones'].std(),
        df_actual['humedad'].mean(), df_actual['humedad'].std(),
        sum(1 for e in df_actual['emocion'] if e in NEGATIVAS) / len(df_actual) if len(df_actual) > 0 else 0
    ]
    features_actuales_df = pd.DataFrame([features_actuales], columns=['puls_mean', 'puls_std', 'hum_mean', 'hum_std', 'neg_emo_perc']).fillna(0)
    prediction = model.predict(features_actuales_df)
    return "mentira" if prediction[0] == 1 else "verdad"


# === FUNCIONES BASE DE DATOS ===
def conectar_db():
    return mysql.connector.connect(**DB_CONFIG, charset='utf8mb4', use_unicode=True, ssl_disabled=True)

# RESTAURADO: Función para insertar persona CON DNI
def insertar_persona(nombre, apellido, edad, dni, comentario, genero, rango):
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT idpersona FROM personas WHERE dni = %s", (dni,));
    if cursor.fetchone(): conn.close(); raise ValueError("DNI ya registrado")
    sql = "INSERT INTO personas (nombre, apellido, edad, dni, comentario, genero, etario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(sql, (nombre, apellido, edad, dni, comentario or None, genero, rango)); conn.commit()
    id_persona = cursor.lastrowid; conn.close(); return id_persona

# RESTAURADO: Función para obtener personas CON DNI
def obtener_personas():
    conn = conectar_db(); cursor = conn.cursor()
    cursor.execute("SELECT idpersona, nombre, apellido, dni FROM personas"); 
    personas = cursor.fetchall(); conn.close(); return personas

def crear_medicion(id_persona):
    conn = conectar_db(); cursor = conn.cursor(); inicio = datetime.now()
    sql = "INSERT INTO medicion (tiempoinicio, personas_idpersona) VALUES (%s, %s)"; cursor.execute(sql, (inicio, id_persona)); conn.commit();
    id_medicion = cursor.lastrowid; conn.close(); return id_medicion

def finalizar_medicion(id_medicion, tipo='prediccion'):
    conn = conectar_db(); cursor = conn.cursor(); fin = datetime.now()
    sql = "UPDATE medicion SET tiempofin = %s, tipo = %s WHERE idmedicion = %s"; cursor.execute(sql, (fin, tipo, id_medicion)); conn.commit(); conn.close()

def guardar_dato(medicion_id, emocion, pulsaciones, humedad):
    conn = conectar_db(); cursor = conn.cursor(); now = datetime.now()
    sql = "INSERT INTO datos (emocion, pulsaciones, humedadcorporal, `fecha/tiempo`, medicion_idmedicion) VALUES (%s, %s, %s, %s, %s)"; cursor.execute(sql, (emocion, pulsaciones, humedad, now, medicion_id)); conn.commit(); conn.close()

def guardar_resultado(id_medicion, resultado_maquina):
    valor = None if resultado_maquina.startswith("indeterminado") else (1 if resultado_maquina == "verdad" else 0)
    conn = conectar_db(); cursor = conn.cursor()
    sql = "UPDATE medicion SET resultado = %s WHERE idmedicion = %s"; cursor.execute(sql, (valor, id_medicion)); conn.commit(); conn.close()

def guardar_respuesta_real(id_medicion, respuesta_real):
    conn = conectar_db(); cursor = conn.cursor()
    sql = "UPDATE medicion SET respuesta = %s WHERE idmedicion = %s"; cursor.execute(sql, (respuesta_real, id_medicion)); conn.commit(); conn.close()

def guardar_comentario_medicion(id_medicion, comentario):
    conn = conectar_db(); cursor = conn.cursor()
    sql = "UPDATE medicion SET comentario = %s WHERE idmedicion = %s"; cursor.execute(sql, (comentario, id_medicion)); conn.commit(); conn.close()

def determinar_rango_etario(edad):
    if edad <= 11: return 'niño'
    elif edad <= 17: return 'teen'
    elif edad <= 64: return 'adulto'
    else: return 'anciano'


# === INTERFAZ PRINCIPAL ===
class DetectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Detector de Mentiras v2.5 (Final)")
        
        self.persona_id, self.medicion_id, self.genero = None, None, None
        self.contador, self.running, self.cam_ok = 0, False, False
        self.latest_frame, self.model = None, cargar_modelo()
        self.emotion_samples, self.emotion_lock, self.last_known_emotion = [], threading.Lock(), "neutral"
        
        self.build_ui()
        tk.Button(self.root, text="Re-entrenar Modelo de IA", command=entrenar_y_guardar_modelo).grid(row=1, column=1, pady=10, sticky="ew")
        threading.Thread(target=self.leer_emocion_cam, daemon=True).start()
        try:
            self.serial = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        except serial.SerialException as e:
            messagebox.showerror("Error de Arduino", f"No se pudo conectar al Arduino en {SERIAL_PORT}.\n\nError: {e}"); self.root.destroy(); return
        
        self.actualizar_video()

    def build_ui(self):
        main_frame = tk.Frame(self.root); main_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ns")
        frame = tk.LabelFrame(main_frame, text="Datos Persona"); frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        # RESTAURADO: Campo "DNI" en la interfaz
        labels = ["Nombre", "Apellido", "Edad", "DNI", "Comentario"]
        self.entries = {}
        for i, text in enumerate(labels):
            tk.Label(frame, text=text).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            entry = tk.Entry(frame, width=30); entry.grid(row=i, column=1, padx=5, pady=2)
            self.entries[text] = entry
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

    def set_genero(self, g): self.genero = g; messagebox.showinfo("Género",f"Género seleccionado: {g.capitalize()}")
    
    # RESTAURADO: Cargar personas mostrando el DNI
    def cargar_personas(self): 
        self.personas_dict = {f"{p[1]} {p[2]} — DNI: {p[3]}":p[0] for p in obtener_personas()}; 
        self.combo["values"] = list(self.personas_dict.keys())
        
    def seleccionar_persona(self, event): self.persona_id = self.personas_dict.get(self.combo.get()); self.boton_iniciar.config(state="normal")
    
    # RESTAURADO: Registrar persona CON DNI
    def registrar_persona(self):
        values = {lbl: entry.get() for lbl, entry in self.entries.items()}
        if not all((values["Nombre"], values["Apellido"], values["Edad"], values["DNI"], self.genero)): 
            messagebox.showerror("Faltan datos", "Nombre, Apellido, Edad, DNI y Género son obligatorios."); return
        try: 
            edad, dni = int(values["Edad"]), int(values["DNI"])
        except ValueError: 
            messagebox.showerror("Datos inválidos", "Edad y DNI deben ser números."); return
        try:
            self.persona_id = insertar_persona(values["Nombre"], values["Apellido"], edad, dni, values["Comentario"], self.genero, determinar_rango_etario(edad))
            messagebox.showinfo("Registro Exitoso", f"Persona '{values['Nombre']}' registrada.")
            self.boton_iniciar.config(state="normal"); self.cargar_personas()
            for entry in self.entries.values(): entry.delete(0, tk.END)
        except ValueError as exc: 
            messagebox.showerror("Error de Registro", str(exc))

    def iniciar(self):
        if not self.cam_ok: messagebox.showerror("Error de Cámara", "No se puede iniciar la medición."); return
        with self.emotion_lock: self.emotion_samples.clear()
        self.tabla.delete(*self.tabla.get_children())
        self.contador, self.last_known_emotion, self.medicion_id = 0, "neutral", crear_medicion(self.persona_id)
        self.running = True; self.boton_finalizar.config(state="normal"); self.boton_iniciar.config(state="disabled")
        threading.Thread(target=self.leer_sensores, daemon=True).start(); self.actualizar_tiempo()

    def leer_sensores(self):
        while self.running:
            if not self.serial.in_waiting: time.sleep(0.1); continue
            try:
                linea = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if "|" in linea:
                    pulsaciones, humedad = map(int, linea.split("|"))
                    with self.emotion_lock:
                        moda = Counter(self.emotion_samples).most_common(1)
                        dominant_emotion = moda[0][0] if moda else self.last_known_emotion
                        self.last_known_emotion = dominant_emotion; self.emotion_samples.clear()
                    
                    item_id = f"item_{time.time()}"
                    self.root.after(0, 
                        lambda p=pulsaciones, h=humedad, d=dominant_emotion, i=item_id: 
                        self.tabla.insert("", "end", iid=i, values=(d, p, h))
                    )
                    
                    guardar_dato(self.medicion_id, dominant_emotion, pulsaciones, humedad)
            except Exception as e: print(f"Error procesando datos del serial: {e}")

    def leer_emocion_cam(self):
        cap = cv2.VideoCapture(CAM_INDEX)
        if not cap.isOpened(): print(f"Cámara en índice {CAM_INDEX} no se pudo abrir."); self.cam_ok = False; return
        self.cam_ok = True
        while True:
            if not self.root.winfo_exists(): break 
            ret, frame = cap.read()
            if ret:
                self.latest_frame = frame.copy()
                if self.running:
                    try:
                        result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False, silent=True)
                        emotion = result[0]['dominant_emotion']
                        with self.emotion_lock: self.emotion_samples.append(emotion)
                    except Exception: pass
            time.sleep(0.1) 
        cap.release(); print("Hilo de cámara finalizado.")

    def finalizar(self):
        self.running = False; self.boton_finalizar.config(state="disabled"); self.boton_iniciar.config(state="normal")
        popup = tk.Toplevel(self.root); popup.title("Finalizar Medición"); popup.geometry("400x350"); popup.grab_set(); is_calibracion_var=tk.BooleanVar()
        def on_calibracion_toggle():
            if is_calibracion_var.get(): respuesta_label.pack(pady=5); combo_respuesta_real.pack(pady=5); btn_guardar.config(text="Guardar Calibración")
            else: respuesta_label.pack_forget(); combo_respuesta_real.pack_forget(); btn_guardar.config(text="Predecir y Guardar")
        tk.Checkbutton(popup,text="Es una medición de CALIBRACIÓN",variable=is_calibracion_var,command=on_calibracion_toggle).pack(pady=10); respuesta_label=tk.Label(popup,text="La respuesta real del sujeto fue:"); combo_respuesta_real=ttk.Combobox(popup,state="readonly",values=["verdad","mentira"]); tk.Label(popup,text="Comentario (opcional):").pack(pady=5); comentario_box=tk.Text(popup,height=5,width=40); comentario_box.pack(pady=5)
        def guardar_y_cerrar():
            comentario = comentario_box.get("1.0", tk.END).strip()
            if is_calibracion_var.get():
                respuesta_real = combo_respuesta_real.get();
                if not respuesta_real: messagebox.showerror("Error", "Debes seleccionar 'verdad' o 'mentira'."); return
                finalizar_medicion(self.medicion_id, "calibracion"); guardar_respuesta_real(self.medicion_id, respuesta_real)
                if comentario: guardar_comentario_medicion(self.medicion_id, comentario)
                messagebox.showinfo("Calibración Guardada", "Datos guardados. Re-entrena el modelo para aplicar los cambios."); popup.destroy()
            else:
                self.model = cargar_modelo();
                if self.model is None: messagebox.showerror("Error", "No hay un modelo de IA entrenado."); return
                finalizar_medicion(self.medicion_id, "prediccion"); datos_actuales = [self.tabla.item(i)["values"] for i in self.tabla.get_children()]
                resultado = predecir_con_modelo(datos_actuales, self.model); guardar_resultado(self.medicion_id, resultado)
                if comentario: guardar_comentario_medicion(self.medicion_id, comentario)
                messagebox.showinfo("Predicción de IA", f"La predicción del modelo es: {resultado.upper()}"); popup.destroy()
        btn_guardar = tk.Button(popup, text="Predecir y Guardar", command=guardar_y_cerrar); btn_guardar.pack(pady=10); self.root.wait_window(popup)

    def actualizar_video(self):
        if self.latest_frame is not None:
            img = cv2.cvtColor(self.latest_frame, cv2.COLOR_BGR2RGB); img_pil = Image.fromarray(img)
            img_pil.thumbnail((400, 300)); img_tk = ImageTk.PhotoImage(image=img_pil)
            self.video_label.imgtk = img_tk
            self.video_label.configure(image=img_tk)
        if self.root.winfo_exists():
            self.root.after(30, self.actualizar_video)

    def actualizar_tiempo(self):
        if self.running and self.root.winfo_exists():
            self.contador += 1; self.tiempo_label.config(text=f"Tiempo: {self.contador}s"); self.root.after(1000, self.actualizar_tiempo)

if __name__ == "__main__":
    root = tk.Tk()
    app = DetectorApp(root)
    root.mainloop()