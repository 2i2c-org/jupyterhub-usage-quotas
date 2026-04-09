"""
Script to generate graphical example of how retry time is calculated.

We assume linear behaviour for the sake of simplicity.
"""

import matplotlib.pyplot as plt
import numpy as np

nstep = 1
x_min = 0
x_max = 10
y_min = 0
y_max = 7
quota_limit = 6
x_expire = 1
x_retry = 8
x_current = y_max
transparency = 0.5


x1 = np.arange(x_min, y_max, nstep)
y1 = x1
x2 = np.arange(x1[-1], y_max + 1, nstep)
y2 = x2
x3 = np.arange(x2[-1], x2[-1] + 2, nstep)
y3 = y2[-1::-1]

xc = x2
yc = xc.reshape(-1, 1)
h = np.array([[100, 100], [np.nan, 100]])

fig, ax = plt.subplots(1, 1)

ax.plot(x1, y1)
ax.plot(x2, y2)
ax.plot(x3, y3)
ax.contourf(h, alpha=transparency)
ax.contourf(xc, xc, h, alpha=transparency)
ax.hlines(quota_limit, x_min, x_max, colors="k")
ax.vlines(x_expire, y_min, x_expire, colors="k", linestyle="dashed")
ax.vlines(x_current, y_min, y_max, colors="k", alpha=transparency)
ax.vlines(x_retry, y_min, y_max - 1, colors="k", linestyle="dashed")
ax.set_xlim([x_min, x_max])
ax.set_ylim([y_min, y_max])
ax.set_xlabel("days")
ax.set_ylabel("usage")
ax.set_xticks(np.arange(x_min, x_max, 1))
ax.annotate("$\Delta r$", (y_max + 0.1, y_max - 0.7))
ax.annotate("$t_c$", (x_current + 0.1, 0.2))
ax.annotate("$t_e$", (x_expire + 0.25, 0.2))
ax.annotate("$t_r$", (x_retry + 0.25, 0.2))
ax.set_aspect(0.9)
fig.show()
