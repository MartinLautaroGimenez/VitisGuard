# Modelo de detección

`server/models/lobesia_yolo11n_20261010.pt`: YOLO11n (Ultralytics) con una
sola clase, `Lobesia botrana`, entrenado a 960 px. El servidor lo usa si
está instalado el extra `[yolo]`. Si no, cae al conteo clásico
(`ClassicCounter`), que cuenta cualquier mancha oscura.

## Origen

- Entrenado el 10/10/2026 en otra sesión, sobre el dataset `lobesia_mix`.
- El archivo original (21 MB) era un checkpoint a mitad de entrenamiento:
  época 45 de 60, con el estado del optimizador. Acá se guarda solo con los
  pesos (5.5 MB), que es lo único que hace falta para usarlo.
- Métricas sobre su set de validación: precisión 0.96, recall 0.93,
  mAP50 0.97, mAP50-95 0.76.

## Cuidado con esas métricas

Son sobre el set de validación de `lobesia_mix`. Si ese dataset mezcla
imágenes sintéticas o fotos parecidas a las de entrenamiento, los números
son optimistas. Lo que importa es cómo anda con **fotos de nuestra trampa**:
OV5647 + LED, a la altura final, con polillas de varios días en la goma y
otros insectos mezclados.

Prueba rápida que se hizo:
- Recorte del piso de la foto de referencia: detecta bien las polillas
  visibles, con confianza de 0.2 a 0.83.
- Foto completa (con caja, cable y tornillos): aparecen algunos falsos
  positivos en el cable y los tornillos, con confianza de 0.25 a 0.43. En la
  trampa la cámara solo ve el piso, así que eso no debería pasar.
- Manchas sintéticas (las de los tests del conteo clásico): no las detecta.
  Está bien: aprendió polillas, no manchas.

Esto **no** es una validación: no sabemos si esa foto estaba en el dataset.

## Pendiente para dejarlo a punto

1. **Set de validación propio**: 100–200 fotos del prototipo en el campo,
   etiquetadas a mano (Label Studio o CVAT), que **nunca** se usen para
   entrenar.
2. **Umbral de confianza**: hoy 0.4 (`VG_MODEL_CONF`). Elegirlo con la curva
   precisión/recall del set propio.
3. **Otros insectos**: juntar fotos con moscas, otras polillas y
   restos, y agregarlas como negativos (o como clases aparte).
4. **Polillas chicas**: si al bajar a 960 px las polillas quedan muy chicas,
   evaluar inferencia por mosaicos (SAHI) o entrenar a 1280.
5. **Reentrenar** con las fotos del dispositivo real, partiendo de este modelo.
6. Guardar cada versión con fecha en `server/models/` y registrar con qué
   modelo se contó cada captura (ya se guarda en `captures.detector`).

## Licencia

Ultralytics es AGPL-3.0. Si VitisGuard se ofrece como servicio con
modificaciones y no se publica su código, hace falta la licencia comercial
de Ultralytics. Si el proyecto es abierto (AGPL compatible), no hay problema.
