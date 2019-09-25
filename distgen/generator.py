from .physical_constants import *
from .beam import beam
from .tools import *
from .dist import *
from collections import OrderedDict as odic
import numpy as np
from matplotlib import pyplot as plt

#import seaborn

class generator():

    def __init__(self,verbose):
        
        self.verbose = verbose 
        self.supported_dists = ['r','theta','x','y','z','px','py','pz','t','r','E','crystals',"file","xy"]
    
    def parse_input(self,params):
        
        params = self.convert_params(params)
        self.input_params = params
        self.check_input_consistency(params)

    def check_input_consistency(self,params):
        ''' Perform consistency checks on the user input data'''
        
        if( ("r_dist" in params) or ("x_dist" in params) or ("xy_dist" in params) ):
            assert_with_message( ("r_dist" in params)^("x_dist" in params)^("xy_dist" in params),"User must specify only one transverse distribution.")
        if( ("r_dist" in params) or ("y_dist" in params) or ("xy_dist" in params) ):
            assert_with_message( ("r_dist" in params)^("y_dist" in params)^("xy_dist" in params),"User must specify r dist OR y dist NOT BOTH.")
        
        if(params["beam"]["start_type"] == "cathode"):

            vprint("Ignoring user specified px distribution for cathode start.",self.verbose>0 and "px_dist" in params,0,True )
            vprint("Ignoring user specified py distribution for cathode start.",self.verbose>0 and "py_dist" in params,0,True )
            vprint("Ignoring user specified pz distribution for cathode start.",self.verbose>0 and "pz_dist" in params,0,True )
            assert_with_message("MTE" in params["beam"]["params"],"User must specify the MTE for cathode start.") 

            # Handle momentum distribution for cathode
            MTE = self.input_params["beam"]["params"]["MTE"]
            sigma_pxyz = (np.sqrt( (MTE/MC2).to_reduced_units() )*unit_registry("GB")).to("eV/c")
            self.input_params["px_dist"]={"type":"g","params":{"sigma_px":sigma_pxyz}}
            self.input_params["py_dist"]={"type":"g","params":{"sigma_py":sigma_pxyz}}
            self.input_params["pz_dist"]={"type":"g","params":{"sigma_pz":sigma_pxyz}}
                
    def convert_params(self,all_params):
        
        cparams = {}
        for key in all_params:
            cparams[key]=self.get_dist_params(key,all_params)
            
        return cparams
        
    def get_dist_params(self,dname,all_params):
        
        dparams = {}
        for key in all_params[dname].keys():
            
            if(key=="params"): # make physical quantity
                params = {}
                for p in all_params[dname]["params"]:
                    if(isinstance(all_params[dname]["params"][p],dict) and "value" in all_params[dname]["params"][p] and "units" in all_params[dname]["params"][p]):
                        params[p]=all_params[dname]["params"][p]["value"]*unit_registry(all_params[dname]["params"][p]["units"])
                    else:
                        params[p]=all_params[dname]["params"][p]
                dparams["params"]=params
                
            else: # Copy over
                dparams[key]=all_params[dname][key]
                
        return dparams
                
    def get_beam(self):
    
        watch = stopwatch()
        watch.start()
    
        verbose = self.verbose
        outputfile = []
        
        beam_params = self.input_params["beam"]
        out_params = self.input_params["output"]

        dist_params = {}
        for p in self.input_params:
            if("_dist" in p):
                var = p[:-5]
                dist_params[var]=self.input_params[p]
        
        vprint("Distribution format: "+out_params["type"],self.verbose>0,0,True)
        
        N = int(beam_params["particle_count"])
        bdist = beam(N, beam_params["params"]["total_charge"])
        
        if("file" in out_params):
            outfile = out_params["file"]
        else:
            outfile = "test.out.txt"
            vprint("Warning: no output file specified, defaulting to "+outfile+".",verbose>0,1,True)
        vprint("Output file: "+outfile,verbose>0,0,True)
        
        vprint("\nCreating beam distribution....",verbose>0,0,True)
        vprint("Beam starting from: cathode.",verbose>0,1,True)
        vprint("Total charge: {:0.3f~P}".format(bdist.q)+".",verbose>0,1,True)
        vprint("Number of macroparticles: "+str(N)+".",verbose>0,1,True)
        
        bdist.params["x"] = np.full((N,), 0.0)*unit_registry("meter")
        bdist.params["y"] = np.full((N,), 0.0)*unit_registry("meter")
        bdist.params["z"] = np.full((N,), 0.0)*unit_registry("meter")
        bdist.params["px"]= np.full((N,), 0.0)*unit_registry("eV/c")
        bdist.params["py"]= np.full((N,), 0.0)*unit_registry("eV/c")
        bdist.params["pz"]= np.full((N,), 0.0)*unit_registry("eV/c")
        bdist.params["t"] = np.full((N,), 0.0)*unit_registry("s")

        avgs = odic()
        avgs["x"] = 0*unit_registry("meter")
        avgs["y"] = 0*unit_registry("meter")
        avgs["z"] = 0*unit_registry("meter")
        avgs["px"]= 0*unit_registry("eV/c")
        avgs["py"]= 0*unit_registry("eV/c")
        avgs["pz"]= 0*unit_registry("eV/c")
        avgs["t"] = 0*unit_registry("s")

        stds = odic()
        stds["x"] = 0*unit_registry("meter")
        stds["y"] = 0*unit_registry("meter")
        stds["z"] = 0*unit_registry("meter")
        stds["px"]= 0*unit_registry("eV/c")
        stds["py"]= 0*unit_registry("eV/c")
        stds["pz"]= 0*unit_registry("eV/c")
        stds["t"] = 0*unit_registry("s")
        
        # Get number of populations:
        npop = 0
        for param in self.input_params:

            if("_dist" in param):
                vstr = param[:-5]
                if(vstr in ["r","x","y","z","px","py","pz","t","theta"]):
                    npop = npop + 1
                elif(vstr in ["xy"]):
                    npop = npop + 2
            
        rgen = randgen()
        shape = ( N, npop )
        if(beam_params["rand_type"]=="hammersley"):
            rns = rgen.rand(shape, sequence="hammersley",params={"burnin":-1,"primes":()})
        else:
            rns = rgen.rand(shape)
        
        count = 0
            
        # Do radial dist first if requested
        if("r" in dist_params):
                
            r="r"
            vprint("r distribution: ",verbose>0,1,False)  
                
            # Get distribution
            dist = get_dist(r,dist_params[r]["type"],dist_params[r]["params"],verbose=verbose)      
            rs = dist.cdfinv(rns[count,:])        # Sample to get beam coordinates

            count = count + 1

            if("theta" not in dist_params):

                vprint("Assuming cylindrical symmetry...",verbose>0,2,True)
                    
                # Sample to get beam coordinates
                params = {"min_theta":0*unit_registry("rad"),"max_theta":2*pi}
                ths=(uniform("theta",**params)).cdfinv(rns[-1,:]*unit_registry("dimensionless"))        
   
                avgr=0*unit_registry("m")

                if("sigma_xy" in dist_params[r]["params"]):
                    rrms= math.sqrt(2)*dist_params[r]["params"]["sigma_xy"]
                elif("sigma_xy" in beam_params["params"]):
                    rrms= math.sqrt(2)*beam_params["params"]["sigma_xy"]
                else:
                    rrms = dist.rms()

                avgCos = 0
                avgSin = 0
                avgCos2 = 0.5
                avgSin2 = 0.5
                   
            else:
                count = count+1
                dist_params.pop("theta")
  
            bdist.params["x"]=rs*np.cos(ths)
            bdist.params["y"]=rs*np.sin(ths)

            avgs["x"] = avgr*avgCos
            avgs["y"] = avgr*avgSin

            stds["x"] = rrms*np.sqrt(avgCos2)
            stds["y"] = rrms*np.sqrt(avgSin2)       

            # remove r from list of distributions to sample
            dist_params.pop("r")
            #self.dist_params.pop("x",None)
            #self.dist_params.pop("y",None)
           
        # Do 2D distributions
        if("xy" in dist_params):

            vprint("xy distribution: ",verbose>0,1,False) 
            dist = get_dist("xy",dist_params["xy"]["type"],dist_params["xy"]["params"],verbose=0)
            bdist["x"],bdist["y"] = dist.cdfinv(rns[count:count+2,:]*unit_registry("dimensionless"))
            count = count + 2
            dist_params.pop("xy")

            stds["x"]=bdist["x"].std()
            stds["y"]=bdist["y"].std()
        
        # Do all other specified single coordinate dists   
        for x in dist_params.keys():

            vprint(x+" distribution: ",verbose>0,1,False)   
            dist = get_dist(x,dist_params[x]["type"],dist_params[x]["params"],verbose=verbose)      # Get distribution
            bdist[x]=dist.cdfinv(rns[count,:]*unit_registry("dimensionless"))               # Sample to get beam coordinates
              
            # Fix up the avg and std so they are exactly what user asked for
            if("avg_"+x in dist_params[x]["params"]):
                avgs[x]=dist_params[x]["params"]["avg_"+x]
            else:
                avgs[x] = dist.avg()

            if("sigma_"+x in dist_params[x]["params"]):
                stds[x] = dist_params[x]["params"]["sigma_"+x]
            else:
                stds[x] = dist.std()
               
            count=count+1
        
        # Allow user to overite the distribution moments if desired
        for x in ["x","y","t"]:
            if("avg_"+x in beam_params["params"]):
                avgx = beam_params["params"]["avg_"+x] 
                if(x in avgs and avgx!=avgs[x]):
                    vprint("Overwriting distribution avg "+x+" with user defined value",verbose>0,1,True)
                    avgs[x] = avgx
            if("sigma_"+x in beam_params["params"]):
                stdx = beam_params["params"]["sigma_"+x]
                if(x in stds and stdx!=stds[x]):
                    vprint("Overwriting distribution sigma "+x+" with user defined value",verbose>0,1,True)
                stds[x] = stdx                 

        # Shift and scale coordinates to undo sampling error
        for x in avgs:

            avgi = np.mean(bdist[x])
            stdi = np.std(bdist[x])
            avgf = avgs[x]
            stdf = stds[x]

            # Scale and center each coordinate
            if(stdi.magnitude>0):
                #bdist[x] = (avgf + (stdf/stdi)*(bdist[x] - avgi)).to(avgi.units)
                bdist[x] = ((stdf/stdi)*(bdist[x] - avgi)).to(avgi.units)
            else:
                #bdist[x] = (avgf + (bdist[x] - avgi)).to(avgi.units)
                bdist[x] = (bdist[x] - avgi).to(avgi.units)
        
        # Perform any coordinate rotations before shifting to final average locations
        if("rotate_xy" in beam_params["params"]):
            angle = beam_params["params"]["rotate_xy"]
            C = np.cos(angle)
            S = np.sin(angle)
            
            x =  C*bdist["x"]-S*bdist["y"]
            y = +S*bdist["x"]+C*bdist["y"]
            
            bdist["x"]=x
            bdist["y"]=y
        
        for x in avgs:
            bdist[x] = avgs[x] + bdist[x]
        
        if(beam_params["start_type"]=="cathode"):

            bdist["pz"]=np.abs(bdist["pz"])   # Only take forward hemisphere 
            vprint("Cathode start: fixing pz momenta to forward hemisphere",verbose>0,1,True)
            vprint("avg_pz -> {:0.3f~P}".format(np.mean(bdist["pz"]))+", sigma_pz -> {:0.3f~P}".format(np.std(bdist["pz"])),verbose>0,2,True)

        else:
            raise ValueError("Beam start '"+beam_params["start_type"]+"' is not supported!")

        watch.stop()
        vprint("...done. Time Ellapsed: "+watch.print()+".\n",verbose>0,0,True)
        return (bdist,outfile)

    def get_dist(self,x,dparams):

        dtype = dparams["type"]
        dist=None

        if(dtype=="u" or dtype=="uniform"):
            
            vprint("uniform",self.verbose>0,0,True)
            vprint("min_"+x+" = {:0.3f~P}".format(dparams["min_"+x])+", max_"+x+" = {:0.3f~P}".format(dparams["max_"+x]),self.verbose>0,2,True)
            dist = uniform(dparams["min_"+x],dparams["max_"+x],xstr=x)

            #kwargs = {"tony":1,"beef":"x"}
            #dist.set_params(**kwargs)
            
        elif(dtype=="g" or dtype=="gaussian"):

            vprint("Gaussian",self.verbose>0,0,True)
            if("avg_"+x not in dparams):
                dparams["avg_"+x] = 0*dparams["sigma_"+x].units
            vprint("avg_"+x+" = {:0.3f~P}".format(dparams["avg_"+x])+", sigma_"+x+" = {:0.3f~P}".format(dparams["sigma_"+x]),self.verbose>0,2,True)
            dist = norm(dparams["avg_"+x],dparams["sigma_"+x],xstr=x)

        elif(dtype=="crystals"):

            vprint("crystal temporal laser shaping",self.verbose>0,0,True)
            lengths = [dparams[dp] for dp in dparams if "crystal_length" in dp]
            angles  = [dparams[dp] for dp in dparams if "crystal_angle" in dp]
            dist = temporal_laser_pulse_stacking(lengths,angles,verbose=self.verbose)

        elif( (dtype=="rg" or dtype=="radial_gaussian") and x=="r"):

            vprint("radial Gaussian",self.verbose>0,0,True)
            vprint("sigma_xy = {:0.3f~P}".format(dparams["sigma_xy"]),self.verbose>0,2,True)
            dist = normrad(dparams["sigma_xy"])

        elif( (dtype=="tg" or dtype=="truncated_radial_gaussian") and x=="r"):

            vprint("radial Gaussian",self.verbose>0,0,True)
            vprint("f = {:0.3f~P}".format(dparams["truncation_fraction"]),self.verbose>0,2,False)
            vprint(", pinhole size = {:0.3f~P}".format(dparams["pinhole_size"]),self.verbose>0,0,True)
            dist = normrad_trunc(dparams["pinhole_size"]/2.0, dparams["truncation_fraction"]) 

        elif(dtype == "file" and x == "r"):
           
            vprint("radial distribution file: '"+dparams["file"]["file"]+"' ["+dparams["file"]["units"]+"]",self.verbose>0,0,True)
            dist = radfile(dparams["file"]["file"],units=dparams["file"]["units"])

        elif(dtype == "file" and x == "xy"):

            vprint("xy distribution file: '"+dparams["file"]["file"],self.verbose>0,0,True)
            dist = file2d(dparams["file"]["file"])

        else:
            raise ValueError("Distribution type '"+dtype+"' is not supported.")

        return dist
