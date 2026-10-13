# Gabinete

La idea base es la del prototipo de la foto de referencia: una **caja estanca
blanca montada arriba de una trampa delta estándar**, sostenida por dos
planchuelas atornilladas a los laterales del techo, con la cámara mirando el
piso engomado. La trampa sigue siendo la misma que usa la red de monitoreo:
se cambian piso y feromona como siempre.

```
        ┌─────────────────────┐  ← techo de sombra (chapa/PVC blanco, 2 cm de aire)
        ├─────────────────────┤
        │ Pi · módem · 5 V    │  ← caja estanca IP65 blanca
        │      [cámara]       │
        └───┬───[ventana]───┬─┘
    planchuela    LED       planchuela
           /   ·  ·  ·  ·    \
          /  trampa delta     \
         /____________________ \
         ▔▔ piso engomado ▔▔▔▔▔▔
```

## Decisiones de diseño

**Ventana de la cámara.** Agujero en el fondo de la caja con un vidrio o
acrílico pegado con silicona neutra por dentro. La lente queda pegada al
vidrio con un aro de goma espuma negra alrededor: eso evita que la luz del
LED rebote en el vidrio y aparezca en la foto.

**LED.** Por fuera de la ventana, apuntando al piso, o por dentro pero
separado de la lente por el aro de espuma. Luz difusa: un papel manteca o
acrílico opal delante del LED evita brillos sobre la goma.

**Altura.** La define el lente (ver [hardware.md](hardware.md#lente-y-altura-de-la-cámara)).
Conviene que las planchuelas tengan agujeros chinos o varias perforaciones para
ajustar la altura en el primer armado.

**Calor.** Una caja cerrada al sol en enero puede pasar los 60 °C por dentro.
- Caja blanca + techo de sombra separado ~2 cm (el aire circula entre medio).
- Respiradero con membrana (tipo Gore/ePTFE, o un prensacables con
  membrana): iguala presión y deja salir humedad sin que entre agua ni polvo.

**Condensación.** Noches frías y días calurosos empañan la ventana por dentro.
Sobres de sílica gel dentro de la caja (cambiar con cada cambio de piso) y el
respiradero de arriba. Si persiste: resistencia de 1 W pegada a la ventana
encendida unos minutos antes de la foto.

**Cables.** Prensacables PG7/PG9 para el cable del panel, el del sensor y la
antena. Todo entra por abajo o por los costados, nunca por arriba.

**Batería.** En caja aparte, a la sombra o en el suelo junto al poste: le
saca calor y peso a la trampa, y se cambia sin tocar la electrónica.

**Montaje en el viñedo.** A la altura de los racimos, colgado del alambre del
espaldero o de un poste, como se colocan las trampas de la red. El panel en
un poste aparte, orientado al norte.

## Preguntas para el autor del prototipo

Ya hay contacto con la persona que armó la trampa de la foto. Vale la pena
preguntarle:

- ¿Qué cámara y lente usó, y a qué altura queda sobre el piso? ¿Entra el piso entero?
- ¿Cómo resolvió la iluminación y los reflejos en la ventana o en la goma?
- ¿Tuvo problemas de condensación o de temperatura dentro de la caja en verano?
- ¿Cómo lo alimentó (solar, batería, red) y cuánto duró la batería?
- ¿Qué conectividad usó y cómo fue la señal dentro del viñedo?
- ¿Cuántas fotos sacó en campo? ¿Las tiene y las compartiría? Serían oro para
  validar y reentrenar el modelo.
- ¿Las polillas se ven bien después de varios días en la goma, o se degradan?
  ¿Cada cuánto cambiaba el piso?
- ¿Lo probó junto a ISCAMEN o algún técnico? ¿Qué le pidieron?
- ¿Qué cambiaría si lo hiciera de nuevo?
