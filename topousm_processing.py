import os
from PyQt5.QtCore import QCoreApplication
from osgeo import gdal
from numpy import *
from time import time
"""
/***************************************************************************
 TopoUSM2 QGIS Plugin (Processing module)
                                 
 Generating ambient shading layers for raster terrain data.
 See https://github.com/geoign/TopoUSM-QGIS/

                              -------------------
        begin                : 2018-04-30
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Fumihiko Ikegami
        email                : f.ikegami@gmail.com
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

class Grid:
    def __init__(self, dlg, infile, nodata=[0]):
        self.dlg = dlg
        if not os.path.exists(infile): self.__log__('[Error] File not found: %s' % infile)
        self.fname, self.ds = infile, gdal.Open(infile)
        self.Z = self.ds.GetRasterBand(1).ReadAsArray()
        self.shape = self.Z.shape
        self.x0, self.dx, self.xy, self.y0, self.yx, self.dy = self.ds.GetGeoTransform()
        self.Z = array(self.Z, float)
        for nod in nodata: self.Z[self.Z==nod] = nan
        self.__progress__(init=True, total=self.shape[0]*self.shape[1], progress=0.01)
        self.timestart = time()
    def __set__(self, ix,iy, z): self.Z[iy,ix] = z; return 1
    def __log__(self, text, end='\n'):
        self.dlg.textEdit.insertPlainText(text + end)
    def __progress__(self, init=False, total=0, progress=0.01):
        ## self.processed, self.total, self.milestones ##
        if init:
            self.processed, self.total = 0, total
            self.milestones = arange(0, 10.0, progress)
        else:
            if self.processed/self.total > self.milestones[0]:
                self.__log__(' -> %.1f%%' % (self.processed*100.0/self.total), end='')
                if len(self.milestones) % 5 == 0: self.__log__(' (%.1f sec.)' % (time()-self.timestart))
                self.milestones = delete(self.milestones, 0, axis=0)
    def __nearby__(self, ix1,iy1, ir=1, bound=[-99999,99999,-99999,999999]):
        return array([(ix,iy) \
                for ix in arange(ix1-ir,ix1+ir+1) for iy in arange(iy1-ir,iy1+ir+1) \
		if (sqrt((ix-ix1)**2 + (iy-iy1)**2) <= ir) and \
		(bound[0] <= ix < bound[1]) and (bound[2] <= iy < bound[3])])

    def __unsharp__(self, r=1, max_iter=8, autogain=False):
        ## Create extended grid to preserve margins ##
        Zext = ones(shape=(self.shape[0] + r*2, self.shape[1] + r*2), dtype=float) * nan
        Zext[r:r+self.shape[0], r:r+self.shape[1]] = self.Z
        Zext[0:r,r:-r] = [self.Z[0,:] for i in range(0,r)] #Top
        Zext[-r:,r:-r] = [self.Z[-1,:] for i in range(0,r)] #Bottom
        Zext[r:-r,0:r] = rot90([self.Z[:,0] for i in range(0,r)],3) #Left (270deg rot)
        Zext[r:-r,-r:] = rot90([self.Z[:,-1] for i in range(0,r)],3) #Right (270deg rot)
        Zext[0:r,0:r] = self.Z[0,0]; Zext[-r:,0:r] = self.Z[-1,0] #Corners
        Zext[-r:,-r:] = self.Z[-1,-1]; Zext[0:r,-r:] = self.Z[0,-1]
        ## Create offsetted coordinates (four corners)
        Offsets = [(ix, iy, ix+self.shape[0], iy+self.shape[1]) \
                  for iy in arange(r*2+1) for ix in arange(r*2+1) \
                  if ((ix-r)**2 + (iy-r)**2) < r**2] #exclude edge
        if r>max_iter: #Sparce sampling to process faster
            sparce = r//max_iter
            Offsets = [offsets for offsets in Offsets \
                       if (offsets[0] % sparce == 0) and (offsets[1] % sparce == 0)]
        Offsets = array(Offsets, dtype=int)
        ## Set amplifiers and normalize it
        Amps = sqrt((Offsets[:,0]-r)**2 + (Offsets[:,1]-r)**2+1) #Distances from center
        self.a1 = Amps
        Amps = 1/(10**Amps) #Inverted & Hardcoded multiplyer :P
        self.a2 = Amps
        Amps = Amps / sum(Amps) * len(Amps) #Normalize them to be len(Offsets)=len(Amps) in total
        self.a3 = Amps
        ## Create blurred array
        self.Znew, self.Zmask = zeros(self.shape, dtype=float), zeros(self.shape, dtype=float)
        def works1(idx, Ze, Zm):
            QCoreApplication.processEvents() ## To avoid freezing
            if idx % 20 == 0: self.__log__(' => (%d%%)' % round(100*idx/len(Offsets)))
            else: self.__log__(' =>', end='')
            corners = Offsets[idx]
            Ztmp = Zext[corners[0]:corners[2], corners[1]:corners[3]].copy()
            if autogain:
                Zm += invert(isnan(Ztmp)) * Amps[idx] #Amplifer
            else:
                Zm += invert(isnan(Ztmp)) * 1
            Ztmp[isnan(Ztmp)] = 0
            Ze += Ztmp
        self.__log__('[Unsharp] %d iterations for r=%d | ' % (len(Offsets),r), end='')
        [works1(i, self.Znew, self.Zmask) for i in range(len(Offsets))]
        self.__log__('OK')
        self.Znew[self.Znew==0] = nan
        return self.Znew/self.Zmask
    
    def save(self, newfile, new=True, nodata=nan, ftype=gdal.GDT_Float32):
        if os.path.exists(newfile): os.remove(newfile)
        if os.path.exists(newfile+'.aux.xml'): os.remove(newfile+'.aux.xml')
        if new:
            ds = gdal.GetDriverByName('GTiff').Create(newfile,self.shape[1],self.shape[0], 1, ftype)
            ds.SetGeoTransform((self.x0, self.dx, self.xy, self.y0, self.yx, self.dy))
        else:
            ds = gdal.GetDriverByName('GTiff').CreateCopy(newfile, self.ds)
            ds.GetRasterBand(1).WriteArray(self.Z)
        ds.GetRasterBand(1).WriteArray(self.Z)
        if not isnan(nodata): ds.GetRasterBand(1).SetNoDataValue(nodata)
        ds = None

    def save_asint16(self, newfile, nodata=0, amp=30000):
        Z = self.Z.copy() ## Copy memory
        Zmax = nanmax(absolute(Z))
        Z = (Z / Zmax) * amp ## Normalize
        Z[isnan(Z)] = nodata; Z = array(Z, dtype=int16)
        ds = gdal.GetDriverByName('GTiff').Create(newfile,self.shape[1],self.shape[0], 1, gdal.GDT_Int16)
        ds.SetGeoTransform((self.x0, self.dx, self.xy, self.y0, self.yx, self.dy))
        ds.GetRasterBand(1).WriteArray(Z)
        ds.GetRasterBand(1).SetNoDataValue(nodata)
        ds = None
        
    def remove_isolated(self, limit=2):
        self.__log__('[Removing isolated nodes] ')
        def shoulddelete(ix,iy):
            self.processed+=1; self.__progress__()
            Z = take(self.Z, self.__nearby__(ix,iy,radius=1))
            return True if sum(isnan(Z))<limit else False
        self.__progress__(init=True, total=self.shape[0]*self.shape[1])
        [self.__set__(ix,iy,nan) for ix in range(self.shape[1]) for iy in range(self.shape[0]) if shoulddelete(ix,iy)]
       
    def TopoUSM2(self, r=4, max_iter=8, autogain=False):
        self.__log__('[TopoUSM] r=%d' % r)
        self.Z_blurred = self.__unsharp__(r, max_iter, autogain)
        self.Z -= self.Z_blurred

    def log10(self, amp=1):
        zmax = nanmax(absolute(self.Z))
        ## Normalize to 0.1~1.0 for positive and negative and then apply log10
        for i in range(amp):
            self.Z[self.Z>0] = log10(self.Z[self.Z>0] / zmax * 0.9 + 0.1)
            self.Z[self.Z<0] = -log10(absolute(self.Z[self.Z<0]) / zmax * 0.9 + 0.1)

    def fillNaN_USM(self, r=4, max_iter=4):
        if sum(isnan(self.Z))==0:
            self.__log__('[FillNaN-USM] No NaN node in the grid. Skipping...')
            return 1
        self.__log__('[FillNaN-USM] %.2f%% NaN' % (sum(isnan(self.Z)) / self.shape[0] / self.shape[1] * 100), end='')
        self.__log__(' (n=%d)' % sum(isnan(self.Z)))
        Znew = self.__unsharp__(r, max_iter)
        Znan = isnan(self.Z)
        self.Z[Znan] = Znew[Znan]

