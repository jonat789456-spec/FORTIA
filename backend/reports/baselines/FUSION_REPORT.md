# Baseline de fusión

{
  "method": "equal_probability_average",
  "weights": {
    "frames": 0.2,
    "health": 0.2,
    "inventory": 0.2,
    "map": 0.2,
    "audio": 0.2
  },
  "modalities": [
    "frames",
    "health",
    "inventory",
    "map",
    "audio"
  ],
  "validation": {
    "samples": 118,
    "f1_macro": 0.992034632034632,
    "balanced_accuracy": 0.9962121212121212,
    "log_loss": 0.1548077017068863
  },
  "test_used": false
}