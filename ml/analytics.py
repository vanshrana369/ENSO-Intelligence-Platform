import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity
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


def get_forecast_accuracy(mei_data):
    """
    Backtest: train on all but last 12 months, test on last 12 months.
    Return MAE, accuracy %, direction accuracy %.
    """
    if len(mei_data) < 24:
        return {'mae': 0, 'accuracy_pct': 0, 'direction_accuracy': 0}

    # Split: train on all but last 12, test on last 12
    train = mei_data[:-12].copy()
    test = mei_data[-12:].copy()

    if len(train) < 50:
        return {'mae': 0, 'accuracy_pct': 0, 'direction_accuracy': 0}

    # Simple rolling prediction: use mean of last 3 months as next month prediction
    predictions = []
    for i in range(len(test)):
        idx = len(train) + i
        if idx >= 3:
            # Predict using last 3 values before this point
            history = mei_data['mei_value'].iloc[:idx].tail(3).values
            pred = np.mean(history)
        else:
            pred = train['mei_value'].mean()
        predictions.append(pred)

    actuals = test['mei_value'].values
    predictions = np.array(predictions)

    # Metrics
    mae = np.mean(np.abs(predictions - actuals))

    # Direction accuracy: did we predict the right direction of change?
    pred_changes = np.diff(predictions) > 0
    actual_changes = np.diff(actuals) > 0
    direction_acc = np.mean(pred_changes == actual_changes) * 100 if len(pred_changes) > 0 else 0

    # Simple accuracy: within 0.3 of actual
    accuracy = np.mean(np.abs(predictions - actuals) < 0.3) * 100

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
    """
    correlations = {}

    if commodity_path is None:
        commodity_path = str(_PROJECT_ROOT / 'data' / 'raw')

    # Find latest commodity prices CSV
    commodity_files = glob.glob(f"{commodity_path}/commodity_prices_*.csv")
    if not commodity_files:
        return {'wheat': 0, 'crude_oil': 0, 'soybean': 0}

    try:
        latest_commodity = max(commodity_files)
        prices_df = pd.read_csv(latest_commodity)

        # Get commodities
        for commodity in ['wheat', 'crude_oil', 'soybean']:
            commodity_prices = prices_df[prices_df['commodity'].str.lower() == commodity.lower()]['price'].values

            if len(commodity_prices) > 10:
                # Truncate to same length for correlation
                min_len = min(len(commodity_prices), len(mei_data))
                corr = np.corrcoef(mei_data['mei_value'].tail(min_len).values,
                                   commodity_prices[-min_len:])[0, 1]
                correlations[commodity] = round(corr, 2)
            else:
                correlations[commodity] = 0
    except:
        correlations = {'wheat': 0, 'crude_oil': 0, 'soybean': 0}

    return correlations


def find_similar_events(mei_data, n_similar=3):
    """
    Find past 12-month MEI windows most similar to current pattern using cosine similarity.
    """
    if len(mei_data) < 24:
        return []

    # Current 12-month window
    current_window = mei_data['mei_value'].tail(12).values.reshape(1, -1)

    # Normalize for comparison
    current_window = (current_window - np.mean(current_window)) / (np.std(current_window) + 1e-6)

    similar_events = []

    # Check all historical 12-month windows
    for start in range(len(mei_data) - 24):
        window = mei_data['mei_value'].iloc[start:start+12].values.reshape(1, -1)
        window = (window - np.mean(window)) / (np.std(window) + 1e-6)

        # Cosine similarity
        similarity = cosine_similarity(current_window, window)[0, 0]

        if similarity > 0.7:  # Only keep highly similar
            start_date = mei_data['date'].iloc[start]
            end_date = mei_data['date'].iloc[start+11]

            # Simple outcome: what happened in next 12 months?
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

            similar_events.append({
                'period': f"{pd.to_datetime(start_date).strftime('%Y-%m')} to {pd.to_datetime(end_date).strftime('%Y-%m')}",
                'similarity_pct': int(similarity * 100),
                'outcome': outcome
            })

    # Sort by similarity, return top N
    similar_events = sorted(similar_events, key=lambda x: x['similarity_pct'], reverse=True)[:n_similar]

    return similar_events


def run_analytics(mei_data_path=None):
    """
    Main function: compute all analytics and return as single JSON.
    """
    try:
        if mei_data_path is None:
            mei_data_path = str(_PROJECT_ROOT / 'data' / 'raw' / 'mei_index.csv')

        # Load data
        mei_data = pd.read_csv(mei_data_path)
        mei_data['date'] = pd.to_datetime(mei_data['date'])
        mei_data = mei_data[(mei_data['mei_value'] >= -3) & (mei_data['mei_value'] <= 3)]
        mei_data = mei_data.sort_values('date').reset_index(drop=True)

        current_mei = mei_data['mei_value'].iloc[-1]

        result = {
            'phase_probabilities': get_phase_probabilities(current_mei, mei_data),
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
