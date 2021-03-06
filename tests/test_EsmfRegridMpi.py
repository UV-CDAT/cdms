"""
$Id: testEsmfRegridMpi.py 2354 2012-07-11 15:28:14Z pletzer $

Unit tests for parallel esmf interface

"""

import operator
import numpy
import cdat_info
import cdms2
import regrid2.esmf
import regrid2
import unittest
import ESMF
import time
import copy
import sys
from functools import reduce
try:
    from mpi4py import MPI
    has_mpi = True
except BaseException:
    has_mpi = False

PLOT = False
if PLOT:
    from matplotlib import pylab


class Test(unittest.TestCase):

    def setUp(self):
        pass

    def test_2d_esmf(self):
        # print 'running test_2d_esmf...'
        f = cdms2.open(cdat_info.get_sampledata_path() +
                       '/so_Omon_ACCESS1-0_historical_r1i1p1_185001-185412_2timesteps.nc')
        so = f('so')[0, 0, :, :]
        clt = cdms2.open(cdat_info.get_sampledata_path() +
                         '/clt.nc')('clt')[0, :, :]
        tic = time.time()
        soInterp = so.regrid(
            clt.getGrid(),
            regridTool='ESMF',
            regridMethod='CONSERVE')  # , periodicity=1)
        soInterpInterp = soInterp.regrid(
            so.getGrid(), regridTool='ESMF', regridMethod='CONSERVE')
        toc = time.time()
        # print 'time to interpolate (ESMF linear) forward/backward: ', toc -
        # tic

        if has_mpi:
            mype = MPI.COMM_WORLD.Get_rank()
        else:
            mype = 0
        if mype == 0:
            ntot = reduce(operator.mul, so.shape)
            avgdiff = numpy.sum(so - soInterpInterp) / float(ntot)
            # print 'avgdiff = ', avgdiff
            self.assertLess(abs(avgdiff), 5.2e18)

            if PLOT:
                pylab.figure(2)
                pylab.pcolor(abs(so - soInterpInterp), vmin=0.0, vmax=1.0)
                pylab.colorbar()
                pylab.title('ESMF linear')

    # disable core dump in python 3!!
    def dtest_2d_esmf_interface(self):
        # print 'running test_2d_esmf_interface...'
        f = cdms2.open(cdat_info.get_sampledata_path() +
                       '/so_Omon_ACCESS1-0_historical_r1i1p1_185001-185412_2timesteps.nc')
        so = f('so')[0, 0, :, :]
        clt = cdms2.open(cdat_info.get_sampledata_path() +
                         '/clt.nc')('clt')[0, :, :]
        tic = time.time()
        # assume so and clt are cell centered
        srcGrid = regrid2.esmf.EsmfStructGrid(so.shape,
                                              coordSys=ESMF.CoordSys.SPH_DEG,
                                              periodicity=0)
        dstGrid = regrid2.esmf.EsmfStructGrid(clt.shape,
                                              coordSys=ESMF.CoordSys.SPH_DEG,
                                              periodicity=0)
        srcGrid.setCoords([so.getGrid().getLatitude(), so.getGrid().getLongitude()],
                          staggerloc=ESMF.StaggerLoc.CENTER)
        # convert to curvilinear
        ny, nx = clt.shape
        y = clt.getGrid().getLatitude()
        x = clt.getGrid().getLongitude()
        yy = numpy.outer(y, numpy.ones((nx,), numpy.float32))
        xx = numpy.outer(numpy.ones((ny,), numpy.float32), x)
        dstGrid.setCoords([yy, xx],
                          staggerloc=ESMF.StaggerLoc.CENTER)
        mask = numpy.zeros(so.shape, numpy.int32)
        mask[:] = numpy.ma.masked_where((so == so.missing_value), so).mask
        srcGrid.setMask(mask)
        srcFld = regrid2.esmf.EsmfStructField(srcGrid, 'srcFld',
                                              datatype='float64',
                                              staggerloc=ESMF.StaggerLoc.CENTER)
        srcFld.setLocalData(numpy.array(so), staggerloc=ESMF.StaggerLoc.CENTER)

        dstFld = regrid2.esmf.EsmfStructField(dstGrid, 'dstFld',
                                              datatype='float64',
                                              staggerloc=ESMF.StaggerLoc.CENTER)
        dstFld.setLocalData(so.missing_value * numpy.ones(clt.shape, numpy.float32),
                            staggerloc=ESMF.StaggerLoc.CENTER)

        srcFld2 = regrid2.esmf.EsmfStructField(srcGrid, 'srcFld2',
                                               datatype='float64',
                                               staggerloc=ESMF.StaggerLoc.CENTER)
        srcFld2.setLocalData(so.missing_value * numpy.ones(so.shape, numpy.float32),
                             staggerloc=ESMF.StaggerLoc.CENTER)

        rgrd1 = regrid2.esmf.EsmfRegrid(srcFld, dstFld,
                                        srcFrac=None,
                                        dstFrac=None,
                                        srcMaskValues=mask,
                                        dstMaskValues=numpy.array(
                                            [1], numpy.int32),
                                        regridMethod=ESMF.RegridMethod.BILINEAR,
                                        unMappedAction=ESMF.UnmappedAction.IGNORE)
        print("before")
        rgrd1(srcFld, dstFld)
        print("after")
        mask = numpy.zeros(dstFld.field.data.shape, numpy.int32)
        mask[:] = numpy.ma.masked_where(
            (dstFld.field.data >= so.missing_value),
            dstFld.field.data).mask
        dstGrid.setMask(mask)
        rgrd2 = regrid2.esmf.EsmfRegrid(dstFld, srcFld2,
                                        srcFrac=None,
                                        dstFrac=None,
                                        srcMaskValues=mask,
                                        dstMaskValues=numpy.array(
                                            [1], numpy.int32),
                                        regridMethod=ESMF.RegridMethod.BILINEAR,
                                        unMappedAction=ESMF.UnmappedAction.IGNORE)
        rgrd2(dstFld, srcFld2)
        soInterp = numpy.reshape(dstFld.getPointer(), clt.shape)
        soInterp = numpy.ma.array(soInterp, fill_value=1e20)
        soInterp = numpy.ma.masked_where((soInterp >= 1e20), soInterp)

        soInterpInterp = numpy.reshape(srcFld2.getPointer(), so.shape)
        soInterpInterp = numpy.ma.array(soInterpInterp, fill_value=1e20)
        soInterpInterp = numpy.ma.masked_where(
            (soInterpInterp >= 1e20), soInterpInterp)

        toc = time.time()
        print('time to interpolate (ESMF interface) forward/backward: ', toc - tic)
        ntot = reduce(operator.mul, so.shape)
        avgdiff = numpy.sum(so - soInterpInterp) / float(ntot)
        print('avgdiff = ', avgdiff)
        self.assertLess(abs(avgdiff), 3.0)

        if PLOT:
            pylab.figure(4)
            pylab.subplot(2, 2, 1)
            pylab.pcolor(so, vmin=20.0, vmax=40.0)
            pylab.colorbar()
            pylab.title("esmf.py so")
            pylab.subplot(2, 2, 2)
            pylab.pcolor(soInterp, vmin=20.0, vmax=40.0)
            pylab.title("esmf.py soInterp")
            pylab.colorbar()
            pylab.subplot(2, 2, 3)
            pylab.pcolor(soInterpInterp, vmin=20.0, vmax=40.0)
            pylab.title("esmf.py soInterpInterp")
            pylab.colorbar()
            pylab.subplot(2, 2, 4)
            pylab.pcolor(abs(so - soInterpInterp), vmin=-0.5, vmax=0.5)
            pylab.colorbar()
            pylab.title("esmf.py error")


if __name__ == '__main__':
    print("")
    ESMF.Manager()
    suite = unittest.TestLoader().loadTestsFromTestCase(Test)
    unittest.TextTestRunner(verbosity=1).run(suite)
    if PLOT:
        pylab.show()
