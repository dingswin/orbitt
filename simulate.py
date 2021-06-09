#!/usr/bin/env python
"""
sterne.simulate_samples.py is written in python3 by Hao Ding.
The main code to run is simulate().
"""
import bilby, inspect
from astropy.time import Time
import numpy as np
import astropy.units as u
from astropy import constants
import os, sys
import howfun
from astropy.table import Table
from model import reflex_motion
from model.positions import positions
def simulate(refepoch, initsfile, pmparin, parfile, *args, **kwargs):
    """
    Input parameters
    ----------------
    refepoch : float
        Reference epoch (MJD).
    initsfile : str
        A file ending with '.inits' that contains priors of parameters to fit. initsfile\
        should be pre-made. It can be made with generate_initsfile(). Priors in initsfile\
        need to be updated before running simulate().
    pmparin : str
        A file ending with '.pmpar.in' which contains observed position info.
    parfile : str
        A parfile ending with '.par' which contains orbital info for a pulsar binary system.
        parfiles should be pre-made. 
        1) Each parfile can be made with 'psrcat -e PULSARNAME > PARFILENAME',\
            using the PSRCAT catalog. Om_asc and incl in parfiles are so far unused.\
            The timing parameters offered in parfiles should be updated before use.
        2) Only when a parfile is provided for a pmparin will reflex_motion be provoked to 
            estimate related position offset. In case where reflex_motion is not required,
            please provide '' for parfile. By doing so, reflex_motion will be turned off,\
            even when the correspoinding shares indice are >=0.
    args : str(s)
        1) to provide extra pmparin files and parfiles.
        2) the order of args should be either pmparin1, parfile1, pmparin2, parfile2,....
        3) an example for two pulsars in a globular cluster: 
        4) an arg both containing '.pmpar.in' and ending with '.par' should be avoided. 
    kwargs : key=value
        1) shares : 2-D array 
            Used to assign shared parameters to fit and which paramters to not fit.\
            The size of shares is 7*N, 7 refers to the 7 parameters ('dec','incl',\
            'mu_a','mu_d','Om_asc','px','ra' in alphabetic order); N refers to the number\
            of pmparins. As an example, for four pmparins, shares can be\
            [[0,1,2,2],[0,0,1,1],[0,0,1,1],[0,0,1,1],[0,0,1,1],[0,0,0,0],[0,1,2,3]]. Same\
            numbers in the same row shares the same parallax (e.g. 'px' is shared by all\
            pmparins). Furthermore, if shares[i][j]<0, it means the inference for\
            parameter[i] with pmparins[j] is turned off. This turn-off function is not so\
            useful now, but may be helpful in future.
            Default : [list(range(N)),[0]*N,[0]*N,[0]*N,[0]*N,[0]*N,list(range(N))].
        2) iterations : float
            'iterations' that will be passed to bilby.run_sampler().
        3) nwalkers : float
            'nwalkers' that will be passed to bilby.run_sampler().

    ** Examples ** :
        1) For two pulsars in a globular cluster:
            simulate(57444,'a.inits','p1.pmpar.in','','p2.pmpar.in','p2.par',shares=[[0,1],[-1,0],\
                [0,1], [0,1],[-1,0],[0,0],[0,1]])
        2) For a pulsar with two in-beam calibrators:
            simulate(57444,'a.inits','i1.pmpar.in','p.par','i2.pmpar.in','p.par',\
                shares=[[0,1],[0,0],[0,0],[0,0],[0,0],[0,0],[0,1]])
        3) For two pulsars in a globular cluster sharing an in-beam calibrator:
            simulate(57444,'a.inits','i1p1.pmpar.in', '', 'i2p1.pmpar.in','', 'i1p2.pmpar.in',\
                'p2.par','i2p2.pmpar.in','p2.par',shares=[[1,2,3,4],[0,0,1,1],[1,1,2,2],\
                [1,1,2,2],[0,0,1,1],[1,1,1,1],[1,2,3,4]])
    """
    ##############################################################
    ############ parse args to get pmparins, parfiles ############
    ##############################################################
    if not os.path.exists(initsfile):
        print('%s does not exist; aborting' % initsfile)
        sys.exit()
    args = list(args)
    args.reverse()
    args.append(parfile)
    args.append(pmparin)
    args.reverse() #put the major pmparin at first
    pmparins, parfiles = [], []
    for arg in args:
        if ('.pmpar.in' in arg) and arg.endswith('.par'):
            print('arg does not follow naming convention,\
                please follow the docstring! Aborting.')
            sys.exit()
        elif '.pmpar.in' in arg:
            pmparins.append(arg)
        elif arg.endswith('.par') or arg=='':
            parfiles.append(arg)
    NoP = len(pmparins)
    if NoP != len(parfiles):
        print('Unequal number of parfiles provided for pmparins.\
            See the docstring for more info. Aborting now.')
        sys.exit()
    try:
        shares = kwargs['shares']
    except KeyError:
        shares = [list(range(NoP)), [0]*NoP, [0]*NoP, [0]*NoP, [0]*NoP,\
            [0]*NoP, list(range(NoP))]
    
    print(pmparins, parfiles, initsfile, shares)
    ##############################################################
    #################  get two list_of_dict ######################
    ##############################################################
    list_of_dict_timing = []
    for parfile in parfiles:
        if parfile != '':
            dict_of_timing_parameters = reflex_motion.read_parfile(parfile)
        else:
            dict_of_timing_parameters = {}
        list_of_dict_timing.append(dict_of_timing_parameters)
    print(list_of_dict_timing)

    list_of_dict_VLBI = []
    for pmparin in pmparins:
        t = readpmparin(pmparin)
        radecs = np.concatenate([t['RA'], t['DEC']])
        errs = np.concatenate([t['errRA'], t['errDEC']])
        epochs = np.array(t['epoch'])
        dictionary = {}
        dictionary['epochs'] = epochs
        dictionary['radecs'] = radecs
        dictionary['errs'] = errs
        list_of_dict_VLBI.append(dictionary)
    print(list_of_dict_VLBI)
    
    ##############################################################
    ###################### run simulations #######################
    ##############################################################
    likelihood = Gaussianlikelihood(refepoch, list_of_dict_timing, list_of_dict_VLBI,\
        shares, positions)
    #initsfile = pmparins[0].replace('pmpar.in', 'inits')
    #if not os.path.exists(initsfile):
    #    generate_initsfile(pmparin, refepoch)
    #generate_initsfile(refepoch, pmparins, parfiles, shares, 20)
    limits = read_inits(initsfile)
    print(limits)
    priors = {}
    for parameter in limits.keys():
        priors[parameter] = bilby.core.prior.Uniform(minimum=limits[parameter][0],\
            maximum=limits[parameter][1], name=parameter, latex_label=parameter)
    try:
        iterations = kwargs['iterations']
    except KeyError:
        iterations = 100
    try:
        nwalkers = kwargs['nwalkers']
    except KeyError:
        nwalkers = 100
    result = bilby.run_sampler(likelihood=likelihood, priors=priors,\
        sampler='emcee', nwalkers=nwalkers, iterations=iterations)
    result.plot_corner()
    result.save_posterior_samples()

