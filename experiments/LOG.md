# Registro de experimentos — plateau-award

Contrato: `CONTRATO-001-irradiancia.md`, registrado antes de la primera medición.
Todas las iteraciones se midieron contra el mismo control (Blender Cycles) y el
mismo escenario (Hiroshima 2022, malla 51324376). Las que fallaron están aquí.

| id | fecha | hipótesis / cambio | config | R² | sesgo medio | err. rel. mediana | p95 | decisión |
|---|---|---|---|---|---|---|---|---|
| E01 | 2026-10-30 | Mapa de sombras por splat de puntos, búsqueda 3×3 téxeles, sesgo por pendiente, sin culling | téxel 1,0 m · 0,3 pts/m² · 24 pasos · 24 sondas | 0,712 | −37,9 % | 76,6 % | 100 % | **Rechazada.** La vecindad 3×3 dilata cada sombra 1 m y apaga la ciudad; además las losas de suelo (cara hacia abajo) entraban en la validación. |
| E02 | 2026-10-30 | Culling de caras frontales (un solo búfer de caras de espaldas a la luz), búsqueda 1×1, téxel fino | téxel 0,5 m · 2 pts/m² · 24 pasos · 117 sondas | 0,896 | +7,3 % | 8,5 % | 386 % | Parcial. La mediana cae de 76,6 % a 8,5 %. Quedan sondas donde el control da ~0 y el motor propio da cielo abierto. |
| E03 | 2026-10-30 | Normales exteriores por paridad de rayos contra el propio edificio (sustituye la prueba de huella) | ídem E02 | 0,967 | +1,5 % | 8,5 % | 80 % | Aceptada. 2 625 caras estaban invertidas hacia dentro del sólido; con la normal correcta dejan de recibir cielo falso. |
| E04 | 2026-10-30 | Cielo isótropo usado como *razón* (factor de visión) sobre el valor exacto DHI·(1+cos β)/2, en vez de sumar parches | ídem | 0,898 | +5,8 % | 11,4 % | 343 % | Mantenida pese al empeoramiento aparente: el conjunto de sondas cambió al excluir caras enterradas. Elimina el sesgo de discretización del domo, medido en 15 % de mediana contra el valor analítico en el caso sin obstáculos. |
| E05 | 2026-10-30 | Detección de caras enterradas (paridad vertical contra edificios vecinos) y exclusión de la salida | ídem | 0,899 | +5,6 % | 11,4 % | 343 % | Aceptada por corrección física (1 924 caras), sin efecto medible en las sondas. |
| E06 | 2026-10-30 | Segunda pasada del domo sin culling para detectar superficies encerradas (umbral 0,02) | ídem | 0,899 | +5,6 % | 11,4 % | 343 % | **Rechazada.** Duplicaba el coste (17 s → 33 s) y no capturaba los casos en desacuerdo. Sustituida por E08. |
| E07 | 2026-10-30 | Diagnóstico independiente: trazado de rayos con el BVH de Blender sobre las sondas en desacuerdo | 14 sondas peores | — | — | — | — | Resultado: 145/145 direcciones bloqueadas en todas ellas. **El control tenía razón**; el motor propio no veía la oclusión. Causa: las caras enterradas se estaban excluyendo también de la *escena*, no solo de la salida. |
| E08 | 2026-10-30 | Dos búferes por dirección: trasero (sesgo exacto) para la sombra urbana, frontal (sesgo por pendiente) para el encierro; la escena vuelve a contener todas las caras | téxel 0,5 m · 2 pts/m² · 24 pasos · 117 sondas | 0,982 | −2,9 % | 9,1 % | 73 % | **Aceptada.** Configuración final. |
| E09 | 2026-10-30 | Medición final con el muestreo completo del año | téxel 0,5 m · 2 pts/m² · 141 pasos solares + 145 parches · 900 sondas · Cycles 512 muestras | **0,977** | **−0,5 %** | **8,5 %** | **605 %** | Resultado publicado. H1 **no** se cumple por el percentil 95; C1, H2 y H3 sí. |

## Lectura de E09

- Por clase: tejados 1,3 % de error mediano, muros 13,8 %, caras LOD1 13,7 %.
- 117 de las 900 sondas quedaron fuera de la comparación porque el control
  devuelve ≈0: son caras selladas dentro de sólidos CityGML superpuestos que el
  detector de caras enterradas no alcanzó. Es el límite conocido del método.
