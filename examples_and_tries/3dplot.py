from mpl_toolkits.mplot3d import axes3d
import matplotlib.pyplot as plt
import numpy

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Grab some test data.
X, Y, Z = axes3d.get_test_data(0.05)
# X = numpy.array(shape=(3, 3), dtype=float)
# X = numpy.array([[1,2,3,4,5], [2,3,4,5,6], [3,4,5,6,7], [4,5,6,7,8], [5,6,7,8,9]])
# Y = numpy.array([[2,2,2,2,2], [4,3,2,1,0], [3,2,1,0,-1], [2,1,0,-1,-2], [1,0,-1,-2,-3]])
# Z = numpy.array([[1,1,1,1,1], [8,7,6,5,4], [7,6,5,4,3], [6,5,4,3,2], [5,4,3,2,1]])
# X = numpy.array([[1,2,3], [2,3,4], [6,5,4]])
# Y = numpy.array([[2,2,2], [4,3,2], [3,2,1]])
# Z = numpy.array([[1,1,1], [8,5,2], [7,8,6]])
# Plot a basic wireframe.
ax.plot_wireframe(X, Y, Z, rstride=10, cstride=10)
plt.show()
