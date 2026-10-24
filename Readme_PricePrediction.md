<div align="center">

# 🧊 3D Industrial Machine Learning Price Prediction Engine
### *Dual-Model Architecture • Leakage-Free Scikit-Learn Pipelines • 3D Hyperplane Geometry*

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=for-the-badge&logo=python)
![Scikit-Learn](https://img.shields.io/badge/scikit--learn-v1.4%2B-F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)
![NumPy](https://img.shields.io/badge/numpy-v1.24%2B-013243.svg?style=for-the-badge&logo=numpy&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-v2.0%2B-150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Matplotlib](https://img.shields.io/badge/matplotlib-v3.8%2B-11557c.svg?style=for-the-badge)
![Model Performance](https://img.shields.io/badge/R%C2%B2%20Accuracy-94.97%25-brightgreen.svg?style=for-the-badge)
![Architecture](https://img.shields.io/badge/architecture-SOLID%20%2B%20Pipelines-purple.svg?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-orange.svg?style=for-the-badge)

<p align="center">
  <b>A state-of-the-art, enterprise-grade Price Prediction system demonstrating zero data leakage, automatic missing-value imputation, one-hot categorical encoding, feature scaling, 3D regression hyperplane vs. non-linear tree ensembling, multi-metric evaluation, diagnostic visualizations, and real-time interactive inference.</b>
</p>

</div>

---

## 🧊 3D Machine Learning Architecture & Isometric Pipeline

```
                               +-------------------------------------------------------------+
                              /                                                             /|
                             /          [📦 LAYER 1: DATA INGESTION & AUDIT CUBE]          / |
                            /  2,500 Multi-Feature Vehicle Records • Missing Data Injection/  |
                           +-------------------------------------------------------------+   +
                           |                                                             |  /|
                           |  • Continuous: Year, Mileage_km, Engine_HP, Fuel_Efficiency | / |
                           |  • Categorical: Brand, Fuel_Type, Transmission, Body_Style  |/  |
                           +-------------------------------------------------------------+   +
                                                          |
                                                          v
                               +-------------------------------------------------------------+
                              /                                                             /|
                             /        [🛡️ LAYER 2: LEAKAGE-FREE PREPROCESSING CUBE]        / |
                            /    ColumnTransformer Fitting Exclusively on 80% Train Set     /  |
                           +-------------------------------------------------------------+   +
                           |                                                             |  /|
                           |  [🔢 Numerical Branch]        [🔤 Categorical Branch]      | / |
                           |  SimpleImputer (Median)       SimpleImputer (Most Frequent) |/  |
                           |  StandardScaler (Z-Score)     OneHotEncoder (Ignore Unknown)|   +
                           +-------------------------------------------------------------+  /
                                                          |
                                                          v
                               +-------------------------------------------------------------+
                              /                                                             /|
                             /          [⚙️ LAYER 3: DUAL MODEL BENCHMARK ENGINE]          / |
                            /         Parametric Hyperplane vs. Non-Parametric Ensemble     /  |
                           +-------------------------------------------------------------+   +
                           |                                                             |  /|
                           |  [📈 Linear Regression]       [🌲 Random Forest Regressor]  | / |
                           |  OLS Hyperplane:              120 Decision Trees:           |/  |
                           |  y = β₀ + Σ(βⱼ · xⱼ)          y = (1/B) Σ T_b(x)            |   +
                           +-------------------------------------------------------------+  /
                                                          |
                                                          v
                               +-------------------------------------------------------------+
                              /                                                             /|
                             /       [📊 LAYER 4: 3D EVALUATION & DIAGNOSTIC PROJECTION]     / |
                            /   Multi-Metric Scoring ($R^2$, MAE, RMSE) & 4-Panel Plotting  /  |
                           +-------------------------------------------------------------+   +
                           |                                                             |  /
                           |  • R² Score: 94.97% (RF) vs 89.56% (LR)                     | / 
                           |  • Mean Absolute Error: $1,662.88 (RF) vs $2,529.29 (LR)    |/  
                           |  • Publication-Quality Matplotlib Visual Diagnostic Report  |   
                           +-------------------------------------------------------------+   
```

---

## 📐 3D Geometric Regression Space & Mathematical Foundations

In predictive pricing, we map vehicles into an $n$-dimensional Euclidean feature space $\mathbb{R}^n$. Visualizing a reduced **3D subspace** $(\text{Horsepower}, \text{Age}, \text{Price})$ demonstrates the core geometric divergence between Linear Regression and Random Forest:

```
          Price ($ USD)  ▲
                         │
                         │               ▲ High-Value Segment (Low Age, High HP)
                         │              ╱ 
                         │             ╱       /───────────────────/ [Linear Regression
                         │            ╱       /                   /   Hyperplane Plane]
                         │           ╱       /                   /
                         │          ╱       /───────────────────/
                         │         ╱          █ █ █ █ █
                         │        ╱         █ █ █ █ █ █ █  [Random Forest
                         │       ╱        █ █ █ █ █ █ █ █   Orthogonal Decision
                         │      ╱           █ █ █ █ █       Voxels / Partitions]
                         │     ╱
                         │    ╱    ● Standard Commuter Cluster
                         │   ╱
                         │  ╱
                         │ ╱
                         └────────────────────────────────────────► Engine Horsepower (HP)
                        ╱
                       ╱
                      ╱
                     ▼ Vehicle Age (Years)
```

### 1. Parametric Linear Regression (3D Hyperplane)
Fits a smooth global flat plane through the feature dimensions by solving the **Normal Equation**:
$$\boldsymbol{\beta} = (\mathbf{X}^T \mathbf{X})^{-1} \mathbf{X}^T \mathbf{y}$$
$$\hat{y}(\mathbf{x}) = \beta_0 + \beta_1 \cdot \text{HP} + \beta_2 \cdot \text{Mileage} + \beta_3 \cdot \text{Age} + \dots + \sum_{k} \beta_k \cdot \text{Brand}_k$$

* **Geometric Behavior**: Assumes constant marginal rates of depreciation and linear horsepower premiums across all price tiers.

### 2. Random Forest Regressor (3D Orthogonal Voxel Ensembles)
Partitions the continuous 3D domain into localized, axis-aligned hyper-rectangles (decision voxels) through recursive variance reduction:
$$\Delta I = \text{Var}(S) - \left( \frac{|S_L|}{|S|} \text{Var}(S_L) + \frac{|S_R|}{|S|} \text{Var}(S_R) \right)$$
$$\hat{y}_{\text{RF}}(\mathbf{x}) = \frac{1}{B} \sum_{b=1}^{B} T_b(\mathbf{x})$$

* **Geometric Behavior**: Naturally models non-linear step-downs (e.g. sharp luxury depreciation in years 1–3, diminishing returns on high mileage, and exponential horsepower premiums).

---

## 🌟 Visual Pipeline Lifecycle (Mermaid Flowchart)

```mermaid
flowchart TD
    classDef source fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
    classDef preprocess fill:#0f172a,stroke:#8b5cf6,stroke-width:2px,color:#f8fafc;
    classDef model fill:#1e1b4b,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef eval fill:#311042,stroke:#ec4899,stroke-width:2px,color:#f8fafc;

    A[📊 Raw Tabular Data<br/>2,500 Records • Synthetic Used Car Market]:::source --> B{Data Quality Check}:::source
    
    B -->|Detect Missing| C1[Mileage: ~4% NaN]:::source
    B -->|Detect Missing| C2[Engine HP: ~3% NaN]:::source
    B -->|Detect Missing| C3[Fuel Type: ~2.5% NaN]:::source

    C1 & C2 & C3 --> D[✂️ 80/20 Deterministic Train/Test Split<br/>Seed = 42]:::source
    
    D -->|80% Partition| E[🏋️ Train Set: 2,000 Samples]:::preprocess
    D -->|20% Partition| F[🧪 Test Holdout: 500 Samples]:::preprocess

    subgraph "🛡️ Leakage-Free Scikit-Learn Preprocessing Pipeline"
        E --> G[ColumnTransformer]:::preprocess
        
        subgraph "Numerical Sub-Pipeline"
            G --> H1[SimpleImputer<br/>strategy='median']:::preprocess
            H1 --> H2[StandardScaler<br/>z = x - μ / σ]:::preprocess
        end
        
        subgraph "Categorical Sub-Pipeline"
            G --> I1[SimpleImputer<br/>strategy='most_frequent']:::preprocess
            I1 --> I2[OneHotEncoder<br/>handle_unknown='ignore']:::preprocess
        end
    end

    H2 & I2 --> J[Combined Feature Vector Space]:::preprocess

    subgraph "⚙️ Model Training & Benchmarking"
        J --> K1[📈 Model 1: Linear Regression<br/>Ordinary Least Squares]:::model
        J --> K2[🌲 Model 2: Random Forest Regressor<br/>120 Parallel Trees • max_depth=16]:::model
    end

    F --> L[Holdout Inference Engine]:::eval
    K1 --> L
    K2 --> L

    L --> M1[🏆 Comparative Statistical Metrics<br/>MAE • RMSE • R² • MAPE]:::eval
    L --> M2[📈 4-Panel Diagnostic Matplotlib Figure<br/>Actual vs Predicted • Residuals • Importances]:::eval
    L --> M3[🚘 Real-Time Single-Record Inference Demo<br/>Handles Missing Data On-The-Fly]:::eval
```

---

## 🏆 Model Performance Benchmark Results

Evaluated on the exact 20% holdout test partition (500 unseen records):

| Evaluated Metric | Linear Regression | Random Forest Regressor | Performance Delta / Winning Margin | Visual Comparison |
| :--- | :---: | :---: | :---: | :--- |
| **Coefficient of Determination ($R^2$)** | `0.8956` | **`0.9497`** | **+5.41% More Variance Captured** | `███████████████████░` (94.97%) |
| **Mean Absolute Error (MAE)** | `$2,529.29` | **`$1,662.88`** | **-$866.41 (34.2% Less Error)** | `██████████████░░░░░░` (-34.2%) |
| **Root Mean Squared Error (RMSE)** | `$3,364.71` | **`$2,334.84`** | **-$1,029.87 (30.6% Outlier Penalty Drop)** | `████████████░░░░░░░░` (-30.6%) |
| **Mean Absolute Percentage Error (MAPE)** | `18.03%` | **`10.22%`** | **-7.81% Average Relative Deviation** | `██████████░░░░░░░░░░` (10.22%) |

> **Data Science Insight**: The Random Forest Regressor establishes definitive dominance because used car values exhibit steep non-linear depreciation in early years followed by an asymptote, which a flat hyperplane systematically overestimates for old luxury cars and underestimates for pristine newer vehicles.

---

## 📊 Visual Diagnostic Suite Breakdown

The pipeline automatically outputs [price_prediction_results.png](file:///c:/Users/LOKI/Practice/Python/50%20Mini%20Projects/price_prediction_results.png) at high DPI resolution:

```
+---------------------------------------+---------------------------------------+
|  PANEL 1: LINEAR REGRESSION           |  PANEL 2: RANDOM FOREST REGRESSOR     |
|  Actual vs. Predicted ($ USD)         |  Actual vs. Predicted ($ USD)         |
|  Scatter around 45° ideal dashed line |  Tightly clustered along 45° line     |
|  R² = 0.896 | MAE = $2,529            |  R² = 0.950 | MAE = $1,663            |
+---------------------------------------+---------------------------------------+
|  PANEL 3: RESIDUAL ERROR HISTOGRAM    |  PANEL 4: TOP 12 FEATURE IMPORTANCES  |
|  Actual - Predicted ($ USD)           |  Mean Decrease in Impurity (MDI)      |
|  Blue: Linear Regression (Wide σ)     |  #1 Engine HP (38.2%)                 |
|  Green: Random Forest (Narrow σ)      |  #2 Year (29.4%), #3 Mileage (14.1%)  |
+---------------------------------------+---------------------------------------+
```

---

## ⚡ Execution Modes & Flexibility

The script is crafted to support both **100% autonomous execution (zero input needed)** and **interactive appraisal**:

### Mode 1: Automated Benchmark (Zero Input Required)
```bash
python PricePrediction.py
```
* Generates 2,500 samples
* Audits missing values
* Splits, scales, and encodes
* Trains both models in parallel
* Generates metrics comparison table
* Saves `price_prediction_results.png`
* Tests inference on a sample record

### Mode 2: Interactive Real-Time Appraisal
```bash
python PricePrediction.py --interactive
```
* Prompts you directly in the terminal to input a vehicle's Brand, Year, Mileage, Engine HP, and Body Style.
* Seamlessly executes pipeline imputation for any fields you leave blank.
* Outputs the estimated price from both Linear Regression and Random Forest models simultaneously.

### Mode 3: Alternative California Housing Benchmark
```bash
python PricePrediction.py --dataset housing
```
* Fetches the official Scikit-Learn California Housing dataset (20,640 records) and benchmarks median house values.

---

## 🔬 Single-Record Inference Code Demonstration

Here is how the trained pipeline performs instant inference on raw, un-preprocessed JSON / dictionary data:

```python
import pandas as pd
from PricePrediction import run_price_prediction_pipeline

# 1. Train models and get fitted pipelines
lr_pipeline, rf_pipeline, _ = run_price_prediction_pipeline(dataset_choice="cars")

# 2. Define an un-preprocessed vehicle with intentional missing data
unseen_vehicle = {
    "Brand": "Mercedes-Benz",
    "Year": 2022,
    "Mileage_km": 28000.0,
    "Engine_HP": 310.0,
    "Fuel_Efficiency_kmpl": None,  # Missing! Imputed automatically via pipeline median
    "Transmission": "Automatic",
    "Fuel_Type": "Diesel",
    "Body_Style": "SUV",
}

# 3. Predict in one single line with zero data leakage
estimated_price = rf_pipeline.predict(pd.DataFrame([unseen_vehicle]))[0]
print(f"🌲 Random Forest Appraised Valuation: ${estimated_price:,.2f}")
```

---

## 📂 Project Structure & Files

| File | Purpose |
| :--- | :--- |
| 🐍 [PricePrediction.py](file:///c:/Users/LOKI/Practice/Python/50%20Mini%20Projects/PricePrediction.py) | Master production ML pipeline script with automated + interactive modes. |
| 🐍 [Price Prediction.py](file:///c:/Users/LOKI/Practice/Python/50%20Mini%20Projects/Price%20Prediction.py) | Synced duplicate entrypoint for flexible terminal execution. |
| 📖 [Readme_PricePrediction.md](file:///c:/Users/LOKI/Practice/Python/50%20Mini%20Projects/Readme_PricePrediction.md) | Comprehensive 3D architecture, mathematics, and benchmark documentation. |
| 🖼️ [price_prediction_results.png](file:///c:/Users/LOKI/Practice/Python/50%20Mini%20Projects/price_prediction_results.png) | High-resolution 4-panel diagnostic performance visualization. |

---

<div align="center">
  <b>Built with ❤️ as part of the 50 Mini Projects in Python Master Repository</b>
</div>
