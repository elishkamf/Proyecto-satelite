#include <SoftwareSerial.h>

#define RX_PIN 10
#define TX_PIN 11

#define LED_VERDE 13   // Indica recepción correcta
#define LED_AMARILLO 7 // Alarma de comunicación (sin datos)
#define LED_ROJO 6     // Alarma de fallo del sensor

SoftwareSerial enlace(RX_PIN, TX_PIN);

unsigned long ultimoMensaje = 0;  // Marca de tiempo del último mensaje
bool falloComunicacion = false;   // Estado de comunicación

void setup() {
  Serial.begin(9600);     // Comunicación con el PC
  enlace.begin(9600);     // Comunicación con el satélite

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);

  Serial.println("🌍 Estación Tierra lista");
}

void loop() {
  // --- Si llegan datos del satélite ---
  if (enlace.available()) {
    String linea = enlace.readStringUntil('\n');
    linea.trim();

    if (linea.length() > 0) {
      Serial.println(linea);        // Reenviar al PC
      ultimoMensaje = millis();     // Actualiza tiempo de último mensaje
      falloComunicacion = false;    // Comunicación OK
      digitalWrite(LED_AMARILLO, LOW);  // Apagar alarma comunicación

      // LED verde parpadea brevemente
      digitalWrite(LED_VERDE, HIGH);
      delay(300);
      digitalWrite(LED_VERDE, LOW);

      // Si llega mensaje de fallo del sensor
      if (linea == "FALLO_SENSOR") {
        digitalWrite(LED_ROJO, HIGH);   // Enciende LED rojo
        Serial.println("🚨 FALLO EN SENSOR DHT!");
      } else {
        digitalWrite(LED_ROJO, LOW);    // Sensor funcionando bien
      }
    }
  }

  // --- Verificación de comunicación cada ciclo ---
  if (millis() - ultimoMensaje > 5000 && !falloComunicacion) {
    falloComunicacion = true;
    digitalWrite(LED_AMARILLO, HIGH);   // Alarma comunicación
    Serial.println("⚠️ FALLO DE COMUNICACIÓN con el Satélite");
  }
}
