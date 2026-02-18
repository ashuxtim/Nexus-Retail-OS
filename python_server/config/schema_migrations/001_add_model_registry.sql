-- ================================================
-- Migration: Add MLOps Model Registry
-- Version: 001
-- ================================================

-- 1. Model Registry Table
CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT UNIQUE NOT NULL,
    task_type TEXT NOT NULL CHECK(task_type IN ('churn', 'forecast', 'market_basket')),
    algorithm TEXT NOT NULL,
    model_version TEXT NOT NULL,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trained_rows INTEGER NOT NULL,
    data_window_months INTEGER DEFAULT 24,
    feature_version TEXT DEFAULT 'v1',
    file_path TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    is_active INTEGER DEFAULT 0 CHECK(is_active IN (0,1)),
    promoted_at TIMESTAMP,
    replaced_by TEXT,
    evaluation_status TEXT CHECK(evaluation_status IN ('pending', 'approved', 'rejected')),
    evaluation_notes TEXT,
    FOREIGN KEY (replaced_by) REFERENCES model_registry(model_id)
);

CREATE INDEX IF NOT EXISTS idx_model_task_active ON model_registry(task_type, is_active);
CREATE INDEX IF NOT EXISTS idx_model_trained_at ON model_registry(trained_at DESC);

-- 2. Dataset Snapshots Table
CREATE TABLE IF NOT EXISTS dataset_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    row_count INTEGER NOT NULL,
    feature_version TEXT,
    feature_hash TEXT,
    missing_rate REAL,
    outlier_rate REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES model_registry(model_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshot_model ON dataset_snapshots(model_id);

-- 3. Prediction Log Table (Aggregated)
CREATE TABLE IF NOT EXISTS prediction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    task_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    total_predictions INTEGER,
    avg_prediction REAL,
    high_risk_count INTEGER,
    p25 REAL,
    p50 REAL,
    p75 REAL,
    p95 REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, task_type, model_version) ON CONFLICT REPLACE
);

CREATE INDEX IF NOT EXISTS idx_pred_log_date ON prediction_log(date DESC);

-- 4. Verify
SELECT 'Migration 001 Complete' as status;