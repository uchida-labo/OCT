import numpy as np
from scipy import interpolate
from tqdm import tqdm

class SignalProcessorHamasaki():
    """
    A class that packages various types of signal processing for OCT.
    """
    c = 2.99792458e8  # Speed of light in vacuum [m/sec].

    def __init__(self,wavelength,n,depth_max,resolution,signal_length=3):
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
        resolution : `int`
            Resolution of calculation result.
            The larger the value, the sharper the graph,but the calculation time.
        signal_length :  `float`
            Signal length.
            The calculation result always be periodic function. 
            This parameter controls the length of the cycle.
            The higher this parameter, the longer the period, but also the longer the time required for the calculation.

        """
        # Axis conversion for resampling
        self.__wl=wavelength
        self.__res=int(resolution)
        self.__depth=np.linspace(0, depth_max, self.__res)
        self.__time=2*(n*self.__depth*1e-3)/SignalProcessorHamasaki.c
        self.__freq=(SignalProcessorHamasaki.c/(self.__wl*1e9))*1e6
        self.__freq_fixed=np.linspace(np.amin(self.__freq),np.amax(self.__freq),int(len(self.__wl)*signal_length))
        self.__freq_dataset=self.__prepare_sinusoid(self.__freq_fixed)
        #initialize data container
        self.__ref=None
        self.__inc=None

    #functions for OCT
    @property
    def depth(self):
        """ Horizontal axis after FFT (depth [mm])
        """
        return self.__depth
    
    @property
    def frequency(self):
        """Frequency axis after re-sampling[THz] (Used to describe how the signal is processed.)
        """
        return self.__freq_fixed

    def __prepare_sinusoid(self, freq_fixed):
        """To speed up the calculation, this function calculates the sine wave needed for signal processing in advance.

        Parameter
        ----------
        freq_fixed : `1d-ndarray`, required
            Use equal width for each value, not the inverse of wavelength axis.
        
        Return
        ----------
        freq_dataset : `2d-ndarray`
            Calculated sine wave data set. If this array is referenced when using apply_inverse_ft function, processing can be sped up.
        """
        freq_dataset=np.zeros((len(freq_fixed),len(self.__time)))
        for i in range(len(freq_fixed)):
            freq_dataset[i]=np.sin(2*np.pi*self.__time*self.__freq_fixed[i]*1e12)
        return freq_dataset

    def resample(self, spectra):
        """ Resamples the spectra.

        Parameter
        ----------
        spectra : `1d-ndarray`, required
            Spectra sampled evenly in the wavelength space.
        Return
        -------
        `1d-ndarray`
            Spectra resampled evenly in the frequency space.
        """
        func = interpolate.interp1d(self.__freq, spectra, kind='cubic')
        return func(self.__freq_fixed)

    def set_reference(self,reference):
        """ Specify the reference spectra. This spectra will be used in later calculations.

        Parameter
        ----------
        spectra : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.
        """
        self.__ref=self.resample(reference)

    def remove_background(self,spectra):
        """Subtract reference light from interference light.
    
        Parameter
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

        Parameter
        ----------
        spectra : `1d-ndarray`, required
            spectra(After applying resampling)

        Return
        ----------
        `1d-array`
            Data after IFFT
        
        """
        result=np.zeros_like(self.__depth)
        for i in range(len(spectra)):
            result+=spectra[i]*self.__freq_dataset[i]
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
        
        Return
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
    
    def generate_bscan(self,interference,reference):
        """Generate a B-scan by calling generate_ascan function multiple times.

        Parameters
        ----------
        intereference : `2d-ndarray`, required
            Spectra of interference light only, sampled evenly in wavelength space.
         reference : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.           

        Return
        ----------
        bscan : `2d-ndarray`
            Light intensity data in the time domain(i.e. B-scan)
            The corresponding horizontal axis data(depth) can be obtained with `self.depth`.      
        """
        bscan=np.zeros((len(interference),self.__res))
        print("Generating B-scan...")
        for i in tqdm(range(len(interference))):
            bscan[i]=self.generate_ascan(interference[i], reference)
        return bscan
    
    def generate_cscan(self, interference,reference):
        """Generate a C-scan by calling generate_ascan function multiple times.

        Parameters
        ----------
        intereference : `3d-ndarray`, required
            Spectra of interference light only, sampled evenly in wavelength space.
         reference : `1d-ndarray`, required
            Spectra of reference light only, sampled evenly in wavelength space.           

        Return
        ----------
        bscan : `3d-ndarray`
            Light intensity data in the time domain(i.e. C-scan)
            The corresponding horizontal axis data(depth) can be obtained with `self.depth`.      
        """
        cscan=np.zeros((len(interference),len(interference[0]),self.__res))
        print('Generating C-scan...')
        for i in tqdm(range(len(interference))):
            for j in range(len(interference[i])):
                cscan[i][j]=self.generate_ascan(interference[i][j],reference)
        return cscan

    #functions for Absorbance calculation
    def set_incidence(self, incidence):
        """Specify the incidence light spectra.This spectra will be used for absorbance calculation later.

        Parameter
        ----------
        incidence : `1d-ndarray`, required
            Spectra of incident light only, sampled evenly in wavelength space.
        """
        self.__inc=incidence
    
    def calculate_absorbance(self, reflection ,incidence):
        """Calculate tranmittance based on the incident and reflected light.
        Parameter
        ----------
        reflection : `1d-ndarray`, required
            Spectrum of the light source used to measure absorbance

        Return
        ----------
        absorbance : `1d-ndarray`
            calculated absorbance data 
        """
        if self.__inc is None:
            self.set_incidence(incidence)
        
        #calculation
        with np.errstate(divide='ignore',invalid='ignore'):
            absorbance=np.log10(reflection/self.__inc)*(-1)
        
        #replacement (np.inf -> np.nan) for graph drawing
        for i in range(len(absorbance)):
            if np.isinf(absorbance[i]):
                absorbance[i]=np.nan
        return absorbance    
    
    def calculate_absorbance_2d(self, reflection):
        """Generate a absorbance distribution map by calling calculate_absorbance function multiple times.

        Parameter
        ----------
        reflection : `2d-ndarray`, required
            Spectrum of the light source used to measure absorbance

        Return 
        ----------
        absorbance_2d : `2d-ndarray`
            calculated absorbance data
        """
        absorbance_2d=np.zeros((len(reflection),len(self.__inc)))
        print('Generating absorbance distribution map(2D)...')
        for i in tqdm(range((len(reflection)))):
            absorbance_2d[i]=self.calculate_absorbance(reflection[i])
        return absorbance_2d
    
    @staticmethod
    def find_index(wavelength,wl_range):
        """
        Finds the index of an array of wavelengths from a specified range

        Parameters
        ----------
        wavelength : `1d-ndarray`, required
            avelength axis[nm] The given spectra must be sampled evenly in wavelength space.
        wavelength_range : `list`
            Wavelength range [nm] of the spectra to be found.
            Specify the lower limit in the first element and the upper limit in the next element.

        Returns
        ----------
        start : `int`
            bottom of index
        end : `int`
            top of index   
        """
        #find bottom of index
        for i in range(len(wavelength)):
           if wavelength[i]>=wl_range[0]:
                start=i
                break

        #find top of index
        for i in range(len(wavelength)):
            if wavelength[i]>=wl_range[1]:
                end=i
                break
        return start, end
    
    @staticmethod
    def analyze_cscan(cscan, target:float, mode:str ,y_max:float=None, depth=None):
        """Generates a 2D-image data at a specified width, height and depth in a plane parallel or perpendicular to the optical axis direction.
        
        Parameters
        ----------
        cscan : `3d-ndarray`, required
            Data calculated by generate_cscan function
        target : `float` ,required
            Width/Height/Depth to generate tomographical view[mm].
        mode : `str`, required
            'xd' : generate X(height) versus depth data
            'yd' : generate Y(width)  versus depth data
            'xy' : generate X-Y data
            other : not supported
        y_max : `float`, required when mode is 'xd' or 'yd'
            Vertical/Horizontal scaninng distance[mm]
        depth : `1d-ndarray`, required when mode is 'xy'
            The corresponding horizontal axis data to C-scan.
    
        Return
        ----------
        tmg_view : `2d-ndarray`
            Generated tomographical view of C-csan.
        """
        result = None
        if mode == 'xd' or mode == 'yd':
            if y_max is None:
                print('Error : y_max is required when generate (X or Y) vs Depth data.')
            else:
                #find index to generate tomographical view
                if y_max < target or 0 > target:
                    print("Error:Target is not included in y-axis array. Returned y_axis[0]")
                    index=0
                else:
                    if mode == 'xd':
                        y_axis=np.linspace(0,y_max,len(cscan))
                    else:
                        y_axis = np.linspace(0,y_max,len(cscan[0]))

                for i in range(len(y_axis)):
                    if y_axis[i]>=target:
                        index=i
                        break
                        
                # mode = 'xd' to generage width versus depth graph
                if mode == 'xd':
                    result=cscan[index]

                # mode = 'yd' to generage height versus depth graph
                else:
                    result=np.zeros((len(cscan),len(cscan[0][0])))
                    for i in tqdm(range(len(cscan))):
                        result[i]=cscan[i][index]

        elif mode =='xy':
            if depth is None:
                print("Error:depth is required when generate X vs Y data.")
            else:
                if np.amax(depth)<target or np.amin(depth)>target:
                    print("Error:Target is not included in depth array. Returned depth[0].")
                    index = 0
                for i in range(len(depth)):
                    if depth[i]>=target:
                        index=i
                        break
                result=np.zeros((len(cscan),len(cscan[0])))
                for i in range(len(cscan)):
                    for j in range(len(cscan[i])):
                        result[i][j]=cscan[i][j][index]           
        return result
            
def calculate_absorbance(reflection,incidence):
    """Calculate tranmittance based on the incident and transmitted light.
    Parameters
    ----------
    reflection : `1d-ndarray`, required
        Spectrum of light reflected from the sample
    incidence : `1d-ndarray`, required
        Spectrum of the light source used to measure absorbance
        
    Return
    ----------
    absorbance : `1d-ndarray`
        calculated absorbance data 
    """
    with np.errstate(divide='ignore',invalid='ignore'):
        absorbance=np.log10(reflection/incidence)*(-1)
    for i in range(len(absorbance)):
        if np.isinf(absorbance[i]):
            absorbance[i]=np.nan
    return absorbance

def calculate_absorbance_2d(reflection,incidence):
    """Generate a absorbance distribution map by calling calculate_absorbance function multiple times.
    Parameter
    ----------
    reflection : `2d-ndarray`, required
        Spectrum of the light source used to measure absorbance
    Return 
    ----------
    absorbance_2d : `2d-ndarray`
        calculated absorbance data
    """
    absorbance_2d=np.zeros((len(reflection),len(incidence)))
    print('Generating absorbance distribution map(2D)...')
    for i in tqdm(range((len(reflection)))):
        absorbance_2d[i]=calculate_absorbance(reflection[i],incidence)
    return absorbance_2d

#changed 2022.1115
def calculate_reflectance(reflection,incidence):
    """Calculate reflectance based on the incident and reflected light.
    Parameters
    ----------
    reflection  : `1d-ndarray`, required
        Spectrum of the light source used to measure reflectance
    incidence   : `1d-ndarray`, required
        Spectrum of light passing through the sample
    
    Return
    ----------
    reflectance : `1d-ndarray`
        calculated reflectance data 
    """
    with np.errstate(divide='ignore',invalid='ignore'):
        reflectance=reflection/incidence
    for i in range(len(reflectance)):
        if np.isinf(reflectance[i]):
            reflectance[i]=np.nan
    return reflectance

if __name__=="__main__":
    import matplotlib.pyplot as plt
    import data_handler as dh

    st = 775
    ed = 890

    #load data
    data=dh.load_spectra('data/data.csv',[st,ed])
    
    #call class
    sp=SignalProcessorHamasaki(wavelength=data['wavelength'], n=1.5, depth_max=0.2, resolution=2500)

    #generate A-scan
    ascan=sp.generate_ascan(data['spectra'],data['reference'])

    #graph drawing
    plt.rcParams["figure.figsize"] = (9, 6)
    plt.tick_params(direction='in')
    plt.plot(sp.depth*1e3,ascan)
    plt.xlabel('Depth [μm]',fontsize=17)
    plt.ylabel('Light intensity [arb. unit]',fontsize=17)
    plt.ylim(bottom=0)
    plt.xlim(0, 200)
    plt.xticks([50, 100, 150, 200],fontsize=15)
    plt.yticks(fontsize=14)
    plt.xticks(fontsize=14)
    plt.show()