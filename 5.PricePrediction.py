"""
========================================================================================
Project: End-to-End Price Prediction Machine Learning Pipeline
Description: Production-ready Machine Learning system predicting prices using:
             - Scikit-Learn Pipelines & ColumnTransformers
             - Robust Missing Value Imputation (Median & Most Frequent)
             - One-Hot Categorical Encoding with unknown category handling
             - Feature Standardization (StandardScaler)
             - 80/20 Train-Test Splitting (train_test_split)
             - Linear Regression vs. Random Forest Regressor Comparison
             - Comprehensive Metric Evaluation (MAE, RMSE, R², MAPE)
             - Multi-Panel Publication-Quality Matplotlib Visualizations
             - Sample Single-Record Inference
Dataset: Realistic Multi-Feature Used Car Valuation (supports California Housing too)
Author: Expert Data Science Team
========================================================================================
"""

# =====================================================================
# STEP 0: IMPORT REQUIRED SCIENTIFIC & MACHINE LEARNING LIBRARIES
# =====================================================================

# Standard library imports for system diagnostics, file operations, and type hints
import os
import sys
from typing import Dict, List, Optional, Tuple, Union

# On Windows consoles, ensure stdout and stderr use UTF-8 encoding to avoid charmap errors
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Core scientific computation & tabular data processing libraries
import numpy as np  # High-performance multi-dimensional array operations
import pandas as pd  # Data manipulation, cleaning, and DataFrame representation

