# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TopoUSM2
                                 A QGIS plugin
 Terrain shading enhancer
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2018-04-30
        copyright            : (C) 2018 by Fumihiko Ikegami
        email                : f.ikegami@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load TopoUSM2 class from file TopoUSM2.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .topousm2 import TopoUSM2
    return TopoUSM2(iface)