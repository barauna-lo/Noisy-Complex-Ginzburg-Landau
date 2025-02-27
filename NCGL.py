import numpy as np
from numpy.fft import fftn,ifftn,fftfreq
import math
import random
import itertools
import tqdm as tqdm
from collections import namedtuple
from scipy.signal import convolve2d
import cNoise
from scipy.interpolate import interp1d

class NCGL():
	'''
	NCGL - Noisy Complex Ginzburg-Landau
	
	Wrote by: Rubens Andreas Sautter (2022)
	
	Adapted from Aranson, et.al.(1997)
	https://arxiv.org/abs/patt-sol/9709005
	
	Adittional References:

	de Franciscis, d’Onofrio (2012) (Tsallis-Borland model)
	https://journals.aps.org/pre/abstract/10.1103/PhysRevE.86.021118
	
	
	
	Complex Ginzburg-Landau equation solved with Fourier pseudospectral methods, and integrated with RK45.
	
	A new method 

	'''

	def __init__(self, c1=1.0, c2=1.0,h=1.0, msize = 128, ic='r', sigma_r= 1.0, noiseSpeed=1.0, noiseType='multiplicative', noiseArgs=None):
		'''
		Spatial parameters:
			ic = initial condition('r', 'g')
			h - grid spacing

		GL parameters:
			c1 - diffusion parameter - (1+ib)Nabla A
			c2 - reaction parameter  - (1+ic)(|A|^2)A
			
		Noise Parameters:
			noiseSpeed - ]0,1[ - the speed (relative to the number of iterations) which the noise moves
			sigma_r - reactive noise 'strenght'
			noiseArgs - Colored noise parameters {'beta':2,std = 0.01}
		'''
		
		self.c1, self.c2 = c1,c2
		self.a0 = 0.01
		
		self.h = h
		self.ic = ic
		self.msize = msize
		self.dim = 2
		self.sigma_r = sigma_r
		self.noiseType = noiseType
		self.noiseSpeed = noiseSpeed
		if noiseArgs is None:
			self.noiseArgs = {}
		else:
			self.noiseArgs = noiseArgs

	def __getRandom(self,n,dim):
		newShape = tuple([n for i in range(dim)])
		return np.random.rand(n**dim).reshape(newShape)
		
	def __getGaussian(self,n,dim):
		out = np.zeros(np.repeat(n,dim))
		c = n/2
		squareDists = np.sum((np.indices(out.shape)-c)**2,as_vs=0)
		return np.exp(-squareDists/n)
		
	def getInitialCondition(self):
		if self.ic=='r':
			self.a = self.a0*((self.__getRandom(self.msize,self.dim)-0.5)+1j*(self.__getRandom(self.msize,self.dim)-0.5))
		else:
			self.a = self.a0*(self.__getGaussian(self.msize,self.dim)+1j*self.__getGaussian(self.msize,self.dim))
			
		return np.array(self.a)
		
	
	def getChainedSingleReaction(self,a0=None,dt=0.1, nit=3000):
		'''
		Returns the iteration of a single amplitude (spatial part is ignored)
		
		The function integrates with rk4 method
		'''
		states = []
		delta = 1e-6*(np.random.rand()-0.5)
		if a0 is None:
			at = self.a0+delta
		else:
			at = a0
				
		for i in range(nit):
			states.append(at)
			
			t = i*dt
			k1 = self.reaction(at,t)
			k2 = self.reaction((at+dt*k1/2), t+dt/2.)
			k3 = self.reaction((at+dt*k2/2), t+dt/2.)
			k4 = self.reaction((at+dt*k3), t+dt)
			at = at + dt*(k1+2*k2+2*k3+k4)/6.
		return np.array(states)
	
	def __interpolate1D(self,noise,t):
		p1, p2 = int(np.floor(t)),int(np.ceil(t))
		if p1 == p2:
			return noise[p1]
		else:
			return noise[p1]*np.abs(t-p1)/np.abs(p1-p2) + noise[p2]*np.abs(t-p2)/np.abs(p1-p2)
	
	def getNoisyChainedSingleReaction(self,a0=None,beta=0,dt=0.1, nit=3000):
		'''
		Returns the iteration of a single amplitude (spatial part is ignored)
		
		The function integrates with rk4 method
		'''
		states = []
		delta = 1e-6*(np.random.rand()-0.5)
		if a0 is None:
			at = self.a0+delta
		else:
			at = a0
		
		eta = cNoise.cNoise(beta=beta,shape=(nit+2,),std=1)+1j*cNoise.cNoise(beta=beta,shape=(nit+2,),std=1)
		eta = np.gradient(eta)
		
		for i in range(nit):
			states.append(at)
			t = i*dt
			if self.noiseType == 'multiplicative':
				k1 = self.reaction(at,t)+self.sigma_r*at*self.__interpolate1D(eta,i)
				k2 = self.reaction((at+dt*k1/2), t+dt/2.)+self.sigma_r*(at+dt*k1/2)*self.__interpolate1D(eta,i+0.5)
				k3 = self.reaction((at+dt*k2/2), t+dt/2.)+self.sigma_r*(at+dt*k2/2)*self.__interpolate1D(eta,i+0.5)
				k4 = self.reaction((at+dt*k3), t+dt)+self.sigma_r*(at+dt*k3)*self.__interpolate1D(eta,i+1)
			else:
				k1 = self.reaction(at,t)+self.sigma_r*self.__interpolate1D(eta,i)
				k2 = self.reaction((at+dt*k1/2), t+dt/2.)+self.sigma_r*self.__interpolate1D(eta,i+0.5)
				k3 = self.reaction((at+dt*k2/2), t+dt/2.)+self.sigma_r*self.__interpolate1D(eta,i+0.5)
				k4 = self.reaction((at+dt*k3), t+dt)+self.sigma_r*self.__interpolate1D(eta,i+1)
			at = at + dt*(k1+2*k2+2*k3+k4)/6.
		return np.array(states)
		
	def reaction(self, a, t):
		a1 = a - (1+1j*self.c2)*(np.abs(a)**2)*a
		return np.array(a1)
		
	def interpolateNoise(self,time):
		'''
		Linear interpolation of the noise
		
		return the slice of nr and ni at the given time
		'''
		
		t = np.linspace(0,1,self.nr1.shape[0])
		p1, p2 = int(np.floor((self.nr1.shape[0]-1)*time)),int(np.ceil((self.nr1.shape[0]-1)*time))
		
		t1 = t[p1]
		t2 = t[p2]
		mr1 = self.nr1[p1]
		mr2 = self.nr1[p2]
		
		md1 = self.nr2[p1]
		md2 = self.nr2[p2]
		
		if np.abs(t1-t2)<1e-15:
			mr3 = mr1
			md3 = md1
		else:
			mr3 = np.abs(t1-time)*mr1/(np.abs(t2-t1))+np.abs(t2-time)*mr2/(np.abs(t2-t1))
			md3 = np.abs(t1-time)*md1/(np.abs(t2-t1))+np.abs(t2-time)*md2/(np.abs(t2-t1))
		return mr3, md3
		
		
	def solveRKF45(self,dt,ntimes,stepsave,dtTolerace=1e-4):
		state = self.getInitialCondition()
		times = []
		states = [state]	
			
		w = np.array([	[					0,0,0,0,0,0],
				[1/4,					0,0,0,0,0],
				[3/32,9/32,				0,0,0,0],
				[1932/2197,-7200/2197,7296/2197,	0,0,0],
				[439/216,-8,3680/513,-845/4104,	0,0],
				[-8/27, 2,-3544/2565,1859/4104,-11/40,0]
			])
		t = 0.0
		
		if 'beta' in self.noiseArgs:
			exponent = self.noiseArgs['beta']
		else:
			exponent = 2
		if 'std' in self.noiseArgs:
			std = self.noiseArgs['std']
		else:
			std = 0.01
		self.nr1 = cNoise.cNoise(beta=exponent,shape=(int(self.noiseSpeed*ntimes),self.msize,self.msize),std=std)
		self.nr2 = self.nr1.copy()
		self.nr1, _, _ = np.gradient(self.nr1)
			
		self.maxTime = (ntimes+2)*dt
				
		for time in tqdm.tqdm(range(ntimes)):
		
			step = dt
			
			k1 = step*self.timeDerivatives(state,								t		)
			k2 = step*self.timeDerivatives(state+k1*w[1,0], 		        				t+step/4	)
			k3 = step*self.timeDerivatives(state+k1*w[2,0]+k2*w[2,1], 					t+3*step/8	)
			k4 = step*self.timeDerivatives(state+k1*w[3,0]+k2*w[3,1]+k3*w[3,2],    				t+12*step/13	)
			k5 = step*self.timeDerivatives(state+k1*w[4,0]+k2*w[4,1]+k3*w[4,2]+k4*w[4,3],    		t+step		)
			k6 = step*self.timeDerivatives(state+k1*w[5,0]+k2*w[5,1]+k3*w[5,2]+k4*w[5,3]+k5*w[5,4],    	t+step/2	)
			
			approach4 = state + (25/216)*k1 + (1408/2565)*k3 + (2197/4101)*k4 -k5/5
			approach5 = state + (16/135)*k1 + (6656/12825)*k3 + (28561/56430)*k4 - (9/50)*k5 + (2/55)*k6
			
			error = np.max(np.abs(approach4-approach5))
			if error> dtTolerace:
				step = dt*((dtTolerace/(2*error))**.25)
			
				k1 = step*self.timeDerivatives(state,								t		)
				k2 = step*self.timeDerivatives(state+k1*w[1,0], 		        				t+step/4	)
				k3 = step*self.timeDerivatives(state+k1*w[2,0]+k2*w[2,1], 					t+3*step/8	)
				k4 = step*self.timeDerivatives(state+k1*w[3,0]+k2*w[3,1]+k3*w[3,2],    				t+12*step/13	)
				k5 = step*self.timeDerivatives(state+k1*w[4,0]+k2*w[4,1]+k3*w[4,2]+k4*w[4,3],    		t+step		)
				k6 = step*self.timeDerivatives(state+k1*w[5,0]+k2*w[5,1]+k3*w[5,2]+k4*w[5,3]+k5*w[5,4],    	t+step/2	)
				
				approach4 = state + (25/216)*k1 + (1408/2565)*k3 + (2197/4101)*k4 -k5/5
				
			t += step
			state = approach4 
			times.append(t)
			if time in stepsave:
				states.append(state)
		return np.array(states), np.array(times)
		
	def timeDerivatives(self,state,time):
		
		#PseudoSpectral approach:
		fx  = 2*np.pi*fftfreq(state.shape[0])
		fy  = 2*np.pi*fftfreq(state.shape[1])
		
		rFtState = fftn(np.real(state))
		iFtState = fftn(np.imag(state))
		normalizedTime = time/self.maxTime
		
		
		tnr1,tnr2 = self.interpolateNoise(normalizedTime)
		
		lap  =    np.real(ifftn(-(fx[None,:]**2)*rFtState -(fy[:,None]**2)* rFtState )) + 1j*np.real(ifftn(-(fx[None,:]**2)*iFtState -(fy[:,None]**2)* iFtState ))/(self.h**2)
		#adv  =    np.real(ifftn(fx[None,:]*1j*rFtState + 1j*fy[:,None]* rFtState )) + 1j*np.real(ifftn(1j*fx[None,:]*iFtState +1j*fy[:,None]* iFtState ))/(self.h)
		#unitary = lap / np.abs(lap)
		
		if self.noiseType == 'diffusive':
			return (1+self.c1*1j)*np.array(lap) + self.reaction(state,time) + self.sigma_r*lap*tnr2/np.abs(lap)
		elif self.noiseType == 'multiplicative':
			return (1+self.c1*1j)*np.array(lap) + self.reaction(state,time) + self.sigma_r*state*(tnr1 + 1j*tnr1)
		else:
			return (1+self.c1*1j)*np.array(lap) + self.reaction(state,time) + self.sigma_r*(tnr1 + 1j*tnr1)