# Scikit-Learn tools for preprocessing, pipelines, model building, and validation
from sklearn.compose import ColumnTransformer  # Applies distinct transformers to numerical & categorical subsets
from sklearn.datasets import fetch_california_housing  # Standard benchmark housing dataset
from sklearn.ensemble import RandomForestRegressor  # Non-linear tree ensemble regressor
from sklearn.impute import SimpleImputer  # Fills missing values (NaNs) safely
from sklearn.linear_model import LinearRegression  # Parametric linear baseline regressor
from sklearn.metrics import (  # Standard regression evaluation metrics
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split  # Splits data into train and test sets
from sklearn.pipeline import Pipeline  # Chains data transformation and estimator steps
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # Encoders and scalers

# Visualization libraries for diagnostic plotting (headless-safe)
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend ensures headless reliability when generating plots
import matplotlib.pyplot as plt  # Core plotting module
import matplotlib.ticker as ticker  # Formatter for currency and ticks


# =====================================================================
# STEP 1: SYNTHETIC DATASET GENERATION (USED CAR MARKET VALUATION)
# =====================================================================

def generate_used_car_dataset(
    n_samples: int = 2500,
    random_state: int = 42,
    introduce_missing_values: bool = True
) -> pd.DataFrame:
    """
    Generates a realistic synthetic used-car market valuation dataset.

    Includes:
    - Numerical features (Year, Mileage_km, Engine_HP, Fuel_Efficiency_kmpl)
    - Categorical features (Brand, Fuel_Type, Transmission, Body_Style)
    - Realistic non-linear pricing logic (depreciation, brand prestige, horsepower curve)
    - Realistic missing data (NaN values) to demonstrate preprocessing pipelines.

    Parameters:
        n_samples (int): Number of car records to simulate.
        random_state (int): Seed for reproducible random numbers.
        introduce_missing_values (bool): Inject missing values if True.

    Returns:
        pd.DataFrame: Synthetic dataset with features and target 'Price_USD'.
    """
    # Seed the NumPy random number generator for 100% deterministic reproducibility
    rng = np.random.default_rng(seed=random_state)

    # 1. Simulate vehicle manufacturing years (between 2008 and 2024)
    # Younger cars will naturally carry significantly higher residual value
    years = rng.integers(low=2008, high=2025, size=n_samples)
    current_year = 2025
    age = current_year - years  # Vehicle age in years

    # 2. Simulate vehicle brands with realistic market share weights
    brands_pool = ["Toyota", "Honda", "Ford", "BMW", "Mercedes-Benz", "Audi", "Hyundai", "Chevrolet"]
    brand_weights = [0.22, 0.18, 0.15, 0.10, 0.08, 0.07, 0.12, 0.08]
    brands = rng.choice(brands_pool, size=n_samples, p=brand_weights)

    # 3. Simulate categorical features: Fuel type, Transmission, and Body Style
    fuel_types = rng.choice(["Petrol", "Diesel", "Hybrid", "Electric"], size=n_samples, p=[0.50, 0.25, 0.18, 0.07])
    transmissions = rng.choice(["Automatic", "Manual"], size=n_samples, p=[0.70, 0.30])
    body_styles = rng.choice(["Sedan", "SUV", "Hatchback", "Truck", "Coupe"], size=n_samples, p=[0.35, 0.35, 0.15, 0.10, 0.05])

    # 4. Simulate Engine Horsepower (HP) correlated loosely with body style and brand tier
    base_hp = rng.normal(loc=175, scale=45, size=n_samples).clip(min=75, max=480)
    # Luxury brands (BMW, Mercedes, Audi) receive an extra horsepower bump
    luxury_mask = np.isin(brands, ["BMW", "Mercedes-Benz", "Audi"])
    engine_hp = np.where(luxury_mask, base_hp + rng.uniform(30, 80, size=n_samples), base_hp).round()

    # 5. Simulate Mileage (km): Average 12,000 km per year of age with random variation
    mileage_km = (age * rng.normal(loc=13500, scale=3500, size=n_samples) + rng.uniform(2000, 15000, size=n_samples))
    mileage_km = np.clip(mileage_km, a_min=1000, a_max=320000).round()

    # 6. Simulate Fuel Efficiency (km per liter) - inversely related to Horsepower
    fuel_efficiency = (35.0 - (engine_hp * 0.07) + rng.normal(loc=0, scale=2.0, size=n_samples)).clip(min=8.0, max=28.0).round(1)

    # 7. Ground-truth Economic Pricing Formula with non-linear relationships:
    # Base MSRP determined by brand tier, body style, and fuel type
    brand_premiums = {
        "Toyota": 26000, "Honda": 25000, "Ford": 24000, "Hyundai": 21000,
        "Chevrolet": 22000, "BMW": 44000, "Mercedes-Benz": 48000, "Audi": 43000
    }
    body_premiums = {"Sedan": 1.0, "SUV": 1.15, "Hatchback": 0.88, "Truck": 1.25, "Coupe": 1.20}
    fuel_premiums = {"Petrol": 1.0, "Diesel": 1.04, "Hybrid": 1.12, "Electric": 1.22}

    base_prices = np.array([brand_premiums[b] * body_premiums[bs] * fuel_premiums[ft]
                            for b, bs, ft in zip(brands, body_styles, fuel_types)])

    # Exponential depreciation curve: ~9.5% value loss per year of age
    depreciation_factor = np.exp(-0.095 * age)

    # Mileage penalty: Value decay as kilometers accumulate
    mileage_penalty = np.exp(-0.0000028 * mileage_km)

    # Horsepower premium: Additional value added by potent performance engines
    hp_bonus = (engine_hp - 100) * 85.0

    # Gaussian market noise simulating vehicle condition, local supply/demand, and haggling
    market_noise = rng.normal(loc=0, scale=1200, size=n_samples)

    # Calculate final price and enforce a market floor of $2,500
    prices = (base_prices * depreciation_factor * mileage_penalty + hp_bonus + market_noise)
    prices = np.clip(prices, a_min=2500.0, a_max=125000.0).round(2)

    # Assemble raw tabular data into a structured Pandas DataFrame
    df = pd.DataFrame({
        "Brand": brands,
        "Year": years,
        "Mileage_km": mileage_km,
        "Engine_HP": engine_hp,
        "Fuel_Efficiency_kmpl": fuel_efficiency,
        "Transmission": transmissions,
        "Fuel_Type": fuel_types,
        "Body_Style": body_styles,
        "Price_USD": prices,
    })

    # 8. Inject realistic Missing Values (NaN) if requested (e.g. ~4% in specific fields)
    if introduce_missing_values:
        # Simulate missing values in continuous feature 'Mileage_km' (unreported odometer)
        nan_mileage_idx = rng.choice(n_samples, size=int(n_samples * 0.04), replace=False)
        df.loc[nan_mileage_idx, "Mileage_km"] = np.nan

        # Simulate missing values in continuous feature 'Engine_HP'
        nan_hp_idx = rng.choice(n_samples, size=int(n_samples * 0.03), replace=False)
        df.loc[nan_hp_idx, "Engine_HP"] = np.nan

        # Simulate missing values in categorical feature 'Fuel_Type'
        nan_fuel_idx = rng.choice(n_samples, size=int(n_samples * 0.025), replace=False)
        df.loc[nan_fuel_idx, "Fuel_Type"] = np.nan

    return df


# =====================================================================
# STEP 2: PREPROCESSING PIPELINE BUILDER
# =====================================================================

def build_preprocessor(
    numerical_features: List[str],
    categorical_features: List[str]
) -> ColumnTransformer:
    """
    Constructs an industrial-grade Scikit-Learn ColumnTransformer pipeline.

    Why this architecture?
    - Prevents data leakage by encapsulating transformation logic within estimator pipelines.
    - Imputes missing numerical values with the median (robust against outliers).
    - Standardizes numerical variables to zero mean and unit variance (essential for Linear Models).
    - Imputes missing categorical values with the mode ('most_frequent').
    - One-hot encodes nominal categoricals, safely ignoring unknown future categories during inference.

    Parameters:
        numerical_features (List[str]): Column names of numerical continuous features.
        categorical_features (List[str]): Column names of categorical string features.

    Returns:
        ColumnTransformer: Preprocessor ready to be chained inside a Model Pipeline.
    """
    # Pipeline for Numerical Features:
    # 1. SimpleImputer: Fills missing entries using the median of the column
    # 2. StandardScaler: Z-score standardization (x - mean) / std_dev
    numerical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    # Pipeline for Categorical Features:
    # 1. SimpleImputer: Fills missing text values with the most frequent category
    # 2. OneHotEncoder: Converts categories into binary one-hot vectors
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    # ColumnTransformer unites distinct transformers based on targeted column subsets
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numerical_pipeline, numerical_features),
            ("cat", categorical_pipeline, categorical_features),
        ],
        remainder="drop",  # Drops any extraneous columns not specified in feature lists
        verbose_feature_names_out=False,
    )

    return preprocessor


