#!/usr/bin/gnuplot
#
# plots any kind of time series with days on the x-axis
# assumes microseconds as x-input. this script normalizes the microseconds to days.
#
reset

# set color of borders to gray
set style line 11 lc rgb '#808080' lt 1
set border back ls 11
#set border 3 back ls 11 		# enable this if you want only bottom and left borders
set tics nomirror

# line style definitions
set style line 1 lc rgb '#8b1a0e' pt 1 ps 1 lt 1 lw 0.5 # --- red
set style line 2 lc rgb '#5e9c36' pt 6 ps 1 lt 1 lw 2 # --- green

# define grid to be only at x-axis and gray with dotted lines
set style line 12 lc rgb '#808080' lt 0 lw 2
set grid xtics ls 12

# define a second y-axis (e.g. if you want to plot both number of jobs and number of tasks in the same plot)
#
#set y2label "Y2Y2Y2"
#set y2tics auto 			# set this to something else, if you want
#set y2range [0:330]


set   autoscale                        	# scale axes automatically
unset log                              	# remove any log-scaling
unset label                            	# remove any previous labels
set xtic 1                             	# set xtics to 1,2,3,.... If not wanted, use e.g. "set xtic auto"
set ytic auto                          	# set ytics automatically
#set title "XXX"
#set xr [0:20000]
#set logscale x
#set yr [0:1]
set xlabel "Time since 600 seconds before the start of the trace (days)"
set ylabel "XXX"
set terminal pngcairo size 1600,400
set output "XXX.png"
# one day has 86400000000 microseconds

# standard plot (only one y-axis)
plot "XXX.dat" using ($1/86400000000):($2) with lines ls 1 notitle

# Two y-axes, here you have to specify which dataset should be plotted with which y-axis
# plot "DATA1.dat" using 1:2 t 'Y1 TITLE' w lines ls 1 axis x1y1, \
#	"DATA2.dat" using 1:2 t 'Y2 TITLE' w lines ls 2 axis x1y2


