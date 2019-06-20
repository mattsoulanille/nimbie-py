import usb.core
import usb.util
array = usb.util.array.array
import sys
import time

# Largest incoming packet in bytes as listed in the endpoint descriptor
IN_SIZE = 64

dev = usb.core.find(idVendor=0x1723, idProduct=0x0945)
# was it found?
if dev is None:
    raise ValueError('Device not found')# was it found?

dev.set_configuration() # There's only one config so use that one

# get an endpoint instance
cfg = dev.get_active_configuration()
intf = cfg[(0,0)]

in_ep = usb.util.find_descriptor(
    intf,
    # match the first OUT endpoint
    # OUT means out of the computer and into the device
    custom_match = \
    lambda e: \
        usb.util.endpoint_direction(e.bEndpointAddress) == \
        usb.util.ENDPOINT_IN)



out_ep = usb.util.find_descriptor(
    intf,
    # match the first OUT endpoint
    # OUT means out of the computer and into the device
    custom_match = \
    lambda e: \
        usb.util.endpoint_direction(e.bEndpointAddress) == \
        usb.util.ENDPOINT_OUT)



def send_command(*args):
    if len(args) > 6:
        raise Exception("Too many arguments. Maximum of 6")

    message = bytearray(8)
    for i in range(len(args)):
        message[i + 2] = args[i]

    out_ep.write(message)
    return get_response()

def get_response(minimum=1):
    # Get at least `minimum` messages
    messages = []

    # Get the minimum number of messages
    for i in range(minimum):
        message = read()
        messages.append(message)

    # Get any more messages that aren't null
    message = read()
    while len(message) > 0:
        messages.append(message)
        message = read()
    return messages


class NotStringError(TypeError):
    pass
    
def array_to_string(array):

    if (len(array) == 0):
        return ""
    
    # Expect null termination if nonempty string
    if array[-1] != 0:
        raise NotStringError("Expected array to be null terminated but got " + str(array[-1]))
    return "".join([chr(x) for x in array][:-1])

def read_data():
    return in_ep.read(IN_SIZE, 20000)

def read():
    data = read_data()
    try:
        return array_to_string(data)
    except NotStringError:
        return data

def print_data(array):
    print(array_to_string(array))

# Place the next disk on the tray
def place_disk():
    return send_command(0x52, 0x01)

# Lift the disk from the tray
def lift_disk():
    return send_command(0x47, 0x01)

# Drop the disk into the accept pile
def accept_disk():
    return send_command(0x52, 0x02)

# Drop the disk into the reject pile
def reject_disk():
    return send_command(0x52, 0x03)