# =====================================================================
# STEP 3: MODEL FACTORIES (LINEAR REGRESSION & RANDOM FOREST)
# =====================================================================

def create_full_pipeline(
    preprocessor: ColumnTransformer,
    model_type: str = "linear_regression"
) -> Pipeline:
    """
    Combines the ColumnTransformer preprocessor and an Estimator into a complete Pipeline.

    Parameters:
        preprocessor (ColumnTransformer): Preprocessing pipeline.
        model_type (str): Either 'linear_regression' or 'random_forest'.

    Returns:
        Pipeline: Combined preprocessing + model estimator pipeline.
    """
    if model_type == "linear_regression":
        # Linear Regression: Parametric algorithm fitting an optimal hyperplane
        estimator = LinearRegression()
    elif model_type == "random_forest":
        # Random Forest Regressor: Non-parametric ensemble of decision trees
        # - n_estimators=120: 120 individual decision trees for reduced variance
        # - max_depth=16: Prevents excessive tree depth to safeguard against overfitting
        # - min_samples_split=4: Demands at least 4 samples to perform an internal node split
        # - random_state=42: Guaranteed deterministic reproducibility
        # - n_jobs=-1: Utilizes all CPU cores for parallelized tree fitting
        estimator = RandomForestRegressor(
            n_estimators=120,
            max_depth=16,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Unknown model_type: '{model_type}'. Choose 'linear_regression' or 'random_forest'.")

    # Return end-to-end composite pipeline
    return Pipeline(steps=[("preprocessor", preprocessor), ("regressor", estimator)])


# =====================================================================
# STEP 4: MODEL EVALUATION & COMPARISON SUITE
# =====================================================================

def evaluate_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str
) -> Dict[str, Union[str, float]]:
    """
    Calculates essential statistical regression evaluation metrics:
    - MAE: Mean Absolute Error (average magnitude of errors in original currency units)
    - RMSE: Root Mean Squared Error (penalizes large outlier mistakes more heavily)
    - R²: Coefficient of Determination (percentage of variance explained by the model)
    - MAPE: Mean Absolute Percentage Error (relative percentage error)

    Parameters:
        y_true (np.ndarray): Actual true target values.
        y_pred (np.ndarray): Model predicted target values.
        model_name (str): Label for the model being evaluated.

    Returns:
        Dict: Dictionary containing computed evaluation metrics.
    """
    # 1. Mean Absolute Error: sum(|y_true - y_pred|) / n
    mae = mean_absolute_error(y_true, y_pred)

    # 2. Root Mean Squared Error: sqrt(sum((y_true - y_pred)^2) / n)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

    # 3. R-squared Score: 1 - (residual sum of squares / total sum of squares)
    r2 = r2_score(y_true, y_pred)

    # 4. Mean Absolute Percentage Error: average(|(y_true - y_pred) / y_true|) * 100
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100.0

    return {
        "Model": model_name,
        "MAE ($)": round(float(mae), 2),
        "RMSE ($)": round(float(rmse), 2),
        "R² Score": round(float(r2), 4),
        "MAPE (%)": round(float(mape), 2),
    }


