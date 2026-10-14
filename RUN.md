# How to run

## 1. The live attack (no dependencies — stdlib only)
    python3 demo.py

## 2. The interactive web dashboard
    pip install flask matplotlib
    python3 web/app.py
    # open http://127.0.0.1:5000

## 3. Reproduce the experiments (resumable; writes results/experiments.csv)
    python3 experiments/run_experiments.py

## 4. Regenerate the plots from the CSV
    python3 experiments/make_plots.py
