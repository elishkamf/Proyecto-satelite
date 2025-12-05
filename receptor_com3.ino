#include <SoftwareSerial.h>


#define RX_PIN 10  
#define TX_PIN 11  
#define LED_VERDE 13    
#define LED_AMARILLO 7  
#define LED_ROJO 6      


SoftwareSerial emisor(RX_PIN, TX_PIN);


unsigned long ultimoMensaje = 0;
bool falloComunicacion = false;


// ----------- FUNCION CHECKSUM -----------
uint8_t calcularChecksum(String mensaje) {
  uint16_t suma = 0;
  for (unsigned int i = 0; i < mensaje.length(); i++) {
    suma += (uint8_t)mensaje[i];
  }
  return suma % 256;
}
// ----------------------------------------


void setup() {
  Serial.begin(9600);
  emisor.begin(9600);


  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);


  Serial.println("🌍 Estación Tierra lista");


  // Enviar comando inicial (opcional)
  emisor.print('T');
  digitalWrite(LED_VERDE, HIGH);
  delay(500);
  digitalWrite(LED_VERDE, LOW);
}


void loop() {
  // --- Reenviar comandos del PC al emisor por LoRa ---
  if (Serial.available()) {
    char comando = Serial.read();
    if (comando == 'T' || comando == 'D' || comando == 'U' || comando == 'P' || comando == 'O') {
      emisor.print(comando);
    }
  }


  // --- Procesar mensajes del emisor ---
  if (emisor.available()) {
    String linea = emisor.readStringUntil('\n');
    linea.trim();


    // Verificar checksum
    int separador = linea.lastIndexOf('*');
    if (separador == -1) {
      Serial.println("MENSAJE_DESCARTADO_SIN_CHECKSUM");
      return;
    }


    String datos = linea.substring(0, separador);
    String checksumStr = linea.substring(separador + 1);


    uint8_t csRecibido = checksumStr.toInt();
    uint8_t csCalculado = calcularChecksum(datos);


    if (csRecibido != csCalculado) {
      Serial.println("MENSAJE_CORRUPTO_DESCARTADO");
      return;
    }


    // Enviar datos válidos al PC (Python)
    Serial.println(datos);
   
    // Resetear temporizador de fallo
    ultimoMensaje = millis();
    falloComunicacion = false;
    digitalWrite(LED_AMARILLO, LOW);


    // LED verde para datos de temperatura/humedad válidos
    int comaIndex = datos.indexOf(',');
    if (comaIndex > 0) {
      String tempStr = datos.substring(comaIndex + 1);
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


    // LED rojo SOLO para fallos
    if (datos == "FALLO_SENSOR" || datos == "FALLO_ULTRASONICO") {
      digitalWrite(LED_ROJO, HIGH);
    } else {
      digitalWrite(LED_ROJO, LOW);
    }
  }


  // --- Detección de timeout ---
  if (millis() - ultimoMensaje > 5000 && !falloComunicacion) {
    falloComunicacion = true;
    digitalWrite(LED_AMARILLO, HIGH);
  }
}
