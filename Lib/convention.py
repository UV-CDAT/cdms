""" metadata conventions """

from __future__ import print_function
from .error import CDMSError
from collections import UserList

# On in order to turn off some warnings
WITH_GRIDSPEC_SUPPORT = True

MethodNotImplemented = "Method not yet implemented"


class AliasList (UserList):
    def __init__(self, alist):
        UserList.__init__(self, alist)

    def __setitem__(self, i, value):
        self.data[i] = value.lower()

    def __setslice(self, i, j, values):
        self.data[i:j] = [x.lower() for x in values]

    def append(self, value):
        self.data.append(value.lower())


level_aliases = AliasList(['plev'])
longitude_aliases = AliasList([])
latitude_aliases = AliasList([])
time_aliases = AliasList([])
forecast_aliases = AliasList([])


class AbstractConvention:

    def getAxisIds(self, vardict):
        raise CDMSError(MethodNotImplemented)

    def getAxisAuxIds(self, vardict, axiskeys):
        raise CDMSError(MethodNotImplemented)

    def getDsetnodeAuxAxisIds(self, dsetnode):
        raise CDMSError(MethodNotImplemented)

    def axisIsLatitude(self, axis):
        id = axis.id.lower()
        return (id[0:3] == 'lat') or (id in latitude_aliases)

    def axisIsLongitude(self, axis):
        id = axis.id.lower()
        return (id[0:3] == 'lon') or (id in longitude_aliases)

    def getVarLatId(self, var, vardict=None):
        lat = None
        nlat = 0

        for obj in [d[0] for d in var.getDomain()]:
            if self.axisIsLatitude(obj):
                if nlat == 0:
                    lat = obj
                nlat += 1
        return (lat, nlat)

    def getVarLonId(self, var, vardict=None):
        lon = None
        nlon = 0
        for obj in [d[0] for d in var.getDomain()]:
            if self.axisIsLongitude(obj):
                if nlon == 0:
                    lon = obj
                nlon += 1
        return (lon, nlon)


class NUGConvention(AbstractConvention):

    def __init__(self, version=None):
        self._version = version

    def getAxisIds(self, vardict):
        "Get 1-D coordinate axis IDs."
        result = []
        for name in list(vardict.keys()):
            dimensions = vardict[name].dimensions
            if len(dimensions) == 1 and (name in dimensions):
                result.append(name)
        return result

    def getAxisAuxIds(self, vardict, axiskeys):
        return []


class COARDSConvention(NUGConvention):

    def __init__(self, version=None):
        NUGConvention.__init__(self, version)