def infer_estimates_from_bilby_results(samplefile):
    t = Table.read(samplefile, format='ascii')
    parameters = t.colnames[:-2]
    dict_median = {}
    dict_bound = {} #16% and 84% percentiles
    outputfile = samplefile.replace('posterior_samples', 'bayesian_estimates')
    writefile = open(outputfile, 'w')
    writefile.write('#Units: px in mas; ra and dec in rad; mu_a and mu_d in mas/yr; om_asc and incl in deg.\n')
    for p in parameters:
        dict_median[p] = howfun.sample2median(t[p])
        dict_bound[p] = howfun.sample2median_range(t[p], 1)
        writefile.write('%s = %f + %.11f - %.11f\n' % (p, dict_median[p],\
            dict_bound[p][1]-dict_median[p], dict_median[p]-dict_bound[p][0]))
    writefile.close()







def read_inits(initsfile):
    #initsfile = pmparin.replace('pmpar.in', 'inits')
    readfile = open(initsfile, 'r')
    lines = readfile.readlines()
    readfile.close()
    dict_limits = {}
    for line in lines:
        if not line.startswith('#'):
            for keyword in ['ra', 'dec', 'mu_a', 'mu_d', 'px', 'incl', 'om_asc']:
                if keyword in line:
                    parameter = line.split(':')[0].strip()
                    limits = line.split(':')[-1].strip().split(',')
                    limits = [float(limit.strip()) for limit in limits]
                    dict_limits[parameter] = limits
    return dict_limits 



