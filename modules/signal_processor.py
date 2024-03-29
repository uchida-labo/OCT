import numpy as np
from scipy import special, interpolate

class SignalProcessor():
    """ Class that summarizes the various types of signal processing for OCT.
    """
    c = 2.99792458e8  # Speed of light in a vacuum [m/sec].

    def __init__(self, wavelength, n, alpha=1.5) -> None:
        """ Initialization and preprocessing of parameters.

        Parameters
        ----------
        wavelength : `1d-ndarray`, required
            Wavelength axis [nm]. The given spectra must be sampled evenly in wavelength space.
        n : `float`, required
            Refractive index of the sample.
        alpha : `float`
            Design factor of Kaiser window.
        """
        # Data containers
        self.__ref_fix = None

        # Axis conversion for resampling
        self.__wl = wavelength
        self.__ns = len(self.__wl)  # Number of samples after resampling
        i = np.arange(self.__ns)
        s = (self.__ns-1)/(self.__wl.max()-self.__wl.min()) * (1/(1/self.__wl.max()+i/(self.__ns-1)*(1/self.__wl.min()-1/self.__wl.max())) - self.__wl.min())
        self.__wl_fix = self.__wl.min() + s*(self.__wl.max()-self.__wl.min())/(self.__ns-1)  # Fixed Wavelength
        
        # Generating window functions
        x = np.linspace(0, self.__ns, self.__ns)
        self.__window = special.iv(0, np.pi*alpha*np.sqrt(1-(2*x/len(x)-1)**2)) / special.iv(0, np.pi*alpha)  # Kaiser window
        self.__window = np.reshape(self.__window, [self.__window.shape[0],1])

        # Axis conversion for FFT
        freq = SignalProcessor.c / (self.__wl_fix*1e-9*n)
        fs = 2*freq.max()  # Nyquist frequency
        self.__nf = self.__ns * 2 # Number of samples after IFFT
        t = self.__nf / fs  # Maximum value of time axis after IFFT
        self.__depth = np.linspace(0, SignalProcessor.c*t/2, self.__ns)

    @property
    def depth(self) -> np.ndarray:
        """ Horizontal axis after FFT (depth [m])
        """
        return self.__depth

    def resample(self, spectra, kind='cubic') -> np.ndarray:
        """ Resamples the spectra.

        Parameters
        ----------
        spectra : `ndarray`, required
            Spectra sampled evenly in the wavelength space.
            For data in 2 or more dimensions, use axis0 as the wavelength axis.
        kind : `str`
            Data interpolation methods. For more information, see
            https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.interp1d.html

        Returns
        -------
        `ndarray`
            Spectra resampled evenly in the frequency space.
        """
        resampled = np.zeros_like(spectra)
        if spectra.ndim <= 1:
            func = interpolate.interp1d(self.__wl, spectra, kind)
            resampled = np.reshape(func(self.__wl_fix), [spectra.shape[0],1])
        elif spectra.ndim == 2:
            for i in range(spectra.shape[1]):
                func = interpolate.interp1d(self.__wl, spectra[:,i], kind)
                resampled[:,i] = func(self.__wl_fix)
        elif spectra.ndim == 3:
            for j in range(spectra.shape[2]):
                for i in range(spectra.shape[1]):
                    func = interpolate.interp1d(self.__wl, spectra[:,i,j], kind)
                    resampled[:,i,j] = func(self.__wl_fix)
        return self.normalize(resampled, axis=0)

    def remove_background(self, spectra) -> np.ndarray:
        """ Removes the reference spectra from the interference spectra.

        Parameters
        ----------
        spectra : `ndarray`, required
            Spectra. Normally, specify the interference spectra after resampling.
            For data in 2 or more dimensions, use axis0 as the wavelength axis.

        Returns
        -------
        `ndarray`
            Spectra after reference spectra removal.
        """
        return spectra - self.__ref_fix
    
    def apply_window(self, spectra) -> np.ndarray:
        """ Multiply the spectra by the window function.

        Parameters
        ----------
        spectra : `ndarray`, required
            Spectra after removing the background.

        Returns
        -------
        `ndarray`
            Spectra after applying the window function.
        """
        return spectra*self.__window
    
    def apply_ifft(self, spectra) -> np.ndarray:
        """ Apply IFFT to the spectra and convert it to time domain data (i.e. A-scan).

        Parameters
        ----------
        spectra : `ndarray`, required
            Spectra after applying the window function.

        Returns
        -------
        `ndarray`
            Data after IFFT.
        """
        magnitude = np.abs(np.fft.ifft(spectra, n=self.__nf, axis=0))
        return magnitude[:self.__ns]
    
    def set_reference(self, spectra) -> np.ndarray:
        """ Specify the reference spectra. This spectra will be used in later calculations.

        Parameters
        ----------
        spectra : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.
        
        Returns
        -------
        `1d-ndarray`
            Reference spectra after resampling.
        """
        self.__ref_fix = self.resample(spectra)
        return self.__ref_fix
    
    @staticmethod
    def normalize(array, axis=None) -> np.ndarray:
        """ Min-Max Normalization.

        Parameters
        ----------
        x : `ndarray`, required
            Array to be normalized.
        
        axis : `int`
            If specified, normalization is performed according to the maximum and minimum values along this axis.
            Otherwise, normalization is performed by the maximum and minimum values of the entire array.
        
        Returns
        -------
        `ndarray`
            An array normalized between a minimum value of 0 and a maximum value of 1.
        """
        min = array.min(axis=axis, keepdims=True)
        max = array.max(axis=axis, keepdims=True)
        return (array-min)/(max-min)
    
    @staticmethod
    def moving_average(array, filter_size):
        """ Moving average filter with convolutional integration
        """
        v = np.ones(filter_size)/filter_size
        return np.convolve(array, v, mode='same')
    
    @staticmethod
    def median(array, filter_size):
        """ 1-dimensional median filter
        """
        w = len(array)
        idx = np.fromfunction(lambda i, j: i + j, (filter_size, w), dtype=np.int) - filter_size // 2
        idx[idx < 0] = 0
        idx[idx > w - 1] = w - 1
        return np.median(array[idx], axis=0)
    
    @staticmethod
    def low_pass(array, cutoff):
        """ Digital low pass filter
        """
        n = len(array)
        fft = np.fft.fft(array)
        fft = fft/(n/2)
        fft[0] = fft[0]/2
        fft[(np.arange(n)>cutoff)] = 0 + 0j
        return np.real(np.fft.ifft(fft)*n)
    
    def generate_ascan(self, interference, reference) -> np.ndarray:
        """ Performs a series of signal processing in one step.

        Parameters
        ----------
        interference : `ndarray`, required
            Spectra of interference light only, sampled evenly in wavelength space.
        reference : `ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.

        Returns
        -------
        ascan : `ndarray`
            Light intensity data in the time domain (i.e. A-scan).
            The corresponding horizontal axis data (depth) can be obtained with `self.depth`.
        """
        if self.__ref_fix is None:
            self.set_reference(reference)
        itf = self.resample(interference)
        rmv = self.remove_background(itf)
        wnd = self.apply_window(rmv)
        ascan = self.apply_ifft(wnd)
        if interference.ndim <= 1:
            ascan = ascan.reshape([ascan.size,])
        return ascan


