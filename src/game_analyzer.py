"""
Game Analyzer - Visualize pathfinding behavior and generate heatmaps
"""

import json
from pathlib import Path
from typing import List, Tuple
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import defaultdict

from game import cfg
from game.map import Map, Status, Terrain
from game.role import Agent, Enemy
from random import randint


class GameRecorder:
    """Records game state for later analysis."""
    
    def __init__(self):
        self.positions: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []  # (agent_pos, enemy_pos)
        self.paths: List[List[Tuple[int, int]]] = []  # Enemy paths
        self.checkpoint_visits: List[Tuple[int, str]] = []  # (step, checkpoint)
        self.tunnel_uses: List[Tuple[int, Tuple[int, int], Tuple[int, int]]] = []  # (step, from, to)
        
    def record_step(self, agent_pos: Tuple[int, int], enemy_pos: Tuple[int, int], 
                   enemy_path: List[Tuple[int, int]], step: int):
        self.positions.append((agent_pos, enemy_pos))
        self.paths.append(enemy_path.copy())
    
    def record_checkpoint(self, step: int, checkpoint: str):
        self.checkpoint_visits.append((step, checkpoint))
    
    def record_tunnel(self, step: int, from_pos: Tuple[int, int], to_pos: Tuple[int, int]):
        self.tunnel_uses.append((step, from_pos, to_pos))


