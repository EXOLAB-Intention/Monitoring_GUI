# Fichier : controller_generator.py
import math
import random

class ControllerState:
    def __init__(self, num_buttons=4):
        self.num_buttons = num_buttons
        self.last_press_time = [0.0] * num_buttons
        self.next_press_delay = [random.uniform(1.0, 2.0) for _ in range(num_buttons)]
        self.joystick_phase = random.uniform(0, 2 * math.pi)
        self.motion_start_time = None

    def generate(self, t):
        buttons = []
        for i in range(self.num_buttons):
            if t - self.last_press_time[i] > self.next_press_delay[i]:
                buttons.append(True)
                self.last_press_time[i] = t
                self.next_press_delay[i] = random.uniform(1.0, 2.0)
            else:
                buttons.append(False)

        if self.motion_start_time is None and random.random() < 0.01:
            self.motion_start_time = t
            self.joystick_phase = random.uniform(0, 2 * math.pi)

        if self.motion_start_time is not None:
            dt = t - self.motion_start_time
            if dt > 2.0:
                self.motion_start_time = None
                joy_x, joy_y = 128, 128
            else:
                joy_x = int(128 + 60 * math.sin(0.5 * dt + self.joystick_phase))
                joy_y = int(128 + 60 * math.sin(0.4 * dt + self.joystick_phase + 1))
        else:
            joy_x, joy_y = 128, 128

        return {
            "buttons": buttons,
            "joystick": {"x": joy_x, "y": joy_y}
        }
