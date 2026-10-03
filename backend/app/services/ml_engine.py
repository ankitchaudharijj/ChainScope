"""
AI/ML Engine (architecture doc component 06).

Two jobs, kept deliberately separate from the rule-based Risk Engine:

  1. Behaviour classification — label a wallet's transaction pattern
     (Normal / Exchange-like / Mixer-related / High-risk / Rapid Fund
     Movement) using a trained classifier over engineered features,
     not a hand-written if/else chain restating the risk rules.
  2. Wallet clustering — group wallets by behavioural similarity
     (KMeans over the same feature space), the ML half of "Wallet
     Clustering (ML + Graph)" — the Graph Engine's multi-hop proximity
     is the other half.

The model trains on a small synthetic labelled dataset built from the
same domain knowledge the Risk Engine encodes (sanctions exposure,
mixer interaction, velocity, dormancy) but expressed as continuous
features a classifier learns boundaries over, rather than fixed
point-thresholds. It is a real, fitted scikit-learn model — not a
lookup table — but it is trained on synthetic examples, not on labelled
real-world fraud data (that's a licensed-dataset problem, same caveat
as the VASP directory). Treat its output as a second, ML-derived signal
alongside the Risk Engine's rule-based score, not a ground truth label.
"""
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

LABELS = ["Normal", "Exchange-like", "Mixer-related", "High-risk", "Rapid Fund Movement"]

FEATURE_NAMES = [
    "tx_count", "unique_counterparties", "avg_amount", "amount_std",
    "in_out_ratio", "vasp_interaction_share", "mixer_interaction_share",
    "high_value_tx_share", "dormant_flag", "sanctions_flag",
]


def extract_features(wallet, edges, vasp_lookup: dict) -> np.ndarray:
    """
    Turns a wallet + its edges into a fixed-length numeric feature
    vector. vasp_lookup maps a counterparty address to its Vasp row —
    the same lookup the attribution endpoint already builds, passed in
    rather than re-queried here.
    """
    if not edges:
        return np.zeros(len(FEATURE_NAMES))

    amounts = np.array([e.amount for e in edges])
    directions = [e.direction for e in edges]
    counterparties = {e.to_address for e in edges}

    n_in = directions.count("in")
    n_out = directions.count("out")
    in_out_ratio = n_in / max(n_out, 1)

    vasp_hits = sum(1 for e in edges if e.to_address in vasp_lookup)
    mixer_hits = sum(
        1 for e in edges
        if e.to_address in vasp_lookup
        and "mixing" in vasp_lookup[e.to_address].vasp_type.lower()
    )
    high_value_share = float(np.mean(amounts > np.percentile(amounts, 75))) if len(amounts) > 1 else 0.0

    return np.array([
        wallet.tx_count,
        len(counterparties),
        float(np.mean(amounts)),
        float(np.std(amounts)) if len(amounts) > 1 else 0.0,
        in_out_ratio,
        vasp_hits / len(edges),
        mixer_hits / len(edges),
        high_value_share,
        1.0 if wallet.flag_dormant_revival else 0.0,
        1.0 if wallet.flag_sanctions else 0.0,
    ])


