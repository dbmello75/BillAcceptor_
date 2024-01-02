# Replace this line with the actual path to your host.py file
from host import Host
import sys

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
