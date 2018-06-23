import numpy as np
import matplotlib
matplotlib.use('cairo')
import matplotlib.pyplot as plt
import time

mu, sigma = 0, 0.1
# s = np.random.normal(mu, sigma, 5000)
# s = np.random.poisson(100, 100)#(10, 20))
# s = np.random.rand(5000)
# s = np.random.pareto(1, 1000)
# s = s/max(s)
# t = np.random.pareto(2, 1000)
# t = t/max(t)
# u = np.random.pareto(3, 1000)
# u = u/max(u)
#s = np.random.lognormal(1, 1, 50)
#s = np.random.logistic(100, 10, 1000)
s = np.random.chisquare(3, 5000)


if abs(mu - np.mean(s)) < 0.01:
    print('да')

if abs(sigma - np.std(s, ddof=1)) < 0.01:
    print('тоже да')

# print(s)
print(min(s), max(s))
print(np.mean(s), np.std(s))

count, bins, ignored = plt.hist(s, 100)
# count, bins, ignored = plt.hist(t, 10, normed=True)
# count, bins, ignored = plt.hist(u, 10, normed=True)
# toplot = 1/(sigma * np.sqrt(2 * np.pi)) * np.exp(-(bins - mu)**2 / (2*sigma**2))
# plt.plot(toplot, linewidth=2, color='r')
# plt.plot(bins, toplot, linewidth=2, color='r')
plt.show()
plt.savefig("./dist.png")

def trynew(**kwargs):
    print(kwargs)
