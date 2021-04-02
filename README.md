# nimbie-py
Python driver for acronova's nimbie NB21


# Using this Project
1. Edit `eject.py` to work with your operating system
2. In your own python source file, import Nimbie (`from driver import Nimbie` should do it). Then, instantiate `Nimbie` and call its `map_over_disks` or `map_over_disks_forever` function, passing it a callback that does whatever you need to do with each disk. The callback can return True or False to accept or reject the disk.

If anyone wants to clean this up and submit it to PyPi as a real package, feel free to. I unfortunately don't have time at the moment to do this myself.
