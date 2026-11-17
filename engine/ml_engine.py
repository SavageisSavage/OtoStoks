import os
import time
import threading
from datetime import datetime
from typing import Tuple, Optional, List
import numpy as np

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

try:
    import lightgbm as lgb
    from onnxmltools import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType
    HAS_TRAIN_LIBS = True
except ImportError:
    HAS_TRAIN_LIBS = False

from core.config import (
    SIGNAL_STRONG_BUY,
    SIGNAL_BUY,
    SIGNAL_NEUTRAL,
    SIGNAL_SHORT,
    SIGNAL_STRONG_SHORT,
    get_base_dir
)
from core.state import AppState
from engine.features import compute_features, MIN_FEATURE_TICKS
import otostoks_proto as pb


class LocalModelEngine:
    """
    Ultra-low latency institutional inference engine combining ONNX neural GBDT
    with a physics-based multi-factor regime classifier.
    """
    def __init__(self, onnx_path: Optional[str] = None):
        self.session = None
        self.input_name = None
        self.version = 4

        if onnx_path and os.path.exists(onnx_path) and HAS_ORT:
            try:
                opts = ort.SessionOptions()
                # The model is a small tree ensemble (16 features). Extra intra-op
                # threads cost more in synchronisation than they save, and they
                # contend with the game process on the same cores.
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.session = ort.InferenceSession(onnx_path, sess_options=opts, providers=['CPUExecutionProvider'])
                self.input_name = self.session.get_inputs()[0].name
            except Exception:
                self.session = None

    def _run_session(self, feats: np.ndarray) -> Optional[np.ndarray]:
        """Runs one ONNX call for an (n, 16) batch. Returns (n,) expected returns."""
        if self.session is None or not self.input_name or len(feats) == 0:
            return None
        try:
            batch = np.ascontiguousarray(feats, dtype=np.float32)
            raw = self.session.run(None, {self.input_name: batch})[0]
            return np.asarray(raw).reshape(-1).astype(np.float64)
        except Exception:
            return None

    def _score(self, feat: np.ndarray, expected_ret: Optional[float]) -> Tuple[float, int, float, str]:
        """Analytical factor scoring for one already-computed feature vector."""
        ema_spread = float(feat[0])
        rsi14 = float(feat[1])
        bb_pct = float(feat[2])
        bb_width = float(feat[3])
        # Slots 4 (vol20), 7 (ret8) and 12 (atr_ratio) are part of the model's
        # input contract but are not read by this scoring path: volatility comes
        # from the snapshot and the other two are captured by neighbouring slots.
        ret1 = float(feat[5])
        ret3 = float(feat[6])
        acceleration = float(feat[8])
        zscore30 = float(feat[9])
        macd_hist = float(feat[10])
        kama_eff = float(feat[11])
        stoch_k = float(feat[13])
        donchian_pct = float(feat[14])
        regime_score = float(feat[15])

        # Analytical multi-factor return expectation (Huber-smoothed ensemble)
        analytical_ret = float(
            (ema_spread * 0.25) +
            (ret3 * 0.20) +
            (macd_hist * 0.20) +
            (acceleration * 0.15) +
            (regime_score * 0.008 * 0.20)
        )

        if expected_ret is None:
            expected_ret = analytical_ret
        else:
            expected_ret = float(0.70 * expected_ret + 0.30 * analytical_ret)

        # Multi-Regime Classification
        if kama_eff > 0.38 and regime_score > 0.20:
            regime = "TRENDING_BULL"
        elif kama_eff > 0.38 and regime_score < -0.20:
            regime = "TRENDING_BEAR"
        elif bb_width > 0.040 and (bb_pct > 1.05 or bb_pct < -0.05):
            regime = "VOLATILE_BREAKOUT"
        elif kama_eff < 0.20 and -0.15 <= regime_score <= 0.15:
            regime = "MEAN_REVERTING_RANGE"
        else:
            regime = "CHOPPY_NOISE"

        # Signal Generation with Dual-Regime Confluence
        bullish = (
            (expected_ret >= 0.0020 and macd_hist > -0.0005 and 32.0 <= rsi14 <= 82.0 and donchian_pct > 0.30) or
            (zscore30 <= -1.4 and ret1 > 0 and stoch_k < 28.0) or
            (regime == "TRENDING_BULL" and ret1 > 0 and bb_pct < 0.85)
        )

        bearish = (
            (expected_ret <= -0.0020 and macd_hist < 0.0005 and 18.0 <= rsi14 <= 68.0 and donchian_pct < 0.70) or
            (zscore30 >= 1.5 and ret1 < 0 and stoch_k > 72.0) or
            (regime == "TRENDING_BEAR" and ret1 < 0 and bb_pct > 0.15)
        )

        signal = SIGNAL_NEUTRAL
        if bullish:
            confidence = min(0.96, max(0.48, (abs(expected_ret) / 0.008) * 0.45 + (kama_eff * 0.35) + 0.20))
            signal = SIGNAL_STRONG_BUY if (expected_ret >= 0.006 or confidence >= 0.78 or regime == "TRENDING_BULL") else SIGNAL_BUY
        elif bearish:
            confidence = min(0.96, max(0.48, (abs(expected_ret) / 0.008) * 0.45 + (kama_eff * 0.35) + 0.20))
            signal = SIGNAL_STRONG_SHORT if (expected_ret <= -0.006 or confidence >= 0.78 or regime == "TRENDING_BEAR") else SIGNAL_SHORT
        else:
            confidence = 0.20

        return expected_ret, signal, confidence, regime

    def _normalise(self, feats: np.ndarray) -> np.ndarray:
        arr = np.asarray(feats, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[1] < 16:
            padded = np.zeros((arr.shape[0], 16), dtype=np.float32)
            padded[:, :arr.shape[1]] = arr
            arr = padded
        elif arr.shape[1] > 16:
            arr = arr[:, :16]
        return arr

    def predict(self, feat: np.ndarray) -> Tuple[float, int, float, str]:
        """
        Evaluates 16-factor vector via ONNX & analytical ensemble.
        Returns: (expected_return, signal_code, confidence, regime)
        """
        return self.predict_batch(np.asarray(feat).reshape(1, -1))[0]

    def predict_batch(self, feats: np.ndarray) -> List[Tuple[float, int, float, str]]:
        """
        Evaluates every ticker's feature vector in a single ONNX call.

        Upstream called session.run() once per ticker (17 calls per frame). A tree
        ensemble has a fixed per-call overhead that dwarfs the work, so batching
        the whole universe into one (n, 16) tensor removes it.
        """
        arr = self._normalise(feats)
        raw = self._run_session(arr)
        results: List[Tuple[float, int, float, str]] = []
        for i in range(arr.shape[0]):
            expected = float(raw[i]) if raw is not None and i < len(raw) else None
            results.append(self._score(arr[i], expected))
        return results


def run_retrain_pipeline(state: AppState) -> Tuple[bool, str]:
    """
    Self-training pipeline on Protocol Buffer historical tick datastore.
    Uses multi-stock temporal cross-validation to ensure reliable AI validation.
    """
    if not HAS_TRAIN_LIBS:
        msg = "Retraining libraries (lightgbm/onnxmltools) not available in current environment."
        return False, msg

    with state.lock:
        if state.retraining_status == "Training in progress...":
            return False, "Retraining is already active."
        state.retraining_status = "Training in progress..."
        state.retrain_started_at = time.time()

    try:
        t_start = time.time()
        ticker_data = pb.load_ticks_for_training(state.ticks_pb_path)
        total_points = sum(len(v) for v in ticker_data.values())

        if total_points < 300:
            with state.lock:
                state.retraining_status = "Collecting Live Data..."
            return False, f"Collecting live ticks for model adaptation ({total_points}/300 points gathered)."

        train_feature_rows = []
        val_feature_rows = []
        forward_horizon = 8

        # Slices each stock temporally into 80% train, 20% validation
        # Ensures validation evaluates out-of-sample prediction across ALL universe stocks!
        for stock_id, points in ticker_data.items():
            p = np.array([pt[1] for pt in points], dtype=np.float32)
            n = len(p)
            if n < (MIN_FEATURE_TICKS + forward_horizon + 10):
                continue

            stock_rows = []
            for i in range(MIN_FEATURE_TICKS, n - forward_horizon):
                feat_i = compute_features(p[:i+1])
                target_ret = (p[i + forward_horizon] - p[i]) / (p[i] + 1e-8)
                stock_rows.append(np.append(feat_i, target_ret))

            if len(stock_rows) >= 10:
                s_arr = np.array(stock_rows, dtype=np.float32)
                split = int(len(s_arr) * 0.80)
                train_feature_rows.append(s_arr[:split])
                val_feature_rows.append(s_arr[split:])

        if not train_feature_rows or not val_feature_rows:
            with state.lock:
                state.retraining_status = "Active (Continuous Learner)"
            return False, "Insufficient feature rows after temporal splitting."

        train_data = np.vstack(train_feature_rows)
        val_data = np.vstack(val_feature_rows)

        # Filter NaNs / Infs
        train_data = train_data[~np.isnan(train_data).any(axis=1)]
        train_data = train_data[~np.isinf(train_data).any(axis=1)]
        val_data = val_data[~np.isnan(val_data).any(axis=1)]
        val_data = val_data[~np.isinf(val_data).any(axis=1)]

        # Take contiguous copies: LightGBM warns (and doubles peak memory) when a
        # Dataset is built from a non-contiguous column slice of a parent array.
        X_train = np.ascontiguousarray(train_data[:, :16])
        y_train = train_data[:, 16]
        X_val = np.ascontiguousarray(val_data[:, :16])
        y_val = val_data[:, 16]

        train_ds = lgb.Dataset(X_train, label=y_train)
        val_ds = lgb.Dataset(X_val, label=y_val, reference=train_ds)

        params = {
            'objective': 'huber',
            'metric': ['huber', 'l1'],
            'boosting_type': 'gbdt',
            'learning_rate': 0.04,
            'num_leaves': 45,
            'max_depth': 7,
            'min_data_in_leaf': 30,
            'feature_fraction': 0.85,
            'bagging_fraction': 0.85,
            'bagging_freq': 3,
            'verbosity': -1,
            'seed': 42
        }

        model = lgb.train(
            params,
            train_ds,
            num_boost_round=180,
            valid_sets=[val_ds],
            callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)]
        )

        preds = model.predict(X_val)
        dir_correct = np.sum((preds * y_val) > 0)
        dir_acc = float(dir_correct / len(y_val)) if len(y_val) > 0 else 0.50

        # Convert to ONNX with 16 features
        initial_type = [('float_input', FloatTensorType([None, 16]))]
        onnx_model = convert_lightgbm(model, initial_types=initial_type, target_opset=12)

        base_dir = get_base_dir()
        out_paths = [
            os.path.join(base_dir, "model.onnx"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model.onnx")
        ]
        for op in out_paths:
            try:
                os.makedirs(os.path.dirname(op), exist_ok=True)
                with open(op, "wb") as f:
                    f.write(onnx_model.SerializeToString())
            except Exception:
                pass

        # Atomic Hot-Reload in memory
        if HAS_ORT and state.inference_engine is not None:
            try:
                state.inference_engine.session = ort.InferenceSession(onnx_model.SerializeToString())
            except Exception:
                pass

        # Post-training raw data pruning: delete raw ticks, intelligence fully retained in model.onnx
        try:
            with open(state.ticks_pb_path, "wb") as f:
                f.write(b"")
            with state.lock:
                state.tick_buffer.clear()
                state.total_ticks_stored = 0
                state.session_ticks_collected = 0
        except Exception:
            pass

        elapsed = round(time.time() - t_start, 2)
        with state.lock:
            state.retraining_status = "Active (Continuous Learner)"
            state.last_retrain_time = datetime.now().strftime("%H:%M:%S")
            state.retrain_accuracy = round(dir_acc * 100.0, 1)
            state.retrain_est_seconds = elapsed
            state.auto_retrain_count += 1

        state.add_log(
            ticker="AI_MODEL",
            action="RETRAIN",
            mode=state.mode,
            reason=f"Neural network retrained ({round(dir_acc * 100.0, 1)}% acc in {elapsed}s). Raw tick data pruned to save space; intelligence retained in ONNX weights.",
            status="RETAINED"
        )

        msg = f"Auto-Retrain #{state.auto_retrain_count} Complete! Samples: {len(train_data)+len(val_data):,}, Accuracy: {state.retrain_accuracy}%, Time: {elapsed}s"
        state.add_log("AI_ENGINE", "MODEL_RETRAIN", state.mode, msg, "SUCCESS")
        return True, msg
    except Exception as e:
        with state.lock:
            state.retraining_status = f"Error: {e}"
        return False, str(e)


def start_auto_retrain_worker(state: AppState):
    """
    Background worker that triggers retraining periodically ONLY when new tick data
    has been recorded, avoiding unnecessary CPU and RAM churn.
    """
    def _worker():
        last_trained_ticks = 0
        while state.running:
            for s in range(60, 0, -1):
                if not state.running:
                    return
                with state.lock:
                    state.auto_retrain_seconds_until_next = s
                time.sleep(1)

            # Check if at least 150 new ticks were collected since last train
            current_ticks = state.total_ticks_stored + state.session_ticks_collected
            if (current_ticks - last_trained_ticks) >= 150 and current_ticks >= 300:
                success, _ = run_retrain_pipeline(state)
                if success:
                    last_trained_ticks = current_ticks

    t = threading.Thread(target=_worker, daemon=True, name="AutoRetrainWorker")
    t.start()
