# Hardware

## Lista de materiales (prototipo)

| Componente | Recomendado | Notas |
|---|---|---|
| Computadora | **Raspberry Pi Zero 2 W** | La Zero W (ARMv6, 1 núcleo) alcanza para foto + subida, pero cualquier procesamiento local es muy lento y cada vez menos software la soporta. La Zero 2 W tiene el mismo tamaño y pinout. |
| Cámara | Camera Module 3 (estándar, no wide) | Enfoque automático hasta ~10 cm: el piso queda a 10–15 cm. Con el Module 2 hay que ajustar el foco a mano. Cable FFC para Zero (22 pines). |
| Iluminación | Anillo/tira LED blanca 5 V + MOSFET logic-level (AO3400) | Luz constante = conteo consistente sin importar la hora o el sol. Difusor para evitar reflejos en la goma. |
| Módem | SIM7600SA-H o A7670SA (bandas LATAM) | Placa USB o HAT. Verificar bandas de Claro/Personal/Movistar en la zona. Antena externa: dentro del viñedo la señal cae. |
| Corte de módem | MOSFET P o módulo de carga con enable | El módem consume ~20–30 mA en reposo y picos de 2 A; se corta fuera de la ventana de subida. |
| Temperatura | DS18B20 sumergible | GPIO4, 1-Wire, resistencia 4.7 kΩ. Ubicarlo a la sombra, no dentro de la caja. |
| Energía | Panel 10 W + regulador MPPT + batería LiFePO4 12 V 6 Ah + step-down 5 V 3 A | Ver presupuesto abajo. LiFePO4 tolera mejor el calor de enero. |
| Almacenamiento | microSD industrial 16 GB | Las SD comunes se corrompen con cortes de energía. Considerar overlayfs (raíz de solo lectura). |
| Gabinete | Caja estanca IP65 blanca | La de la foto de referencia funciona. Ventilación con prensacables + malla: en verano supera 50 °C al sol. |

## Presupuesto de energía (Pi siempre encendida)

| Consumo | Corriente a 5 V | Horas/día | Wh/día |
|---|---|---|---|
| Pi Zero 2 W reposo, Wi-Fi/HDMI apagados | ~100 mA | 24 | 12 |
| Foto + LED | ~400 mA | 0.02 | 0.04 |
| Módem durante la subida | ~500 mA prom. | 0.1 | 0.25 |
| **Total** | | | **~12.5 Wh** |

Con ~5 horas de sol efectivo en Mendoza, un panel de 10 W cubre el día con
margen, y 6 Ah a 12 V (~72 Wh) dan más de 4 días de autonomía nublada.

Optimización futura: un temporizador de encendido (Witty Pi 4 o un ATtiny
propio) que apague la Pi entre muestras baja el consumo a ~1–2 Wh/día y
permite usar un panel de 5 W y una batería chica.

## Conexionado

| Señal | GPIO (BCM) | Pin físico |
|---|---|---|
| DS18B20 datos | 4 | 7 |
| LED (gate MOSFET) | 17 | 11 |
| Alimentación módem (enable) | 27 | 13 |

## Preparación de la imagen

1. Raspberry Pi OS Lite (Bookworm, 32 bits para Zero W / 64 bits para Zero 2 W).
2. Deshabilitar HDMI y Bluetooth; dejar Wi-Fi solo para el armado en taller.
3. `sudo ./device/install.sh`
4. Configurar el APN en NetworkManager: `nmcli c add type gsm ifname '*' con-name 4g apn <apn>`.
5. Probar con `python -m vitisguard_device -v run`.
