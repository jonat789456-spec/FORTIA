# Baselines

Los modelos se ajustaron únicamente con `train` y se compararon en `validation`.

| Modalidad | F1 macro | Balanced accuracy | Log loss |
|---|---:|---:|---:|
| frames | 0.8635 | 0.8851 | 0.3215 |
| health | 0.7932 | 0.8699 | 0.1284 |
| inventory | 0.8539 | 0.8652 | 0.1587 |
| map | 0.9425 | 0.9924 | 0.1401 |
| audio | 0.8608 | 0.9440 | 0.4008 |

El conjunto `test` no se utilizó.

Las características son baselines de imagen reducida; no representan todavía modelos finales.