# =====================================================================
# STEP 5: VISUALIZATION SUITE (PUBLICATION-QUALITY MATPLOTLIB)
# =====================================================================

def plot_model_diagnostics(
    y_test: np.ndarray,
    y_pred_lr: np.ndarray,
    y_pred_rf: np.ndarray,
    rf_pipeline: Pipeline,
    categorical_features: List[str],
    numerical_features: List[str],
    save_path: Optional[str] = "price_prediction_results.png"
) -> None:
    """
    Renders an elegant 4-panel diagnostic plot comparing model behavior:
    1. Actual vs. Predicted Prices: Linear Regression
    2. Actual vs. Predicted Prices: Random Forest Regressor
    3. Residual Error Distributions: Side-by-Side Histogram
    4. Feature Importances: Top 12 most influential features from Random Forest

    Parameters:
        y_test: Ground truth test target values.
        y_pred_lr: Predictions from Linear Regression.
        y_pred_rf: Predictions from Random Forest.
        rf_pipeline: Trained Random Forest pipeline (for extracting feature names & importances).
        categorical_features: List of categorical feature names.
        numerical_features: List of numerical feature names.
        save_path: File path to save generated graphic image.
    """
    # Set clean aesthetic style and typography
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=120)
    fig.patch.set_facecolor("#f8f9fa")

    # Define color palette
    c_lr = "#1f77b4"  # Professional blue
    c_rf = "#2ca02c"  # High-confidence forest green
    c_ideal = "#d62728"  # Precision crimson line

    min_price = min(float(y_test.min()), float(y_pred_lr.min()), float(y_pred_rf.min())) * 0.92
    max_price = max(float(y_test.max()), float(y_pred_lr.max()), float(y_pred_rf.max())) * 1.05

    # -------------------------------------------------------------
    # Panel 1: Actual vs. Predicted (Linear Regression)
    # -------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.set_facecolor("#ffffff")
    ax1.scatter(y_test, y_pred_lr, alpha=0.35, color=c_lr, edgecolors="none", s=28, label="Test Samples")
    # Plot ideal 1:1 perfect prediction diagonal
    ax1.plot([min_price, max_price], [min_price, max_price], color=c_ideal, linestyle="--", linewidth=2.0, label="Ideal Fit (y = x)")
    r2_lr = r2_score(y_test, y_pred_lr)
    mae_lr = mean_absolute_error(y_test, y_pred_lr)
    ax1.set_title(f"Linear Regression: Actual vs. Predicted\n(R²: {r2_lr:.3f} | MAE: ${mae_lr:,.0f})", fontsize=12, fontweight="bold", pad=10)
    ax1.set_xlabel("Actual Price ($ USD)", fontsize=11, fontweight="medium")
    ax1.set_ylabel("Predicted Price ($ USD)", fontsize=11, fontweight="medium")
    ax1.xaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax1.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax1.legend(loc="upper left", frameon=True)
    ax1.set_xlim(min_price, max_price)
    ax1.set_ylim(min_price, max_price)

    # -------------------------------------------------------------
    # Panel 2: Actual vs. Predicted (Random Forest Regressor)
    # -------------------------------------------------------------
    ax2 = axes[0, 1]
    ax2.set_facecolor("#ffffff")
    ax2.scatter(y_test, y_pred_rf, alpha=0.35, color=c_rf, edgecolors="none", s=28, label="Test Samples")
    ax2.plot([min_price, max_price], [min_price, max_price], color=c_ideal, linestyle="--", linewidth=2.0, label="Ideal Fit (y = x)")
    r2_rf = r2_score(y_test, y_pred_rf)
    mae_rf = mean_absolute_error(y_test, y_pred_rf)
    ax2.set_title(f"Random Forest: Actual vs. Predicted\n(R²: {r2_rf:.3f} | MAE: ${mae_rf:,.0f})", fontsize=12, fontweight="bold", pad=10)
    ax2.set_xlabel("Actual Price ($ USD)", fontsize=11, fontweight="medium")
    ax2.set_ylabel("Predicted Price ($ USD)", fontsize=11, fontweight="medium")
    ax2.xaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax2.yaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax2.legend(loc="upper left", frameon=True)
    ax2.set_xlim(min_price, max_price)
    ax2.set_ylim(min_price, max_price)

    # -------------------------------------------------------------
    # Panel 3: Residual Error Distributions (Error = Actual - Predicted)
    # -------------------------------------------------------------
    ax3 = axes[1, 0]
    ax3.set_facecolor("#ffffff")
    residuals_lr = y_test - y_pred_lr
    residuals_rf = y_test - y_pred_rf

    # Histogram of residuals
    bins = np.linspace(-15000, 15000, 45)
    ax3.hist(residuals_lr, bins=bins, alpha=0.55, color=c_lr, label=f"Linear Regression (Std: ${np.std(residuals_lr):,.0f})")
    ax3.hist(residuals_rf, bins=bins, alpha=0.55, color=c_rf, label=f"Random Forest (Std: ${np.std(residuals_rf):,.0f})")
    ax3.axvline(0, color="black", linestyle="--", linewidth=1.5, label="Zero Error Mark")
    ax3.set_title("Residual Error Distribution (Actual - Predicted)", fontsize=12, fontweight="bold", pad=10)
    ax3.set_xlabel("Prediction Error ($ USD)", fontsize=11, fontweight="medium")
    ax3.set_ylabel("Sample Frequency", fontsize=11, fontweight="medium")
    ax3.xaxis.set_major_formatter(ticker.StrMethodFormatter("${x:,.0f}"))
    ax3.legend(loc="upper right", frameon=True)

    # -------------------------------------------------------------
    # Panel 4: Random Forest Feature Importances
    # -------------------------------------------------------------
    ax4 = axes[1, 1]
    ax4.set_facecolor("#ffffff")

    try:
        # Extract fitted preprocessor and transformed feature column names
        fitted_preprocessor = rf_pipeline.named_steps["preprocessor"]
        feature_names = fitted_preprocessor.get_feature_names_out()

        # Extract MDI (Mean Decrease in Impurity) feature importances from Random Forest
        rf_model = rf_pipeline.named_steps["regressor"]
        importances = rf_model.feature_importances_

        # Sort features by highest importance
        sorted_indices = np.argsort(importances)[::-1][:12]  # Top 12 features
        top_features = [feature_names[i] for i in sorted_indices][::-1]
        top_importances = importances[sorted_indices][::-1]

        # Horizontal bar chart
        bars = ax4.barh(range(len(top_features)), top_importances, color="#4a69bd", edgecolor="#1e3799", height=0.65)
        ax4.set_yticks(range(len(top_features)))
        ax4.set_yticklabels(top_features, fontsize=10)
        ax4.set_title("Top 12 Most Influential Predictive Features (Random Forest)", fontsize=12, fontweight="bold", pad=10)
        ax4.set_xlabel("Relative Importance Weight", fontsize=11, fontweight="medium")
        ax4.set_xlim(0, max(top_importances) * 1.15)

        # Annotate bar percentages
        for bar in bars:
            width = bar.get_width()
            ax4.text(width + 0.005, bar.get_y() + bar.get_height() / 2, f"{width * 100:.1f}%",
                     va="center", ha="left", fontsize=9, color="#2c3e50")
    except Exception as exc:
        ax4.text(0.5, 0.5, f"Feature Importance unavailable:\n{exc}", ha="center", va="center")

    plt.suptitle("End-to-End Price Prediction Model Evaluation & Diagnostic Report", fontsize=16, fontweight="bold", y=0.995)
    plt.tight_layout(rect=[0, 0.03, 1, 0.97])

    # Save visualization to disk
    if save_path:
        plt.savefig(save_path, bbox_inches="tight", dpi=150)
        print(f"\n[Visualization] High-resolution diagnostic plot saved successfully to: '{save_path}'")
    plt.close(fig)


