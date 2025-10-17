#include <DHT.h>

#define DHTPIN 2         // Pin del sensor DHT11
#define DHTTYPE DHT11
#define LED_VERDE 12     // LED indicador de envío correcto

DHT dht(DHTPIN, DHTTYPE);

unsigned long nextHT = 0;           // Tiempo del próximo muestreo
unsigned long nextTimeoutHT = 0;    // Tiempo límite para fallo
bool esperandoTimeout = false;      // Flag de espera por error

void setup() {
  Serial.begin(9600);
  dht.begin();
  pinMode(LED_VERDE, OUTPUT);
}

void loop() {
  // --- Cada 3 segundos tomamos una lectura ---
  if (millis() >= nextHT) {
    nextHT = millis() + 3000;
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      // Si falla, comenzamos cuenta regresiva de 5 s
      if (!esperandoTimeout) {
        esperandoTimeout = true;
        nextTimeoutHT = millis() + 5000;
      }
    } else {
      // Lectura correcta
      esperandoTimeout = false;
      Serial.print(h, 1);
      Serial.print(",");
      Serial.println(t, 1);

      // LED verde parpadea para indicar envío
      digitalWrite(LED_VERDE, HIGH);
      delay(100);
      digitalWrite(LED_VERDE, LOW);
    }
  }

  // --- Si pasan 5 s sin lectura correcta, enviamos "FALLO_SENSOR" ---
  if (esperandoTimeout && millis() >= nextTimeoutHT) {
    Serial.println("FALLO_SENSOR");
    esperandoTimeout = false;
  }
}

