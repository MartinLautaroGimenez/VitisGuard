# Hardware

Pensado para lo que se consigue en Argentina (Mercado Libre) sin importar.

## Lista de materiales (prototipo)

| Componente | Elegido | Notas |
|---|---|---|
| Computadora | **Raspberry Pi Zero W** | Solo saca la foto y la sube; el modelo corre en el servidor. Si aparece una Zero 2 W sirve igual, mismo pinout. |
| Cámara | **OV5647 (Camera v1.3 / clon) con lente M12** | La más fácil de conseguir. Preferir la versión con lente rosca M12 intercambiable (ver "Lente y altura"). Cable FFC para Zero (22 a 15 pines). |
| Iluminación | Anillo o tira LED blanca 5 V + MOSFET logic-level (AO3400 o IRLZ44N) | Luz constante = conteo consistente a cualquier hora. Difusor para evitar reflejos en la goma. |
| Módem | SIM7600SA-H o A7670SA (bandas LATAM) | Placa USB o HAT. Verificar bandas del operador en la zona. Antena externa: dentro del viñedo la señal cae. |
| Corte de módem | MOSFET P o módulo de carga con enable | El módem consume en reposo y tiene picos de 2 A; se corta fuera de la ventana de subida. |
| Sensor | **DHT22 (AM2302)** | Temperatura + humedad. Va **afuera** de la caja, en un protector de radiación. Ver "DHT22 vs DS18B20". |
| Energía | Panel 10 W + regulador + batería LiFePO4 12 V 6 Ah + step-down 5 V 3 A | Ver presupuesto abajo. LiFePO4 tolera mejor el calor de enero. |
| Almacenamiento | microSD industrial / "High Endurance" 16 GB | Las comunes se corrompen con cortes de energía. |
| Gabinete | Caja estanca IP65 blanca | Ver [gabinete.md](gabinete.md). |

## Lente y altura de la cámara

El piso de la trampa tiene que entrar entero en la foto. El campo de visión
depende del lente y de la altura a la que queda la cámara sobre el piso:

| Lente (OV5647) | Campo horizontal | Altura para cubrir 20 cm de ancho |
|---|---|---|
| Estándar 3.6 mm | ~54° | ~20 cm |
| M12 2.8 mm | ~66° | ~15 cm |
| M12 2.1 mm | ~82° | ~11.5 cm |
| Ojo de pez 160° | — | Demasiada distorsión en los bordes, evitar |

Medir el piso real de las trampas que se usen (el ancho de 20 cm es un
ejemplo). Con la lente estándar la caja tiene que ir más alta que en la foto
de referencia; con un M12 de 2.8 mm entra a la altura del techo de la trampa.

Con 2592 px sobre 20 cm, una polilla de 8 mm ocupa ~100 px: sobra resolución.
Enfocar a mano a la altura final y fijar la lente con una gota de pegamento.

## DHT22 vs DS18B20

| | DHT22 | DS18B20 |
|---|---|---|
| Mide | Temperatura y humedad | Solo temperatura |
| Precisión de temperatura | ±0.5 °C | ±0.5 °C |
| Robustez a la intemperie | Media: la humedad y el polvo lo degradan en 1–3 temporadas | Alta: versión sumergible en vaina de acero |
| Lectura en la Pi Zero W | Con el driver del kernel (`dtoverlay=dht11`) anda bien; desde Python puro falla seguido | Muy confiable (1-Wire) |

Para grados-día alcanza con la temperatura, pero la humedad suma: con calor
y aire seco baja la viabilidad de huevos y larvas de Lobesia, y sirve para
otros modelos (botrytis, peronóspora). **Elegimos DHT22** y el software
también soporta DS18B20 (`sensor: ds18b20` en el config). Si el DHT22 da
problemas en el campo, una alternativa robusta con humedad es el SHT31/SHT40
por I²C.

Importante: el sensor **no va dentro de la caja** (al sol supera por mucho la
temperatura del aire). Va a la sombra, debajo de la trampa, dentro de un
protector de radiación (pila de platitos plásticos blancos separados).

## Presupuesto de energía (Pi siempre encendida)

| Consumo | Corriente a 5 V | Horas/día | Wh/día |
|---|---|---|---|
| Pi Zero W reposo, HDMI/Bluetooth apagados | ~80 mA | 24 | ~10 |
| Foto + LED | ~400 mA | 0.02 | 0.04 |
| Módem durante la subida | ~500 mA prom. | 0.1 | 0.25 |
| **Total** | | | **~10.5 Wh** |

Con ~5 horas de sol efectivo en Mendoza, un panel de 10 W cubre el día con
margen, y 6 Ah a 12 V (~72 Wh) dan más de 5 días de autonomía nublada.

Optimización futura: un temporizador de encendido (ATtiny o RTC con alarma
controlando un MOSFET) que apague la Pi entre muestras baja el consumo a
~1–2 Wh/día y permite un panel y una batería más chicos.

## Conexionado

| Señal | GPIO (BCM) | Pin físico |
|---|---|---|
| DHT22 datos (pull-up 10 kΩ a 3.3 V) | 4 | 7 |
| LED (gate MOSFET) | 17 | 11 |
| Alimentación módem (enable) | 27 | 13 |

## Preparación de la imagen

1. Raspberry Pi OS Lite (Bookworm, 32 bits: la Zero W es ARMv6).
2. Deshabilitar HDMI y Bluetooth; dejar Wi-Fi solo para el armado en taller.
3. `sudo ./device/install.sh` (habilita el driver del DHT22 y la OV5647).
4. Configurar el APN en NetworkManager: `nmcli c add type gsm ifname '*' con-name 4g apn <apn>`.
5. Probar con `python -m vitisguard_device -v run`.