class SignalProcessorHamasaki():
    """
    A class that packages various types of signal processing for OCT.
    """
    c = 2.99792458e8  # Speed of light in vacuum [m/sec].

    def __init__(self,wavelength,n,depth_max,signal_length):
        """
        Initialization and preprocessing of parameters.

        Parameters
        ----------
        wavelength : `1d-ndarray`, required
            Wavelength axis[nm] The given spectra must be sampled evenly in wavelength space.
        n : `float`, required
            Refractive index of the sample .
        xmax : 'float', required
            maximum value of depth axis[mm]
        signal_length :  `float`, required
            Signal length.(3 is recomended)
            The calculation result always be periodic function. 
            This parameter controls the length of the cycle.
            The higher this parameter, the longer the period, but also the longer the time required for the calculation.

        """
        # Axis conversion for resampling
        self.__wl=wavelength
        self.__depth=np.linspace(0, depth_max, int(200))
        self.__time=2*(n*self.__depth*1e-3)/SignalProcessorHamasaki.c
        self.__freq=(SignalProcessorHamasaki.c/(self.__wl*1e9))*1e6
        self.__freq_fixed=np.linspace(np.amin(self.__freq),np.amax(self.__freq),int(len(self.__wl)*signal_length))
        #initialize data container
        self.__ref=None

    @property
    def depth(self):
        """ Horizontal axis after FFT (depth [m])
        """
        return self.__depth*1e-3

    def resample(self, spectra):
        """ Resamples the spectra.

        Parameters
        ----------
        spectra : `1d-ndarray`, required
            Spectra sampled evenly in the wavelength space.

        Returns
        -------
        `1d-ndarray`
            Spectra resampled evenly in the frequency space.
        """
        func = interpolate.interp1d(self.__freq, spectra, kind='cubic')
        return func(self.__freq_fixed)

    def set_reference(self,reference):
        """ Specify the reference spectra. This spectra will be used in later calculations.

        Parameters
        ----------
        spectra : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.
        """
        self.__ref=self.resample(reference)

    def remove_background(self,spectra):
        """Subtract reference light from interference light.
    
        Parameters
        ----------
        sp : `1d-ndarray`, required
            Spectra. Normally, specify the interference spectra after resampling.

        
        Return
        -------
        `1d-ndarray`
            interference light removed background[arb. unit]
        """
        return spectra-np.multiply(self.__ref,(np.amax(spectra)/np.amax(self.__ref)))

    def apply_inverse_ft(self,spectra):
        """Apply inverse ft to the spectra and convert it to distance data

        Parameters
        ----------
        sp : `1d-ndarray`, required
            spectra(After applying resampling)

        Returns
        ----------
        `1d-array`
            Data after IFFT
        
        """
        for  i in range(len(self.__freq_fixed)):
            if i==0:
                result=spectra[i]*np.sin(2*np.pi*self.__time*self.__freq_fixed[i]*1e12)
            else:
                result+=spectra[i]*np.sin(2*np.pi*self.__time*self.__freq_fixed[i]*1e12)
        result/=np.amax(result)
        return abs(result)

    def generate_ascan(self,interference,reference):
        """ Performs a series of signal processing in one step.

        Parameters
        ----------
        interference : `1d-ndarray`, required
            Spectra of interference light only, sampled evenly in wavelength space.
        reference : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.

        Returns
        -------
        ascan : `1d-ndarray`
            Light intensity data in the time domain (i.e. A-scan).
            The corresponding horizontal axis data (depth) can be obtained with `self.depth`.
        """
        if self.__ref is None:
            self.set_reference(reference)
        itf=self.resample(interference)
        rmv=self.remove_background(itf)
        ascan=self.apply_inverse_ft(rmv)
        return ascan


