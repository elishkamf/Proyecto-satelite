#include <DHT.h>
#include <Servo.h>

#define DHTPIN 2
#define DHTTYPE DHT11
#define LED_VERDE 12
#define TRIG_PIN 9
#define ECHO_PIN 8
#define SERVO_PIN 4

DHT dht(DHTPIN, DHTTYPE);
Servo servo;

unsigned long nextHT = 0;
unsigned long nextTimeoutHT = 0;
bool esperandoTimeout = false;

unsigned long nextUltrasonic = 0;
int servoPos = 0;
bool scanning = false;
int servoDirection = 1;
bool paused = false;

void setup() {
  Serial.begin(9600);
  dht.begin();
  pinMode(LED_VERDE, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  servo.attach(SERVO_PIN);
  delay(500);
  servo.write(0);
  delay(500);

  digitalWrite(TRIG_PIN, LOW);
}

void loop() {

  // --- COMANDOS DEL RECEPTOR ---
  if (Serial.available()) {
    char comando = Serial.read();
    
    if (comando == 'U') {           // Iniciar radar
      scanning = true;
      paused = false;
      servoPos = 0;
      servoDirection = 1;
      servo.write(servoPos);
      nextUltrasonic = 0;
      Serial.println("RADAR_INICIADO");
    }

    else if (comando == 'P') {      // Pausar radar
      paused = !paused;
    }

    else if (comando == 'T' || comando == 'D') {
      scanning = false;
      paused = false;
      servo.write(0);
      Serial.println("RADAR_DETENIDO");
    }
  }

  // ============================
  //   MODO TEMPERATURA/HUMEDAD
  // ============================
  if (!scanning && millis() >= nextHT) {
    nextHT = millis() + 3000;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (isnan(h) || isnan(t)) {
      if (!esperandoTimeout) {
        esperandoTimeout = true;
        nextTimeoutHT = millis() + 5000;
      }
    } else {
      esperandoTimeout = false;

      // SOLO AQUÍ se enciende el LED verde
      digitalWrite(LED_VERDE, HIGH);

      Serial.print(h, 1);
      Serial.print(",");
      Serial.println(t, 1);

      delay(80);
      digitalWrite(LED_VERDE, LOW);
    }
  }

  // ============================
  //        MODO RADAR
  // ============================
  if (scanning && !paused && millis() >= nextUltrasonic) {

    nextUltrasonic = millis() + 150;

    // Mover servo
    servoPos += servoDirection * 15;
    if (servoPos >= 180) {
      servoDirection = -1;
      servoPos = 180;
    } else if (servoPos <= 0) {
      servoDirection = 1;
      servoPos = 0;
    }
    servo.write(servoPos);

    // Medir distancia
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000);

    if (duration <= 0) {
      Serial.println("FALLO_ULTRASONICO");
    } else {
      long distance = duration * 0.034 / 2;

      //Solo ángulo,distancia (sin LED verde, sin IR)
      Serial.print(servoPos);
      Serial.print(",");
      Serial.println(distance);
    }

    //  Importante: EL RADAR NO TOCA EL LED VERDE
  }

  // ============================
  //   TIMEOUT SENSOR DHT
  // ============================
  if (esperandoTimeout && millis() >= nextTimeoutHT) {
    Serial.println("FALLO_SENSOR");
    esperandoTimeout = false;
  }
}
