import os
import datetime
import calendar
import inspect
import pickle

import netCDF4
import numpy as np
import scipy.linalg as linalg
import scipy.sparse as sparse
import scipy.sparse.linalg as sparse_linalg
import matplotlib
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.colors as colors
from matplotlib.gridspec import GridSpec

import cartopy
import cartopy.util
import cartopy.crs as ccrs
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
import cmocean.cm

# Configure logger first before importing any sub-module that depend on the logger being already configured.
import coloredlogs, logging.config

logging.config.fileConfig('logging.ini')
logger = logging.getLogger(__name__)

data_dir_path = 'D:\\data\\'
figure_dir_path = 'D:\\figures\\'

# Load land sea mask (land=0, sea=1)
lsmask_filepath = os.path.join(data_dir_path, 'lsmask.oisst.v2.nc')
logger.info('Loading dataset: {}'.format(lsmask_filepath))
lsmask_dataset = netCDF4.Dataset(lsmask_filepath)

lats_lsmask = np.array(lsmask_dataset.variables['lat'])
lons_lsmask = np.array(lsmask_dataset.variables['lon'])
land_sea_mask = np.array(lsmask_dataset.variables['lsmask'])[0]


def is_land(lat, lon):
    if lat < -67.5:
        return True

    # if lat < -67.5 and 160 <= lon <= 210:  # Weird pointy Antarctic bit.
    #     return True

    # if 60 < lat < 70 and 180 < lon < 200:  # Block out Bering Strait
    #     return True

    idx_lat = np.abs(lats_lsmask - lat).argmin()
    idx_lon = np.abs(lons_lsmask - lon).argmin()
    return False if land_sea_mask[idx_lat][idx_lon] else True


def distance(lat1, lon1, lat2, lon2):
    R = 6371.228e3  # average radius of the earth [m]

    # Calculate the distance between two points on the Earth (lat1, lon1) and (lat2, lon2) using the haversine formula.
    # See: http://www.movable-type.co.uk/scripts/latlong.html

    lat1, lon1, lat2, lon2 = np.deg2rad([lat1, lon1, lat2, lon2])
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = np.sin(delta_lat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(delta_lon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R*c


def plot_scalar_field(lats, lons, field, cmap, vmin, vmax):
    # Add land to the plot with a 1:50,000,000 scale. Line width is set to 0 so that the edges aren't poofed up in
    # the smaller plots.
    land_50m = cartopy.feature.NaturalEarthFeature('physical', 'land', '50m', edgecolor='black', facecolor='white',
                                                   linewidth=0.5)
    ice_50m = cartopy.feature.NaturalEarthFeature('physical', 'antarctic_ice_shelves_polys', '50m', edgecolor='black',
                                                  facecolor='white', linewidth=0.5)
    vector_crs = ccrs.PlateCarree()

    field, lons = cartopy.util.add_cyclic_point(field, coord=lons)

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    ax = plt.subplot(111, projection=ccrs.PlateCarree(central_longitude=180))
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree(central_longitude=180))

    ax.set_xticks([-180, -120, -60, 0, 60, 120, 180], crs=ccrs.PlateCarree(central_longitude=180))
    ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree(central_longitude=180))
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    # gl = ax.gridlines(crs=ccrs.PlateCarree(central_longitude=180), draw_labels=True,
    #                   linewidth=1, color='black', alpha=0.8, linestyle='--')
    # LON_TICKS = [-180, -90, 0, 90, 180]
    # LAT_TICKS = [-90, -60, -30, 0, 30, 60, 90]
    # gl.xlabels_top = gl.ylabels_right = False
    # gl.xlocator = mticker.FixedLocator(LON_TICKS)
    # gl.ylocator = mticker.FixedLocator(LAT_TICKS)
    # gl.xformatter = LONGITUDE_FORMATTER
    # gl.yformatter = LATITUDE_FORMATTER

    im = ax.pcolormesh(lons, lats, field, transform=vector_crs, cmap=cmap, vmin=vmin, vmax=vmax)
    clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    clb.ax.set_title(r'W/m$^2$')

    plt.title('Net upward heat flux')

    png_filepath = os.path.join(figure_dir_path, 'net_upward_heat_flux.png')
    logger.info('Saving diagnostic figure: {:s}'.format(png_filepath))
    plt.savefig(png_filepath, dpi=300, format='png', transparent=False)
    plt.close()


