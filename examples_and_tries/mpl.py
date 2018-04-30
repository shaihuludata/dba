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
ax = fig.add_subplot(2, 1, 1)
a = [3, 4, 6, None]
ax.plot([1, 4, 6, 10], a)
ax.set_xlim(0, 15)

b = np.arange(10)


time.sleep(5)
plt.show()
