from firebase_admin import firestore
import pandas as pd
import itertools
from sklearn.model_selection import train_test_split
from datetime import datetime
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

# Function to save predictions from Firestore
def SavePredictions(isin, predictions):
    try:
        # If predictions is a DataFrame, convert it to a list of dictionaries.
        if hasattr(predictions, "to_dict"):
            predictions = predictions.to_dict(orient="records")
            
        db = firestore.client()
        db.collection("predictions").document(isin).set({"predictions": predictions})
        print(f"Document added with ID: {isin}")
        return predictions
    except Exception as e:
        print(f"An error occurred: {e}")
        
# Function to get predictions from Firestore
def GetPredictions(isin):
    try:
        db = firestore.client()
        doc_ref = db.collection("predictions").document(isin)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"No document found for ID: {isin}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None        
    
# Function to process input data and return forecast
def forecast_from_data(data):
    # Convert input list to DataFrame
    df = pd.DataFrame(data, columns=['date', 'value'])
    df['date'] = pd.to_datetime(df['date'])

    # Examine data types and missing values
    print(df.info())
    print("\nPercentage of missing values per column:")
    print(df.isnull().sum() / len(df) * 100)

    # Summarize numerical features
    print("\nDescriptive statistics for numerical features:")

    # Identify the time range
    print("\nTime Range:")
    print(f"Earliest date: {df['date'].min()}")
    print(f"Latest date: {df['date'].max()}")

    # Calculate total time span
    earliest_date = df['date'].min()
    latest_date = df['date'].max()
    time_span = latest_date - earliest_date
    print(f"Total Time Span: {time_span.days} days")

    # Calculate the correlation matrix (excluding the 'date' column)
    correlation_matrix = df.drop(columns=['date']).corr()

    # Sort the DataFrame chronologically by the 'date' column
    df.sort_values(by='date', inplace=True)

    # Create a new column representing the day of the week
    df['DayOfWeek'] = df['date'].dt.dayofweek

    # Create lagged features
    for lag in [1, 7, 30]:
        df[f'value_Lag_{lag}'] = df['value'].shift(lag).fillna(method='ffill')

    # Create rolling statistics features
    for window in [7, 30]:
        df[f'value_Rolling_Mean_{window}'] = (
            df['value'].rolling(window=window).mean().fillna(method='ffill')
        )
        df[f'value_Rolling_Std_{window}'] = (
            df['value'].rolling(window=window).std().fillna(method='ffill')
        )

    # Extract month and year
    df['Month'] = df['date'].dt.month
    df['Year'] = df['date'].dt.year

    # Define features (X) and target variable (y)
    X = df.drop(columns=['date', 'value'])
    y = df['value']

    # Split data into training and testing sets using a time-based split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # Print the shapes of the training and testing sets
    print("X_train shape:", X_train.shape)
    print("y_train shape:", y_train.shape)
    print("X_test shape:", X_test.shape)
    print("y_test shape:", y_test.shape)

    # Reduced parameter grid
    param_grid = {
        'seasonality_mode': ['additive', 'multiplicative'],
        'seasonality_prior_scale': [0.1, 1.0],  
        'changepoint_prior_scale': [0.01, 0.1]  
    }

    # Generate all combinations of parameters
    all_params = [dict(zip(param_grid.keys(), v))
                  for v in itertools.product(*param_grid.values())]

    # Perform cross-validation and evaluate performance
    best_params = None
    best_rmse = float('inf')
    early_stop_counter = 0  # Initialize early stopping counter

    for params in all_params:
        m = Prophet(**params)
        m.fit(pd.DataFrame({'ds': df['date'][:len(X_train)], 'y': y_train}))

        # Dynamically calculate initial based on data size (≥70% of total history)
        total_days = (df['date'].max() - df['date'].min()).days
        initial_days = int(total_days * 0.7)
        initial = f'{initial_days} days'
  
        period = '50 days'

    
        # Perform cross-validation with dynamic parameters
        df_cv = cross_validation(m, initial=initial, period=period, horizon=period)
        df_p = performance_metrics(df_cv, rolling_window=1)
        rmse = df_p['rmse'].values[0]

        if rmse < best_rmse:
            best_rmse = rmse
            best_params = params
            early_stop_counter = 0  # Reset counter
        else:
            early_stop_counter += 1

        if early_stop_counter >= 5:  # Early stopping after 5 non-improving iterations
            break

    # Retrain the model with the best hyperparameters
    print(f"Best parameters: {best_params}")
    print(f"Best RMSE: {best_rmse}")
    optimized_model = Prophet(**best_params).fit(pd.DataFrame({'ds': df['date'][:len(X_train)], 'y': y_train}))

    # Create future dataframe for predictions
    predictfor = 365 * 2
    if total_days > 2000:
        predictfor = 365 * 7
        
    
    
    future = optimized_model.make_future_dataframe(periods=predictfor)  

    # Make predictions
    forecast = optimized_model.predict(future)

    # Display the forecast
    print(forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']])

    # Prepare the result DataFrame
    pred = forecast[['ds', 'yhat','yhat_lower','yhat_upper']].copy()
    pred.rename(columns={'ds': 'date', 'yhat': 'value','yhat_lower':'min','yhat_upper':'max'}, inplace=True)

    # Rebuild a clean index column
    pred.reset_index(drop=True, inplace=True)
    pred.insert(0, 'index', pred.index)

    return pred
