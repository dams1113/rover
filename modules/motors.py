# modules/motors.py
from robot_hat import Motor
import time

motor_left = Motor("M1")
motor_right = Motor("M2")

def stop():
    motor_left.stop()
    motor_right.stop()

def forward(speed=50, duration=None):
    motor_left.speed(speed)
    motor_right.speed(speed)
    if duration:
        time.sleep(duration)
        stop()

def backward(speed=50, duration=None):
    motor_left.speed(-speed)
    motor_right.speed(-speed)
    if duration:
        time.sleep(duration)
        stop()

def turn_left(speed=50, duration=None):
    motor_left.speed(-speed)
    motor_right.speed(speed)
    if duration:
        time.sleep(duration)
        stop()

def turn_right(speed=50, duration=None):
    motor_left.speed(speed)
    motor_right.speed(-speed)
    if duration:
        time.sleep(duration)
        stop()
