import usb.core
import usb.util
array = usb.util.array.array
import sys
from eject import open_tray, close_tray


# Largest incoming packet in bytes as listed in the endpoint descriptor
IN_SIZE = 64

# The array -> string decoder's error message
class NotStringError(TypeError):
    pass

# If the state of the hardware does not support
# the requested operation
class HardwareStateError(Exception):
    pass

# No disk available in the input queue
class NoDiskError(HardwareStateError):
    pass


class Nimbie:
    def __init__(self):
        dev = usb.core.find(idVendor=0x1723, idProduct=0x0945)
        if dev is None:
            raise ValueError('Device not found')# was it found?

        dev.set_configuration() # There's only one config so use that one
        
        # get an endpoint instance
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]

        self.in_ep = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            # OUT means out of the computer and into the device
            custom_match = \
            lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_IN)

        self.out_ep = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            # OUT means out of the computer and into the device
            custom_match = \
            lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_OUT)

    def send_command(self, *args):
        if len(args) > 6:
            raise Exception("Too many arguments. Maximum of 6")

        message = bytearray(8)
        for i in range(len(args)):
            message[i + 2] = args[i]

        self.out_ep.write(message)
        return self.get_response()

    def get_response(self, minimum=1):
        # Get at least `minimum` messages
        messages = []

        # Get the minimum number of messages
        for i in range(minimum):
            message = self.read()
            messages.append(message)

        # Get any more messages that aren't null
        message = self.read()
        while len(message) > 0:
            messages.append(message)
            message = self.read()
        return messages

    @staticmethod
    def array_to_string(array):
        if (len(array) == 0):
            return ""

        # Expect null termination if nonempty string
        if array[-1] != 0:
            raise NotStringError("Expected array to be null terminated but got " + str(array[-1]))
        return "".join([chr(x) for x in array][:-1])

    def read_data(self):
        # Maybe have the timeout be an option instead of just 20 seconds?
        return self.in_ep.read(IN_SIZE, 20000)

    def read(self):
        data = self.read_data()
        try:
            return self.array_to_string(data)
        except NotStringError:
            return data

#def print_data(array):
#    print(array_to_string(array))


    # Place the next disk on the tray
    def place_disk(self):
        if (not self.disk_available()):
            raise NoDiskError("Cannot place non-existent disk")

        return self.send_command(0x52, 0x01)

    # Lift the disk from the tray
    def lift_disk(self):
        return self.send_command(0x47, 0x01)

    # Drop the disk into the accept pile
    def accept_disk(self):
        return self.send_command(0x52, 0x02)

    # Drop the disk into the reject pile
    def reject_disk(self):
        return self.send_command(0x52, 0x03)

    # Whether or not a disk is available in the input queue
    def disk_available(self):
        status_res = self.send_command(0x43)
        # Sometimes it takes a while to respond
        try:
            ok_index = status_res.index("OK")
        except ValueError:
            raise ValueError("Expected message 'OK' from nimbie "
                            +"but did not receive message. Instead got "
                            +str(status_res))
        status = status_res[ok_index + 1]
        return status[2] == "1"
    
    # Load the next disk into the cd reader    
    def load_next_disk(self):
        open_tray()
        self.place_disk()
        close_tray()

    # Accept the currently loaded disk
    def accept_current_disk(self):
        open_tray()
        self.lift_disk()
        close_tray()
        self.accept_disk()

    # Reject the currently loaded disk
    def reject_current_disk(self):
        open_tray()
        self.lift_disk()
        close_tray()
        self.reject_disk()


if __name__ == "__main__":
    n = Nimbie()
    