def plot_vector_field(lats, lons, field, u, v, cmap, vmin, vmax):
    # Add land to the plot with a 1:50,000,000 scale. Line width is set to 0 so that the edges aren't poofed up in
    # the smaller plots.
    land_50m = cartopy.feature.NaturalEarthFeature('physical', 'land', '50m', edgecolor='face', facecolor='dimgray',
                                                   linewidth=0)
    ice_50m = cartopy.feature.NaturalEarthFeature('physical', 'antarctic_ice_shelves_polys', '50m', edgecolor='face',
                                                  facecolor='darkgray', linewidth=0)
    vector_crs = ccrs.PlateCarree()

    u, lons_cyclic = cartopy.util.add_cyclic_point(u, coord=lons)
    v, lons_cyclic = cartopy.util.add_cyclic_point(v, coord=lons)
    field, lons_cyclic = cartopy.util.add_cyclic_point(field, coord=lons)

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    ax = plt.subplot(111, projection=ccrs.PlateCarree())
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree())

    im = ax.pcolormesh(lons, lats, field, transform=vector_crs, cmap=cmap, vmin=vmin, vmax=vmax)

    Q = ax.quiver(lons_cyclic[::3], lats[::3], u[::3, ::3]/1e6, v[::3, ::3]/1e6,
                  pivot='middle', transform=vector_crs, units='width', width=0.002, scale=50)

    clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    clb.ax.set_title(r'MW/m')

    plt.show()
    plt.close(fig)


def solve_for_ocean_heat_transport_potential_spherical():
    # Load net upward heat flux dataset.
    nuhf_filepath = os.path.join(data_dir_path, 'net_upward_heatflux.nc')
    logger.info('Loading dataset: {}'.format(nuhf_filepath))
    nuhf_dataset = netCDF4.Dataset(nuhf_filepath)

    lats_nuhf = np.array(nuhf_dataset.variables['Y'])  # TODO: But this includes 90 N and 90 S!
    lons_nuhf = np.array(nuhf_dataset.variables['X'])
    net_upward_heat_flux = np.array(nuhf_dataset.variables['asum'])
    net_upward_heat_flux, lons_nuhf = cartopy.util.add_cyclic_point(net_upward_heat_flux, coord=lons_nuhf)

    # Load land sea mask (land=0, sea=1)
    lsmask_filepath = os.path.join(data_dir_path, 'lsmask.oisst.v2.nc')
    logger.info('Loading dataset: {}'.format(lsmask_filepath))
    lsmask_dataset = netCDF4.Dataset(lsmask_filepath)

    lats_lsmask = np.array(lsmask_dataset.variables['lat'])
    lons_lsmask = np.array(lsmask_dataset.variables['lon'])
    land_sea_mask = np.array(lsmask_dataset.variables['lsmask'])[0]

    # plot_scalar_field(lats_nuhf, lons_nuhf, net_upward_heat_flux, 'BrBG', -200, 200)
    # plot_scalar_field(lats_lsmask, lons_lsmask, land_sea_mask, 'RdBu', 0, 1)

    # Setting up the linear system A*chi = f for the discretized Poisson equation with Dirchlet boundary conditions on
    # a sphere.
    lats, lons = np.deg2rad(lats_nuhf), np.deg2rad(lons_nuhf)
    m, n = lats.size, lons.size
    delta_phi, delta_lambda = np.pi/m, 2*np.pi/n

    beta = 4 / (n * delta_phi**2)

    logger.info('m = {:d}, n = {:d}, delta_phi = {:f}, delta_lambda = {:f}'.format(m, n, delta_phi, delta_lambda))

    A = sparse.lil_matrix((m*n+2, m*n+2))
    chi = sparse.lil_matrix((m*n+2, 1))
    f = sparse.lil_matrix((m*n+2, 1))

    # Applying Dirchlet boundary condition that chi=0 over land.
    for i in np.arange(0, n):
        lat = lats_nuhf[i]
        for j in np.arange(0, m):
            lon = lons_nuhf[j]
            if is_land(lat, lon):
                chi[i*n + j*m] = 0

    # North pole condition
    A[0, 0] = -beta*n
    for j in np.arange(1, n+1):
        A[0, j*m] = beta

    f[0] = np.mean(net_upward_heat_flux[0, :])  # Use average value at 90 N to get f_N.

    # South pole condition
    A[m*n+1, m*n+1] = -beta*n
    for j in np.arange(0, n):
        A[m*n+1, j*m] = beta

    f[m*n+1] = np.mean(net_upward_heat_flux[-1, :])  # Use average value at 90 S to get f_S.

    # Interior points
    for i in np.arange(0, n):
        phi_i = i * delta_phi
        phi_imh = (i - 0.5) * delta_phi
        phi_iph = (i + 0.5) * delta_phi

        a_i = np.sin(phi_imh) / (delta_phi**2 * np.sin(phi_i))
        b_i = np.sin(phi_iph) / (delta_phi**2 * np.sin(phi_i))
        d_i = 1 / (delta_lambda**2 * np.sin(phi_i)**2)

        for j in np.arange(1, m+1):
            A[i*n + j*m, i*n + j*m - 1] = a_i               # Coefficient of chi(i-1,j)
            A[i*n + j*m, i*n + j*m + 1] = b_i               # Coefficient of chi(i+1,j)
            A[i*n + j*m, i*n + j*m - m] = d_i               # Coefficient of chi(i,j-1)
            A[i*n + j*m, i*n + j*m + m] = d_i               # Coefficient of chi(i,j+1)
            A[i*n + j*m, i*n + j*m] = -(a_i + b_i + 2*d_i)  # Coefficient of chi(i,j)

            # Construct the RHS vector source term
            f[i*n + j*m] = net_upward_heat_flux[i, j]

    # 4. Use conjugate gradient iterative method from SciPy to solve this system.


