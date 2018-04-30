from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
import numpy as np


fig = plt.figure()
ax = fig.gca(projection='3d')

# Make data.
# X = np.arange(-5, 5, 0.25)
# Y = np.arange(-5, 5, 0.25)
# X, Y = np.meshgrid(X, Y)
# R = np.sqrt(X**2 + Y**2)
# Z = np.sin(R)

# X = np.array([[1,2,3,4,5], [2,3,4,5,6], [3,4,5,6,7], [4,5,6,7,8], [5,6,7,8,9]])
# Y = np.array([[2,2,2,2,2], [4,3,2,1,0], [3,2,1,0,-1], [2,1,0,-1,-2], [1,0,-1,-2,-3]])
# Z = np.array([[1,1,1,1,1], [8,7,6,5,4], [7,6,5,4,3], [6,5,4,3,2], [5,4,3,2,1]])
X = [1,2,3,4,5,6]
Y = [7,6,5,5,4,3,6,5,4,7,5,4]
X, Y = np.meshgrid(X, Y)
Z = X+Y

# Plot the surface.
surf = ax.plot_surface(X, Y, Z, cmap=cm.coolwarm,
                       linewidth=0, antialiased=False)

# Customize the z axis.
# ax.set_zlim(-1.01, 1.01)
ax.zaxis.set_major_locator(LinearLocator(10))
ax.zaxis.set_major_formatter(FormatStrFormatter('%.02f'))

# Add a color bar which maps values to colors.
fig.colorbar(surf, shrink=0.5, aspect=5)

plt.show()