def create_heatmap(recorder: GameRecorder, map: Map, title: str = "Enemy Movement Heatmap"):
    """Create a heatmap showing where the enemy spent most time."""
    
    # Count visits to each position
    visit_count = defaultdict(int)
    for _, enemy_pos in recorder.positions:
        visit_count[enemy_pos] += 1
    
    # Create grid
    heatmap = [[0 for _ in range(map.height)] for _ in range(map.width)]
    max_visits = max(visit_count.values()) if visit_count else 1
    
    for (x, y), count in visit_count.items():
        heatmap[x][y] = count / max_visits
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Draw heatmap
    for x in range(map.width):
        for y in range(map.height):
            if map.wall(x, y):
                color = 'black'
            else:
                intensity = heatmap[x][y]
                color = (1-intensity, 1-intensity, 1)  # White to blue
            
            rect = patches.Rectangle((x, y), 1, 1, linewidth=0.5, 
                                     edgecolor='gray', facecolor=color)
            ax.add_patch(rect)
    
    # Mark start and end positions
    if recorder.positions:
        start_agent, start_enemy = recorder.positions[0]
        end_agent, end_enemy = recorder.positions[-1]
        
        ax.plot(start_agent[0] + 0.5, start_agent[1] + 0.5, 'g*', markersize=20, label='Agent Start')
        ax.plot(end_agent[0] + 0.5, end_agent[1] + 0.5, 'gx', markersize=15, label='Agent End')
        ax.plot(start_enemy[0] + 0.5, start_enemy[1] + 0.5, 'r*', markersize=20, label='Enemy Start')
        ax.plot(end_enemy[0] + 0.5, end_enemy[1] + 0.5, 'rx', markersize=15, label='Enemy End')
    
    ax.set_xlim(0, map.width)
    ax.set_ylim(0, map.height)
    ax.set_aspect('equal')
    ax.set_title(title)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def create_path_visualization(recorder: GameRecorder, map: Map, step_interval: int = 50):
    """Visualize enemy paths at different time intervals."""
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    axes = axes.flatten()
    
    intervals = [len(recorder.positions) // 4 * i for i in range(1, 5)]
    
    for idx, step in enumerate(intervals):
        if step >= len(recorder.positions):
            continue
            
        ax = axes[idx]
        
        # Draw map
        for x in range(map.width):
            for y in range(map.height):
                if map.wall(x, y):
                    color = 'black'
                elif map.terrain(x, y) == Terrain.BUSH:
                    color = 'green'
                else:
                    color = 'white'
                
                rect = patches.Rectangle((x, y), 1, 1, linewidth=0.5,
                                         edgecolor='gray', facecolor=color)
                ax.add_patch(rect)
        
        # Draw path
        if step < len(recorder.paths) and recorder.paths[step]:
            path = recorder.paths[step]
            path_x = [p[0] + 0.5 for p in path]
            path_y = [p[1] + 0.5 for p in path]
            ax.plot(path_x, path_y, 'r-', linewidth=2, alpha=0.7, label='Enemy Path')
        
        # Draw positions
        agent_pos, enemy_pos = recorder.positions[step]
        ax.plot(agent_pos[0] + 0.5, agent_pos[1] + 0.5, 'g*', markersize=15, label='Agent')
        ax.plot(enemy_pos[0] + 0.5, enemy_pos[1] + 0.5, 'ro', markersize=12, label='Enemy')
        
        ax.set_xlim(0, map.width)
        ax.set_ylim(0, map.height)
        ax.set_aspect('equal')
        ax.set_title(f'Step {step}')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def create_distance_plot(recorder: GameRecorder):
    """Plot distance between agent and enemy over time."""
    
    distances = []
    for agent_pos, enemy_pos in recorder.positions:
        dist = abs(agent_pos[0] - enemy_pos[0]) + abs(agent_pos[1] - enemy_pos[1])
        distances.append(dist)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    steps = list(range(len(distances)))
    ax.plot(steps, distances, 'b-', linewidth=2, label='Manhattan Distance')
    ax.axhline(y=2, color='r', linestyle='--', label='Safe Distance Threshold')
    
    # Mark checkpoint visits
    for step, checkpoint in recorder.checkpoint_visits:
        ax.axvline(x=step, color='green', linestyle=':', alpha=0.5)
        ax.text(step, max(distances) * 0.9, f'CP {checkpoint}', 
               rotation=90, verticalalignment='bottom')
    
    # Mark tunnel uses
    for step, _, _ in recorder.tunnel_uses:
        ax.axvline(x=step, color='purple', linestyle=':', alpha=0.5)
    
    ax.set_xlabel('Step')
    ax.set_ylabel('Distance')
    ax.set_title('Agent-Enemy Distance Over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


def analyze_game(algorithm: str, visualize: bool = True, save_plots: bool = False):
    """Run a game and analyze the behavior."""
    
    print(f"\nAnalyzing {algorithm.upper()} algorithm...")
    
    # Setup game
    from comparison_test import setup_game
    status, map = setup_game(algorithm)
    
    recorder = GameRecorder()
    
    # Run game
    move_enemy = False
    max_steps = cfg.max_steps
    
    for step in range(max_steps):
        if status.game_end:
            break
            
        # Record positions
        if hasattr(status.enemy, 'path'):
            path = status.enemy.path
        else:
            path = []
        recorder.record_step(status.agent.pos, status.enemy.pos, path, step)
        
        # Move
        status.agent.move()
        
        if move_enemy:
            prev_pos = status.enemy.pos
            status.enemy.move()
            
            # Check for tunnel use
            if prev_pos in status.tunnels and status.enemy.pos == status.tunnels[prev_pos]:
                recorder.record_tunnel(step, prev_pos, status.enemy.pos)
            
            # Check checkpoint visits
            if status.checkpoint_a and status.enemy.pos == status.checkpoint_a:
                if not status.enemy_visited_a:
                    status.enemy_visited_a = True
                    recorder.record_checkpoint(step, 'A')
            
            if status.checkpoint_b and status.enemy.pos == status.checkpoint_b:
                if not status.enemy_visited_b:
                    status.enemy_visited_b = True
                    recorder.record_checkpoint(step, 'B')
            
            # Check capture
            if status.enemy.pos == status.agent.pos and status.enemy_can_capture():
                status.end_game()
                break
        
        status.new_step()
        move_enemy = not move_enemy
        
        if status.agent.stuck():
            status.end_game()
            break
    
    # Print statistics
    print(f"\nGame Statistics:")
    print(f"  Total Steps: {status.steps}")
    print(f"  Good Steps: {status.good_steps}")
    print(f"  Score: {status.score}%")
    print(f"  Outcome: {'Agent Survived' if not status.game_end or status.steps == max_steps else 'Enemy Won'}")
    print(f"  Checkpoints Visited: {'A' if status.enemy_visited_a else '_'} {'B' if status.enemy_visited_b else '_'}")
    print(f"  Tunnel Uses: {len(recorder.tunnel_uses)}")
    
    # Calculate path efficiency
    total_path_length = sum(len(path) for path in recorder.paths if path)
    avg_path_length = total_path_length / len([p for p in recorder.paths if p]) if recorder.paths else 0
    print(f"  Avg Path Length: {avg_path_length:.1f}")
    
    # Visualize
    if visualize:
        try:
            import matplotlib
            matplotlib.use('TkAgg')  # Use TkAgg backend for display
            
            # Create visualizations
            heatmap_fig = create_heatmap(recorder, map, f"{algorithm.upper()} - Movement Heatmap")
            path_fig = create_path_visualization(recorder, map)
            distance_fig = create_distance_plot(recorder)
            
            if save_plots:
                output_dir = Path("analysis_output")
                output_dir.mkdir(exist_ok=True)
                
                heatmap_fig.savefig(output_dir / f"{algorithm}_heatmap.png", dpi=150)
                path_fig.savefig(output_dir / f"{algorithm}_paths.png", dpi=150)
                distance_fig.savefig(output_dir / f"{algorithm}_distance.png", dpi=150)
                
                print(f"\nPlots saved to {output_dir}/")
            
            plt.show()
            
        except ImportError:
            print("\nMatplotlib not installed. Install with: pip install matplotlib")
        except Exception as e:
            print(f"\nError creating visualizations: {e}")
    
    return recorder, status


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze Chase AI pathfinding algorithms")
    parser.add_argument("algorithm", type=str, choices=["aStar", "dijkstra", "bfs", "greedy", "jps"],
                       help="Algorithm to analyze")
    parser.add_argument("--no-viz", action="store_true", help="Skip visualization")
    parser.add_argument("--save", action="store_true", help="Save plots to files")
    
    args = parser.parse_args()
    
    # Load config
    config_path = Path(__file__).parent / "config.json"
    cfg.load(config_path)
    
    analyze_game(args.algorithm, visualize=not args.no_viz, save_plots=args.save)
    
    print("\nAnalysis complete!")