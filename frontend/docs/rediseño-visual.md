# Rediseño visual FORTIA

## Alcance

Este cambio modifica únicamente la presentación visual. No cambia arquitectura, estado, servicios, contratos, datos simulados, distribución general ni lógica de predicción.

## Sistema centralizado

La nueva capa visual está al final de src/styles.css para preservar los estilos existentes y aplicar el tema de forma controlada. Sus variables semánticas incluyen superficies, texto, acentos neón, predicciones, sombras y transiciones.

## Jerarquía cromática

- Eliminado: rojo neón y magenta.
- Eliminación: cian y azul eléctrico.
- Victoria: dorado y amarillo.
- Ganar: verde neón y cian.
- Perder: rojo neón y magenta.
- Procesando: azul eléctrico y cian.
- Advertencia: naranja y dorado.

## Cambios aplicados

- Fondo con resplandores radiales cian y morado.
- Tarjetas con superficies escalonadas, bordes semitransparentes y sombras profundas.
- Modelo principal con borde superior degradado y halo contextual.
- Visor central con borde cian, sombra interior y placeholder más intencional.
- Barras de vida, escudo y probabilidades con degradados y brillo moderado.
- Rarezas de inventario diferenciadas mediante bordes y resplandores tenues.
- Frames con hover, focus visible, estado procesando y profundidad interior.
- Alertas y recomendaciones diferenciadas por prioridad.
- Botón principal con degradado cian-azul-morado y estados hover/focus.
- Modal con fondo translúcido, desenfoque moderado y borde cian.

## Compatibilidad

Se conserva el layout existente para escritorio y sus breakpoints. Se mantiene el respeto a prefers-reduced-motion.