def _synthetic_training_set(n_per_class: int = 60, seed: int = 42):
    """
    Hand-designed synthetic examples for each behaviour class, with
    Gaussian noise so the classifier has to learn a real decision
    boundary rather than memorising exact points. The centres reflect
    the same domain reasoning as the Risk Engine (see app/services/
    risk.py) — e.g. "Mixer-related" wallets get a high mixer-share
    centre — but a RandomForest fits nonlinear boundaries over this
    feature space, so its output isn't just those rules re-executed.
    """
    rng = np.random.default_rng(seed)
    X, y = [], []

    centres = {
        "Normal": dict(tx_count=40, unique_cp=6, avg_amt=0.5, amt_std=0.3,
                       io_ratio=0.9, vasp_share=0.1, mixer_share=0.0,
                       hv_share=0.15, dormant=0.0, sanctions=0.0),
        "Exchange-like": dict(tx_count=300, unique_cp=15, avg_amt=1.2, amt_std=0.8,
                               io_ratio=1.1, vasp_share=0.7, mixer_share=0.0,
                               hv_share=0.25, dormant=0.0, sanctions=0.0),
        "Mixer-related": dict(tx_count=80, unique_cp=8, avg_amt=3.0, amt_std=2.0,
                               io_ratio=0.3, vasp_share=0.4, mixer_share=0.6,
                               hv_share=0.4, dormant=0.0, sanctions=0.3),
        "High-risk": dict(tx_count=150, unique_cp=20, avg_amt=2.5, amt_std=2.5,
                           io_ratio=0.4, vasp_share=0.3, mixer_share=0.3,
                           hv_share=0.5, dormant=0.1, sanctions=0.8),
        "Rapid Fund Movement": dict(tx_count=500, unique_cp=25, avg_amt=1.8, amt_std=1.5,
                                     io_ratio=0.2, vasp_share=0.5, mixer_share=0.1,
                                     hv_share=0.6, dormant=0.0, sanctions=0.1),
    }

    for label, c in centres.items():
        for _ in range(n_per_class):
            row = [
                max(1, rng.normal(c["tx_count"], c["tx_count"] * 0.25)),
                max(1, rng.normal(c["unique_cp"], c["unique_cp"] * 0.3)),
                max(0.01, rng.normal(c["avg_amt"], c["avg_amt"] * 0.3)),
                max(0.0, rng.normal(c["amt_std"], c["amt_std"] * 0.3 + 0.01)),
                max(0.0, rng.normal(c["io_ratio"], 0.15)),
                np.clip(rng.normal(c["vasp_share"], 0.15), 0, 1),
                np.clip(rng.normal(c["mixer_share"], 0.1), 0, 1),
                np.clip(rng.normal(c["hv_share"], 0.15), 0, 1),
                1.0 if rng.random() < c["dormant"] else 0.0,
                1.0 if rng.random() < c["sanctions"] else 0.0,
            ]
            X.append(row)
            y.append(label)

    return np.array(X), np.array(y)


@dataclass
class BehaviourResult:
    label: str
    confidence: float
    class_probabilities: dict[str, float]


class MLEngine:
    def __init__(self):
        X, y = _synthetic_training_set()
        self._scaler = StandardScaler().fit(X)
        self._clf = RandomForestClassifier(
            n_estimators=200, max_depth=8, random_state=42, class_weight="balanced"
        )
        self._clf.fit(self._scaler.transform(X), y)

    def classify(self, wallet, edges, vasp_lookup: dict) -> BehaviourResult:
        features = extract_features(wallet, edges, vasp_lookup).reshape(1, -1)
        scaled = self._scaler.transform(features)
        probs = self._clf.predict_proba(scaled)[0]
        classes = self._clf.classes_
        best_idx = int(np.argmax(probs))
        return BehaviourResult(
            label=classes[best_idx],
            confidence=round(float(probs[best_idx]) * 100, 1),
            class_probabilities={c: round(float(p) * 100, 1) for c, p in zip(classes, probs)},
        )

    def cluster(self, wallets_with_edges: list, vasp_lookup: dict, n_clusters: int = 3):
        """
        wallets_with_edges: list of (Wallet, [WalletEdge]) tuples.
        Returns one entry per wallet with its cluster id, plus a short
        description of each cluster derived from its centroid.
        """
        if len(wallets_with_edges) < n_clusters:
            n_clusters = max(1, len(wallets_with_edges))

        X = np.array([
            extract_features(w, edges, vasp_lookup) for w, edges in wallets_with_edges
        ])
        scaled = self._scaler.transform(X)
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit(scaled)

        # describe each cluster by its centroid's most distinctive features
        centroids = self._scaler.inverse_transform(km.cluster_centers_)
        descriptions = {}
        for cid, centroid in enumerate(centroids):
            mixer_share, vasp_share, io_ratio, tx_count = (
                centroid[FEATURE_NAMES.index("mixer_interaction_share")],
                centroid[FEATURE_NAMES.index("vasp_interaction_share")],
                centroid[FEATURE_NAMES.index("in_out_ratio")],
                centroid[FEATURE_NAMES.index("tx_count")],
            )
            if mixer_share > 0.25:
                desc = "Elevated mixer interaction"
            elif vasp_share > 0.5 and tx_count > 150:
                desc = "High-volume, exchange-heavy activity"
            elif io_ratio < 0.5:
                desc = "Predominantly outbound fund movement"
            else:
                desc = "Low-volume, mixed counterparties"
            descriptions[cid] = desc

        return [
            {"address": w.address, "cluster_id": int(km.labels_[i]),
             "cluster_description": descriptions[int(km.labels_[i])]}
            for i, (w, edges) in enumerate(wallets_with_edges)
        ]


ml_engine = MLEngine()
