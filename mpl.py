import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mp
#mp.use('agg')

fig = plt.figure(1, figsize=(9, 6))
ax = fig.add_subplot(111)
data_to_plot = [np.array([1,2,3]), np.array([4,6]), np.array([5, 10])]
bp = ax.boxplot(data_to_plot, capprops=dict(color="red"))

fig.show()
#fig.savefig('fig1.png', bbox_inches='tight')
import time
time.sleep(10)