# =====================================================================
# STEP 6: REAL-WORLD INFERENCE DEMONSTRATOR
# =====================================================================

def predict_single_car_price(
    sample_car: Dict[str, Union[str, float, int, None]],
    lr_pipeline: Pipeline,
    rf_pipeline: Pipeline
) -> None:
    """
    Demonstrates model deployment inference on a single, unseen vehicle specification.
    Shows how the pipeline seamlessly handles raw dictionary input with missing values.

    Parameters:
        sample_car: Dictionary representing features of a test vehicle.
        lr_pipeline: Trained Linear Regression Pipeline.
        rf_pipeline: Trained Random Forest Pipeline.
    """
    # Convert input dictionary to single-row DataFrame
    input_df = pd.DataFrame([sample_car])

    # Predict using both trained pipelines (preprocessing handled completely internally!)
    predicted_price_lr = lr_pipeline.predict(input_df)[0]
    predicted_price_rf = rf_pipeline.predict(input_df)[0]

    print("\n" + "=" * 70)
    print(">> REAL-TIME SINGLE CAR PRICE INFERENCE TEST")
    print("=" * 70)
    print("Input Vehicle Specifications:")
    for feature_name, value in sample_car.items():
        val_str = "MISSING (NaN - To Be Imputed)" if value is None or pd.isna(value) else str(value)
        print(f"  * {feature_name:<22}: {val_str}")

    print("-" * 70)
    print(f"Linear Regression Estimated Price : ${predicted_price_lr:,.2f}")
    print(f"Random Forest Estimated Price     : ${predicted_price_rf:,.2f}")
    print("=" * 70)


