import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
import warnings

warnings.filterwarnings('ignore')

# Global cache for trained models (in-memory)
_model_cache = {
    'model_mean': None,
    'model_lower': None,
    'model_upper': None,
    'last_data_hash': None
}

class ENSOForecaster:
    """Predicts MEI values 6 months ahead using ML."""

    # Absolute path so this works regardless of CWD (local dev vs Render)
    _DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'raw' / 'mei_index.csv'

    def __init__(self, data_path=None):
        self.data_path = Path(data_path) if data_path else self._DEFAULT_DATA_PATH
        self.model_mean = None
        self.model_lower = None
        self.model_upper = None
        self.data = None
        self._load_and_prepare_data()
        self._train_models()

    def _load_and_prepare_data(self):
        """Load MEI data and clean it."""
        self.data = pd.read_csv(self.data_path)
        self.data['date'] = pd.to_datetime(self.data['date'])

        # Remove the header row that has year value (first row with strange value)
        self.data = self.data[(self.data['mei_value'] >= -3) & (self.data['mei_value'] <= 3)]
        self.data = self.data.sort_values('date').reset_index(drop=True)

    def _create_lag_features(self, df):
        """Create lag features for ML model."""
        df = df.copy()
        df['lag1'] = df['mei_value'].shift(1)
        df['lag2'] = df['mei_value'].shift(2)
        df['lag3'] = df['mei_value'].shift(3)
        df['lag6'] = df['mei_value'].shift(6)
        df['rolling_mean_3'] = df['mei_value'].rolling(window=3).mean()
        df['rolling_std_3'] = df['mei_value'].rolling(window=3).std()

        # Forward fill NaN from rolling windows
        df['rolling_std_3'] = df['rolling_std_3'].fillna(0)

        # Drop rows with NaN from lag features (first 6 rows)
        return df.dropna()

    def _train_models(self):
        """Train three GBR models or use cached versions."""
        global _model_cache

        df = self._create_lag_features(self.data)

        # Hash the data to detect changes
        data_hash = hash(pd.util.hash_pandas_object(df['mei_value'], index=True).sum())

        # Return cached models if data hasn't changed
        if (
            _model_cache['last_data_hash'] == data_hash and
            _model_cache['model_mean'] is not None
        ):
            self.model_mean = _model_cache['model_mean']
            self.model_lower = _model_cache['model_lower']
            self.model_upper = _model_cache['model_upper']
            return

        feature_cols = ['lag1', 'lag2', 'lag3', 'lag6', 'rolling_mean_3', 'rolling_std_3']
        X = df[feature_cols]
        y = df['mei_value']

        # Model for mean prediction (lighter config for speed)
        self.model_mean = GradientBoostingRegressor(
            n_estimators=50,
            learning_rate=0.1,
            max_depth=4,
            random_state=42
        )
        self.model_mean.fit(X, y)

        # Model for lower bound (10th percentile)
        self.model_lower = GradientBoostingRegressor(
            n_estimators=50,
            learning_rate=0.1,
            max_depth=4,
            loss='quantile',
            alpha=0.1,
            random_state=42
        )
        self.model_lower.fit(X, y)

        # Model for upper bound (90th percentile)
        self.model_upper = GradientBoostingRegressor(
            n_estimators=50,
            learning_rate=0.1,
            max_depth=4,
            loss='quantile',
            alpha=0.9,
            random_state=42
        )
        self.model_upper.fit(X, y)

        # Update cache
        _model_cache['model_mean'] = self.model_mean
        _model_cache['model_lower'] = self.model_lower
        _model_cache['model_upper'] = self.model_upper
        _model_cache['last_data_hash'] = data_hash

    def _classify_phase(self, mei_value):
        """Classify ENSO phase based on MEI value."""
        if mei_value >= 0.5:
            return 'El Niño'
        elif mei_value <= -0.5:
            return 'La Niña'
        else:
            return 'Neutral'

    def forecast(self, months_ahead=6):
        """Generate forecast for next N months with trend detection."""
        df = self._create_lag_features(self.data).copy()
        feature_cols = ['lag1', 'lag2', 'lag3', 'lag6', 'rolling_mean_3', 'rolling_std_3']

        # Detect trend direction from last 6 months
        last_6_months = df['mei_value'].tail(6).values
        trend_slope = np.polyfit(range(len(last_6_months)), last_6_months, 1)[0]

        forecasts = []
        last_date = pd.to_datetime(df['date'].iloc[-1])
        last_mei = df['mei_value'].iloc[-1]

        # Use last known values as starting point
        current_row = df.iloc[-1][feature_cols].values.reshape(1, -1)

        for i in range(months_ahead):
            # Predict using ML model
            mei_ml_pred = self.model_mean.predict(current_row)[0]

            # Add trend adjustment: if trending up (toward El Niño) or down (toward La Niña)
            trend_adjustment = trend_slope * (i + 1) * 0.5
            mei_pred = mei_ml_pred + trend_adjustment

            # Clamp to realistic bounds [-2, 2]
            mei_pred = np.clip(mei_pred, -2.0, 2.0)

            mei_lower = self.model_lower.predict(current_row)[0] + trend_adjustment
            mei_upper = self.model_upper.predict(current_row)[0] + trend_adjustment

            # Ensure bounds are valid
            mei_lower = np.clip(mei_lower, -2.0, mei_pred)
            mei_upper = np.clip(mei_upper, mei_pred, 2.0)

            future_date = last_date + timedelta(days=30 * (i + 1))
            month_str = future_date.strftime('%b %y')

            forecasts.append({
                'month': month_str,
                'mei': round(mei_pred, 2),
                'lower': round(mei_lower, 2),
                'upper': round(mei_upper, 2),
                'is_forecast': True
            })

            # Update features for next iteration (rolling forecast)
            mei_prev_1 = mei_pred
            mei_prev_2 = current_row[0][0]  # old lag1 → new lag2
            mei_prev_3 = current_row[0][1]  # old lag2 → new lag3
            # Average the three most recent predictions (not mei_pred twice)
            rolling_mean = (mei_pred + mei_prev_2 + mei_prev_3) / 3
            rolling_std = np.std([mei_pred, mei_prev_2, mei_prev_3])

            current_row = np.array([[
                mei_prev_1,           # lag1
                mei_prev_2,           # lag2
                mei_prev_3,           # lag3
                current_row[0][3],    # lag6 (keep last value)
                rolling_mean,         # rolling_mean_3
                rolling_std           # rolling_std_3
            ]])

        return forecasts

    def get_full_forecast(self):
        """Get historical + forecast data."""
        df = self.data[self.data['mei_value'] >= -3].copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        # Last 12 months of history
        historical = df.tail(12).copy()
        historical['month'] = historical['date'].dt.strftime('%b %y')
        historical_data = [
            {
                'month': row['month'],
                'mei': round(row['mei_value'], 2),
                'is_forecast': False
            }
            for _, row in historical.iterrows()
        ]

        # Get forecast (extended to 9 months to show phase transitions)
        forecast_data = self.forecast(months_ahead=9)

        # Determine predicted phase from forecast
        if len(forecast_data) > 0:
            # Get last forecasted month and trend
            predicted_mei = forecast_data[-1]['mei']
            forecast_trend = forecast_data[-1]['mei'] - forecast_data[0]['mei']

            # Classify based on value AND trend direction
            if forecast_trend > 0.3:  # Strong upward trend suggests transition to El Niño
                predicted_phase = 'El Nino (Transition)'
            elif forecast_trend < -0.3:  # Strong downward trend
                predicted_phase = 'Deepening La Nina'
            else:
                # Use standard classification
                predicted_phase = self._classify_phase(predicted_mei)

            # Calculate confidence (blend spread-based and trend-based confidence)
            avg_spread = np.mean([abs(f['upper'] - f['lower']) for f in forecast_data])
            spread_confidence = max(50, min(95, 100 - (avg_spread * 12)))
            trend_confidence = min(95, 60 + abs(forecast_trend) * 50)
            # Weight: spread 60%, trend strength 40%
            confidence = 0.6 * spread_confidence + 0.4 * trend_confidence
            confidence = max(50, min(95, confidence))

        else:
            predicted_phase = 'Unknown'
            confidence = 0

        return {
            'historical': historical_data,
            'forecast': forecast_data,
            'predicted_phase': predicted_phase,
            'confidence_pct': int(confidence),
            'model_info': 'Gradient Boosting with trend detection (NOAA MEI 1979–2026)'
        }


def run_forecast():
    """Main function to get current forecast."""
    try:
        forecaster = ENSOForecaster()
        return forecaster.get_full_forecast()
    except Exception as e:
        return {
            'error': str(e),
            'historical': [],
            'forecast': [],
            'predicted_phase': 'Unknown',
            'confidence_pct': 0,
            'model_info': 'Error loading model'
        }