def create_dictionary_of_boundaries_with_pmpar(refepoch, pmparins, HowManySigma=20):
    """
    do not cover 'incl' and 'om_asc'.
    """
    HMS = HowManySigma
    roots = ['dec', 'mu_a', 'mu_d', 'px', 'ra']
    dec_lows, dec_ups, mu_a_lows, mu_a_ups, mu_d_lows, mu_d_ups,\
        px_lows, px_ups, ra_lows, ra_ups = [], [], [], [], [],\
        [],[],[],[],[]
    for i in range(len(pmparins)):
        pmparout = pmparins[i].replace('pmpar.in','pmpar.out')
        replace_pmparin_refepoch(pmparins[i], refepoch)
        os.system("pmpar %s > %s" % (pmparins[i], pmparout))
        [ra, error_ra, dec, error_dec, mu_a, error_mu_a, mu_d, error_mu_d, px, error_px, rchsq, junk] = readpmparout(pmparout)
        errors = np.array([error_ra, error_dec, error_mu_a, error_mu_d, error_px])
        print(errors, rchsq)
        errors *= rchsq**0.5
        print(errors)
        error_ra, error_dec, error_mu_a, error_mu_d, error_px = errors
        dec_lows.append(dec - HMS * error_dec)
        dec_ups.append(dec + HMS * error_dec)
        mu_a_lows.append(mu_a - HMS * error_mu_a)
        mu_a_ups.append(mu_a + HMS * error_mu_a)
        mu_d_lows.append(mu_d - HMS * error_mu_d)
        mu_d_ups.append(mu_d + HMS * error_mu_d)
        px_lows.append(px - HMS * error_px)
        px_ups.append(px + HMS * error_px)
        ra_lows.append(ra - HMS * error_ra)
        ra_ups.append(ra + HMS * error_ra)
    dec_limits, mu_a_limits, mu_d_limits, px_limits, ra_limits = {},{},{},{},{}
    dec_limits['low'], dec_limits['up'] = dec_lows, dec_ups
    mu_a_limits['low'], mu_a_limits['up'] = mu_a_lows, mu_a_ups
    mu_d_limits['low'], mu_d_limits['up'] = mu_d_lows, mu_d_ups
    px_limits['low'], px_limits['up'] = px_lows, px_ups
    ra_limits['low'], ra_limits['up'] = ra_lows, ra_ups
    dict_limits = {}
    for root in roots:
        exec("dict_limits[root] = %s_limits" % root)
    return dict_limits
    
def generate_initsfile(refepoch, pmparins, shares, HowManySigma=20):
    """
    Used to generate initsfile.
    Common parameters might have more than 1 list of priors.
    In such cases, the larger outer bound will be adopted.
    """
    HMS = HowManySigma
    roots = ['dec', 'mu_a', 'mu_d', 'px', 'ra']
    dict_limits = create_dictionary_of_boundaries_with_pmpar(refepoch, pmparins, HowManySigma)
    parameters = get_parameters_from_shares(shares)
    inits = pmparins[0].replace('pmpar.in','inits')
    writefile = open(inits, 'w')
    writefile.write('#Prior info at MJD %f.\n' % refepoch)
    writefile.write('#%d reduced-chi-squre-corrected sigma limits are used.\n' % HMS)
    writefile.write('#The prior info is based on the pmpar results.\n')
    writefile.write('#Units: dec and ra in rad; px in mas; mu_a and mu_d in mas/yr; incl and om_asc in deg.\n')
    writefile.write('#parameter name explained: dec_0_1, for example, means this dec parameter is inferred for both pmparin0 and pmparin1.\n')
    for parameter in parameters.keys():
        if (not 'om_asc' in parameter) and (not 'incl' in parameter):
            related_pmparins_indice, root = parameter_name_to_pmparin_indice(parameter)
            lower_limit, upper_limit = render_parameter_boundaries(parameter, dict_limits)
            writefile.write('%s: %.11f,%.11f\n' % (parameter, lower_limit, upper_limit))
        else:
            writefile.write('%s: 0,360\n' % parameter)
    writefile.close()

