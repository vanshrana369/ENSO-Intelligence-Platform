import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
import glob

# Absolute path to project root (two levels up from this file: ml/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _native(obj):
    """Recursively convert NumPy scalars/arrays to plain Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_native(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

def get_phase_probabilities(mei_value, mei_data):
    """
    Calculate forward-looking probability of each ENSO phase 6 months ahead,
    based on historical transitions from similar MEI levels.

    Logic: find all past months where MEI was within ±0.4 of the current value,
    then look at what phase occurred 6 months LATER. This gives a true
    transition probability rather than a trivially circular frequency count
    (which always returns ~100% for whichever phase the current value is in).
    """
    window = 0.4
    horizon = 6  # months ahead

    mei_values = mei_data['mei_value'].values
    n = len(mei_values)

    el_nino_count = 0
    la_nina_count = 0
    neutral_count = 0
    total = 0

    for i in range(n - horizon):
        if abs(mei_values[i] - mei_value) <= window:
            future_val = mei_values[i + horizon]
            if future_val >= 0.5:
                el_nino_count += 1
            elif future_val <= -0.5:
                la_nina_count += 1
            else:
                neutral_count += 1
            total += 1

    if total == 0:
        # Fallback: no historical analog — use climatological base rates
        return {'el_nino': 35, 'la_nina': 35, 'neutral': 30}

    return {
        'el_nino': max(0, min(100, round(el_nino_count / total * 100))),
        'la_nina': max(0, min(100, round(la_nina_count / total * 100))),
        'neutral': max(0, min(100, round(neutral_count / total * 100)))
    }


def _build_lag_features(df):
    """Shared feature engineering for backtest — mirrors forecaster.py."""
    df = df.copy().reset_index(drop=True)
    v = df['mei_value']
    df['lag1']  = v.shift(1)
    df['lag2']  = v.shift(2)
    df['lag3']  = v.shift(3)
    df['lag6']  = v.shift(6)
    df['lag9']  = v.shift(9)
    df['lag12'] = v.shift(12)
    df['rolling_mean_3'] = v.rolling(3).mean()
    df['rolling_std_3']  = v.rolling(3).std().fillna(0)
    df['rolling_mean_6'] = v.rolling(6).mean()
    df['rolling_std_6']  = v.rolling(6).std().fillna(0)
    months = pd.to_datetime(df['date']).dt.month
    df['month_sin'] = np.sin(2 * np.pi * months / 12)
    df['month_cos'] = np.cos(2 * np.pi * months / 12)
    return df.dropna()


def get_forecast_accuracy(mei_data):
    """
    Backtest the Gradient Boosting model (same architecture as forecaster.py)
    via a single 80/20 train-test split.
    Returns MAE, accuracy (±0.3), and direction accuracy.
    """
    if len(mei_data) < 30:
        return {'mae': 0, 'accuracy_pct': 0, 'direction_accuracy': 0}

    df = _build_lag_features(mei_data)
    if len(df) < 30:
        return {'mae': 0, 'accuracy_pct': 0, 'direction_accuracy': 0}

    feature_cols = ['lag1', 'lag2', 'lag3', 'lag6', 'lag9', 'lag12',
                    'rolling_mean_3', 'rolling_std_3', 'rolling_mean_6', 'rolling_std_6',
                    'month_sin', 'month_cos']

    split = int(len(df) * 0.8)
    train, test = df[:split], df[split:]

    model = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=4,
        subsample=0.8, min_samples_split=5, random_state=42
    )
    model.fit(train[feature_cols], train['mei_value'])
    predictions = model.predict(test[feature_cols])
    actuals = test['mei_value'].values

    mae = float(np.mean(np.abs(predictions - actuals)))
    accuracy = float(np.mean(np.abs(predictions - actuals) < 0.3) * 100)

    pred_dir   = np.diff(predictions) > 0
    actual_dir = np.diff(actuals) > 0
    direction_acc = float(np.mean(pred_dir == actual_dir) * 100) if len(pred_dir) > 0 else 0.0

    return {
        'mae': round(mae, 3),
        'accuracy_pct': int(accuracy),
        'direction_accuracy': int(direction_acc)
    }


def detect_anomalies(mei_data):
    """
    Detect unusual MEI movements using z-score on month-over-month changes.
    """
    if len(mei_data) < 2:
        return {'is_anomaly': False, 'z_score': 0, 'message': 'Not enough data'}

    mei_values = mei_data['mei_value'].values
    changes = np.diff(mei_values)

    if len(changes) < 2:
        return {'is_anomaly': False, 'z_score': 0, 'message': 'Not enough history'}

    # Z-score of last change
    mean_change = np.mean(changes)
    std_change = np.std(changes)

    if std_change == 0:
        z_score = 0
    else:
        z_score = (changes[-1] - mean_change) / std_change

    is_anomaly = abs(z_score) > 2.0

    if is_anomaly:
        message = f"MEI moved {abs(changes[-1]):.2f} - unusually {('fast' if abs(changes[-1]) > 0.5 else 'volatile')}"
    else:
        message = "MEI changing at normal rate"

    return {
        'is_anomaly': is_anomaly,
        'z_score': round(z_score, 2),
        'message': message
    }


def seasonal_decomposition(mei_data):
    """
    Simple decomposition into trend + seasonal + residual.
    Uses numpy-based approach (no statsmodels needed).
    """
    if len(mei_data) < 24:
        return {'trend': [], 'seasonal': [], 'residual': []}

    values = mei_data['mei_value'].values

    # Trend: 12-month moving average
    trend = pd.Series(values).rolling(window=12, center=True).mean().bfill().ffill().values

    # Detrended
    detrended = values - trend

    # Seasonal: average of each month position across years
    seasonal = np.zeros_like(values)
    for i in range(len(values)):
        month_pos = i % 12
        # Average all values at this month position
        similar_months = [detrended[j] for j in range(len(values)) if j % 12 == month_pos]
        seasonal[i] = np.mean(similar_months)

    # Residual
    residual = values - trend - seasonal

    return {
        'trend': trend.tolist(),
        'seasonal': seasonal.tolist(),
        'residual': residual.tolist()
    }


def commodity_sensitivity(mei_data, commodity_path=None):
    """
    Calculate Pearson correlation between MEI and each commodity price.
    Returns results for all commodities found in the CSV (dynamic).
    """
    if commodity_path is None:
        commodity_path = str(_PROJECT_ROOT / 'data' / 'raw')

    commodity_files = glob.glob(f"{commodity_path}/commodity_prices_*.csv")
    if not commodity_files:
        return {'wheat': 0, 'crude_oil': 0, 'soybean': 0}

    try:
        prices_df = pd.read_csv(max(commodity_files))
        prices_df['date'] = pd.to_datetime(prices_df['date'])

        # Monthly MEI series keyed by year-month period (MEI is already monthly).
        mei_monthly = mei_data.copy()
        mei_monthly['ym'] = pd.to_datetime(mei_monthly['date']).dt.to_period('M')
        mei_monthly = mei_monthly.groupby('ym')['mei_value'].mean()

        all_commodities = prices_df['commodity'].str.lower().unique().tolist()
        correlations = {}
        for commodity in all_commodities:
            sub = prices_df[prices_df['commodity'].str.lower() == commodity].copy()
            # Resample daily prices to monthly mean, keyed by year-month period.
            sub['ym'] = sub['date'].dt.to_period('M')
            price_monthly = sub.groupby('ym')['price'].mean()

            # Inner-join on the year-month key → only overlapping aligned points.
            aligned = pd.concat(
                [price_monthly.rename('price'), mei_monthly.rename('mei')],
                axis=1, join='inner'
            ).dropna()

            if len(aligned) < 3:
                correlations[commodity] = 0
                continue

            corr = np.corrcoef(aligned['mei'].values, aligned['price'].values)[0, 1]
            correlations[commodity] = round(float(corr), 2) if not np.isnan(corr) else 0
        return correlations if correlations else {'wheat': 0, 'crude_oil': 0, 'soybean': 0}
    except Exception:
        return {'wheat': 0, 'crude_oil': 0, 'soybean': 0}


def find_similar_events(mei_data, n_similar=3):
    """
    Find past 12-month MEI windows most similar to the current pattern.

    Level-aware: compares the RAW (non-normalized) current window against each
    historical window using RMSE, so the actual ENSO level matters (a La Niña-era
    window of all-negative values will NOT match a neutral/warming present).
    """
    if len(mei_data) < 24:
        return []

    # Current 12-month window (raw — level information preserved).
    current_window = mei_data['mei_value'].tail(12).values

    candidates = []

    # Check all historical 12-month windows.
    for start in range(len(mei_data) - 24):
        window = mei_data['mei_value'].iloc[start:start+12].values

        # RMSE between raw windows → respects actual level, not just shape.
        rmse = float(np.sqrt(np.mean((current_window - window) ** 2)))
        # Monotonic bounded transform: rmse=0 → 100%, larger rmse → lower %.
        similarity_pct = int(round(100 * np.exp(-rmse)))

        start_date = mei_data['date'].iloc[start]
        end_date = mei_data['date'].iloc[start+11]

        # Simple outcome: what happened in the next 12 months?
        if start + 24 < len(mei_data):
            next_period = mei_data['mei_value'].iloc[start+12:start+24].values
            avg_next = np.mean(next_period)

            if avg_next > 0.5:
                outcome = "El Niño emerged"
            elif avg_next < -0.5:
                outcome = "La Niña persisted"
            else:
                outcome = "Transitioned to Neutral"
        else:
            outcome = "Recent event"

        candidates.append({
            'rmse': rmse,
            'period': f"{pd.to_datetime(start_date).strftime('%Y-%m')} to {pd.to_datetime(end_date).strftime('%Y-%m')}",
            'similarity_pct': similarity_pct,
            'outcome': outcome
        })

    # Rank by smallest distance (most similar first).
    candidates = sorted(candidates, key=lambda x: x['rmse'])

    # Prefer reasonably strong matches; fall back to closest if none qualify.
    strong = [c for c in candidates if c['similarity_pct'] >= 60]
    selected = (strong if strong else candidates)[:n_similar]

    return [{'period': c['period'], 'similarity_pct': c['similarity_pct'], 'outcome': c['outcome']}
            for c in selected]


def run_analytics(mei_data_path=None, current_mei=None):
    """
    Main function: compute all analytics and return as single JSON.

    current_mei: optional live Niño3.4 / MEI override.  When provided it is used
    for phase probability calculations so the distribution reflects the actual
    current ENSO state rather than the (potentially lagged) CSV tail value.
    """
    try:
        if mei_data_path is None:
            mei_data_path = str(_PROJECT_ROOT / 'data' / 'raw' / 'mei_index.csv')

        # Load data
        mei_data = pd.read_csv(mei_data_path)
        mei_data['date'] = pd.to_datetime(mei_data['date'])
        mei_data = mei_data[(mei_data['mei_value'] >= -3) & (mei_data['mei_value'] <= 3)]
        mei_data = mei_data.sort_values('date').reset_index(drop=True)

        # Use the live value for phase probabilities if supplied; otherwise fall back
        # to the CSV tail (which may be months behind the real current state).
        prob_mei = current_mei if current_mei is not None else mei_data['mei_value'].iloc[-1]

        result = {
            'phase_probabilities': get_phase_probabilities(prob_mei, mei_data),
            'forecast_accuracy': get_forecast_accuracy(mei_data),
            'anomaly': detect_anomalies(mei_data),
            'seasonal': seasonal_decomposition(mei_data),
            'commodity_sensitivity': commodity_sensitivity(mei_data),
            'similar_events': find_similar_events(mei_data),
            'status': 'success'
        }
        return _native(result)
    except Exception as e:
        return {
            'phase_probabilities': {'el_nino': 33, 'la_nina': 33, 'neutral': 34},
            'forecast_accuracy': {'mae': 0, 'accuracy_pct': 0, 'direction_accuracy': 0},
            'anomaly': {'is_anomaly': False, 'z_score': 0, 'message': f'Compute error: {str(e)}'},
            'seasonal': {'trend': [], 'seasonal': [], 'residual': []},
            'commodity_sensitivity': {'wheat': 0, 'crude_oil': 0, 'soybean': 0},
            'similar_events': [],
            'status': f'error: {str(e)}'
        }
