import pandas as pd
import numpy as np
import pywt
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, GridSearchCV
import lightgbm as lgbm
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler
import joblib
import os
import glob
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / 'data' / 'training' / 'primary'
MODEL_PATH = PROJECT_ROOT / 'models' / 'active'
PLOT_PATH = PROJECT_ROOT / 'artifacts' / 'plots'

# Fungsi extract_features (tidak diubah)
def extract_features(data_series):
    features = {}
    features['mean'] = data_series.mean()
    features['std_dev'] = data_series.std()
    features['variance'] = data_series.var()
    features['max_val'] = data_series.max()
    features['min_val'] = data_series.min()
    features['skewness'] = data_series.skew()
    features['kurtosis'] = data_series.kurtosis()
    zero_crossings = np.where(np.diff(np.sign(data_series)))[0]
    features['zcr'] = len(zero_crossings) / len(data_series)
    coeffs = pywt.wavedec(data_series, 'db4', level=4)
    cA4, cD4, cD3, cD2, cD1 = coeffs
    features['energy_d1'] = np.sum(np.square(cD1))
    features['energy_d2'] = np.sum(np.square(cD2))
    features['energy_d3'] = np.sum(np.square(cD3))
    features['energy_d4'] = np.sum(np.square(cD4))
    features['energy_a4'] = np.sum(np.square(cA4))
    return features

# ==================================================================
# FUNGSI BARU UNTUK AUGMENTASI DATA
# ==================================================================
def augment_signal(data_series, noise_level=0.05):
    """Menambahkan Gaussian noise ke sinyal."""
    noise = np.random.normal(0, data_series.std() * noise_level, len(data_series))
    return data_series + noise

# ==================================================================
# DATA LOADING DENGAN AUGMENTASI
# ==================================================================
all_csv_files = glob.glob(str(DATA_PATH / 'tahap[0-4]' / '*.csv'))

all_features_list = []
window_size = 256
step = 32

for f in all_csv_files:
    folder_name = os.path.basename(os.path.dirname(f))
    label = folder_name.replace('tahap', 'Tahap-')
    signal_data = pd.read_csv(f)['frekuensi'].dropna()
    
    for i in range(0, len(signal_data) - window_size, step):
        window = signal_data[i : i + window_size]
        
        if len(window) == window_size:
            # 1. Proses data asli
            original_features = extract_features(window)
            original_features['label'] = label
            all_features_list.append(original_features)
            
            # 2. Buat & proses data augmentasi (versi noisy)
            augmented_window = augment_signal(window)
            augmented_features = extract_features(augmented_window)
            augmented_features['label'] = label
            all_features_list.append(augmented_features)

df = pd.DataFrame(all_features_list).fillna(0)
print("DataFrame baru dengan AUGMENTASI berhasil dibuat.")
print("Jumlah data (potongan sinyal) per label (setelah augmentasi):")
print(df['label'].value_counts())
print("-" * 30)

# (Sisa kode untuk persiapan data, GridSearchCV, dan evaluasi tetap sama)
X = df.drop('label', axis=1)
y = df['label']
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)
joblib.dump(scaler, MODEL_PATH / 'scaler_augmented.joblib')
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42, stratify=y)

print("Memulai pencarian parameter terbaik untuk LightGBM dengan data augmentasi...")
param_grid = {
    'n_estimators': [100, 200],
    'learning_rate': [0.05, 0.1],
    'num_leaves': [31, 50]
}
lgbm_model = lgbm.LGBMClassifier(random_state=42)
grid_search = GridSearchCV(estimator=lgbm_model, param_grid=param_grid, 
                           cv=3, n_jobs=-1, verbose=2, scoring='accuracy')
grid_search.fit(X_train, y_train)

print("\nPencarian Selesai!")
print("Parameter terbaik yang ditemukan:")
print(grid_search.best_params_)
print("-" * 30)

best_lgbm_model = grid_search.best_estimator_
joblib.dump(best_lgbm_model, MODEL_PATH / 'model_terbaik_augmented.joblib')
print(">>> Model terbaik (augmented) berhasil disimpan.")

y_pred = best_lgbm_model.predict(X_test)
print(f"\nAkurasi pada Data Training: {best_lgbm_model.score(X_train, y_train):.4f}")
print(f"Akurasi pada Data Testing: {accuracy_score(y_test, y_pred):.4f}")
print("\nFinal Classification Report on Test Data (Augmented):")
target_names = sorted(y.unique())
print(classification_report(y_test, y_pred, target_names=target_names))

cm = confusion_matrix(y_test, y_pred, labels=target_names)
plt.figure(figsize=(10,8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=target_names, yticklabels=target_names)
plt.title('Final Confusion Matrix - Best Augmented LGBM Model')
plt.savefig(PLOT_PATH / "Final_CM_Best_Augmented_LGBM_Model.png", dpi=300, bbox_inches='tight')
plt.close()
print("Final confusion matrix saved as Final_CM_Best_Augmented_LGBM_Model.png")