def render_parameter_boundaries(parameter, dict_limits):
    """
    use the minimum and maximum value for parameters calculated from the relevant pmparins
    """
    related_pmparins_indice, root = parameter_name_to_pmparin_indice(parameter)
    lows, ups = [], []
    for i in related_pmparins_indice:
        lows.append(dict_limits[root]['low'][i])
        ups.append(dict_limits[root]['up'][i])
    lower_limit, upper_limit = min(lows), max(ups)
    return lower_limit, upper_limit
    
def parameter_name_to_pmparin_indice(string):
    """
    Example :
        input 'mu_a_0_2_3' --> out: ([0,2,3], 'mu_a')
    """
    alist = string.split('_')
    pmparin_indice = []
    parameter_root = []
    for element in alist:
        try:
            pmparin_indice.append(int(element))
        except ValueError:
            parameter_root.append(element)
    parameter_root = '_'.join(parameter_root)
    return pmparin_indice, parameter_root

def readpmparout(pmparout):
    """
    The function serves to offer priors for the simulation.
    """
    rchsq = 0
    lines = open(pmparout).readlines()
    for line in lines:
        if 'epoch' in line:
            epoch = line.split('=')[1].strip()
        if 'Reduced' in line:
            rchsq = float(line.split('=')[1].strip())
        for estimate in ['mu_a', 'mu_d', 'pi']:
            if estimate in line:
                #globals()['line'] = line
                #string = ("%s = " % estimate.strip())
                value = line.split('=')[-1].split('+')[0].strip()
                #print(value)
                #print(estimate.strip())
                exec("%s='%s'" % (estimate.strip(), value), globals())
        if 'RA' in line: #here, due to a bug in exec(), it is not combined with the other three parameters
            RA = line.split('=')[-1].split('+')[0].strip()
            RA = howfun.dms2deg(RA)
        if 'Dec  ' in line:
            Dec = line.split('=')[-1].split('+')[0].strip()
            Dec = howfun.dms2deg(Dec)

    for line in lines:
        if 'RA' in line:
            error_RA = float(line.split('+-')[1].strip().split(' ')[0])
        if 'Dec  ' in line:
            error_Dec = float(line.split('+-')[1].strip().split(' ')[0])
        for estimate in ['mu_a', 'mu_d', 'pi']:
            if estimate in line:
                error = line.split('+-')[1].strip().split(' ')[0]
                exec("error_%s = %s" % (estimate.strip(), error), globals())
                #exec("print(error_%s)" % estimate)
                exec("%s = float(%s)" % (estimate.strip(), estimate.strip()), globals())
    RA *= 15 * np.pi/180. #rad
    Dec *= np.pi/180. #rad
    error_RA *= 15 * np.pi/180./3600. #rad
    error_Dec *= np.pi/180./3600. #rad
    return RA, error_RA, Dec, error_Dec, mu_a, error_mu_a, mu_d, error_mu_d, pi, error_pi, rchsq, float(epoch)
    


def replace_pmparin_refepoch(pmparin, refepoch):
    """
    refepoch in MJD
    """
    readfile = open(pmparin, 'r')
    lines = readfile.readlines()
    for i in range(len(lines)):
        if 'epoch' in lines[i] and (not lines[i].strip().startswith('#')):
            lines[i] = 'epoch = ' + str(refepoch) + '\n'
    readfile.close()
    writefile = open(pmparin, 'w')
    writefile.writelines(lines)
    writefile.close()

