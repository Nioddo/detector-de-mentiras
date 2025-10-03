import cv2
from deepface import DeepFace
from collections import deque, Counter

def main():
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("No se pudo abrir la cámara")
        return

    emotion_buffer = deque(maxlen=15)  # Buffer para 15 frames aprox 0.5 seg si 30 fps

    print("Presiona 'q' para salir")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer frame")
            break

        try:
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            if isinstance(result, list):
                result = result[0]

            emotion = result['dominant_emotion']
            emotion_buffer.append(emotion)

            # Obtener la emoción más frecuente del buffer
            most_common_emotion = Counter(emotion_buffer).most_common(1)[0][0]

            print(f"Emoción detectada filtrada: {most_common_emotion}")

            cv2.putText(frame, f"Emocion: {most_common_emotion}", (50, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2, cv2.LINE_AA)

        except Exception as e:
            print(f"Error en análisis: {e}")

        cv2.imshow("Camara con emociones", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
