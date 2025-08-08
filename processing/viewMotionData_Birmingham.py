# -*- coding: utf-8 -*-
"""
Created on Tue Dec  3 11:08:54 2024

@author: Soren
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.close('all')

#########
# 0   7 #
# 1   6 #
# 2   5 #
# 3   4 #
#   X   #
######### 

def moments(bins, histos, power):
    
    s = histos.shape
    m = np.zeros((s[0], s[1]))
    for i in range(s[0]):
        m[i, :] = np.sum((bins**power)*histos[i, :, :], axis=1)/np.sum(histos[i, :, :], axis=1)
    return m    

def readdata(dataname):
    
    FRAME_ID_MAX = 256
    
    x = np.array(pd.read_csv(dataname))
    ind1 = np.where(x[:, 1] == 1)[0][0]  #1st line in csv with good data
    x = x[ind1:, :]
    camera = x[:, 0]
    timept = x[:, 1]
    temperature = x[:, 1026]
    
    camera_inds = np.unique(camera)
    ncameras = len(camera_inds)#int(np.amax(camera)+1)
    rollovers = np.insert(np.cumsum((np.diff(timept)<0)), 0, 0)
    
    timept = rollovers * FRAME_ID_MAX + timept
    ntimepts = int(np.amax(timept))
    
    data = np.zeros((ncameras, ntimepts, 1024))
    
    for i in range(len(camera)):
        data[int(np.where(camera_inds == camera[i])[0]), int(timept[i]-1), :] = x[i, 2:1026]
     
    return data, camera_inds, timept, temperature


def plotwaveformsBirmingham(x, y, f, camera_inds, nmodules, legend, t1=0, t2=0):
    
    t = np.arange(x.shape[1], dtype=float)/f
    if t2<=t1 or t2==0:
        t2 = t[-1]    
    ind1 = int(f*t1)
    ind2 = int(f*t2)    
            
    ncameras = int(len(camera_inds)/nmodules)
    
    fig, ax = plt.subplots(nrows=ncameras, ncols=2)
    
    for j in range(nmodules):
        for i in range(ncameras):
            
            #adding this so that Birmingham gets far sensor on top
            if i==0:
                m=0
            elif i==1:
                m=2
            elif i==2:
                m=3
            elif i==3:
                m=1
            
            ind_cam = ncameras*j + i
            line1 = ax[m, j].plot(t[ind1:ind2], x[ind_cam, ind1:ind2], 'k', linewidth=2, label=legend[0]) 
            ax2 = ax[m, j].twinx()
            line2 = ax2.plot(t[ind1:ind2], y[ind_cam, ind1:ind2], 'r', linewidth=1, label=legend[1])
            ax2.tick_params(axis='y', colors='red')

            if legend[0]=='contrast':
                ax[i, 0].invert_yaxis()
            if legend[1]=='mean':
                ax2.invert_yaxis()
        
            lines = line1 + line2
            labels = [l.get_label() for l in lines]
            ax[m, j].legend(lines, labels)
            ax[m, j].set_ylabel('Camera ' + str(int(camera_inds[i])))
        
    ax[0, 0].set_title('Left')
    ax[0, 1].set_title('Right')
    ax[3, 0].set_xlabel('Time (s)')
    ax[3, 1].set_xlabel('Time (s)')

###############################################

# user inputs
datapath = 'E:/CURRENT-WORK/openwater/ow-bloodflow-app/scan_data'
datanames = [
 'scan_ow5GDXVO_20250808_153616_left_mask66.csv',
 'scan_ow5GDXVO_20250808_153616_right_mask66.csv']

t1 = 0  # start time of displayed data in seconds (Allow user to zoom into waveform)  
t2 = 120    # end time of displayed data.  If t2<t1 all the data is displayed

################################################3

t1 = np.max([t1, 0.5]) #do not display the first 20 frames

# constants
darkinterval = 600
noisyBinMin = 10
frequency = 40
bins = np.expand_dims(np.arange(1024, dtype=float), axis=0)

# calibration values
I_min = np.array([[  0,   0,   0,   0,   0,   0,   0,   0], [  0,   0,   0,   0,   0,   0,   0,   0]]) # may need to make slightly negative, hopefully not
I_max = np.array([[150, 300, 300, 300, 300, 300, 300, 150], [150, 300, 300, 300, 300, 300, 300, 150]]) # set to 2x of value on phantom
C_min = np.array([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]) # should be demod phantom value when available
C_max = np.array([[0.2, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.2], [0.2, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.2]]) # set to phantom value

# read in data
nmodules = len(datanames)
lasername = datapath + '/' + datanames[0]
histos, camera_inds, timept, temperature = readdata(lasername) #(camera, time, bin)
ncameras = len(camera_inds)
if nmodules == 2:
    lasername = datapath + '/' + datanames[1]
    histos2, camera_inds2, timept2, temperature2 = readdata(lasername) #(camera, time, bin)
    histos = np.concatenate((histos, histos2), axis=0)
    camera_inds = np.concatenate((camera_inds, camera_inds2), axis=0)
    temperature = np.concatenate((temperature, temperature2), axis=0)
histos[:, :, 0] -= 6
histos[histos<noisyBinMin]=0

# crop data so that final frame is dark
ntimepts = int(darkinterval*np.floor(histos.shape[1]/darkinterval) + 1)
histos = histos[:, :ntimepts, :]
timept = timept[:ntimepts]
temperature = temperature[:ntimepts]

# get dark histograms
inds_dark = np.arange(0, ntimepts, darkinterval)
ndark = len(inds_dark)
histos_dark = np.zeros((ncameras*nmodules, ndark, 1024))
for i in range(ndark):
    histos_dark[:, i, :] = histos[:, int(inds_dark[i]), :]

# get dark stats
u1_dark = np.zeros((ncameras*nmodules, ntimepts))
u2_dark = np.zeros((ncameras*nmodules, ntimepts))
var_dark = np.zeros((ncameras*nmodules, ntimepts))
temp1 = moments(bins, histos_dark, 1)
temp2 = moments(bins, histos_dark, 2)
tempv = temp2 - temp1**2
for i in range(ndark-1):
    ind = int(inds_dark[i])
    interval = inds_dark[i+1] - ind
    for j in range(ncameras):    
        u1_dark[j, ind:(ind+interval)]  = temp1[j, i] + (temp1[j, i+1]-temp1[j, i])*np.arange(interval)/(interval-1)
        var_dark[j, ind:(ind+interval)] = tempv[j, i] + (tempv[j, i+1]-tempv[j, i])*np.arange(interval)/(interval-1)
u1_dark[:, -1]=temp1[:, -1]
var_dark[:, -1]=tempv[:, -1]

#get laser stats
u1 = moments(bins, histos, 1)
u2 = moments(bins, histos, 2)
mean = u1 - u1_dark
var = u2 - u1**2 - var_dark
std = np.sqrt(var)
contrast = std/mean

#quadratic interpolation to fill in dark frames
for i in range(1, ndark-1):
    mean[:, inds_dark[i]]     =  (-1/6)*mean[:, inds_dark[i]-2]     + (2/3)*mean[:, inds_dark[i]-1]     + (2/3)*mean[:, inds_dark[i]+1]     + (-1/6)*mean[:, inds_dark[i]+2]
    contrast[:, inds_dark[i]] =  (-1/6)*contrast[:, inds_dark[i]-2] + (2/3)*contrast[:, inds_dark[i]-1] + (2/3)*contrast[:, inds_dark[i]+1] + (-1/6)*contrast[:, inds_dark[i]+2]
mean=mean[:, 1:-1]         #remove first and last (dark) frames
contrast=contrast[:, 1:-1] #remove first and last (dark) frames

BFI = np.zeros(contrast.shape)
BVI = np.zeros(mean.shape)
for i in range(nmodules):
    for j in range(ncameras):
        ind = ncameras*i + j
        cam = int(camera_inds[ind])
        BFI[ind, :] = (1 - ( contrast[ind, :] - C_min[i, cam] ) / ( C_max[i, cam] - C_min[i, cam] ) ) * 10
        BVI[ind, :] = (1 - ( mean[ind, :]     - I_min[i, cam] ) / ( I_max[i, cam] - I_min[i, cam] ) ) * 10

#plot data
plotwaveformsBirmingham(BFI, BVI, frequency, camera_inds, nmodules, ['BFI', 'BVI'], t1, t2)