class Gaussianlikelihood(bilby.Likelihood):
    def __init__(self, refepoch, list_of_dict_timing, list_of_dict_VLBI, shares, positions):
        """
        Addition of multiple Gaussian likelihoods

        Parameters
        ----------
        data: array_like
            The data to analyse
        """
        self.refepoch = refepoch
        self.LoD_VLBI = list_of_dict_VLBI
        self.LoD_timing = list_of_dict_timing
        self.positions = positions
        self.shares = shares
        self.number_of_pmparins = len(self.LoD_VLBI)

        #parameters = inspect.getargspec(positions).args
        #parameters.pop(0)
        parameters = get_parameters_from_shares(self.shares)
        print(parameters)
        super().__init__(parameters)

    def log_likelihood(self):
        """
        the name has to be log_likelihood, and the PDF has to do the log calculation.
        """
        log_p = 0
        for i in range(self.number_of_pmparins):
            res = self.LoD_VLBI[i]['radecs'] - self.positions(self.refepoch, self.LoD_VLBI[i]['epochs'], self.LoD_timing[i], i, self.parameters)
            log_p += -0.5 * np.sum((res/self.LoD_VLBI[i]['errs'])**2) #if both RA and errRA are weighted by cos(DEC), the weighting is canceled out
        return log_p
    

def get_parameters_from_shares(shares):
    parameters = {}
    roots = parameter_roots = ['dec', 'incl', 'mu_a', 'mu_d', 'om_asc', 'px', 'ra']
    NoP = number_of_pmparins = len(shares[0])
    for i in range(7):
        list_of_strings = group_elements_by_same_values(shares[i])
        for string in list_of_strings:
            parameter = roots[i] + string
            parameters[parameter] = None
    return parameters
def group_elements_by_same_values(alist):
    """
    Input parameters
    ----------------
    alist : list of int

    Return parameters
    -----------------
    
    """
    LoS = list_of_string = []
    alist = np.array(alist)
    GEI = grouped_element_indice = []
    N = len(alist)
    for i in range(len(alist)):
        if (not i in GEI) and (alist[i]>=0):
            each_group = np.where(alist==alist[i])[0]
            each_group = each_group.tolist()
            GEI += each_group
            each_group.sort()
            each_group = [str(element) for element in each_group]
            str_of_group = '_' + '_'.join(each_group)
            LoS.append(str_of_group)
    return LoS





def dms2rad(ra, dec):
    """
    Input parameters
    ----------------
    ra : str
        Right ascension, in hh:mm:ss.sss.
    dec : str
        Declination, in dd:mm:ss.ssss.

    Return parameters
    -----------------
    ra : float
        Right ascension, in rad.
    dec : float
        Declination, in rad.
    """
    ra = howfun.dms2deg(ra)
    ra *= 15 * np.pi/180 #in rad
    dec = howfun.dms2deg(dec)
    dec *= np.pi/180 #in rad
    return ra, dec
    






def readpmparin(pmparin):
    """
    """
    epochs = RAs = errRAs = DECs = errDECs = np.array([])
    lines = open(pmparin).readlines()
    for line in lines:
        #if 'epoch' in line and not line.strip().startswith('#'):
        #    refepoch = line.split('=')[1].strip()
        if line.count(':')==4 and (not line.strip().startswith('#')): 
            epoch, RA, errRA, DEC, errDEC = line.strip().split(' ')
            epoch = decyear2mjd(float(epoch.strip())) #in MJD
            DEC = howfun.dms2deg(DEC.strip()) #in deg
            DEC *= np.pi/180. #in rad
            RA = howfun.dms2deg(RA.strip()) #in hr
            RA *= 15*np.pi/180. #in rad
            errRA = float(errRA.strip()) #in s
            errRA *= 15 * np.pi/180./3600. #in rad
            errDEC = float(errDEC.strip()) #in arcsecond
            errDEC *= np.pi/180./3600 #in rad

            epochs = np.append(epochs, epoch)
            RAs = np.append(RAs, RA)
            DECs = np.append(DECs, DEC)
            errRAs = np.append(errRAs, errRA)
            errDECs = np.append(errDECs, errDEC)
    t = Table([epochs, RAs, errRAs, DECs, errDECs], names=['epoch', 'RA', 'errRA', 'DEC', 'errDEC'])
    return t

def decyear2mjd(epoch):
    """
    """
    threshold = 10000
    if epoch > threshold:
        return epoch
    else:
        decyear = Time(epoch, format='decimalyear')
        MJD = float(format(decyear.mjd))
        return MJD

