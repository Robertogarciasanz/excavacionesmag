# Soporte con ranura en arco (SR-001)

| Archivo | Qué es |
|---|---|
| `Soporte_Ranurado_plano.pdf` | Plano A3 a escala 1:1: alzado, perfil izquierdo, planta e isométrica (sistema europeo) |
| `Soporte_Ranurado_plano.png` | El mismo plano en imagen |
| `Soporte_Ranurado_v1.bas` | Macro VBA de SolidWorks que crea la pieza nativa, con árbol, cotas y ecuaciones |
| `generar_planos.py` | Regenera el plano (`pip install matplotlib shapely`, luego `python3 generar_planos.py`) |

## Ejecutar la macro en SolidWorks
1. Herramientas > Macro > Nueva (o Editar una macro existente `.swp`).
2. En el editor VBA: Archivo > Importar archivo > `Soporte_Ranurado_v1.bas`.
3. Coloca el cursor dentro de `Sub main()` y pulsa F5.
4. Al terminar sale un aviso; comprueba que hay 1 sólido y guarda la pieza como `Soporte_Ranurado.SLDPRT`.

Árbol que se crea: Base > Alma > Oreja > Bujes > Taladros_Bujes > Ranura > Taladros_Base > Avellanados > Redondeo_Base.

## Cotas (variables globales en Herramientas > Ecuaciones)
`L=160 H=13 D=54 E=20 XP=48 YP=46 RR=40 DB=33 LB=44 DS=17 DT=12 AR=24 AS=12 XO=87 XG=110 XB1=100 XB2=135 ZB=34 DA=14 DAV=28 RF=10`

Las cotas se han interpretado a partir de un boceto de baja resolución. Las que
salen del boceto son 160, 48, 39, 13, 33, 57/103, ø33, ø12, R40 y R52. Las demás
son supuestas: fondo de la base 54, espesor del alma 20, largo de los bujes 44,
ø17, posición de los avellanados y ángulos de la ranura (18°–52°). Si cambias
alguna, edita la ecuación o la constante `v...` al principio de la macro.
