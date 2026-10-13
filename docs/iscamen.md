# Contexto e ideas para trabajar con ISCAMEN

## El problema

Lobesia botrana se detectó en Mendoza en 2010 y desde entonces ISCAMEN
(Instituto de Sanidad y Calidad Agropecuaria Mendoza) lleva adelante el programa
de control: red de trampas delta con feromona, distribución de difusores de
confusión sexual, avisos de tratamiento por zona y control de traslado de uva.

La polilla tiene en general 3 vuelos por temporada en Mendoza (a veces un 4.º
parcial) y el momento de tratar depende de cuándo arranca cada vuelo. Hoy eso se
sabe recorriendo trampas, típicamente una vez por semana: el dato llega tarde y
cuesta horas-hombre y combustible.

## Qué aporta VitisGuard

1. **Datos diarios** en lugar de semanales: el inicio de un vuelo se ve días antes.
2. **Menos recorridas**: el técnico solo va a cambiar piso y feromona.
3. **Grados-día por trampa**: con un sensor en cada trampa el modelo fenológico
   usa la temperatura del cuartel, no la de una estación a kilómetros.
4. **Foto como evidencia**: cada conteo queda auditado con la imagen.
5. **Control de eficacia de la confusión sexual**: en cuarteles con difusores las
   capturas deberían caer casi a cero; una trampa que sigue capturando marca
   una falla (difusores agotados, bordes, mala cobertura).

## Ideas para proponer

- **Piloto**: 10–20 trampas en paralelo a trampas convencionales de la red de
  ISCAMEN, en dos oasis distintos (ej. Este y Valle de Uco), una temporada
  completa. Medir concordancia del conteo automático contra el manual.
- **Dataset compartido**: las fotos etiquetadas por los técnicos (Lobesia vs.
  otros insectos) son lo que permite pasar del conteo clásico a un detector
  entrenado. Es el activo más valioso del proyecto.
- **Calibración del modelo**: con las series históricas de capturas y
  temperatura de ISCAMEN se ajustan los grados-día de cada vuelo por oasis
  (`server/vitisguard_server/phenology.py` tiene valores orientativos).
- **Integración con avisos**: exportar los datos al formato que use ISCAMEN para
  sus avisos de tratamiento, o una API que puedan consultar.
- **Temperatura sin sensor**: cruzar con la red de estaciones meteorológicas de la
  provincia (DACC) para trampas sin DS18B20 o para validar.
- **Alertas a productores**: aviso por WhatsApp/Telegram cuando la trampa de su
  zona supera el umbral, con la foto adjunta.

## A validar con ISCAMEN (no lo sabemos todavía)

- Umbral de capturas que dispara acciones según zona y momento de la temporada.
- Frecuencia de cambio de piso y feromona que usan en la red.
- Grados-día de referencia por vuelo para Mendoza.
- Si la confusión sexual en la zona del piloto afecta la interpretación.
