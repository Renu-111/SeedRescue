"""Prediction uncertainty helpers for tree ensembles."""
import numpy as np

def tree_prediction_stats(model, X):
    if not hasattr(model, "estimators_"):
        return None
    arr=np.stack([est.predict(X) for est in model.estimators_],axis=0)
    mean=arr.mean(axis=0)[0]
    std=arr.std(axis=0)[0]
    return mean,std

def confidence_from_std(std, scale=25.0):
    return float(np.clip(1.0-np.mean(std)/scale,0,1))
