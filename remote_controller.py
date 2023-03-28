import pygame as pg
import traceback
import math
import zmq
import json

ip = "192.168.8.233"
port = 5555

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"tcp://{ip}:{port}")
print(f"Connected to {ip} {port}")

offset_y = 64
WIDTH = 812
HEIGHT = 554 + offset_y

vec = pg.math.Vector2

# initialize pygame
pg.init()
screen = pg.display.set_mode((WIDTH, HEIGHT))
clock = pg.time.Clock()

pg.joystick.init()

deadzone_stick = 0.2
deadzone_trigger = 0.01

stick_l = vec(0, 0)
stick_r = vec(0, 0)

stick_l_center = vec(214, 175 + offset_y)
stick_r_center = vec(510, 294 + offset_y)

stick_radius = 30
stick_size = 20

trigger_r = 0
trigger_l = 0

# white color
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)

# light shade of the button
color_light = (170,170,170)

# dark shade of the button
color_dark = (100,100,100)

# stores the width of the
# screen into a variable
width = screen.get_width()

# stores the height of the
# screen into a variable
height = screen.get_height()

font = pg.font.SysFont(None, 24)


# game loop
running = True
inverted = False
invert_buffer = 0
try:
    while running:
        clock.tick(60)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False

        # detect gamepad
        gamepads = [pg.joystick.Joystick(x) for x in range(
            pg.joystick.get_count())]
        if len(gamepads) > 0:
            gamepads[0].init()
            axes = gamepads[0].get_numaxes()

            trigger_r = 0
            trigger_l = 0

            # get axes values
            # https://www.pygame.org/docs/ref/joystick.html#pygame.joystick.Joystick
            # current mappings are to Xbox360 controller
            for i in range(axes):
                axis = gamepads[0].get_axis(i)
                if i == 0 and abs(axis) > deadzone_stick:
                    # left stick left/right
                    stick_l.x = axis
                elif i == 1 and abs(axis) > deadzone_stick:
                    # left stick up/down
                    stick_l.y = axis
                elif i == 2 and abs(axis) > deadzone_stick:
                    # right stick left/right
                    stick_r.x = axis
                elif i == 3 and abs(axis) > deadzone_stick:
                    # right stick up/down
                    stick_r.y = axis
                elif i == 4 and axis > deadzone_trigger:
                    # left trigger
                    trigger_l = 1
                elif i == 5 and axis > deadzone_trigger:
                    # right trigger
                    trigger_r = 1

            # A button, prevent inversion from triggering for 10 iterations to prevent button spam input
            if gamepads[0].get_button(0) and invert_buffer >= 10:
                inverted = not inverted
                invert_buffer = 0

            invert_buffer = min(invert_buffer + 1, 10)

            # draw analog sticks
            # left stick
            draw_stick_l = vec(0, 0)
            draw_stick_l.x = stick_l.x * math.sqrt(1 - 0.5 * stick_l.y ** 2)
            draw_stick_l.y = -stick_l.y * math.sqrt(1 - 0.5 * stick_l.x ** 2)
            if round(draw_stick_l.length(), 1) >= deadzone_stick:
                stick_l = vec(0,0)

            # right stick
            draw_stick_r = vec(0, 0)
            draw_stick_r.x = stick_r.x * math.sqrt(1 - 0.5 * stick_r.y ** 2)
            draw_stick_r.y = -stick_r.y * math.sqrt(1 - 0.5 * stick_r.x ** 2)
            if round(draw_stick_r.length(), 1) >= deadzone_stick:
                stick_r = vec(0,0)

            controls = {
                "invert_button": inverted,
                "left_stick_y": draw_stick_l.y,
                "right_stick_y": draw_stick_r.y,
                "left_trigger": trigger_l,
                "right_trigger": trigger_r
            }

            controls_json = json.dumps(controls)
            # socket.send_string(controls_json)

            # response = socket.recv_string()
            # packet = response.replace("\\", "").strip('"')
            packet = json.loads(controls_json)
            response_json = {
                k: v for (k, v) in dict(packet).items()
            }
            right_stick_gui = response_json["right_stick_y"]
            left_stick_gui = response_json["left_stick_y"]
            right_trigger_gui = response_json["right_trigger"]
            left_trigger_gui = response_json["left_trigger"]
            inverted_gui = response_json["invert_button"]

            screen.fill((255, 255, 255))
            pg.draw.rect(screen, color_dark, [width / 2, height / 2, 140, 40])
            screen.blit(font.render(str(inverted_gui), True, BLACK), (20, 20))
            screen.blit(font.render(str(right_stick_gui), True, BLACK), (20, 40))
            screen.blit(font.render(str(left_stick_gui), True, BLACK), (20, 60))
            screen.blit(font.render(str(right_trigger_gui), True, BLACK), (20, 80))
            screen.blit(font.render(str(left_trigger_gui), True, BLACK), (20, 100))

            pg.display.update()
        else:
            text = "No Device plugged in."
            print(text)

    pg.quit()
except Exception:
    traceback.print_exc()
    pg.quit()