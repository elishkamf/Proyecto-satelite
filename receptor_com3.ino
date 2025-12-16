#include <SoftwareSerial.h>
#include <IRremote.h>


// ---------- PINES ----------
#define RX_PIN 10     // RX desde EMISOR
#define TX_PIN 11     // TX hacia EMISOR
#define LED_VERDE 13
#define LED_AMARILLO 7
#define LED_ROJO 6
#define IR_PIN 5


#define IR_CODE_TEMP   0xF30CFF00  // Modo TEMP/HUM  Boton 1
#define IR_CODE_RADAR  0xE718FF00  // RADAR  Boton 2
#define IR_CODE_ORBITA 0xA15EFF00 // ORBITAL  Boton 3
#define IR_CODE_PAUSA  0xF708FF00 // PAUSA   Boton 4
#define IR_CODE_STOP   0xE31CFF00  // STOP Boton 5




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
  Serial.begin(9600);      // USB hacia PC/Python
  emisor.begin(9600);      // Enlace serie hacia EMISOR
  IrReceiver.begin(IR_PIN, ENABLE_LED_FEEDBACK);


  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);


  Serial.println("🌍 Estación Tierra lista");


  // Enviar comando inicial (opcional) al EMISOR
  emisor.print('T');
  digitalWrite(LED_VERDE, HIGH);
  delay(500);
  digitalWrite(LED_VERDE, LOW);
}


void loop() {


  // --- 1) Reenviar comandos del PC al emisor ---
  if (Serial.available()) {
    char comando = Serial.read();
    if (comando == 'T' || comando == 'D' || comando == 'U' || comando == 'P' || comando == 'O') {
      emisor.print(comando);
    }
  }


  // --- 2) COMANDOS DESDE MANDO IR ---
  if (IrReceiver.decode()) {
    unsigned long code = IrReceiver.decodedIRData.decodedRawData;


    // Según el botón IR, enviar comando al EMISOR
    // y además mandar etiqueta IR_... a Python
    if (code == IR_CODE_TEMP) {
      emisor.print('T');
      String msg = "IR_TEMP";
      uint8_t cs = calcularChecksum(msg);
      Serial.print(msg);
      Serial.print("*");
      Serial.println(cs);
    }
    else if (code == IR_CODE_RADAR) {
      emisor.print('U');
      String msg = "IR_RADAR";
      uint8_t cs = calcularChecksum(msg);
      Serial.print(msg);
      Serial.print("*");
      Serial.println(cs);
    }
    else if (code == IR_CODE_ORBITA) {
      emisor.print('O');
      String msg = "IR_ORBITAL";
      uint8_t cs = calcularChecksum(msg);
      Serial.print(msg);
      Serial.print("*");
      Serial.println(cs);
    }
    else if (code == IR_CODE_PAUSA) {
      emisor.print('P');
      String msg = "IR_PAUSA";
      uint8_t cs = calcularChecksum(msg);
      Serial.print(msg);
      Serial.print("*");
      Serial.println(cs);
    }
    else if (code == IR_CODE_STOP) {
      emisor.print('T');
      String msg = "IR_STOP";
      uint8_t cs = calcularChecksum(msg);
      Serial.print(msg);
      Serial.print("*");
      Serial.println(cs);
    }


    IrReceiver.resume();
  }


  // --- 3) Procesar mensajes del EMISOR ---
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


    // LED verde para datos de temperatura/humedad válidos (formato h,t)
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


  // --- 4) Detección de timeout ---
  if (millis() - ultimoMensaje > 5000 && !falloComunicacion) {
    falloComunicacion = true;
    digitalWrite(LED_AMARILLO, HIGH);
  }
}



