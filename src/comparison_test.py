"""
Algorithm Comparison Tool for Chase AI
Run this to compare performance of different pathfinding algorithms
"""

import json
import time
from pathlib import Path
from typing import Dict, List
import statistics

from game import cfg
from game.map import Map, Status
from game.role import Agent, Enemy
from random import randint


class BenchmarkResult:
    def __init__(self, algorithm: str):
        self.algorithm = algorithm
        self.wins = 0
        self.losses = 0
        self.timeouts = 0
        self.avg_score = 0.0
        self.avg_steps = 0.0
        self.avg_time = 0.0
        self.scores: List[int] = []
        self.times: List[float] = []
        self.steps: List[int] = []

    def add_result(self, score: int, steps: int, duration: float, outcome: str):
        self.scores.append(score)
        self.steps.append(steps)
        self.times.append(duration)
        
        if outcome == "win":
            self.wins += 1
        elif outcome == "loss":
            self.losses += 1
        else:
            self.timeouts += 1

    def calculate_stats(self):
        if self.scores:
            self.avg_score = statistics.mean(self.scores)
            self.avg_steps = statistics.mean(self.steps)
            self.avg_time = statistics.mean(self.times)

    def __str__(self):
        total = self.wins + self.losses + self.timeouts
        win_rate = (self.wins / total * 100) if total > 0 else 0
        
        return f"""
Algorithm: {self.algorithm.upper()}
{'='*50}
Games: {total}
Wins: {self.wins} ({win_rate:.1f}%)
Losses: {self.losses}
Timeouts: {self.timeouts}
Avg Score: {self.avg_score:.1f}%
Avg Steps: {self.avg_steps:.1f}
Avg Time: {self.avg_time:.3f}s
Score StdDev: {statistics.stdev(self.scores) if len(self.scores) > 1 else 0:.1f}
"""


def create_test_map() -> Map:
    """Create a map for testing."""
    width = randint(cfg.map_size["width"]["min"], cfg.map_size["width"]["max"])
    height = randint(cfg.map_size["height"]["min"], cfg.map_size["height"]["max"])
    
    for _ in range(100):
        map = Map(width, height)
        if len(map.blanks()) >= 6:  # Need space for roles, checkpoints, tunnels
            return map
    
    raise RuntimeError("Failed to create valid map")


