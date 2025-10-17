import cv2
from fer import FER
import numpy as np

def main():
    cap = cv2.VideoCapture(1)
    detector = FER(mtcnn=True)

    if not cap.isOpened():
        print("No se pudo abrir la cámara")
        return

    print("Presiona 'q' para salir")

    frame_count = 0
    last_results = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Preprocesamiento para mejor detección
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        proc_frame = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)

        # Detectar emociones cada 5 frames
        if frame_count % 5 == 0:
            last_results = detector.detect_emotions(proc_frame)

        # Dibujar resultados (usando la última detección)
        for face in last_results:
            (x, y, w, h) = face["box"]
            emotions = face["emotions"]
            
            # Suavizar emociones con promedio móvil simple
            # Aquí puedes guardar estados anteriores para cada cara (más avanzado)
            
            dominant_emotion = max(emotions, key=emotions.get)
            confidence = emotions[dominant_emotion]

            # Filtrar detección si confianza es baja
            if confidence < 0.5:
                continue

            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            text = f"{dominant_emotion}: {confidence:.2f}"
            cv2.putText(frame, text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Emociones FER", frame)
        frame_count += 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
