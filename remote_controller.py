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
# print(pg.font.get_fonts())
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
YELLOW = (255, 255, 0)

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

font = pg.font.SysFont("lucidaconsole", 20)
logo = pg.image.load("assets/logo.png")
logo = pg.transform.scale(logo, (120, 120))
name = pg.image.load("assets/name.png")
name = pg.transform.scale(name, (340, 100))

# game loop
running = True
inverted = False
invert_buffer = 0
paused = False
try:
    while running:
        screen.fill((255, 255, 255))
        screen.blit(logo, (0, 0))
        screen.blit(name, (140, 10))

        clock.tick(60)

        # detect gamepad
        gamepads = [pg.joystick.Joystick(x) for x in range(
            pg.joystick.get_count())]
        # if not paused:
        if len(gamepads) > 0 and not paused:
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
                "type": "control",
                "invert_button": inverted,
                "left_stick_y": draw_stick_l.y,
                "right_stick_y": draw_stick_r.y,
                "left_trigger": trigger_l,
                "right_trigger": trigger_r
            }

            controls_json = json.dumps(controls)

            ### UNCOMMENT THE NEXT THREE LINES FOR ACTUAL USE
            socket.send_string(controls_json)
            response = socket.recv_string()
            packet = response.replace("\\", "").strip('"')

            # packet = json.loads(controls_json) ### COMMENT OUT THIS LINE WHEN USING -- TESTING ONLY LINE
            response_json = {
                k: v for (k, v) in dict(packet).items()
            }
            # response_json["battery"] = 4 ### COMMENT OUT THIS LINE WHEN USING -- TESTING ONLY LINE
            right_stick_gui = response_json["right_stick_y"]
            left_stick_gui = response_json["left_stick_y"]
            right_trigger_gui = response_json["right_trigger"]
            left_trigger_gui = response_json["left_trigger"]
            inverted_gui = response_json["invert_button"]
            battery_gui = response_json["battery"]

            # min 20, max 502, width mid = 261, height mid = 359, min 120, max 598

            # inverted status
            inverted_text = font.render("UPRIGHT" if not inverted_gui else "INVERTED", True, GREEN if not inverted_gui else RED)
            screen.blit(inverted_text, (261 - inverted_text.get_width() / 2, 142))

            # trigger rectangles
            lt_text = font.render("LT", True, BLACK)
            rt_text = font.render("RT", True, BLACK)
            pg.draw.rect(screen, color_light if left_trigger_gui == 0 else GREEN, [56, 200, 150, 150])
            screen.blit(lt_text, (131 - lt_text.get_width() / 2, 178))
            pg.draw.rect(screen, color_light if right_trigger_gui == 0 else GREEN, [307, 200, 150, 150])
            screen.blit(rt_text, (382 - rt_text.get_width() / 2, 178))

            # have direction of spinner in controller center
            # ^, v, -
            # left trigger - right trigger, 1 when active, 0 when not therefore 1 is motor forward, -1 is motor backward
            spinner_dir = left_trigger_gui - right_trigger_gui
            spinner_text = font.render("-", True, BLACK)
            if (spinner_dir == 1 and not inverted_gui) or (spinner_dir == -1 and inverted_gui):
                spinner_text = font.render("^", True, BLACK)
            elif (spinner_dir == -1 and not inverted_gui) or (spinner_dir == 1 and inverted_gui):
                spinner_text = font.render("v", True, BLACK)
            screen.blit(spinner_text, (260 - spinner_text.get_width() / 2, 230))
            screen.blit(spinner_text, (260 - spinner_text.get_width() / 2, 252))
            screen.blit(spinner_text, (260 - spinner_text.get_width() / 2, 274))
            screen.blit(spinner_text, (260 - spinner_text.get_width() / 2, 296))

            # sticks
            ls_text = font.render("LS", True, BLACK)
            rs_text = font.render("RS", True, BLACK)
            ls_text_value = font.render(str(left_stick_gui)[:5], True, BLACK)
            rs_text_value = font.render(str(right_stick_gui)[:5], True, BLACK)
            pg.draw.rect(screen, color_light, [130, 400, 2, 178])
            pg.draw.rect(screen, color_dark, [123, 400 + 89 - 89 * left_stick_gui - 2, 15, 4])
            screen.blit(ls_text, (131 - ls_text.get_width() / 2, 378))
            screen.blit(ls_text_value, (171 - ls_text_value.get_width() / 2, 400 + 89 - 10))
            pg.draw.rect(screen, color_light, [381, 400, 2, 178])
            pg.draw.rect(screen, color_dark, [374, 400 + 89 - 89 * right_stick_gui - 2, 15, 4])
            screen.blit(rs_text, (382 - rs_text.get_width() / 2, 378))
            screen.blit(rs_text_value, (342 - rs_text_value.get_width() / 2, 400 + 89 - 10))

            # Battery
            percentage = 100 * battery_gui / 24
            battery_text = "Battery: " + str(battery_gui) + "/24 V (" + "%.1f%%" % percentage + ")"
            screen.blit(font.render(battery_text, True, BLACK), (width - 300 - 6, 252))
            # battery bounding box
            pg.draw.rect(screen, color_light, [width - 300 - 6, 274, 288, 2]) # top
            pg.draw.rect(screen, color_light, [width - 300 - 6, 274, 2, 80]) # left
            pg.draw.rect(screen, color_light, [width - 300 - 6, 354, 288, 2]) # bottom
            pg.draw.rect(screen, color_light, [width - 20, 274, 2, 80]) # right
            # battery image
            battery_color = GREEN
            if percentage <= 25:
                battery_color = RED
            elif percentage <= 50:
                battery_color = YELLOW
            pg.draw.rect(screen, battery_color, [width - 300 - 2, 278, 280 * percentage / 100, 74])

            # Raw last packet received data
            screen.blit(font.render("Last Packet Raw:", True, BLACK), (width - 300, height - 244))
            screen.blit(font.render("{", True, BLACK), (width - 300, height - 222))
            offset = 22
            for key in response_json:
                value = str(response_json[key])
                if key == "right_stick_y" or key == "left_stick_y":
                    value = value[:5]
                screen.blit(font.render(str(key) + ":" + value, True, BLACK), (width - 280, height - 222 + offset))
                offset += 22
            screen.blit(font.render("}", True, BLACK), (width - 300, height - 222 + offset))
        elif paused:
            packet = {"type":"pause"}
            print("paused")
            ### UNCOMMENT THIS LINE FOR ACTUAL USE
            socket.send_string(json.dumps(packet))
        else:
            text = "No Controller Detected"
            screen.blit(font.render(text, True, RED), (20, 140))
            print(text)

        mouse = pg.mouse.get_pos()
        for event in pg.event.get():
            # print(event)
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEBUTTONDOWN:
                if width - 291 <= mouse[0] <= width - 20 and 20 + 100 + 2 <= mouse[1] <= 20 + 100 + 2 + 100:
                    paused = not paused
                elif width - 291 <= mouse[0] <= width - 20 and 20 <= mouse[1] <= 20 + 100:
                    running = False
            # elif event.type == pg.KEYDOWN:
            #     if event.key == pg.K_p:
            #         paused = not paused
            #     elif event.key == pg.K_q:
            #         pg.quit()

        # kill button
        pg.draw.rect(screen, RED, [width - 291, 20, 273, 100])
        kill_text = font.render("KILL", True, color_light)
        screen.blit(kill_text, (width - 20 - 137 - kill_text.get_width() / 2, 60))

        # pause button
        pg.draw.rect(screen, GREEN if not paused else RED, [width - 291, 122, 273, 100])
        pause_text = font.render("PAUSE", True, color_light)
        screen.blit(pause_text, (width - 20 - 137 - pause_text.get_width() / 2, 162))

        # status
        screen.blit(font.render("STATUS: PAUSED" if paused else "STATUS: RUNNING", True, GREEN if not paused else RED), (width - 300 - 6, 232))

        # last packet box
        pg.draw.rect(screen, color_light, [width - 300 - 6, height - 244 - 6, 288, 2]) # top
        pg.draw.rect(screen, color_light, [width - 300 - 6, height - 244 - 6, 2, 230]) # left
        pg.draw.rect(screen, color_light, [width - 300 - 6, height - 20 - 2, 288, 2]) # bottom
        pg.draw.rect(screen, color_light, [width - 20, height - 244 - 6, 2, 230]) # right

        # controller bounding box
        pg.draw.rect(screen, color_light, [20, 120, 482, 2]) # top
        pg.draw.rect(screen, color_light, [20, 120, 2, 478]) # left
        pg.draw.rect(screen, color_light, [500, 120, 2, 478]) # right
        pg.draw.rect(screen, color_light, [20, 596, 482, 2]) # bottom

        pg.display.update()

    pg.quit()
except Exception:
    traceback.print_exc()
    pg.quit()