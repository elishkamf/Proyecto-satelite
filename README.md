# Proyecto-satelite Grupo 10
Somos Germán, Yassin y Elishka y en este repositorio presentamos nuestro trabajo sobre la implementación de un sistema satelital compuesto por un satélite y una estación de tierra.

## Versión 1:

La Versión 1 del proyecto establece la base del sistema de monitoreo entre el Arduino satélite y la estación de tierra. En esta primera fase se incluyen los componentes esenciales: medir la temperatura y la humedad con un sensor DHT11, enviar estos datos mediante comunicación entre arduinos, y mostrarlos en tiempo real en una interfaz gráfica hecha en Python.
Esta versión también permite controlar el envío de datos, pudiendo detenerlo y reanudarlo, y cuenta con alertas que avisan si hay problemas con el sensor o con la comunicación entre los Arduinos. Además, se hicieron pruebas para comprobar que tanto el sensor como la comunicación funcionen correctamente.
La estructura creada en esta versión servirá como base para añadir funciones más avanzadas en las próximas fases del proyecto.

#### Video:

[Haz click Aquí si quieres ver nuestro video de la versión 1](https://youtu.be/voEOzH-IipM) 


## Versión 2:

En la versión 2 del proyecto se añaden nuevas funciones al sistema de monitoreo. Ahora el satélite puede medir la distancia a objetos cercanos usando un sensor ultrasónico, y se calcula el promedio de los últimos 10 valores de temperatura para generar alertas cuando sea necesario.

#### Video:

[Haz click Aquí si quieres ver nuestro video de la versión 2](https://youtu.be/EIzg0IGf5FU)
