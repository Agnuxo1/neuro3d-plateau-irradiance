# CONTRATO-001 — Irradiancia urbana sobre PLATEAU: Neuro3D frente a control profesional

Registrado **antes** de ejecutar cualquier medición, 2026-10-30, por el agente del
concurso PLATEAU AWARD 2026. Las cifras que salgan se publican tal cual, positivas
o negativas.

## Escenario

- Datos: Project PLATEAU, Hiroshima 2022 (v3), CityGML LOD2, malla de 3.er nivel
  `51324376` (centro de Hiroshima, zona del Parque Memorial de la Paz).
  1190 edificios, 46 862 triángulos (41 778 con semántica LOD2, 5 084 de
  `lod1Solid` para edificios sin LOD2). Licencia PLATEAU respetada; el conjunto
  **no** se republica.
- Magnitud medida: irradiación solar anual de cielo claro sobre cada superficie,
  kWh/m²/año, separada en haz directo y difusa del cielo.
- Modelo de radiación idéntico en ambos motores: posición solar NOAA, cielo claro
  de Hottel con la correlación difusa de Liu–Jordan, cúpula isótropa de Tregenza
  de 145 parches, días representativos (día 15 de cada mes) con cada hora de luz
  pesada por los días del mes. **Es un modelo de cielo claro, no datos
  meteorológicos medidos**, y así se declara en todas las figuras.
- Sin interreflexión en ninguno de los dos motores: la ciudad es un cuerpo
  lambertiano negro. La comparación aísla el sombreado y la visibilidad del cielo.
- Las dos ejecuciones comparten máquina (carril CPU de server-ia, 16 núcleos),
  mismos pasos temporales y misma geometría.

## Motores

- **Neuro3D (tecnología propia).** Por cada dirección de luz se vuelca la escena
  en un búfer de profundidad ortográfico (splat de puntos muestreados por área) y
  todos los puntos de consulta se prueban contra el búfer en una sola comparación
  vectorizada. Una dirección cuesta un `scatter_reduce` más un `gather`,
  independientemente de cuántas superficies ocluyan. Calcula los 46 862 triángulos.
- **Control profesional.** Blender Cycles 4.5.9, trazado de caminos, misma
  geometría y mismas fuentes; se evalúa por *baking* del paso difuso
  directo+indirecto sobre sondas lambertianas de albedo 1, de donde la
  irradiancia es π veces el valor horneado. Se evalúa sobre una muestra
  estratificada de ~900 triángulos (clase semántica × tres bandas de altura).

## Control del control (calibración absoluta)

Una sonda horizontal adicional se coloca 200 m sobre la ciudad, donde nada la
puede sombrear. Su irradiancia horneada debe coincidir con el valor analítico
`DNI·sin(altura) + DHI` integrado en el año.

- **C1:** error relativo de calibración ≤ 3 %. Si falla, la comparación no es
  válida y se declara así; no se maquilla.

## Hipótesis y umbrales

- **H1 (exactitud).** Sobre las sondas, la irradiación anual total del motor
  propio frente al control cumple:
  - R² ≥ 0,90;
  - sesgo medio |E[propio − control]| ≤ 10 % de la media del control;
  - error relativo mediano ≤ 15 % y percentil 95 ≤ 40 %.
- **H2 (coste).** En la misma máquina, mismos pasos temporales, el motor propio
  gasta al menos 20 veces menos segundos por superficie calculada que el control.
  Se compara segundos/superficie: el propio sobre 46 862 superficies, el control
  sobre las ~900 sondas.
- **H3 (utilidad urbana).** El mapa resultante distingue superficies con y sin
  sombra urbana: la pérdida media por sombreado del distrito frente al caso sin
  obstáculos es ≥ 10 %, y la distribución del factor de visión de cielo cubre al
  menos el rango 0,2–0,9. Es una comprobación de que el problema no es trivial,
  no una validación de exactitud.

## Criterios de decisión

- H1 y C1 se cumplen → el motor propio se declara validado frente al control en
  este distrito y se usa como núcleo de la obra presentada.
- C1 falla → se corrige el control antes de afirmar nada.
- H1 falla → se publica el fallo, se declara el motor propio como aproximación
  rápida no validada y la obra presentada explica el límite medido. No se
  presenta como exacto.
- H2 falla → se retira toda afirmación de velocidad.

## Lo que este contrato **no** demuestra

- Nada sobre irradiación real medida en Hiroshima: no hay datos meteorológicos ni
  medidas de campo.
- Nada sobre exactitud fuera de este distrito, ni con interreflexión, ni con
  vegetación, ni con terreno (se asume el terreno plano implícito en la geometría
  del teselado; no se carga el modelo de relieve `dem`).
- Nada sobre precisión de Cycles como verdad absoluta: Cycles es el control
  profesional, con su propio ruido de muestreo, declarado por el número de
  muestras.

---

# ADENDA, 2026-10-31 (no modifica lo registrado arriba)

Una revisión independiente previa (`REVISION_COG_VERIFIER.md`, hecha con un
subagente verificador y **declarada no equivalente a la auditoría de Codex**)
encontró dos defectos en la comparación de la primera medición. Se corrigen aquí
y se vuelve a medir; los números originales quedan en `experiments/LOG.md`.

1. **El cielo no era el mismo en los dos motores.** El fondo uniforme de Blender
   ilumina desde la esfera completa, mientras que el motor propio integra solo la
   hemisfera superior. En el control sin ciudad, una superficie vertical recibía
   ×1,30 en Cycles. Corrección: se añade al control un disco negro de 20 km de
   radio a la cota mínima del teselado, que bloquea la mitad inferior del cielo
   igual que lo haría el suelo. Las superficies horizontales no se ven afectadas,
   y por eso la calibración C1 seguía pasando.
2. **El veredicto de H1 se estaba leyendo sobre un subconjunto.** El contrato no
   excluía sondas; el código filtraba las que el control deja por debajo de
   1 kWh/m²·año (13 % de la muestra). A partir de ahora el veredicto registrado
   se calcula sobre **las 900 sondas**, y el subconjunto se publica aparte y
   etiquetado como posterior al contrato.

Además se añade una medida de **carga igual**: el motor propio ejecutado sobre
exactamente las mismas 900 superficies y las mismas direcciones, para que la
comparación de coste no mezcle «coste amortizado en todo el distrito» con
«coste de evaluar las mismas superficies».

Estas tres cosas hacen la comparación más exigente para la tecnología propia, no
menos. Lo que salga se publica igual.
