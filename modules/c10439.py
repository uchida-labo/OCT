import time
import atexit
import numpy as np
import nidaqmx

class C10439_11:
    """ Class to control photodetector (C10439-11) by NIDAQ devices.
    """

    def __init__(self, ai_channels: str):
        """ Initiates and unlocks communication with the device.

        Parameters
        ----------
        ai_channels : `str`, required
            The port on the DAQ device where the photo detector is connected.
        """
        self.__task = nidaqmx.Task()
        self.__task.ai_channels.add_ai_voltage_chan(ai_channels)
        self.__task.start()
        # Register the exit process
        atexit.register(self.stop_measuring)
        print("C10439-11 is ready.")
    
    def read_voltage(self, samples=1):
        """ Reads the output voltage of a photodetector.

        Parameters
        ----------
        samples : `int`
            Number of data to be acquired.

        Returns
        -------
        data : `2d-ndarray`
            Line 0: Time [s] from start of measurement.
            Line 1: Output voltage [V] of photodetector.
        """
        if samples <= 1:
            return self.__task.read()
        data = np.zeros((2,samples))
        start_time = time.time()
        for i in range(samples):
            data[0,i] = time.time() - start_time
            data[1,i] = self.__task.read()
        return data
    
    def stop_measuring(self):
        """ Stop the measurement and release the device.
        """
        self.__task.stop()
        self.__task.close()


if __name__ == "__main__":

    import matplotlib.pyplot as plt

    data = np.zeros((2,100))  # photodetector output (time, voltage)

    # Initialize DAQMX(A/D convertor) tasks.
    pd = C10439_11(ai_channels="Dev1/ai2")

    # Initialize graph.
    fig, ax = plt.subplots(1, 1)
    ax.set_ylim((0, 0.5))
    ax.set_title("photodetector output")
    ax.set_xlabel("time [sec]")
    ax.set_ylabel("voltage [V]")
    graph, = ax.plot(data[0], data[1])

    start = time.time()
    while True:
        # Measure
        data[0,0] = time.time() - start
        data[1,0] = pd.read_voltage()
        # plot
        data = np.roll(data, -1, axis=1)
        graph.set_data(data[0], data[1])
        ax.set_xlim((data[0].min(), data[0].max()))
        ax.set_ylim((0, 2*data[1].max()))
        plt.pause(0.0001)
