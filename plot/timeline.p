#!/usr/bin/gnuplot
#
# plots any kind of time series with days on the x-axis
#
reset

# set color of borders to gray
set style line 11 lc rgb '#808080' lt 1
set border back ls 11
#set border 3 back ls 11 		# enable this if you want only bottom and left borders
set tics nomirror

# line style definitions
set style line 1 lc rgb '#f1595f' pt 1 ps 1 lt 1 lw 2 # --- red
set style line 2 lc rgb '#79c36a' pt 1 ps 1 lt 1 lw 2 # --- green
set style line 3 lc rgb '#599ad3' pt 1 ps 1 lt 1 lw 2 # --- blue
set style line 4 lc rgb '#f9a65a' pt 1 ps 1 lt 1 lw 2 # --- orange
set style line 5 lc rgb '#6e66ab' pt 1 ps 1 lt 1 lw 2 # --- violett

# define grid to be only at x-axis and gray with dotted lines
set style line 12 lc rgb '#808080' lt 0 lw 2
set grid xtics ls 12

# define a second y-axis (e.g. if you want to plot both number of jobs and number of tasks in the same plot)
#
#set y2label "Y2Y2Y2"
#set y2tics auto 			# set this to something else, if you want
#set y2range [0:330]
set key font ",14"

set   autoscale                        	# scale axes automatically
unset log                              	# remove any log-scaling
unset label                            	# remove any previous labels
set xtic auto font ",16"                # set xtics to 1,2,3,.... If not wanted, use e.g. "set xtic auto"
set ytic auto font ",16"               	# set ytics automatically
set title "Latency test on Amazon instances (micro)"
#set xr [0:20000]
#set logscale x
#set yr [0:1]
set xlabel "Time since start of test (s)" font ",16"
set ylabel "Response time (s)" font ",16"
set terminal pngcairo size 1000,500
set output "timeline.png"

# Two y-axes, here you have to specify which dataset should be plotted with which y-axis
plot "../benchmark/t2_in.dat" using 1:($2/1000) t '2 Workers' w lines ls 2, \
	"../benchmark/t4_in.dat" using 1:($2/1000) t '4 Workers' w lines ls 3, \
	"../benchmark/t8_in.dat" using 1:($2/1000) t '8 Workers' w lines ls 4, \
    "../benchmark/ta_in.dat" using 1:($2/1000) t 'autoscaling' w lines ls 5


