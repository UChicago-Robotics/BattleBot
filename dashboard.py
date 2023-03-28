import pygame as pg
import traceback
import math
import json
import zmq
import time
import json

ip = "10.150.71.206"
port = 5555

context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect(f"tcp://{ip}:{port}")
print(f"Connected to {ip} {port}")

# checking the pygame version because they behave different
version = pg.__version__
PGVERSION = int(version.split('.')[0])

offset_y = 64
WIDTH = 812
HEIGHT = 554 + offset_y

vec = pg.math.Vector2

# initialize pygame
pg.init()
screen = pg.display.set_mode((WIDTH, HEIGHT))
clock = pg.time.Clock()
# white color
color = (255,255,255)
  
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

  



# game loop
running = True
try:
    while running:
        screen.fill((255, 255, 255))
        clock.tick(60)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            if event.type == pg.MOUSEBUTTONDOWN:
                if width/2 <= mouse[0] <= width/2+140 and height/2 <= mouse[1] <= height/2+40:
                    print("adssad")
        mouse = pg.mouse.get_pos()
        pg.draw.rect(screen,color_dark,[width/2,height/2,140,40])
        #controls_json = json.dumps(controls)
        #socket.send_string(controls_json)

        #message = socket.recv_string()
        #print(f"Server replied: {message}\n")
        pg.display.update()
    pg.quit()
except Exception:
    traceback.print_exc()
    pg.quit()