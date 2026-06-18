# Sample Solution Notes

This folder contains the final sample solution implementation for the anomaly detection pipeline. It includes the training, drift detection, retrain, and serving components that work together with the MLflow model registry.

## Run the pipeline from start to finish

These commands assume you are running from the `sample-solution` folder and that the sibling `data` folder is available at `..\data`.

Yes, I did consider the use of curl, or other bash-synonymous tools. I tried those commands, as if it would work on Linux, but apparently PS required a different parameter scheme. That is the motivation for the section below to stick with PS-friendly syntax (though, IMO, I despise PS). I need not some shell that converts the textual commands into something resembles OOP. Oh well, that's the philosophy of Microsoft for the last two decades anyway, first came VB, then C# and its dotnet packages, then PS came originally as a recommended tool for Windows Server. Now it is the default shell on Windows 11 onwards. 

1. Set the MLflow tracking URI in the shell:
   - PowerShell: `$env:MLFLOW_TRACKING_URI = "http://localhost:5000"`
   - Command Prompt: `set MLFLOW_TRACKING_URI=http://localhost:5000`

2. Start the MLflow tracking server and registry. If you use Docker Compose from the parent folder, start the stack before running the sample solution.

3. Train the initial production model on baseline data:
   ```powershell
   uv run python pipeline.py --data ..\data\baseline.csv
   ```

4. Start the serving API:
   ```powershell
   uv run python serve.py --host 0.0.0.0 --port 8000
   ```

5. Run drift detection on the current window:
   ```powershell
   uv run python drift_detector.py --reference ..\data\baseline.csv --current ..\data\drifted.csv --check-mode combined --labeled-current ..\data\drifted.csv --model-uri models:/anomaly-detector@production
   ```

6. Run retrain and candidate promotion from staging to production:
   ```powershell
   uv run python retrain.py --reference ..\data\baseline.csv --current ..\data\drifted.csv --holdout ..\data\holdout.csv --post-deploy-eval ..\data\post_deploy_eval.csv
   ```

7. If you want to skip the manual approval prompt for testing only:
   ```powershell
   uv run python retrain.py --reference ..\data\baseline.csv --current ..\data\drifted.csv --holdout ..\data\holdout.csv --post-deploy-eval ..\data\post_deploy_eval.csv --auto-approve
   ```

8. Verify the active production version from the serve API:
   ```powershell
   Invoke-RestMethod http://localhost:8000/health/active-version
   ```

## Notes

- The `pipeline.py` script trains an IsolationForest model on `baseline.csv`, logs the run to MLflow, registers the model, and sets the `production` alias.
- The `serve.py` API loads the current `production` alias from MLflow and exposes `/predict`, `/health/active-version`, and `/reload`.
- The `drift_detector.py` script computes data drift with Evidently and can also perform a labeled performance check.
- The `retrain.py` orchestrator retrains on the sliding window of baseline + current data, registers the new version as `staging`, and promotes it after approval.
- The `retrain.py` script includes holdout validation and post-deploy monitoring for auto-rollback if v2 precision drops below the threshold.

## Provenance

- Base code started from the provided sample-solution templates.
- Extended the retrain pipeline to handle degenerate holdout label sets.
- Added explicit rollback reporting and audit events for auto_rollback_v2_to_v1.
- Kept the MLflow alias strategy to support blue-green production swaps without changing the serve code.

## Windows setup journey

- Converted bash into batch files. These are not included in the submission.
- Verified the pipeline on Windows using PowerShell and the local virtual environment at `.\.venv\Scripts\python.exe`.
- Installed `mlflow==2.13.2` and `evidently==0.4.40` into Python 3.11.15.
- Confirmed Windows required Visual Studio C++ Desktop Development 2015 and MSVC v140 build tools to compile binary dependencies.
- Tested `serve.py`, `drift_detector.py`, and `retrain.py` end to end on localhost.
- Verified the holdout path with `--holdout ..\data\holdout.csv` and the auto-rollback path with `--post-deploy-eval ..\data\post_deploy_eval.csv`.
- Confirmed `outputs/audit_log.jsonl` contains the rollback event and that the service reloads after alias swaps.