# =====================================================================
# STEP 7: MASTER EXECUTION ORCHESTRATOR
# =====================================================================

def run_price_prediction_pipeline(dataset_choice: str = "cars") -> Tuple[Pipeline, Pipeline, pd.DataFrame]:
    """
    Orchestrates the complete end-to-end Machine Learning Workflow:
    1. Dataset Loading / Generation
    2. Missing Value & Outlier Inspection
    3. Pipeline Construction (Imputation, One-Hot Encoding, Scaling)
    4. 80/20 Train-Test Splitting
    5. Model Training (Linear Regression & Random Forest)
    6. Multi-Metric Evaluation & Comparison Table
    7. Matplotlib Visualizations
    8. Interactive Inference Demonstration

    Parameters:
        dataset_choice (str): 'cars' for Used Car Valuation, 'housing' for California Housing.

    Returns:
        Tuple of (fitted_lr_pipeline, fitted_rf_pipeline, test_dataframe)
    """
    print("\n" + "=" * 78)
    print(">> STARTING MACHINE LEARNING PRICE PREDICTION PIPELINE")
    print("=" * 78)

    # -------------------------------------------------------------
    # 1. Dataset Acquisition
    # -------------------------------------------------------------
    if dataset_choice == "cars":
        print("\n[Step 1/6] Generating Realistic Used Car Market Dataset (2,500 samples)...")
        df = generate_used_car_dataset(n_samples=2500, random_state=42, introduce_missing_values=True)
        target_column = "Price_USD"

        # Explicitly declare numerical continuous and nominal categorical columns
        numerical_features = ["Year", "Mileage_km", "Engine_HP", "Fuel_Efficiency_kmpl"]
        categorical_features = ["Brand", "Fuel_Type", "Transmission", "Body_Style"]

    elif dataset_choice == "housing":
        print("\n[Step 1/6] Fetching Standard California Housing Dataset from Scikit-Learn...")
        housing = fetch_california_housing(as_frame=True)
        df = housing.frame.copy()
        # Scale target from tens-of-thousands to actual dollar amount ($100,000s)
        df["MedHouseVal"] = df["MedHouseVal"] * 100000.0
        target_column = "MedHouseVal"

        # California Housing is fully numeric
        numerical_features = [col for col in df.columns if col != target_column]
        categorical_features = []
    else:
        raise ValueError("Invalid dataset_choice. Choose either 'cars' or 'housing'.")

    # Display dataset schema and exploratory summary
    print(f"\nDataset Loaded: {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"Target Variable: '{target_column}'")
    print("\n--- First 5 Records ---")
    print(df.head())

    # Check for missing values to prove preprocessing necessity
    missing_summary = df.isnull().sum()
    print("\n--- Missing Values Detected (Before Preprocessing) ---")
    print(missing_summary[missing_summary > 0] if missing_summary.sum() > 0 else "Zero missing values.")

    # -------------------------------------------------------------
    # 2. Train-Test Splitting (Strict 80% Train, 20% Test)
    # -------------------------------------------------------------
    print("\n[Step 2/6] Splitting Dataset into Train and Test Subsets (80/20 Split)...")
    # Separate feature matrix X and target vector y
    X = df.drop(columns=[target_column])
    y = df[target_column].values

    # Perform split with random_state=42 to guarantee reproducibility
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.20,      # 20% reserved strictly for unbiased out-of-sample evaluation
        random_state=42,     # Reproducible partition
        shuffle=True         # Shuffles data before splitting
    )
    print(f"Training Set : {X_train.shape[0]} instances (80%)")
    print(f"Testing Set  : {X_test.shape[0]} instances (20%)")

    # -------------------------------------------------------------
    # 3. Pipeline Construction
    # -------------------------------------------------------------
    print("\n[Step 3/6] Building Scikit-Learn Preprocessing & Estimator Pipelines...")
    preprocessor = build_preprocessor(
        numerical_features=numerical_features,
        categorical_features=categorical_features
    )

    # Instantiate end-to-end pipelines combining preprocessor and regression model
    lr_pipeline = create_full_pipeline(preprocessor, model_type="linear_regression")
    rf_pipeline = create_full_pipeline(preprocessor, model_type="random_forest")

    # -------------------------------------------------------------
    # 4. Model Training
    # -------------------------------------------------------------
    print("\n[Step 4/6] Training Machine Learning Models on Training Partition...")

    # Train Linear Regression model
    print("  * Fitting Model 1: Ordinary Least Squares Linear Regression...")
    lr_pipeline.fit(X_train, y_train)
    print("    [+] Linear Regression fit completed.")

    # Train Random Forest Regressor
    print("  * Fitting Model 2: Random Forest Regressor (120 Trees, Parallel)...")
    rf_pipeline.fit(X_train, y_train)
    print("    [+] Random Forest Regressor fit completed.")

    # -------------------------------------------------------------
    # 5. Out-of-Sample Evaluation & Comparison
    # -------------------------------------------------------------
    print("\n[Step 5/6] Evaluating Models on Unseen Test Partition (20%)...")
    # Generate test predictions
    y_pred_lr = lr_pipeline.predict(X_test)
    y_pred_rf = rf_pipeline.predict(X_test)

    # Compute regression performance metrics
    metrics_lr = evaluate_predictions(y_test, y_pred_lr, model_name="Linear Regression")
    metrics_rf = evaluate_predictions(y_test, y_pred_rf, model_name="Random Forest Regressor")

    # Display comparison table
    comparison_df = pd.DataFrame([metrics_lr, metrics_rf])
    print("\n" + "=" * 78)
    print("FINAL MODEL PERFORMANCE COMPARISON TABLE")
    print("=" * 78)
    print(comparison_df.to_string(index=False))
    print("=" * 78)

    # Highlight winning model
    if metrics_rf["R² Score"] > metrics_lr["R² Score"]:
        print(f"\n[Analysis Insight] Random Forest Regressor outperformed Linear Regression")
        print(f"   with a higher R² of {metrics_rf['R² Score']} (vs {metrics_lr['R² Score']})")
        print(f"   and a lower MAE of ${metrics_rf['MAE ($)']:,.2f} (vs ${metrics_lr['MAE ($)']:,.2f}).")
        print("   This highlights Random Forest's ability to model non-linear price depreciation,")
        print("   brand interactions, and mileage decay curves without requiring manual polynomial features.")
    else:
        print(f"\n[Analysis Insight] Linear Regression performed competitively with R² = {metrics_lr['R² Score']}.")

    # -------------------------------------------------------------
    # 6. Matplotlib Diagnostics & Visualization
    # -------------------------------------------------------------
    print("\n[Step 6/6] Generating High-Fidelity Diagnostic Visualizations...")
    plot_file = "price_prediction_results.png"
    plot_model_diagnostics(
        y_test=y_test,
        y_pred_lr=y_pred_lr,
        y_pred_rf=y_pred_rf,
        rf_pipeline=rf_pipeline,
        categorical_features=categorical_features,
        numerical_features=numerical_features,
        save_path=plot_file,
    )

    # -------------------------------------------------------------
    # 7. Sample Single Inference Demonstration
    # -------------------------------------------------------------
    if dataset_choice == "cars":
        sample_used_car = {
            "Brand": "BMW",
            "Year": 2021,
            "Mileage_km": 42000.0,
            "Engine_HP": 255.0,
            "Fuel_Efficiency_kmpl": None,  # Intentionally missing to test automatic imputation!
            "Transmission": "Automatic",
            "Fuel_Type": "Petrol",
            "Body_Style": "Sedan",
        }
        predict_single_car_price(sample_used_car, lr_pipeline, rf_pipeline)

    print("\n[+] Machine Learning Price Prediction Pipeline completed successfully!\n")
    return lr_pipeline, rf_pipeline, df


