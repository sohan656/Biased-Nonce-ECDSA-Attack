#!/usr/bin/env python3
"""
app.py -- Flask web dashboard for the biased-nonce ECDSA key-recovery attack.

Run:   cd ecdsa-hnp-attack  &&  python3 web/app.py
Then open http://127.0.0.1:5000

Endpoints:
  GET  /                 the dashboard
  POST /api/attack       run the live attack (JSON: model, l, t) -> staged result
  GET  /api/results      empirical success-rate / runtime summary from the CSV
  GET  /api/health       liveness check
"""
import sys, os, csv, io, json
from collections import defaultdict
from flask import Flask, request, jsonify, render_template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src import ecdsa_hnp as e

app = Flask(__name__, template_folder="templates", static_folder="static")

CSV_PATH = os.path.join(ROOT, "results", "experiments.csv")

# Safety rails so the web UI can never ask for something that hangs the server.
L_MIN, L_MAX = 6, 28
T_MIN, T_MAX = 15, 48


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


@app.route("/api/attack", methods=["POST"])
def api_attack():
    data = request.get_json(force=True, silent=True) or {}
    model = str(data.get("model", "zero_msb"))
    if model not in e.MODEL_INFO:
        return jsonify({"error": f"unknown model {model!r}"}), 400
    try:
        l = int(data.get("l", 20))
        t = int(data.get("t", 25))
    except (TypeError, ValueError):
        return jsonify({"error": "l and t must be integers"}), 400
    l = max(L_MIN, min(L_MAX, l))
    t = max(T_MIN, min(T_MAX, t))

    result = e.attack_stages(model=model, l=l, t=t)
    return jsonify(result)


@app.route("/api/results")
def api_results():
    """Summarise the experiment CSV into success-rate / runtime series."""
    if not os.path.exists(CSV_PATH):
        return jsonify({"available": False})

    rows = []
    with open(CSV_PATH) as f:
        for r in csv.DictReader(f):
            rows.append(r)

    def rate_series(exp, key):
        agg = defaultdict(lambda: [0, 0])          # value -> [successes, trials]
        for r in rows:
            if r["experiment"] != exp:
                continue
            k = int(r[key])
            agg[k][0] += int(r["success"])
            agg[k][1] += 1
        xs = sorted(agg)
        return {"x": xs, "rate": [round(agg[x][0] / agg[x][1], 3) for x in xs],
                "trials": [agg[x][1] for x in xs]}

    def runtime_series(exp):
        agg = defaultdict(list)
        for r in rows:
            if r["experiment"] != exp:
                continue
            agg[int(r["dim"])].append(float(r["seconds"]))
        xs = sorted(agg)
        return {"x": xs, "seconds": [round(sum(agg[x]) / len(agg[x]), 2) for x in xs]}

    def model_series():
        agg = defaultdict(lambda: [0, 0, 0.0])     # model -> [succ, trials, secsum]
        for r in rows:
            if r["experiment"] != "models":
                continue
            m = r["model"]
            agg[m][0] += int(r["success"]); agg[m][1] += 1
            agg[m][2] += float(r["seconds"])
        return {m: {"rate": round(v[0] / v[1], 3),
                    "avg_seconds": round(v[2] / v[1], 2), "trials": v[1]}
                for m, v in agg.items()}

    return jsonify({
        "available": True,
        "total_trials": len(rows),
        "vs_bias": rate_series("vs_bias", "l"),
        "vs_sigs": rate_series("vs_sigs", "t"),
        "runtime": runtime_series("runtime"),
        "models": model_series(),
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  Biased-Nonce ECDSA Attack -- web dashboard")
    print("  open http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
