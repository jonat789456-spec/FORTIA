# Automatic temporal labeling

Pipeline batch aislado del sistema productivo. Lee videos desde `F:\Cursos\Ciencia de Datos\Modulo 5\CODIGOS\Proyecto Fotnite\VIDEOS\ORIGINAL` y escribe solamente en `backend/data/automatic_temporal_annotations`.

## Ejecución

```powershell
cd "C:\Users\jonat\Downloads\FORTNITE IA 2\backend\temporal_labeling"
python run_pipeline.py --sample
python run_pipeline.py
python validate_outputs.py
```

`--sample` procesa los videos 21, 126 y 166. El pipeline no abre `test`, no entrena, no modifica el registry ni altera los videos. La etiqueta histórica se conserva solo como señal secundaria.

## Confianza

La aceptación es específica por evento: OCR inequívoco en región esperada para eliminaciones, o OCR exacto/persistente del banner para victoria. La ausencia de audio se registra como señal ausente y no se penaliza como contradicción. Cada candidato conserva texto original y normalizado, similitud difusa, región relativa, persistencia, señales disponibles/ausentes/contradictorias, regla, umbral, incertidumbre temporal y frame completo, recorte, preprocesado y máscara.

Solo se exportan a `automatic_events.csv` los eventos `high_confidence`: OCR específico, persistencia temporal y señal visual compatible. Los eventos medios, bajos o ambiguos se escriben en `excluded_ambiguous_events.csv` y nunca entran automáticamente a entrenamiento.

El OCR es opcional, pero para cobertura real se recomienda instalar `pytesseract`, Tesseract OCR y `pyarrow` para exportar Parquet. Sin OCR disponible, el pipeline debe producir exclusiones, no etiquetas inventadas.

La ausencia del ejecutable Tesseract se registra en `coverage_summary.json`; no se sustituye por la etiqueta histórica ni por el nombre del archivo. `automatic_events.parquet` y `excluded_ambiguous_events.parquet` se escriben incluso cuando están vacíos.
