# motion_singleton.py
from omotion.Interface import MOTIONInterface

motion_interface, console_connected, left_sensor, right_sensor = MOTIONInterface.acquire_motion_interface()

