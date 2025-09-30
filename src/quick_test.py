import json
import sys
from pathlib import Path

# Get the directory where this script is located
script_dir = Path(__file__).parent

# Look for config.json in the script directory first, then parent
config_path = script_dir / "config.json"
if not config_path.exists():
    config_path = script_dir.parent / "config.json"
if not config_path.exists():
    # Create default config if it doesn't exist
    print("Config file not found. Creating default config.json...")
    
    default_config = {
        "fps": 10,
        "maxSteps": 500,
        "mapSize": {
            "height": {"min": 8, "max": 12},
            "width": {"min": 12, "max": 16}
        },
        "terrainProb": {
            "wall": 0.25,
            "bush": 0.2
        },
        "moveCost": {
            "grass": 1,
            "bush": 10
        },
        "strategyWeights": {
            "agent": {
                "random": 1,
                "moveAway": 0,
                "wallDensity": 0
            },
            "enemy": {
                "random": 0.2,
                "aStar": 1,
                "moveClose": 0.1,
                "wallDensity": 0
            }
        }
    }
    
    config_path = script_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=4)
    print(f"Created config at: {config_path}\n")

algorithms = ["aStar", "dijkstra", "bfs", "greedy", "jps"]

print("\nSelect algorithm:")
for i, algo in enumerate(algorithms, 1):
    print(f"{i}. {algo.upper()}")

try:
    choice = input("\nEnter number (1-5): ").strip()
    selected = algorithms[int(choice) - 1]
except (ValueError, IndexError):
    print("Invalid choice. Using aStar as default.")
    selected = "aStar"

# Load config
with open(config_path) as f:
    config = json.load(f)

# Set selected algorithm
config["strategyWeights"]["enemy"] = {algo: 0 for algo in algorithms}
config["strategyWeights"]["enemy"][selected] = 1

# Also reset other strategies in enemy config
for key in list(config["strategyWeights"]["enemy"].keys()):
    if key not in algorithms:
        config["strategyWeights"]["enemy"][key] = 0

# Save config
with open(config_path, 'w') as f:
    json.dump(config, f, indent=4)

print(f"\nRunning with {selected.upper()} algorithm...")
print(f"Config saved to: {config_path}\n")

# Import and run game
import main
main.main()