import numpy as np
import matplotlib
# matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

# %matplotlib inline
# %config InlineBackend.figure_format='retina'
# библиотеки

def mandelbrot(pmin, pmax, ppoints, qmin, qmax, qpoints,
               max_iterations=200, infinity_border=10):
    image = np.zeros((ppoints, qpoints))
    p, q = np.mgrid[pmin:pmax:(ppoints*1j), qmin:qmax:(qpoints*1j)]
    c = p + 1j*q
    z = np.zeros_like(c)
    for k in range(max_iterations):
        z = z**2 + c
        mask = (np.abs(z) > infinity_border) & (image == 0)
        image[mask] = k
        z[mask] = np.nan
    return -image.T

# инициализиация
pmin, pmax, qmin, qmax = -2.5, 1.5, -2, 2
# пусть c = p + iq и p меняется в диапазоне от pmin до pmax,
# а q меняется в диапазоне от qmin до qmax
ppoints, qpoints = 100, 100
# число точек по горизонтали и вертикали
max_iterations = 300
# максимальное количество итераций
infinity_border = 10
# если ушли на это расстояние, считаем, что ушли на бесконечность

image = mandelbrot(pmin, pmax, ppoints, qmin, qmax, qpoints)

plt.xticks([])
plt.yticks([])

# выключим метки на осях
fig = plt.figure(1, figsize=(15, 15))
fig.show()
ax = fig.add_subplot(1, 1, 1)
ax.imshow(image, cmap='flag', interpolation='none')
fig.savefig("./fractal.png")
plt.close()

# plt.imshow(-image.T, cmap='Greys')
# транспонируем картинку, чтобы оси были направлены правильно
# перед image стоит знак минус, чтобы множество Мандельброта рисовалось
# чёрным цветом\
