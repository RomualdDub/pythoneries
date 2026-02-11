import pygame
import random

# Configuration
WIDTH, HEIGHT = 1000, 800
CENTER = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
NUM_STARS = 5000
STAR_COLOR = (255, 255, 255)
FIXED_SPEED = 15


class Star:
    def __init__(self):
        self.reset()

    def reset(self, far=False):
        self.x = random.uniform(-WIDTH, WIDTH)
        self.y = random.uniform(-HEIGHT, HEIGHT)
        self.z = WIDTH if far else random.uniform(1, WIDTH)
        self.prev_z = self.z

        # VARIATION DE TAILLE :
        # 80% de petites (taille 1), 15% de moyennes (taille 2), 5% de grosses (taille 4)
        rand = random.random()
        if rand < 0.8:
            self.base_size = 1
        elif rand < 0.95:
            self.base_size = 2
        else:
            self.base_size = 4

    def update(self, speed):
        self.prev_z = self.z
        self.z -= speed
        if self.z <= speed:
            self.reset(far=True)

    def draw(self, screen):
        f_pos = (pygame.Vector2(self.x, self.y) / self.z) * WIDTH + CENTER
        p_pos = (pygame.Vector2(self.x, self.y) / self.prev_z) * WIDTH + CENTER

        if 0 <= f_pos.x <= WIDTH and 0 <= f_pos.y <= HEIGHT:
            alpha = int((1 - self.z / WIDTH) * 255)

            # L'épaisseur dépend maintenant de la taille de base ET de la proximité
            thickness = int(max(1, (1 - self.z / WIDTH) * (self.base_size * 3)))

            pygame.draw.line(screen, (alpha, alpha, alpha), p_pos, f_pos, thickness)


# --- Main ---
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
stars = [Star() for _ in range(NUM_STARS)]

overlay = pygame.Surface((WIDTH, HEIGHT))
overlay.set_alpha(60)
overlay.fill((0, 0, 0))

running = True
while running:
    screen.blit(overlay, (0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    for star in stars:
        star.update(FIXED_SPEED)
        star.draw(screen)

    pygame.display.set_caption(f"Starfield - FPS: {int(clock.get_fps())}")
    pygame.display.flip()
    clock.tick(60)

pygame.quit()