- El percentil 95 se dispara en caras oscuras con valores absolutos de unos
  pocos kWh/m²·año, donde una diferencia pequeña es un porcentaje enorme.
- Coste: 0,91 ms por superficie frente a 1 112 ms del control, en la misma
  máquina (16 núcleos CPU) y con el mismo conjunto de direcciones.

## Entorno

- Motor propio: Python 3.13, NumPy 2.5, PyTorch 2.14 (CPU), carril `cpu` de
  server-ia, 16 núcleos. Trabajo `959c6b55ea724f0f`.
- Control: Blender 4.5.9 LTS, Cycles, CPU, 512 muestras, 141 horneados.
- Preproceso (normales y caras enterradas) en el PC local; no entra en el
  tiempo medido, y así se declara.

---

## Segunda ronda, 2026-10-31: correcciones tras la revisión independiente

La revisión previa (`REVISION_COG_VERIFIER.md`, hecha con un subagente
verificador y **declarada no equivalente a la auditoría de Codex**) encontró dos
defectos en la comparación. Ambos se corrigieron y se volvió a medir.

| id | fecha | cambio | efecto medido |
|---|---|---|---|
| E10 | 2026-10-31 | **El control recibía cielo desde la esfera completa.** El fondo uniforme de Blender ilumina también desde abajo del horizonte, mientras que el motor propio integra solo la hemisfera superior: una sonda vertical recibía ×1,30 de más en el control. Se añade al control un disco negro de 20 km de radio a la cota mínima del teselado. | Los muros pasan de 13,8 % a **6,3 %** de error mediano y las caras LOD1 de 13,7 % a **4,0 %**. La calibración C1 no cambia (las superficies horizontales no ven el hemisferio inferior). |
| E11 | 2026-10-31 | **El veredicto de H1 se leía sobre un subconjunto.** El contrato no excluía sondas; el código filtraba `control > 1 kWh/m²·año`. Ahora el veredicto se calcula sobre las 900 y el subconjunto se publica etiquetado como posterior al contrato. | Sobre las 900: R² 0,884, sesgo +11,9 %, mediana 4,8 %, p95 57 265 % → **H1 no se cumple** por R², sesgo y p95. Sobre las 772 restantes: R² 0,985, sesgo +4,0 %, mediana 2,6 %. |
| E12 | 2026-10-31 | **Medida de carga igual.** El motor propio ejecutado sobre exactamente las mismas 900 superficies y las mismas 286 direcciones. | 40,6 s frente a 1 075,6 s del control: **26×**. El 1 343× anterior es el coste por superficie cuando el mismo trabajo cubre las 44 902 caras del distrito, y así se etiqueta. |

### Causa única del fallo de H1

128 de las 900 sondas son caras selladas dentro de sólidos CityGML superpuestos.
El trazador de caminos devuelve ≈0 y el motor propio devuelve luz (varios cientos
de kWh/m²·año de más). El detector de caras enterradas encuentra 1 924, pero deja
estas fuera. Esas 128 sondas, por sí solas, tumban R², el sesgo y el percentil 95.
Es un problema de detección de geometría, no del transporte de luz: en las 772
sondas restantes el acuerdo es R² 0,985 con 2,6 % de error mediano.

### Correcciones de redacción derivadas de la misma revisión

- «mismo modelo de radiación» ahora dice explícitamente que el cielo se limita a
  la hemisfera superior en los dos motores (antes no era cierto).
- «los datos no se redistribuyen» ahora distingue el CityGML original (no se
  redistribuye) del binario del visor (sí, es un derivado, con atribución).
- La diferencia de T2 y T4 contra el valor analítico ya **no** se atribuye a la
  discretización: queda como causa por identificar.
- El percentil 5 del factor de visión de cielo (0,00) se explica por las losas
  inferiores.
- Se publica `experiments/LOG.md` en el repositorio, que la solicitud citaba.
- Se declara que «registrado antes de medir» es autodeclarado y que las
  iteraciones E02–E08 ajustaron el motor contra el mismo control y distrito, sin
  conjunto de validación independiente.
