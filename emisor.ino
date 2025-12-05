#include <DHT.h>
#include <Servo.h>
#include <SoftwareSerial.h>


// Pines LoRa
#define RX_PIN 10
#define TX_PIN 11
SoftwareSerial lora(RX_PIN, TX_PIN);


#define DHTPIN 2
#define DHTTYPE DHT11
#define LED_VERDE 12
#define TRIG_PIN 9
#define ECHO_PIN 8
#define SERVO_PIN 4


// Constantes para la simulación de órbita
const double G = 6.67430e-11;
const double M = 5.97219e24;
const double R_EARTH = 6371000;
const double ALTITUDE = 400000;
const double EARTH_ROTATION_RATE = 7.2921159e-5;
const double TIME_COMPRESSION = 90.0;


// Variables de la simulación
double real_orbital_period;
double r;


DHT dht(DHTPIN, DHTTYPE);
Servo servo;


unsigned long nextHT = 0;
unsigned long nextTimeoutHT = 0;
bool esperandoTimeout = false;


unsigned long nextUltrasonic = 0;
int servoPos = 0;
bool scanning = false;
bool modoOrbital = false;
int servoDirection = 1;
bool paused = false;
unsigned long lastOrbitalSend = 0;


// ---------------- FUNCION CHECKSUM ----------------
uint8_t calcularChecksum(String mensaje) {
  uint16_t suma = 0;
  for (unsigned int i = 0; i < mensaje.length(); i++) {
    suma += (uint8_t)mensaje[i];
  }
  return suma % 256;  
}
// --------------------------------------------------


void setup() {
  lora.begin(9600);   // LoRa en pines 10 y 11
  r = R_EARTH + ALTITUDE;
  real_orbital_period = 2 * PI * sqrt(pow(r, 3) / (G * M));
 
  dht.begin();
  pinMode(LED_VERDE, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
 
  servo.attach(SERVO_PIN);
  delay(500);
  servo.write(0);
  delay(500);


  digitalWrite(TRIG_PIN, LOW);
 
  lastOrbitalSend = millis();
}


void loop() {
  unsigned long currentTime = millis();


  // --- COMANDOS DEL RECEPTOR POR LoRa ---
  if (lora.available()) {
    char comando = lora.read();
   
    if (comando == 'U') {
      scanning = true;
     
      modoOrbital = false;
      paused = false;
      servoPos = 0;
      servoDirection = 1;
      servo.write(servoPos);
      nextUltrasonic = 0;
      lora.println("RADAR_INICIADO");
    }
    else if (comando == 'O') {
    modoOrbital = true;
    scanning = false;
    paused = false;
    servo.write(0);
   
    // Enviar confirmación inmediata
    String mensaje = "MODO_ORBITAL_ACTIVADO";
    uint8_t cs = calcularChecksum(mensaje);
    lora.print(mensaje);
    lora.print("*");
    lora.println(cs);
    delay(100);  // Pequeño delay
}


    else if (comando == 'P') {
      paused = !paused;
    }
    else if (comando == 'T' || comando == 'D') {
      scanning = false;
      modoOrbital = false;
      paused = false;
      servo.write(0);
      lora.println("MODO_DETENIDO");
    }
  }


  // ============================
  //      MODO ORBITAL
  // ============================
  if (modoOrbital && (currentTime - lastOrbitalSend >= 1000)) {
    simulate_orbit(currentTime, 0, 0);
    lastOrbitalSend = currentTime;
  }


  // ============================
  //   MODO TEMPERATURA/HUMEDAD
  // ============================
  if (!scanning && !modoOrbital && millis() >= nextHT) {
    nextHT = millis() + 3000;


        // 1. DESCONECTAR servo antes de leer sensor
    if (servo.attached()) {
      servo.detach();
      pinMode(SERVO_PIN, INPUT);  // Alta impedancia
      delay(10);
    }


    float h = dht.readHumidity();
    float t = dht.readTemperature();


    if (isnan(h) || isnan(t)) {
      if (!esperandoTimeout) {
        esperandoTimeout = true;
        nextTimeoutHT = millis() + 5000;
      }
    } else {
      esperandoTimeout = false;


      digitalWrite(LED_VERDE, HIGH);


      String mensaje = String(h, 1) + "," + String(t, 1);
      uint8_t cs = calcularChecksum(mensaje);
      lora.print(mensaje);
      lora.print("*");  
      lora.println(cs);
      delay(3000);


      delay(80);
      digitalWrite(LED_VERDE, LOW);
    }
  }


  // ============================
  //        MODO RADAR
  // ============================
  if (scanning && !paused && millis() >= nextUltrasonic) {


  // 2. RECONECTAR servo solo si estamos en modo radar
    if (scanning && !servo.attached()) {
      servo.attach(SERVO_PIN);
      servo.write(servoPos);  // Volver a la posición anterior
    }


    nextUltrasonic = millis() + 150;


    servoPos += servoDirection * 15;
    if (servoPos >= 180) {
      servoDirection = -1;
      servoPos = 180;
    } else if (servoPos <= 0) {
      servoDirection = 1;
      servoPos = 0;
    }
    servo.write(servoPos);


    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);


    long duration = pulseIn(ECHO_PIN, HIGH, 30000);


    if (duration <= 0) {
      String mensaje = "FALLO_ULTRASONICO";
      uint8_t cs = calcularChecksum(mensaje);
      lora.print(mensaje);
      lora.print("*");
      lora.println(cs);
      delay(3000);
    } else {
      long distance = duration * 0.034 / 2;


      String mensaje = String(servoPos) + "," + String(distance);
      uint8_t cs = calcularChecksum(mensaje);
      lora.print(mensaje);
      lora.print("*");
      lora.println(cs);
      delay(3000);
    }
  }
 
  // ============================
  //   TIMEOUT SENSOR DHT
  // ============================
  if (esperandoTimeout && millis() >= nextTimeoutHT) {
    String mensaje = "FALLO_SENSOR";
    uint8_t cs = calcularChecksum(mensaje);
    lora.print(mensaje);
    lora.print("*");
    lora.println(cs);
    delay(3000);
   
    esperandoTimeout = false;
  }
}


void simulate_orbit(unsigned long millis, double inclination, int ecef) {
    double time = (millis / 1000.0) * TIME_COMPRESSION;
    double angle = 2 * PI * (time / real_orbital_period);
    double x = r * cos(angle);
    double y = r * sin(angle) * cos(inclination);
    double z = r * sin(angle) * sin(inclination);


    if (ecef) {
        double theta = EARTH_ROTATION_RATE * time;
        double x_ecef = x * cos(theta) - y * sin(theta);
        double y_ecef = x * sin(theta) + y * cos(theta);
        x = x_ecef;
        y = y_ecef;
    }


    String mensaje = "Position: (X:" + String(x, 2) + " m, Y:" + String(y, 2) + " m, Z:" + String(z, 2) + " m)";
   
    uint8_t cs = calcularChecksum(mensaje);
    lora.print(mensaje);
    lora.print("*");
    lora.println(cs);
    delay(3000);
}
