import subprocess
import os
import pandas as pd

# Ruta al ejecutable de OpenFace
openface_path = os.path.expanduser("~/OpenFace/build/bin/FeatureExtraction")

# Ruta al archivo de salida temporal
output_csv = "output_openface.csv"

# Entrada: podés poner un video o usar la webcam (remplazá con tu archivo si querés)
input_video = "video_entrada.mp4"  # o poné "" para usar webcam

# Comando para ejecutar OpenFace
cmd = [
    openface_path,
    "-f", input_video,                      # Usá "-device 0" si querés webcam
    "-out_dir", ".",                       # Salida en directorio actual
    "-of", output_csv,                     # Nombre del archivo CSV
    "-aus", "-2Dfp", "-pose", "-gaze"      # Qué features extraer
]

# Ejecutar OpenFace
print("Ejecutando OpenFace...")
subprocess.run(cmd)

# Cargar CSV con pandas y mostrar un resumen
if os.path.exists(output_csv):
    df = pd.read_csv(output_csv)
    print("✅ Análisis completado. Mostrando columnas de emociones:")
    print(df.filter(like='AU').head())  # Muestra solo columnas de Action Units (emociones)

    # Podés hacer más análisis con df aquí
else:
    print("❌ No se encontró el archivo de salida. ¿Falló OpenFace?")
