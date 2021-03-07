from ctypes import *
from ctypes.util import find_library

readline = cdll.LoadLibrary(find_library('readline'))

# Type declarations
rl_command_func_t = CFUNCTYPE(c_int, c_int, c_int)

# Cursor variables
rl_point = c_int.in_dll(readline, 'rl_point')
rl_end = c_int.in_dll(readline, 'rl_end')

rl_forced_update_display = readline.rl_forced_update_display

rl_bind_key = readline.rl_bind_key
rl_bind_key.argtypes = [c_int, rl_command_func_t]
rl_bind_key.restype = c_int

def force_redisplay():
    """Force the line to be updated and redisplayed, whether or not Readline
    thinks the screen display is correct."""
    rl_forced_update_display()

def bind_key(key, callback):
    """Bind key to function. Function must be a callable with one argument
    representing the count for that key."""
    c_callback = rl_command_func_t(callback)
    rl_bind_key(key, c_callback)

def cursor(pos=None):
    """Set or get the cursor location."""
    if pos is None:
        return rl_point.value
    elif rl_point.value > rl_end.value:
        rl_point.value = rl_end.value
    elif rl_point.value < 0:
        rl_point.value = 0
    else:
        rl_point.value = pos
    return 0
