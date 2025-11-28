#include "DFRobot_Heartrate.h"
 
#define heartratePin A2  // Pin compartido para ambos sensores, cambia si necesitas
int sensorPin = A0;
 
DFRobot_Heartrate heartrate(ANALOG_MODE); ///< ANALOG_MODE o DIGITAL_MODE
 
int humedad;
int porcentaje;
 
unsigned long lastMeasureTime = 0;
const unsigned long interval = 5000; // Se mantiene tu intervalo de 5 segundos
unsigned long beatSum = 0;
int beatCount = 0;
 
void setup() {
  Serial.begin(115200);
  Serial.println("Monitor iniciado"); // Se mantiene tu mensaje original
}
 
void loop() {
  // === LECTURA DE HUMEDAD (Tu lógica original sin cambios) ===
  humedad = analogRead(sensorPin);
  porcentaje = map(humedad, 1023, 0, 0, 100);  // Mapeo invertido
 
  // === PRIMER CAMBIO: Se eliminan todas las líneas de texto de la humedad ===
  // Serial.print("Valor sensor: ");
  // ... (todas las líneas de texto descriptivo han sido borradas)
 
  // === LECTURA DE RITMO CARDIACO (Tu lógica original sin cambios) ===
  uint8_t rateValue = heartrate.getValue(heartratePin);
 
  if (rateValue > 0) {
    beatSum += (unsigned long)rateValue;
    beatCount++;
  }
 
  // === BLOQUE DE ENVÍO (CON EL CAMBIO DE FORMATO) ===
  if (millis() - lastMeasureTime >= interval) {
    int muestra = 0; // Se define aquí para tener un valor si beatCount es 0
    if (beatCount > 0) {
      int avgBPM = beatSum / beatCount;
      muestra = avgBPM / 1.60;  // Tu cálculo de muestra se mantiene
    }
 
    // === SEGUNDO CAMBIO: En lugar del texto, se imprime el formato para Python ===
    Serial.print(muestra);
    Serial.print("|");
    Serial.println(porcentaje);
 
    // Reiniciar contadores (Tu lógica original sin cambios)
    beatSum = 0;
    beatCount = 0;
    lastMeasureTime = millis();
  }
 
  // Se mantiene tu delay original para que la medición sea exactamente como antes
  delay(5000);
}