def solve_for_ocean_heat_transport_potential_cartesian():
    # Load net upward heat flux dataset.
    nuhf_filepath = os.path.join(data_dir_path, 'net_upward_heatflux.nc')
    logger.info('Loading dataset: {}'.format(nuhf_filepath))
    nuhf_dataset = netCDF4.Dataset(nuhf_filepath)

    lats_nuhf = np.array(nuhf_dataset.variables['Y'])
    lons_nuhf = np.array(nuhf_dataset.variables['X'])
    net_upward_heat_flux = np.array(nuhf_dataset.variables['asum'])

    # Remove the 90 N and 90 S rows.
    lats_nuhf = lats_nuhf[1:-1]
    net_upward_heat_flux = net_upward_heat_flux[1:-1, :]

    m, n = lons_nuhf.size, lats_nuhf.size

    # Setting net upward flux to zero over land.
    for i in range(len(lats_nuhf)):
        for j in range(len(lons_nuhf)):
            lat, lon = lats_nuhf[i], lons_nuhf[j]
            if is_land(lat, lon):
                net_upward_heat_flux[i, j] = 0

    # Count the number of land points.
    N_land_cells = 0
    for j in np.arange(n):
        for i in np.arange(m):
            lat, lon = lats_nuhf[j], lons_nuhf[i]
            if is_land(lat, lon):
                N_land_cells = N_land_cells + 1

    logger.info('m*n={:d}, N_land_cells={:d}, m*n-N={:d}'.format(m * n, N_land_cells, m * n - N_land_cells))

    # Create map of the southmost cell at each longitude for the purposes of setting boundary conditions.
    idx_southmost = np.zeros((m, 1))
    for i in np.arange(m):
        for j in np.arange(n-1, -1, -1):
            lat, lon = lats_nuhf[j], lons_nuhf[i]
            if not is_land(lat, lon):
                idx_southmost[i] = j

    # Create map of the northmost cell at each longitude for the purposes of setting boundary conditions.
    idx_northmost = np.zeros((m, 1))
    for i in np.arange(m):
        for j in np.arange(n):
            lat, lon = lats_nuhf[j], lons_nuhf[i]
            if not is_land(lat, lon):
                idx_northmost[i] = j

    # Create 1D map that maps the cell (i,j)'s index  j*m + i on the grid including land to the index
    # j*m + i - n_land_cells on the grid excluding land points, where n_land_cells is the number of land cells
    # encountered so far.
    idx_map = np.zeros((m*n, 1))
    n_land_cells = 0
    for j in np.arange(n):
        for i in np.arange(m):
            lat, lon = lats_nuhf[j], lons_nuhf[i]
            if is_land(lat, lon):
                n_land_cells = n_land_cells + 1
            idx_map[j*m + i] = j * m + i - n_land_cells

    # Normalize array to integrate to zero, to satisfy the compatibility condition.
    logger.info('Before normalization: sum={:f}, mean={:f}'
                .format(np.sum(net_upward_heat_flux), np.mean(net_upward_heat_flux)))

    net_upward_heat_flux = net_upward_heat_flux - np.mean(net_upward_heat_flux)

    logger.info('After normalization: sum={:f}, mean={:f}'
                .format(np.sum(net_upward_heat_flux), np.mean(net_upward_heat_flux)))

    # lons_nuhf = np.append(lons_nuhf[97:], lons_nuhf[0:97])
    # net_upward_heat_flux = np.append(net_upward_heat_flux[:, 97:], net_upward_heat_flux[:, 0:97], axis=1)

    plot_scalar_field(lats_nuhf, lons_nuhf, net_upward_heat_flux, cmap=cmocean.cm.balance, vmin=-150, vmax=150)

    # Setting up the linear system A*u = f for the discretized Poisson equation.
    A = sparse.lil_matrix((m * n - N_land_cells, m * n - N_land_cells))
    # A = sparse.csc_matrix((m * n - N_land_cells, m * n - N_land_cells))
    f = np.zeros((m * n - N_land_cells, 1))

    n_land_cells = 0

    for j in np.arange(n):
        delta_lat, delta_lon = lats_nuhf[1] - lats_nuhf[0], lons_nuhf[2] - lons_nuhf[1]
        dy = distance(lats_nuhf[j] - 0.5 * delta_lat, lons_nuhf[0], lats_nuhf[j] + 0.5 * delta_lat, lons_nuhf[0])
        dx_j = distance(lats_nuhf[j], lons_nuhf[1], lats_nuhf[j], lons_nuhf[2])
        logger.info('j={:d}, lat={:f}, dy={:f}, dx_j={:f}'.format(j, lats_nuhf[j], dy, dx_j))
        for i in np.arange(m):
            # Taking modulus of i-1 and i+1 to get the correct index in the special cases of
            #  * i=0 (180 W) and need to use the value from i=m (180 E)
            #  * i=m (180 E) and need to use the value from i=0 (180 W)
            im1 = (i - 1) % m
            ip1 = (i + 1) % m

            delta_lat, delta_lon = lats_nuhf[1] - lats_nuhf[0], lons_nuhf[2] - lons_nuhf[1]
            dy = distance(lats_nuhf[j] - 0.5*delta_lat, lons_nuhf[0], lats_nuhf[j] + 0.5*delta_lat, lons_nuhf[0])
            dx_j = distance(lats_nuhf[j], lons_nuhf[1], lats_nuhf[j], lons_nuhf[2])

            if is_land(lats_nuhf[j], lons_nuhf[i]):
                n_land_cells = n_land_cells + 1
                continue

            # idx = j * m + i
            idx = j*m + i - n_land_cells

            dm_m = None  # \Delta m_-: subtract from idx to get the index of the gridpoint below, i.e. (j-1, i).
            dm_p = None  # \Delta m_+: add to idx to get the index of the gridpoint above, i.e. (j+1, i).

            if j > 0:
                dm_m = int(idx_map[j*m + i] - idx_map[j*m + i - m])

            if j < n-1:
                dm_p = int(idx_map[j*m + i + m] - idx_map[j*m + i])

            # print('i={:}, j={:}, n={:}, j*m+i={:}, j*m+i-n={:}, j*m+i-m={:}, '
            #       'idx_map[j*m+i]={:}, idx_map[j*m+i-m]={:}, dm_m={:}, dm_p={:}'
            #       .format(i, j, n_land_cells, j*m+i, j*m+i-n_land_cells, j*m+i-m,
            #               int(idx_map[j*m+i]), int(idx_map[j*m+i-m]), dm_m, dm_p))

            # if is_land(lats_nuhf[j-1], lons_nuhf[i]) or is_land(lats_nuhf[j+1], lons_nuhf[i]):
            #     dy = 0
            # elif is_land(lats_nuhf[j], lons_nuhf[im1]) or is_land(lats_nuhf[j], lons_nuhf[ip1]):
            #     dx_j = 0

            if j == idx_southmost[i]:
                logger.info('(SOUTH) j={:d}, i={:d}'.format(j, i))
                # Setting phi(i,0) = phi(i,1) at southern boundary
                A[idx, idx] = -2 * (dx_j ** 2 + dy ** 2)
                A[idx, idx + dm_p] = 2 * (dx_j ** 2 + dy ** 2)
                f[idx] = 0

            elif j == idx_northmost[j] or j == n-1:
                logger.info('(NORTH) j={:d}, i={:d}'.format(j, i))
                # Setting phi(i,n-1) = phi(i,n-2) at northern boundary
                A[idx, idx] = -2 * (dx_j ** 2 + dy ** 2)
                A[idx, idx - dm_m] = 2 * (dx_j ** 2 + dy ** 2)
                f[idx] = 0

            else:
                A[idx, idx - 1] = dx_j ** 2  # Coefficient of u(i-1,j)
                A[idx, idx + 1] = dx_j ** 2  # Coefficient of u(i+1,j)
                A[idx, idx - dm_m] = dy ** 2  # Coefficient of u(i,j-1)
                A[idx, idx + dm_p] = dy ** 2  # Coefficient of u(i,j+1)
                A[idx, idx] = -2 * (dx_j ** 2 + dy ** 2)  # Coefficient of u(i,j)

                # f[idx] = -(dx_j ** 2 * dy ** 2) * net_upward_heat_flux[j, i]
                # Set the source term to zero in the polar regions.
                if np.abs(lats_nuhf[j]) > 70:
                    f[idx] = 0
                    net_upward_heat_flux[j, i] = 0
                else:
                    f[idx] = -(dx_j**2 * dy**2) * net_upward_heat_flux[j, i]

                # if is_land(lats_nuhf[j-1], lons_nuhf[i]):
                #     A[idx, idx] = -2*(dx_j**2 + dy**2)
                #     A[idx, idx - dm_m] = 2*(dx_j**2 + dy**2)
                #     f[idx] = 0
                #
                # if is_land(lats_nuhf[j+1], lons_nuhf[i]):
                #     A[idx, idx] = -2*(dx_j**2 + dy**2)
                #     A[idx, idx + dm_p] = 2*(dx_j**2 + dy**2)
                #     f[idx] = 0
                #
                # if is_land(lats_nuhf[j], lons_nuhf[im1]):
                #     A[idx, idx] = -2*(dx_j**2 + dy**2)
                #     A[idx, idx - 1] = 2*(dx_j**2 + dy**2)
                #     f[idx] = 0
                #
                # if is_land(lats_nuhf[j], lons_nuhf[ip1]):
                #     A[idx, idx] = -2*(dx_j**2 + dy**2)
                #     A[idx, idx + 1] = 2*(dx_j**2 + dy**2)
                #     f[idx] = 0
                #
                # else:
                #     A[idx, idx - 1] = dx_j**2   # Coefficient of u(i-1,j)
                #     A[idx, idx + 1] = dx_j**2   # Coefficient of u(i+1,j)
                #     A[idx, idx - dm_m] = dy**2  # Coefficient of u(i,j-1)
                #     A[idx, idx + dm_p] = dy**2  # Coefficient of u(i,j+1)
                #     A[idx, idx] = -2*(dx_j**2 + dy**2)  # Coefficient of u(i,j)
                #
                #     f[idx] = -(dx_j ** 2 * dy ** 2) * net_upward_heat_flux[j, i]

            # Set the source term to zero in the polar regions.
            # if np.abs(lats_nuhf[j]) > 80:
            #     f[idx] = 0
            #     net_upward_heat_flux[j, i] = 0
            # else:
            #     f[idx] = -(dx_j**2 * dy**2) * net_upward_heat_flux[j, i]

            # A[idx, idx - 1] = 1 / dx_j ** 2  # Coefficient of u(i-1,j)
            # A[idx, idx + 1] = 1 / dx_j ** 2  # Coefficient of u(i+1,j)
            # A[idx, idx - dm_m] = 1 / dy ** 2  # Coefficient of u(i,j-1)
            # A[idx, idx + dm_p] = 1 / dy ** 2  # Coefficient of u(i,j+1)
            # A[idx, idx] = -2 * (dx_j ** 2 + dy ** 2) / (dx_j ** 2 * dy ** 2)  # Coefficient of u(i,j)

            # Incorperate Neumann boundary condition at continental boundaries for grid points beside land.
            # if is_land(lats_nuhf[j-1], lons_nuhf[i]):
            #     A[idx, idx - dm_m] = 0            # Coefficient of u(i,j-1)
            #     A[idx, idx + dm_p] = 2 / (dy**2)  # Coefficient of u(i,j+1)
            #
            # if is_land(lats_nuhf[j+1], lons_nuhf[i]):
            #     A[idx, idx - dm_m] = 2 / (dy**2)  # Coefficient of u(i,j-1)
            #     A[idx, idx + dm_p] = 0            # Coefficient of u(i,j+1)
            #
            # if is_land(lats_nuhf[j], lons_nuhf[im1]):
            #     A[idx, idx - 1] = 0              # Coefficient of u(i-1,j)
            #     A[idx, idx + 1] = 2 / (dx_j**2)  # Coefficient of u(i+1,j)
            #
            # if is_land(lats_nuhf[j], lons_nuhf[ip1]):
            #     A[idx, idx - 1] = 2 / (dx_j**2)  # Coefficient of u(i-1,j)
            #     A[idx, idx + 1] = 0              # Coefficient of u(i+1,j)

            # f[idx] = net_upward_heat_flux[j, i]
            # f[idx] = -net_upward_heat_flux[j, i]

    logger.info('net_upward_heat_flux.shape={:}'.format(net_upward_heat_flux.shape))
    logger.info('A.shape={:}, f.shape={:}'.format(A.shape, f.shape))
    logger.info('m={:d}, n={:d}, m*n={:d}, m*n-N_land_cells={:d}'.format(m, n, m*n, m*n-N_land_cells))

    def report(xk):
        frame = inspect.currentframe().f_back
        print('iter={:d} resid={:f} info={:} ndx1={:} ndx2={:} sclr1={:} sclr2={:} ijob={:}'
              .format(frame.f_locals['iter_'], frame.f_locals['resid'], frame.f_locals['info'], frame.f_locals['ndx1'],
                      frame.f_locals['ndx2'], frame.f_locals['sclr1'], frame.f_locals['sclr2'], frame.f_locals['ijob']))

    logger.info('Computing Jacobi preconditioner...')

    P = sparse.lil_matrix(A.shape)

    # Jacobi preconditioner matrix P. Could be effective in our case as our A matrix is (just barely!)
    # diagonally dominant. It actually helps quite a bit!
    for i in np.arange(m*n - N_land_cells):
        # logger.info('A[{:d},{:d}]={:f}, f[{:d}={:}'.format(i, i, A[i, i], i, f[i]))
        P[i, i] = 1 / A[i, i]

    # logger.info('Computing ILU preconditioner...')
    # P_ILU = sparse_linalg.spilu(A)
    # M_x = lambda x: P_ILU.solve(x)
    # M_ILU = sparse_linalg.LinearOperator(A.shape, M_x)

    # We try using two iterative solvers for sparse nonsymmetric linear systems, the
    # BIConjugate Gradient STABilized iteration (bicgstab) and the Generalized Minimal RESidual iteration (GMRES).
    # u_no_land, _ = sparse_linalg.bicgstab(A, f, tol=0.05, callback=report)
    u_no_land, _ = sparse_linalg.gmres(A, f, tol=0.135, callback=report)

    # logger.info('Directly solving linear system...')
    # u_no_land = sparse_linalg.spsolve(A, f)

    # The potential is unique up to a constant, so we pick the "gauge" or normalization that it must integrate to zero.
    logger.info('Before normalization: sum(u_no_land)={:f}, mean(u_no_land)={:f}'
                .format(np.sum(u_no_land), np.mean(np.mean(u_no_land))))

    u_no_land = u_no_land - np.mean(u_no_land)

    logger.info('Before normalization: sum(u_no_land)={:f}, mean(u_no_land)={:f}'
                .format(np.sum(u_no_land), np.mean(np.mean(u_no_land))))

    # Add the land cells back in as NaN.
    u = np.zeros((m*n, 1))
    n_land_cells = 0
    for j in np.arange(n):
        for i in np.arange(m):
            lat, lon = lats_nuhf[j], lons_nuhf[i]
            if is_land(lat, lon):
                u[j*m + i] = np.nan
                n_land_cells = n_land_cells + 1
            else:
                u[j*m + i] = u_no_land[j*m + i - n_land_cells]

    # pickle_filepath = 'D:\\output\\phi_bicgstab.pickle'
    #
    # # Create directory if it does not exist already.
    # pickle_dir = os.path.dirname(pickle_filepath)
    # if not os.path.exists(pickle_dir):
    #     logger.info('Creating directory: {:s}'.format(pickle_dir))
    #     os.makedirs(pickle_dir)
    #
    # with open(pickle_filepath, 'wb') as f:
    #     pickle.dump(u, f, pickle.HIGHEST_PROTOCOL)
    #
    # with open(pickle_filepath, 'rb') as f:
    #     u = pickle.load(f)

    phi = np.reshape(u, (n, m))

    # phi[:, 0] = phi[:, 1]
    # phi[:, -1] = phi[:, -2]
    # phi[0, :] = phi[1, :]
    # phi[-1, :] = phi[-2, :]

    phi_x = np.zeros(phi.shape)
    phi_y = np.zeros(phi.shape)

    phi_x[0, :] = np.nan
    phi_x[-1, :] = np.nan
    phi_y[0, :] = np.nan
    phi_y[-1, :] = np.nan

    for j in np.arange(1, n - 1):
        for i in np.arange(m):
            # Taking modulus of i-1 and i+1 to get the correct index in the special cases of
            #  * i=0 (180 W) and need to use the value from i=m (180 E)
            #  * i=m (180 E) and need to use the value from i=0 (180 W)
            im1 = (i - 1) % m
            ip1 = (i + 1) % m

            dx_j = distance(lats_nuhf[j], lons_nuhf[0], lats_nuhf[j + 1], lons_nuhf[0])
            dy = distance(lats_nuhf[j], lons_nuhf[0], lats_nuhf[j], lons_nuhf[1])

            if is_land(lats_nuhf[j], lons_nuhf[i]) \
                    or is_land(lats_nuhf[j-1], lons_nuhf[i]) or is_land(lats_nuhf[j+1], lons_nuhf[i]) \
                    or is_land(lats_nuhf[j], lons_nuhf[im1]) or is_land(lats_nuhf[j], lons_nuhf[ip1]):
                phi_x[j, i] = np.nan
                phi_y[j, i] = np.nan
            else:
                phi_x[j, i] = (phi[j, ip1] - phi[j, im1]) / (2*dx_j)
                phi_y[j, i] = (phi[j+1, i] - phi[j-1, i]) / (2*dy)

    # Add land to the plot with a 1:50,000,000 scale. Line width is set to 0 so that the edges aren't poofed up in
    # the smaller plots.
    land_50m = cartopy.feature.NaturalEarthFeature('physical', 'land', '50m', edgecolor='black', facecolor='white',
                                                   linewidth=0.5)
    ice_50m = cartopy.feature.NaturalEarthFeature('physical', 'antarctic_ice_shelves_polys', '50m', edgecolor='black',
                                                  facecolor='white', linewidth=0.5)
    vector_crs = ccrs.PlateCarree()

    phi, lons_cyclic = cartopy.util.add_cyclic_point(phi, coord=lons_nuhf)
    phi_x, lons_cyclic = cartopy.util.add_cyclic_point(phi_x, coord=lons_nuhf)
    phi_y, lons_cyclic = cartopy.util.add_cyclic_point(phi_y, coord=lons_nuhf)

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    # Plot ocean heat potential phi_o.
    ax = plt.subplot(111, projection=ccrs.PlateCarree(central_longitude=180))
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree(central_longitude=180))

    # gl = ax.gridlines(crs=ccrs.PlateCarree(central_longitude=180), draw_labels=True,
    #                   linewidth=1, color='black', alpha=0.8, linestyle='--')
    # LON_TICKS = [-180, -90, 0, 90, 180]
    # LAT_TICKS = [-90, -60, -30, 0, 30, 60, 90]
    # gl.xlabels_top = gl.ylabels_right = False
    # gl.xlocator = mticker.FixedLocator(LON_TICKS)
    # gl.ylocator = mticker.FixedLocator(LAT_TICKS)
    # gl.xformatter = LONGITUDE_FORMATTER
    # gl.yformatter = LATITUDE_FORMATTER

    ax.set_xticks([-180, -120, -60, 0, 60, 120, 180], crs=ccrs.PlateCarree(central_longitude=180))
    ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree(central_longitude=180))
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    # im = ax.contourf(lons_cyclic, lats_nuhf, phi / 1e15, 25, transform=vector_crs, cmap=cmocean.cm.matter)
    im = ax.contour(lons_cyclic, lats_nuhf, phi / 1e15, np.arange(-0.24, 0.20, 0.04), colors='red',
                    transform=vector_crs, linestyles='solid')

    # ax.contour(lons_cyclic, lats_nuhf[:-8], np.ma.array(phi_x[:-8, :], mask=np.isnan(phi_x[:-8, :])), levels=[0],
    #            colors='blue', linewidths=2, transform=vector_crs)
    # ax.contour(lons_cyclic, lats_nuhf[:-8], np.ma.array(phi_y[:-8, :], mask=np.isnan(phi_y[:-8, :])), levels=[0],
    #            colors='black', linewidths=2, transform=vector_crs)

    EFE_patch = mpatches.Patch(color='black', label=r'energy flux equator (EFE), $v_h=0$ ')
    EFPM_patch = mpatches.Patch(color='blue', label=r'energy flux prime meridian (EFPM), $u_h=0$')

    # plt.legend(handles=[EFE_patch, EFPM_patch], loc='lower center',
    #            bbox_to_anchor=(0, -0.2, 1, -0.2), ncol=1, mode='expand', borderaxespad=0, frameon=False)

    # m = plt.cm.ScalarMappable(cmap=cm.get_cmap('PuOr', 15))
    # m.set_array(phi)
    # m.set_clim(-2, 2)
    # clb = fig.colorbar(m, extend='both', fraction=0.046, pad=0.1)
    # clb.ax.set_title(r'$\phi_o$ (PW)')

    # clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    # clb.ax.set_title(r'PW ($\times 10^{15}$ W)')

    plt.title(r'Ocean heat transport potential $\phi_o$ (contours every 0.04 PW)')

    png_filepath = os.path.join(figure_dir_path, 'ocean_heat_transport_potential.png')
    logger.info('Saving diagnostic figure: {:s}'.format(png_filepath))
    plt.savefig(png_filepath, dpi=300, format='png', transparent=False)
    plt.close(fig)

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    # Plot zonal heat transport.
    ax = plt.subplot(111, projection=ccrs.PlateCarree(central_longitude=180))
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree(central_longitude=180))

    # gl = ax.gridlines(crs=ccrs.PlateCarree(central_longitude=180), draw_labels=True,
    #                   linewidth=1, color='black', alpha=0.8, linestyle='--')
    # LON_TICKS = [-180, -90, 0, 90, 180]
    # LAT_TICKS = [-90, -60, -30, 0, 30, 60, 90]
    # gl.xlabels_top = gl.ylabels_right = False
    # gl.xlocator = mticker.FixedLocator(LON_TICKS)
    # gl.ylocator = mticker.FixedLocator(LAT_TICKS)
    # gl.xformatter = LONGITUDE_FORMATTER
    # gl.yformatter = LATITUDE_FORMATTER

    ax.set_xticks([-180, -120, -60, 0, 60, 120, 180], crs=ccrs.PlateCarree(central_longitude=180))
    ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree(central_longitude=180))
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    nuhf, lons_nuhf2 = cartopy.util.add_cyclic_point(net_upward_heat_flux, coord=lons_nuhf)
    im = ax.pcolormesh(lons_nuhf2, lats_nuhf, nuhf, transform=vector_crs, cmap=cmocean.cm.balance, vmin=-150, vmax=150)

    # im = ax.pcolormesh(lons_cyclic, lats_nuhf, phi_x / 1e8, transform=vector_crs,
    #                    cmap=cmocean.cm.balance, vmin=-1, vmax=1)

    Q = ax.quiver(lons_cyclic[::3], lats_nuhf[::3],
                  np.ma.array(phi_x / 1e8, mask=np.isnan(phi_x))[::3, ::3],
                  np.ma.array(phi_y / 1e8, mask=np.isnan(phi_y))[::3, ::3],
                  pivot='middle', transform=vector_crs, units='width', width=0.002)
    plt.quiverkey(Q, 0.70, 0.88, 1, r'$10^8$ W/m ', labelpos='E', coordinates='figure',
                  fontproperties={'size': 11}, transform=ax.transAxes)

    ax.contour(lons_cyclic, lats_nuhf[:-8], np.ma.array(phi_x[:-8, :], mask=np.isnan(phi_x[:-8, :])), levels=[0],
               colors='blue', linewidths=2, transform=vector_crs)
    ax.contour(lons_cyclic, lats_nuhf[:-8], np.ma.array(phi_y[:-8, :], mask=np.isnan(phi_y[:-8, :])), levels=[0],
               colors='black', linewidths=2, transform=vector_crs)

    EFE_patch = mpatches.Patch(color='black', label=r'energy flux equator (EFE), $v_h=0$ ')
    EFPM_patch = mpatches.Patch(color='blue', label=r'energy flux prime meridian (EFPM), $u_h=0$')

    plt.legend(handles=[EFE_patch, EFPM_patch], loc='lower center',
               bbox_to_anchor=(0, -0.2, 1, -0.2), ncol=1, mode='expand', borderaxespad=0, frameon=False)

    # ax.streamplot(lons_cyclic, lats_nuhf, phi_x, phi_y, color='black', linewidth=2, density=5, transform=vector_crs)

    # ax.contour(lons_cyclic, lats_nuhf, phi / 1e15, levels=[-0.20, -0.15, -0.10, -0.05, 0, 0.05, 0.10, 0.15],
    #            colors='red', linewidths=2, transform=vector_crs)

    clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    clb.ax.set_title('Net upward\nheat flux ' r'(W/m$^2$)')
    # clb.ax.set_title(r'$10^8$ W/m ')

    plt.title(r'Ocean heat transport $\mathbf{u}_h = (u_h, v_h)$')

    png_filepath = os.path.join(figure_dir_path, 'ocean_heat_transport.png')
    logger.info('Saving diagnostic figure: {:s}'.format(png_filepath))
    plt.savefig(png_filepath, dpi=300, format='png', transparent=False)

    # plt.show()
    plt.close(fig)

    # Calculate and plot Laplacian
    F_up = np.zeros(phi.shape)
    for j in np.arange(1, n-1):
        lat = lats_nuhf[j]
        logger.info('lat={:}'.format(lat))
        for i in np.arange(m):
            # Taking modulus of i-1 and i+1 to get the correct index in the special cases of
            #  * i=0 (180 W) and need to use the value from i=m (180 E)
            #  * i=m (180 E) and need to use the value from i=0 (180 W)
            im1 = (i - 1) % m
            ip1 = (i + 1) % m

            dx_j = distance(lats_nuhf[j], lons_nuhf[0], lats_nuhf[j], lons_nuhf[1])
            dy = distance(lats_nuhf[j], lons_nuhf[0], lats_nuhf[j+1], lons_nuhf[0])

            if is_land(lats_nuhf[j], lons_nuhf[i]) \
                    or is_land(lats_nuhf[j-1], lons_nuhf[i]) or is_land(lats_nuhf[j+1], lons_nuhf[i]) \
                    or is_land(lats_nuhf[j], lons_nuhf[im1]) or is_land(lats_nuhf[j], lons_nuhf[ip1]):
                F_up[j, i] = np.nan
            else:
                F_up[j, i] = - (phi[j-1, i] + phi[j+1, i] + phi[j, ip1] + phi[j, im1] - 4*phi[j, i]) / (dx_j * dy)

            if lat <= -70 or lat >= 70:
                F_up[j, i] = 0

    net_upward_heat_flux, lons_cyclic = cartopy.util.add_cyclic_point(net_upward_heat_flux, coord=lons_nuhf)
    error = F_up - net_upward_heat_flux

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    ax = plt.subplot(111, projection=ccrs.PlateCarree(central_longitude=180))
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree(central_longitude=180))

    ax.set_xticks([-180, -120, -60, 0, 60, 120, 180], crs=ccrs.PlateCarree(central_longitude=180))
    ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree(central_longitude=180))
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    im = ax.pcolormesh(lons_cyclic, lats_nuhf, F_up, transform=vector_crs, cmap=cmocean.cm.balance, vmin=-150, vmax=150)
    clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    clb.ax.set_title(r'W/m$^2$')

    plt.title('Reconstructed net upward heat flux')

    png_filepath = os.path.join(figure_dir_path, 'F_up.png')
    logger.info('Saving diagnostic figure: {:s}'.format(png_filepath))
    plt.savefig(png_filepath, dpi=300, format='png', transparent=False)
    plt.close()

    fig = plt.figure(figsize=(16, 9))
    matplotlib.rcParams.update({'font.size': 10})

    ax = plt.subplot(111, projection=ccrs.PlateCarree(central_longitude=180))
    ax.add_feature(land_50m)
    ax.add_feature(ice_50m)
    ax.set_extent([-180, 180, -90, 90], ccrs.PlateCarree(central_longitude=180))

    ax.set_xticks([-180, -120, -60, 0, 60, 120, 180], crs=ccrs.PlateCarree(central_longitude=180))
    ax.set_yticks([-90, -60, -30, 0, 30, 60, 90], crs=ccrs.PlateCarree(central_longitude=180))
    lon_formatter = LongitudeFormatter(zero_direction_label=True)
    lat_formatter = LatitudeFormatter()
    ax.xaxis.set_major_formatter(lon_formatter)
    ax.yaxis.set_major_formatter(lat_formatter)

    im = ax.pcolormesh(lons_cyclic, lats_nuhf, error, transform=vector_crs, cmap=cmocean.cm.curl,
                       vmin=-100, vmax=100)
    clb = fig.colorbar(im, ax=ax, extend='both', fraction=0.046, pad=0.1)
    clb.ax.set_title(r'W/m$^2$')

    plt.title('Error = reconstructed source term - source term')

    png_filepath = os.path.join(figure_dir_path, 'error.png')
    logger.info('Saving diagnostic figure: {:s}'.format(png_filepath))
    plt.savefig(png_filepath, dpi=300, format='png', transparent=False)
    plt.close()


if __name__ == '__main__':
    solve_for_ocean_heat_transport_potential_cartesian()