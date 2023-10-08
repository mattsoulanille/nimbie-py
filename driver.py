import usb.core
import usb.util
array = usb.util.array.array
import sys
from eject import open_tray, close_tray
from typing import List, Union, Dict, Callable, Optional
from time import sleep

# Largest incoming packet in bytes as listed in the endpoint descriptor
IN_SIZE = 64

# The array -> string decoder's error message
class NotStringError(TypeError):
    pass

# If the state of the hardware does not support
# the requested operation
class HardwareStateError(Exception):
    pass

# The tray already has a disk
class DiskInTrayError(HardwareStateError):
    pass

# The tray has no disk in it
class NoDiskInTrayError(HardwareStateError):
    pass

# No disk available in the input queue
class NoDiskError(HardwareStateError):
    pass

# The tray is closed or opened when it should be the opposite
class TrayInvalidStateError(HardwareStateError):
    pass

# An error involving the state of the dropper
# Perhaps it is missing a disk
# Perhaps you're trying to place another disk
# while the dropper is still up.
class DropperError(HardwareStateError):
    pass

class Nimbie:
    def __init__(self, open_tray_fn: Optional[Callable] = open_tray, close_tray_fn: Optional[Callable] = close_tray):
        """Detect the connected Nimbie"""

        self.open_tray_fn = open_tray_fn
        self.close_tray_fn = close_tray_fn
        
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

        
    def send_command(self, *command: int) -> str:
        """
        Send a command of up to six bytes to the Nimbie
        """
        if len(command) > 6:
            raise Exception("Too many arguments. Maximum of 6")

        message = bytearray(8)
        for i in range(len(command)):
            message[i + 2] = command[i]

        self.out_ep.write(message)
        response = self.get_response()
        return self.extract_statuscode(response)

    def get_response(self, minimum=1) -> List[str]:
        """
        Get the Nimbie's raw response to a command

        The nimbie sends several messages in response to a command.
        This function reads messages from the Nimbie until it receives
        an empty message. Since the first message is usually empty, 
        the `minimum` variable specifies a minimum number of messages
        to read.
        """
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
    def extract_statuscode(response_list: List[str]) -> str:
        """Attempt to extract the Nimbie's status code from a sequence of its messages

        The Nimbie responds to commands with an undefined number of 
        empty messages, then the message "OK", and finally its status code.
        This function extracts and returns the status code.
        """
        try:
            ok_index = response_list.index("OK")
        except ValueError:
            raise ValueError("Expected message 'OK' from nimbie "
                             +"but did not receive message. Instead got "
                             +str(response_list))

        return response_list[ok_index + 1]

    @staticmethod
    def array_to_string(array: array) -> str:
        """Attempt to parse an array of integers as a null terminated ASCII string"""
        if (len(array) == 0):
            return ""

        # Expect null termination if nonempty string
        if array[-1] != 0:
            raise NotStringError("Expected array to be null terminated but got " + str(array[-1]))
        return "".join([chr(x) for x in array][:-1])

    def read_data(self) -> array:
        """Read the next message from the Nimbie as an array of integers"""
        # Maybe have the timeout be an option instead of just 20 seconds?
        return self.in_ep.read(IN_SIZE, 20000)

    def read(self) -> Union[str, array]:
        """Attempt to read a null terminated string from the Nimbie

        Returns an array of integers if it is not null terminated
        """
        data = self.read_data()
        try:
            return self.array_to_string(data)
        except NotStringError:
            return data

    @staticmethod
    def decode_statuscode(statuscode: str) -> Union[Exception, str]:
        """Decode one of the Nimbie's status codes
        
        Returns an exception on error codes and a string on status codes.
        """
        assert statuscode[0:3] == "AT+" # The prefix for all status codes
        code = statuscode[3:] # The part that changes

        if (code == "S12"):
            return DiskInTrayError("The tray already has a disk")
        if (code == "S14"):
            return NoDiskError("No disk in disk queue")
        if (code == "S10"):
            return TrayInvalidStateError("The tray is in the "
                                         +"opposite state it should be in")
        if (code == "S03"):
            return DropperError("The dropper has an error (maybe it's "
                                +"missing a disk. Maybe you're attempting "
                                +"to place a disk on it while it's still up).")
        if (code == "S00"):
            return NoDiskInTrayError("The tray has no disk in it")
        if (code == "O"):
            return "Dropper success (lifting or dropping)"
        if (code == "S07"):
            return "Successfully placed disk on tray"

        return "Unknown status code"

    # Try the command and throw an error if we get an error code
    def try_command(self, *command: int) -> str:
        """Try the command, throwing an error if the Nimbie throws one"""
        result = self.send_command(*command)
        decoded = self.decode_statuscode(result)
        if isinstance(decoded, Exception):
            raise decoded
        return decoded
        
    def place_disk(self) -> str:
        """Place the next disk from the queue into the tray"""
        return self.try_command(0x52, 0x01)

    def lift_disk(self) -> str:
        """Lift the disk from the tray"""
        return self.try_command(0x47, 0x01)

    def accept_disk(self) -> str:
        """Drop the lifted disk into the accept pile"""
        return self.try_command(0x52, 0x02)

    def reject_disk(self) -> str:
        """Drop the lifted disk into the reject pile"""
        return self.try_command(0x52, 0x03)

    def get_state(self) -> Dict[str, bool]:
        """Gets the state of the Nimbie hardware
        
        The state is a dictionary of boolean values with 
        the following strings as keys:
            disk_available
            disk_in_open_tray
            disk_lifted
            tray_out
        """
        state_str = self.send_command(0x43)
        
        return {"disk_available": state_str[2] == "1",
                "disk_in_open_tray": state_str[4] == "1",
                "disk_lifted": state_str[5] == "1",
                "tray_out": state_str[6] == "1",
        }

    def disk_available(self) -> bool:
        """Whether or not a disk is available in the input queue"""
        return self.get_state()["disk_available"]

    def load_next_disk(self) -> None:
        """Load the next disk into the reader
        
        Ejects the tray, places the disk, and returns the tray.
        """
        self.maybe_open_tray()
        self.place_disk()
        self.maybe_close_tray()

    def accept_current_disk(self) -> None:
        """Accept the currently loaded disk
        
        Ejects the disk, picks it up, and drops it into
        the accept pile.
        """
        self.maybe_open_tray()
        self.lift_disk()
        self.maybe_close_tray()
        self.accept_disk()

    def reject_current_disk(self) -> None:
        """Reject the currently loaded disk

        Ejects the disk, picks it up, and drops it into
        the reject pile.
        """
        self.maybe_open_tray()
        self.lift_disk()
        self.maybe_close_tray()
        self.reject_disk()

    def is_tray_out(self) -> bool:
        """Whether or not the disk tray is out"""
        return self.get_state()["tray_out"]

    def is_disk_in_open_tray(self) -> bool:
        """Whether a disk in an open tray"""
        return self.get_state()["disk_in_open_tray"]

    def maybe_open_tray(self):
        if not self.is_tray_out():
            self.open_tray_fn()

    def maybe_close_tray(self):
        if self.is_tray_out():
            self.close_tray_fn()

    def map_over_disks(self, func: Callable[[], bool]) -> None:
        """Maps the function `func` over all disks in the disk queue
        
        `func` should return whether to accept or reject the current disk
        """
        # Handle if there's not already a disk in the tray
        self.maybe_open_tray()
        if not self.get_state()["disk_in_open_tray"]:
            self.load_next_disk()
        self.maybe_close_tray()

        try:
            while True:
                if func():
                    self.accept_current_disk()
                else:
                    self.reject_current_disk()
                self.load_next_disk()

        except NoDiskError:
            # No more disks means we're done
            return

    def map_over_disks_forever(self, func: Callable[[], bool]) -> None:
        """Maps `func` over disks forever, waiting for more when empty"""
        while True:
            self.map_over_disks(func)
            while not self.disk_available():
                sleep(1)
            sleep(5) # Give the user a chance to place disks

        

if __name__ == "__main__":
    n = Nimbie()
    
