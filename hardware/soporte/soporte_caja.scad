// VitisGuard — soporte de la caja estanca sobre la trampa delta.
//
// Reemplaza las planchuelas del prototipo de referencia: se imprimen DOS
// piezas iguales, una a cada lado. Cada una tiene:
//   - ala superior: se atornilla al fondo de la caja (ranuras para ajustar)
//   - montante: define la altura de la cámara sobre la trampa
//   - pata inclinada: se atornilla al lateral de la trampa (ranuras para ajustar)
//
//            caja estanca
//   ═══════════════════════════════
//      ▔▔▔▔▔▔┓            ┏▔▔▔▔▔▔    ← ala superior
//            ┃  montante  ┃
//            ╲            ╱          ← pata (ángulo del lateral de la trampa)
//             ╲  trampa  ╱
//
// MEDIDAS DE PRUEBA: reemplazar por las reales y volver a exportar:
//   openscad -o soporte_caja.stl -D 'parte="imprimir"' soporte_caja.scad
//   openscad -o ensamble.png -D 'parte="ensamble"' soporte_caja.scad
//
// Material: PETG o, mejor, ASA. El PLA se ablanda al sol de Mendoza.

/* [Qué mostrar] */
parte = "ensamble"; // [imprimir, pieza, ensamble]

/* [Trampa delta] */
// Ángulo del lateral de la trampa respecto de la horizontal (°)
angulo_lateral = 60;
// Ancho del techo plano de la trampa, de lateral a lateral (mm)
ancho_techo = 110;
// Largo de la trampa (solo para la vista de ensamble)
largo_trampa = 250;
// Altura de la trampa (solo para la vista de ensamble)
alto_trampa = 120;

/* [Caja estanca] */
caja_ancho = 120;
caja_largo = 120;
caja_alto = 90;

/* [Soporte] */
espesor = 4;
// Ancho de cada pieza, a lo largo de la trampa
ancho = 40;
// Largo del ala que va bajo la caja
largo_ala = 40;
// Separación extra entre caja y techo: sube la cámara
alto_montante = 20;
largo_pata = 70;
// Refuerzo triangular en las esquinas
refuerzo = 8;

/* [Tornillería] */
// 4.5 = paso para M4
diam_tornillo = 4.5;
// Recorrido de las ranuras para ajustar
largo_ranura = 14;

$fn = 40;
e = 0.01;

// Perfil 2D de una pieza (x hacia afuera de la trampa, y hacia arriba).
// El origen es el borde interno del ala; y = 0 es donde apoya la caja.
x_mont = largo_ala - espesor;          // cara interna del montante
y_base = -espesor - alto_montante;     // pie del montante

module perfil() {
    // ala superior
    translate([0, -espesor]) square([largo_ala, espesor]);
    // montante
    translate([x_mont, y_base]) square([espesor, alto_montante + espesor]);
    // pata: su cara inferior apoya sobre el lateral de la trampa
    translate([x_mont, y_base]) rotate(-angulo_lateral) square([largo_pata, espesor]);
    // codo montante-pata engrosado (es donde se concentra el esfuerzo)
    hull() {
        translate([x_mont, y_base]) square([espesor, refuerzo]);
        translate([x_mont, y_base]) rotate(-angulo_lateral) square([refuerzo, espesor]);
    }
    // refuerzo ala-montante
    polygon([[x_mont + e, -espesor + e], [x_mont - refuerzo, -espesor + e],
             [x_mont + e, -espesor - refuerzo]]);
}

module ranura(largo) {
    hull() {
        cylinder(d = diam_tornillo, h = espesor * 3, center = true);
        translate([largo, 0, 0]) cylinder(d = diam_tornillo, h = espesor * 3, center = true);
    }
}

// Pieza en coordenadas de montaje: x afuera, y a lo largo de la trampa, z arriba.
module pieza() {
    difference() {
        rotate([90, 0, 0]) linear_extrude(height = ancho, center = true) perfil();

        // ranuras del ala (tornillos a la caja)
        ala_libre = x_mont - refuerzo;
        for (y = [-ancho / 4, ancho / 4])
            translate([(ala_libre - largo_ranura) / 2, y, -espesor / 2])
                ranura(min(largo_ranura, ala_libre - diam_tornillo * 1.5));

        // ranuras de la pata (tornillos a la trampa), en la mitad inferior
        translate([x_mont, 0, y_base]) rotate([0, angulo_lateral, 0])
            for (y = [-ancho / 4, ancho / 4])
                translate([largo_pata * 0.5, y, espesor / 2]) ranura(largo_ranura);
    }
}

// Para imprimir: el perfil acostado en la cama. Las capas siguen el perfil,
// que es la dirección en que trabaja la pieza: mucho más fuerte que acostada
// sobre el ala, y sin soportes.
module para_imprimir() {
    translate([0, 0, ancho / 2]) rotate([-90, 0, 0]) pieza();
}

module ensamble() {
    // centro de la trampa en x = 0; los laterales pasan por el pie del montante
    dx = ancho_techo / 2 - x_mont;
    for (s = [1, -1]) mirror([s < 0 ? 1 : 0, 0, 0])
        translate([dx, 0, 0]) color("orange") pieza();

    // caja estanca
    %translate([-caja_ancho / 2, -caja_largo / 2, 0]) cube([caja_ancho, caja_largo, caja_alto]);

    // trampa: techo plano y laterales inclinados
    lat = alto_trampa / sin(angulo_lateral);
    %translate([0, 0, y_base]) {
        translate([-ancho_techo / 2, -largo_trampa / 2, -1]) cube([ancho_techo, largo_trampa, 1]);
        for (s = [1, -1]) mirror([s < 0 ? 1 : 0, 0, 0])
            translate([ancho_techo / 2, 0, 0]) rotate([0, angulo_lateral, 0])
                translate([0, -largo_trampa / 2, -1]) cube([lat, largo_trampa, 1]);
    }
}

// Datos útiles al cambiar medidas (aparecen en la consola de OpenSCAD).
hueco_camara = ancho_techo - 2 * largo_ala + 2 * espesor;
echo(str("Hueco libre entre alas para la ventana de la cámara: ", hueco_camara, " mm"));
echo(str("La caja queda ", espesor + alto_montante, " mm por encima del techo de la trampa"));
assert(hueco_camara > 25, "Las alas tapan la cámara: achicar largo_ala o agrandar ancho_techo");
assert(ancho_techo / 2 + espesor <= caja_ancho / 2 + 10, "Los montantes quedan muy afuera de la caja");

if (parte == "imprimir") para_imprimir();
else if (parte == "pieza") pieza();
else ensamble();
