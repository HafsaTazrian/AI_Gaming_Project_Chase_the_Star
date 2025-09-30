import logging
import sys
from random import randint, choice

import pygame as pg
from pygame.locals import *

from game import cfg
from game.map import Map, Status
from game.role import Agent, Enemy
from displayer import Displayer


def create_map() -> Map:
    map_size = cfg.map_size
    if not 1 < map_size["width"]["min"] <= map_size["width"]["max"] \
       or not 1 < map_size["height"]["min"] <= map_size["height"]["max"]:
        raise ValueError("Invalid size of map.")

    curr_try, max_try = 0, 100
    while curr_try < max_try:
        width = randint(map_size["width"]["min"], map_size["width"]["max"])
        height = randint(map_size["height"]["min"], map_size["height"]["max"])
        map = Map(width, height)
        if len(map.blanks()) >= 2:
            return map
        else:
            curr_try += 1
    raise RuntimeError(f"Failed to create a map containing at least 2 blanks within {max_try} times.")


def create_roles(status: Status, map: Map) -> None:
    blanks = map.blanks()
    assert len(blanks) >= 2

    def random_blank() -> tuple[int, int]:
        pos = blanks[randint(0, len(blanks) - 1)]
        blanks.remove(pos)
        return pos

    agent = Agent(status, map, random_blank())
    status.agent = agent
    enemy = Enemy(status, map, random_blank())
    status.enemy = enemy

    # Initialize fixed checkpoints A and B (ensure non-wall, distinct from roles)
    if len(blanks) >= 2:
        a = blanks[randint(0, len(blanks) - 1)]
        blanks.remove(a)
        b = blanks[randint(0, len(blanks) - 1)]
        status.set_checkpoints(a, b)

    # Initialize hidden tunnels: create bidirectional pairs from remaining blanks
    tunnels: dict[tuple[int, int], tuple[int, int]] = {}
    # Create up to 2 bidirectional tunnels if enough blanks remain
    for _ in range(min(2, len(blanks) // 2)):
        if len(blanks) < 2:
            break
        src = blanks[randint(0, len(blanks) - 1)]
        blanks.remove(src)
        dst = blanks[randint(0, len(blanks) - 1)]
        blanks.remove(dst)
        tunnels[src] = dst
        tunnels[dst] = src
    status.set_tunnels(tunnels)


def display_stats(screen: pg.Surface, status: Status, algorithm: str) -> None:
    """Display game statistics on screen."""
    font = pg.font.SysFont('Arial', 16)
    y_offset = 5
    
    texts = [
        f"Algorithm: {algorithm}",
        f"Steps: {status.steps}/{cfg.max_steps}",
        f"Score: {status.score}%",
        f"Good Steps: {status.good_steps}",
        f"Checkpoints: {'A' if status.enemy_visited_a else '_'} {'B' if status.enemy_visited_b else '_'}",
    ]
    
    for i, text in enumerate(texts):
        surf = font.render(text, True, (255, 255, 255))
        rect = surf.get_rect()
        rect.topleft = (10, y_offset + i * 20)
        # Draw background
        bg_rect = rect.inflate(10, 4)
        pg.draw.rect(screen, (0, 0, 0, 180), bg_rect)
        screen.blit(surf, rect)


def get_enemy_algorithm() -> str:
    """Determine which algorithm the enemy is using."""
    weights = cfg.strategy_weights("enemy")
    max_weight = 0
    algo = "Mixed"
    
    for name, weight in weights.items():
        if weight > max_weight:
            max_weight = weight
            algo = name.upper()
    
    return algo


def main():
    pg.init()
    pg.display.set_caption("Chase AI - Enhanced Edition")
    
    status = Status()
    map = create_map()
    create_roles(status, map)
    displayer = Displayer().init(map, status)
    
    enemy_algorithm = get_enemy_algorithm()
    print(f"\n{'='*50}")
    print(f"🎮 CHASE AI - ENHANCED EDITION")
    print(f"{'='*50}")
    print(f"Enemy Algorithm: {enemy_algorithm}")
    print(f"Map Size: {map.width}x{map.height}")
    print(f"Checkpoints: A at {status.checkpoint_a}, B at {status.checkpoint_b}")
    print(f"Tunnels: {len(status.tunnels) // 2} bidirectional pairs")
    print(f"{'='*50}\n")

    move_enemy = False
    paused = False
    
    while True:
        for event in pg.event.get():
            if event.type == QUIT:
                pg.quit()
                sys.exit()
            elif event.type == KEYDOWN:
                if event.key == K_SPACE:
                    paused = not paused
                    print(f"Game {'PAUSED' if paused else 'RESUMED'}")
                elif event.key == K_r:
                    print("\n🔄 Restarting game...")
                    main()
                    return
                elif event.key == K_q:
                    pg.quit()
                    sys.exit()
        
        if not status.game_end and not paused:
            status.agent.move()
            if move_enemy:
                status.enemy.move()

                # Track enemy visits to checkpoints A and B
                if status.checkpoint_a and status.enemy.pos == status.checkpoint_a:
                    if not status.enemy_visited_a:
                        status.enemy_visited_a = True
                        print(f"✓ Enemy visited checkpoint A at step {status.steps}")
                
                if status.checkpoint_b and status.enemy.pos == status.checkpoint_b:
                    if not status.enemy_visited_b:
                        status.enemy_visited_b = True
                        print(f"✓ Enemy visited checkpoint B at step {status.steps}")

                # Enemy catches agent only if checkpoints visited
                if status.enemy.pos == status.agent.pos and status.enemy_can_capture():
                    status.end_game()
                    print(f"\n{'='*50}")
                    print(f"💀 GAME OVER - Enemy caught Agent!")
                    print(f"{'='*50}")
                    print(f"Final Score: {status.score}%")
                    print(f"Total Steps: {status.steps}")
                    print(f"Good Steps: {status.good_steps}")
                    print(f"{'='*50}")
                    print("Press R to restart, Q to quit")
            
            # Only increment step if game is still running
            if not status.game_end:
                status.new_step()
                move_enemy = not move_enemy
            
                # The game will end if the agent is stuck or the number of steps reaches its maximum.
                if status.agent.stuck():
                    status.end_game()
                    print(f"\n{'='*50}")
                    print(f"🎯 AGENT STUCK - Game Over!")
                    print(f"{'='*50}")
                    print(f"Agent Score: {status.score}%")
                    print(f"Total Steps: {status.steps}")
                    print(f"Good Steps: {status.good_steps}")
                    print(f"{'='*50}")
                    print("Press R to restart, Q to quit")
                elif status.steps >= cfg.max_steps:
                    status.end_game()
                    print(f"\n{'='*50}")
                    print(f"⏱️ TIME'S UP - Agent Survived!")
                    print(f"{'='*50}")
                    print(f"Agent Score: {status.score}%")
                    print(f"Total Steps: {status.steps}")
                    print(f"Good Steps: {status.good_steps}")
                    print(f"{'='*50}")
                    print("Press R to restart, Q to quit")
        
        displayer.update()
        
        # Display stats on screen
        display_stats(displayer._window, status, enemy_algorithm)
        pg.display.flip()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    print("\n🎮 CONTROLS:")
    print("  SPACE - Pause/Resume")
    print("  R - Restart Game")
    print("  Q - Quit")
    print()

    try:
        main()
    except SystemExit:
        pass
    except BaseException as err:
        logger.exception(err)
        sys.exit(1)