if __name__ == "__main__":

    import data_handler as dh

    # Data loading
    data = dh.load_spectra('data/data.csv', wavelength_range=[770,910])
    # dataset = dh.load_dataset('PET', data['wavelength'])

    # Signal processing
    sp = SignalProcessor(data['wavelength'], 1.0)
    ascan = sp.generate_ascan(data['spectra'], data['reference'])

    # Show Graph
    dh.draw_graph(format='ascan', y=[ascan,], x=[sp.depth*1e6], name=['Numpy IFFT',])
    # dh.draw_graph(format='bscan', x=sp.depth*1e6, y=np.arange(300), z=ascan.T, zmax=0.004)


# if __name__=="__main__":
#     import matplotlib.pyplot as plt

#     st = 762
#     ed = 953
#     name=['wl','bg','sp']
#     data=pd.read_csv('data/210924_0.csv', header=3, index_col=0,names=name)
#     wl=data.loc[st:ed,'wl'] # Wavelength
#     bg=data.loc[st:ed,'bg'] # Background spectra
#     sp=data.loc[st:ed,'sp'] # Sample spectra

#     SigPro=SignalProcessorHamasaki(wl,1.4,0.2,3)
#     depth,result=SigPro.generate_ascan(sp,bg)
#     plt.plot(depth,result)
#     plt.xlabel('depth[mm]',fontsize=17)
#     plt.ylabel('intensity[arb. unit]',fontsize=17)
#     plt.show()
