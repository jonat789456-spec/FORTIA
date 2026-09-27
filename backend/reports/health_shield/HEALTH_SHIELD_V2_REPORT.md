# Diagnóstico y mejora de vida/escudo

## Causa confirmada

El lector anterior recibía un recorte fijo de `0:489, 552:768` escalado desde
`1360x768`, buscaba cualquier píxel verde o azul en todo el recorte y convertía
el mínimo/máximo global en porcentaje. No detectaba la geometría de la barra,
mezclaba iconos y escenario, usaba una confianza mínima de `0.25` y no tenía
suavizado ni persistencia de alertas. Además, `mss` entregaba BGR mientras el
pipeline trataba la captura como RGB.

## Método v2

- La captura se normaliza a RGB inmediatamente después de `mss`.
- La ROI conserva coordenadas relativas y se analiza en bandas independientes:
  escudo `45–68%` y vida `62–92%` de la altura del recorte.
- La barra se localiza por color tolerante, continuidad horizontal y geometría.
- El valor se calcula contra el tramo de barra, no contra todo el recorte.
- Vida y escudo tienen máscaras, valores, confianza y estado independientes.
- La ventana temporal conserva hasta 7 lecturas y rechaza picos aislados.
- La confianza mínima operativa es `0.75`; los fallos devuelven `not_detected`,
  `low_confidence` o `stale`, nunca cero inventado.
- Las alertas usan persistencia de 3 lecturas e histéresis: vida `40/45` y
  escudo `30/35`. Vida crítica queda en `20`.

## Evidencia

Sobre `video_0001_vida_01.jpg`, un recorte real disponible en `VIDA`, el detector
v2 produjo:

```json
{
  "healthValue": 100.0,
  "shieldValue": 98.38,
  "confidence": 0.999,
  "status": "available",
  "regionUsed": "health_hud_relative"
}
```

El conjunto `df_recortes_vida.csv` contiene 15 020 recortes de 751 videos, pero
solo etiquetas de clase y no valores numéricos de vida/escudo. Por ello no se
entrenó ni calibró una regresión numérica con etiquetas inválidas y no se
modificaron los datos originales, el conjunto test ni los modelos existentes.

## Limitaciones

El método actual es `bar_color_geometry`; no se añadió OCR porque el entorno
base no incluye un motor OCR y las etiquetas numéricas disponibles no son
fiables para supervisarlo. La configuración versionada está en
`backend/config/health_shield_detector_v2.yaml`. El OCR puede añadirse como
verificación posterior sin reemplazar la lectura de barra.
