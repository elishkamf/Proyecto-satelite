#include <SoftwareSerial.h>


// Comunicación con el Arduino Emisor
#define RX_PIN 10       // Conectado al TX del emisor
#define TX_PIN 11       // Conectado al RX del emisor


#define LED_VERDE 13    // Indica recepción correcta de datos de Temp/Hum
#define LED_AMARILLO 7  // Alarma de comunicación (sin datos)
#define LED_ROJO 6      // Alarma de fallo del sensor


SoftwareSerial emisor(RX_PIN, TX_PIN);  // Comunicación con Arduino emisor


unsigned long ultimoMensaje = 0;  // Marca de tiempo del último mensaje
bool falloComunicacion = false;   // Estado de comunicación


void setup() {
  Serial.begin(9600);
  emisor.begin(9600);


  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);


  Serial.println("🌍 Estación Tierra lista");


  // Enviar comando inicial al emisor
  emisor.print('T');
  digitalWrite(LED_VERDE, HIGH);
  delay(500);
  digitalWrite(LED_VERDE, LOW);
}


void loop() {
  // --- Cambio de modo desde Python ---
  if (Serial.available()) {
    char comando = Serial.read();
    if (comando == 'T' || comando == 'D' || comando == 'U' || comando == 'P') {
      emisor.print(comando);  // Reenviar comando al emisor
    }
  }


  // --- Si llegan datos del emisor ---
  if (emisor.available()) {
    String linea = emisor.readStringUntil('\n');
    linea.trim();


    if (linea.length() > 0) {
      Serial.println(linea);        // Reenviar al PC
      ultimoMensaje = millis();     // Actualiza tiempo de último mensaje
      falloComunicacion = false;    // Comunicación OK
      digitalWrite(LED_AMARILLO, LOW);


      // ---- CONTROL DE LED VERDE ----
      // Solo se enciende si la línea contiene datos de temperatura/humedad
      int comaIndex = linea.indexOf(',');
      if (comaIndex > 0) {
        // Verificar que haya dos números
        String tempStr = linea.substring(comaIndex + 1);
        tempStr.trim();
        bool validos = true;
        for (unsigned int i = 0; i < tempStr.length(); i++) {
          char c = tempStr[i];
          if (!isDigit(c) && c != '.') validos = false;
        }
        if (validos) {
          delay(100);
          digitalWrite(LED_VERDE, HIGH);
          delay(50);
          digitalWrite(LED_VERDE, LOW);
        }
      }


      // ---- CONTROL LED ROJO ----
      if (linea == "FALLO_SENSOR" || linea == "FALLO_ULTRASONICO") {
        digitalWrite(LED_ROJO, HIGH);
      } else {
        digitalWrite(LED_ROJO, LOW);
      }
    }
  }


  // --- Verificación de comunicación ---
  if (millis() - ultimoMensaje > 5000 && !falloComunicacion) {
    falloComunicacion = true;
    digitalWrite(LED_AMARILLO, HIGH);
  }
}



