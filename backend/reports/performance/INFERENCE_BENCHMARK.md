# Benchmark de inferencia — baseline-0.2.0

Fecha de ejecución: 2026-09-21. Plataforma: Windows 11, Python 3.12.10, CPU.

La medición utilizó vectores cero únicamente para medir latencia del cargador y del clasificador. No evalúa calidad predictiva y no utiliza el conjunto `test`.

| Modalidad | Muestras | Media (ms) | P95 (ms) | Mínimo (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| frames | 20 | 0.0824 | 0.0965 | 0.0769 | 0.1110 |
| health | 20 | 0.0777 | 0.0908 | 0.0738 | 0.0935 |
| inventory | 20 | 0.0786 | 0.0844 | 0.0736 | 0.1165 |
| map | 20 | 0.0753 | 0.0788 | 0.0732 | 0.0835 |
| audio | 20 | 0.0758 | 0.0815 | 0.0736 | 0.0867 |
| fusion multimodal | 20 | 0.0808 | 0.0876 | 0.0775 | 0.0917 |

La medición no incluye captura de pantalla, codificación JPEG, recortes, transporte WebSocket ni fusión. Debe repetirse con Fortnite abierto para obtener la latencia integral.
