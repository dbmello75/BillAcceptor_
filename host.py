from threading import Thread
import serial
import time
import binascii
import csv  # Added import for CSV handling

### Globals ###
# Change this value to modify polling rate. Currently 100 ms
POLL_RATE = 0.1

# pylint: disable-msg=R0902

class Host(object):
    """
    An RS-232 master interface. A master operates with an RS-232
    slave for the purpose of accepting money in exchange for goods or services.
    """

    state_dict = {
        1: "Idling ", 2: "Accepting ", 4: "Escrowed ", 8: "Stacking ",
        16: "Stacked ", 32: "Returning", 64: "Returned",
        17: "Stacked Idling ", 65: "Returned Idling "
    }
    event_dict = {0: "", 1: "Cheated ", 2: "Rejected ", 4: "Jammed ", 8: "Full "}

    def __init__(self):
        # Set to False to kill
        self.running = True
        self.bill_count = bytearray([0, 0, 0, 0, 0, 0, 0, 0])
        self.ack = 0
        self.credit = 0
        self.last_state = ''
        self.escrowed = False
        self.verbose = False
        self.barcode_data = ""  # New variable to store barcode data

        # Background worker thread
        self._serial_thread = None

    def start(self, portname):
        """
        Start Host in a non-daemon thread

        Args:
            portname -- string name of the port to open and listen on

        Returns:
            None
        """
        self._serial_thread = Thread(target=self._serial_runner, args=(portname,))
        # Per https://docs.python.org/2/library/threading.html#thread-objects
        # 16.2.1: Daemon threads are abruptly stopped, set to false for proper
        # release of resources (i.e. our comm port)
        self._serial_thread.daemon = False
        self._serial_thread.start()

    def stop(self):
        """
        Blocks until Host can safely be stopped

        Args:
            None

        Returns:
            None
        """
        self.running = False
        self._serial_thread.join()

    def set_barcode_data(self, data):
        """Set barcode data"""
        self.barcode_data = data

    def parse_cmd(self, cmd):
        """
        Applies the given command to modify the state/event of
        this Host

        Args:
            cmd -- string arg

        Returns:
            Int -- 0 if okay, 1 to exit, 2 to quit
        """
        if cmd == 'Q':
            return 1
        if cmd == '?' or cmd == 'H':
            return 2

        if cmd == 'V':
            self.verbose = not self.verbose
        elif cmd == 'B':
            barcode = input("Enter Barcode: ")
            self.set_barcode_data(barcode)

        return 0

    def _serial_runner(self, portname):
        """
        Polls and interprets message from slave acceptor over serial port
        using global poll rate

        Args:
            portname -- string portname to open

        Returns:
            None
        """

        ser = serial.Serial(
            port=portname,
            baudrate=9600,
            bytesize=serial.SEVENBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE
        )

        while ser.isOpen() and self.running:
            # basic message   0      1     2      3      4      5     6         7
            #               start, len,  ack, bills,escrow,resv'd,  end, checksum
            msg = bytearray([0x02, 0x08, 0x10, 0x7F,  0x00,  0x00, 0x03, 0x00])

            msg[2] = 0x10 | self.ack
            self.ack ^= 1

            # If escrow, stack the note
            if self.escrowed:
                msg[4] |= 0x20

            # Set the checksum
            for byte in range(1, 6):
                msg[7] ^= msg[byte]

            ser.write(msg)
            time.sleep(0.1)

            out = ''
            while ser.inWaiting() > 0:
                # out += ser.read(1)
                out += ser.read(1).decode('utf-8')
            if out == '':
                continue

            # With the exception of Stacked and Returned, only we can
            # only be in one state at once
            try:
                status = Host.state_dict[ord(out[3])]
            except KeyError:
                status = ''
                print("unknown state dic key {:d}".format(ord(out[3])))

            self.escrowed = ord(out[3]) & 4

            # If there is no match, we get an empty string
            try:
                status += Host.event_dict[ord(out[4]) & 1]
                status += Host.event_dict[ord(out[4]) & 2]
                status += Host.event_dict[ord(out[4]) & 4]
                status += Host.event_dict[ord(out[4]) & 8]
            except KeyError:
                print("unknown state dic key {:d}".format(ord(out[4])))

            if ord(out[4]) & 0x10 != 0x10:
                status += " CASSETTE MISSING"

            # Only update the status if it has changed
            if self.last_state != status:
                print('Acceptor status:', status)
                self.last_state = status

            if self.verbose:
                print(", ".join("0x{:02x}".format(ord(c)) for c in out))

            # Print credit(s)
            credit = (ord(out[5]) & 0x38) >> 3

            if credit != 0:
                if ord(out[3]) & 0x10:
                    print("Bill credited: Bill#", credit)
                    self.bill_count[credit] += 1
                    print("Acceptor now holds: {:s}".format(
                        binascii.hexlify(self.bill_count).decode('utf-8')))

                    # Simulate saving data to CSV (modify this part based on your CSV structure)
                    self.save_to_csv()

            time.sleep(POLL_RATE)

        print("port closed")
        ser.close()

    def save_to_csv(self):
        """Simulate saving data to CSV (modify based on your CSV structure)"""
        with open('output.csv', 'a', newline='') as csvfile:
            fieldnames = ['Bag#', 'Total1S', 'TotalLarge']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Simulating data, modify this part based on your requirements
            bag_number = '00403064'
            total_1s = 45
            total_large = 45

            writer.writerow({'Bag#': bag_number, 'Total1S': total_1s, 'TotalLarge': total_large})


# Main Routine
def main(usb_port):
    """
    Starts the Master RS-232 service
    """

    cmd_table = '''

    H or ? to show Help
    Q or CTRL+C to Quit
    B to simulate Barcode scanning
    V - Enable Verbose mode
    '''

    print("Starting RS-232 Master on USB port {:s}".format(usb_port))
    master = Host()
    master.start(usb_port)

    # Loop until we are to exit
    try:
        print(cmd_table)
        while master.running:

            cmd = input()
            result = master.parse_cmd(cmd)
            if result == 0:
                pass
            elif result == 1:
                master.stop()
            elif result == 2:
                print(cmd_table)

    except KeyboardInterrupt:
        master.running = False

    print('\n\nGoodbye!')
    print('USB port {:s} closed'.format(usb_port))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_name.py <USB_port>")
        sys.exit(1)

    usb_port = sys.argv[1]
    main(usb_port)
