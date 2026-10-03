from __future__ import annotations
import hashlib, json, time
from pathlib import Path
import joblib, numpy as np
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, log_loss, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'backend/artifacts/experimental_training_20261001'
MODELS = OUT / 'models'
FEATURES = ROOT / 'backend/reports/fusion_candidates_20261001/validation_features.npz'
CLASS_NAMES = ('Eliminado', 'Eliminacion', 'Victoria')

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def evaluate(model, x, y):
    times=[]; p=model.predict_proba(x)
    for _ in range(100):
        t=time.perf_counter(); model.predict_proba(x); times.append((time.perf_counter()-t)*1000/max(1,len(y)))
    pred=model.classes_[p.argmax(axis=1)]
    precision, recall, f1, support=precision_recall_fscore_support(y,pred,labels=[0,1,2],zero_division=0)
    return {
      'samples': int(len(y)), 'precision': {n:float(v) for n,v in zip(CLASS_NAMES,precision)},
      'recall': {n:float(v) for n,v in zip(CLASS_NAMES,recall)}, 'f1': {n:float(v) for n,v in zip(CLASS_NAMES,f1)},
      'support': {n:int(v) for n,v in zip(CLASS_NAMES,support)}, 'macro_f1':float(f1_score(y,pred,average='macro',zero_division=0)),
      'balanced_accuracy':float(balanced_accuracy_score(y,pred)), 'confusion_matrix':confusion_matrix(y,pred,labels=[0,1,2]).tolist(),
      'prediction_distribution':{CLASS_NAMES[i]:int((pred==i).sum()) for i in range(3)},
      'mean_probability':{n:float(v) for n,v in zip(CLASS_NAMES,p.mean(axis=0))},
      'brier_score':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1))), 'log_loss':float(log_loss(y,p,labels=[0,1,2])),
      'latency_ms_mean':float(np.mean(times)), 'latency_ms_p95':float(np.percentile(times,95))
    }

def main():
    z=np.load(FEATURES); x=z['features']; y=z['labels'].astype(np.int64)
    report={'status':'CANDIDATO EXPERIMENTAL NO PROMOVIBLE','test_used':False,'validation_features_source':str(FEATURES),
            'validation_features_hash':sha256(FEATURES),'class_order':[0,1,2],'class_names':list(CLASS_NAMES),
            'train_videos':496,'validation_videos':118,'train_class_counts':{'Eliminado':69,'Eliminacion':412,'Victoria':15},'candidates':{}}
    for path in sorted(MODELS.glob('fusion_*.joblib')):
        pack=joblib.load(path); metrics=evaluate(pack['model'],x,y)
        report['candidates'][path.stem.removeprefix('fusion_')]={'artifact':str(path),'hash':sha256(path),'class_weight':pack.get('class_weight'),'metrics_validation':metrics}
    report['elapsed_seconds']=0.0
    (OUT/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'config.json').write_text(json.dumps({'version':'experimental-training-20261001','class_order':[0,1,2],'labels':{'Eliminado':0,'Eliminacion':1,'Victoria':2},'modalities':['frames','health','inventory','map','audio'],'scaler':None,'encoder':{'Eliminado':0,'Eliminacion':1,'Victoria':2},'seed':42,'test_used':False},ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps({'status':'CANDIDATO EXPERIMENTAL NO PROMOVIBLE','allowed_splits':['train','validation'],'forbidden_split':'test','split':'backend/data/splits/video_split.csv','validation_features_hash':sha256(FEATURES)},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'CANDIDATO EXPERIMENTAL NO PROMOVIBLE','metrics':str(OUT/'metrics.json'),'test_used':False},ensure_ascii=False))
if __name__=='__main__': main()
