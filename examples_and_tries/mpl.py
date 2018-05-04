import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mp
#mp.use('agg')

#plt.dr
# plt.ion()
# fig = plt.figure(1, figsize=(9, 6))
# ax = fig.add_subplot(111)
# #data_to_plot = [np.array([1, 3]), np.array([4, 6]), np.array([5, 10])]
# data_to_plot = [[1, 3], [4, 6], [5, 10]]
# fig.show()
# #plt.show(fig)
# for dtp in data_to_plot:
#     #bp = ax.boxplot(dtp)#, capprops=dict(color="red"))
#     ax.boxplot(dtp)
#     fig.canvas.draw()
#     time.sleep(1)

#fig.savefig('fig1.png', bbox_inches='tight')
#import time
#time.sleep(10)

fig = plt.figure(1, figsize=(15, 15))
fig.show()
# y = [3, 4, 6, None]
x = np.array([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.9, 1])
y = np.array([0, 1, 2, 3, 4, 5, 6, 20, 100])

ax = fig.add_subplot(1, 1, 1)
z = np.polyfit(x, y, 6)
ax.plot(x, y)
p = np.poly1d(z)
ax.plot(x, p(x))
fig.canvas.draw()
plt.show()

q = np.poly1d([4.34470329e+03, -9.89671083e+03, 8.30071007e+03,
               -3.16340293e+03, 5.35889941e+02, -2.12260766e+01, 3.03372901e-02])

# y.append([0, 5])
# for i in range(1, 5):
#     ax = fig.add_subplot(2, 2, i)
#     z = np.polyfit(x, y, i+3)
#     ax.plot(x, y)
# #ax.plot(x, y[1])
#     p = np.poly1d(z)
#     ax.plot(x, p(x))
#     fig.canvas.draw()
# #ax.set_xlim(0, 15)
#     time.sleep(1)

