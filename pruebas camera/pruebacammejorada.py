import cv2
from deepface import DeepFace
from collections import deque, Counter
import time

def main():
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("No se pudo abrir la cámara")
        return

    emotion_buffer = deque(maxlen=30)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    last_analysis_time = 0
    analysis_interval = 0.5  # Análisis cada 0.5 segundos

    cv2.namedWindow("Camara con emociones", cv2.WINDOW_NORMAL)
    print("Presiona 'q' para salir")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("No se pudo leer frame")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            face_img = frame[y:y+h, x:x+w]
            face_img = cv2.resize(face_img, (224, 224))  # Tamaño estándar

            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

            current_time = time.time()
            if current_time - last_analysis_time > analysis_interval:
                try:
                    result = DeepFace.analyze(face_img, actions=['emotion'], enforce_detection=False)
                    emotion = result[0]['dominant_emotion'] if isinstance(result, list) else result['dominant_emotion']
                    emotion_buffer.append(emotion)
                    last_analysis_time = current_time

                except Exception as e:
                    print(f"Error en análisis: {e}")

            if emotion_buffer:
                most_common_emotion = Counter(emotion_buffer).most_common(1)[0][0]
                print(f"Emoción detectada (suavizada): {most_common_emotion}")
                cv2.putText(frame, f"Emocion: {most_common_emotion}", (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
        else:
            print("No se detectó rostro")

        cv2.imshow("Camara con emociones", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
