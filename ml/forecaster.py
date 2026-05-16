import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
import warnings

warnings.filterwarnings('ignore')

class ENSOForecaster:
    """Predicts MEI values 6 months ahead using ML."""

    def __init__(self, data_path='data/raw/mei_index.csv'):
        self.data_path = Path(data_path)
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
        """Train three GBR models: mean, lower quartile, upper quartile."""
        df = self._create_lag_features(self.data)

        feature_cols = ['lag1', 'lag2', 'lag3', 'lag6', 'rolling_mean_3', 'rolling_std_3']
        X = df[feature_cols]
        y = df['mei_value']

        # Model for mean prediction
        self.model_mean = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.model_mean.fit(X, y)

        # Model for lower bound (10th percentile)
        self.model_lower = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            loss='quantile',
            alpha=0.1,
            random_state=42
        )
        self.model_lower.fit(X, y)

        # Model for upper bound (90th percentile)
        self.model_upper = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            loss='quantile',
            alpha=0.9,
            random_state=42
        )
        self.model_upper.fit(X, y)

    def _classify_phase(self, mei_value):
        """Classify ENSO phase based on MEI value."""
        if mei_value >= 0.5:
            return 'El Niño'
        elif mei_value <= -0.5:
            return 'La Niña'
        else:
            return 'Neutral'

    def forecast(self, months_ahead=6):
        """Generate forecast for next N months."""
        df = self._create_lag_features(self.data).copy()
        feature_cols = ['lag1', 'lag2', 'lag3', 'lag6', 'rolling_mean_3', 'rolling_std_3']

        forecasts = []
        last_date = pd.to_datetime(df['date'].iloc[-1])

        # Use last known values as starting point
        current_row = df.iloc[-1][feature_cols].values.reshape(1, -1)

        for i in range(months_ahead):
            # Predict for this month
            mei_pred = self.model_mean.predict(current_row)[0]
            mei_lower = self.model_lower.predict(current_row)[0]
            mei_upper = self.model_upper.predict(current_row)[0]

            # Ensure bounds are valid
            mei_lower = min(mei_lower, mei_pred)
            mei_upper = max(mei_upper, mei_pred)

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
            mei_prev_2 = current_row[0][0]  # lag1 becomes lag2
            mei_prev_3 = current_row[0][1]  # lag2 becomes lag3
            # lag6 and rolling stats would need more data, approximate
            rolling_mean = (mei_pred + mei_prev_1 + mei_prev_2) / 3
            rolling_std = np.std([mei_pred, mei_prev_1, mei_prev_2])

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

        # Get forecast
        forecast_data = self.forecast(months_ahead=6)

        # Determine predicted phase from forecast
        if len(forecast_data) > 0:
            predicted_mei = forecast_data[-1]['mei']  # Last forecasted month
            predicted_phase = self._classify_phase(predicted_mei)

            # Calculate confidence (based on upper-lower spread)
            avg_spread = np.mean([abs(f['upper'] - f['lower']) for f in forecast_data])
            confidence = max(50, min(95, 100 - (avg_spread * 15)))  # Heuristic confidence
        else:
            predicted_phase = 'Unknown'
            confidence = 0

        return {
            'historical': historical_data,
            'forecast': forecast_data,
            'predicted_phase': predicted_phase,
            'confidence_pct': int(confidence),
            'model_info': 'Gradient Boosting (lag features, trained on NOAA MEI 1979–2026)'
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
