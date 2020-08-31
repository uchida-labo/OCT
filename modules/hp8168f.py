import time
import pyvisa


class HP8168F:

    def __init__(self, gpib_id: str, pin='8168'):
        """ Initiates and unlocks communication with the device.

        Parameters
        ----------
        gpib_id : `str`, required
            GPIB address of the device.

        pin : `str`, optional
            Four-character PIN to unlock the device. Default is 8168.
        """
        self.__rm = pyvisa.ResourceManager()
        # print(self.__rm.list_resources())  # Get a list of GPIB addresses.
        self.__dev = self.__rm.open_resource(gpib_id)
        self.__dev.read_termination = '\n'  # Set the delimiter
        self.__dev.write_termination = '\n'
        self.__dev.timeout = None
        print(self.__dev.query('*IDN?'))  # Identify the device.
        # print(self.__dev.query('*TST?'))  # Run a self-test.
        self.__dev.write(':LOCK OFF,{}'.format(pin))
        self.__dev.write(':POW:UNIT W')  # Set the unit of power to Watt.
    
    def output(self, wavelength: float, power: int):
        """ Output laser.
        
        Parameters
        ----------
        wavelength : `float`, required
            Laser wavelength [nm]. It can be set between 1475 ~ 1580nm.

        power : `int`, required
            Laser power intensity [μW]. It can be set between 10 ~ 450μW.
        """
        self.__dev.write(':WAVE {:.3f}NM'.format(wavelength))
        self.__dev.write(':POW {}UW'.format(power))
        self.__dev.write(':OUTP ON')

    def stop(self):
        """ Stop the laser output.
        """
        self.__dev.write(':OUTP OFF')
    
    def read_status(self):
        """ Reads the status of the device.

        Returns
        -------
        `dict` Name and data pairs.

            {
                'output'    : bool, State of laser output.
                'wavelength': float, Laser wavelength [nm].
                'power'     : float, Laser power intensity [μW].
            }
        """
        status = {}
        if self.__dev.query(':OUTP?') == '+1':
            status['output'] = True
        else:
            status['output'] = False
        status['wavelength'] = float(self.__dev.query(':WAVE?')) * 1e9
        status['power'] = float(self.__dev.query(':POW?')) * 1e6
        return status


if __name__ == "__main__":

    laser = HP8168F(gpib_id='GPIB0::24::INSTR', pin=0000)
    print(laser.read_status())