"""
train.py — Treina modelo de localização de áudio a partir de samples.csv
Uso: python train.py
Saída: model.pkl (usado por radar_ml.py)
"""

import csv
import os
import math
import pickle
import numpy as np

# ── Dependências ──────────────────────────────────────────────────────────────
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.metrics import classification_report, confusion_matrix
except ImportError:
    print("Instale: pip install scikit-learn")
    exit(1)

CSV_FILE  = "samples.csv"
MODEL_OUT = "model.pkl"

# Ângulos que o modelo vai prever
ANGLES = [0, 45, 90, 135, 180, 225, 270, 315]


def load_data():
    X, y = [], []
    with open(CSV_FILE, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row:
                continue
            try:
                angle = int(row[0])
                feats = [float(v) for v in row[1:]]
                X.append(feats)
                y.append(angle)
            except:
                pass
    return np.array(X), np.array(y)


def augment_data(X, y):
    """
    Data augmentation simples:
    - Adiciona ruído gaussiano leve às features
    - Triplica o dataset, ajuda com poucos samples
    """
    X_aug, y_aug = [X], [y]
    for noise_level in [0.005, 0.01]:
        noise = np.random.normal(0, noise_level, X.shape)
        X_aug.append(X + noise)
        y_aug.append(y)
    return np.vstack(X_aug), np.concatenate(y_aug)


def train():
    print("=" * 50)
    print("  ACOUSTIC MODEL TRAINER")
    print("=" * 50)

    if not os.path.exists(CSV_FILE):
        print(f"ERRO: {CSV_FILE} não encontrado. Colete samples primeiro.")
        return

    print(f"\n[1/5] Carregando {CSV_FILE}...")
    X, y = load_data()
    print(f"      {len(X)} samples | {X.shape[1]} features")

    # Distribuição por ângulo
    print("\n      Distribuição:")
    for ang in ANGLES:
        n = np.sum(y == ang)
        bar = "█" * (n // 2)
        print(f"      {ang:>3}°  {bar} {n}")

    min_samples = min(np.sum(y == a) for a in ANGLES)
    if min_samples < 10:
        print(f"\n⚠  Ângulo com apenas {min_samples} samples — colete mais para melhor acurácia.")

    # Augmentation
    print("\n[2/5] Augmentando dados...")
    X_aug, y_aug = augment_data(X, y)
    print(f"      {len(X_aug)} samples após augmentation")

    # Normalização
    print("\n[3/5] Normalizando features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_aug)

    # Split treino/teste (usando dados originais para teste, sem augmentation)
    X_orig_scaled = scaler.transform(X)
    X_train, X_test, y_train, y_test = train_test_split(
        X_orig_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── Treina 3 modelos e escolhe o melhor ───────────────────────────────────
    print("\n[4/5] Treinando modelos...")

    candidates = {
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.1,
            random_state=42
        ),
        "MLP": MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            max_iter=500,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1
        ),
    }

    best_name  = None
    best_score = 0.0
    best_model = None

    for name, model in candidates.items():
        # Cross-val nos dados augmentados
        cv_scores = cross_val_score(
            model, X_scaled, y_aug, cv=5, scoring='accuracy', n_jobs=-1
        )
        print(f"      {name:<20} CV acc: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        if cv_scores.mean() > best_score:
            best_score = cv_scores.mean()
            best_name  = name
            # Re-treina no dataset completo augmentado
            model.fit(X_scaled, y_aug)
            best_model = model

    print(f"\n      ✓ Melhor modelo: {best_name} (CV acc={best_score:.3f})")

    # ── Avaliação no test set ──────────────────────────────────────────────────
    print("\n[5/5] Avaliando no test set...")
    y_pred = best_model.predict(X_test)
    test_acc = np.mean(y_pred == y_test)
    print(f"      Test accuracy: {test_acc:.3f}")

    print("\n      Classification report:")
    print(classification_report(y_test, y_pred,
                                 target_names=[f"{a}°" for a in sorted(set(y_test))],
                                 zero_division=0))

    # Confusion matrix simplificada
    print("      Confusion matrix (linhas=real, colunas=previsto):")
    labels = sorted(set(y))
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    header = "       " + "  ".join(f"{a:>3}" for a in labels)
    print(header)
    for i, row in enumerate(cm):
        print(f"  {labels[i]:>3}°  " + "  ".join(f"{v:>3}" for v in row))

    # ── Salva modelo + scaler ──────────────────────────────────────────────────
    payload = {
        'model':      best_model,
        'scaler':     scaler,
        'model_name': best_name,
        'cv_acc':     best_score,
        'test_acc':   test_acc,
        'n_samples':  len(X),
        'angles':     ANGLES,
    }
    with open(MODEL_OUT, 'wb') as f:
        pickle.dump(payload, f)

    print(f"\n{'='*50}")
    print(f"  ✓ Modelo salvo em {MODEL_OUT}")
    print(f"  Acurácia CV:   {best_score:.1%}")
    print(f"  Acurácia test: {test_acc:.1%}")
    print(f"{'='*50}")

    if test_acc < 0.6:
        print("\n⚠  Acurácia baixa — colete mais samples variados.")
    elif test_acc < 0.8:
        print("\n↑  Bom começo. Mais samples vão melhorar.")
    else:
        print("\n✓  Boa acurácia! Pode usar em radar_ml.py.")


if __name__ == "__main__":
    train()