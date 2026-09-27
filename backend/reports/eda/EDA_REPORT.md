# Reporte EDA

Videos analizados: **751**

## Distribución de clases

| clase       |   etiqueta |   videos |
|:------------|-----------:|---------:|
| Eliminacion |          1 |      616 |
| Eliminado   |          0 |      114 |
| Victoria    |          2 |       21 |

## Perfil numérico

|              |   count |      mean |     std |     min |     25% |     50% |     75% |     max |
|:-------------|--------:|----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| duration_sec |     751 |   19.6042 | 2.37596 |   12.48 |   20.03 |   20.22 |   20.38 |   29.28 |
| fps          |     751 |   60      | 0       |   60    |   60    |   60    |   60    |   60    |
| width        |     751 | 1360      | 0       | 1360    | 1360    | 1360    | 1360    | 1360    |
| height       |     751 |  768      | 0       |  768    |  768    |  768    |  768    |  768    |

## Calidad por modalidad

| modality   |   files |   corrupt |   min_width |   max_width |   min_height |   max_height |
|:-----------|--------:|----------:|------------:|------------:|-------------:|-------------:|
| audio      |     751 |         0 |        1678 |        1683 |          725 |          725 |
| frames     |    4506 |         0 |        1360 |        1360 |          768 |          768 |
| health     |   15020 |         0 |         489 |         489 |          216 |          216 |
| inventory  |   15020 |         0 |         640 |         640 |          185 |          185 |
| map        |   15020 |         0 |         313 |         313 |          261 |          261 |

## Observaciones

- Las modalidades tienen disponibilidad para los 751 `id_video` según la matriz auditada.
- `Victoria` tiene 21 videos y debe evaluarse con validación agrupada y cautela.
- Los gráficos se encuentran en este mismo directorio.