def setup_game(algorithm: str) -> tuple[Status, Map]:
    """Setup a game with specific algorithm."""
    status = Status()
    map = create_test_map()
    
    blanks = map.blanks()
    
    def random_blank() -> tuple[int, int]:
        pos = blanks[randint(0, len(blanks) - 1)]
        blanks.remove(pos)
        return pos
    
    # Create roles
    agent = Agent(status, map, random_blank())
    status.agent = agent
    enemy = Enemy(status, map, random_blank())
    status.enemy = enemy
    
    # Set checkpoints
    if len(blanks) >= 2:
        a = random_blank()
        b = random_blank()
        status.set_checkpoints(a, b)
    
    # Set tunnels
    tunnels: dict[tuple[int, int], tuple[int, int]] = {}
    for _ in range(min(2, len(blanks) // 2)):
        if len(blanks) < 2:
            break
        src = random_blank()
        dst = random_blank()
        tunnels[src] = dst
        tunnels[dst] = src
    status.set_tunnels(tunnels)
    
    # Override enemy strategy with test algorithm
    original_config = cfg.strategy_weights("enemy").copy()
    test_weights = {k: 0 for k in original_config.keys()}
    test_weights[algorithm] = 1
    
    # Reload enemy with new weights
    cfg._cfg["strategyWeights"]["enemy"] = test_weights
    
    return status, map


def run_single_game(algorithm: str, max_steps: int = 500, verbose: bool = False) -> tuple[int, int, str]:
    """
    Run a single game and return (score, steps, outcome).
    Outcome: 'win', 'loss', 'timeout'
    """
    status, map = setup_game(algorithm)
    
    move_enemy = False
    step = 0
    
    while step < max_steps and not status.game_end:
        status.agent.move()
        
        if move_enemy:
            status.enemy.move()
            
            # Check checkpoint visits
            if status.checkpoint_a and status.enemy.pos == status.checkpoint_a:
                status.enemy_visited_a = True
            if status.checkpoint_b and status.enemy.pos == status.checkpoint_b:
                status.enemy_visited_b = True
            
            # Check capture
            if status.enemy.pos == status.agent.pos and status.enemy_can_capture():
                status.end_game()
                return status.score, status.steps, "loss"
        
        status.new_step()
        move_enemy = not move_enemy
        step += 1
        
        # Check if agent stuck
        if status.agent.stuck():
            status.end_game()
            return status.score, status.steps, "loss"
    
    # Timeout - agent survived
    if not status.game_end:
        status.end_game()
        return status.score, status.steps, "timeout"
    
    return status.score, status.steps, "win"


def benchmark_algorithm(algorithm: str, num_games: int = 10, verbose: bool = True) -> BenchmarkResult:
    """Run multiple games and collect statistics."""
    result = BenchmarkResult(algorithm)
    
    if verbose:
        print(f"\nTesting {algorithm.upper()}...")
        print(f"Running {num_games} games...\n")
    
    for i in range(num_games):
        start_time = time.time()
        score, steps, outcome = run_single_game(algorithm)
        duration = time.time() - start_time
        
        result.add_result(score, steps, duration, outcome)
        
        if verbose:
            outcome_symbol = "✓" if outcome == "timeout" else "✗" if outcome == "loss" else "~"
            print(f"  Game {i+1:2d}: {outcome_symbol} Score: {score:3d}% | Steps: {steps:3d} | Time: {duration:.3f}s | {outcome.upper()}")
    
    result.calculate_stats()
    return result


def compare_all_algorithms(num_games: int = 10):
    """Compare all pathfinding algorithms."""
    algorithms = ["aStar", "dijkstra", "bfs", "greedy", "jps"]
    results: Dict[str, BenchmarkResult] = {}
    
    print("\n" + "="*60)
    print("CHASE AI - ALGORITHM COMPARISON BENCHMARK")
    print("="*60)
    print(f"Games per algorithm: {num_games}")
    print(f"Max steps per game: {cfg.max_steps}")
    print("="*60)
    
    # Run benchmarks
    for algo in algorithms:
        try:
            results[algo] = benchmark_algorithm(algo, num_games, verbose=True)
        except Exception as e:
            print(f"Error testing {algo}: {e}")
    
    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK RESULTS")
    print("="*60)
    
    for algo, result in results.items():
        print(result)
    
    # Print comparison table
    print("\n" + "="*60)
    print("COMPARATIVE ANALYSIS")
    print("="*60)
    print(f"{'Algorithm':<12} {'Win Rate':<12} {'Avg Score':<12} {'Avg Steps':<12} {'Avg Time':<12}")
    print("-"*60)
    
    for algo, result in results.items():
        total = result.wins + result.losses + result.timeouts
        win_rate = (result.wins / total * 100) if total > 0 else 0
        print(f"{algo:<12} {win_rate:>6.1f}%     {result.avg_score:>6.1f}%     {result.avg_steps:>8.1f}     {result.avg_time:>7.3f}s")
    
    # Find best performer
    best_score = max(results.values(), key=lambda r: r.avg_score)
    fastest = min(results.values(), key=lambda r: r.avg_time)
    most_wins = max(results.values(), key=lambda r: r.wins)
    
    print("\n" + "="*60)
    print("WINNERS")
    print("="*60)
    print(f"Highest Score: {best_score.algorithm.upper()} ({best_score.avg_score:.1f}%)")
    print(f"Fastest: {fastest.algorithm.upper()} ({fastest.avg_time:.3f}s avg)")
    print(f"Most Wins: {most_wins.algorithm.upper()} ({most_wins.wins} wins)")
    print("="*60 + "\n")


def head_to_head(algo1: str, algo2: str, num_games: int = 20):
    """Direct comparison between two algorithms."""
    print(f"\n{'='*60}")
    print(f"HEAD-TO-HEAD: {algo1.upper()} vs {algo2.upper()}")
    print(f"{'='*60}")
    
    result1 = benchmark_algorithm(algo1, num_games, verbose=False)
    result2 = benchmark_algorithm(algo2, num_games, verbose=False)
    
    print(f"\n{algo1.upper()}:")
    print(f"  Avg Score: {result1.avg_score:.1f}%")
    print(f"  Avg Steps: {result1.avg_steps:.1f}")
    print(f"  Wins: {result1.wins}")
    
    print(f"\n{algo2.upper()}:")
    print(f"  Avg Score: {result2.avg_score:.1f}%")
    print(f"  Avg Steps: {result2.avg_steps:.1f}")
    print(f"  Wins: {result2.wins}")
    
    if result1.avg_score > result2.avg_score:
        print(f"\nWINNER: {algo1.upper()} by {result1.avg_score - result2.avg_score:.1f}%")
    elif result2.avg_score > result1.avg_score:
        print(f"\nWINNER: {algo2.upper()} by {result2.avg_score - result1.avg_score:.1f}%")
    else:
        print(f"\nRESULT: TIE")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark Chase AI pathfinding algorithms")
    parser.add_argument("--games", type=int, default=10, help="Number of games per algorithm")
    parser.add_argument("--compare", nargs=2, metavar=("ALGO1", "ALGO2"), 
                       help="Compare two specific algorithms head-to-head")
    parser.add_argument("--single", type=str, help="Test a single algorithm")
    parser.add_argument("--all", action="store_true", help="Compare all algorithms")
    
    args = parser.parse_args()
    
    # Load config
    config_path = Path(__file__).parent / "config.json"
    cfg.load(config_path)
    
    if args.compare:
        head_to_head(args.compare[0], args.compare[1], args.games)
    elif args.single:
        result = benchmark_algorithm(args.single, args.games, verbose=True)
        print(result)
    else:
        # Default: compare all
        compare_all_algorithms(args.games)
    
    print("\nBenchmark complete!")