class CFConvention(COARDSConvention):

    current = 'CF-1.0'

    def __init__(self, version):
        COARDSConvention.__init__(self, version)

    def getAxisAuxIds(self, vardict, axiskeys):
        "Get Axis2D and AuxAxis1D IDs"
        coorddict = {}
        for var in list(vardict.values()):
            if hasattr(var, 'coordinates'):
                coordnames = var.coordinates.split()
                for item in coordnames:
                    # Don't include if already a 1D coordinate axis.
                    if item in axiskeys:
                        continue
                    coorddict[item] = 1
        for key in list(coorddict.keys()):
            try:
                coord = vardict[key]
            except KeyError:
                # Note: not everything referenced by .coordinates attribute is
                # in fact a coordinate axis, e.g., scalar coordinates
                if not WITH_GRIDSPEC_SUPPORT:
                    print(
                        'Warning: coordinate attribute points to non-existent variable: %s' %
                        key)
                del coorddict[key]
                continue
            # Omit scalar dimensions, and dimensions greater than 2-D
            if len(coord.shape) not in [1, 2]:
                del coorddict[key]
        return list(coorddict.keys())

    def getDsetnodeAuxAxisIds(self, dsetnode):
        "Get auxiliary axis IDs from a dataset node"
        coorddict = {}
        dsetdict = dsetnode.getIdDict()
        for node in list(dsetdict.values()):
            coordnames = node.getExternalAttr('coordinates')
            if coordnames is not None:
                coordnames = coordnames.split()
                for item in coordnames:
                    # Don't include if already a 1D coordinate axis.
                    if item in dsetdict and dsetdict[item].tag == 'axis':
                        continue
                    # It's not an axis node, so must be a variable, so getDomain is defined.
                    # Check the rank, don't include if not 1D or 2D (e.g.,
                    # scalar coordinate)
                    domnode = dsetdict[item].getDomain()
                    if domnode.getChildCount() not in [1, 2]:
                        continue
                    coorddict[item] = 1
        return list(coorddict.keys())

    def getVarLatId(self, var, vardict):
        lat = None
        nlat = 0

        # Coordinates don't have coordinates
        if var.isAbstractCoordinate():
            return (lat, nlat)

        if hasattr(var, 'coordinates'):
            coordnames = var.coordinates.split()
            for name in coordnames:
                coord = vardict.get(name)

                # Note: not everything referenced by .coordinates attribute is
                # in fact a coordinate axis, e.g., scalar coordinates
                if coord is not None and hasattr(
                        coord, 'isLatitude') and coord.isLatitude():
                    if nlat == 0:
                        lat = coord
                    nlat += 1
        if lat is None:
            lat, nlat = AbstractConvention.getVarLatId(self, var, vardict)

        return (lat, nlat)

    def getVarLonId(self, var, vardict):
        lon = None
        nlon = 0

        # Coordinates don't have coordinates
        if var.isAbstractCoordinate():
            return (lon, nlon)

        if hasattr(var, 'coordinates'):
            coordnames = var.coordinates.split()
            for name in coordnames:
                coord = vardict.get(name)

                # Note: not everything referenced by .coordinates attribute is
                # in fact a coordinate axis, e.g., scalar coordinates
                if coord is not None and hasattr(
                        coord, 'isLongitude') and coord.isLongitude():
                    if nlon == 0:
                        lon = coord
                    nlon += 1
        if lon is None:
            lon, nlon = AbstractConvention.getVarLonId(self, var, vardict)

        return (lon, nlon)

    def axisIsLatitude(self, axis):
        if (hasattr(axis, 'axis') and axis.axis == 'Y'):
            return True
        elif (hasattr(axis, 'units') and axis.units.lower() in [
                'degrees_north', 'degree_north', 'degree_n', 'degrees_n', 'degreen', 'degreesn'] and
                not (axis.isLongitude() or axis.isLevel() or axis.isTime())):
            return True
        elif (hasattr(axis, 'standard_name') and axis.standard_name.lower() == 'latitude'):
            return True
        else:
            return AbstractConvention.axisIsLatitude(self, axis)

    def axisIsLongitude(self, axis):
        if (hasattr(axis, 'axis') and axis.axis == 'X'):
            return True
        elif (hasattr(axis, 'units') and axis.units.lower() in [
                'degrees_east', 'degree_east', 'degree_e', 'degrees_e', 'degreee', 'degreese'] and
                not (axis.isLatitude() or axis.isLevel() or axis.isTime())):
            return True
        elif (hasattr(axis, 'standard_name') and axis.standard_name.lower() == 'longitude'):
            return True
        else:
            return AbstractConvention.axisIsLongitude(self, axis)

    def getVariableBounds(self, dset, var):
        """Get the bounds variable for the variable, from a dataset or file."""
        if hasattr(var, 'bounds'):
            boundsid = var.bounds
            if boundsid in dset.variables:
                result = dset[boundsid]
            else:
                print(
                    'Warning: bounds variable not found in %s: %s' %
                    (dset.id, boundsid))
                result = None
        else:
            result = None

        return result


NUG = NUGConvention()
COARDS = COARDSConvention()
CF1 = CFConvention('CF-1')


def getDatasetConvention(dset):
    "Return an appropriate convention object. dset is a file or dataset object"
    return CF1