def interactive_car_appraisal(lr_pipeline: Pipeline, rf_pipeline: Pipeline) -> None:
    """
    Allows the user to interactively enter custom vehicle specifications
    from the terminal to get live price predictions from both models.
    """
    print("\n" + "=" * 70)
    print(">> INTERACTIVE CUSTOM CAR PRICE ESTIMATOR")
    print("=" * 70)
    print("Enter vehicle specifications below (press [Enter] to use defaults):")

    brands_pool = ["Toyota", "Honda", "Ford", "BMW", "Mercedes-Benz", "Audi", "Hyundai", "Chevrolet"]
    print(f"\nAvailable Brands: {', '.join(brands_pool)}")
    brand_in = input("Select Brand [default: Toyota]: ").strip()
    brand = brand_in if brand_in in brands_pool else ("Toyota" if not brand_in else brand_in)

    year_in = input("Manufacturing Year (e.g. 2021) [default: 2021]: ").strip()
    try:
        year = int(year_in) if year_in else 2021
    except ValueError:
        year = 2021

    mileage_in = input("Odometer Mileage in km (e.g. 35000) [default: 35000]: ").strip()
    try:
        mileage = float(mileage_in) if mileage_in else 35000.0
    except ValueError:
        mileage = 35000.0

    hp_in = input("Engine Horsepower (HP, e.g. 190) [default: 190]: ").strip()
    try:
        hp = float(hp_in) if hp_in else 190.0
    except ValueError:
        hp = 190.0

    fe_in = input("Fuel Efficiency km/l (press Enter to leave empty for auto-imputation): ").strip()
    fe = float(fe_in) if fe_in else None

    trans_in = input("Transmission (Automatic/Manual) [default: Automatic]: ").strip().capitalize()
    transmission = trans_in if trans_in in ["Automatic", "Manual"] else "Automatic"

    fuel_in = input("Fuel Type (Petrol/Diesel/Hybrid/Electric) [default: Petrol]: ").strip().capitalize()
    fuel = fuel_in if fuel_in in ["Petrol", "Diesel", "Hybrid", "Electric"] else "Petrol"

    body_in = input("Body Style (Sedan/SUV/Hatchback/Truck/Coupe) [default: Sedan]: ").strip().capitalize()
    body = body_in if body_in in ["Sedan", "SUV", "Hatchback", "Truck", "Coupe"] else "Sedan"

    custom_car = {
        "Brand": brand,
        "Year": year,
        "Mileage_km": mileage,
        "Engine_HP": hp,
        "Fuel_Efficiency_kmpl": fe,
        "Transmission": transmission,
        "Fuel_Type": fuel,
        "Body_Style": body,
    }

    predict_single_car_price(custom_car, lr_pipeline, rf_pipeline)


# =====================================================================
# SCRIPT ENTRYPOINT
# =====================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="End-to-End Price Prediction Pipeline")
    parser.add_argument(
        "--dataset",
        choices=["cars", "housing"],
        default="cars",
        help="Dataset choice: 'cars' for used car valuation, 'housing' for California housing (default: cars)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively enter vehicle specifications to estimate custom price",
    )
    args, unknown = parser.parse_known_args()

    # 1. Run the core pipeline (100% automated, zero input required!)
    lr_model, rf_model, dataset = run_price_prediction_pipeline(dataset_choice=args.dataset)

    # 2. Optional interactive input: only prompts if requested or when run interactively in a TTY
    if args.interactive:
        interactive_car_appraisal(lr_model, rf_model)
    elif sys.stdin.isatty():
        try:
            choice = input("\nWould you like to enter custom car specifications for price prediction? (y/N): ").strip().lower()
            if choice == "y":
                interactive_car_appraisal(lr_model, rf_model)
        except (EOFError, KeyboardInterrupt):
            pass
